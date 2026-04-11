<script lang="ts" setup>
import { computed, ref, watch } from 'vue';

import { ZqDialog } from '#/components/zq-dialog';

import { ElMessage, ElOption, ElSelect } from 'element-plus';

import { cleanSchedulerLogsApi } from '#/api/core/scheduler';

// Props
interface Props {
  visible: boolean;
}

const props = defineProps<Props>();

// Emits
const emit = defineEmits<{
  'update:visible': [value: boolean];
  success: [];
}>();

// 表单数据
const formData = ref({
  days: 7,
});

// 提交loading
const confirmLoading = ref(false);

// 保留最近选项
const retentionOptions = [
  { label: '7天', value: 7 },
  { label: '30天', value: 30 },
  { label: '90天', value: 90 },
  { label: '180天', value: 180 },
];

// 计算弹窗标题
const dialogTitle = computed(() => '清理执行日志');

// 监听visible变化，重置表单
watch(
  () => props.visible,
  (newVal) => {
    if (newVal) {
      // 打开时重置表单
      formData.value = {
        days: 7,
      };
    }
  },
);

// 同步弹窗状态给父组件
function handleUpdateVisible(val: boolean) {
  emit('update:visible', val);
}

// 提交清理
async function handleSubmit() {
  confirmLoading.value = true;
  try {
    const result = await cleanSchedulerLogsApi({ days: formData.value.days });
    ElMessage.success(`成功清理 ${result.count} 条日志记录`);

    // 关闭弹窗
    handleUpdateVisible(false);

    // 触发成功事件
    emit('success');
  } catch (error: any) {
    console.error('清理日志失败:', error);
    ElMessage.error(error?.message || '清理日志失败');
  } finally {
    confirmLoading.value = false;
  }
}
</script>

<template>
  <ZqDialog
    :model-value="visible"
    :title="dialogTitle"
    width="500px"
    :confirm-loading="confirmLoading"
    confirm-text="确认清理"
    confirm-button-type="danger"
    @update:model-value="handleUpdateVisible"
    @confirm="handleSubmit"
  >
    <div class="clean-log-form">
      <!-- 表单内容 -->
      <div class="form-content">
        <!-- 保留最近 -->
        <div class="form-item">
          <label class="form-label required">保留最近</label>
          <ElSelect
            v-model="formData.days"
            placeholder="请选择保留天数"
            style="width: 100%"
          >
            <ElOption
              v-for="item in retentionOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </ElSelect>
        </div>

        <!-- 警告提示 -->
        <div class="warning-box">
          <span style=" font-size: 13px;color: #d48806;">⚠️ 清理后无法恢复，请谨慎操作</span>
        </div>
      </div>
    </div>
  </ZqDialog>
</template>

<style scoped>
.clean-log-form {
  padding: 16px 0;
}

.warning-box {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 12px 16px;
  margin-bottom: 24px;
  background-color: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 4px;
}

.warning-icon {
  font-size: 16px;
  line-height: 1;
}

.warning-text {
  font-size: 14px;
  font-weight: 500;
  color: #d48806;
}

.form-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.form-label.required::before {
  margin-right: 4px;
  color: #ff4d4f;
  content: '*';
}

.form-help {
  margin-top: 4px;
  font-size: 12px;
  color: #999;
}
</style>