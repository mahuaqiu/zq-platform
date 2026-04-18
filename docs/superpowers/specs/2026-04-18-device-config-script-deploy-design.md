# 设备配置页面支持脚本下发功能设计

## 需求概述

远程设备新增了 scripts 接口，需要在配置管理页面新增支持下发脚本功能，并进行页面名称和文案调整。

## 需求清单

1. **页面名称调整**：配置管理 → 设备配置
2. **左侧面板标题**：配置模板 → 下发列表
3. **新建模板弹窗**：标题改为"新建模板"，新增模板类型选项（配置/脚本内容）
4. **脚本类型功能**：支持下发 Windows PowerShell/Batch 和 Mac Shell 脚本
5. **编辑器高亮**：根据模板类型动态切换语法高亮（YAML/PowerShell/Shell）
6. **右侧列表文案**：配置更新中 → 下发更新中，配置状态 → 下发状态

## Worker scripts 接口定义

```
URL: POST http://{host}:{port}/worker/scripts

请求参数:
{
  "name": "play_ppt.ps1",              // 必填，脚本名称，只允许 .ps1/.sh/.bat 扩展名
  "content": "param([string]$FilePath)...",  // 必填，脚本内容
  "version": "20260418-120000",        // 必填，版本号格式：YYYYMMDD-HHMMSS
  "overwrite": true                    // 可选，是否覆盖已有脚本，默认 true
}

成功响应:
{
  "status": "success",
  "message": "脚本更新成功",
  "name": "play_ppt.ps1",
  "version": "20260418-120000",
  "path": "D:\\code\\autotest\\tools\\play_ppt.ps1",
  "updated": true
}

错误响应:
- 400: 版本号格式无效 / 脚本名称不合法
- 409: 脚本更新进行中 / 脚本已存在且 overwrite=false
- 503: Worker 未初始化
```

## 设计方案

### 一、后端变更

#### 1. 数据模型变更

**修改 `config_template` 表，新增字段：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | String(20) | `config` | 模板类型：`config`（配置）/ `script`（脚本） |
| `script_name` | String(128) | null | 脚本名称（仅脚本类型使用），如 `play_ppt.ps1` |

**现有字段语义调整：**
- `name`：模板名称（用户自定义，如"默认配置模板"、"PPT播放脚本"）
- `config_content`：配置类型存储 YAML 内容；脚本类型存储脚本内容
- `namespace`：两种类型都使用，用于筛选下发目标设备

**约束规则：**
- 脚本类型时，`script_name` 必填
- 脚本名称扩展名只能是 `.ps1`、`.bat`、`.sh`
- 配置类型时，`script_name` 为 null

**脚本目标系统识别规则：**
| 扩展名 | 目标系统 | 设备类型过滤 |
|--------|---------|--------------|
| `.ps1`, `.bat` | Windows | device_type = 'windows' |
| `.sh` | Mac | device_type = 'mac' |

#### 2. Schema 变更

**ConfigTemplateCreate 新增字段：**
```python
type: str = Field(default="config", description="模板类型: config/script")
script_name: Optional[str] = Field(None, max_length=128, description="脚本名称")
```

**ConfigTemplateUpdate 新增字段：**
```python
type: Optional[str] = Field(None, description="模板类型")
script_name: Optional[str] = Field(None, max_length=128, description="脚本名称")
```

**ConfigTemplateResponse 新增字段：**
```python
type: str = Field(..., description="模板类型")
script_name: Optional[str] = Field(None, description="脚本名称")
```

#### 3. Service 变更

**新增方法：**

```python
@staticmethod
def _get_target_os_from_extension(script_name: str) -> str:
    """
    根据脚本扩展名返回目标操作系统

    :param script_name: 脚本名称
    :return: 'windows' 或 'mac'
    """
    ext = script_name.lower().split('.')[-1] if '.' in script_name else ''
    if ext in ('ps1', 'bat'):
        return 'windows'
    elif ext == 'sh':
        return 'mac'
    return ''

@staticmethod
async def _send_script_to_worker(machine: EnvMachine, template: ConfigTemplate) -> Tuple[bool, Optional[str], str]:
    """
    调用 Worker scripts 接口下发脚本

    :param machine: 机器对象
    :param template: 配置模板（脚本类型）
    :return: (是否成功, 错误信息, machine_id)
    """
    url = f"http://{machine.ip}:{machine.port}/worker/scripts"
    payload = {
        "name": template.script_name,
        "content": template.config_content,
        "version": template.version,
        "overwrite": True
    }
    # ... 发送请求逻辑
```

**修改 deploy_config 方法：**

根据 template.type 分别调用不同的下发方法：
- `type == 'config'` → 调用 `_send_config_to_worker`
- `type == 'script'` → 调用 `_send_script_to_worker`

**修改 get_preview 方法：**

