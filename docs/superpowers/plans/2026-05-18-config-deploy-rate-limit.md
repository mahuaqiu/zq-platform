# 配置下发限流机制实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为配置下发添加并发限制（每批最多 20 台），新增状态/版本校验，新增 Worker 上报 scripts 字段

**Architecture:** 批次控制 + 状态校验 + 版本校验，下发成功后立即更新数据库版本，使用 flag_modified 确保 JSON 字段更新生效

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic + asyncio

---

## 文件结构

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `core/env_machine/model.py` | 修改 | 新增 config_status 和 scripts 字段 |
| `core/env_machine/schema.py` | 修改 | EnvRegisterRequest 和 EnvMachineResponse 新增字段 |
| `core/env_machine/api.py` | 修改 | 注册上报更新 scripts 字段 |
| `core/config_template/schema.py` | 修改 | DeployDetail 和 DeployResponse 新增字段 |
| `core/config_template/service.py` | 修改 | 实现校验和批次控制逻辑 |

---

### Task 1: EnvMachine 模型新增字段

**Files:**
- Modify: `backend-fastapi/core/env_machine/model.py:79-83`

- [ ] **Step 1: 新增 config_status 字段**

在 `config_version` 字段后新增：

```python
# 配置下发状态
config_status = Column(String(20), nullable=True, default=None, comment="配置状态: updating/null")
```

- [ ] **Step 2: 新增 scripts 字段**

在 `config_status` 字段后新增：

```python
# 脚本版本字典（JSON 格式）
scripts = Column(JSON, nullable=True, comment="脚本版本字典")
```

- [ ] **Step 3: 更新 to_cache_dict 方法**

在 `to_cache_dict()` 方法内（第 104-123 行），`config_version` 字段后新增：

```python
"config_version": self.config_version,
"config_status": self.config_status,  # 新增
"scripts": self.scripts,  # 新增
"last_keepusing_time": self.last_keepusing_time.isoformat() if self.last_keepusing_time else None,
```

- [ ] **Step 4: 确认 STATUS_DISPLAY 映射**

**注意**：`STATUS_DISPLAY` 字典中已包含 `"config_updating": "配置更新中"`，无需修改。

确认现有映射：
```python
STATUS_DISPLAY = {
    "online": "在线",
    "using": "使用中",
    "offline": "离线",
    "upgrading": "升级中",
    "config_updating": "配置更新中",  # 已存在
}
```

- [ ] **Step 5: 验证修改**

启动服务检查是否有语法错误：

```bash
cd backend-fastapi && python -c "from core.env_machine.model import EnvMachine; print('Model OK')"
```

Expected: 输出 "Model OK"

- [ ] **Step 6: Commit**

```bash
git add backend-fastapi/core/env_machine/model.py
git commit -m "feat(env_machine): 新增 config_status 和 scripts 字段"
```

---

### Task 2: EnvRegisterRequest 新增 scripts 参数

**Files:**
- Modify: `backend-fastapi/core/env_machine/schema.py:16-24`

- [ ] **Step 1: 新增 scripts 参数**

在 `EnvRegisterRequest` 类中，`devices` 字段后新增：

```python
scripts: Optional[Dict[str, str]] = Field(
    None,
    description="脚本版本字典，key为脚本名，value为版本号"
)
```

需要确保导入 `Dict` 类型（已导入）。

- [ ] **Step 2: 验证修改**

```bash
cd backend-fastapi && python -c "from core.env_machine.schema import EnvRegisterRequest; print('Schema OK')"
```

Expected: 输出 "Schema OK"

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/core/env_machine/schema.py
git commit -m "feat(env_machine): EnvRegisterRequest 新增 scripts 参数"
```

---

### Task 3: EnvMachineResponse 新增字段

**Files:**
- Modify: `backend-fastapi/core/env_machine/schema.py:88-112`

- [ ] **Step 1: 新增 config_status 字段**

在 `config_version` 字段后新增：

```python
config_status: Optional[str] = Field(None, description="配置状态")
```

- [ ] **Step 2: 新增 scripts 字段**

在 `config_status` 字段后新增：

```python
scripts: Optional[Dict[str, str]] = Field(None, description="脚本版本字典")
```

- [ ] **Step 3: 验证修改**

```bash
cd backend-fastapi && python -c "from core.env_machine.schema import EnvMachineResponse; print('Response OK')"
```

Expected: 输出 "Response OK"

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/core/env_machine/schema.py
git commit -m "feat(env_machine): EnvMachineResponse 新增 config_status 和 scripts 字段"
```

---

### Task 4: 注册上报更新 scripts 字段

**Files:**
- Modify: `backend-fastapi/core/env_machine/api.py`

- [ ] **Step 1: 查找注册上报更新位置**

