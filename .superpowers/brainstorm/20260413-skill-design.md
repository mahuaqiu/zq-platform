---
name: skill-management-design
description: AI 助手 Skill 技能管理页面设计方案
type: project
---

# Skill 管理页面设计方案

## 概述

在 AI 助手模块中新增 Skill 技能管理子页面，用于管理 NanoClaw 的 Skill 文件（SKILL.md）。支持 Skill 的增删改查，以及 Skill 与群组角色的分配关系管理。

## 需求来源

根据 HTTP_API_INTEGRATION.md，NanoClaw 提供以下 Skill 相关 API：

**Skill 全局管理**：
- `GET /api/skills` - 查询所有全局 Skill
- `GET /api/skills/{skillId}` - 查询 Skill 详情（包含完整 content）
- `POST /api/skills/{skillId}` - 新增 Skill（传入完整 SKILL.md content）
- `PUT /api/skills/{skillId}` - 编辑 Skill
- `DELETE /api/skills/{skillId}` - 删除 Skill

**Skill 分配给角色（关键：需要群组+角色两个维度）**：
- `GET /api/profiles/{jid}/{profileId}/skills` - 查询特定群组中特定角色的 Skill 列表
- `POST /api/profiles/{jid}/{profileId}/skills/{skillId}` - 分配 Skill 到特定群组的特定角色
- `DELETE /api/profiles/{jid}/{profileId}/skills/{skillId}` - 移除特定群组特定角色的 Skill

**重要说明**：Skill 是分配给**特定群组中的特定角色**，不是全局分配给角色。同一个角色在不同群组可能有不同的 Skill 配置。

## 核心功能

### 1. Skill 列表页

**页面位置**：`/ai-assistant/skill`

**布局**：卡片列表形式

**列表字段**：
- Skill ID（唯一标识）
- Skill 名称（从 frontmatter 解析）
- 描述（从 frontmatter 解析）
- 已分配位置列表（显示"群组名 / 角色名"标签）
- 操作按钮：编辑、分配位置、删除

**搜索筛选**：
- 搜索 Skill ID 或名称
- 筛选未分配/已分配的 Skill

**交互**：
- 点击卡片进入编辑弹窗
- 点击"分配位置"打开分配弹窗（选择群组+角色）
- 点击"删除"确认后删除

### 2. Skill 编辑弹窗

**设计要点**：
- 弹窗宽度：650px
- 弹窗高度：自适应，最大 80vh
- 内容：仅包含 Monaco Editor，无需额外表单字段

**编辑器配置**：
- Monaco Editor（VS Code 风格）
- 深色主题（vs-dark）
- 语言：markdown
- 显示行号
- 语法高亮（YAML frontmatter + Markdown）
- minimap: false（关闭小地图）
- fontSize: 14

**SKILL.md 格式示例**：
```markdown
---
name: "agent-browser"
description: "Browse the web for any task"
---

# Browser Automation

Browse the web for any task:
- Research topics
- Read articles
- Interact with web apps
```

**保存逻辑**：
- 前端提交完整的 Markdown content
- 后端解析 frontmatter 提取 name 和 description
- Skill ID 从路由参数获取（编辑时不可修改）
- frontmatter 解析失败时返回错误提示

### 3. Skill 分配位置弹窗

**设计要点**：
- 弹窗宽度：500px
- 内容：群组-角色树形选择器

**选择器结构**：
```
技术讨论群
  ├ ☑ 小马助手 (@xiaoma)
  ├ ☐ 小威 (@小威)
  └ ☐ 技术专家 (@Tech)

日报群
  ├ ☐ 日报助手 (@Daily)
```

**交互**：
- 展开群组显示其下角色
- 勾选/取消勾选角色
- 显示已分配状态（高亮或勾选）
- 批量保存分配关系

**API 调用**：
- 获取群组列表：`GET /api/core/ai/group`（包含角色信息）
- 分配 Skill：`POST /api/profiles/{jid}/{profileId}/skills/{skillId}`
- 移除 Skill：`DELETE /api/profiles/{jid}/{profileId}/skills/{skillId}`

**jid 格式**：`http:{chat_id}`，如 `http:group-001`

### 4. 新增 Skill

**流程**：
1. 点击"新增 Skill"按钮
2. 打开编辑弹窗（空白内容）
3. 弹窗标题区域显示 Skill ID 输入框
4. 用户编写 SKILL.md 内容
5. 保存时调用 `POST /api/skills/{skillId}`

**Skill ID 验证**：
- 格式：字母、数字、短横线，如 `agent-browser`
- 不允许中文、空格、特殊符号

## 技术方案

### 前端实现

**新增文件**：
- `web/apps/web-ele/src/views/ai-assistant/skill/index.vue` - Skill 列表页
- `web/apps/web-ele/src/views/ai-assistant/skill/components/SkillEditDialog.vue` - 编辑弹窗
- `web/apps/web-ele/src/views/ai-assistant/skill/components/SkillAssignDialog.vue` - 分配位置弹窗

