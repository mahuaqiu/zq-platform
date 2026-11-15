# 场景回放（录制标注导出）功能设计

- 日期：2026-11-15
- 状态：设计定稿（UI 定稿原型 v7：`docs/mockups/scenario-replay.html`）
- 涉及仓库：zq-platform（本仓库，主体）、autotest（worker 小改）、testcase（新 SKILL，独立交付）

## 1. 背景与目标

### 1.1 现状痛点

testcase 仓库当前用 `testcase-create` skill 从手工文本用例生成 pytest 用例，已知易错点（有代码证据）：

1. **文本与代码漂移**：文本写"开启等候室"，代码 `enable=False`（test_waitingroom_001.py 实例）
2. **步骤遗漏**：文本 1 步实际是多个原子操作（离会+断言+入会+断言）
3. **正则易错**：OCR 文字需 `reg_` 前缀正则，转义/异体字（帐/账）靠手工
4. **图片模板缺失**：`image_click` 依赖事先截好的模板图

根因：AI 只有文本意图，没有"实际界面长什么样、实际点了什么"的事实依据。

### 1.2 目标

在测试平台新增「场景回放」模块：测试人员申请设备、**远程操作真实设备录制操作步骤**（每步自动截图），在编辑器里**挑选/标注/插入验证点**，**导出结构化步骤包**，由新 SKILL 结合文本用例生成合规范的 testcase 用例。

### 1.3 边界（明确不做）

- **平台不做执行/回放**：执行验证由 testcase 工程 pytest 承担（经评审移除了真实执行回放）
- **不做用例管理**：用例体系仍在 testcase 仓库，平台只到"导出"为止
- **不做物理设备直操作**：一期只支持投屏页远程操作（设备端输入监听为远期演进）

## 2. 总体流程与状态机

```
新建场景(配置用户+标签) → 申请占用设备 → 录制工作台(投屏操作,自动截图)
   ├─ 放弃退出 → 场景删除,不出现在列表
   └─ 结束并保存 → 场景编辑(树状时间线标注) → 导出(md+截图包) → SKILL 生成用例
```

场景状态机（对应列表展示规则）：

| 状态 | 含义 | 列表展示 | 可用操作 |
|---|---|---|---|
| `draft`（录制中） | 已申请设备、尚未保存 | 显示"录制中·未保存" | **继续录制 / 放弃**（无编辑/导出） |
| `saved` | 录制完成已保存 | 正常行 | 编辑 / 导出步骤 / 复制 / 删除 |
| （放弃） | draft 被放弃 | **不显示**（软删） | — |

规则（用户确认）：
- 用户数量在新建时确定，录制中不可增减
- 保存后才可编辑/查看；放弃未保存的列表不显示
- 单次占用最长 **30 分钟**，录制页打开期间自动续期，超时自动释放并终止录制

## 3. UI 设计（定稿依据：原型 v7）

菜单：一级目录「场景回放」→ 子菜单「场景列表」「录制场景」；编辑页 `hideInMenu`（`/scenario-edit/:id`）。按平台惯例：前端 `views/scenario/` + `routes/modules/scenario.ts` + `init_all_menus.py` 增种子。

### 3.1 场景列表

- 搜索（名称/创建人/标签）
- 列：勾选、场景名称（占用中带标记）、场景用户 chips（颜色按用户，A 蓝/B 绿/C 紫/D 橙）、创建人、最近更新、操作
- 操作按状态机出按钮（见第 2 节表格）
- 新建录制场景 → 配置弹窗：名称/描述/设备池(namespace)/场景用户（user+标签行，可增删）→ 申请设备

### 3.2 录制工作台

- 顶栏：返回（触发放弃确认）、场景名、录制中标记+计时、**占用倒计时（剩余 mm:ss）**、放弃退出、结束并保存
- 用户 Tab（数量=开场配置，不可增减），切 Tab 切换投屏面板
- 单大屏投屏面板（复用 device-debug 的 `useWebSocket/useScreenInteraction`，contain 适配）；**在画面上直接操作即自动录制**
- **插入步骤（截取全部设备）**：位于画面与操作流之间；一次截取所有设备当前画面，插入一个多截图步骤节点（不切换 Tab 抢时间）
- 操作流（最新在上，不自动滚动）：缩略图、用户、操作类型标签（**点击可重新归类**）、内容、时间、状态；每次操作自动截取操作前画面
- 结束保存弹窗：汇总 + "保存后释放设备"勾选

