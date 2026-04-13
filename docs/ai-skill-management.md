# Skill 管理功能文档

## 概述

Skill 管理功能允许用户在平台上管理 NanoClaw 的 Skill 技能文件，包括创建自定义 Skill、编辑 Skill 内容、将 Skill 分配给不同群组的 AI 角色。

## 功能位置

- **菜单路径**：AI助手 → Skill管理
- **页面路径**：`/ai-assistant/skill`

## API 接口

### 后端 API 端点

所有 Skill API 都在 `/api/core/ai/skill` 路径下：

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/core/ai/skill` | GET | Skill 列表 |
| `/api/core/ai/skill` | POST | 创建 Skill |
| `/api/core/ai/skill/{skill_id}` | GET | Skill 详情 |
| `/api/core/ai/skill/{skill_id}` | PUT | 更新 Skill |
| `/api/core/ai/skill/{skill_id}` | DELETE | 删除 Skill |
| `/api/core/ai/skill/{skill_id}/assignments` | GET | 查询分配位置 |
| `/api/core/ai/skill/{skill_id}/assign` | POST | 分配到群组角色 |
| `/api/core/ai/skill/{skill_id}/assign` | DELETE | 移除分配 |

### 1. Skill 列表

```
GET /api/core/ai/skill
```

**响应示例**：

```json
{
  "items": [
    {
      "id": "agent-browser",
      "name": "Browser Automation",
      "description": "Browse the web for any task",
      "content": "",
      "assigned_locations": [
        {
          "group_id": "group-001",
          "group_name": "技术讨论群",
          "jid": "http:group-001",
          "profile_id": "xiaoma",
          "profile_name": "小马助手"
        }
      ]
    }
  ],
  "total": 1
}
```

### 2. Skill 详情

```
GET /api/core/ai/skill/{skill_id}
```

**响应示例**：

```json
{
  "id": "agent-browser",
  "name": "Browser Automation",
  "description": "Browse the web for any task",
  "content": "---\nname: agent-browser\ndescription: Browse the web...\n---\n\n# Browser Automation\n\n...",
  "assigned_locations": [...]
}
```

### 3. 创建 Skill

```
POST /api/core/ai/skill
```

**请求体**：

```json
{
  "id": "my-custom-skill",
  "content": "---\nname: My Custom Skill\ndescription: A custom skill description\n---\n\n# My Skill\n\nInstructions here..."
}
```

**Skill ID 格式要求**：
- 只允许字母、数字、短横线
- 不允许中文、空格、特殊符号
- 正则表达式：`^[a-zA-Z0-9\-]+$`

**响应示例**：

```json
{
  "id": "my-custom-skill",
  "name": "My Custom Skill",
  "description": "A custom skill description",
  "content": "...",
  "assigned_locations": []
}
```

### 4. 更新 Skill

```
PUT /api/core/ai/skill/{skill_id}
```

**请求体**：

```json
{
  "content": "---\nname: Updated Name\ndescription: Updated description\n---\n\n# Updated Skill\n\nNew content..."
}
```

### 5. 删除 Skill

```
DELETE /api/core/ai/skill/{skill_id}
```

**响应**：

```json
{
  "status": "success",
  "message": "删除成功"
}
```

### 6. 查询分配位置

```
GET /api/core/ai/skill/{skill_id}/assignments
```

**响应示例**：

```json
{
  "skill_id": "agent-browser",
  "assignments": [
    {
      "group_id": "group-001",
      "group_name": "技术讨论群",
      "jid": "http:group-001",
      "profile_id": "xiaoma",
      "profile_name": "小马助手"
    }
  ],
  "count": 1
}
```

### 7. 分配到群组角色

```
POST /api/core/ai/skill/{skill_id}/assign
```

**请求体**：

```json
{
  "jid": "http:group-001",
  "profile_id": "xiaoma"
}
```

**重要说明**：Skill 分配给**特定群组中的特定角色**，不是全局分配。同一个角色在不同群组可能有不同的 Skill 配置。

**jid 格式**：`http:{chat_id}`，如 `http:group-001`

### 8. 移除分配

```
DELETE /api/core/ai/skill/{skill_id}/assign
```

**请求体**：

```json
{
  "jid": "http:group-001",
  "profile_id": "xiaoma"
}
```

## SKILL.md 文件格式

每个 Skill 是一个 Markdown 文件，包含 YAML frontmatter：

```markdown
---
name: "skill-name"
description: "Skill description"
---

# Skill Title

Skill content and instructions here...

## Features

- Feature 1
- Feature 2

## Usage

How to use this skill...
```

**frontmatter 字段**：
- `name`：Skill 名称（显示名称）
- `description`：Skill 描述

前端编辑时，name 和 description 从 frontmatter 解析，无需单独填写。

## 前端功能

### Skill 列表页

- 卡片布局展示 Skill
- 显示 Skill ID、名称、描述
- 显示已分配位置（群组/角色标签）
- 搜索和筛选功能
- 操作按钮：编辑、分配位置、删除

### Skill 编辑弹窗

- 使用 Monaco Editor（VS Code 风格）
- 深色主题，Markdown 语法高亮
- 显示行号，关闭小地图
- 新建时输入 Skill ID
- 编辑时只显示内容（ID 不可修改）

### Skill 分配位置弹窗

- 树形选择器展示群组和角色
- 群组作为父节点，角色作为子节点
- Checkbox 选择模式
- 保存时自动计算差异（添加/移除）

## 技术实现

### 后端文件

| 文件 | 说明 |
|------|------|
| `backend-fastapi/core/ai_assistant/nanoclaw_client.py` | NanoClaw API 客户端，8 个 Skill 方法 |
| `backend-fastapi/core/ai_assistant/schema.py` | Skill Schema 定义 |
| `backend-fastapi/core/ai_assistant/service.py` | AISkillService 服务类 |
| `backend-fastapi/core/ai_assistant/api.py` | Skill API 路由 |
| `backend-fastapi/scripts/init_ai_skill_menu.py` | 菜单初始化脚本 |

### 前端文件

| 文件 | 说明 |
|------|------|
| `web/apps/web-ele/src/api/core/ai-assistant.ts` | Skill API 接口定义 |
| `web/apps/web-ele/src/views/ai-assistant/skill/index.vue` | Skill 列表页 |
| `web/apps/web-ele/src/views/ai-assistant/skill/components/SkillEditDialog.vue` | 编辑弹窗（Monaco Editor） |
| `web/apps/web-ele/src/views/ai-assistant/skill/components/SkillAssignDialog.vue` | 分配位置弹窗 |
| `web/apps/web-ele/src/router/routes/modules/ai-assistant.ts` | Skill 路由配置 |

## 使用流程

### 创建新 Skill

1. 点击"新增 Skill"按钮
2. 输入 Skill ID（如 `my-skill`）
3. 编写 SKILL.md 内容（包含 frontmatter）
4. 保存

### 编辑 Skill

1. 点击 Skill 卡片的"编辑"按钮
2. 在 Monaco Editor 中修改内容
3. 保存

### 分配 Skill

1. 点击 Skill 卡片的"分配位置"按钮
2. 在树形选择器中勾选群组下的角色
3. 保存（自动添加/移除分配）

### 删除 Skill

1. 点击 Skill 卡片的"删除"按钮
2. 确认删除

## 初始化

首次使用需运行菜单初始化脚本：

```bash
cd backend-fastapi && python scripts/init_ai_skill_menu.py
```

这会在 AI助手菜单下创建 Skill管理 子菜单。