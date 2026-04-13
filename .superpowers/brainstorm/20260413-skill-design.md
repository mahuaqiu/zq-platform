---
name: skill-management-design
description: AI 助手 Skill 技能管理页面设计方案
type: project
---

# Skill 管理页面设计方案

## 概述

在 AI 助手模块中新增 Skill 技能管理子页面，用于管理 NanoClaw 的 Skill 文件（SKILL.md）。支持 Skill 的增删改查，以及 Skill 与 AI 角色（Profile）的分配关系管理。

## 需求来源

根据 HTTP_API_INTEGRATION.md，NanoClaw 提供以下 Skill 相关 API：

- `GET /api/skills` - 查询所有全局 Skill
- `GET /api/skills/{skillId}` - 查询 Skill 详情（包含完整 content）
- `POST /api/skills/{skillId}` - 新增 Skill（传入完整 SKILL.md content）
- `PUT /api/skills/{skillId}` - 编辑 Skill
- `DELETE /api/skills/{skillId}` - 删除 Skill
- `GET /api/profiles/{jid}/{profileId}/skills` - 查询角色的 Skill 列表
- `POST /api/profiles/{jid}/{profileId}/skills/{skillId}` - 分配 Skill 给角色
- `DELETE /api/profiles/{jid}/{profileId}/skills/{skillId}` - 移除角色的 Skill

## 核心功能

### 1. Skill 列表页

**页面位置**：`/ai-assistant/skill`

**布局**：卡片列表形式（方案 A）

**列表字段**：
- Skill ID（唯一标识）
- Skill 名称（从 frontmatter 解析）
- 描述（从 frontmatter 解析）
- 已分配角色列表（显示角色名称标签）
- 操作按钮：编辑、分配角色、删除

**搜索筛选**：
- 搜索 Skill ID 或名称
- 筛选未分配/已分配的 Skill

**交互**：
- 点击卡片进入编辑弹窗
- 点击"分配角色"打开角色分配弹窗
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

### 3. Skill 分配角色弹窗

**设计要点**：
- 弹窗宽度：400px
- 内容：角色勾选列表

**角色列表显示**：
- 角色名称
- 触发词（如 @xiaoma）
- 已分配/未分配状态（高亮区分）

**交互**：
- 勾选/取消勾选角色
- 批量保存分配关系

**API 调用**：
- 获取所有角色列表：调用现有角色管理 API
- 分配 Skill：调用 NanoClaw `POST /api/profiles/{jid}/{profileId}/skills/{skillId}`
- 移除 Skill：调用 NanoClaw `DELETE /api/profiles/{jid}/{profileId}/skills/{skillId}`

### 4. 新增 Skill

**流程**：
1. 点击"新增 Skill"按钮
2. 打开编辑弹窗（空白内容）
3. 用户输入 Skill ID（弹窗标题区域显示输入框）
4. 用户编写 SKILL.md 内容
5. 保存时调用 `POST /api/skills/{skillId}`

**Skill ID 输入**：
- 新增时弹窗标题改为输入框
- 编辑时弹窗标题显示 Skill ID（不可修改）

## 技术方案

### 前端实现

**新增文件**：
- `web/apps/web-ele/src/views/ai-assistant/skill/index.vue` - Skill 列表页
- `web/apps/web-ele/src/views/ai-assistant/skill/components/SkillEditDialog.vue` - 编辑弹窗
- `web/apps/web-ele/src/views/ai-assistant/skill/components/SkillAssignDialog.vue` - 分配角色弹窗
- `web/apps/web-ele/src/api/core/ai-skill.ts` - Skill API 接口定义

**路由配置**：
- 在 `web/apps/web-ele/src/router/routes/modules/ai-assistant.ts` 添加 Skill 路由

**Monaco Editor 集成**：
- 使用 `@monaco-editor/loader` 或直接引入 Monaco Editor
- 配置 markdown 语言模式
- 深色主题（vs-dark）

**依赖安装**：
```bash
pnpm add monaco-editor
```

### 后端实现

**新增模块**：`backend-fastapi/core/ai_skill/`

**文件结构**：
- `model.py` - Skill 数据模型（本地缓存）
- `schema.py` - Pydantic Schema
- `service.py` - SkillService（调用 NanoClaw API）
- `api.py` - FastAPI 路由

**后端路由**：
- `GET /api/core/ai/skill` - Skill 列表
- `GET /api/core/ai/skill/{skill_id}` - Skill 详情
- `POST /api/core/ai/skill` - 新增 Skill
- `PUT /api/core/ai/skill/{skill_id}` - 编辑 Skill
- `DELETE /api/core/ai/skill/{skill_id}` - 删除 Skill
- `GET /api/core/ai/skill/{skill_id}/roles` - 查询已分配角色
- `POST /api/core/ai/skill/{skill_id}/roles` - 批量分配角色

**NanoClaw 客户端扩展**：
- 在 `nanoclaw_client.py` 添加 Skill 相关 API 方法

### 菜单配置

**后端菜单初始化脚本**：
- 创建 `scripts/init_ai_skill_menu.py`
- 作为 AI 助手的子菜单

## 数据模型

### Skill Schema（前端）

```typescript
interface AISkill {
  id: string;           // Skill ID
  name: string;         // 从 frontmatter 解析
  description?: string; // 从 frontmatter 解析
  content: string;      // 完整 SKILL.md 内容
  assigned_roles?: AIRole[]; // 已分配角色列表
  sys_create_datetime?: string;
  sys_update_datetime?: string;
}
```

### Skill Schema（后端）

```python
class AISkillBase(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    content: str

class AISkillCreate(AISkillBase):
    pass

class AISkillUpdate(BaseModel):
    content: str  # 只更新 content，其他从 frontmatter 解析

class AISkillResponse(AISkillBase):
    assigned_roles: List[AIRoleBrief] = []
```

## 实现顺序

1. **后端 NanoClaw 客户端扩展** - 添加 Skill API 方法
2. **后端 Skill 模块** - 创建 model、schema、service、api
3. **后端菜单初始化** - 运行脚本创建菜单
4. **前端 API 接口** - 创建 ai-skill.ts
5. **前端 Skill 列表页** - 卡片布局
6. **前端编辑弹窗** - Monaco Editor 集成
7. **前端分配角色弹窗** - 角色勾选列表
8. **路由配置** - 添加 Skill 路由

## 为什么：业务需求
用户需要在平台上管理 NanoClaw 的 Skill 技能文件，包括创建自定义 Skill、编辑 Skill 内容、将 Skill 分配给不同的 AI 角色，实现精细化的 AI 能力管理。

## 如何应用：设计决策
- 采用弹窗编辑而非独立页面，是为了快速操作不离开列表页
- 使用 Monaco Editor 提供 VS Code 级别的编辑体验，适合编辑复杂 Markdown 内容
- Skill 信息从 frontmatter 解析而非单独字段，遵循 Markdown 文件的原始格式