### 3.3 场景编辑器（Git 图树状时间线）

- 顶栏：返回、场景名、用户 chips、保存态、插入 AW、撤销(Ctrl+Z，30 步)、导出步骤、保存
- 工具行：筛选（全部/userA/userB/…/已禁用，按场景用户动态生成）+ 步骤搜索
- **中央加粗主干线（8px，每用户一条，颜色同用户）+ 泳道头（吸顶：徽标/名称/标签/设备名）**
- 步骤卡片**按用户就近固定同侧**（线偏左→全在左，否则全在右），向中间靠齐（内边缘距中线 70px，宽度 fit-content）
- 卡片：勾选框、缩略图（点击→灯箱大图）、编号、用户徽标、类型标签（点击→重新归类菜单）、内容、来源（手动插入/验证）、验证点计数；悬停浮出：编辑/上移/下移/禁用/删除
- 点击卡片 → 右侧抽屉：大图 + OCR 热区（点文字即选为定位目标）、设为验证点/框选图片模板/重截此图、属性表单（按类型出字段，对齐 worker Action）、验证点增删、备注
- 灯箱：大图 + 步骤信息，Esc/空白关闭
- 批量：勾选 ≥1 浮出批量条（批量删除/禁用/启用/全选当前显示/取消）
- 插入 AW 弹窗：cmd_exec / start_app / stop_app / navigate / press / wait（追加到时间线末尾，可↑↓调序）

### 3.4 操作类型清单（对齐 testcase BaseAW 常用原子操作，分组菜单）

- 点击：ocr_click / image_click / click
- 输入：ocr_input / input / paste
- 手势按键：swipe / scroll / press
- 验证（选即转验证点）：ocr_wait / ocr_assert / image_assert / ocr_exist
- 应用/系统：start_app / stop_app / cmd_exec / navigate / wait
- 手动截图（快照节点）

## 4. 数据模型（新增 `core/scenario/` 模块，四件套：model/schema/service/api）

```
scenario_scenario
  id uuid pk; name; description
  namespace text                    -- 设备池
  users_config jsonb                -- [{user:"A", tag:"web"}]
  status text                       -- draft | saved
  recording_session_id uuid null    -- 进行中的录制会话
  created_by / sys_create_datetime / is_deleted ... (继承 BaseModel)

scenario_step
  id uuid pk; scenario_id fk; seq int          -- 全局顺序(含跨用户交错)
  user text;                                    -- A/B/C...
  source text                                   -- recorded | manual | verify
  action_type text                              -- ocr_click / input / cmd_exec ...
  action_params jsonb                           -- 对齐 worker Action 字段
                                                --   ocr_click: {target, match_mode, timeout}
                                                --   image_click: {tpl, threshold}
                                                --   ocr_input: {target, value}
                                                --   cmd_exec: {value, background}
  screenshot_id uuid null                       -- 操作前截图
  extra_shots jsonb null                        -- 插入步骤的多设备截图 [{user, shot_id}]
  enabled bool default true
  note text null

scenario_screenshot
  id uuid pk; scenario_id fk; file_path         -- 本地盘相对路径
  width int; height int
  ocr_result jsonb null                         -- 懒加载: [{text, bbox, center}]
```

存储：截图存本地磁盘 `settings.SCENARIO_SCREENSHOT_PATH`（参照 test_report 的本地盘+URL 模式），URL 由静态路由提供。

状态机实现：新建录制即插 `scenario_scenario(status=draft, recording_session_id)`；结束保存 → `status=saved`；放弃 → 软删（`is_deleted=true`）+ 释放设备。

## 5. 录制链路（平台 ↔ worker 接口）

### 5.1 设备占用（复用 env_machine 现有能力）

- 申请：`POST /api/core/env-machine/{namespace}/application`，body `{"userA":"web","userB":"windows"}`（即场景 users_config）
- 续期：录制页打开期间前端定时 `POST /keepusing`
- 释放：放弃/保存勾选释放/超时，调 `POST /release`
- 30 分钟上限：平台录制会话记录起始时间，前端倒计时展示；到点平台侧强制 `release` 并经 WS 通知前端终止录制（即使前端已关闭也能释放——后台兜底任务对超时 recording_session 执行释放）