**API 接口**（添加到 `ai-assistant.ts`）：
```typescript
// Skill 类型定义
interface AISkill {
  id: string;
  name: string;
  description?: string;
  content: string;
  assigned_locations?: { group_name: string; role_name: string; jid: string; profile_id: string }[];
}

// Skill API 函数
getAISkillListApi(params)
getAISkillDetailApi(skill_id)
createAISkillApi(skill_id, content)
updateAISkillApi(skill_id, content)
deleteAISkillApi(skill_id)
getAISkillAssignmentsApi(skill_id)
assignSkillToProfileApi(jid, profile_id, skill_id)
removeSkillFromProfileApi(jid, profile_id, skill_id)
```

**路由配置**：
- 在 `ai-assistant.ts` 添加 Skill 路由

**Monaco Editor 集成**：
```typescript
import * as monaco from 'monaco-editor';

const editor = monaco.editor.create(container, {
  value: content,
  language: 'markdown',
  theme: 'vs-dark',
  minimap: { enabled: false },
  fontSize: 14,
  lineNumbers: 'on',
  automaticLayout: true,
});
```

**依赖安装**：
```bash
pnpm add monaco-editor
```

### 后端实现

**扩展 ai_assistant 模块**（不新建模块）：

**Schema（添加到 `ai_assistant/schema.py`）**：
```python
class AISkillBase(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    content: str

class AISkillCreate(BaseModel):
    id: str  # Skill ID，有格式验证
    content: str

class AISkillUpdate(BaseModel):
    content: str

class AISkillResponse(AISkillBase):
    assigned_locations: List[dict] = []  # [{group_name, role_name, jid, profile_id}]

class SkillAssignment(BaseModel):
    jid: str          # 群组标识，格式 http:{chat_id}
    profile_id: str   # 角色 ID
```

**Service（添加到 `ai_assistant/service.py`）**：
```python
class AISkillService:
    async def get_skill_list(self) -> List[AISkillResponse]
    async def get_skill_detail(self, skill_id: str) -> AISkillResponse
    async def create_skill(self, skill_id: str, content: str) -> AISkillResponse
    async def update_skill(self, skill_id: str, content: str) -> AISkillResponse
    async def delete_skill(self, skill_id: str)
    async def get_skill_assignments(self, skill_id: str) -> List[dict]
    async def assign_skill(self, skill_id: str, assignment: SkillAssignment)
    async def remove_skill(self, skill_id: str, jid: str, profile_id: str)
```

**API（添加到 `ai_assistant/api.py`）**：
```
GET  /api/core/ai/skill                     # Skill 列表
GET  /api/core/ai/skill/{skill_id}          # Skill 详情
POST /api/core/ai/skill                     # 新增 Skill
PUT  /api/core/ai/skill/{skill_id}          # 编辑 Skill
DELETE /api/core/ai/skill/{skill_id}        # 删除 Skill
GET  /api/core/ai/skill/{skill_id}/assignments  # 查询分配位置
POST /api/core/ai/skill/{skill_id}/assign   # 分配到群组角色
DELETE /api/core/ai/skill/{skill_id}/assign # 移除分配
```

**NanoClaw 客户端扩展（添加到 `nanoclaw_client.py`）**：
```python
async def get_skills(self) -> Dict[str, Any]
async def get_skill_detail(self, skill_id: str) -> Dict[str, Any]
async def create_skill(self, skill_id: str, content: str) -> Dict[str, Any]
async def update_skill(self, skill_id: str, content: str) -> Dict[str, Any]
async def delete_skill(self, skill_id: str) -> Dict[str, Any]
async def assign_skill_to_profile(self, jid: str, profile_id: str, skill_id: str) -> Dict[str, Any]
async def remove_skill_from_profile(self, jid: str, profile_id: str, skill_id: str) -> Dict[str, Any]
async def get_profile_skills(self, jid: str, profile_id: str) -> Dict[str, Any]
```

### 菜单配置

**后端菜单初始化脚本**：
- 创建 `scripts/init_ai_skill_menu.py`
- 作为 AI 助手的子菜单

## 实现顺序

1. **后端 NanoClaw 客户端扩展** - 添加 Skill API 方法
2. **后端 Schema 定义** - 在 ai_assistant/schema.py 添加 Skill Schema
3. **后端 Service 扩展** - 在 ai_assistant/service.py 添加 Skill Service
4. **后端 API 路由** - 在 ai_assistant/api.py 添加 Skill 路由
5. **前端 API 接口** - 在 ai-assistant.ts 添加 Skill API
6. **前端 Skill 列表页** - 卡片布局
7. **前端编辑弹窗** - Monaco Editor 集成
8. **前端分配位置弹窗** - 群组-角色树形选择器
9. **路由配置** - 添加 Skill 路由
10. **菜单初始化脚本** - 运行脚本创建菜单

## 为什么：业务需求
用户需要在平台上管理 NanoClaw 的 Skill 技能文件，包括创建自定义 Skill、编辑 Skill 内容、将 Skill 分配给不同群组的 AI 角色，实现精细化的 AI 能力管理。

## 如何应用：设计决策
- 采用弹窗编辑而非独立页面，是为了快速操作不离开列表页
- 使用 Monaco Editor 提供 VS Code 级别的编辑体验，适合编辑复杂 Markdown 内容
- Skill 信息从 frontmatter 解析而非单独字段，遵循 Markdown 文件的原始格式
- Skill 分配采用群组-角色树形选择器，因为 Skill 是分配给特定群组的特定角色，需同时选择两个维度