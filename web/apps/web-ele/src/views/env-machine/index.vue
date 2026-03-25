<script lang="ts" setup>
import type { EnvMachine } from '#/api/core/env-machine';

import { computed, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import { Page } from '@vben/common-ui';
import { Plus } from '@vben/icons';

import { ElButton, ElMessage, ElMessageBox } from 'element-plus';

import { deleteEnvMachineApi, getEnvMachineListApi } from '#/api/core/env-machine';
import { useZqTable } from '#/components/zq-table';

import {
  useManualColumns,
  useManualSearchFormSchema,
  useStandardColumns,
  useStandardSearchFormSchema,
} from './data';
import { NAMESPACE_MAP } from './types';
import MachineFormModal from './modules/machine-form-modal.vue';

defineOptions({ name: 'EnvMachinePage' });

const route = useRoute();

// 表单弹窗引用
const formModalRef = ref<InstanceType<typeof MachineFormModal>>();

// 判断是否为手工使用页面
const isManual = computed(() => {
  const lastSegment = route.path.split('/').filter(Boolean).pop();
  return lastSegment === 'manual';
});

// 从路由获取 namespace
const namespaceKey = computed(() => {
  const lastSegment = route.path.split('/').filter(Boolean).pop();
  return lastSegment || '';
});

// 获取映射后的 namespace
const namespace = computed(() => {
  return NAMESPACE_MAP[namespaceKey.value] || '';
});

// 处理操作列点击
function onActionClick({ row, code }: { row: EnvMachine; code: string }) {
  switch (code) {
    case 'edit': {
      onEdit(row);
      break;
    }
    case 'delete': {
      onDelete(row);
      break;
    }
    case 'use': {
      onUse(row);
      break;
    }
    case 'keep': {
      onKeep(row);
      break;
    }
  }
}

/**
 * 编辑设备
 */
function onEdit(row: EnvMachine) {
  formModalRef.value?.open(row);
}

/**
 * 新增设备
 */
function onCreate() {
  formModalRef.value?.open();
}

/**
 * 删除设备
 */
function onDelete(row: EnvMachine) {
  const displayName = row.asset_number || row.ip || row.id;
  ElMessageBox.confirm(`确定要删除设备 "${displayName}" 吗？`, '删除确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(async () => {
      try {
        await deleteEnvMachineApi(row.id);
        ElMessage.success('删除成功');
        gridApi.reload();
      } catch {
        ElMessage.error('删除失败');
      }
    })
    .catch(() => {
      // 用户取消
    });
}

/**
 * 使用设备（手工使用页面）
 */
function onUse(row: EnvMachine) {
  // TODO: 实现使用设备功能
  console.log('使用设备:', row);
  ElMessage.info(`使用设备: ${row.ip}`);
}

/**
 * 保持设备（手工使用页面）
 */
function onKeep(row: EnvMachine) {
  // TODO: 实现保持设备功能
  console.log('保持设备:', row);
  ElMessage.info(`保持设备: ${row.ip}`);
}

// 获取表格列配置
const columns = computed(() => {
  return isManual.value
    ? useManualColumns(onActionClick)
    : useStandardColumns(onActionClick);
});

// 获取搜索表单配置
const searchFormSchema = computed(() => {
  return isManual.value
    ? useManualSearchFormSchema()
    : useStandardSearchFormSchema();
});

// 数据查询函数
async function fetchData(params: {
  form: Record<string, any>;
  page: { currentPage: number; pageSize: number };
}) {
  if (!namespace.value) {
    return { items: [], total: 0 };
  }

  const res = await getEnvMachineListApi({
    namespace: namespace.value,
    device_type: params.form.device_type,
    ip: params.form.ip,
    asset_number: params.form.asset_number,
    mark: params.form.mark,
    available: params.form.available,
    status: params.form.status,
    page: params.page.currentPage,
    page_size: params.page.pageSize,
  });

  return {
    items: res.items,
    total: res.total,
  };
}

// 使用 ZqTable
const [Grid, gridApi] = useZqTable({
  gridOptions: {
    columns: columns.value,
    border: true,
    stripe: true,
    showOverflow: true,
    proxyConfig: {
      autoLoad: true,
      ajax: {
        query: fetchData,
      },
    },
    pagerConfig: {
      enabled: true,
      pageSize: 20,
    },
    toolbarConfig: {
      search: true,
      refresh: true,
      zoom: true,
      custom: true,
    },
  },
  formOptions: {
    schema: searchFormSchema.value,
    showCollapseButton: true,
    submitOnChange: false,
  },
});

// 监听路由变化，重新加载表格
watch(namespaceKey, () => {
  gridApi.reload();
});

// 监听列配置变化
watch(columns, (newColumns) => {
  gridApi.setState({
    gridOptions: {
      columns: newColumns,
    },
  });
});

// 监听搜索表单配置变化
watch(searchFormSchema, (newSchema) => {
  gridApi.setState({
    formOptions: {
      schema: newSchema,
    },
  });
});
</script>

<template>
  <Page auto-content-height>
    <!-- 新增/编辑表单弹窗 -->
    <MachineFormModal
      ref="formModalRef"
      :namespace="namespace"
      @success="gridApi.reload()"
    />

    <!-- 数据表格 -->
    <Grid>
      <!-- 工具栏操作按钮 -->
      <template #toolbar-actions>
        <ElButton
          v-if="isManual"
          type="primary"
          :icon="Plus"
          @click="onCreate"
        >
          新增设备
        </ElButton>
      </template>
    </Grid>
  </Page>
</template>