### 5.2 操作事件捕获（关键新能力，worker 为唯一捕获点）

统一在 worker 侧实现录制会话，两条控制通道都经过它：

- **WS 实时指针**（harmony_mobile / harmony_pc / windows）：前端已有 WS input 事件流（`receive_activity`）。新增录制钩子：record 会话激活时，收到 `pointer down` → **先截操作前图** → 注入 → 记录事件
- **REST 手势**（iOS / Android / web 兜底）：平台 `/debug-action` → worker `/remote/execute`。record 会话激活时，`execute_remote_sync` 入口同样先截操作前图再执行动作
- 手动插入步骤（多设备快照）：平台收到请求后并行调各设备 `/remote/execute` 的 `screenshot`，聚合成一个步骤

worker 新增接口（`worker/server.py`）：

```
POST /remote/record/start  {device_id, scenario_id, user}   -- 开始该设备录制会话
POST /remote/record/stop   {device_id}                       -- 结束（释放录制动资源）
```

worker → 平台回传步骤（新增平台接口）：

```
POST /api/core/scenario/{scenario_id}/steps/batch
  [{user, source, action_type, action_params, screenshot_b64, client_time}]
```

平台落库（存截图文件、建 step）→ 经既有 `/ws/notifications` 推前端刷新操作流。

### 5.3 场景 CRUD 与导出（平台新增，注册进 core/router.py）

```
POST   /api/core/scenario                        -- 新建（含 users_config）
GET    /api/core/scenario                        -- 列表（分页/筛选）
GET    /api/core/scenario/{id}                   -- 详情（含 steps + screenshots）
PUT    /api/core/scenario/{id}                   -- 保存（steps 全量替换, 状态转 saved）
DELETE /api/core/scenario/{id}                   -- 删除
POST   /api/core/scenario/{id}/steps/batch       -- worker 回传录制步骤（内部）
POST   /api/core/scenario/{id}/insert-snapshot   -- 插入步骤(截全部设备)
POST   /api/core/scenario/{id}/start-record      -- 开始录制(分配结果+通知各 worker record/start)
POST   /api/core/scenario/{id}/stop-record       -- 结束录制
GET    /api/core/scenario/{id}/export            -- 导出 zip(md + screenshots/)
GET    /api/core/scenario/{id}/ocr/{shot_id}     -- 某截图的 OCR 热区(懒加载调 OCR 服务)
```

OCR：编辑器打开步骤时按需调 `/ocr/{shot_id}`；平台经 worker 转发 OCR 服务 `POST /ocr/get_ocr_infos`，结果缓存进 `scenario_screenshot.ocr_result`。

## 6. 导出物契约（唯一格式：Markdown + 截图包）

导出 = zip：`{场景名}.md` + `screenshots/stepNN.png`。**已禁用步骤不导出**（头部注明条数）。

固定模板（SKILL 解析约定，字段行不可变）：

```markdown
# 场景：{name}
- 设备池: {namespace}
- 用户: userA=web, userB=windows, ...
- 步骤: {total}（启用 {enabled}，已禁用 {disabled} 不导出）
- 验证点: {count}
- 导出时间: {ts}

## STEP {seq} [user{X}·{tag}] {类型名}
- 动作: {action_type}
- 目标文字: {target}            # ocr_click/ocr_input/ocr_wait/ocr_assert
- 输入内容: {value}             # input 类
- 命令: {value}                 # cmd_exec（@tools/ 占位符保留）
- 匹配: {match_mode} · 超时 {timeout}ms
- 截图: screenshots/step{seq}.png
- 验证点: {sub}「{target}」{timeout}s   # 可多行
- 备注: {note}
```

字段清单及用途（SKILL 消费视角）：

| 字段 | 用途 |
|---|---|
| seq + user | 执行顺序与跨用户交错（parallel 分组依据） |
| action_type + action_params | 原子 AW 直出原料 |
| 操作前截图 | AI 看界面 / 业务 AW 匹配的视觉证据 / 图片模板裁剪源 |
| 验证点 | 直接映射 `should_*` 断言 |
| 备注（一句话，可选） | 意图补充；描述性文字由文本用例提供 |

## 7. 新 SKILL：`testcase-from-scenario`（testcase 仓，独立交付）

**新建独立 skill**，不改造 `testcase-create`（输入源与校验方向不同）。AW 对齐是 SKILL 的职责，导出物保持平台无关。

