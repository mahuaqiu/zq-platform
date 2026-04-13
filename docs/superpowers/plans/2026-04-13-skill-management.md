# Skill 管理页面实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 AI 助手模块新增 Skill 技能管理页面，支持 Skill 的增删改查及分配给群组角色。

**Architecture:** 扩展现有 ai_assistant 后端模块，添加 Skill Schema、Service 和 API。前端新增 Skill 列表页、编辑弹窗和分配位置弹窗，集成 Monaco Editor 实现 Markdown 编辑。

**Tech Stack:** FastAPI + Vue 3 + Element Plus + Monaco Editor + NanoClaw API

---

## 文件结构

### 后端文件（扩展 ai_assistant 模块）

| 文件 | 职责 | 操作 |
|------|------|------|
| `backend-fastapi/core/ai_assistant/nanoclaw_client.py` | NanoClaw API 客户端，添加 Skill 相关方法 | 修改 |
| `backend-fastapi/core/ai_assistant/schema.py` | Pydantic Schema 定义，添加 Skill Schema | 修改 |
| `backend-fastapi/core/ai_assistant/service.py` | Skill 业务逻辑，不持久化（直接调用 NanoClaw） | 修改 |
| `backend-fastapi/core/ai_assistant/api.py` | FastAPI 路由，添加 Skill CRUD + 分配 API | 修改 |
| `backend-fastapi/scripts/init_ai_skill_menu.py` | 菜单初始化脚本 | 新增 |

### 前端文件

| 文件 | 职责 | 操作 |
|------|------|------|
| `web/apps/web-ele/src/api/core/ai-assistant.ts` | Skill API 接口定义 | 修改 |
| `web/apps/web-ele/src/views/ai-assistant/skill/index.vue` | Skill 列表页（卡片布局） | 新增 |
| `web/apps/web-ele/src/views/ai-assistant/skill/components/SkillEditDialog.vue` | Skill 编辑弹窗（Monaco Editor） | 新增 |
| `web/apps/web-ele/src/views/ai-assistant/skill/components/SkillAssignDialog.vue` | Skill 分配位置弹窗（树形选择器） | 新增 |
| `web/apps/web-ele/src/router/routes/modules/ai-assistant.ts` | 添加 Skill 路由配置 | 修改 |

---

## Task 1: 后端 NanoClaw 客户端扩展

**Files:**
- Modify: `backend-fastapi/core/ai_assistant/nanoclaw_client.py`

- [ ] **Step 1: 添加 Skill API 方法到 nanoclaw_client.py**

在 `nanoclaw_client.py` 文件末尾（`NanoClawClient` 类内）添加以下方法：

```python
    async def get_skills(self) -> Dict[str, Any]:
        """
        查询 NanoClaw 所有全局 Skill
        
        Returns:
            {"skills": [...], "count": N}
        """
        url = f"{self.api_url}/api/skills"
        logger.info(f"[NanoClaw] 查询 Skill 列表请求: GET {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 查询 Skill 列表响应: count={result.get('count', 0)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 查询 Skill 列表超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 查询 Skill 列表请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 查询 Skill 列表异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def get_skill_detail(self, skill_id: str) -> Dict[str, Any]:
        """
        查询 NanoClaw Skill 详情
        
        Args:
            skill_id: Skill ID
            
        Returns:
            {"id": "...", "name": "...", "description": "...", "content": "..."}
        """
        url = f"{self.api_url}/api/skills/{skill_id}"
        logger.info(f"[NanoClaw] 查询 Skill 详情请求: GET {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 查询 Skill 详情响应: id={skill_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 查询 Skill 详情超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 查询 Skill 详情请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 查询 Skill 详情异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def create_skill(self, skill_id: str, content: str) -> Dict[str, Any]:
        """
        创建 NanoClaw Skill
        
        Args:
            skill_id: Skill ID
            content: SKILL.md 完整内容（含 frontmatter）
            
        Returns:
            {"status": "ok", "id": "..."} 或 {"error": "..."}
        """
        url = f"{self.api_url}/api/skills/{skill_id}"
        data = {"content": content}
        logger.info(f"[NanoClaw] 创建 Skill 请求: POST {url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self.headers, json=data)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 创建 Skill 响应: id={skill_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 创建 Skill 超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 创建 Skill 请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 创建 Skill 异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def update_skill(self, skill_id: str, content: str) -> Dict[str, Any]:
        """
        更新 NanoClaw Skill
        
        Args:
            skill_id: Skill ID
            content: SKILL.md 完整内容（含 frontmatter）
            
        Returns:
            {"status": "ok", "id": "..."} 或 {"error": "..."}
        """
        url = f"{self.api_url}/api/skills/{skill_id}"
        data = {"content": content}
        logger.info(f"[NanoClaw] 更新 Skill 请求: PUT {url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.put(url, headers=self.headers, json=data)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 更新 Skill 响应: id={skill_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 更新 Skill 超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 更新 Skill 请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 更新 Skill 异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def delete_skill(self, skill_id: str) -> Dict[str, Any]:
        """
        删除 NanoClaw Skill
        
        Args:
            skill_id: Skill ID
            
        Returns:
            {"status": "ok", "id": "..."} 或 {"error": "..."}
        """
        url = f"{self.api_url}/api/skills/{skill_id}"
        logger.info(f"[NanoClaw] 删除 Skill 请求: DELETE {url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 删除 Skill 响应: id={skill_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 删除 Skill 超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 删除 Skill 请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 删除 Skill 异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def assign_skill_to_profile(
        self, jid: str, profile_id: str, skill_id: str
    ) -> Dict[str, Any]:
        """
        分配 Skill 到群组角色
        
        Args:
            jid: 群组标识，格式 http:{chat_id}
            profile_id: 角色 ID
            skill_id: Skill ID
            
        Returns:
            {"status": "ok", ...} 或 {"error": "..."}
        """
        url = f"{self.api_url}/api/profiles/{jid}/{profile_id}/skills/{skill_id}"
        logger.info(f"[NanoClaw] 分配 Skill 请求: POST {url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 分配 Skill 响应: skill={skill_id} -> profile={profile_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 分配 Skill 超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 分配 Skill 请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 分配 Skill 异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def remove_skill_from_profile(
        self, jid: str, profile_id: str, skill_id: str
    ) -> Dict[str, Any]:
        """
        移除群组角色的 Skill
        
        Args:
            jid: 群组标识，格式 http:{chat_id}
            profile_id: 角色 ID
            skill_id: Skill ID
            
        Returns:
            {"status": "ok", ...} 或 {"error": "..."}
        """
        url = f"{self.api_url}/api/profiles/{jid}/{profile_id}/skills/{skill_id}"
        logger.info(f"[NanoClaw] 移除 Skill 请求: DELETE {url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 移除 Skill 响应: skill={skill_id} from profile={profile_id}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 移除 Skill 超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 移除 Skill 请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 移除 Skill 异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}

    async def get_profile_skills(self, jid: str, profile_id: str) -> Dict[str, Any]:
        """
        查询群组角色的 Skill 列表
        
        Args:
            jid: 群组标识，格式 http:{chat_id}
            profile_id: 角色 ID
            
        Returns:
            {"skills": [...], "count": N} 或 {"error": "..."}
        """
        url = f"{self.api_url}/api/profiles/{jid}/{profile_id}/skills"
        logger.info(f"[NanoClaw] 查询角色 Skill 列表请求: GET {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info(f"[NanoClaw] 查询角色 Skill 列表响应: count={result.get('count', 0)}")
                return result
        except httpx.TimeoutException as e:
            logger.error(f"[NanoClaw] 查询角色 Skill 列表超时: {str(e)}")
            return {"error": "timeout", "message": str(e)}
        except httpx.RequestError as e:
            logger.error(f"[NanoClaw] 查询角色 Skill 列表请求失败: {str(e)}")
            return {"error": "request_error", "message": str(e)}
        except Exception as e:
            logger.error(f"[NanoClaw] 查询角色 Skill 列表异常: {str(e)}")
            return {"error": "unknown", "message": str(e)}
```

