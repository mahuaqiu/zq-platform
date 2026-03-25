import type { VxeTableGridOptions } from '@vben/plugins/vxe-table';

import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn } from '#/adapter/vxe-table';
import type { EnvMachine } from '#/api/core/env-machine';

import { z } from '#/adapter/form';

import {
  AVAILABLE_OPTIONS,
  DEVICE_TYPE_OPTIONS,
  STATUS_OPTIONS,
} from './types';

/**
 * 获取 Namespace 选项
 */
export function getNamespaceOptions() {
  return [
    { label: 'Gamma', value: 'gamma' },
    { label: 'App', value: 'app' },
    { label: 'AV', value: 'av' },
    { label: 'Public', value: 'public' },
    { label: 'Manual', value: 'manual' },
  ];
}

/**
 * 标准页面搜索表单
 */
export function useStandardSearchFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Select',
      fieldName: 'device_type',
      label: '设备类型',
      componentProps: {
        placeholder: '请选择设备类型',
        options: DEVICE_TYPE_OPTIONS,
        clearable: true,
      },
    },
    {
      component: 'Input',
      fieldName: 'ip',
      label: 'IP地址',
      componentProps: {
        placeholder: '请输入IP地址',
      },
    },
    {
      component: 'Input',
      fieldName: 'asset_number',
      label: '资产编号',
      componentProps: {
        placeholder: '请输入资产编号',
      },
    },
    {
      component: 'Input',
      fieldName: 'mark',
      label: '标签',
      componentProps: {
        placeholder: '请输入标签',
      },
    },
    {
      component: 'Select',
      fieldName: 'available',
      label: '是否启用',
      componentProps: {
        placeholder: '请选择',
        options: AVAILABLE_OPTIONS,
        clearable: true,
      },
    },
  ];
}

/**
 * 手工使用页面搜索表单
 */
export function useManualSearchFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Select',
      fieldName: 'device_type',
      label: '设备类型',
      componentProps: {
        placeholder: '请选择设备类型',
        options: DEVICE_TYPE_OPTIONS,
        clearable: true,
      },
    },
    {
      component: 'Input',
      fieldName: 'ip',
      label: 'IP地址',
      componentProps: {
        placeholder: '请输入IP地址',
      },
    },
    {
      component: 'Input',
      fieldName: 'mark',
      label: '标签',
      componentProps: {
        placeholder: '请输入标签',
      },
    },
    {
      component: 'Select',
      fieldName: 'status',
      label: '状态',
      componentProps: {
        placeholder: '请选择状态',
        options: STATUS_OPTIONS.map((opt) => ({
          label: opt.label,
          value: opt.value,
        })),
        clearable: true,
      },
    },
  ];
}

/**
 * 标准页面表格列
 */