输入：导出包（md + screenshots/）+ 文本用例（docstring 或 md）。

五步流程：

1. **对齐（先于生成，人工确认）**：文本 STEP ↔ 录制步骤做覆盖对照表，输出给人确认
   - 文本步骤数 < 录制原子操作数 → 标出疑似遗漏的子步骤
   - 文本与录制事实冲突（如"开启等候室"与录制操作不符）→ 以录制为准并标红
2. **复用优先**：每步先匹配业务层 AW（读 `AGENTS.md` + `aw/INDEX.md` + 平台 INDEX + 相似用例，最多读 4 个）；匹配不到 → 用录制事实组合原子 AW；全新操作 → 标"需新建 AW"（按 `testcase-aw` 规则一次一个）
3. **事实回填**：参数一律取录制值——OCR 文字用真实命中文字（异体字/转义自动正确）、图片模板从截图裁剪、等待取录制间隔；禁 `time.sleep`（用 `self.wait`）
4. **断言合并**：录制验证点 + 文本 EXPECT → `should_*`；文本有 EXPECT 但录制无验证 → 标黄问人
5. **生成 + 复查**：标准模板生成（docstring 场景、`@pytest.mark.users`、`# STEP n` 注释、parallel 块、断言放块外），并执行 testcase-create 既有的复查清单（步骤覆盖表/命名/索引同步）

## 8. 错误处理

| 场景 | 处理 |
|---|---|
| 申请设备失败（无可用/标签不匹配） | 展示 fail_reason，可重试申请 |
| 占用超 30 分钟 | 平台强制 release + WS 通知前端终止；后台兜底任务清理超时 draft 会话（防前端关闭后泄漏） |
| 投屏 WS 断开 | 自动重连（复用 device-debug 逻辑）；步骤已实时落库，不丢失 |
| worker 截图失败 | 步骤照常记录，screenshot_id 空，编辑器提供"重截此图" |
| 录制中设备离线 | 该用户 Tab 标记离线，停止录入该设备；恢复后可继续 |
| 录制页直接关闭（未走放弃/保存） | 前端 beforeunload 尽力调 stop-record；兜底任务 30 分钟超时释放 |

## 9. 测试策略

- 后端单测：scenario 状态机（draft→saved / 放弃软删）、steps/batch 落库、导出生成器（模板渲染/禁用过滤/截图打包）、超时会话清理
- worker 单测：record 会话下 pointer/REST 两通道的"先截图后注入"顺序、多设备快照聚合
- 集成：worker 回传 → 平台落库 → WS 推送全链路
- 前端：对照原型 v7 手动验收 + 关键交互（批量/撤销/归类菜单）
- SKILL：用真实导出包（试点场景：会议等候室）生成用例并人工评审

## 10. 分期

- **一期（本设计范围）**：平台内闭环——录制/编辑/导出 + worker 录制会话 + `testcase-from-scenario` v1（对齐+生成）
- **二期候选**：物理设备直操作的输入监听评估、AW 智能推荐（基于历史用例 embedding）、导出格式扩展（如需机器流水线消费再议 JSON）

## 11. 设计决策记录（评审定稿）

| 决策 | 结论 | 时间 |
|---|---|---|
| 操作方式 | 投屏页远程操作（复用 device-debug） | 第 1 轮 |
| 截图时机 | 每次操作仅截操作前一张；结果画面用"插入步骤"补 | 第 5 轮 |
| 回放执行 | 平台不做执行；验证交给 testcase 工程 pytest | 第 2 轮 |
| 用户数量 | 新建时定死，录制中不可增减 | 第 3 轮 |
| 暂停 | 无暂停；放弃退出（未保存不进列表）或结束保存 | 第 3 轮 |
| 占用上限 | 单次 30 分钟，页面自动续期，超时强制释放 | 第 4 轮 |
| 编辑器形态 | Git 图树状时间线，主干线 8px，同用户固定同侧 | 第 3/6/7 轮 |
| 导出格式 | 仅 Markdown + 截图包；JSON 取消（消费方是 SKILL） | 第 8 轮 |
| AW 对齐 | 归 SKILL；导出物保持平台无关 | 第 8 轮 |
| 生成流程 | 先对齐（人工确认对照表）再生成；事实回填；复用优先 | 第 8 轮 |
