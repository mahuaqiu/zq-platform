# 配置中心设计（含 OCR 服务文本替换联动）

日期：2026-09-11
状态：已评审定稿（页面设计稿 v3 经用户确认，含决策：值列=键值对标签每对一行、编辑=键值对编辑器、批量粘贴导入=要、通用键/值表述不绑定 OCR）

## 背景与目标

OCR 识别偶发错字（如「允许」→「充许」、「聊天」→「聊关」），影响下游自动化使用。方案：

1. 测试平台（zq-platform）新增通用「配置中心」模块：可视化维护键值对配置，并提供外部免鉴权查询接口。
2. OCR 服务（ocr_service）启动时拉取 `ocr_config` 配置，在拿到原始识别结果后、任何 `reg_`/文本匹配之前对识别文本做整串替换；每天 12:00 定时拉取刷新。

配置中心是通用键值对存储，不绑定 OCR 场景；`ocr_config` 只是首个配置项。

## 范围

**做：**
- zq-platform 后端：`core/config_center` 模块（新表、管理 CRUD、免鉴权查询接口）+ alembic 迁移 + 菜单初始化。
- zq-platform 前端：配置中心页面（列表 / 键值对编辑抽屉 / 查看弹窗 / 批量粘贴导入）。
- ocr_service：文本替换单例、配置拉取客户端、启动拉取、每日 12:00 定时刷新、识别文本替换。

**不做（YAGNI）：**
- 值的其他 JSON 类型（数组/嵌套对象/纯字符串）——固定为「字符串 → 字符串」的键值对字典。
- 配置变更历史/审计、配置版本、灰度发布。
- Permission 表权限点初始化（Permission 无记录时中间件默认放行，管理接口仅要求登录）。
- ocr_service 的其他定时任务框架（不引入 APScheduler，用 asyncio 循环）。

## 一、zq-platform 后端

### 数据模型（新表 `config_center_item`）

继承 `app.base_model.BaseModel`（id/sort/is_deleted/时间戳/操作人）：

| 字段 | 类型 | 说明 |
|------|------|------|
| key | String(64), not null | 配置键，活动记录内唯一（部分唯一索引 `postgresql_where=is_deleted=false`，参照 config_template 惯例） |
| value | Text, not null | 配置值：JSON 对象字符串，如 `{"充许":"允许","聊关":"聊天"}`（键值对按编辑顺序存储） |
| remark | Text, nullable | 备注 |

模块文件：`backend-fastapi/core/config_center/{__init__,model,schema,service,api,public_api}.py`。

### 校验规则

- key：正则 `^[A-Za-z0-9_-]{1,64}$`，活动记录内唯一（服务层校验，创建/更新时返回 400）。
- value：`json.loads` 后必须是 dict，且所有键值均为 str（Pydantic field_validator 双重校验；前端键值对编辑器天然保证）。
- 更新时 key 不可修改（schema 更新模型不含 key；接口层忽略）。

### 管理端 API（需登录，挂在 core_router 下）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/core/config-center | 分页列表，query: page/page_size/keyword（key/remark ilike）/返回 PaginatedResponse |
| POST | /api/core/config-center | 创建（校验 key 唯一） |
| GET | /api/core/config-center/{item_id} | 详情 |
| PUT | /api/core/config-center/{item_id} | 更新（key 不可改） |
| DELETE | /api/core/config-center/{item_id} | 软删除，返回 `{"status":"success","message":"删除成功"}` |
| GET | /api/core/config-center/check/key | key 唯一性校验（query: key, exclude_id），供表单实时校验 |

路由注册：`core/router.py` 增加两行（import + include）。

### 免鉴权外部查询接口

- 路径：`GET /api/public/config-center/query?key={key}`
- 挂载：`main.py` 单独 `app.include_router(public_config_center_router)`（参照 `public_config_template_router` 惯例，router 前缀写绝对路径 `/api/public/config-center`）。
- 鉴权：中间件已有白名单正则 `^/api/public/.*`，**无需改动 auth_middleware**。
- 响应：直接返回解析后的字典本身（不包 envelope）：
  - 200：`{"充许":"允许","聊关":"聊天"}`
  - 404：`{"detail":"配置项不存在: xxx"}`
  - 500：`{"detail":"配置项 value 不是合法的 JSON 对象"}`（正常流程不会出现，管理端已保证）
