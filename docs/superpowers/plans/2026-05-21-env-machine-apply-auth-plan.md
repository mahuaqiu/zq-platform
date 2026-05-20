# 执行机申请权限验证实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为执行机申请接口增加权限验证，通过 Header 中的 X-Env-Auth 字段验证申请权限。

**Architecture:** 使用 FastAPI Depends 依赖注入方式验证权限，配置存储在 .env 文件中，使用 Settings 类的 property 解析 JSON 配置。

**Tech Stack:** FastAPI, Pydantic Settings, Python 3.12

---

## 文件结构

```
backend-fastapi/
├── app/config.py                [修改] - 添加 ENV_APPLY_AUTH 字段和 property
├── core/env_machine/
│   ├── auth.py                  [新增] - 权限验证依赖函数
│   └── api.py                   [修改] - 申请接口添加依赖
├── env/
│   ├── dev.env                  [修改] - 添加开发环境配置
│   ├── uat.env                  [修改] - 添加 UAT 环境配置
│   └── prod.env                 [修改] - 添加生产环境配置
```

---

## Task 1: 添加配置字段和解析逻辑

**Files:**
- Modify: `backend-fastapi/app/config.py:77-194`

### Step 1: 在 Settings 类添加 ENV_APPLY_AUTH 字段

```python
# 在 backend-fastapi/app/config.py 第 77 行之后添加
ENV_APPLY_AUTH: str = ""  # 执行机申请权限配置（JSON格式）
```

### Step 2: 添加 env_apply_auth_map property

```python
# 在 backend-fastapi/app/config.py 第 195 行之后添加（namespace_map property 之后）
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

### Step 3: 验证配置加载

运行 FastAPI 服务器验证配置加载无误：
```bash
cd backend-fastapi
python main.py
```
Expected: 服务器正常启动，无配置错误提示

### Step 4: Commit

```bash
git add backend-fastapi/app/config.py
git commit -m "feat(config): 添加 ENV_APPLY_AUTH 配置字段和解析 property"
```

---

## Task 2: 创建权限验证依赖函数

**Files:**
- Create: `backend-fastapi/core/env_machine/auth.py`

### Step 1: 创建 auth.py 文件

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-05-21
@File: auth.py
@Desc: 执行机申请权限验证
"""
from fastapi import Header, HTTPException
from typing import Optional
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
    # 使用 settings property 获取配置
    key_namespace_map = settings.env_apply_auth_map
    
    # 检查 header 中的 key
    if not x_env_auth:
        raise HTTPException(status_code=401, detail="缺少 X-Env-Auth header")
    
    # 检查 key 是否存在，以及 namespace 是否在该 key 的授权列表中
    allowed_namespaces = key_namespace_map.get(x_env_auth, [])
    if namespace not in allowed_namespaces:
        raise HTTPException(
            status_code=401, 
            detail="权限不足: 无权申请该命名空间的机器"
        )
```

### Step 2: 验证文件创建成功

```bash
ls backend-fastapi/core/env_machine/auth.py
```
Expected: 文件存在

### Step 3: Commit

```bash
git add backend-fastapi/core/env_machine/auth.py
git commit -m "feat(env_machine): 添加执行机申请权限验证依赖函数"
```

---

## Task 3: 修改申请接口添加权限验证

**Files:**
- Modify: `backend-fastapi/core/env_machine/api.py:227-236`

### Step 1: 导入验证函数

```python
# 在 backend-fastapi/core/env_machine/api.py 第 38 行之后添加
from core.env_machine.auth import verify_env_apply_auth
```

### Step 2: 添加依赖到申请接口

```python
# 修改 backend-fastapi/core/env_machine/api.py 第 227-230 行
@router.post(
    "/{namespace}/application",
    summary="申请执行机",
    dependencies=[Depends(verify_env_apply_auth)]  # 添加权限验证依赖
)
```

### Step 3: 更新接口文档注释

```python
# 修改 backend-fastapi/core/env_machine/api.py 第 237-241 行
"""
申请执行机接口

Header:
    X-Testcase-Id: 用例编号（可选），用于合并连续失败记录
    X-Env-Auth: 申请权限key（必填），用于验证申请权限

从指定 namespace 的机器池中申请机器。
```

### Step 4: Commit

```bash
git add backend-fastapi/core/env_machine/api.py
git commit -m "feat(env_machine): 申请接口添加权限验证依赖"
```

---

## Task 4: 添加环境配置