- [ ] **Step 2: 提交代码**

```bash
git add backend-fastapi/core/ai_assistant/nanoclaw_client.py
git commit -m "feat(ai): NanoClaw 客户端添加 Skill API 方法"
```

---

## Task 2: 后端 Skill Schema 定义

**Files:**
- Modify: `backend-fastapi/core/ai_assistant/schema.py`

- [ ] **Step 1: 在 schema.py 末尾添加 Skill Schema 定义**

```python
# ============ Skill Schema ============

class AISkillCreate(BaseModel):
    """创建 Skill"""
    id: str = Field(..., description="Skill ID（字母、数字、短横线）")
    content: str = Field(..., description="SKILL.md 完整内容（含 YAML frontmatter）")


class AISkillUpdate(BaseModel):
    """更新 Skill"""
    content: str = Field(..., description="SKILL.md 完整内容（含 YAML frontmatter）")


class SkillAssignment(BaseModel):
    """Skill 分配请求"""
    jid: str = Field(..., description="群组标识，格式 http:{chat_id}")
    profile_id: str = Field(..., description="角色 ID")


class SkillAssignmentRemove(BaseModel):
    """移除 Skill 分配请求"""
    jid: str = Field(..., description="群组标识，格式 http:{chat_id}")
    profile_id: str = Field(..., description="角色 ID")


class SkillAssignmentInfo(BaseModel):
    """Skill 分配位置信息"""
    group_id: str = Field(..., description="外部群组 ID")
    group_name: str = Field(..., description="群组名称")
    jid: str = Field(..., description="NanoClaw 群组标识")
    profile_id: str = Field(..., description="角色 ID")
    profile_name: str = Field(..., description="角色名称")


class AISkillResponse(BaseModel):
    """Skill 响应"""
    id: str = Field(..., description="Skill ID")
    name: Optional[str] = Field(None, description="Skill 名称（从 frontmatter 解析）")
    description: Optional[str] = Field(None, description="Skill 描述（从 frontmatter 解析）")
    content: str = Field(..., description="SKILL.md 完整内容")
    assigned_locations: List[SkillAssignmentInfo] = Field(
        default_factory=list, 
        description="已分配位置列表（群组 + 角色）"
    )


class AISkillListResponse(BaseModel):
    """Skill 列表响应"""
    items: List[AISkillResponse] = Field(default_factory=list, description="Skill 列表")
    total: int = Field(..., description="总数")
```

- [ ] **Step 2: 提交代码**

```bash
git add backend-fastapi/core/ai_assistant/schema.py
git commit -m "feat(ai): 添加 Skill Schema 定义"
```

---

## Task 3: 后端 Skill Service 实现

**Files:**
- Modify: `backend-fastapi/core/ai_assistant/service.py`

- [ ] **Step 1: 在 service.py 末尾添加 AISkillService 类**

需要先在文件开头添加 yaml 导入：

```python
import yaml  # 添加到现有导入语句中
```

然后在文件末尾添加：