export function useStandardColumns(
  onActionClick?: OnActionClickFn<EnvMachine>,
): VxeTableGridOptions<EnvMachine>['columns'] {
  return [
    {
      type: 'checkbox',
      width: 60,
      align: 'center',
      fixed: 'left',
    },
    {
      field: 'namespace',
      title: '分类',
      minWidth: 100,
      cellRender: {
        name: 'CellDict',
        props: {
          dict: getNamespaceOptions(),
        },
      },
    },
    {
      field: 'device_type',
      title: '设备类型',
      minWidth: 100,
      cellRender: {
        name: 'CellTag',
        options: DEVICE_TYPE_OPTIONS.map((opt) => ({
          ...opt,
          type: 'info',
        })),
      },
    },
    {
      field: 'asset_number',
      title: '资产编号',
      minWidth: 120,
    },
    {
      field: 'ip',
      title: 'IP地址',
      minWidth: 140,
    },
    {
      field: 'device_sn',
      title: '设备SN',
      minWidth: 140,
      visible: false,
    },
    {
      field: 'port',
      title: '端口',
      minWidth: 80,
      align: 'center',
    },
    {
      field: 'mark',
      title: '标签',
      minWidth: 120,
      showOverflow: 'tooltip',
    },
    {
      field: 'status',
      title: '状态',
      minWidth: 100,
      align: 'center',
      cellRender: {
        name: 'CellTag',
        options: STATUS_OPTIONS,
      },
    },
    {
      field: 'available',
      title: '是否启用',
      minWidth: 100,
      align: 'center',
      cellRender: {
        name: 'CellTag',
        options: AVAILABLE_OPTIONS.map((opt) => ({
          label: opt.label,
          value: opt.value,
          type: opt.value ? 'success' : 'danger',
        })),
      },
    },
    {
      field: 'note',
      title: '备注',
      minWidth: 150,
      showOverflow: 'tooltip',
      visible: false,
    },
    {
      field: 'sync_time',
      title: '同步时间',
      minWidth: 180,
      cellRender: {
        name: 'CellDatetime',
      },
    },
    {
      field: 'version',
      title: '版本',
      minWidth: 100,
      visible: false,
    },
    {
      field: 'sys_create_datetime',
      title: '创建时间',
      minWidth: 180,
      cellRender: {
        name: 'CellDatetime',
      },
    },
    {
      align: 'right',
      cellRender: {
        attrs: {
          nameField: 'asset_number',
          nameTitle: '资产编号',
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: ['edit', 'delete'],
      },
      field: 'operation',
      fixed: 'right',
      headerAlign: 'center',
      showOverflow: false,
      title: '操作',
      minWidth: 150,
    },
  ];
}

/**
 * 手工使用页面表格列
 */
export function useManualColumns(
  onActionClick?: OnActionClickFn<EnvMachine>,
): VxeTableGridOptions<EnvMachine>['columns'] {
  return [
    {
      type: 'checkbox',
      width: 60,
      align: 'center',
      fixed: 'left',
    },
    {
      field: 'device_type',
      title: '设备类型',
      minWidth: 100,
      cellRender: {
        name: 'CellTag',
        options: DEVICE_TYPE_OPTIONS.map((opt) => ({
          ...opt,
          type: 'info',
        })),
      },
    },
    {
      field: 'ip',
      title: 'IP地址',
      minWidth: 140,
    },
    {
      field: 'device_sn',
      title: '设备SN',
      minWidth: 140,
    },
    {
      field: 'port',
      title: '端口',
      minWidth: 80,
      align: 'center',
    },
    {
      field: 'mark',
      title: '标签',
      minWidth: 120,
      showOverflow: 'tooltip',
    },
    {
      field: 'status',
      title: '状态',
      minWidth: 100,
      align: 'center',
      cellRender: {
        name: 'CellTag',
        options: STATUS_OPTIONS,
      },
    },
    {
      field: 'available',
      title: '是否启用',
      minWidth: 100,
      align: 'center',
      cellRender: {
        name: 'CellTag',
        options: AVAILABLE_OPTIONS.map((opt) => ({
          label: opt.label,
          value: opt.value,
          type: opt.value ? 'success' : 'danger',
        })),
      },
    },
    {
      field: 'note',
      title: '备注',
      minWidth: 150,
      showOverflow: 'tooltip',
    },
    {
      align: 'right',
      cellRender: {
        attrs: {
          nameField: 'ip',
          nameTitle: 'IP地址',
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'use',
            text: '使用',
            icon: 'ep:video-play',
          },
          {
            code: 'keep',
            text: '保持',
            icon: 'ep:timer',
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      headerAlign: 'center',
      showOverflow: false,
      title: '操作',
      minWidth: 150,
    },
  ];
}

/**
 * 新增/编辑表单 Schema
 * @param isMobile 是否为移动端设备
 */
export function useFormSchema(isMobile: boolean = false): VbenFormSchema[] {
  const baseSchema: VbenFormSchema[] = [
    {
      component: 'Select',
      fieldName: 'namespace',
      label: '机器分类',
      rules: z.string().min(1, '请选择机器分类'),
      componentProps: {
        placeholder: '请选择机器分类',
        options: getNamespaceOptions(),
      },
    },
    {
      component: 'Select',
      fieldName: 'device_type',
      label: '设备类型',
      rules: z.string().min(1, '请选择设备类型'),
      componentProps: {
        placeholder: '请选择设备类型',
        options: DEVICE_TYPE_OPTIONS,
      },
    },
    {
      component: 'Input',
      fieldName: 'asset_number',
      label: '资产编号',
      rules: z
        .string()
        .min(1, '请输入资产编号')
        .max(100, '资产编号最长100个字符'),
      componentProps: {
        placeholder: '请输入资产编号',
      },
    },
  ];

  // 根据设备类型显示不同字段
  if (isMobile) {
    baseSchema.push({
      component: 'Input',
      fieldName: 'device_sn',
      label: '设备SN',
      rules: z.string().min(1, '请输入设备SN'),
      componentProps: {
        placeholder: '请输入设备SN',
      },
    });
  } else {
    baseSchema.push({
      component: 'Input',
      fieldName: 'ip',
      label: 'IP地址',
      rules: z
        .string()
        .min(1, '请输入IP地址')
        .regex(
          /^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$/,
          '请输入有效的IP地址',
        ),
      componentProps: {
        placeholder: '请输入IP地址',
      },
    });
  }

  baseSchema.push({
    component: 'Input',
    fieldName: 'mark',
    label: '标签',
    componentProps: {
      placeholder: '请输入标签，多个标签用逗号分隔',
    },
  });

  baseSchema.push({
    component: 'Textarea',
    fieldName: 'note',
    label: '备注',
    componentProps: {
      placeholder: '请输入备注',
      rows: 3,
    },
  });

  return baseSchema;
}