- 只提供按 key 的单点查询，不提供列表/枚举接口，减小免鉴权面。

## 二、zq-platform 前端（web/apps/web-ele）

### 菜单与路由

- 菜单：`scripts/init_all_menus.py` 的 ALL_MENUS 增加 `system-config-center`（name: SystemConfigCenter，title: 配置中心，path: /system/config-center，type: menu，component: /views/config-center/index，parent_id: system-root，order: 7）。
- 前端路由模块：`src/router/routes/modules/config-center.ts`（hideInMenu: true，仅做组件映射，mixed 模式下菜单由后端下发）。

### 页面结构（views/config-center/）

- `index.vue`：useZqTable 列表页（defineOptions name 必须为 SystemConfigCenter 以支持 keepAlive）。
  - 搜索表单：配置键（Input）、备注（Input）。
  - 工具栏：新增配置、批量删除；右侧刷新/全屏/列设置（toolbarConfig）。
  - 列：序号 | 配置键（等宽字体）| 配置值（键值对）| 备注 | 更新时间 | 操作（编辑/查看/删除）。
  - 配置值列：每对键值一个浅蓝标签「键 → 值」，**每对独占一行**竖排；超过 15 对（约 200px 高）单元格内部滚动，不撑开行高；标签下方小字「共 N 对」。删除/批量删除均有确认框。
  - 错误提示遵循平台约定：请求失败只由请求层全局拦截器弹一次，页面 catch 不再 ElMessage.error。
- `data.ts`：useZqTableColumns + 搜索表单 schema。
- `modules/form.vue`：ZqDrawer（700px）编辑表单。
  - 字段：配置键（编辑态禁改）、备注、配置值（键值对编辑器）。
  - 键值对编辑器：表格（键 | → | 值 | 删除），至少 1 对，键非空且不重复（前端校验），行数多时区域内部滚动（约 480px），「＋添加」按钮。
  - **批量粘贴导入**：弹窗粘贴多行文本，每行一条 `键=值`（分隔符支持 `=`、`，`/`,`、Tab、`→`），解析预览后填入键值对表格，可继续修改再保存。
- 「查看」弹窗：只读两列表格（键 | 值），内容多时区域滚动。
- API 封装：`src/api/core/config-center.ts`（不加入 api/core/index.ts re-export，遵循大模块惯例）。

## 三、ocr_service

### 新文件 `ocr_service/text_replacer.py`

- 替换字典单例（参照 config.py 的 get/set 惯例）：`get_replace_map() -> dict[str,str]`、`set_replace_map()`；空字典 = 不替换（零开销直通）。
- `apply_replacements(text: str) -> str`：按配置顺序逐对 `str.replace(键, 值)`。
- `fetch_replace_map() -> dict`（async，httpx.AsyncClient）：`GET {OCR_CONFIG_CENTER_URL}?key={OCR_CONFIG_CENTER_KEY}`；校验响应为 `dict[str,str]`，非法则抛异常。
- `refresh_replace_map() -> bool`：拉取成功 → set_replace_map 并记 `[CONFIG]` INFO 日志；失败 → 保留旧配置并记 ERROR 日志（服务不断/不空窗）。

### 配置项（config.py，环境变量）

| 变量 | 默认 | 说明 |
|------|------|------|
| OCR_CONFIG_CENTER_URL | ""（空=功能禁用） | 平台免鉴权查询地址，如 `http://<platform>:8000/api/public/config-center/query` |
| OCR_CONFIG_CENTER_KEY | "ocr_config" | 拉取的配置键 |
| OCR_CONFIG_CENTER_TIMEOUT | 5.0 | 请求超时（秒） |

### 替换应用点（core/ocr_engine.py）

`OCREngine.recognize()` 中 `OCRResult.parse_from_paddleocr(...)` 解析出 TextBlock 列表后，立即对每个 `TextBlock.text` 应用 `apply_replacements`。此时机：