```python
# ==================== Skill 服务 ====================

class AISkillService:
    """
    Skill 服务
    
    不使用数据库持久化，直接调用 NanoClaw API。
    """
    
    @staticmethod
    def parse_frontmatter(content: str) -> dict:
        """
        解析 SKILL.md 的 YAML frontmatter
        
        Args:
            content: SKILL.md 完整内容
            
        Returns:
            {"name": "...", "description": "..."} 或空字典
        """
        if not content.startswith("---"):
            return {}
        
        try:
            # 找到第二个 --- 的位置
            parts = content.split("---", 2)
            if len(parts) < 3:
                return {}
            
            frontmatter_str = parts[1].strip()
            if not frontmatter_str:
                return {}
            
            frontmatter = yaml.safe_load(frontmatter_str)
            return {
                "name": frontmatter.get("name", ""),
                "description": frontmatter.get("description", ""),
            }
        except yaml.YAMLError:
            return {}
        except Exception:
            return {}

    @classmethod
    async def get_skill_list(cls) -> List[AISkillResponse]:
        """
        获取 Skill 列表
        
        Returns:
            Skill 列表（不含 content）
        """
        from core.ai_assistant.nanoclaw_client import nanoclaw_client
        from core.ai_assistant.service import AIGroupService, AIRoleService
        from app.database import async_session_factory
        
        result = await nanoclaw_client.get_skills()
        
        if "error" in result:
            return []
        
        skills_data = result.get("skills", [])
        
        # 获取所有群组及其角色，用于计算分配位置
        async with async_session_factory() as db:
            groups = await AIGroupService.get_active_groups(db)
            
            # 构建 group_id -> group 的映射
            group_map = {}
            for g in groups:
                group_map[g.group_id] = g
            
            # 为每个 Skill 查询分配位置
            skills = []
            for skill in skills_data:
                skill_id = skill.get("id", "")
                
                # 查询该 Skill 的分配位置
                assigned_locations = []
                for group in groups:
                    jid = f"http:{group.group_id}"
                    for role in group.roles:
                        if role.is_active:
                            profile_skills = await nanoclaw_client.get_profile_skills(
                                jid, role.role_id or str(role.id)
                            )
                            if "error" not in profile_skills:
                                for ps in profile_skills.get("skills", []):
                                    if ps.get("id") == skill_id:
                                        assigned_locations.append({
                                            "group_id": group.group_id,
                                            "group_name": group.group_name,
                                            "jid": jid,
                                            "profile_id": role.role_id or str(role.id),
                                            "profile_name": role.name,
                                        })
                
                skills.append(AISkillResponse(
                    id=skill_id,
                    name=skill.get("name", skill_id),
                    description=skill.get("description", ""),
                    content="",  # 列表不返回完整内容
                    assigned_locations=assigned_locations,
                ))
        
        return skills

    @classmethod
    async def get_skill_detail(cls, skill_id: str) -> Optional[AISkillResponse]:
        """
        获取 Skill 详情
        
        Args:
            skill_id: Skill ID
            
        Returns:
            Skill 详情或 None
        """
        from core.ai_assistant.nanoclaw_client import nanoclaw_client
        from core.ai_assistant.service import AIGroupService
        from app.database import async_session_factory
        
        result = await nanoclaw_client.get_skill_detail(skill_id)
        
        if "error" in result:
            return None
        
        content = result.get("content", "")
        parsed = cls.parse_frontmatter(content)
        
        # 查询分配位置
        async with async_session_factory() as db:
            groups = await AIGroupService.get_active_groups(db)
            
            assigned_locations = []
            for group in groups:
                jid = f"http:{group.group_id}"
                for role in group.roles:
                    if role.is_active:
                        profile_skills = await nanoclaw_client.get_profile_skills(
                            jid, role.role_id or str(role.id)
                        )
                        if "error" not in profile_skills:
                            for ps in profile_skills.get("skills", []):
                                if ps.get("id") == skill_id:
                                    assigned_locations.append({
                                        "group_id": group.group_id,
                                        "group_name": group.group_name,
                                        "jid": jid,
                                        "profile_id": role.role_id or str(role.id),
                                        "profile_name": role.name,
                                    })
        
        return AISkillResponse(
            id=skill_id,
            name=parsed.get("name", skill_id),
            description=parsed.get("description", ""),
            content=content,
            assigned_locations=assigned_locations,
        )

    @classmethod
    async def create_skill(cls, skill_id: str, content: str) -> Optional[AISkillResponse]:
        """
        创建 Skill
        
        Args:
            skill_id: Skill ID
            content: SKILL.md 内容
            
        Returns:
            创建的 Skill 或 None
        """
        from core.ai_assistant.nanoclaw_client import nanoclaw_client
        
        # 验证 frontmatter 格式
        parsed = cls.parse_frontmatter(content)
        if not parsed:
            return None  # frontmatter 格式错误
        
        result = await nanoclaw_client.create_skill(skill_id, content)
        
        if "error" in result:
            return None
        
        return AISkillResponse(
            id=skill_id,
            name=parsed.get("name", skill_id),
            description=parsed.get("description", ""),
            content=content,
            assigned_locations=[],
        )

    @classmethod
    async def update_skill(cls, skill_id: str, content: str) -> Optional[AISkillResponse]:
        """
        更新 Skill
        
        Args:
            skill_id: Skill ID
            content: SKILL.md 内容
            
        Returns:
            更新后的 Skill 或 None
        """
        from core.ai_assistant.nanoclaw_client import nanoclaw_client
        
        parsed = cls.parse_frontmatter(content)
        
        result = await nanoclaw_client.update_skill(skill_id, content)
        
        if "error" in result:
            return None
        
        # 重新获取详情（含分配位置）
        return await cls.get_skill_detail(skill_id)

    @classmethod
    async def delete_skill(cls, skill_id: str) -> bool:
        """
        删除 Skill
        
        Args:
            skill_id: Skill ID
            
        Returns:
            是否成功
        """
        from core.ai_assistant.nanoclaw_client import nanoclaw_client
        
        result = await nanoclaw_client.delete_skill(skill_id)
        
        return "error" not in result

    @classmethod
    async def assign_skill(cls, skill_id: str, jid: str, profile_id: str) -> bool:
        """
        分配 Skill 到群组角色
        
        Args:
            skill_id: Skill ID
            jid: 群组标识
            profile_id: 角色 ID
            
        Returns:
            是否成功
        """
        from core.ai_assistant.nanoclaw_client import nanoclaw_client
        
        result = await nanoclaw_client.assign_skill_to_profile(jid, profile_id, skill_id)
        
        return "error" not in result

    @classmethod
    async def remove_skill_assignment(cls, skill_id: str, jid: str, profile_id: str) -> bool:
        """
        移除 Skill 分配
        
        Args:
            skill_id: Skill ID
            jid: 群组标识
            profile_id: 角色 ID
            
        Returns:
            是否成功
        """
        from core.ai_assistant.nanoclaw_client import nanoclaw_client
        
        result = await nanoclaw_client.remove_skill_from_profile(jid, profile_id, skill_id)
        
        return "error" not in result
```

- [ ] **Step 2: 提交代码**

```bash
git add backend-fastapi/core/ai_assistant/service.py
git commit -m "feat(ai): 添加 AISkillService 实现"
```

---

