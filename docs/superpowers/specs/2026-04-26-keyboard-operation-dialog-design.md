---
name: keyboard-operation-dialog
description: Windows/MAC 远程桌面控制按键操作弹窗设计
type: project
---

# Windows/MAC 按键操作弹窗设计

## 概述

为设备调试功能（device-debug）添加 Windows 和 MAC 平台的按键操作弹窗，支持用户通过虚拟键盘远程发送按键和组合键操作。

**Why:** 当前按键操作弹窗（KeyPressDialog.vue）仅支持 Android/iOS 的移动端按键（HOME、BACK、音量键等），Windows 和 MAC 设备的键盘操作功能缺失，影响远程桌面控制体验。

**How to apply:** 本设计用于指导前端弹窗组件的开发，包括 UI 布局、交互逻辑和平台适配。

## 设计目标

1. **弹窗选择按键** - 提供虚拟键盘界面，用户点击按钮发送按键
2. **组合键支持** - 支持常用组合键一键发送，以及自定义组合键累加发送
3. **单独按键发送** - 支持所有标准键盘按键的单独发送
4. **平台动态适配** - 根据设备类型自动显示 Windows 或 MAC 键盘布局

## 功能设计

### 1. 弹窗布局结构

弹窗采用居中布局，包含以下区域：

```
┌─────────────────────────────────────────────────────────────┐
│  常用快捷键区 (一键发送预设组合键)                              │
├─────────────────────────────────────────────────────────────┤
│  虚拟键盘区 (108键标准布局)                     │ 使用说明 │
│  ┌─────────────┬──────────┬──────────┐        │          │
│  │ 主键盘区    │ 编辑键区 │ 数字键盘 │        │  右侧    │
│  │ (字母/数字/ │ Ins/Home │ Num/7-9  │        │  说明    │
│  │  F1-F12)    │ Del/End  │ / * - +  │        │  区域    │
│  │             │ 方向键   │ Enter/.  │        │          │
│  │ 修饰键行    │          │          │        │          │
│  │ (Ctrl/Alt/  │          │          │        │          │
│  │  Win/Space) │          │          │        │          │
│  └─────────────┴──────────┴──────────┘        │          │
├─────────────────────────────────────────────────────────────┤
│  [清空修饰键] [关闭]                                         │
└─────────────────────────────────────────────────────────────┘
```

### 2. 常用快捷键区

预设组合键按钮，点击直接发送，无需累加操作：

| 快捷键 | 功能 | 颜色 |
|--------|------|------|
| Ctrl+C | 复制 | 蓝色 |
| Ctrl+V | 粘贴 | 蓝色 |
| Ctrl+Z | 撤销 | 蓝色 |
| Ctrl+S | 保存 | 蓝色 |
| Ctrl+A | 全选 | 橙色 |
| Alt+Tab | 切换窗口 | 绿色 |
| Ctrl+Alt+Del | 安全选项 | 红色 |
| Shift+Del | 永久删除 | 灰色 |
| Win+E | 打开文件管理器 | 绿色 |
| Win+D | 显示桌面 | 绿色 |

**MAC 模式对应快捷键：**
- Ctrl → Command(⌘)
- Alt → Option(⌥)
- Win → Command(⌘)

### 3. 虚拟键盘区

#### 3.1 主键盘区（左侧）

按标准108键键盘排列：

**功能键行：** PrtSc | ScrLk | Pause | Esc | F1-F12

**数字行：** 1-9 | 0 | - | = | Backspace

**字母行：**
- 第一行：Tab | Q W E R T Y U I O P | [ ] \
- 第二行：Caps | A S D F G H J K L | ; ' Enter
- 第三行：Shift | Z X C V B N M | , . / | Shift

**修饰键行（底行）：** Ctrl | Win | Alt | Space | Alt | Win | Menu | Ctrl

> 修饰键（Ctrl/Alt/Win）显示橙色，表示支持累加模式。

#### 3.2 编辑键区（中间）

| 按键 | 功能 |
|------|------|
| Ins | 插入模式 |
| Home | 行首 |
| PgUp | 上翻页 |
| Del | 删除 |
| End | 行尾 |
| PgDn | 下翻页 |

**方向键：** ↑ | ← ↓ →

#### 3.3 数字小键盘区（右侧）

| Num | / | * | - |
| 7 | 8 | 9 | + |
| 4 | 5 | 6 |   |
| 1 | 2 | 3 | Enter |
| 0 | . |   |   |

