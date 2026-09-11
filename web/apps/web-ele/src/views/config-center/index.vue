<script lang="ts" setup>
import type { ConfigCenterItem } from '#/api/core/config-center';

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { Edit, Eye, Plus, Trash2 } from '@vben/icons';

import {
  ElButton,
  ElDialog,
  ElMessage,
  ElMessageBox,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus';

import {
  batchDeleteConfigItemApi,
  deleteConfigItemApi,
  getConfigItemListApi,
  parseConfigValue,
} from '#/api/core/config-center';
import { useZqTable } from '#/components/zq-table';

import { useSearchFormSchema, useZqTableColumns } from './data';
import Form from './modules/form.vue';

defineOptions({ name: 'SystemConfigCenter' });

const formRef = ref<InstanceType<typeof Form>>();
const selectedRows = ref<ConfigCenterItem[]>([]);

// 查看弹窗状态
const viewVisible = ref(false);
const viewKey = ref('');
const viewRemark = ref('');
const viewPairs = ref<Array<{ key: string; value: string }>>([]);

function onView(row: ConfigCenterItem) {
  viewKey.value = row.key;
  viewRemark.value = row.remark ?? '';
  viewPairs.value = parseConfigValue(row.value);
  viewVisible.value = true;
}

function onEdit(row: ConfigCenterItem) {
  formRef.value?.open(row);
}

function onCreate() {
  formRef.value?.open();
}

function onDelete(row: ConfigCenterItem) {
  ElMessageBox.confirm(`确定删除配置「${row.key}」吗？`, '删除确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(async () => {
      await deleteConfigItemApi(row.id);
      ElMessage.success('删除成功');
      refreshGrid();
    })
    .catch(() => {
      // 用户取消或请求失败（请求层已统一弹错）
    });
}

function onBatchDelete() {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先勾选要删除的配置');
    return;
  }
  const keys = selectedRows.value.map((row) => row.key).join('、');
  ElMessageBox.confirm(
    `确定删除选中的 ${selectedRows.value.length} 个配置（${keys}）吗？`,
    '批量删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
  )
    .then(async () => {
      const ids = selectedRows.value.map((row) => row.id);
      await batchDeleteConfigItemApi({ ids });
      ElMessage.success('批量删除成功');
      selectedRows.value = [];
      refreshGrid();
    })
    .catch(() => {
      // 用户取消或请求失败（请求层已统一弹错）
    });
}

function handleSelectionChange(items: Record<string, any>[]) {
  selectedRows.value = items as ConfigCenterItem[];
}

const fetchItemList = async (params: any) => {
  const res = await getConfigItemListApi({
    page: params.page.currentPage,
    pageSize: params.page.pageSize,
    key: params.form?.key,
    remark: params.form?.remark,
  });
  return { items: res.items, total: res.total };
};

const [Grid, gridApi] = useZqTable({
  gridOptions: {
    columns: useZqTableColumns(),
    border: true,
    stripe: true,
    showSelection: true,
    showIndex: true,
    proxyConfig: {
      autoLoad: true,
      ajax: {
        query: fetchItemList,
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
    schema: useSearchFormSchema(),
    showCollapseButton: false,
    submitOnChange: false,
  },
});

function refreshGrid() {
  gridApi.reload();
}
</script>

<template>
  <Page auto-content-height>
    <Form ref="formRef" @success="refreshGrid" />

    <Grid @selection-change="handleSelectionChange">
      <template #toolbar-actions>
        <ElButton type="primary" :icon="Plus" @click="onCreate">
          新增配置
        </ElButton>
        <ElButton type="danger" plain :icon="Trash2" @click="onBatchDelete">
          批量删除{{ selectedRows.length > 0 ? `(${selectedRows.length})` : '' }}
        </ElButton>
      </template>

      <!-- 配置键（等宽字体） -->
      <template #cell-key="{ row }">
        <span class="font-mono">{{ row.key }}</span>
      </template>

      <!-- 配置值：键值对标签，每对一行，超过约 200px 内部滚动 -->
      <template #cell-value="{ row }">
        <div v-if="parseConfigValue(row.value).length > 0">
          <div
            class="max-h-[200px] overflow-y-auto rounded border border-solid border-[#ebeef5] bg-[#fafafa] p-2"
          >
            <div
              v-for="(pair, index) in parseConfigValue(row.value)"
              :key="index"
              class="mb-1 last:mb-0"
            >
              <ElTag size="small">{{ pair.key }} → {{ pair.value }}</ElTag>
            </div>
          </div>
          <div class="mt-0.5 text-xs text-[#909399]">
            共 {{ parseConfigValue(row.value).length }} 对
          </div>
        </div>
        <span v-else>-</span>
      </template>

      <template #cell-actions="{ row }">
        <ElButton link type="primary" :icon="Edit" @click="onEdit(row)">
          编辑
        </ElButton>
        <ElButton link type="primary" :icon="Eye" @click="onView(row)">
          查看
        </ElButton>
        <ElButton link type="danger" :icon="Trash2" @click="onDelete(row)">
          删除
        </ElButton>
      </template>
    </Grid>

    <!-- 查看弹窗：只读键值对列表 -->
    <ElDialog
      v-model="viewVisible"
      :title="`查看配置 · ${viewKey}`"
      width="560px"
    >
      <ElTable :data="viewPairs" max-height="420" size="small" border>
        <ElTableColumn prop="key" label="键" min-width="40%" />
        <ElTableColumn prop="value" label="值" min-width="60%" />
      </ElTable>
      <div class="mt-1 text-xs text-[#909399]">
        共 {{ viewPairs.length }} 对 · 备注：{{ viewRemark || '-' }}
      </div>
    </ElDialog>
  </Page>
</template>
