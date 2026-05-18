---
name: config-deploy-rate-limit
description: 配置下发限流机制和 Worker 上报脚本版本设计
metadata:
  type: project
---

# 配置下发限流机制设计

## 背景

当前配置下发功能没有并发限制，用户一次性选择多台机器时，后端会并发调用所有 Worker 的配置接口，可能导致：
- Worker 压力过大
- 网络拥塞
- 部分请求失败

升级管理已有完善的限流机制（最多 10 台并发 + 队列等待），配置下发需要类似的控制。

**与升级管理的差异**：
- 配置下发速度快（通常几秒内完成），不需要队列机制
- 采用批次控制 + 状态/版本校验即可满足需求

## 需求总结

1. **并发限制**：每批最多 20 台并发下发
2. **状态校验**：仅 `online` 状态可下发
3. **版本校验**：版本号相同则跳过（避免重复下发）
4. **交互模式**：批次处理后立即返回结果，版本更新通过 Worker 心跳异步完成
5. **Worker 上报**：新增 `scripts` 字段存储脚本版本字典

## 设计详情

### 一、配置下发限流机制

#### 并发控制

**常量定义**：
```python
MAX_CONCURRENT_CONFIG_DEPLOY = 20
```

**实现方式**：使用批次控制，每批最多并发 20 个请求。

#### 校验规则

**状态校验**：仅 `status == "online"` 且 `config_status != "updating"` 的机器可下发。

跳过条件：
- `status == "offline"` → 跳过（机器离线）
- `status == "using"` → 跳过（机器使用中）
- `status == "upgrading"` → 跳过（机器升级中）
- `config_status == "updating"` → 跳过（配置更新中）

**版本校验**：
   - **配置类型**：`machine.config_version != template.version`
   - **脚本类型**：`machine.scripts.get(script_name) != template.version`
   - 版本号相同 → 跳过（已是最新版本）

#### 批次控制具体实现

```python
# 常量定义
MAX_CONCURRENT_CONFIG_DEPLOY = 20

async def _deploy_batch(
    tasks: List[Tuple[EnvMachine, ConfigTemplate]],
    batch_size: int = MAX_CONCURRENT_CONFIG_DEPLOY
) -> List[Tuple[bool, Optional[str], str]]:
    """
    分批并发下发配置

    Args:
        tasks: 待下发的任务列表（machine, template）
        batch_size: 每批最大并发数

    Returns:
        List[Tuple[是否成功, 错误信息, machine_id]]
    """
    results = []
    total = len(tasks)

    for i in range(0, total, batch_size):
        batch = tasks[i:i + batch_size]
        logger.info(f"下发第 {i//batch_size + 1} 批，共 {len(batch)} 台")

        # 批次内并发执行
        batch_tasks = [_send_config_to_worker(m, t) for m, t in batch]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        # 处理批次结果（使用批次内索引）
        for idx, task_result in enumerate(batch_results):
            if isinstance(task_result, Exception):
                results.append((False, str(task_result), batch[idx][0].id))
            else:
                results.append(task_result)

        logger.info(f"第 {i//batch_size + 1} 批完成，成功 {sum(1 for r in batch_results if not isinstance(r, Exception) and r[0])} 台")

    return results
```

#### 下发流程

```
1. 获取模板信息（版本号、类型、script_name）
2. 查询机器列表
3. 遍历校验：
   - 状态不是 online → 记录跳过（原因：离线/使用中/升级中）
   - 版本号相同 → 记录跳过（原因：已是最新版本）
   - 通过校验 → 收集待下发列表
4. 分批下发（每批最多 20 台）：
   - 批次内并发调用 Worker 接口
   - 批次完成后继续下一批
5. 立即返回结果（成功/失败/跳过）
```

#### 返回结果增强

`DeployResponse` 增加 `skipped_count` 字段：

```python
class DeployResponse(BaseModel):
    """下发配置响应 Schema"""
    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    skipped_count: int = Field(0, description="跳过数量")
    details: List[DeployDetail] = Field(..., description="下发详情列表")
```

`DeployDetail` 增加跳过状态和原因：

```python
class DeployDetail(BaseModel):
    """下发详情 Schema"""
    machine_id: str = Field(..., description="机器ID")
    ip: str = Field(..., description="机器IP")
    status: str = Field(..., description="下发状态: success/failed/skipped")
    error_message: Optional[str] = Field(None, description="错误信息")
    skip_reason: Optional[str] = Field(None, description="跳过原因")  # 新增字段
```

