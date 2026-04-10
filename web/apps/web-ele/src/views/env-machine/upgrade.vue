<script lang="ts" setup>
import type { UpgradeConfig, UpgradePreviewResponse, UpgradeQueueItem, BatchUpgradeParams } from '#/api/core/env-machine-upgrade';

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElCheckbox,
  ElDialog,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElSelect,
  ElTable,
  ElTableColumn,
} from 'element-plus';

import {
  getUpgradeConfigListApi,
  updateUpgradeConfigApi,
  getUpgradePreviewApi,
  batchUpgradeApi,
  getUpgradeQueueApi,
  removeUpgradeQueueApi,
} from '#/api/core/env-machine-upgrade';

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

// 可选机器列表（待升级 + 待队列）
const selectableMachines = computed(() => {
  if (!previewData.value) return [];
  return previewData.value.machines.filter(m =>
    m.upgrade_status === '待升级' || m.upgrade_status === '待队列' ||
    m.upgrade_status === 'upgradable' || m.upgrade_status === 'waiting'
  );
});

// 全选状态计算
const isAllSelected = computed(() => {
  if (selectableMachines.value.length === 0) return false;
  return selectedMachineIds.value.length === selectableMachines.value.length;
});

// 半选状态
const isIndeterminate = computed(() => {
  const selectedLen = selectedMachineIds.value.length;
  const selectableLen = selectableMachines.value.length;
  return selectedLen > 0 && selectedLen < selectableLen;
});

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

// 全选切换
function handleSelectAllChange(val: boolean) {
  if (val) {
    selectedMachineIds.value = selectableMachines.value.map(m => m.id);
  } else {
    selectedMachineIds.value = [];
  }
}

// 单选切换
function handleCheckboxChange(machineId: string, checked: boolean) {
  if (checked) {
    if (!selectedMachineIds.value.includes(machineId)) {
      selectedMachineIds.value.push(machineId);
    }
  } else {
    selectedMachineIds.value = selectedMachineIds.value.filter(id => id !== machineId);
  }
}

