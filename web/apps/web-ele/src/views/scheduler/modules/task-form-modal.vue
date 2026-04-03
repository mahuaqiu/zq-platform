<script lang="ts" setup>
import type { SchedulerJob } from '#/api/core/scheduler';

import { computed, ref, watch } from 'vue';

import { ZqDialog } from '#/components/zq-dialog';
import { $t } from '@vben/locales';

import { ElButton, ElMessage } from 'element-plus';

import { useVbenForm } from '#/adapter/form';
import { z } from '#/adapter/form';
import {
  createSchedulerJobApi,
  getSchedulerJobDetailApi,
  updateSchedulerJobApi,
} from '#/api/core/scheduler';
import { JOB_STATUS_OPTIONS, TRIGGER_TYPE_OPTIONS } from '../data';

const emit = defineEmits(['success']);

const formData = ref<SchedulerJob>();
const visible = ref(false);
const confirmLoading = ref(false);

const getTitle = computed(() => {
  return formData.value?.id ? '编辑任务' : '新增任务';
});

// 动态显示触发配置字段
const triggerType = ref('cron');

const [Form, formApi] = useVbenForm({
  layout: 'vertical',
  wrapperClass: 'grid-cols-2 gap-x-4',
  schema: [
    {
      component: 'Input',
      fieldName: 'name',
      label: '任务名称',
      formItemClass: 'col-span-2',
      rules: z
        .string()
        .min(1, '请输入任务名称')
        .max(100, '任务名称最多100个字符'),
      componentProps: {
        placeholder: '请输入任务名称',
      },
    },
    {
      component: 'Input',
      fieldName: 'code',
      label: '任务编码',
      formItemClass: 'col-span-2',
      rules: z
        .string()
        .min(1, '请输入任务编码')
        .max(50, '任务编码最多50个字符')
        .regex(/^[a-zA-Z0-9_-]+$/, '任务编码只能包含字母、数字、下划线和短横线'),
      componentProps: {
        placeholder: '请输入任务编码（唯一标识）',
      },
    },
    {
      component: 'Select',
      fieldName: 'trigger_type',
      label: '触发类型',
      formItemClass: 'col-span-2',
      rules: z.string().min(1, '请选择触发类型'),
      defaultValue: 'cron',
      componentProps: {
        options: TRIGGER_TYPE_OPTIONS,
        placeholder: '请选择触发类型',
      },
    },
    {
      component: 'Input',
      fieldName: 'cron_expression',
      label: 'Cron表达式',
      formItemClass: 'col-span-2',
      dependencies: {
        triggerFields: ['trigger_type'],
        if: (values) => values.trigger_type === 'cron',
        show: true,
      },
      rules: z.string().min(1, '请输入Cron表达式'),
      componentProps: {
        placeholder: '例如: 0 23 * * * (每天23:00执行)',
      },
      help: '格式: 秒 分 时 日 月 周，例如 "0 23 * * *" 表示每天23:00执行',
    },
    {
      component: 'InputNumber',
      fieldName: 'interval_seconds',
      label: '间隔秒数',
      formItemClass: 'col-span-2',
      dependencies: {
        triggerFields: ['trigger_type'],
        if: (values) => values.trigger_type === 'interval',
        show: true,
      },
      rules: z.number().min(1, '间隔秒数必须大于0'),
      componentProps: {
        placeholder: '请输入间隔秒数',
        min: 1,
        style: { width: '100%' },
      },
    },
    {
      component: 'DatePicker',
      fieldName: 'run_date',
      label: '执行时间',
      formItemClass: 'col-span-2',
      dependencies: {
        triggerFields: ['trigger_type'],
        if: (values) => values.trigger_type === 'date',
        show: true,
      },
      rules: z.string().min(1, '请选择执行时间'),
      componentProps: {
        type: 'datetime',
        placeholder: '请选择执行时间',
        format: 'YYYY-MM-DD HH:mm:ss',
        valueFormat: 'YYYY-MM-DD HH:mm:ss',
        style: { width: '100%' },
      },
    },
    {
      component: 'Input',
      fieldName: 'task_func',
      label: '任务函数路径',
      formItemClass: 'col-span-2',
      rules: z
        .string()
        .min(1, '请输入任务函数路径')
        .max(200, '任务函数路径最多200个字符'),
      componentProps: {
        placeholder: '例如: core.scheduler.tasks.cleanup_task',
      },
      help: 'Python函数的完整路径，模块名.函数名',
    },
    {
      component: 'Textarea',
      fieldName: 'task_kwargs',
      label: '任务参数（JSON）',
      formItemClass: 'col-span-2',
      componentProps: {
        placeholder: '{"days": 30}',
        rows: 3,
      },
      rules: z.string().optional().refine(
        (val) => {
          if (!val || val.trim() === '') return true;
          try {
            JSON.parse(val);
            return true;
          } catch {
            return false;
          }
        },
        { message: '任务参数必须是有效的JSON格式' },
      ),
    },
    {
      component: 'Input',
      fieldName: 'group',
      label: '任务分组',
      defaultValue: 'default',
      formItemClass: 'col-span-1',
      componentProps: {
        placeholder: 'default',
      },
    },
    {
      component: 'Select',
      fieldName: 'status',
      label: '任务状态',
      defaultValue: 1,
      formItemClass: 'col-span-1',
      componentProps: {
        options: JOB_STATUS_OPTIONS.map((opt) => ({
          label: opt.label,
          value: opt.value,
        })),
        placeholder: '请选择任务状态',
      },
    },
    {
      component: 'Input',
      fieldName: 'execute_host_ip',
      label: '执行主机IP',
      formItemClass: 'col-span-2',
      componentProps: {
        placeholder: '如 192.168.1.100，为空则任意机器可执行',
      },
      help: '指定任务执行的机器IP，需配合服务端 HOST_IP 配置使用',
    },
  ],
  showDefaultActions: false,
});