#### 返回结果转换

`_deploy_batch` 返回 `List[Tuple[bool, Optional[str], str]]`，需要转换为 `List[DeployDetail]`：

```python
def _convert_results_to_details(
    results: List[Tuple[bool, Optional[str], str]],
    machine_map: Dict[str, EnvMachine]
) -> List[DeployDetail]:
    """将批次下发结果转换为 DeployDetail 列表"""
    details = []
    for success, error_msg, machine_id in results:
        machine = machine_map[machine_id]
        details.append(DeployDetail(
            machine_id=machine_id,
            ip=machine.ip,
            status="success" if success else "failed",
            error_message=error_msg if not success else None,
            skip_reason=None,
        ))
    return details
```

### 二、Worker 上报脚本版本

#### EnvMachine 模型新增字段

```python
# 配置下发状态
config_status = Column(String(20), nullable=True, default=None, comment="配置状态: updating/null")

# 脚本版本字典（JSON 格式）
scripts = Column(JSON, nullable=True, comment="脚本版本字典")
```

**config_status 字段说明**：
- `null`（默认）：配置正常
- `updating`：配置正在下发/更新中

存储格式示例（scripts）：
```json
{
  "play_ppt.ps1": "20260418-120000",
  "download_install.ps1": "20260501-090000"
}
```

#### EnvRegisterRequest Schema 新增字段

```python
scripts: Optional[Dict[str, str]] = Field(
    None,
    description="脚本版本字典，key为脚本名，value为版本号"
)
```

#### 注册上报更新逻辑

在 `core/env_machine/api.py` 的注册上报接口中，新增 `scripts` 字段更新：

```python
if data.scripts:
    existing_machine.scripts = data.scripts
```

#### 版本对比逻辑

配置下发时的版本对比（含设备类型校验）：

```python
def _should_deploy(machine: EnvMachine, template: ConfigTemplate) -> Tuple[bool, Optional[str]]:
    """
    判断是否需要下发配置

    Returns:
        (是否需要下发, 跳过原因)
    """
    # 状态校验
    if machine.status != "online":
        return False, f"机器状态为 {machine.status}"

    # 配置更新中校验
    if machine.config_status == "updating":
        return False, "配置正在更新中"

    # 设备类型校验（脚本类型）
    if template.type == "script":
        target_os = _get_target_os_from_extension(template.script_name)
        if target_os == "windows" and machine.device_type != "windows":
            return False, "脚本仅支持 Windows 设备"
        elif target_os == "mac" and machine.device_type != "mac":
            return False, "脚本仅支持 Mac 设备"

        # 脚本版本校验
        machine_script_version = machine.scripts.get(template.script_name) if machine.scripts else None
        if machine_script_version == template.version:
            return False, "脚本已是最新版本"
    else:
        # 配置类型版本校验
        if machine.config_version == template.version:
            return False, "配置已是最新版本"

    return True, None


def _get_target_os_from_extension(script_name: str) -> str:
    """根据脚本扩展名返回目标操作系统"""
    if not script_name:
        return ''
    ext = script_name.lower().split('.')[-1] if '.' in script_name else ''
    if ext in ('ps1', 'bat'):
        return 'windows'
    elif ext == 'sh':
        return 'mac'
    return ''
```

#### 缓存同步

**需要修改 `EnvMachine.to_cache_dict()` 方法**，新增 `scripts` 字段：

```python
# 在 model.py 的 to_cache_dict() 方法中新增
"scripts": self.scripts,
```

**Redis 缓存自动同步脚本版本**，通过现有的心跳上报机制。

#### 下发成功后的版本更新策略

配置下发成功后，有两种版本更新策略：

1. **立即更新数据库（推荐）**：下发成功后立即更新 `machine.config_version` 或 `machine.scripts`
   - 优点：前端刷新后立即看到新版本，用户体验好
   - 缺点：与 Worker 实际执行状态可能存在短暂不一致

2. **等待 Worker 心跳上报**：完全依赖 Worker 下次心跳上报版本
   - 优点：版本号来源可信，与 Worker 实际状态一致
   - 缺点：前端刷新可能看到过时版本（心跳间隔约 5-10 秒）

**推荐采用策略 1**：下发成功后立即更新数据库版本，Worker 心跳时再确认同步。

**重要：SQLAlchemy JSON 字段更新需要调用 `flag_modified()` 才能确保数据库更新生效**：

