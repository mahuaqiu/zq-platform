# IP 模板弹窗重做设计

- 日期：2026-07-08
- 模块：`/env-machine/config` 页面（前端 `web/apps/web-ele/src/views/env-machine/config.vue` + 后端 `backend-fastapi/core/config_template/`）
- 状态：设计已确认，待转实现计划

## 1. 背景与目标

`/env-machine/config` 页面的「使用 IP 模板」与「保存为 IP 模板」两个弹窗当前功能过简：

- 「使用 IP 模板」弹窗每个模板只显示 `包含 N 台机器`，看不到具体哪些 IP。用户勾了几十台 IP、存成模板后，无法核对模板里到底有哪些机器、是否还在、是否离线。
- 点「使用」直接整体替换主表格 `selectedMachineIds`，无预览、无二次确认；且应用逻辑 `template.machine_ids.filter(id => allMachineIds.includes(id))` 依赖当前预览过滤后的列表，会静默吃掉被 namespace/device_type/ip 过滤掉的机器，用户不知道少了多少。
- 模板存的是 `machine_ids`（原始 ID）。机器被删后 ID 失效，模板仍显示老数量，无失效提示。
- 「保存为 IP 模板」弹窗只有「名字 + 备注 + 已选择 N 台」，看不到将要保存的具体 IP 列表。
- 整体 UI 简陋。

目标：点开模板能看清内含全部 IP（含在线/离线/已删除状态，不显示 config_version），弹窗内预览并确认应用，失效 ID 明确标出，UI 美观。已与用户确认采用**方案 A（左模板列表 / 右明细表格）**布局，列表与明细均可上下滚动。

## 2. 范围

**改动**：
- 后端 `core/config_template/schema.py`、`machine_selection_template_service.py`、`api.py`
- 前端 `web/apps/web-ele/src/api/core/env-machine-config.ts`
- 前端 `web/apps/web-ele/src/views/env-machine/config.vue`（两弹窗 + 相关逻辑）

**不动**：下发主表格、配置/脚本/命令模板编辑弹窗、任务历史 Tab、命令/脚本下发链路。

## 3. 后端设计

### 3.1 列表接口增加统计字段

`GET /api/core/machine-selection-template` 的响应 `MachineSelectionTemplateResponse` 增加 `resolved_stats` 字段，一次批量查询得出，无需前端二次请求：

```
resolved_stats: {
  total:      int   # 模板 machine_ids 总数
  available:  int   # 在 EnvMachine 中且 is_deleted=false 且 is_virtual=false 的数量
  online:     int   # 上述 available 中 status="online" 的数量
  offline:    int   # available 中 status≠"online" 的数量
  lost:       int   # machine_ids 中不在 EnvMachine（已删除）的数量
}
```

实现：在 `MachineSelectionTemplateService.get_list` 中，对每条模板取 `machine_ids`，聚合所有 id 一次 `select EnvMachine where id in(all_ids) and is_deleted=false and is_virtual=false`，回填每条 stats。空 `machine_ids` 全 0。

### 3.2 新增详情接口

`GET /api/core/machine-selection-template/{id}/machines` 返回该模板全部 `machine_ids` 的明细，前端点开某模板时异步拉取：

```
{
  "template_id": "uuid",
  "machines": [
    {
      "id": "uuid",
      "ip": "10.0.1.21" | null,
      "device_type": "windows" | null,
      "status": "online" | null,
      "exists": true | false
    }
  ]
}
```

`exists=false` 表示该 id 在 EnvMachine 中不存在（已删除），`ip/device_type/status` 为 null。前端据此标红划线、checkbox 禁用。明细**不含** `config_status` 与 `config_version`（用户明确不需要）。

实现：`MachineSelectionTemplateService.get_machines_detail(template_id)` → 取模板 `machine_ids` → 批量查 EnvMachine → 对每个 id 回填（缺失的 `exists=false`）。

### 3.3 Schema 新增

- `MachineSelectionTemplateStatsResponse`：上述 stats 五字段。
- `MachineDetailResponse`：id/ip/device_type/status/exists。
- `MachineSelectionTemplateDetailResponse`：template_id + machines 列表。
- `MachineSelectionTemplateResponse` 增加 `resolved_stats: MachineSelectionTemplateStatsResponse`。

## 4. 前端设计

### 4.1 API (`env-machine-config.ts`)

- 改 `MachineSelectionTemplate` 接口加 `resolved_stats` 字段。
- 加 `getIpTemplateMachinesApi(id)` → `GET /machine-selection-template/{id}/machines`，返回 `MachineSelectionTemplateDetail`。