## Task 4: 后端 Skill API 路由

**Files:**
- Modify: `backend-fastapi/core/ai_assistant/api.py`

- [ ] **Step 1: 在 api.py 导入部分添加 Skill Schema**

在现有导入语句后添加：

```python
from core.ai_assistant.schema import (
    # ... 现有导入 ...
    AISkillCreate,
    AISkillUpdate,
    AISkillResponse,
    AISkillListResponse,
    SkillAssignment,
    SkillAssignmentRemove,
    SkillAssignmentInfo,
)
from core.ai_assistant.service import (
    # ... 环有导入 ...
    AISkillService,
)
```

- [ ] **Step 2: 在 api.py 末尾添加 Skill API 路由**

在文件末尾（最后一个路由之后）添加：

```python
# ==================== Skill 管理接口 ====================

@router.get("/skill", response_model=AISkillListResponse, summary="Skill 列表")
async def list_skills():
    """
    Skill 列表
    
    从 NanoClaw 获取所有 Skill，并计算分配位置。
    """
    skills = await AISkillService.get_skill_list()
    
    return AISkillListResponse(
        items=skills,
        total=len(skills),
    )


@router.get("/skill/{skill_id}", response_model=AISkillResponse, summary="Skill 详情")
async def get_skill_detail(skill_id: str) -> AISkillResponse:
    """
    Skill 详情
    
    Args:
        skill_id: Skill ID
    """
    skill = await AISkillService.get_skill_detail(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    
    return skill


@router.post("/skill", response_model=AISkillResponse, summary="创建 Skill")
async def create_skill(data: AISkillCreate) -> AISkillResponse:
    """
    创建 Skill
    
    Args:
        data: Skill 创建数据（含 id 和 content）
    """
    # 验证 Skill ID 格式
    import re
    if not re.match(r^[a-zA-Z0-9\-]+$, data.id):
        raise HTTPException(
            status_code=400, 
            detail="Skill ID 格式错误：只允许字母、数字、短横线"
        )
    
    # 验证 frontmatter 格式
    parsed = AISkillService.parse_frontmatter(data.content)
    if not parsed:
        raise HTTPException(
            status_code=400, 
            detail="SKILL.md 格式错误：缺少有效的 YAML frontmatter"
        )
    
    skill = await AISkillService.create_skill(data.id, data.content)
    if not skill:
        raise HTTPException(status_code=500, detail="NanoClaw 创建 Skill 失败")
    
    logger.info(f"创建 Skill 成功: id={data.id}")
    return skill


@router.put("/skill/{skill_id}", response_model=AISkillResponse, summary="更新 Skill")
async def update_skill(
    skill_id: str,
    data: AISkillUpdate
) -> AISkillResponse:
    """
    更新 Skill
    
    Args:
        skill_id: Skill ID
        data: Skill 更新数据（含 content）
    """
    skill = await AISkillService.update_skill(skill_id, data.content)
    if not skill:
        raise HTTPException(status_code=500, detail="NanoClaw 更新 Skill 失败")
    
    logger.info(f"更新 Skill 成功: id={skill_id}")
    return skill


@router.delete("/skill/{skill_id}", summary="删除 Skill")
async def delete_skill(skill_id: str):
    """
    删除 Skill
    
    Args:
        skill_id: Skill ID
    """
    success = await AISkillService.delete_skill(skill_id)
    if not success:
        raise HTTPException(status_code=500, detail="NanoClaw 删除 Skill 失败")
    
    logger.info(f"删除 Skill 成功: id={skill_id}")
    return {"status": "success", "message": "删除成功"}


@router.get("/skill/{skill_id}/assignments", summary="查询 Skill 分配位置")
async def get_skill_assignments(skill_id: str):
    """
    查询 Skill 已分配的群组角色列表
    
    Args:
        skill_id: Skill ID
    """
    skill = await AISkillService.get_skill_detail(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    
    return {
        "skill_id": skill_id,
        "assignments": skill.assigned_locations,
        "count": len(skill.assigned_locations),
    }


@router.post("/skill/{skill_id}/assign", summary="分配 Skill 到群组角色")
async def assign_skill(
    skill_id: str,
    data: SkillAssignment
):
    """
    分配 Skill 到指定群组的指定角色
    
    Args:
        skill_id: Skill ID
        data: 分配请求（含 jid 和 profile_id）
    """
    success = await AISkillService.assign_skill(skill_id, data.jid, data.profile_id)
    if not success:
        raise HTTPException(status_code=500, detail="NanoClaw 分配 Skill 失败")
    
    logger.info(f"分配 Skill 成功: skill={skill_id} -> jid={data.jid}, profile={data.profile_id}")
    return {"status": "success", "message": "分配成功"}


@router.delete("/skill/{skill_id}/assign", summary="移除 Skill 分配")
async def remove_skill_assignment(
    skill_id: str,
    data: SkillAssignmentRemove
):
    """
    移除指定群组角色的 Skill
    
    Args:
        skill_id: Skill ID
        data: 移除请求（含 jid 和 profile_id）
    """
    success = await AISkillService.remove_skill_assignment(
        skill_id, data.jid, data.profile_id
    )
    if not success:
        raise HTTPException(status_code=500, detail="NanoClaw 移除 Skill 分配失败")
    
    logger.info(f"移除 Skill 分配成功: skill={skill_id} from jid={data.jid}, profile={data.profile_id}")
    return {"status": "success", "message": "移除成功"}
```

- [ ] **Step 3: 提交代码**

```bash
git add backend-fastapi/core/ai_assistant/api.py
git commit -m "feat(ai): 添加 Skill API 路由"
```

---

## Task 5: 前端 Skill API 接口

**Files:**
- Modify: `web/apps/web-ele/src/api/core/ai-assistant.ts`

- [ ] **Step 1: 在 ai-assistant.ts 末尾添加 Skill API**

