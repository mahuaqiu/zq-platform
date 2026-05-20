# 执行机申请权限验证设计文档

## 日期
2026-05-21

## 概述
为执行机申请接口增加权限控制，通过 Header 中的 `X-Env-Auth` 字段验证申请权限，确保只有持有正确 key 且该 key 对目标 namespace 有授权的用户才能申请机器。

## 背景
当前执行机申请接口缺乏权限控制，任何用户都可以申请任意 namespace 的机器。需要增加权限验证，防止未授权的申请操作。

## 需求
1. 申请接口需要权限验证
2. Header 中增加 `X-Env-Auth` 字段传递认证 key
3. 只有申请接口需要验证，其他接口不受影响
4. key 和 namespace 的授权关系配置在 `.env` 文件中
5. 验证失败返回 401 权限不足

## 架构设计

### 整体流程
```
Client Request → Header(X-Env-Auth) → FastAPI Depends(verify_env_apply_auth) →
验证失败 → HTTPException(401) → 返回错误
验证成功 → 继续执行接口逻辑 → 返回成功响应
```

### 核心组件
- **配置管理**: `.env` 文件存储 key-namespace 映射
- **依赖函数**: `verify_env_apply_auth` 验证 header 中的 key
- **接口改造**: 申请接口添加 `Depends(verify_env_apply_auth)` 依赖

## 组件设计

### 1. 环境配置

在 `backend-fastapi/env/dev.env` 中添加配置项：

```bash
# 执行机申请权限配置（JSON格式）
# key -> namespace列表 的映射
ENV_APPLY_AUTH={"key_gamma":["meeting_gamma"],"key_app":["meeting_app"],"key_common":["meeting_gamma","meeting_app"]}
```

### 2. 配置管理实现

修改 `backend-fastapi/app/config.py`，添加配置字段和解析 property：

```python
# 在 Settings 类中添加字段定义
ENV_APPLY_AUTH: str = ""  # 执行机申请权限配置（JSON格式）

# 在 Settings 类中添加 property
@property
def env_apply_auth_map(self) -> Dict[str, List[str]]:
    """解析执行机申请权限配置"""
    if not self.ENV_APPLY_AUTH:
        return {}
    try:
        return json.loads(self.ENV_APPLY_AUTH)
    except json.JSONDecodeError as e:
        logger.warning(f"ENV_APPLY_AUTH JSON 解析失败: {e}")
        return {}
```

### 3. 依赖验证函数

创建新文件 `backend-fastapi/core/env_machine/auth.py`：

```python
"""
执行机申请权限验证
"""
from fastapi import Header, HTTPException, Depends
from typing import Optional, Dict, List
from app.config import settings

async def verify_env_apply_auth(
    namespace: str,
    x_env_auth: Optional[str] = Header(None, alias="X-Env-Auth")
) -> None:
    """
    验证执行机申请权限
    
    Args:
        namespace: 申请的命名空间
        x_env_auth: Header中的认证key
    
    Raises:
        HTTPException: 401 权限不足
    """
    # 1. 使用 settings property 获取配置
    key_namespace_map = settings.env_apply_auth_map
    
    # 2. 检查 header 中的 key
    if not x_env_auth:
        raise HTTPException(status_code=401, detail="缺少 X-Env-Auth header")
    
    # 3. 检查 key 是否存在，以及 namespace 是否在该 key 的授权列表中
    allowed_namespaces = key_namespace_map.get(x_env_auth, [])
    if namespace not in allowed_namespaces:
        raise HTTPException(
            status_code=401, 
            detail="权限不足: 无权申请该命名空间的机器"
        )
```

### 4. 接口改造

修改申请接口 `backend-fastapi/core/env_machine/api.py`：

```python
# 导入依赖验证函数
from core.env_machine.auth import verify_env_apply_auth

@router.post(
    "/{namespace}/application",
    summary="申请执行机",
    dependencies=[Depends(verify_env_apply_auth)]  # 添加权限验证依赖
)
async def apply_env_machines(
    namespace: str,
    data: Dict[str, str],
    db: AsyncSession = Depends(get_db),
    x_testcase_id: Optional[str] = Header(None, alias="X-Testcase-Id")
) -> Union[EnvSuccessResponse, EnvFailResponse]:
    """
    申请执行机接口
    
    Header:
        X-Testcase-Id: 用例编号（可选）
        X-Env-Auth: 申请权限key（必填）
    
    ...原有逻辑不变...
    """
    # 原有的申请逻辑保持不变
    ...
```

## 数据流设计

### 正常申请流程

```
1. Client 发送请求：
   POST /api/core/env_machine/meeting_gamma/application
   Headers: { "X-Env-Auth": "key_gamma", "X-Testcase-Id": "test001" }
   Body: { "userA": "windows", "userB": "web" }

2. FastAPI 路由匹配 → 触发依赖验证 verify_env_apply_auth

3. 验证函数执行：
   - 读取 settings.ENV_APPLY_AUTH 配置
   - 解析 JSON: {"key_gamma": ["meeting_gamma"], ...}
   - 检查 x_env_auth="key_gamma"
   - 检查 namespace="meeting_gamma" 是否在 ["meeting_gamma"] 中
   - 验证通过

4. 继续执行 apply_env_machines → 分配机器 → 返回成功响应
```

### 验证失败流程