搜索 `if data.config_version:` 找到更新 config_version 的位置。

**注意**：有两处需要修改：
1. 现有机器更新（约第 96-97 行）
2. 新机器创建（约第 113-125 行 和 第 177-189 行）

- [ ] **Step 2: 现有机器更新 - 新增 scripts 更新逻辑**

在第一处 `if data.config_version:` 后新增：

```python
# 现有机器更新（Windows/Mac 约 96-97 行，Android/iOS 约 160-161 行）
if data.config_version:
    existing_machine.config_version = data.config_version
if data.scripts:
    existing_machine.scripts = data.scripts
```

- [ ] **Step 3: 新机器创建 - 新增 scripts 参数**

在 `EnvMachine(...)` 创建时新增 `scripts` 参数（两处：Windows/Mac 和 Android/iOS）：

```python
# Windows/Mac 创建（约 113-125 行）
new_machine = EnvMachine(
    namespace=data.namespace,
    ...
    config_version=data.config_version,
    scripts=data.scripts,  # 新增
)

# Android/iOS 创建（约 177-189 行）
new_machine = EnvMachine(
    namespace=data.namespace,
    ...
    config_version=data.config_version,
    scripts=data.scripts,  # 新增
)
```

- [ ] **Step 4: 验证修改**

```bash
cd backend-fastapi && python -c "from core.env_machine.api import router; print('API OK')"
```

Expected: 输出 "API OK"

- [ ] **Step 5: Commit**

```bash
git add backend-fastapi/core/env_machine/api.py
git commit -m "feat(env_machine): 注册上报更新 scripts 字段"
```

---

### Task 5: DeployDetail 和 DeployResponse 新增字段

**Files:**
- Modify: `backend-fastapi/core/config_template/schema.py:87-99`

- [ ] **Step 1: DeployDetail 新增 skip_reason 字段**

修改 `DeployDetail` 类：

```python
class DeployDetail(BaseModel):
    """下发详情 Schema"""
    machine_id: str = Field(..., description="机器ID")
    ip: str = Field(..., description="机器IP")
    status: str = Field(..., description="下发状态: success/failed/skipped")
    error_message: Optional[str] = Field(None, description="错误信息")
    skip_reason: Optional[str] = Field(None, description="跳过原因")
```

- [ ] **Step 2: DeployResponse 新增 skipped_count 字段**

修改 `DeployResponse` 类：

```python
class DeployResponse(BaseModel):
    """下发配置响应 Schema"""
    success_count: int = Field(0, description="成功数量")
    failed_count: int = Field(0, description="失败数量")
    skipped_count: int = Field(0, description="跳过数量")
    details: List[DeployDetail] = Field(default_factory=list, description="下发详情列表")
```

- [ ] **Step 3: 验证修改**

```bash
cd backend-fastapi && python -c "from core.config_template.schema import DeployResponse, DeployDetail; print('Schema OK')"
```

