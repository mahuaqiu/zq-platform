# 运行命令模板与 IP 模板功能设计

## 需求背景

1. 设备列表页面的"批量执行命令"功能需要重构：
   - 删除设备列表页面的批量执行命令入口
   - 将功能迁移到"下发列表"页面，改为"运行命令"模板类型

2. 需要支持保存下发机器的 IP 模板，不用每次重新选择

3. 运行命令需要调用 worker 的异步接口，执行时间可能较长，需要任务历史查看功能

4. 任务历史需要定期清理（7天）

---

## 数据库设计

### 1. 扩展 ConfigTemplate 表

| 字段 | 类型 | 说明 |
|------|------|------|
| type | Enum | config / script / **command** |
| command | Text | 命令内容（仅 command 类型使用） |

### 2. 新增 MachineSelectionTemplate 表（IP 模板）

```python
class MachineSelectionTemplate(BaseModel):
    """机器选择模板表"""
    __tablename__ = "machine_selection_template"
    
    name = Column(String(64), nullable=False, unique=True, comment="模板名称")
    namespace = Column(String(64), nullable=True, comment="命名空间筛选")
    device_type = Column(String(20), nullable=True, comment="设备类型筛选")
    ip_pattern = Column(String(64), nullable=True, comment="IP模糊匹配")
    machine_ids = Column(JSON, nullable=True, comment="固定机器ID列表")
    note = Column(Text, nullable=True, comment="备注说明")
    version = Column(String(20), nullable=False, comment="版本号")
```

### 3. 新增 CommandTask 表（任务历史）

```python
class CommandTask(BaseModel):
    """命令任务记录表"""
    __tablename__ = "command_task"
    
    template_id = Column(UUID, nullable=True, comment="关联模板ID")
    template_type = Column(String(20), nullable=False, comment="模板类型: config/script/command")
    template_name = Column(String(64), nullable=False, comment="模板名称")
    command = Column(Text, nullable=True, comment="命令内容（仅command类型）")
    machine_count = Column(Integer, nullable=False, default=0, comment="目标机器数量")
    status = Column(String(20), nullable=False, default="running", comment="任务状态: running/success/failed/partial")
    success_count = Column(Integer, nullable=False, default=0, comment="成功数量")
    failed_count = Column(Integer, nullable=False, default=0, comment="失败数量")
    result_detail = Column(JSON, nullable=True, comment="每台机器的执行结果详情")
    finished_datetime = Column(DateTime, nullable=True, comment="任务结束时间")
```

---

## API 接口设计

### 1. 配置模板 API（扩展）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/core/config-template | 获取模板列表（支持 type=command 过滤） |
| POST | /api/core/config-template | 创建模板（支持 command 类型） |
| PUT | /api/core/config-template/{id} | 更新模板 |
| DELETE | /api/core/config-template/{id} | 删除模板 |
| POST | /api/core/config-template/deploy | 下发配置/脚本/命令 |

### 2. IP 模板 API（新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/core/machine-selection-template | 获取 IP 模板列表 |
| POST | /api/core/machine-selection-template | 创建 IP 模板 |
| PUT | /api/core/machine-selection-template/{id} | 更新 IP 模板 |
| DELETE | /api/core/machine-selection-template/{id} | 删除 IP 模��� |

### 3. 任务历史 API（新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/core/command-task | 获取任务历史列表 |
| GET | /api/core/command-task/{id} | 获取任务详情（含每台机器执行结果） |
| DELETE | /api/core/command-task/{id} | 删除单条任务记录 |

---

## 前端页面设计

### 下发列表页面 (config.vue)

```
+-------------------------------------------------------------+
|  📝 下发列表                              [新建] [Tab]       |
+------------------------+--------------------------------------+
|                        |  [筛选：命名空间/设备类型/IP]         |
|  配置模板              |  [保存为IP模板] [使用IP模板]          |
|  ─────────---          |  +---------------------------------+ |
|  脚本模板              |  | ☐ 192.168.1.1  Windows  在线   | |
|  ─────────---          |  | ☑ 192.168.1.2  Mac      在线   | |
|  运行命令 ←新增        |  | ☑ 192.168.1.3  Windows  在线   | |
|                        |  | ☐ 192.168.1.4  iOS      离线   | |
|                        |  +---------------------------------+ |
|                        |  已选 2 台                      [下发]|
+------------------------+--------------------------------------+
```