**Files:**
- Modify: `backend-fastapi/env/dev.env`
- Modify: `backend-fastapi/env/uat.env`
- Modify: `backend-fastapi/env/prod.env`

### Step 1: 添加开发环境配置

```bash
# 在 backend-fastapi/env/dev.env 文件末尾添加
# ==================== 执行机申请权限配置 ====================
# 执行机申请权限配置（JSON格式），key -> namespace列表 的映射
ENV_APPLY_AUTH={"dev_key":["meeting_gamma","meeting_app","meeting_perf"]}
```

### Step 2: 添加 UAT 环境配置

```bash
# 在 backend-fastapi/env/uat.env 文件末尾添加
# ==================== 执行机申请权限配置 ====================
ENV_APPLY_AUTH={"uat_key_gamma":["meeting_gamma"],"uat_key_app":["meeting_app"]}
```

### Step 3: 添加生产环境配置

```bash
# 在 backend-fastapi/env/prod.env 文件末尾添加
# ==================== 执行机申请权限配置 ====================
ENV_APPLY_AUTH={"prod_key_gamma":["meeting_gamma"],"prod_key_app":["meeting_app"]}
```

### Step 4: Commit

```bash
git add backend-fastapi/env/dev.env backend-fastapi/env/uat.env backend-fastapi/env/prod.env
git commit -m "feat: 添加各环境执行机申请权限配置"
```

---

## Task 5: 功能测试验证

**Files:**
- None (手动测试)

### Step 1: 启动后端服务

```bash
cd backend-fastapi
python main.py
```
Expected: 服务正常启动在 http://localhost:8000

### Step 2: 测试缺少 Header（应返回 401）

```bash
curl -X POST http://localhost:8000/api/core/env/meeting_gamma/application \
  -H "Content-Type: application/json" \
  -d '{"userA": "windows"}'
```
Expected: 返回 401，错误信息：{"detail": "缺少 X-Env-Auth header"}

### Step 3: 测试错误的 key（应返回 401）

```bash
curl -X POST http://localhost:8000/api/core/env/meeting_gamma/application \
  -H "Content-Type: application/json" \
  -H "X-Env-Auth: wrong_key" \
  -d '{"userA": "windows"}'
```
Expected: 返回 401，错误信息：{"detail": "权限不足: 无权申请该命名空间的机器"}

### Step 4: 测试正确的 key（应成功）

```bash
curl -X POST http://localhost:8000/api/core/env/meeting_gamma/application \
  -H "Content-Type: application/json" \
  -H "X-Env-Auth: dev_key" \
  -d '{"userA": "windows"}'
```
Expected: 返回成功响应（status: success 或 fail，取决于机器池状态）

### Step 5: 测试多 namespace 授权

```bash
# dev_key 授权了 meeting_app，应成功
curl -X POST http://localhost:8000/api/core/env/meeting_app/application \
  -H "Content-Type: application/json" \
  -H "X-Env-Auth: dev_key" \
  -d '{"userA": "windows"}'
```
Expected: 返回成功响应

### Step 6: 测试未授权 namespace

```bash
# dev_key 未授权 meeting_public（假设存在），应返回 401
curl -X POST http://localhost:8000/api/core/env/meeting_public/application \
  -H "Content-Type: application/json" \
  -H "X-Env-Auth: dev_key" \
  -d '{"userA": "windows"}'
```
Expected: 返回 401

---

## Task 6: 最终提交和文档更新

**Files:**
- None

### Step 1: 查看所有改动

```bash
git status
```
Expected: 所有文件已提交

### Step 2: 查看提交历史

```bash
git log --oneline -5
```
Expected: 看到4个新增提交

### Step 3: 功能验收

确认以下功能正常：
- ✓ 配置正确加载
- ✓ 缺少 Header 返回 401
- ✓ 错误 key 返回 401
- ✓ 正确 key + 授权 namespace 成功申请
- ✓ 正确 key + 未授权 namespace 返回 401
- ✓ 其他接口不受影响（注册、释放等）

---

## 注意事项

1. **配置为空时的行为**：当 ENV_APPLY_AUTH 为空时，所有申请都会被拒绝（安全优先原则）
2. **测试时确保有可用机器池**：申请成功需要 namespace 下有可用的机器
3. **不影响其他接口**：只对申请接口添加验证，注册、保持使用、释放等接口无需 Header
4. **错误信息安全**：不暴露传入的 key 值和授权的 namespace 列表