- 早于所有 `reg_` 正则/exact/contains 匹配（filter_texts、get_coord_by_text、match_near_text 均基于 TextBlock.text），满足「在 reg_ 操作之前」；
- `find_text`/`find_all_texts`/`get_text_center` 内部都经由 `recognize()`，自动覆盖；
- 响应里的 `ocr_info` 一并呈现替换后的文本（所见即所得）。

`[OCR_RAW]` 日志在替换前打印，保留原始识别结果便于排查。

### 启动拉取与定时刷新（server.py）

- `create_app()` 改用 `lifespan` 异步上下文（app 仍在模块期创建，钩子放 lifespan 避免阻塞 import）：
  - 启动：若 `OCR_CONFIG_CENTER_URL` 非空，拉取配置，重试 3 次（间隔 2s/4s）；全部失败不阻塞启动（空字典继续，由定时器兜底再拉）。
  - 后台任务（asyncio.create_task）：休眠至下一个本地时间 12:00 → 刷新；失败则每 10 分钟重试直至成功 → 再休眠至下一个 12:00。关闭时取消任务。
  - 未配置 URL：完全跳过（功能禁用，零行为变化）。
- 日志：`RequestResponseFilter` 放行标签增加 `[CONFIG]`，保证配置拉取/刷新日志进入 ocr.log。
- 多 worker：每个 worker 进程各自拉取/刷新（幂等，可接受）；Docker `TZ=Asia/Shanghai` 保证 12:00 为本地正午。

### 测试（tests/test_text_replacer.py，pytest，风格对齐现有测试）

- `apply_replacements`：基本替换、多对、顺序叠加、空字典直通。
- `fetch_replace_map`：httpx.MockTransport 模拟 200 字典 / 非 dict / 非法 JSON / 404。
- `refresh_replace_map`：失败保留旧值。
- 下一个 12:00 的计算（含跨天边界）。
- 不触碰真实 PaddleOCR 引擎。

## 数据流总览

```
[页面] 键值对编辑器 → POST /api/core/config-center (value={"充许":"允许",...})
                                              │
[ocr_service 启动/每日12:00] ──GET /api/public/config-center/query?key=ocr_config──▶ PostgreSQL
        │ 200 {"充许":"允许",...}
        ▼
replace_map 单例 ──▶ recognize() 解析后逐块 str.replace ──▶ reg_/exact 匹配（不受影响地匹配到正字）
```

## 部署步骤

1. zq-platform：`alembic upgrade head`（新迁移文件 `add_config_center_item`）。
2. zq-platform：`python scripts/init_all_menus.py`（会清空并重建菜单表，管理员角色自动分配全部菜单）。
3. 重启后端与前端。
4. ocr_service：设置 `OCR_CONFIG_CENTER_URL` 指向平台后重启（Docker 同步在 docker-compose.yml 增加该变量）。
5. 页面「系统管理 → 配置中心」新增 `ocr_config` 键值对。

## 验收路径

1. 管理端 CRUD 正常；key 重复被 400 拦截。
2. `curl 'http://<platform>:8000/api/public/config-center/query?key=ocr_config'`（无 Token）返回 `{"充许":"允许",...}`；不存在的 key 返回 404。
3. ocr_service 启动日志出现 `[CONFIG]` 拉取成功（N 对规则）。
4. OCR 识别含「充许」的图片：`get_ocr_texts` 返回「允许」；`get_coord_by_text` 用 `filter_text=允许`（含 `reg_允[许]`）能命中；用 `filter_text=充许` 不再命中（符合预期）。
5. 手动改配置后，等 12:00 或重启服务，新规则生效；拔掉平台后重启 ocr_service，服务可用（空规则），日志有 ERROR。

## 风险与权衡

- **链式替换**：配置顺序执行 `str.replace`，若同时配 A→B、B→C 会产生 A→C 叠加；属预期行为，页面备注提醒即可。
- **免鉴权面**：仅暴露单 key 查询、key 格式受限、不提供枚举；平台部署在内网。
- **替换影响匹配语义**：替换后「充许」作为 filter_text 不再命中（需用正字查询），这正是需求本意。
- **多 worker 重复拉取**：幂等 GET，量级为每日 1 次 + 启动 1 次，可忽略。
