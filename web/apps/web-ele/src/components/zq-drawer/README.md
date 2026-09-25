# ZqDrawer 抽屉组件

基于 ElementPlus 的 `el-drawer` 封装的抽屉组件，提供了更丰富的功能和更好的用户体验。

## 特性

- 📦 **开箱即用**：内置常用配置，快速上手
- 🎨 **灵活定制**：支持多个插槽，满足各种业务场景
- 🔄 **全屏切换**：支持全屏显示，提升内容展示空间
- 📱 **响应式**：自适应不同屏幕尺寸
- 🎯 **类型安全**：完整的 TypeScript 类型定义
- 🎭 **主题适配**：支持亮色/暗色主题切换

## 基础用法

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { ZqDrawer } from '@/components/zq-drawer';

const visible = ref(false);

function handleConfirm() {
  console.log('确认');
  visible.value = false;
}

function handleCancel() {
  console.log('取消');
}
</script>

<template>
  <ZqDrawer
    v-model="visible"
    title="抽屉标题"
    @confirm="handleConfirm"
    @cancel="handleCancel"
  >
    <div>抽屉内容</div>
  </ZqDrawer>
</template>
```

## API

### Props

| 参数 | 说明 | 类型 | 默认值 |
| --- | --- | --- | --- |
| modelValue | 是否显示抽屉 | `boolean` | `false` |
| title | 标题 | `string` | `''` |
| size | 抽屉宽度 | `string \| number` | `'30%'` |
| direction | 抽屉方向 | `'ltr' \| 'rtl' \| 'ttb' \| 'btt'` | `'rtl'` |
| contentHeight | 内容区固定高度 | `string \| number` | - |
| maxHeight | 内容区最大高度 | `string \| number` | - |
| loading | 内容区 loading 状态 | `boolean` | `false` |
| confirmLoading | 确认按钮 loading 状态 | `boolean` | `false` |
| showFooter | 是否显示底部 | `boolean` | `true` |
| showConfirmButton | 是否显示确认按钮 | `boolean` | `true` |
| showCancelButton | 是否显示取消按钮 | `boolean` | `true` |
| confirmText | 确认按钮文字 | `string` | `'确定'` |
| cancelText | 取消按钮文字 | `string` | `'取消'` |
| confirmButtonType | 确认按钮类型 | `'primary' \| 'success' \| 'warning' \| 'danger' \| 'info' \| 'default'` | `'primary'` |
| showFullscreenButton | 是否显示全屏按钮 | `boolean` | `true` |
| defaultFullscreen | 默认是否全屏 | `boolean` | `false` |
| showCloseButton | 是否显示关闭按钮 | `boolean` | `true` |
| destroyOnClose | 关闭时销毁内容 | `boolean` | `true` |
| closeOnClickModal | 点击遮罩层关闭 | `boolean` | `false` |
| appendToBody | 是否插入到 body | `boolean` | `true` |

### Events

| 事件名            | 说明                   | 回调参数           |
| ----------------- | ---------------------- | ------------------ |
| update:modelValue | 显示状态改变时触发     | `(value: boolean)` |
| confirm           | 点击确认按钮时触发     | -                  |
| cancel            | 点击取消按钮时触发     | -                  |
| open              | 抽屉打开动画开始时触发 | -                  |
| opened            | 抽屉打开动画结束时触发 | -                  |
| close             | 抽屉关闭动画开始时触发 | -                  |
| closed            | 抽屉关闭动画结束时触发 | -                  |

### Slots

| 插槽名         | 说明                                     |
| -------------- | ---------------------------------------- |
| default        | 抽屉内容                                 |
| title          | 标题区域                                 |
| header-extra   | 标题右侧额外内容（在全屏和关闭按钮之前） |
| footer         | 底部内容（完全自定义底部）               |
| footer-left    | 底部左侧内容                             |
| footer-prepend | 底部按钮前置插槽（在取消按钮之前）       |
| footer-append  | 底部按钮后置插槽（在确认按钮之后）       |

### Expose Methods

| 方法名            | 说明                      | 参数               |
| ----------------- | ------------------------- | ------------------ |
| open              | 打开抽屉                  | -                  |
| close             | 关闭抽屉                  | -                  |
| setLoading        | 设置内容区 loading 状态   | `(value: boolean)` |
| setConfirmLoading | 设置确认按钮 loading 状态 | `(value: boolean)` |

## 示例

### 自定义标题

```vue
<ZqDrawer v-model="visible">
  <template #title>
    <div class="flex items-center gap-2">
      <Icon icon="mdi:information" />
      <span>自定义标题</span>
    </div>
  </template>
  <div>内容</div>
</ZqDrawer>
```

### 自定义底部

```vue
<ZqDrawer v-model="visible" :show-footer="false">
  <div>内容</div>
  <template #footer>
    <div class="flex justify-end gap-2">
      <ElButton>自定义按钮1</ElButton>
      <ElButton type="primary">自定义按钮2</ElButton>
    </div>
  </template>
</ZqDrawer>
```

### 底部左侧插槽

```vue
<ZqDrawer v-model="visible">
  <template #footer-left>
    <ElButton type="danger">删除</ElButton>
  </template>
  <div>内容</div>
</ZqDrawer>
```

### 底部前置/后置插槽

```vue
<ZqDrawer v-model="visible">
  <template #footer-prepend>
    <ElButton>重置</ElButton>
  </template>
  <template #footer-append>
    <ElButton type="success">保存并继续</ElButton>
  </template>
  <div>内容</div>
</ZqDrawer>
```

### 隐藏头部按钮

```vue
<ZqDrawer
  v-model="visible"
  :show-fullscreen-button="false"
  :show-close-button="false"
>
  <div>内容</div>
</ZqDrawer>
```

### 隐藏底部按钮

```vue
<ZqDrawer
  v-model="visible"
  :show-confirm-button="false"
  :show-cancel-button="false"
>
  <div>内容</div>
</ZqDrawer>
```

### 使用 ref 控制

```vue
<script setup lang="ts">
import { ref } from 'vue';
import type { ZqDrawerExpose } from '@/components/zq-drawer';

const drawerRef = ref<ZqDrawerExpose>();

function openDrawer() {
  drawerRef.value?.open();
}

function closeDrawer() {
  drawerRef.value?.close();
}

async function handleConfirm() {
  drawerRef.value?.setConfirmLoading(true);
  await someAsyncOperation();
  drawerRef.value?.setConfirmLoading(false);
  drawerRef.value?.close();
}
</script>

<template>
  <ZqDrawer ref="drawerRef" @confirm="handleConfirm">
    <div>内容</div>
  </ZqDrawer>
</template>
```

### 不同方向

```vue
<ZqDrawer v-model="visible" direction="ltr">
  <div>从左侧弹出</div>
</ZqDrawer>

<ZqDrawer v-model="visible" direction="ttb">
  <div>从顶部弹出</div>
</ZqDrawer>

<ZqDrawer v-model="visible" direction="btt">
  <div>从底部弹出</div>
</ZqDrawer>
```