// 判断是否可选（待升级或待队列）
function isSelectable(upgradeStatus: string): boolean {
  return upgradeStatus === '待升级' || upgradeStatus === '待队列' ||
         upgradeStatus === 'upgradable' || upgradeStatus === 'waiting';
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

// 获取升级状态标签样式
function getUpgradeStatusStyle(status: string): { bg: string; color: string } {
  const styleMap: Record<string, { bg: string; color: string }> = {
    '待升级': { bg: '#fff7e6', color: '#faad14' },
    '已最新': { bg: '#f6ffed', color: '#52c41a' },
    '待队列': { bg: '#f9f0ff', color: '#722ed1' },
    '离线': { bg: '#fff1f0', color: '#ff4d4f' },
    '升级中': { bg: '#f9f0ff', color: '#722ed1' },
    'upgradable': { bg: '#fff7e6', color: '#faad14' },
    'latest': { bg: '#f6ffed', color: '#52c41a' },
    'waiting': { bg: '#f9f0ff', color: '#722ed1' },
    'offline': { bg: '#fff1f0', color: '#ff4d4f' },
    'upgrading': { bg: '#f9f0ff', color: '#722ed1' },
  };
  return styleMap[status] || { bg: '#f5f5f5', color: '#666' };
}

// 获取状态文本
function getStatusText(status: string): string {
  const textMap: Record<string, string> = {
    online: '在线',
    using: '使用中',
    upgrading: '升级中',
    offline: '离线',
  };
  return textMap[status] || status;
}

// 获取升级状态文本
function getUpgradeStatusText(status: string): string {
  const textMap: Record<string, string> = {
    'upgradable': '待升级',
    'latest': '已最新',
    'waiting': '待队列',
    'offline': '离线',
    'upgrading': '升级中',
  };
  return textMap[status] || status;
}

// 重置筛选
function handleReset() {
  filterForm.value = { namespace: 'all', device_type: 'all' };
  loadPreview();
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
      <div class="config-card">
        <div class="card-header">
          <span class="card-title">📦 版本配置</span>
        </div>
        <div class="card-body">
          <div class="config-row">
            <!-- Windows 配置 -->
            <div class="config-item">
              <div class="config-tag config-tag-windows">Windows</div>
              <div class="config-form">
                <div class="config-field">
                  <label class="config-label">目标版本</label>
                  <ElInput v-model="windowsForm.version" placeholder="时间戳格式" />
                </div>
                <div class="config-field">
                  <label class="config-label">下载地址</label>
                  <ElInput v-model="windowsForm.download_url" placeholder="安装包下载地址" />
                </div>
                <div class="config-field">
                  <label class="config-label">备注</label>
                  <ElInput v-model="windowsForm.note" placeholder="版本说明" />
                </div>
                <ElButton type="success" class="save-btn" @click="saveConfig(windowsConfig, windowsForm)">保存配置</ElButton>
              </div>
            </div>

            <!-- Mac 配置 -->
            <div class="config-item">
              <div class="config-tag config-tag-mac">Mac</div>
              <div class="config-form">
                <div class="config-field">
                  <label class="config-label">目标版本</label>
                  <ElInput v-model="macForm.version" placeholder="时间戳格式" />
                </div>
                <div class="config-field">
                  <label class="config-label">下载地址</label>
                  <ElInput v-model="macForm.download_url" placeholder="安装包下载地址" />
                </div>
                <div class="config-field">
                  <label class="config-label">备注</label>
                  <ElInput v-model="macForm.note" placeholder="版本说明" />
                </div>
                <ElButton type="success" class="save-btn" @click="saveConfig(macConfig, macForm)">保存配置</ElButton>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 批量升级区 -->
      <div class="upgrade-card">
        <div class="card-header">
          <span class="card-title">🚀 批量升级</span>
        </div>
        <div class="card-body">
          <!-- 筛选条件 -->
          <div class="filter-row">
            <div class="filter-item">
              <label class="filter-label">设备类别:</label>
              <ElSelect v-model="filterForm.namespace" style="width: 150px">
                <ElOption v-for="opt in NAMESPACE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
              </ElSelect>
            </div>
            <div class="filter-item">
              <label class="filter-label">设备类型:</label>
              <ElSelect v-model="filterForm.device_type" style="width: 120px">
                <ElOption v-for="opt in DEVICE_TYPE_FILTER_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
              </ElSelect>
            </div>
            <ElButton type="primary" @click="loadPreview">查询预览</ElButton>
          </div>

          <!-- 统计信息 -->
          <div class="stats-row" v-if="previewData">
            <span class="stats-item stats-primary"><strong>可升级:</strong> {{ previewData.upgradable_count }}台</span>
            <span class="stats-item stats-warning"><strong>使用中(待队列):</strong> {{ previewData.waiting_count }}台</span>
            <span class="stats-item stats-success"><strong>已最新:</strong> {{ previewData.latest_count }}台</span>
            <span class="stats-item stats-danger"><strong>离线:</strong> {{ previewData.offline_count }}台</span>
          </div>

          <!-- 机器列表 -->
          <div class="table-wrapper">
            <ElTable
              :data="previewData?.machines || []"
              v-loading="previewLoading"
              border
              stripe
              class="preview-table"
            >
              <ElTableColumn width="80">
                <template #header>
                  <div class="select-header">
                    <ElCheckbox
                      :model-value="isAllSelected"
                      :indeterminate="isIndeterminate"
                      @change="handleSelectAllChange"
                    />
                    <span class="select-label">全选</span>
                  </div>
                </template>
                <template #default="{ row }">
                  <ElCheckbox
                    v-if="isSelectable(row.upgrade_status)"
                    :model-value="selectedMachineIds.includes(row.id)"
                    @change="(val: boolean) => handleCheckboxChange(row.id, val)"
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
              <ElTableColumn prop="version" label="当前版本" min-width="120">
                <template #default="{ row }">
                  <span :class="{'version-old': row.upgrade_status === '待升级' || row.upgrade_status === 'upgradable'}">
                    {{ row.version || '-' }}
                  </span>
                </template>
              </ElTableColumn>
              <ElTableColumn prop="status" label="状态" min-width="80">
                <template #default="{ row }">
                  <span :class="`status-${row.status}`">{{ getStatusText(row.status) }}</span>
                </template>
              </ElTableColumn>
              <ElTableColumn prop="upgrade_status" label="升级状态" min-width="100">
                <template #default="{ row }">
                  <span
                    class="upgrade-status-tag"
                    :style="{
                      background: getUpgradeStatusStyle(row.upgrade_status).bg,
                      color: getUpgradeStatusStyle(row.upgrade_status).color
                    }"
                  >
                    {{ getUpgradeStatusText(row.upgrade_status) }}
                  </span>
                </template>
              </ElTableColumn>
            </ElTable>
          </div>

          <!-- 操作按钮 -->
          <div class="action-row">
            <ElButton type="primary" @click="openConfirmDialog">
              批量升级选中的机器 ({{ selectedMachineIds.length }}台)
            </ElButton>
            <ElButton class="reset-btn" @click="handleReset">重置筛选</ElButton>
          </div>
        </div>
      </div>

      <!-- 升级队列区 -->
      <div class="queue-card">
        <div class="card-header card-header-flex">
          <span class="card-title">📋 升级队列</span>
          <span class="queue-badge">等待: {{ queueData.total }}台</span>
        </div>
        <div class="card-body">
          <div class="table-wrapper">
            <ElTable :data="queueData.items" v-loading="queueLoading" border stripe class="queue-table">
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
                  <span
                    class="upgrade-status-tag"
                    :style="{
                      background: getUpgradeStatusStyle(row.status).bg,
                      color: getUpgradeStatusStyle(row.status).color
                    }"
                  >
                    {{ row.status }}
                  </span>
                </template>
              </ElTableColumn>
              <ElTableColumn label="操作" min-width="80">
                <template #default="{ row }">
                  <a class="remove-link" @click="handleRemoveQueue(row)">移除队列</a>
                </template>
              </ElTableColumn>
            </ElTable>
          </div>
        </div>
      </div>

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
  background: #f5f5f5;
  padding: 20px;
  min-height: 100%;
  font-size: 13px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