// 监听触发类型变化
watch(
  () => formApi.form?.values?.trigger_type,
  (newVal) => {
    if (newVal) {
      triggerType.value = newVal;
    }
  },
);

function resetForm() {
  formApi.resetForm();
  if (formData.value) {
    formApi.setValues(formData.value);
  }
}

async function onSubmit() {
  const { valid } = await formApi.validate();
  if (valid) {
    confirmLoading.value = true;
    try {
      const values = await formApi.getValues();

      // 处理触发配置：根据触发类型清理不需要的字段
      const submitData = { ...values };
      if (submitData.trigger_type === 'cron') {
        submitData.interval_seconds = undefined;
        submitData.run_date = undefined;
      } else if (submitData.trigger_type === 'interval') {
        submitData.cron_expression = undefined;
        submitData.run_date = undefined;
      } else if (submitData.trigger_type === 'date') {
        submitData.cron_expression = undefined;
        submitData.interval_seconds = undefined;
      }

      if (formData.value?.id) {
        // 编辑模式
        await updateSchedulerJobApi(formData.value.id, submitData);
        ElMessage.success('更新成功');
      } else {
        // 新增模式
        await createSchedulerJobApi(submitData);
        ElMessage.success('创建成功');
      }

      visible.value = false;
      emit('success');
    } catch (error: any) {
      ElMessage.error(error?.message || '操作失败');
    } finally {
      confirmLoading.value = false;
    }
  }
}

async function open(jobId?: string) {
  visible.value = true;
  formApi.resetForm();

  if (jobId) {
    // 编辑模式：获取任务详情
    try {
      const jobDetail = await getSchedulerJobDetailApi(jobId);
      formData.value = jobDetail;
      formApi.setValues(jobDetail);
      triggerType.value = jobDetail.trigger_type;
    } catch (error: any) {
      ElMessage.error(error?.message || '获取任务详情失败');
      visible.value = false;
    }
  } else {
    // 新增模式
    formData.value = undefined;
    triggerType.value = 'cron';
  }
}

defineExpose({
  open,
});
</script>

<template>
  <ZqDialog
    v-model="visible"
    :title="getTitle"
    width="700px"
    :confirm-loading="confirmLoading"
    @confirm="onSubmit"
  >
    <Form class="mx-4" />
    <template #footer-left>
      <ElButton type="primary" @click="resetForm">
        {{ $t('common.reset') }}
      </ElButton>
    </template>
  </ZqDialog>
</template>