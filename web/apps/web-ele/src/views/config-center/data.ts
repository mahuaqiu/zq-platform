import type { Column } from 'element-plus';

import type { VbenFormSchema } from '#/adapter/form';

/**
 * 搜索表单字段配置
 */
export function useSearchFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      fieldName: 'key',
      label: '配置键',
      componentProps: { placeholder: '请输入配置键', clearable: true },
    },
    {
      component: 'Input',
      fieldName: 'remark',
      label: '备注',
      componentProps: { placeholder: '请输入备注关键字', clearable: true },
    },
  ];
}

/**
 * 表格列配置
 */
export function useZqTableColumns(): Column[] {
  return [
    {
      key: 'key',
      dataKey: 'key',
      title: '配置键',
      width: 150,
      slots: { default: 'cell-key' },
    },
    {
      key: 'value',
      title: '配置值（键值对）',
      width: 380,
      slots: { default: 'cell-value' },
    },
    {
      key: 'remark',
      dataKey: 'remark',
      title: '备注',
      width: 220,
    },
    {
      key: 'sys_update_datetime',
      dataKey: 'sys_update_datetime',
      title: '更新时间',
      width: 170,
    },
    {
      key: 'actions',
      title: '操作',
      width: 200,
      fixed: true,
      align: 'center' as const,
      slots: { default: 'cell-actions' },
    },
  ];
}