/* 卡片通用样式 */
.config-card,
.upgrade-card,
.queue-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
  margin-bottom: 16px;
}

.card-header {
  padding: 16px 16px 8px;
  border-bottom: 1px solid #eee;
}

.card-header-flex {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
}

.card-title {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.card-body {
  padding: 16px;
}

/* 版本配置区 */
.config-row {
  display: flex;
  gap: 24px;
}

.config-item {
  flex: 1;
  background: #fafafa;
  border-radius: 6px;
  padding: 12px;
  border: 1px solid #d9d9d9;
}

.config-tag {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: #fff;
  margin-bottom: 8px;
}

.config-tag-windows {
  background: #1890ff;
}

.config-tag-mac {
  background: #722ed1;
}

.config-form {
  margin-top: 8px;
}

.config-field {
  margin-bottom: 8px;
}

.config-label {
  font-size: 12px;
  color: #666;
  display: block;
  margin-bottom: 4px;
}

/* Element Plus Input 统一字体 */
.config-field :deep(.el-input__inner) {
  font-size: 13px;
}

.save-btn {
  width: 100%;
  margin-top: 8px;
}

/* 筛选条件 */
.filter-row {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 12px;
  background: #fafafa;
  border-radius: 4px;
  margin-bottom: 16px;
}

.filter-item {
  display: flex;
  align-items: center;
}

.filter-label {
  font-size: 12px;
  color: #666;
  margin-right: 8px;
}

/* Element Plus Select 统一字体 */
.filter-item :deep(.el-input__inner) {
  font-size: 13px;
}

/* 统计信息 */
.stats-row {
  display: flex;
  gap: 16px;
  padding: 8px 12px;
  background: #e6f7ff;
  border-radius: 4px;
  border: 1px solid #91d5ff;
  margin-bottom: 12px;
}

.stats-item {
  font-size: 13px;
}

.stats-primary {
  color: #1890ff;
}

.stats-warning {
  color: #faad14;
}

.stats-success {
  color: #52c41a;
}

.stats-danger {
  color: #ff4d4f;
}

/* 表格 */
.table-wrapper {
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  overflow: hidden;
}

.preview-table,
.queue-table {
  font-size: 13px;
}

/* 表头样式 */
.preview-table :deep(th.el-table__cell),
.queue-table :deep(th.el-table__cell) {
  background: #fafafa !important;
  padding: 10px !important;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  border-bottom: 1px solid #e8e8e8 !important;
}

/* 表格单元格样式 */
.preview-table :deep(td.el-table__cell),
.queue-table :deep(td.el-table__cell) {
  padding: 10px !important;
  font-size: 13px;
  color: #333;
}

/* 斑马纹交替背景 */
.preview-table :deep(.el-table__row--striped td.el-table__cell),
.queue-table :deep(.el-table__row--striped td.el-table__cell) {
  background: #fafafa !important;
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
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
}

/* 状态颜色 */
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

/* 版本颜色 */
.version-old {
  color: #ff4d4f;
}

/* 升级状态标签 */
.upgrade-status-tag {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

/* 操作按钮 */
.action-row {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.reset-btn {
  background: #fff;
  color: #333;
  border: 1px solid #d9d9d9;
}

/* 升级队列 */
.queue-badge {
  background: #722ed1;
  color: #fff;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}

.remove-link {
  color: #ff4d4f;
  cursor: pointer;
}

.remove-link:hover {
  text-decoration: underline;
}

/* 确认弹窗 */
.confirm-info {
  font-size: 14px;
  color: #1890ff;
}

.confirm-warning {
  font-size: 13px;
  color: #faad14;
}
</style>