```typescript
// ========== Skill 类型定义 ==========

/**
 * Skill 分配位置信息
 */
export interface SkillAssignmentInfo {
  group_id: string;
  group_name: string;
  jid: string;
  profile_id: string;
  profile_name: string;
}

/**
 * AI Skill
 */
export interface AISkill {
  id: string;
  name: string;
  description?: string;
  content: string;
  assigned_locations: SkillAssignmentInfo[];
}

/**
 * Skill 创建请求
 */
export interface AISkillCreate {
  id: string;
  content: string;
}

/**
 * Skill 更新请求
 */
export interface AISkillUpdate {
  content: string;
}

/**
 * Skill 分配请求
 */
export interface SkillAssignment {
  jid: string;
  profile_id: string;
}

/**
 * Skill 列表响应
 */
export interface AISkillListResponse {
  items: AISkill[];
  total: number;
}

// ========== Skill API ==========

/**
 * 获取 Skill 列表
 */
export async function getAISkillListApi() {
  return requestClient.get<AISkillListResponse>('/api/core/ai/skill');
}

/**
 * 获取 Skill 详情
 */
export async function getAISkillDetailApi(skillId: string) {
  return requestClient.get<AISkill>(`/api/core/ai/skill/${skillId}`);
}

/**
 * 创建 Skill
 */
export async function createAISkillApi(data: AISkillCreate) {
  return requestClient.post<AISkill>('/api/core/ai/skill', data);
}

/**
 * 更新 Skill
 */
export async function updateAISkillApi(skillId: string, data: AISkillUpdate) {
  return requestClient.put<AISkill>(`/api/core/ai/skill/${skillId}`, data);
}

/**
 * 删除 Skill
 */
export async function deleteAISkillApi(skillId: string) {
  return requestClient.delete(`/api/core/ai/skill/${skillId}`);
}

/**
 * 查询 Skill 分配位置
 */
export async function getAISkillAssignmentsApi(skillId: string) {
  return requestClient.get<{ skill_id: string; assignments: SkillAssignmentInfo[]; count: number }>(
    `/api/core/ai/skill/${skillId}/assignments`
  );
}

/**
 * 分配 Skill 到群组角色
 */
export async function assignSkillToProfileApi(skillId: string, data: SkillAssignment) {
  return requestClient.post(`/api/core/ai/skill/${skillId}/assign`, data);
}

/**
 * 移除 Skill 分配
 */
export async function removeSkillFromProfileApi(skillId: string, data: SkillAssignment) {
  return requestClient.delete(`/api/core/ai/skill/${skillId}/assign`, { data });
}
```

- [ ] **Step 2: 提交代码**

```bash
git add web/apps/web-ele/src/api/core/ai-assistant.ts
git commit -m "feat(web): 添加 Skill API 接口定义"
```

---

## Task 6: 前端 Skill 列表页

**Files:**
- Create: `web/apps/web-ele/src/views/ai-assistant/skill/index.vue`

- [ ] **Step 1: 创建 Skill 列表页组件**

```vue
<script lang="ts" setup>
import type { AISkill, SkillAssignmentInfo } from '#/api/core/ai-assistant';

import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElDialog,
  ElEmpty,
  ElMessage,
  ElMessageBox,
  ElTag,
} from 'element-plus';

import {
  getAISkillListApi,
  deleteAISkillApi,
} from '#/api/core/ai-assistant';

import SkillEditDialog from './components/SkillEditDialog.vue';
import SkillAssignDialog from './components/SkillAssignDialog.vue';

defineOptions({ name: 'AISkillPage' });

// 数据
const skillList = ref<AISkill[]>([]);
const loading = ref(false);

// 弹窗控制
const editDialogVisible = ref(false);
const editDialogSkillId = ref('');
const editDialogContent = ref('');
const editDialogIsNew = ref(false);

const assignDialogVisible = ref(false);
const assignDialogSkillId = ref('');

// 加载数据
async function loadData() {
  loading.value = true;
  try {
    const res = await getAISkillListApi();
    skillList.value = res.items || [];
  } catch (error) {
    console.error('加载数据失败:', error);
    ElMessage.error('加载数据失败');
  } finally {
    loading.value = false;
  }
}

// 新增 Skill
function handleCreate() {
  editDialogIsNew.value = true;
  editDialogSkillId.value = '';
  editDialogContent.value = `---
name: ""
description: ""
---

# Skill Title

