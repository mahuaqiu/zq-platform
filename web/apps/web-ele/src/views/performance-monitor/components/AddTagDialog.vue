<script setup lang="ts">
import { ref } from 'vue';
import { ElDialog, ElForm, ElFormItem, ElInput, ElInputNumber, ElSelect, ElOption, ElButton, ElMessage } from 'element-plus';

defineProps<{
  visible: boolean;
  maxTime?: number; // 最大时间（秒），用于限制输入范围
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'submit', data: { name: string; type: 'peak' | 'stable'; start_time: number; end_time: number; note?: string }): void;
}>();

const form = ref({
  name: '',
  type: 'peak' as 'peak' | 'stable',
  start_time: 0,
  end_time: 60,
  note: '',
});

const handleClose = () => {
  emit('update:visible', false);
  // 重置表单
  form.value = { name: '', type: 'peak', start_time: 0, end_time: 60, note: '' };
};

const handleSubmit = () => {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入标签名称');
    return;
  }
  if (form.value.start_time >= form.value.end_time) {
    ElMessage.warning('开始时间必须早于结束时间');
    return;
  }

  emit('submit', {
    name: form.value.name.trim(),
    type: form.value.type,
    start_time: form.value.start_time,
    end_time: form.value.end_time,
    note: form.value.note || undefined,
  });
  handleClose();
};
</script>

<template>
  <ElDialog
    :model-value="visible"
    title="添加区间标签"
    width="400px"
    @update:model-value="emit('update:visible', $event)"
    @close="handleClose"
  >
    <ElForm label-width="80px">
      <ElFormItem label="标签名称">
        <ElInput
          v-model="form.name"
          placeholder="如：场景加载、发起共享"
        />
      </ElFormItem>
      <ElFormItem label="区间类型">
        <ElSelect v-model="form.type">
          <ElOption label="冲高" value="peak" />
          <ElOption label="稳态" value="stable" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="开始时间">
        <ElInputNumber
          v-model="form.start_time"
          :min="0"
          :max="maxTime || 99999"
          :step="1"
          placeholder="相对秒数"
        />
        <span style="margin-left: 8px; color: #999; font-size: 12px;">秒</span>
      </ElFormItem>
      <ElFormItem label="结束时间">
        <ElInputNumber
          v-model="form.end_time"
          :min="0"
          :max="maxTime || 99999"
          :step="1"
          placeholder="相对秒数"
        />
        <span style="margin-left: 8px; color: #999; font-size: 12px;">秒</span>
      </ElFormItem>
      <ElFormItem label="备注">
        <ElInput
          v-model="form.note"
          placeholder="可选"
        />
      </ElFormItem>
    </ElForm>
    <template #footer>
      <ElButton @click="handleClose">取消</ElButton>
      <ElButton type="primary" @click="handleSubmit">确定</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
/* 统一弹窗样式 */
</style>