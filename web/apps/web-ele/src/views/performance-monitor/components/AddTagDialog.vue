<script setup lang="ts">
import { ref } from 'vue';
import { ElDialog, ElForm, ElFormItem, ElInput, ElSelect, ElOption, ElDatePicker, ElButton, ElMessage } from 'element-plus';

defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'submit', data: { name: string; type: 'peak' | 'stable'; start_time: string; end_time: string; note?: string }): void;
}>();

const form = ref({
  name: '',
  type: 'peak' as 'peak' | 'stable',
  start_time: '',
  end_time: '',
  note: '',
});

const handleClose = () => {
  emit('update:visible', false);
  // 重置表单
  form.value = { name: '', type: 'peak', start_time: '', end_time: '', note: '' };
};

const handleSubmit = () => {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入标签名称');
    return;
  }
  if (!form.value.start_time || !form.value.end_time) {
    ElMessage.warning('请选择时间范围');
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
        <ElDatePicker
          v-model="form.start_time"
          type="datetime"
          placeholder="选择开始时间"
          format="YYYY-MM-DD HH:mm:ss"
          value-format="YYYY-MM-DDTHH:mm:ssZ"
        />
      </ElFormItem>
      <ElFormItem label="结束时间">
        <ElDatePicker
          v-model="form.end_time"
          type="datetime"
          placeholder="选择结束时间"
          format="YYYY-MM-DD HH:mm:ss"
          value-format="YYYY-MM-DDTHH:mm:ssZ"
        />
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
/* 统一弹窗样式，与性能监控标记弹窗保持一致 */
</style>