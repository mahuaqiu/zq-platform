<script lang="ts" setup>
import type { UpgradeConfig, UpgradePreviewMachine, UpgradePreviewResponse, UpgradeQueueItem, BatchUpgradeParams } from '#/api/core/env-machine-upgrade';

import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElCheckbox,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPagination,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus';

import {
  getUpgradeConfigListApi,
  updateUpgradeConfigApi,
  getUpgradePreviewApi,
  batchUpgradeApi,
  getUpgradeQueueApi,
  removeUpgradeQueueApi,
} from '#/api/core/env-machine-upgrade';

import { DEVICE_TYPE_OPTIONS } from './types';

defineOptions({ name: 'EnvMachineUpgradePage' });

// 版本配置数据
const windowsConfig = ref<UpgradeConfig | null>(null);
const macConfig = ref<UpgradeConfig | null>(null);
const configLoading = ref(false);

// 批量升级筛选
const filterForm = ref({
  namespace: 'all',
  device_type: 'all',
});

// Namespace 选项
const NAMESPACE_OPTIONS = [
  { label: '全部', value: 'all' },
  { label: '集成验证 (meeting_gamma)', value: 'meeting_gamma' },
  { label: 'APP (meeting_app)', value: 'meeting_app' },
  { label: '音视频 (meeting_av)', value: 'meeting_av' },
  { label: '公共设备 (meeting_public)', value: 'meeting_public' },
];

// 设备类型选项（含全部）
const DEVICE_TYPE_FILTER_OPTIONS = [
  { label: '全部', value: 'all' },
  { label: 'Windows', value: 'windows' },
  { label: 'Mac', value: 'mac' },
];

// 预览数据
const previewData = ref<UpgradePreviewResponse | null>(null);
const previewLoading = ref(false);
const selectedMachineIds = ref<string[]>([]);

// 升级队列数据
const queueData = ref<{ items: UpgradeQueueItem[]; total: number }>({ items: [], total: 0 });
const queueLoading = ref(false);

// 确认弹窗
const confirmDialogVisible = ref(false);
const upgradeLoading = ref(false);

// 加载配置
async function loadConfigs() {
  configLoading.value = true;
  try {
    const configs = await getUpgradeConfigListApi();
    for (const config of configs) {
      if (config.device_type === 'windows') {
        windowsConfig.value = config;
      } else if (config.device_type === 'mac') {
        macConfig.value = config;
      }
    }
  } catch (error) {
    ElMessage.error('加载配置失败');
  } finally {
    configLoading.value = false;
  }
}

// 保存配置
async function saveConfig(config: UpgradeConfig | null, formData: { version: string; download_url: string; note: string }) {
  if (!config) return;
  try {
    await updateUpgradeConfigApi(config.id, {
      version: formData.version,
      download_url: formData.download_url,
      note: formData.note,
    });
    ElMessage.success('保存成功');
    await loadConfigs();
  } catch (error) {
    ElMessage.error('保存失败');
  }
}

// Windows 配置表单
const windowsForm = ref({
  version: '',
  download_url: '',
  note: '',
});

// Mac 配置表单
const macForm = ref({
  version: '',
  download_url: '',
  note: '',
});

// 加载预览
async function loadPreview() {
  previewLoading.value = true;
  try {
    const data = await getUpgradePreviewApi(
      filterForm.value.namespace === 'all' ? undefined : filterForm.value.namespace,
      filterForm.value.device_type === 'all' ? undefined : filterForm.value.device_type
    );
    previewData.value = data;
    selectedMachineIds.value = [];
  } catch (error) {
    ElMessage.error('加载预览失败');
  } finally {
    previewLoading.value = false;
  }
}

// 加载队列
async function loadQueue() {
  queueLoading.value = true;
  try {
    const data = await getUpgradeQueueApi();
    queueData.value = data;
  } catch (error) {
    ElMessage.error('加载队列失败');
  } finally {
    queueLoading.value = false;
  }
}

// 全选
function handleSelectAll(val: boolean) {
  if (val && previewData.value) {
    selectedMachineIds.value = previewData.value.machines
      .filter(m => m.upgrade_status === '待升级' || m.upgrade_status === '待队列')
      .map(m => m.id);
  } else {
    selectedMachineIds.value = [];
  }
}

// 打开确认弹窗
function openConfirmDialog() {
  if (selectedMachineIds.value.length === 0) {
    ElMessage.warning('请选择要升级的机器');
    return;
  }
  confirmDialogVisible.value = true;
}

// 执行批量升级
async function executeBatchUpgrade() {
  upgradeLoading.value = true;
  try {
    const params: BatchUpgradeParams = {
      machine_ids: selectedMachineIds.value,
    };
    const result = await batchUpgradeApi(params);

    if (result.failed_count > 0) {
      ElMessage.warning(`升级完成，但有 ${result.failed_count} 台失败`);
    } else {
      ElMessage.success(`升级成功：${result.upgraded_count} 台已升级，${result.waiting_count} 台待队列`);
    }

    confirmDialogVisible.value = false;
    await loadPreview();
    await loadQueue();
  } catch (error) {
    ElMessage.error('升级失败');
  } finally {
    upgradeLoading.value = false;
  }
}