```python
from sqlalchemy.orm.attributes import flag_modified

# 配置类型：下发成功后立即更新 config_version
if template.type == "config":
    machine.config_version = template.version

# 脚本类型：下发成功后立即更新 scripts 字典（需要 flag_modified）
if template.type == "script":
    if machine.scripts is None:
        machine.scripts = {}
    machine.scripts[template.script_name] = template.version
    flag_modified(machine, "scripts")  # 关键！确保 JSON 字段更新被追踪
```

**版本更新位置**：在结果处理阶段更新（继承现有代码模式），遍历下发结果时对成功的机器更新版本字段。

### 三、文件修改清单

| 文件 | 修改内容 |
|------|----------|
| `core/env_machine/model.py` | 1. 新增 `config_status` 字段（String）；2. 新增 `scripts` 字段（JSON）；3. 更新 `to_cache_dict()` 方法添加两个字段 |
| `core/env_machine/schema.py` | 1. `EnvRegisterRequest` 新增 `scripts` 参数；2. `EnvMachineResponse` 新增 `config_status` 和 `scripts` 字段 |
| `core/env_machine/api.py` | 注册上报时新增 `scripts` 字段更新逻辑 |
| `core/config_template/service.py` | 1. 新增 `_should_deploy` 函数实现完整校验（状态+设备类型+版本）；2. 新增 `_deploy_batch` 函数实现批次控制；3. `deploy_config` 方法调用校验逻辑；4. 下发成功后更新版本字段（含 `flag_modified`）；5. 下发开始时设置 `config_status="updating"`，成功后清除 |
| `core/config_template/schema.py` | 1. `DeployDetail` 新增 `skip_reason` 字段；2. `DeployResponse` 新增 `skipped_count` 字段；3. `status` 字段值新增 `skipped` |

**行为变更说明**：
- 现有代码将 offline/config_status=updating 的机器计入 `failed_count`
- 新设计将不符合下发条件的机器计入 `skipped_count`（新增）
- 前端需适配新的返回结构

### 四、数据库迁移

```bash
alembic revision --autogenerate -m "add config_status and scripts fields to env_machine"
alembic upgrade head
```

### 五、预览功能更新

`get_preview` 方法中的 `_calculate_config_status` 函数需要更新，以正确识别版本状态：

```python
def _calculate_config_status(machine: EnvMachine, template_version: str) -> str:
    """计算机器的配置状态"""
    # 离线或更新中状态
    if machine.status == "offline":
        return "offline"
    if machine.config_status == "updating":
        return "updating"

    # 版本对比
    if machine.config_version == template_version:
        return "synced"  # 已同步

    return "pending"  # 待更新
```

**预览结果新增**：预览列表中需显示版本对比结果，让用户知道哪些机器已是最新版本（会被跳过）。

## 实现计划

1. EnvMachine 模型和 Schema 新增 `scripts` 字段
2. 注册上报接口更新 `scripts` 字段
3. 配置下发逻辑增加并发限制和校验
4. 数据库迁移
5. 前端适配

## 前端适配

**需要修改的页面和组件**：

| 页面 | 组件 | 修改内容 |
|------|------|----------|
| 配置模板列表页 | 下发对话框 | 显示 `skipped_count`，列表中显示跳过原因 |
| 配置模板列表页 | 预览对话框 | 预览时显示"已是最新版本"的机器（新增 `config_status` 显示） |
| 设备列表页 | 设备详情 | 显示 `scripts` 字段（脚本版本字典） |

**API 调用方处理**：
- `DeployResponse` 新增 `skipped_count` 字段，前端需要展示
- `DeployDetail` 新增 `skip_reason` 字段，前端需要显示跳过原因
- `EnvMachineResponse` 新增 `scripts` 字段，前端需要展示脚本版本

## 测试要点

1. **并发限制测试**：选择超过 20 台机器，验证批次下发
2. **状态校验测试**：选择 offline/using/upgrading 状态的机器，验证跳过
3. **版本校验测试**：选择已是最新版本的机器，验证跳过
4. **脚本版本上报测试**：Worker 心跳上报 scripts 字段，验证数据库更新
5. **缓存同步测试**：验证 Redis 缓存包含 scripts 字段

## 注意事项

1. **版本更新策略**：下发成功后立即更新数据库版本，Worker 心跳时确认同步
2. 脚本版本字典可能为空（Worker 未上报），需要处理空值情况：`machine.scripts or {}`
3. 并发限制值为常量（20），未来可考虑配置化
4. 状态校验仅允许 `online` 状态下发，与升级管理一致