# 头像生成工具

## 📍 位置

`/src/utils/avatar.ts` 和 `/src/components/user-selector/user-card.vue`

## 🎯 功能

自动生成用户头像，当用户没有上传头像时使用。

### 特性

**智能文本生成**

- 汉字：显示第一个字
- 字母：显示前两个字母
- 其他：显示第一个字符

**美观的渐变背景**

- 20种精美渐变色
- 基于名字哈希的稳定性（相同名字始终使用同一渐变）
- 135度斜向渐变，视觉效果优雅
- 兼容深色/浅色主题

**优化的视觉设计**

- 文字大小 28px，加粗（font-weight: 700）
- 白色文字，带文字阴影
- 圆形头像，8px 阴影
- 悬停时动画效果（向上浮起 2px）

**完全集成**

- 在 user-card 组件中自动使用
- 不需要手动调用

## 📚 API

### 1. `generateAvatarText(name: string): string`

从名字生成头像显示文本

**示例**

```typescript
generateAvatarText('李明'); // 返回 '李'
generateAvatarText('John Doe'); // 返回 'JO'
```

### 2. `generateAvatarGradient(name: string): string`

根据名字生成漂亮的渐变背景色

**返回值格式**

```
linear-gradient(135deg, #667eea 0%, #764ba2 100%)
```

**特点**

- 返回完整的 CSS 渐变值
- 相同名字始终返回相同渐变
- 20种预设渐变色

### 3. `generateAvatarConfig(name: string): AvatarConfig`

生成完整的头像配置对象

**返回值**

```typescript
interface AvatarConfig {
  text: string; // 显示的文本
  backgroundColor: string; // 背景色 (十六进制，兼容用)
  gradient: string; // 渐变背景 CSS
  color?: string; // 文字颜色 (总是 #ffffff)
}
```

## 🎨 渐变色调色板

20种精心设计的渐变色：

```
紫蓝系：
  linear-gradient(135deg, #667eea 0%, #764ba2 100%)
  linear-gradient(135deg, #4158d0 0%, #c850c0 100%)

粉红系：
  linear-gradient(135deg, #f093fb 0%, #f5576c 100%)
  linear-gradient(135deg, #c471f5 0%, #fa71cd 100%)
  linear-gradient(135deg, #fa709a 0%, #fee140 100%)

青蓝系：
  linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)
  linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%)
  linear-gradient(135deg, #30cfd0 0%, #330867 100%)

绿系：
  linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)
  linear-gradient(135deg, #1f4037 0%, #00a86b 100%)
  linear-gradient(135deg, #56ab2f 0%, #a8e063 100%)

橙/红系：
  linear-gradient(135deg, #ff9a56 0%, #ff6a88 100%)
  linear-gradient(135deg, #ffa751 0%, #ffe259 100%)
  linear-gradient(135deg, #eb3349 0%, #f45c43 100%)
  linear-gradient(135deg, #f12c4f 0%, #ff9f1c 100%)
  linear-gradient(135deg, #872198 0%, #f4a261 100%)

浅色系：
  linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)
  linear-gradient(135deg, #1a7fa0 0%, #4facb3 100%)
  linear-gradient(135deg, #2e2e78 0%, #662d8c 100%)
```

## ✨ 视觉优化

### 文字样式

- **字号**: 28px
- **粗度**: font-weight 700（加粗）
- **颜色**: 白色 (#ffffff)
- **阴影**: 0 1px 2px rgba(0, 0, 0, 0.2)

### 头像样式

- **尺寸**: 56px × 56px
- **圆角**: 50% (完全圆形)
- **阴影**: 0 2px 8px rgba(0, 0, 0, 0.15)
- **渐变**: 135度斜向渐变

### 交互效果

- **悬停**: 向上浮起 2px，阴影加深
- **选中**: 边框变为主题色，背景变浅

## 🔧 在组件中使用

### user-card 组件

自动集成，无需配置。当用户没有头像时，组件会自动：

1. 生成头像文本（汉字/字母/字符）
2. 分配漂亮的渐变背景色
3. 以优雅的样式显示

```vue
<div
  v-if="!user.avatar"
  class="avatar-gradient"
  :style="{ background: avatarGradient }"
>
  <span class="avatar-text">{{ userInitials }}</span>
</div>
```

### 在其他组件中使用

```typescript
import { generateAvatarConfig } from '#/utils/avatar';

const avatarConfig = generateAvatarConfig('李明');

// 使用配置
console.log(avatarConfig.text); // '李'
console.log(avatarConfig.gradient); // 'linear-gradient(...)'
console.log(avatarConfig.color); // '#ffffff'
```

## 🌙 深色模式

头像在深色/浅色模式下都清晰可见：

- 渐变自动适配主题
- 文字始终白色
- 阴影自动调整

---

**更新时间**: 2025-11-04 **版本**: 2.0.0 - 渐变优化版本 **状态**: 生产就绪