// 移除队列项
async function handleRemoveQueue(item: UpgradeQueueItem) {
  ElMessageBox.confirm(`确定移除队列项 "${item.ip}" 吗？`, '确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await removeUpgradeQueueApi(item.id);
      ElMessage.success('移除成功');
      await loadQueue();
    } catch {
      ElMessage.error('移除失败');
    }
  });
}

// 获取状态标签类型
function getStatusTagType(status: string) {
  const typeMap: Record<string, string> = {
    '待升级': 'warning',
    '已最新': 'success',
    '待队列': '',
    '离线': 'danger',
    '升级中': 'info',
  };
  return typeMap[status] || '';
}

// 初始化
onMounted(async () => {
  await loadConfigs();
  // 同步表单数据
  if (windowsConfig.value) {
    windowsForm.value = {
      version: windowsConfig.value.version,
      download_url: windowsConfig.value.download_url,
      note: windowsConfig.value.note || '',
    };
  }
  if (macConfig.value) {
    macForm.value = {
      version: macConfig.value.version,
      download_url: macConfig.value.download_url,
      note: macConfig.value.note || '',
    };
  }
  await loadPreview();
  await loadQueue();
});
</script>

<template>
  <Page auto-content-height>
    <div class="upgrade-page">
      <!-- 版本配置区 -->
      <ElCard class="config-card" shadow="never">
        <template #header>
          <span class="card-title">版本配置</span>
        </template>
        <div class="config-row">
          <!-- Windows 配置 -->
          <div class="config-item">
            <ElTag type="primary" class="config-tag">Windows</ElTag>
            <ElForm label-width="80px" class="config-form">
              <ElFormItem label="目标版本">
                <ElInput v-model="windowsForm.version" placeholder="时间戳格式" />
              </ElFormItem>
              <ElFormItem label="下载地址">
                <ElInput v-model="windowsForm.download_url" placeholder="安装包下载地址" />
              </ElFormItem>
              <ElFormItem label="备注">
                <ElInput v-model="windowsForm.note" placeholder="版本说明" />
              </ElFormItem>
              <ElFormItem>
                <ElButton type="success" @click="saveConfig(windowsConfig, windowsForm)">保存配置</ElButton>
              </ElFormItem>
            </ElForm>
          </div>

          <!-- Mac 配置 -->
          <div class="config-item">
            <ElTag class="config-tag" color="#722ed1" style="color: #fff">Mac</ElTag>
            <ElForm label-width="80px" class="config-form">
              <ElFormItem label="目标版本">
                <ElInput v-model="macForm.version" placeholder="时间戳格式" />
              </ElFormItem>
              <ElFormItem label="下载地址">
                <ElInput v-model="macForm.download_url" placeholder="安装包下载地址" />
              </ElFormItem>
              <ElFormItem label="备注">
                <ElInput v-model="macForm.note" placeholder="版本说明" />
              </ElFormItem>
              <ElFormItem>
                <ElButton type="success" @click="saveConfig(macConfig, macForm)">保存配置</ElButton>
              </ElFormItem>
            </ElForm>
          </div>
        </div>
      </ElCard>

      <!-- 批量升级区 -->
      <ElCard class="upgrade-card" shadow="never">
        <template #header>
          <span class="card-title">批量升级</span>
        </template>

        <!-- 筛选条件 -->
        <div class="filter-row">
          <ElForm inline>
            <ElFormItem label="设备类别">
              <ElSelect v-model="filterForm.namespace" style="width: 180px">
                <ElOption v-for="opt in NAMESPACE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
              </ElSelect>
            </ElFormItem>
            <ElFormItem label="设备类型">
              <ElSelect v-model="filterForm.device_type" style="width: 120px">
                <ElOption v-for="opt in DEVICE_TYPE_FILTER_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
              </ElSelect>
            </ElFormItem>
            <ElFormItem>
              <ElButton type="primary" @click="loadPreview">查询预览</ElButton>
              <ElButton @click="filterForm = { namespace: 'all', device_type: 'all' }; loadPreview()">重置</ElButton>
            </ElFormItem>
          </ElForm>
        </div>

        <!-- 统计信息 -->
        <div class="stats-row" v-if="previewData">
          <ElTag type="primary">可升级: {{ previewData.upgradable_count }}台</ElTag>
          <ElTag type="warning">使用中(待队列): {{ previewData.waiting_count }}台</ElTag>
          <ElTag type="success">已最新: {{ previewData.latest_count }}台</ElTag>
          <ElTag type="danger">离线: {{ previewData.offline_count }}台</ElTag>
        </div>

        <!-- 机器列表 -->
        <ElTable :data="previewData?.machines || []" v-loading="previewLoading" border class="preview-table">
          <ElTableColumn width="80">
            <template #header>
              <div class="select-header">
                <ElCheckbox
                  :model-value="selectedMachineIds.length > 0"
                  @change="handleSelectAll"
                />
                <span class="select-label">全选</span>
              </div>
            </template>
            <template #default="{ row }">
              <ElCheckbox
                v-if="row.upgrade_status === '待升级' || row.upgrade_status === '待队列'"
                :model-value="selectedMachineIds.includes(row.id)"
                @change="(val: boolean) => val ? selectedMachineIds.push(row.id) : selectedMachineIds = selectedMachineIds.filter(id => id !== row.id)"
              />
            </template>
          </ElTableColumn>
          <ElTableColumn prop="ip" label="IP地址" min-width="140">
            <template #default="{ row }">
              <code class="ip-code">{{ row.ip }}</code>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="device_type" label="设备类型" min-width="100">
            <template #default="{ row }">
              {{ row.device_type === 'windows' ? 'Windows' : 'Mac' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="version" label="当前版本" min-width="120" />
          <ElTableColumn prop="status" label="状态" min-width="80">
            <template #default="{ row }">
              <span :class="`status-${row.status}`">{{ row.status === 'online' ? '在线' : row.status === 'using' ? '使用中' : row.status === 'upgrading' ? '升级中' : '离线' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="upgrade_status" label="升级状态" min-width="100">
            <template #default="{ row }">
              <ElTag :type="getStatusTagType(row.upgrade_status)" size="small">{{ row.upgrade_status }}</ElTag>
            </template>
          </ElTableColumn>
        </ElTable>

        <!-- 操作按钮 -->
        <div class="action-row">
          <ElButton type="primary" @click="openConfirmDialog">
            批量升级选中的机器 ({{ selectedMachineIds.length }}台)
          </ElButton>
        </div>
      </ElCard>

      <!-- 升级队列区 -->
      <ElCard class="queue-card" shadow="never">
        <template #header>
          <div class="queue-header">
            <span class="card-title">升级队列</span>
            <ElTag type="info">等待: {{ queueData.total }}台</ElTag>
          </div>
        </template>

        <ElTable :data="queueData.items" v-loading="queueLoading" border>
          <ElTableColumn prop="ip" label="IP地址" min-width="140">
            <template #default="{ row }">
              <code class="ip-code">{{ row.ip }}</code>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="device_type" label="设备类型" min-width="100">
            <template #default="{ row }">
              {{ row.device_type === 'windows' ? 'Windows' : 'Mac' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="target_version" label="目标版本" min-width="120" />
          <ElTableColumn prop="created_at" label="入队时间" min-width="160" />
          <ElTableColumn prop="status" label="状态" min-width="80">
            <template #default="{ row }">
              <ElTag size="small">{{ row.status }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" min-width="80">
            <template #default="{ row }">
              <a class="remove-link" @click="handleRemoveQueue(row)">移除队列</a>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElCard>

      <!-- 确认弹窗 -->
      <ElDialog v-model="confirmDialogVisible" title="确认批量升级" width="400px">
        <p>即将升级选中的机器：</p>
        <p class="confirm-info">已选中 {{ selectedMachineIds.length }} 台机器</p>
        <p class="confirm-warning">升级期间机器将不可用，请确认操作。</p>
        <template #footer>
          <ElButton @click="confirmDialogVisible = false">取消</ElButton>
          <ElButton type="primary" :loading="upgradeLoading" @click="executeBatchUpgrade">确认升级</ElButton>
        </template>
      </ElDialog>
    </div>
  </Page>
</template>

<style scoped>
.upgrade-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-title {
  font-weight: 500;
}

.config-card {
  margin-bottom: 0;
}

.config-row {
  display: flex;
  gap: 24px;
}

.config-item {
  flex: 1;
  background: #fafafa;
  padding: 16px;
  border-radius: 6px;
  border: 1px solid #e8e8e8;
}

.config-tag {
  margin-bottom: 12px;
}

.config-form {
  margin-top: 8px;
}

.filter-row {
  padding: 12px;
  background: #fafafa;
  border-radius: 4px;
  margin-bottom: 12px;
}

.stats-row {
  display: flex;
  gap: 12px;
  padding: 8px 12px;
  background: #e6f7ff;
  border-radius: 4px;
  border: 1px solid #91d5ff;
  margin-bottom: 12px;
}

.preview-table {
  margin-bottom: 12px;
}

.select-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.select-label {
  font-size: 12px;
  color: #1890ff;
}

.ip-code {
  background: #f5f5f5;
  padding: 2px 4px;
  border-radius: 2px;
  font-family: monospace;
}

.status-online {
  color: #52c41a;
}

.status-using {
  color: #e6a23c;
}

.status-upgrading {
  color: #722ed1;
}

.status-offline {
  color: #ff4d4f;
}

.action-row {
  display: flex;
  gap: 12px;
}

.queue-card {
  margin-bottom: 0;
}

.queue-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.remove-link {
  color: #ff4d4f;
  cursor: pointer;
}

.confirm-info {
  font-size: 14px;
  color: #1890ff;
}

.confirm-warning {
  font-size: 13px;
  color: #faad14;
}
</style>