Skill content here...
`;
  editDialogVisible.value = true;
}

// 编辑 Skill
function handleEdit(skill: AISkill) {
  editDialogIsNew.value = false;
  editDialogSkillId.value = skill.id;
  editDialogContent.value = skill.content;
  editDialogVisible.value = true;
}

// 分配位置
function handleAssign(skill: AISkill) {
  assignDialogSkillId.value = skill.id;
  assignDialogVisible.value = true;
}

// 删除 Skill
function handleDelete(skill: AISkill) {
  ElMessageBox.confirm(`确定要删除 Skill "${skill.id}" 吗？`, '删除确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await deleteAISkillApi(skill.id);
      ElMessage.success('删除成功');
      loadData();
    } catch {
      ElMessage.error('删除失败');
    }
  });
}

// 编辑弹窗保存成功
function handleEditSuccess() {
  editDialogVisible.value = false;
  loadData();
}

// 分配弹窗保存成功
function handleAssignSuccess() {
  assignDialogVisible.value = false;
  loadData();
}

// 初始加载
onMounted(() => {
  loadData();
});
</script>

<template>
  <Page auto-content-height>
    <div class="skill-container">
      <!-- 头部区域 -->
      <div class="skill-header">
        <div class="header-row">
          <h2 class="skill-title">Skill 管理</h2>
          <ElButton type="primary" @click="handleCreate">
            + 新增 Skill
          </ElButton>
        </div>
      </div>

      <!-- Skill 卡片列表 -->
      <div class="skill-list" v-loading="loading">
        <template v-if="skillList.length > 0">
          <div class="skill-grid">
            <div
              v-for="skill in skillList"
              :key="skill.id"
              class="skill-card"
            >
              <!-- Skill ID 和名称 -->
              <div class="skill-card-header">
                <div class="skill-id">{{ skill.id }}</div>
                <div class="skill-name" v-if="skill.name && skill.name !== skill.id">
                  {{ skill.name }}
                </div>
              </div>

              <!-- 描述 -->
              <div class="skill-description" v-if="skill.description">
                {{ skill.description }}
              </div>

              <!-- 已分配位置 -->
              <div class="skill-assignments" v-if="skill.assigned_locations.length > 0">
                <span class="assignment-label">已分配：</span>
                <div class="assignment-tags">
                  <ElTag
                    v-for="loc in skill.assigned_locations"
                    :key="`${loc.jid}-${loc.profile_id}`"
                    size="small"
                    type="primary"
                    effect="plain"
                  >
                    {{ loc.group_name }} / {{ loc.profile_name }}
                  </ElTag>
                </div>
              </div>
              <div class="skill-assignments" v-else>
                <span class="assignment-label unassigned">未分配</span>
              </div>

              <!-- 操作按钮 -->
              <div class="skill-actions">
                <a class="skill-link" @click="handleEdit(skill)">编辑</a>
                <a class="skill-link" @click="handleAssign(skill)">分配位置</a>
                <a class="skill-link skill-link-danger" @click="handleDelete(skill)">删除</a>
              </div>
            </div>
          </div>
        </template>

        <template v-else>
          <ElEmpty description="暂无 Skill 数据" />
        </template>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <SkillEditDialog
      v-model:visible="editDialogVisible"
      :skill-id="editDialogSkillId"
      :content="editDialogContent"
      :is-new="editDialogIsNew"
      @success="handleEditSuccess"
    />

    <!-- 分配位置弹窗 -->
    <SkillAssignDialog
      v-model:visible="assignDialogVisible"
      :skill-id="assignDialogSkillId"
      @success="handleAssignSuccess"
    />
  </Page>
</template>

<style scoped>
.skill-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f5f5f5;
}

.skill-header {
  padding: 16px 20px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.skill-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.skill-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.skill-card {
  padding: 16px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  transition: box-shadow 0.2s;
}

.skill-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.skill-card-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.skill-id {
  font-size: 15px;
  font-weight: 600;
  color: #333;
}

.skill-name {
  font-size: 13px;
  color: #666;
}

.skill-description {
  font-size: 13px;
  color: #666;
  margin-bottom: 12px;
  line-height: 1.5;
}

.skill-assignments {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.assignment-label {
  font-size: 12px;
  color: #999;
}

.assignment-label.unassigned {
  color: #999;
}

.assignment-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.skill-actions {
  display: flex;
  gap: 12px;
}

.skill-link {
  font-size: 13px;
  color: #1890ff;
  cursor: pointer;
}

.skill-link:hover {
  text-decoration: underline;
}

.skill-link-danger {
  color: #ff4d4f;
}
</style>
```

- [ ] **Step 2: 创建 components 目录和 SkillEditDialog.vue**

创建目录：`web/apps/web-ele/src/views/ai-assistant/skill/components/`

先创建目录：

```bash
mkdir -p web/apps/web-ele/src/views/ai-assistant/skill/components
```

- [ ] **Step 3: 提交代码**

```bash
git add web/apps/web-ele/src/views/ai-assistant/skill/
git commit -m "feat(web): 创建 Skill 列表页组件"
```

---

## Task 7: 前端 Skill 编辑弹窗（Monaco Editor）

**Files:**
- Create: `web/apps/web-ele/src/views/ai-assistant/skill/components/SkillEditDialog.vue`

**前置依赖：安装 Monaco Editor**

```bash
cd web && pnpm add monaco-editor
```

- [ ] **Step 1: 安装 Monaco Editor**

```bash
cd web && pnpm add monaco-editor
```

- [ ] **Step 2: 创建 SkillEditDialog.vue**

```vue
<script lang="ts" setup>
import type { AISkillCreate, AISkillUpdate } from '#/api/core/ai-assistant';

import { nextTick, onMounted, ref, watch } from 'vue';

import {
  ElButton,
  ElDialog,
  ElInput,
  ElMessage,
} from 'element-plus';

import * as monaco from 'monaco-editor';
import {
  createAISkillApi,
  updateAISkillApi,
} from '#/api/core/ai-assistant';

interface Props {
  visible: boolean;
  skillId: string;
  content: string;
  isNew: boolean;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'success'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const dialogLoading = ref(false);
const editorRef = ref<monaco.editor.IStandaloneCodeEditor | null>(null);
const editorContainerRef = ref<HTMLElement | null>(null);

// 新增时的 Skill ID 输入
const newSkillId = ref('');

// 编辑器内容
const editorContent = ref(props.content);

// 监听 content 变化，更新编辑器
watch(() => props.content, (newContent) => {
  editorContent.value = newContent;
  if (editorRef.value) {
    editorRef.value.setValue(newContent);
  }
});

// 监听弹窗打开，初始化编辑器
watch(() => props.visible, async (visible) => {
  if (visible) {
    if (props.isNew) {
      newSkillId.value = '';
    }
    editorContent.value = props.content;
    
    await nextTick();
    initEditor();
  } else {
    destroyEditor();
  }
});

// 初始化编辑器
function initEditor() {
  if (!editorContainerRef.value) return;
  
  // 销毁旧编辑器
  destroyEditor();
  
  editorRef.value = monaco.editor.create(editorContainerRef.value, {
    value: editorContent.value,
    language: 'markdown',
    theme: 'vs-dark',
    minimap: { enabled: false },
    fontSize: 14,
    lineNumbers: 'on',
    automaticLayout: true,
    scrollBeyondLastLine: false,
    wordWrap: 'on',
  });
}

// 销毁编辑器
function destroyEditor() {
  if (editorRef.value) {
    editorRef.value.dispose();
    editorRef.value = null;
  }
}

// 获取编辑器内容
function getEditorContent(): string {
  if (editorRef.value) {
    return editorRef.value.getValue();
  }
  return editorContent.value;
}

// 提交保存
async function handleSubmit() {
  const content = getEditorContent();
  
  if (props.isNew) {
    // 新增：验证 Skill ID
    if (!newSkillId.value) {
      ElMessage.warning('请输入 Skill ID');
      return;
    }
    
    // 验证 Skill ID 格式
    const idPattern = /^[a-zA-Z0-9\-]+$/;
    if (!idPattern.test(newSkillId.value)) {
      ElMessage.warning('Skill ID 只允许字母、数字、短横线');
      return;
    }
    
    dialogLoading.value = true;
    try {
      await createAISkillApi({
        id: newSkillId.value,
        content,
      });
      ElMessage.success('创建成功');
      emit('success');
    } catch (error: any) {
      const msg = error?.response?.data?.detail || '创建失败';
      ElMessage.error(msg);
    } finally {
      dialogLoading.value = false;
    }
  } else {
    // 编辑
    dialogLoading.value = true;
    try {
      await updateAISkillApi(props.skillId, { content });
      ElMessage.success('更新成功');
      emit('success');
    } catch (error: any) {
      const msg = error?.response?.data?.detail || '更新失败';
      ElMessage.error(msg);
    } finally {
      dialogLoading.value = false;
    }
  }
}

// 关闭弹窗
function handleClose() {
  emit('update:visible', false);
}

// 组件卸载时销毁编辑器
onMounted(() => {
  if (props.visible) {
    initEditor();
  }
});
</script>

<template>
  <ElDialog
    :model-value="visible"
    :title="isNew ? '新增 Skill' : `编辑 Skill: ${skillId}`"
    width="650px"
    :close-on-click-modal="false"
    @update:model-value="handleClose"
  >
    <!-- 新增时显示 Skill ID 输入框 -->
    <div v-if="isNew" style="margin-bottom: 12px;">
      <ElInput
        v-model="newSkillId"
        placeholder="请输入 Skill ID（字母、数字、短横线）"
        style="width: 100%;"
      />
    </div>

    <!-- Monaco Editor 容器 -->
    <div
      ref="editorContainerRef"
      style="height: 400px; border: 1px solid #e8e8e8; border-radius: 4px; overflow: hidden;"
    ></div>

    <template #footer>
      <ElButton @click="handleClose">取消</ElButton>
      <ElButton type="primary" :loading="dialogLoading" @click="handleSubmit">
        保存
      </ElButton>
    </template>
  </ElDialog>
</template>
```