### 4.2「使用 IP 模板」弹窗（方案 A）

布局（弹窗宽度 880px，圆角 12px，渐变头部沿用 `deploy-confirm-dialog` 风格）：

```
标题: 使用 IP 模板
├─ 左栏 (380px, 内部 overflow-y auto): IP 模板列表
│   每条 = 模板名 + 胶囊行 [命中/已删除/离线]
│   选中态: 1.5px #1890ff 边 + #e6f7ff 底
├─ 右栏 (flex 1, 三段纵向):
│   ├─ 顶bar: 模板名 + 备注 + IP 过滤 input（过滤右栏明细）
│   ├─ 统计胶囊行: 可应用N 已删除N 离线N
│   ├─ 明细表格 (flex 1, 内部 overflow): checkbox | IP | 类型 | 状态
│   │   在线绿点 / 离线黄点 / 已删除红 ✕ + IP 划线灰 + checkbox disabled
│   │   表头全选只勾「可应用」项
│   └─ 底bar: 已勾选N台 + [应用到下发列表]
└─ footer: [关闭]
```

行为：
- 打开弹窗 → 拉改造后的列表接口（含 stats）。默认选中第一个模板。
- 选中模板 → 异步拉 `getIpTemplateMachinesApi(id)`，右栏渲染明细；拉取中显示 loading。
- 明细「可应用」= `exists && status=online`。全选只勾可应用项；已删除/离线 checkbox disabled 默认不勾。
- 「应用到下发列表」→ 把勾选项设为主表格 `selectedMachineIds`，关闭弹窗。
- **与主表格可选约束取交集**：主表 `selectableMachines = config_status==="pending" && device_type∈{windows,mac}`。应用时只取 (勾选中可应用) ∩ (主表 selectable) 的交集为最终选中，并用 `ElMessage` 提示被过滤数，如 `模板含 58 台，其中 53 台可下发，5 台已同步/离线已忽略`。
- 交集为空 → `ElMessage.warning`，不关闭弹窗。

滚动保障：左栏列表、右栏明细表格均独立 `overflow-y: auto`，模板多/IP多均可上下滑动。

### 4.3「保存为 IP 模板」弹窗增强

```
标题: 保存为 IP 模板
├─ 模板名 input *
├─ 备注 input
├─ 将保存明细预览 (max-height 200px, 内部滚动):
│   统计行: 共N台 (在线X 离线Y)
│   紧凑表格: IP | 类型 | 状态
└─ footer: 取消 / 保存
```

数据来源：`selectedMachineIds` 反查当前内存中的 `previewData.machines`（已在内存，无需新接口），列 IP/类型/状态。保存内容仍为 `machine_ids`（不变）。

### 4.4 美观要点

- 弹窗收口 720~880px，圆角 12px，渐变头部沿用现有 `deploy-confirm-dialog` 风格统一。
- 胶囊沿用现有色板：`#e6f7ff/#1890ff`、`#fff1f0/#ff4d4f`、`#fafafa/#999`。
- 左栏底色 `#fafbfd`，选中项 `1.5px #1890ff` 边 + `#e6f7ff` 底。
- 明细表沿用主 `preview-table` 的 `:deep()` 样式（已有，复用）。
- 已删除行：背景 `#fff7f6`、IP 划线灰、状态红 ✕。

## 5. 边界与错误处理

- 拉 stats 失败 → 该模板项显示「统计加载失败」灰色，不阻断点开。
- 拉明细失败 → 右栏错误态 + 「重试」按钮。
- 模板 `machine_ids` 为空 → stats 全 0，明细空表 + 提示「该模板未保存机器」。
- 应用时交集为空 → `ElMessage.warning`，不关闭弹窗。
- 已删除机器不计入可应用，永不勾选。

## 6. 测试

- 后端：`MachineSelectionTemplateService.resolve_stats` 对 [全在线 / 全离线 / 全删除 / 混合 / 空 ids] 五种 case 单测。
- 后端：新详情接口返回结构 fixture 测。
- 前端手测三场景：全可用模板应用、含已删除模板应用并看过滤提示、空模板打开。
- 不写前端单测（项目无前端单测惯例，沿用）。

## 7. 不做（YAGNI）

- 不加 IP 模板编辑弹窗（模板靠「保存为」重建即可）。
- 不支持多模板并集应用（本轮只覆盖式应用）。
- 不接入 `namespace`/`device_type`/`ip_pattern` 筛选字段（model 已有但前端未用，本轮不接入，避免范围蔓延）。
- 明细不显示 `config_status` 与 `config_version`（用户明确不需要）。
