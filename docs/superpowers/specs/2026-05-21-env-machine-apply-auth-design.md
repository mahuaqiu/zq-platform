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

### 2. 依赖验证函数

创建新文件 `backend-fastapi/core/env_machine/auth.py`：

```python
"""
执行机申请权限验证
"""
from fastapi import Header, HTTPException, Depends
from typing import Optional, Dict, List
import json
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
    # 1. 从配置读取权限映射
    auth_config = getattr(settings, 'ENV_APPLY_AUTH', '{}')
    try:
        key_namespace_map: Dict[str, List[str]] = json.loads(auth_config)
    except json.JSONDecodeError:
        key_namespace_map = {}
    
    # 2. 检查 header 中的 key
    if not x_env_auth:
        raise HTTPException(status_code=401, detail="缺少 X-Env-Auth header")
    
    # 3. 检查 key 是否存在，以及 namespace 是否在该 key 的授权列表中
    allowed_namespaces = key_namespace_map.get(x_env_auth, [])
    if namespace not in allowed_namespaces:
        raise HTTPException(
            status_code=401, 
            detail=f"权限不足: key={x_env_auth} 无权申请 namespace={namespace}"
        )
```

### 3. 接口改造

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
→ HTTPException(401, detail="权限不足: key=xxx 无权申请 namespace=yyy")
→ 返回: {"detail": "权限不足: key=xxx 无权申请 namespace=yyy"}
```

## 实现要点

### 1. 配置管理
- 配置项 `ENV_APPLY_AUTH` 存储在 `.env` 文件中
- 格式为 JSON 字符串：`{"key1":["namespace1","namespace2"],...}`
- 配置需要在 `app/config.py` 中添加对应的字段解析

### 2. 依赖注入方式
- 使用 `dependencies=[Depends(verify_env_apply_auth)]` 而非参数注入
- 这样验证函数会自动执行，但不改变接口参数结构
- namespace 参数会自动传递给验证函数（FastAPI 的路由参数匹配机制）

### 3. 错误处理
- 所有验证失败统一返回 401 状态码
- 错误信息清晰说明具体原因（缺少 header、key 无权申请等）

### 4. 其他接口不受影响
- 只在申请接口添加依赖验证
- 注册、保持使用、释放、CRUD 等其他接口无需改动

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