- [ ] **Step 3: 提交代码**

```bash
git add web/apps/web-ele/src/views/ai-assistant/skill/components/SkillEditDialog.vue
git commit -m "feat(web): 创建 Skill 编辑弹窗（Monaco Editor）"
```

---

## Task 8: 前端 Skill 分配位置弹窗

**Files:**
- Create: `web/apps/web-ele/src/views/ai-assistant/skill/components/SkillAssignDialog.vue`

- [ ] **Step 1: 创建 SkillAssignDialog.vue**

```vue
<script lang="ts" setup>
import type { AIGroup, SkillAssignmentInfo } from '#/api/core/ai-assistant';

import { onMounted, ref, watch } from 'vue';

import {
  ElButton,
  ElCheckbox,
  ElDialog,
  ElMessage,
  ElTree,
} from 'element-plus';

import {
  getAIGroupListApi,
  getAISkillAssignmentsApi,
  assignSkillToProfileApi,
  removeSkillFromProfileApi,
} from '#/api/core/ai-assistant';

interface Props {
  visible: boolean;
  skillId: string;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'success'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const loading = ref(false);
const saveLoading = ref(false);

// 群组列表
const groupList = ref<AIGroup[]>([]);

// 当前分配位置
const currentAssignments = ref<SkillAssignmentInfo[]>([]);

// 树形数据
const treeData = ref<any[]>([]);

// 选中的节点
const checkedNodes = ref<string[]>([]);

// 默认展开的节点
const expandedNodes = ref<string[]>([]);

// 监听弹窗打开
watch(() => props.visible, async (visible) => {
  if (visible) {
    await loadData();
  }
});

// 加载群组和分配数据
async function loadData() {
  loading.value = true;
  try {
    // 获取群组列表
    const groupRes = await getAIGroupListApi({
      is_active: true,
      page: 1,
      page_size: 100,
    });
    groupList.value = groupRes.items || [];
    
    // 获取当前分配
    const assignRes = await getAISkillAssignmentsApi(props.skillId);
    currentAssignments.value = assignRes.assignments || [];
    
    // 构建树形数据
    buildTreeData();
    
    // 设置选中节点
   setCheckedNodes();
  } catch (error) {
    console.error('加载数据失败:', error);
    ElMessage.error('加载数据失败');
  } finally {
    loading.value = false;
  }
}

// 构建树形数据
function buildTreeData() {
  treeData.value = groupList.value.map(group => {
    const children = group.roles
      .filter(role => role.is_active)
      .map(role => ({
        id: `${group.group_id}:${role.role_id || role.id}`,
        label: `${role.name} (${role.role_id ? '@' + role.role_id : ''})`,
        groupId: group.group_id,
        groupName: group.group_name,
        jid: `http:${group.group_id}`,
        profileId: role.role_id || role.id,
        profileName: role.name,
      }));
    
    return {
      id: group.group_id,
      label: group.group_name,
      children,
      isGroup: true,
    };
  });
  
  // 默认展开所有群组
  expandedNodes.value = groupList.value.map(g => g.group_id);
}

// 设置选中节点
function setCheckedNodes() {
  const checked: string[] = [];
  for (const loc of currentAssignments.value) {
    checked.push(`${loc.group_id}:${loc.profile_id}`);
  }
  checkedNodes.value = checked;
}

// 获取节点信息
function getNodeInfo(nodeId: string): { jid: string; profileId: string } | null {
  for (const group of treeData.value) {
    for (const child of group.children || []) {
      if (child.id === nodeId) {
        return {
          jid: child.jid,
          profileId: child.profileId,
        };
      }
    }
  }
  return null;
}

// 提交保存
async function handleSubmit() {
  saveLoading.value = true;
  
  try {
    // 计算新增和删除的分配
    const currentSet = new Set(
      currentAssignments.value.map(a => `${a.group_id}:${a.profile_id}`)
    );
    const newSet = new Set(checkedNodes.value);
    
    // 新增的分配
    const toAdd = checkedNodes.value.filter(id => !currentSet.has(id));
    // 删除的分配
    const toRemove = [...currentSet].filter(id => !newSet.has(id));
    
    // 执行新增
    for (const nodeId of toAdd) {
      const info = getNodeInfo(nodeId);
      if (info) {
        await assignSkillToProfileApi(props.skillId, {
          jid: info.jid,
          profile_id: info.profileId,
        });
      }
    }
    
    // 执行删除
    for (const nodeId of toRemove) {
      const info = getNodeInfo(nodeId);
      if (info) {
        await removeSkillFromProfileApi(props.skillId, {
          jid: info.jid,
          profile_id: info.profileId,
        });
      }
    }
    
    ElMessage.success('保存成功');
    emit('success');
  } catch (error: any) {
    const msg = error?.response?.data?.detail || '保存失败';
    ElMessage.error(msg);
  } finally {
    saveLoading.value = false;
  }
}

// 关闭弹窗
function handleClose() {
  emit('update:visible', false);
}
</script>

<template>
  <ElDialog
    :model-value="visible"
    :title="`分配 Skill: ${skillId}`"
    width="500px"
    :close-on-click-modal="false"
    @update:model-value="handleClose"
  >
    <div v-loading="loading" style="min-height: 200px;">
      <p style="color: #666; margin-bottom: 12px;">
        勾选群组下的角色，将 Skill 分配给该角色。
      </p>
      
      <ElTree
        :data="treeData"
        :props="{ label: 'label', children: 'children' }"
        show-checkbox
        default-expand-all
        node-key="id"
        :default-checked-keys="checkedNodes"
        :default-expanded-keys="expandedNodes"
        @check="(checkedKeys: any) => { checkedNodes = checkedKeys as string[]; }"
      >
        <template #default="{ node, data }">
          <span :style="{ fontWeight: data.isGroup ? '600' : '400' }">
            {{ data.label }}
          </span>
        </template>
      </ElTree>
    </div>

    <template #footer>
      <ElButton @click="handleClose">取消</ElButton>
      <ElButton type="primary" :loading="saveLoading" @click="handleSubmit">
        保存
      </ElButton>
    </template>
  </ElDialog>
</template>
```

