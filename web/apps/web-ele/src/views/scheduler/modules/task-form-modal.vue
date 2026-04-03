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
  schema: [
    {
      component: 'Input',
      fieldName: 'name',
      label: '任务名称',
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
      rules: z
        .string()
        .min(1, '请输入任务函数路径')
        .max(200, '任务函数路径最多200个字符'),
      componentProps: {
        placeholder: '例如: scheduler.tasks.cleanup_task',
      },
      help: 'Python函数的完整路径，模块名.函数名',
    },
    {
      component: 'Textarea',
      fieldName: 'task_args',
      label: '任务参数(位置参数)',
      componentProps: {
        placeholder: 'JSON数组格式，例如: ["arg1", "arg2"]',
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
        { message: '任务参数必须是有效的JSON数组格式' },
      ),
    },
    {
      component: 'Textarea',
      fieldName: 'task_kwargs',
      label: '任务参数(关键字参数)',
      componentProps: {
        placeholder: 'JSON对象格式，例如: {"key": "value"}',
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
        { message: '任务参数必须是有效的JSON对象格式' },
      ),
    },
    {
      component: 'Input',
      fieldName: 'group',
      label: '任务分组',
      defaultValue: 'default',
      componentProps: {
        placeholder: '默认分组: default',
      },
    },
    {
      component: 'Select',
      fieldName: 'status',
      label: '任务状态',
      defaultValue: 1,
      componentProps: {
        options: JOB_STATUS_OPTIONS.map((opt) => ({
          label: opt.label,
          value: opt.value,
        })),
        placeholder: '请选择任务状态',
      },
    },
    {
      component: 'InputNumber',
      fieldName: 'priority',
      label: '优先级',
      defaultValue: 5,
      componentProps: {
        min: 1,
        max: 10,
        placeholder: '优先级(1-10，数值越大优先级越高)',
        style: { width: '100%' },
      },
    },
    {
      component: 'InputNumber',
      fieldName: 'max_instances',
      label: '最大实例数',
      defaultValue: 1,
      componentProps: {
        min: 1,
        max: 10,
        placeholder: '同时运行的最大实例数',
        style: { width: '100%' },
      },
    },
    {
      component: 'InputNumber',
      fieldName: 'max_retries',
      label: '最大重试次数',
      defaultValue: 0,
      componentProps: {
        min: 0,
        max: 10,
        placeholder: '任务失败后的最大重试次数',
        style: { width: '100%' },
      },
    },
    {
      component: 'InputNumber',
      fieldName: 'timeout',
      label: '超时时间(秒)',
      componentProps: {
        min: 0,
        placeholder: '任务执行超时时间(秒)，0表示不限制',
        style: { width: '100%' },
      },
    },
    {
      component: 'Switch',
      fieldName: 'coalesce',
      label: '合并执行',
      defaultValue: false,
      help: '如果任务错过了执行时间，是否只执行一次',
      componentProps: {
        activeText: '是',
        inactiveText: '否',
      },
    },
    {
      component: 'Switch',
      fieldName: 'allow_concurrent',
      label: '允许并发',
      defaultValue: false,
      help: '是否允许同一任务的多个实例并发执行',
      componentProps: {
        activeText: '是',
        inactiveText: '否',
      },
    },
    {
      component: 'Textarea',
      fieldName: 'remark',
      label: '备注',
      componentProps: {
        placeholder: '请输入备注信息',
        rows: 3,
        maxlength: 500,
        showWordLimit: true,
      },
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