脚本类型模板时，根据扩展名自动过滤设备类型：
```python
if template.type == 'script':
    target_os = cls._get_target_os_from_extension(template.script_name)
    if target_os == 'windows':
        conditions.append(EnvMachine.device_type == 'windows')
    elif target_os == 'mac':
        conditions.append(EnvMachine.device_type == 'mac')
```

#### 4. API 路由变更

**修改路由标签：**
```python
router = APIRouter(prefix="/config-template", tags=["设备配置管理"])
```

**新增校验逻辑：**
- 创建/更新时校验脚本名称扩展名合法性
- 脚本类型时校验 script_name 必填

### 二、前端变更

#### 1. 页面名称和文案调整

| 位置 | 当前文案 | 新文案 |
|------|---------|--------|
| 菜单 title | 配置管理 | 设备配置 |
| 左侧面板标题 | 📝 配置模板 | 📝 下发列表 |
| 弹窗标题 | 新建配置模板 / 编辑配置模板 | 新建模板 / 编辑模板 |
| 统计信息 | 配置更新中 | 下发更新中 |
| 表格列标题 | 配置状态 | 下发状态 |

#### 2. 新建/编辑模板弹窗

**新增字段：**

| 字段 | 类型 | 显示条件 | 说明 |
|------|------|---------|------|
| 模板类型 | 单选下拉 | 常显 | 选项：配置 / 脚本内容 |
| 脚本名称 | 文本输入 | 脚本类型时 | 提示：如 play_ppt.ps1，扩展名仅支持 .ps1/.bat/.sh |

**字段联动逻辑：**
- 选择"配置" → 编辑区标题显示"配置内容 (YAML)"，启用 YAML 高亮
- 选择"脚本内容" → 显示"脚本名称"输入框，编辑区标题显示"脚本内容"
- 输入脚本名称后，根据扩展名切换编辑器语言：
  - `.ps1/.bat` → PowerShell 高亮
  - `.sh` → Shell 高亮

#### 3. Monaco Editor 集成

**替换现有 textarea：**
- 使用 `@monaco-editor/loader` 或 `monaco-editor` 包
- 动态设置语言模式：`yaml` / `powershell` / `shell`
- 保持暗色主题风格（与现有样式一致）
- 配置基本选项：字体大小、行高、缩进

#### 4. 左侧模板列表显示

**配置类型模板：**
```
┌───────────────────────────────────┐
│ 默认配置模板                      │
│ 适用：全部命名空间                │
│ 版本：20260418-120000             │
│                   [编辑] [删除]    │
└───────────────────────────────────┘
```

**脚本类型模板：**
```
┌───────────────────────────────────┐
│ PPT播放脚本                       │
│ 适用：meeting_gamma               │
│ play_ppt.ps1        Windows       │
│ 版本：20260418-120000             │
│                   [编辑] [删除]    │
└───────────────────────────────────┘
```

**显示规则：**
- 脚本名称放在左侧，目标系统（Windows/Mac）放在右侧（同一行）
- 命名空间显示在第二行

#### 5. 下发预览逻辑

**脚本类型模板预览：**
- 自动过滤设备类型，只显示兼容的设备
- `.ps1/.bat` → 只查询 Windows 设备
- `.sh` → 只查询 Mac 设备
- 设备类型筛选下拉框对脚本类型禁用（已自动过滤）

#### 6. API 接口变更

**env-machine-config.ts 新增字段：**
```typescript
export interface ConfigTemplate {
  // ... 现有字段
  type: 'config' | 'script';
  script_name?: string;
}
```

### 三、菜单数据变更

**修改菜单脚本 `init_config_template_menu.py`：**
```python
menu.title = "设备配置"  # 从 "配置管理" 改为 "设备配置"
```

**或通过数据库直接更新：**
```sql
UPDATE menu SET title = '设备配置' WHERE id = 'env-machine-config';
```

### 四、数据库迁移

**Alembic 迁移脚本：**
```python
def upgrade():
    op.add_column('config_template', sa.Column('type', sa.String(20), nullable=False, server_default='config'))
    op.add_column('config_template', sa.Column('script_name', sa.String(128), nullable=True))

def downgrade():
    op.drop_column('config_template', 'script_name')
    op.drop_column('config_template', 'type')
```

## 实现顺序

1. **后端数据库迁移** - 新增 type、script_name 字段
2. **后端 Model/Schema 变更** - 更新模型定义和校验规则
3. **后端 Service 变更** - 新增脚本下发方法和预览过滤逻辑
4. **后端 API 变更** - 更新路由标签和校验
5. **菜单数据更新** - 修改菜单标题
6. **前端 API 定义变更** - 更新 TypeScript 类型
7. **前端页面变更** - 弹窗、编辑器、列表显示、文案调整
8. **测试验证** - 配置下发和脚本下发功能测试