```
情况1: 缺少 X-Env-Auth header
→ HTTPException(401, detail="缺少 X-Env-Auth header")
→ 返回: {"detail": "缺少 X-Env-Auth header"}

情况2: key不存在或namespace不在授权列表中
→ HTTPException(401, detail="权限不足: 无权申请该命名空间的机器")
→ 返回: {"detail": "权限不足: 无权申请该命名空间的机器"}
```

## 实现要点

### 1. 配置管理
- 配置项 `ENV_APPLY_AUTH` 存储在 `.env` 文件中
- 格式为 JSON 字符串：`{"key1":["namespace1","namespace2"],...}`
- 使用 Settings 类的 `env_apply_auth_map` property 解析配置
- 配置解析失败时返回空字典，记录警告日志

### 2. 配置默认行为
- ENV_APPLY_AUTH 配置为空时：拒绝所有申请（安全优先原则）
- 配置解析失败时：拒绝所有申请，记录警告日志

### 3. 依赖注入方式
- 使用 `dependencies=[Depends(verify_env_apply_auth)]` 而非参数注入
- 这样验证函数会自动执行，但不改变接口参数结构
- FastAPI 会解析依赖函数的参数签名，自动注入匹配的路径参数（namespace）、Header 参数（x_env_auth）等
- 这是 FastAPI 的依赖注入系统特性，无需手动传参

### 4. 错误处理
- 所有验证失败统一返回 401 状态码
- 错误信息清晰说明具体原因，但避免暴露敏感信息（如传入的 key 值）

### 5. 其他接口不受影响
- 只在申请接口添加依赖验证
- 注册、保持使用、释放、CRUD 等其他接口无需改动

### 6. 配置验证建议
- 部署前使用 JSON 校验工具验证 ENV_APPLY_AUTH 配置格式
- 建议在 Settings 类中添加启动时配置校验：

```python
from pydantic import field_validator
import json

@field_validator("ENV_APPLY_AUTH")
def validate_env_apply_auth(cls, v):
    if not v:
        logger.warning("ENV_APPLY_AUTH 配置为空，所有申请将被拒绝")
        return v
    try:
        json.loads(v)
        return v
    except json.JSONDecodeError:
        raise ValueError("ENV_APPLY_AUTH JSON 格式错误")
```

## 测试要点

### 1. 正常申请测试
- 使用正确的 key 和对应的 namespace 申请
- 验证能成功申请到机器

### 2. 权限验证测试
- 缺少 X-Env-Auth header → 401
- key 不存在 → 401
- key 存在但 namespace 不在授权列表 → 401

### 3. 配置加载测试
- 验证配置能正确从 .env 加载
- 验证 JSON 解析正确

### 4. 边界场景测试
- 配置为空字符串 → 验证拒绝所有申请（返回 401）
- JSON 配置格式错误 → 验证拒绝所有申请（返回 401）

### 5. 多 namespace 授权测试
- key 授权多个 namespace → 验证每个 namespace 都能成功申请
- key 授权多个 namespace → 验证未授权的 namespace 被拒绝

### 6. 并发申请测试
- 同一 namespace 多个客户端并发申请 → 验证权限验证不影响并发处理

## 文件改动清单

1. **新增文件**: `backend-fastapi/core/env_machine/auth.py` - 权限验证函数
2. **修改文件**: `backend-fastapi/core/env_machine/api.py` - 申请接口添加依赖
3. **修改文件**: `backend-fastapi/env/dev.env` - 添加 ENV_APPLY_AUTH 配置
4. **修改文件**: `backend-fastapi/app/config.py` - 添加 ENV_APPLY_AUTH 字段解析
5. **修改文件**: `backend-fastapi/env/uat.env` - 添加 UAT 环境配置
6. **修改文件**: `backend-fastapi/env/prod.env` - 添加生产环境配置

## 配置示例

### 开发环境配置示例
```bash
ENV_APPLY_AUTH={"dev_key":["meeting_gamma","meeting_app","meeting_perf"]}
```

### 生产环境配置示例
```bash
ENV_APPLY_AUTH={"prod_key_gamma":["meeting_gamma"],"prod_key_app":["meeting_app"]}
```

## 风险评估

1. **配置错误导致申请被拒绝**
   - 风险：JSON 配置格式错误可能导致所有申请被拒绝
   - 缓解措施：部署前验证配置格式，使用配置校验脚本

2. **key 泄露导致未授权申请**
   - 风险：key 泄露后可能被恶意使用
   - 缓解措施：定期更换 key，监控异常申请行为

3. **配置为空时的行为**
   - 风险：配置为空时拒绝所有申请，可能影响正常业务
   - 缓解措施：确保每个环境都有正确配置，开发环境可配置宽松策略

## 回滚方案

如需回滚权限验证功能，按以下步骤操作：

1. **移除依赖验证**
   - 从申请接口移除 `dependencies=[Depends(verify_env_apply_auth)]`
   - 申请接口恢复为无权限验证状态

2. **删除验证代码**
   - 删除 `backend-fastapi/core/env_machine/auth.py` 文件

3. **移除配置**
   - 从各环境 `.env` 文件中移除 `ENV_APPLY_AUTH` 配置项
   - 从 `app/config.py` 中移除相关字段和 property

4. **验证回滚**
   - 测试申请接口无需 header 即可正常申请
   - 确认其他功能不受影响