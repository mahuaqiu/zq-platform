<script lang="ts" setup>
import type { EnvMachine } from '#/api/core/env-machine';

import { computed, ref, watch } from 'vue';

import { ZqDialog } from '#/components/zq-dialog';

import { ElButton, ElMessage } from 'element-plus';

import { useVbenForm } from '#/adapter/form';
import { createEnvMachineApi, updateEnvMachineApi } from '#/api/core/env-machine';
import { isMobileDevice } from '../types';
import { useFormSchema } from '../data';

const props = defineProps<{
  namespace: string;
}>();

const emit = defineEmits(['success']);
const formData = ref<EnvMachine>();
const visible = ref(false);
const confirmLoading = ref(false);

const isMobile = computed(() => {
  const deviceType = formData.value?.device_type || 'windows';
  return isMobileDevice(deviceType as any);
});

const getTitle = computed(() => {
  return formData.value?.id ? '编辑设备' : '新增设备';
});

const [Form, formApi] = useVbenForm({
  layout: 'vertical',
  schema: useFormSchema(false),
  showDefaultActions: false,
});

// 监听设备类型变化，动态切换表单字段
watch(
  () => formApi.form?.values?.device_type,
  (newType) => {
    if (newType) {
      const mobile = isMobileDevice(newType as any);
      formApi.setState({ schema: useFormSchema(mobile) });
    }
  }
);

function resetForm() {
  formApi.resetForm();
  formApi.setValues(formData.value || {});
}

async function onSubmit() {
  const { valid } = await formApi.validate();
  if (!valid) return;

  confirmLoading.value = true;
  const data = await formApi.getValues();

  try {
    if (formData.value?.id) {
      await updateEnvMachineApi(formData.value.id, data);
    } else {
      await createEnvMachineApi({
        ...data,
        namespace: props.namespace,
      });
    }
    visible.value = false;
    emit('success');
    ElMessage.success(formData.value?.id ? '更新成功' : '创建成功');
  } catch (error) {
    ElMessage.error(formData.value?.id ? '更新失败' : '创建失败');
  } finally {
    confirmLoading.value = false;
  }
}

function open(data?: EnvMachine) {
  visible.value = true;
  if (data) {
    formData.value = data;
    // 先设置 schema，再设置值
    const mobile = isMobileDevice(data.device_type as any);
    formApi.setState({ schema: useFormSchema(mobile) });
    setTimeout(() => {
      formApi.setValues(formData.value!);
    }, 0);
  } else {
    formData.value = undefined;
    formApi.setState({ schema: useFormSchema(false) });
    formApi.resetForm();
  }
}

defineExpose({ open });
</script>

<template>
  <ZqDialog
    v-model="visible"
    :title="getTitle"
    :confirm-loading="confirmLoading"
    @confirm="onSubmit"
  >
    <Form class="mx-4" />
    <template #footer-left>
      <ElButton type="primary" @click="resetForm">
        重置
      </ElButton>
    </template>
  </ZqDialog>
</template>