#### Tab1: 下发列表
- 左侧模板列表：配置模板 / 脚本模板 / 运行命令 三个折叠面板
- 运行命令模板：增加命令内容输入框
- 右侧机器选择区：增加"保存为IP模板"和"使用IP模板"按钮

#### Tab2: 任务历史
- 任务列表：显示每次下发的任务记录
- 点击展开：显示每个 IP 的执行详情（stdout/stderr/状态）

### 弹窗设计

#### 1. 保存 IP 模板弹窗
```
+--------------------------------+
|  保存为 IP 模板                 |
+--------------------------------+
|  模板名称：________________    |
|  备注：     ________________    |
|                                 |
|  预览：已选择 3 台机器          |
|  * 192.168.1.1 (Windows)       |
|  * 192.168.1.2 (Mac)           |
|  * 192.168.1.3 (Windows)       |
|                                 |
|  [取消]            [保存]       |
+--------------------------------+
```

#### 2. 使用 IP 模板弹窗
```
+--------------------------------+
|  使用 IP 模板                   |
+--------------------------------+
|  模板名称    | 目标机器 | 操作  |
|  -----------------------       |
|  全部测试机  | 10 台   | [使用]|
|  Win 开发机  | 5 台    | [使用]|
|  Mac 测试机  | 3 台    | [使用]|
|                                 |
|  [新建模板]  [取消]             |
+--------------------------------+
```

#### 3. 运行命令模板编辑弹窗
```
+-----------------------------------------+
|  编辑运行命令模板                        |
+-----------------------------------------+
|  模板名称：________________             |
|  适用命名空间： [选择]                   |
|  命令内容：                              |
|  +-------------------------------------+|
|  | dir C:\Users                       || 
|  +-------------------------------------+|
|  备注：________________                  |
|                                         |
|  [取消]                    [保存]       |
+-----------------------------------------+
```

---

## 执行流程

### 1. 下发命令（异步方式）

```
1. 用户选择运行命令模板 -> 配置命令内容 + 选择机器
2. 后端调用 worker 的 /task/execute_async 接口
3. 后端创建 CommandTask 记录（status=running）
4. 前端跳转到"任务历史"Tab，显示任务进度
5. 前端轮询查询任务状态或用户手动刷新
6. 任务完成后更新 status 和 result_detail
```

### 2. 任务结果查询

```
1. 用户点击任务记录 -> 展开详情
2. 每个 IP 显示：
   - 执行状态（成功/失败）
   - 执行耗时
   - stdout（成功时）
   - stderr（失败时）
```

---

## 定时任务

### 任务清理

- 每天凌晨 3:00 执行清理任务
- 删除 `sys_create_datetime` 超过 7 天的 CommandTask 记录

---

## 待办事项

1. [ ] 数据库迁移：添加 command 字段和新建表
2. [ ] 后端 API：配置模板扩展 + IP 模板 API + 任务历史 API
3. [ ] 后端服务：异步执行逻辑 + 定时清理任务
4. [ ] 前端页面：下发列表页面改造
5. [ ] 前端交互：IP 模板功能 + 任务历史查看
6. [ ] 删除设备列表页面的批量执行命令相关代码

---

## 相关文件

- 前端页面：`web/apps/web-ele/src/views/env-machine/config.vue`
- 设备列表：`web/apps/web-ele/src/views/env-machine/list.vue`
- 批量命令弹窗：`web/apps/web-ele/src/views/env-machine/modules/BatchCommandDialog.vue`
- 后端配置模板：`backend-fastapi/core/config_template/`
- 后端执行机：`backend-fastapi/core/env_machine/api.py`
