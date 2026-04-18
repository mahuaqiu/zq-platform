<script lang="ts" setup>
import { ref, watch } from 'vue';

import { ElButton, ElDialog, ElInputNumber } from 'element-plus';

interface Props {
  visible: boolean;
  screenshotWidth?: number;
  screenshotHeight?: number;
  disabled?: boolean;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'swipe', params: { from_x: number; from_y: number; to_x: number; to_y: number; duration: number }): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// 坐标数据
const fromX = ref(0);
const fromY = ref(0);
const toX = ref(0);
const toY = ref(0);
const duration = ref(500);

// 监听截图尺寸变化，更新默认坐标
watch(
  () => [props.screenshotWidth, props.screenshotHeight],
  ([width, height]) => {
    if (width && height) {
      // 默认起点在屏幕中间偏下
      fromX.value = Math.floor(width / 2);
      fromY.value = Math.floor(height * 0.8);
      // 默认终点在屏幕中间偏上
      toX.value = Math.floor(width / 2);
      toY.value = Math.floor(height * 0.2);
    }
  },
  { immediate: true }
);

// 关闭弹窗
function handleClose() {
  emit('update:visible', false);
}

// 执行滑动
function handleSwipe() {
  emit('swipe', {
    from_x: fromX.value,
    from_y: fromY.value,
    to_x: toX.value,
    to_y: toY.value,
    duration: duration.value,
  });
  handleClose();
}

// 接收从截图区域拖拽的坐标
function setFromPoint(x: number, y: number) {
  fromX.value = x;
  fromY.value = y;
}

function setToPoint(x: number, y: number) {
  toX.value = x;
  toY.value = y;
}

// 暴露方法供父组件调用
defineExpose({ setFromPoint, setToPoint });
</script>

<template>
  <ElDialog
    :model-value="visible"
    title="🎯 自定义滑动"
    width="400px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="swipe-form">
      <div class="form-group-label">起点坐标</div>
      <div class="form-group-row">
        <div class="form-field">
          <label class="form-label">X</label>
          <ElInputNumber
            v-model="fromX"
            :min="0"
            :max="screenshotWidth || 1000"
            :disabled="disabled"
            controls-position="right"
          />
        </div>
        <div class="form-field">
          <label class="form-label">Y</label>
          <ElInputNumber
            v-model="fromY"
            :min="0"
            :max="screenshotHeight || 2000"
            :disabled="disabled"
            controls-position="right"
          />
        </div>
      </div>
      <div class="form-group-label">终点坐标</div>
      <div class="form-group-row">
        <div class="form-field">
          <label class="form-label">X</label>
          <ElInputNumber
            v-model="toX"
            :min="0"
            :max="screenshotWidth || 1000"
            :disabled="disabled"
            controls-position="right"
          />
        </div>
        <div class="form-field">
          <label class="form-label">Y</label>
          <ElInputNumber
            v-model="toY"
            :min="0"
            :max="screenshotHeight || 2000"
            :disabled="disabled"
            controls-position="right"
          />
        </div>
      </div>
      <div class="form-group-label">滑动时长 (ms)</div>
      <ElInputNumber
        v-model="duration"
        :min="100"
        :max="2000"
        :step="100"
        :disabled="disabled"
        controls-position="right"
        class="duration-input"
      />
      <div class="swipe-tip">
        💡 可在截图上拖拽选择起点终点
      </div>
    </div>

    <template #footer>
      <ElButton @click="handleClose">取消</ElButton>
      <ElButton type="primary" :disabled="disabled" @click="handleSwipe">
        执行滑动
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.swipe-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-group-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 6px;
}

.form-group-row {
  display: flex;
  gap: 8px;
}

.form-field {
  flex: 1;
}

.form-label {
  font-size: 11px;
  color: #999;
  display: block;
  margin-bottom: 2px;
}

.form-field :deep(.el-input-number) {
  width: 100%;
}

.duration-input {
  width: 100%;
}

.swipe-tip {
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #666;
}
</style>