- [ ] **Step 2: 提交代码**

```bash
git add web/apps/web-ele/src/views/ai-assistant/skill/components/SkillAssignDialog.vue
git commit -m "feat(web): 创建 Skill 分配位置弹窗（树形选择器）"
```

---

## Task 9: 前端路由配置

**Files:**
- Modify: `web/apps/web-ele/src/router/routes/modules/ai-assistant.ts`

- [ ] **Step 1: 添加 Skill 路由**

在 `ai-assistant.ts` 路由数组末尾添加：

```typescript
  {
    path: '/ai-assistant/skill',
    name: 'AIAssistantSkill',
    component: () => import('#/views/ai-assistant/skill/index.vue'),
    meta: {
      title: 'Skill 管理',
      hideInMenu: true,
    },
  },
```

- [ ] **Step 2: 提交代码**

```bash
git add web/apps/web-ele/src/router/routes/modules/ai-assistant.ts
git commit -m "feat(web): 添加 Skill 路由配置"
```

---

## Task 10: 后端菜单初始化脚本

**Files:**
- Create: `backend-fastapi/scripts/init_ai_skill_menu.py`

- [ ] **Step 1: 创建菜单初始化脚本**

参考现有的 `init_ai_assistant_menu.py` 创建：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-13
@File: init_ai_skill_menu.py
@Desc: 初始化 AI 助手 Skill 子菜单
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session_factory
from core.menu.model import Menu
from core.menu.service import MenuService


async def init_ai_skill_menu():
    """初始化 AI Skill 菜单"""
    async with async_session_factory() as db:
        # 查找 AI 助手父菜单
        result = await db.execute(
            select(Menu).where(
                Menu.name == "AI助手",
                Menu.is_deleted == False
            )
        )
        parent_menu = result.scalar_one_or_none()
        
        if not parent_menu:
            print("未找到 AI 助手父菜单，请先运行 init_ai_assistant_menu.py")
            return
        
        # 检查 Skill 菜单是否已存在
        result = await db.execute(
            select(Menu).where(
                Menu.parent_id == parent_menu.id,
                Menu.name == "Skill管理",
                Menu.is_deleted == False
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print("Skill 菜单已存在，跳过创建")
            return
        
        # 创建 Skill 子菜单
        skill_menu = Menu(
            name="Skill管理",
            code="ai_skill",
            path="/ai-assistant/skill",
            component="ai-assistant/skill/index",
            parent_id=parent_menu.id,
            icon="skill",  # 使用合适的图标
            sort=4,  # 排在角色、群组、会话之后
            is_enabled=True,
            is_visible=True,
            type=1,  # 菜单类型
        )
        db.add(skill_menu)
        await db.commit()
        
        print("Skill 菜单创建成功！")
        print(f"  - 名称: Skill管理")
        print(f"  - 路径: /ai-assistant/skill")
        print(f"  - 父菜单: AI助手")


if __name__ == "__main__":
    asyncio.run(init_ai_skill_menu())
```

- [ ] **Step 2: 运行菜单初始化脚本**

```bash
cd backend-fastapi && python scripts/init_ai_skill_menu.py
```

- [ ] **Step 3: 提交代码**

```bash
git add backend-fastapi/scripts/init_ai_skill_menu.py
git commit -m "feat(ai): 添加 Skill 菜单初始化脚本"
```

---

## Task 11: 测试和验证

- [ ] **Step 1: 启动后端服务测试 API**

```bash
cd backend-fastapi && python main.py
```

访问 Swagger UI: http://localhost:8000/docs
检查 `/api/core/ai/skill` 相关接口是否正常。

- [ ] **Step 2: 启动前端服务测试页面**

```bash
cd web && pnpm dev
```

访问 Skill 管理页面，测试：
- Skill 列表加载
- 新增 Skill（含 Monaco Editor）
- 编辑 Skill
- 分配位置（树形选择器）
- 删除 Skill

- [ ] **Step 3: 最终提交**

```bash
git status
# 确认所有修改已提交
git log --oneline -10
```

---

## 实现完成标志

当所有 checkbox 都被打勾时，Skill 管理页面实现完成。