### 4. 修饰键交互逻辑

#### 4.1 累加模式

修饰键（Ctrl、Alt、Shift、Win/Cmd）支持组合键累加操作：

**流程：**
1. 用户点击修饰键 → 按键进入"按下"状态（橙色高亮），不立即发送
2. 用户继续点击其他键 → 系统组装组合键并发送
3. 发送后 → 修饰键状态自动清空，恢复初始状态

**示例：**
- 点击 Ctrl → Ctrl 高亮
- 点击 C → 发送 `Ctrl+C`，Ctrl 状态清空

**多修饰键组合：**
- 点击 Ctrl → Ctrl 高亮
- 点击 Alt → Ctrl+Alt 高亮
- 点击 Del → 发送 `Ctrl+Alt+Del`，状态清空

#### 4.2 清空操作

用户可点击"清空修饰键"按钮手动清空当前累加状态，无需发送按键。

### 5. 使用说明区域

弹窗右侧显示蓝色说明区域，内容包括：

```
使用说明

🔵 常用快捷键
点击按钮直接发送组合键，无需其他操作

🟠 修饰键 (Ctrl/Alt/Win)
用于组合键累加操作：
- 点击修饰键 → 高亮显示
- 再点击其他键 → 发送组合
- 例：点Ctrl，再点C → 发送Ctrl+C

⚪ 普通按键
点击直接发送单个按键

💡 发送组合键后，修饰键状态自动清空。
需手动清空请点"清空修饰键"
```

### 6. 平台差异适配

#### 6.1 动态检测

根据 `deviceType` 属性自动切换键盘布局：

| deviceType | 平台 | 修饰键 |
|------------|------|--------|
| windows | Windows | Ctrl, Alt, Win |
| mac | macOS | Ctrl, ⌥ Opt, ⌘ Cmd, Fn |

#### 6.2 MAC 特殊键映射

MAC 键盘无部分 Windows 键，需映射处理：

| Windows 键 | MAC 映射 |
|------------|----------|
| Home | Fn + ← |
| End | Fn + → |
| PgUp | Fn + ↑ |
| PgDn | Fn + ↓ |
| Del (删除) | Fn + Backspace |
| Menu | 无对应，可隐藏 |

#### 6.3 MAC 快捷键转换

常用快捷键区显示 MAC 符号：

| Windows | MAC | 符号 |
|---------|-----|------|
| Ctrl+C | ⌘C | ⌘ |
| Ctrl+V | ⌘V | ⌘ |
| Alt+Tab | ⌘Tab | ⌘ |
| Win+E | ⌘E (Finder) | ⌘ |

## 技术实现要点

### 1. 组件结构

修改现有 `KeyPressDialog.vue`，扩展为支持多平台：

```vue
<KeyPressDialog
  :visible="dialogVisible"
  :device-type="deviceType"  // 'windows' | 'mac' | 'android' | 'ios'
  :disabled="isOperating"
  @update:visible="dialogVisible = $event"
  @press="handleKeyPress"
/>
```

### 2. 按键数据结构

定义按键列表，包含平台标识：

```typescript
interface KeyDefinition {
  value: string;       // 发送的按键代码
  label: string;       // 显示文本
  type: 'normal' | 'modifier';  // 按键类型
  platforms: DeviceType[];      // 支持的平台
}
```

### 3. 组合键发送逻辑

- **预设快捷键：** 直接调用 `pressKey('ctrl+c')` 格式
- **累加模式：** 维护 `activeModifiers` 数组，发送时拼接
- **后端处理：** 需支持组合键格式解析（如 `ctrl+c`、`ctrl+alt+delete`）

### 4. 后端 API 扩展

`press` 操作需支持组合键格式：

```python
# action_type: 'press'
# params: { 'key': 'ctrl+c' } 或 { 'key': 'a' }
```

## 成功标准

1. 用户可通过弹窗发送所有标准键盘按键
2. 常用快捷键一键发送，响应时间 < 500ms
3. 修饰键累加模式工作正常，状态显示清晰
4. Windows/MAC 平台自动适配，按键映射正确
5. 弹窗布局居中，键盘按108键标准排列

## 输出文件

- `web/apps/web-ele/src/views/device-debug/components/KeyPressDialog.vue` - 组件修改
- `web/apps/web-ele/src/views/device-debug/types.ts` - 类型定义扩展
- `backend-fastapi/core/env_machine/service.py` - 按键处理逻辑扩展（如需要）