Expected: 输出 "Schema OK"

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/core/config_template/schema.py
git commit -m "feat(config_template): DeployDetail 新增 skip_reason，DeployResponse 新增 skipped_count"
```

---

### Task 6: config_template/service.py 实现校验逻辑

**Files:**
- Modify: `backend-fastapi/core/config_template/service.py`

这是核心任务，包含多个子步骤。

- [ ] **Step 1: 新增常量定义**

在文件顶部（约第 40 行后）新增：

```python
# 最大并发配置下发数量
MAX_CONCURRENT_CONFIG_DEPLOY = 20
```

- [ ] **Step 2: 新增 flag_modified 导入**

在导入区域新增：

```python
from sqlalchemy.orm.attributes import flag_modified
```

- [ ] **Step 3: 新增 _should_deploy 函数**

**注意**：复用现有的 `_get_target_os_from_extension` 方法（service.py 第 303-318 行已存在）。

在 `ConfigTemplateService` 类中新增静态方法：

```python
@staticmethod
def _should_deploy(machine: EnvMachine, template: ConfigTemplate) -> Tuple[bool, Optional[str]]:
    """
    判断是否需要下发配置

    Args:
        machine: 机器对象
        template: 配置模板

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
        target_os = ConfigTemplateService._get_target_os_from_extension(template.script_name)
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
```

- [ ] **Step 4: 新增 _deploy_batch 函数**

在 `ConfigTemplateService` 类中新增静态方法：

```python
@staticmethod
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
        batch_tasks = [
            ConfigTemplateService._send_config_to_worker(m, t) if t.type != "script"
            else ConfigTemplateService._send_script_to_worker(m, t)
            for m, t in batch
        ]
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

- [ ] **Step 5: 重构 deploy_config 方法**

替换现有的 `deploy_config` 方法（约第 320-450 行），使用新的校验和批次控制逻辑：

```python
@classmethod
async def deploy_config(
    cls,
    db: AsyncSession,
    template_id: str,
    machine_ids: List[str],
) -> DeployResponse:
    """
    下发配置到机器（带并发控制和校验）
    """
    # 获取模板
    template = await cls.get_by_id(db, template_id)
    if not template:
        raise ValueError(f"模板不存在: {template_id}")

    # 查询机器
    result = await db.execute(
        select(EnvMachine).where(
            and_(
                EnvMachine.id.in_(machine_ids),
                EnvMachine.is_deleted == False,
            )
        )
    )
    machines = result.scalars().all()

    response = DeployResponse()
    deploy_tasks = []
    deploy_machine_map = {}

    # 遍历校验
    for machine in machines:
        should_deploy, skip_reason = cls._should_deploy(machine, template)

        if not should_deploy:
            response.skipped_count += 1
            response.details.append(DeployDetail(
                machine_id=machine.id,
                ip=machine.ip,
                status="skipped",
                error_message=None,
                skip_reason=skip_reason,
            ))
            continue

        # 设置 config_status 为 updating
        machine.config_status = "updating"

        # 收集待下发任务
        deploy_tasks.append((machine, template))
        deploy_machine_map[machine.id] = machine

    # 分批下发
    if deploy_tasks:
        logger.info(f"开始下发配置到 {len(deploy_tasks)} 台机器，类型: {template.type}")
        results = await cls._deploy_batch(deploy_tasks)

        # 处理结果
        for success, error_msg, machine_id in results:
            machine = deploy_machine_map[machine_id]

            if success:
                # 更新版本字段
                if template.type == "config":
                    machine.config_version = template.version
                else:
                    if machine.scripts is None:
                        machine.scripts = {}
                    machine.scripts[template.script_name] = template.version
                    flag_modified(machine, "scripts")

                # 清除 config_status
                machine.config_status = None

                response.success_count += 1
                response.details.append(DeployDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="success",
                    error_message=None,
                    skip_reason=None,
                ))
            else:
                # 下发失败，清除 config_status
                machine.config_status = None

                response.failed_count += 1
                response.details.append(DeployDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="failed",
                    error_message=error_msg,
                    skip_reason=None,
                ))

    await db.commit()
    return response
```

- [ ] **Step 6: 验证修改**

```bash
cd backend-fastapi && python -c "from core.config_template.service import ConfigTemplateService; print('Service OK')"
```

Expected: 输出 "Service OK"

- [ ] **Step 7: Commit**

```bash
git add backend-fastapi/core/config_template/service.py
git commit -m "feat(config_template): 实现配置下发并发控制和校验逻辑"
```

---

### Task 7: 预览功能更新

**Files:**
- Modify: `backend-fastapi/core/config_template/schema.py:102-111`
- Modify: `backend-fastapi/core/config_template/service.py:_calculate_config_status`

**注意**：预览功能需要支持脚本类型的版本对比，让用户知道哪些机器脚本已是最新版本。

- [ ] **Step 1: ConfigPreviewMachine 新增 scripts 字段**

修改 `ConfigPreviewMachine` 类（schema.py 第 102-111 行）：

```python
class ConfigPreviewMachine(BaseModel):
    """配置预览机器 Schema"""
    id: str = Field(..., description="机器ID")
    ip: str = Field(..., description="机器IP")
    namespace: str = Field(..., description="命名空间")
    device_type: str = Field(..., description="设备类型")
    status: str = Field(..., description="设备状态")
    config_status: str = Field(..., description="配置状态: synced/pending/updating/offline")
    config_version: Optional[str] = Field(None, description="配置版本")
    scripts: Optional[Dict[str, str]] = Field(None, description="脚本版本字典")  # 新增
```

- [ ] **Step 2: 更新 get_preview 方法**

修改 `get_preview` 方法中计算 `config_status` 的逻辑（service.py），传入 template 对象：

对于脚本类型，使用脚本版本对比：

```python
# 在 get_preview 方法中（约第 242-274 行）
for machine in machines:
    # 计算配置状态
    if template.type == "script":
        # 脚本类型：对比脚本版本
        config_status = cls._calculate_script_config_status(machine, template)
    else:
        # 配置类型：对比全局配置版本
        config_status = cls._calculate_config_status(machine, template.version)

    machine_preview = ConfigPreviewMachine(
        id=machine.id,
        ip=machine.ip,
        namespace=machine.namespace,
        device_type=machine.device_type,
        status=machine.status,
        config_status=config_status,
        config_version=machine.config_version,
        scripts=machine.scripts,  # 新增
    )
```

- [ ] **Step 3: 新增 _calculate_script_config_status 方法**

在 `ConfigTemplateService` 类中新增静态方法：

```python
@staticmethod
def _calculate_script_config_status(machine: EnvMachine, template: ConfigTemplate) -> str:
    """
    计算机器的脚本配置状态

    Args:
        machine: 机器对象
        template: 配置模板（脚本类型）

    Returns:
        配置状态（synced/pending/updating/offline）
    """
    # 离线状态
    if machine.status == "offline":
        return "offline"

    # 配置更新中
    if machine.config_status == "updating":
        return "updating"

    # 脚本版本对比
    machine_script_version = machine.scripts.get(template.script_name) if machine.scripts else None

    # 已同步
    if machine_script_version == template.version:
        return "synced"

    # 待更新
    return "pending"
```

- [ ] **Step 4: 简化 _calculate_config_status 方法**

简化 `config_status` 检查逻辑（移除 hasattr）：

```python
@staticmethod
def _calculate_config_status(machine: EnvMachine, template_version: str) -> str:
    """
    计算机器的配置状态（配置类型）

    Args:
        machine: 机器对象
        template_version: 模板版本号

    Returns:
        配置状态（synced/pending/updating/offline）
    """
    # 离线状态
    if machine.status == "offline":
        return "offline"

    # 配置更新中
    if machine.config_status == "updating":
        return "updating"

    # 已同步
    if machine.config_version == template_version:
        return "synced"

    # 待更新
    return "pending"
```

- [ ] **Step 5: 验证修改**

```bash
cd backend-fastapi && python -c "from core.config_template.service import ConfigTemplateService; print('Preview OK')"
```

Expected: 输出 "Preview OK"

- [ ] **Step 6: Commit**

```bash
git add backend-fastapi/core/config_template/schema.py backend-fastapi/core/config_template/service.py
git commit -m "feat(config_template): 预览功能支持脚本版本对比"
```

---

### Task 8: 数据库迁移

**Files:**
- Create: Alembic 迁移文件

- [ ] **Step 1: 创建迁移文件**

```bash
cd backend-fastapi && alembic revision --autogenerate -m "add config_status and scripts fields to env_machine"
```

Expected: 创建迁移文件，包含 `config_status` 和 `scripts` 字段

- [ ] **Step 2: 检查迁移文件**

查看生成的迁移文件，确认包含：
- `sa.Column('config_status', sa.String(20), nullable=True)`
- `sa.Column('scripts', sa.JSON(), nullable=True)`

- [ ] **Step 3: 执行迁移**

```bash
cd backend-fastapi && alembic upgrade head
```

Expected: 迁移成功执行

- [ ] **Step 4: 验证数据库**

通过 ORM 查询验证字段是否存在：

```bash
cd backend-fastapi && python -c "
from app.database import AsyncSessionLocal
from core.env_machine.model import EnvMachine
import asyncio

async def check():
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(EnvMachine).limit(1))
        machine = result.scalar_one_or_none()
        if machine:
            print(f'config_status: {machine.config_status}')
            print(f'scripts: {machine.scripts}')
            print('验证成功')
        else:
            print('数据库无数据，但字段已定义')

asyncio.run(check())
"
```

Expected: 输出 "验证成功" 或 "数据库无数据，但字段已定义"

- [ ] **Step 5: Commit**

```bash
git add backend-fastapi/alembic/versions/*.py
git commit -m "feat(db): 新增 env_machine 表 config_status 和 scripts 字段迁移"
```

---

### Task 9: 集成验证

- [ ] **Step 1: 启动后端服务**

```bash
cd backend-fastapi && python main.py
```

Expected: 服务正常启动，无报错

- [ ] **Step 2: 测试注册上报接口**

使用 Swagger UI 测试 `/api/core/env/register` 接口，传入 `scripts` 参数：

```json
{
  "ip": "192.168.1.100",
  "port": "8080",
  "namespace": "test",
  "version": "0.3.4",
  "config_version": "20260501-090000",
  "devices": {"windows": []},
  "scripts": {"test.ps1": "20260418-120000"}
}
```

Expected: 成功注册，scripts 字段存储到数据库

- [ ] **Step 3: 测试配置下发接口**

使用 Swagger UI 测试 `/api/core/config-template/deploy` 接口，传入超过 20 台机器：

- 验证批次下发日志
- 验证 skipped_count 和 skip_reason

- [ ] **Step 4: 最终 Commit**

```bash
git add -A && git status
```

确认所有修改已提交。

---

## 注意事项

1. **flag_modified 关键**：JSON 字段更新必须调用 `flag_modified(machine, "scripts")` 才能生效
2. **config_status 状态管理**：下发开始设为 `updating`，成功/失败后清除
3. **批次索引**：使用批次内索引 `idx` 而非外层索引 `i`
4. **版本对比**：脚本类型对比 `scripts.get(script_name)`，配置类型对比 `config_version`