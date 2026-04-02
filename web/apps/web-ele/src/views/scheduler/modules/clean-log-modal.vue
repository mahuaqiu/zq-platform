<script lang="ts" setup>
import type { CleanLogParams } from '#/api/core/scheduler';

import { computed, ref, watch } from 'vue';

import { ZqDialog } from '#/components/zq-dialog';

import { ElMessage, ElMessageBox } from 'element-plus';

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
const formData = ref<CleanLogParams>({
  days: 7,
  status: undefined,
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

// 清理状态选项
const statusOptions = [
  { label: '全部状态', value: undefined },
  { label: '仅失败记录', value: 'failed' },
  { label: '仅成功记录', value: 'success' },
];

// 计算弹窗标题
const dialogTitle = computed(() => '清理日志');

// 监听visible变化，重置表单
watch(
  () => props.visible,
  (newVal) => {
    if (newVal) {
      // 打开时重置表单
      formData.value = {
        days: 7,
        status: undefined,
      };
    }
  },
);

// 关闭弹窗
function handleClose() {
  emit('update:visible', false);
}

// 提交清理
async function handleSubmit() {
  // 二次确认
  try {
    await ElMessageBox.confirm(
      `确定要清理 ${formData.value.days} 天前的日志吗？此操作不可恢复！`,
      '确认清理',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    );
  } catch {
    // 用户取消
    return;
  }

  confirmLoading.value = true;
  try {
    const result = await cleanSchedulerLogsApi(formData.value);
    ElMessage.success(`成功清理 ${result.count} 条日志记录`);

    // 关闭弹窗
    handleClose();

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
    @update:model-value="handleClose"
    @confirm="handleSubmit"
  >
    <div class="clean-log-form">
      <!-- 警告提示 -->
      <div class="warning-box">
        <span class="warning-icon">⚠️</span>
        <span class="warning-text">清理后无法恢复，请谨慎操作</span>
      </div>

      <!-- 表单内容 -->
      <div class="form-content">
        <!-- 保留最近 -->
        <div class="form-item">
          <label class="form-label">保留最近</label>
          <el-select
            v-model="formData.days"
            placeholder="请选择保留天数"
            style="width: 100%"
          >
            <el-option
              v-for="item in retentionOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>

        <!-- 清理状态 -->
        <div class="form-item">
          <label class="form-label">清理状态</label>
          <el-select
            v-model="formData.status"
            placeholder="请选择要清理的状态"
            style="width: 100%"
            clearable
          >
            <el-option
              v-for="item in statusOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <div class="form-help">
            不选择则清理所有状态的日志记录
          </div>
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
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background-color: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 4px;
  margin-bottom: 24px;
}

.warning-icon {
  font-size: 16px;
  line-height: 1;
}

.warning-text {
  font-size: 14px;
  color: #d48806;
  font-weight: 500;
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

.form-label::before {
  content: '*';
  color: #ff4d4f;
  margin-right: 4px;
}

.form-help {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
</style>