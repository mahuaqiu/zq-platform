<script lang="ts" setup>
import type { ConfigTemplate, ConfigPreviewResponse, DeployRequest } from '#/api/core/env-machine-config';

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
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
  getConfigTemplateListApi,
  createConfigTemplateApi,
  updateConfigTemplateApi,
  deleteConfigTemplateApi,
  getConfigPreviewApi,
  deployConfigApi,
} from '#/api/core/env-machine-config';

defineOptions({ name: 'EnvMachineConfigPage' });

// 模板列表数据
const templateList = ref<ConfigTemplate[]>([]);
const templateLoading = ref(false);

// 当前选中的模板
const selectedTemplate = ref<ConfigTemplate | null>(null);

// 模板弹窗
const templateDialogVisible = ref(false);
const templateDialogTitle = ref('新建模板');
const templateForm = ref({
  name: '',
  namespace: '',
  config_content: '',
  note: '',
});
const templateFormLoading = ref(false);

// 下发筛选
const filterForm = ref({
  namespace: 'all',
  device_type: 'all',
  ip: '',
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
const previewData = ref<ConfigPreviewResponse | null>(null);
const previewLoading = ref(false);
const selectedMachineIds = ref<string[]>([]);

// 下发确认弹窗
const deployDialogVisible = ref(false);
const deployLoading = ref(false);

// 可选机器列表（synced 或 pending）
const selectableMachines = computed(() => {
  if (!previewData.value) return [];
  return previewData.value.machines.filter(m => m.config_status === 'synced' || m.config_status === 'pending');
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

// 加载模板列表
async function loadTemplates() {
  templateLoading.value = true;
  try {
    const data = await getConfigTemplateListApi();
    templateList.value = data.items || [];
    // 默认选中第一个
    if (templateList.value.length > 0 && !selectedTemplate.value) {
      selectedTemplate.value = templateList.value[0];
    }
  } catch (error) {
    ElMessage.error('加载模板列表失败');
  } finally {
    templateLoading.value = false;
  }
}

// 新建模板
function handleCreateTemplate() {
  templateDialogTitle.value = '新建模板';
  templateForm.value = { name: '', namespace: '', config_content: '', note: '' };
  templateDialogVisible.value = true;
}

// 编辑模板
function handleEditTemplate(template: ConfigTemplate) {
  templateDialogTitle.value = '编辑模板';
  templateForm.value = {
    name: template.name,
    namespace: template.namespace || '',
    config_content: template.config_content,
    note: template.note || '',
  };
  selectedTemplate.value = template;
  templateDialogVisible.value = true;
}

// 保存模板
async function handleSaveTemplate() {
  if (!templateForm.value.name.trim()) {
    ElMessage.warning('请输入模板名称');
    return;
  }
  if (!templateForm.value.config_content.trim()) {
    ElMessage.warning('请输入配置内容');
    return;
  }

  templateFormLoading.value = true;
  try {
    if (templateDialogTitle.value === '新建模板') {
      await createConfigTemplateApi({
        name: templateForm.value.name,
        namespace: templateForm.value.namespace || undefined,
        config_content: templateForm.value.config_content,
        note: templateForm.value.note,
      });
      ElMessage.success('创建成功');
    } else {
      if (selectedTemplate.value) {
        await updateConfigTemplateApi(selectedTemplate.value.id, {
          name: templateForm.value.name,
          namespace: templateForm.value.namespace || undefined,
          config_content: templateForm.value.config_content,
          note: templateForm.value.note,
        });
        ElMessage.success('更新成功');
      }
    }
    templateDialogVisible.value = false;
    await loadTemplates();
  } catch (error) {
    ElMessage.error(templateDialogTitle.value === '新建模板' ? '创建失败' : '更新失败');
  } finally {
    templateFormLoading.value = false;
  }
}

// 删除模板
async function handleDeleteTemplate(template: ConfigTemplate) {
  ElMessageBox.confirm(`确定删除模板 "${template.name}" 吗？`, '确认删除', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await deleteConfigTemplateApi(template.id);
      ElMessage.success('删除成功');
      if (selectedTemplate.value?.id === template.id) {
        selectedTemplate.value = null;
      }
      await loadTemplates();
    } catch {
      ElMessage.error('删除失败');
    }
  });
}

// 选择模板
function handleSelectTemplate(template: ConfigTemplate) {
  selectedTemplate.value = template;
}

// 加载预览
async function loadPreview() {
  if (!selectedTemplate.value) return;
  previewLoading.value = true;
  try {
    const data = await getConfigPreviewApi(
      selectedTemplate.value.id,
      filterForm.value.namespace === 'all' ? undefined : filterForm.value.namespace,
      filterForm.value.device_type === 'all' ? undefined : filterForm.value.device_type,
      filterForm.value.ip || undefined
    );
    previewData.value = data;
    selectedMachineIds.value = [];
  } catch (error) {
    ElMessage.error('加载预览失败');
  } finally {
    previewLoading.value = false;
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

// 判断是否可选（synced 或 pending）
function isSelectable(configStatus: string): boolean {
  return configStatus === 'synced' || configStatus === 'pending';
}

// 重置筛选
function handleReset() {
  filterForm.value = { namespace: 'all', device_type: 'all', ip: '' };
  loadPreview();
}

// 打开发布确认弹窗
function openDeployDialog() {
  if (!selectedTemplate.value) {
    ElMessage.warning('请先选择一个配置模板');
    return;
  }
  if (selectedMachineIds.value.length === 0) {
    ElMessage.warning('请选择要下发的机器');
    return;
  }
  deployDialogVisible.value = true;
}

// 执行下发
async function executeDeploy() {
  if (!selectedTemplate.value) return;

  deployLoading.value = true;
  try {
    const params: DeployRequest = {
      template_id: selectedTemplate.value.id,
      machine_ids: selectedMachineIds.value,
    };
    const result = await deployConfigApi(params);

    // 查找失败详情
    const failedDetails = result.details.filter(d => d.status === 'failed');

    if (result.failed_count > 0) {
      const failedMessages = failedDetails.map(d => `${d.ip}: ${d.error_message}`).join('\n');
      ElMessage.warning({
        message: `下发完成，但有 ${result.failed_count} 台失败:\n${failedMessages}`,
        duration: 5000,
      });
    } else {
      ElMessage.success(`下发成功：${result.success_count} 台已下发`);
    }

    deployDialogVisible.value = false;
    await loadPreview();
  } catch (error) {
    ElMessage.error('下发失败');
  } finally {
    deployLoading.value = false;
  }
}

// 获取状态样式
function getStatusStyle(status: string): { bg: string; color: string } {
  const styleMap: Record<string, { bg: string; color: string }> = {
    online: { bg: '#f6ffed', color: '#52c41a' },
    offline: { bg: '#fff1f0', color: '#ff4d4f' },
    using: { bg: '#fff7e6', color: '#faad14' },
    config_updating: { bg: '#f9f0ff', color: '#722ed1' },
  };
  return styleMap[status] || { bg: '#f5f5f5', color: '#666' };
}

// 获取状态文本
function getStatusText(status: string): string {
  const textMap: Record<string, string> = {
    online: '在线',
    offline: '离线',
    using: '使用中',
    config_updating: '更新中',
  };
  return textMap[status] || status;
}

// 获取配置状态样式
function getConfigStatusStyle(configStatus: string): { bg: string; color: string } {
  const styleMap: Record<string, { bg: string; color: string }> = {
    synced: { bg: '#f6ffed', color: '#52c41a' },
    pending: { bg: '#fff7e6', color: '#faad14' },
    updating: { bg: '#f9f0ff', color: '#722ed1' },
    offline: { bg: '#fff1f0', color: '#ff4d4f' },
  };
  return styleMap[configStatus] || { bg: '#f5f5f5', color: '#666' };
}

// 获取配置状态文本
function getConfigStatusText(configStatus: string): string {
  const textMap: Record<string, string> = {
    synced: '已同步',
    pending: '待更新',
    updating: '更新中',
    offline: '离线',
  };
  return textMap[configStatus] || configStatus;
}

// 初始化
onMounted(async () => {
  await loadTemplates();
  await loadPreview();
});
</script>

<template>
  <Page auto-content-height>
    <div class="config-page">
      <!-- 左侧：模板列表 -->
      <div class="template-panel">
        <div class="panel-header">
          <span class="panel-title">配置模板</span>
          <ElButton type="primary" size="small" @click="handleCreateTemplate">新建</ElButton>
        </div>
        <div class="panel-body">
          <div v-if="templateLoading" class="loading-text">加载中...</div>
          <div v-else-if="templateList.length === 0" class="empty-text">暂无模板</div>
          <div v-else class="template-list">
            <div
              v-for="item in templateList"
              :key="item.id"
              :class="['template-item', { active: selectedTemplate?.id === item.id }]"
              @click="handleSelectTemplate(item)"
            >
              <div class="template-name">{{ item.name }}</div>
              <div class="template-note">{{ item.note || '-' }}</div>
              <div class="template-actions">
                <a class="action-link" @click.stop="handleEditTemplate(item)">编辑</a>
                <a class="action-link danger" @click.stop="handleDeleteTemplate(item)">删除</a>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：下发区域 -->
      <div class="deploy-panel">
        <!-- 选中的模板信息 -->
        <div class="template-info-card">
          <div class="card-header">
            <span class="card-title">当前模板</span>
          </div>
          <div class="card-body">
            <div v-if="selectedTemplate" class="template-content">
              <div class="template-meta">
                <span class="meta-label">名称:</span>
                <span class="meta-value">{{ selectedTemplate.name }}</span>
              </div>
              <div class="template-meta">
                <span class="meta-label">备注:</span>
                <span class="meta-value">{{ selectedTemplate.note || '-' }}</span>
              </div>
              <div class="template-meta">
                <span class="meta-label">版本:</span>
                <span class="meta-value">{{ selectedTemplate.version }}</span>
              </div>
              <div class="config-preview">
                <pre>{{ selectedTemplate.config_content }}</pre>
              </div>
            </div>
            <div v-else class="no-template">
              <span>请选择一个配置模板</span>
            </div>
          </div>
        </div>

        <!-- 筛选条件 -->
        <div class="filter-card">
          <div class="card-header">
            <span class="card-title">下发筛选</span>
          </div>
          <div class="card-body">
            <div class="filter-row">
              <div class="filter-item">
                <label class="filter-label">设备类别:</label>
                <ElSelect v-model="filterForm.namespace" style="width: 180px">
                  <ElOption v-for="opt in NAMESPACE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </ElSelect>
              </div>
              <div class="filter-item">
                <label class="filter-label">设备类型:</label>
                <ElSelect v-model="filterForm.device_type" style="width: 120px">
                  <ElOption v-for="opt in DEVICE_TYPE_FILTER_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </ElSelect>
              </div>
              <div class="filter-item">
                <label class="filter-label">IP地址:</label>
                <ElInput v-model="filterForm.ip" placeholder="输入IP模糊匹配" clearable style="width: 160px" />
              </div>
              <ElButton type="primary" @click="loadPreview">查询预览</ElButton>
              <ElButton class="reset-btn" @click="handleReset">重置</ElButton>
            </div>
          </div>
        </div>

        <!-- 预览区域 -->
        <div class="preview-card">
          <div class="card-header card-header-flex">
            <span class="card-title">设备预览</span>
            <span v-if="previewData" class="stats-badge">
              可下发 {{ previewData.deployable_count }} 台 / 更新中 {{ previewData.updating_count }} 台 / 离线 {{ previewData.offline_count }} 台
            </span>
          </div>
          <div class="card-body">
            <div class="table-wrapper">
              <ElTable
                :data="previewData?.machines || []"
                v-loading="previewLoading"
                border
                stripe
                class="preview-table"
              >
                <ElTableColumn :width="100" label="选择">
                  <template #header>
                    <div class="select-header">
                      <input
                        type="checkbox"
                        class="native-checkbox"
                        :checked="isAllSelected"
                        :indeterminate.prop="isIndeterminate"
                        @change="handleSelectAllChange($event.target.checked)"
                      />
                      <span class="select-label">全选</span>
                    </div>
                  </template>
                  <template #default="{ row }">
                    <input
                      type="checkbox"
                      class="native-checkbox"
                      :checked="selectedMachineIds.includes(row.id)"
                      :disabled="!isSelectable(row.config_status)"
                      @change="handleCheckboxChange(row.id, $event.target.checked)"
                    />
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="ip" label="IP地址" min-width="140">
                  <template #default="{ row }">
                    <code class="ip-code">{{ row.ip }}</code>
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="namespace" label="设备类别" min-width="120">
                  <template #default="{ row }">
                    <span class="namespace-tag">{{ row.namespace }}</span>
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="device_type" label="设备类型" min-width="100">
                  <template #default="{ row }">
                    {{ row.device_type === 'windows' ? 'Windows' : 'Mac' }}
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="status" label="机器状态" min-width="80">
                  <template #default="{ row }">
                    <span class="status-tag" :class="`status-${row.status}`">
                      {{ getStatusText(row.status) }}
                    </span>
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="config_status" label="配置状态" min-width="100">
                  <template #default="{ row }">
                    <span
                      class="status-tag"
                      :style="{
                        background: getConfigStatusStyle(row.config_status).bg,
                        color: getConfigStatusStyle(row.config_status).color
                      }"
                    >
                      {{ getConfigStatusText(row.config_status) }}
                    </span>
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="config_version" label="配置版本" min-width="140">
                  <template #default="{ row }">
                    <span class="version-text">{{ row.config_version || '-' }}</span>
                  </template>
                </ElTableColumn>
              </ElTable>
            </div>

            <!-- 操作按钮 -->
            <div class="action-row">
              <ElButton type="primary" @click="openDeployDialog">
                下发配置到选中机器 ({{ selectedMachineIds.length }}台)
              </ElButton>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 模板编辑弹窗 -->
    <ElDialog
      v-model="templateDialogVisible"
      :title="templateDialogTitle"
      width="720px"
      :close-on-click-modal="false"
    >
      <div class="template-form">
        <div class="form-item">
          <label class="form-label">模板名称 <span class="required">*</span></label>
          <ElInput v-model="templateForm.name" placeholder="请输入模板名称" />
        </div>
        <div class="form-item">
          <label class="form-label">适用命名空间</label>
          <ElSelect v-model="templateForm.namespace" placeholder="全部" clearable style="width: 100%">
            <ElOption v-for="opt in NAMESPACE_OPTIONS.filter(o => o.value !== 'all')" :key="opt.value" :label="opt.label" :value="opt.value" />
          </ElSelect>
        </div>
        <div class="form-item">
          <label class="form-label">配置内容 <span class="required">*</span></label>
          <div class="yaml-editor">
            <textarea
              v-model="templateForm.config_content"
              class="yaml-textarea"
              placeholder="请输入 YAML 配置内容..."
              rows="15"
            ></textarea>
          </div>
        </div>
        <div class="form-item">
          <label class="form-label">备注</label>
          <ElInput v-model="templateForm.note" placeholder="请输入备注" />
        </div>
      </div>
      <template #footer>
        <ElButton @click="templateDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="templateFormLoading" @click="handleSaveTemplate">保存</ElButton>
      </template>
    </ElDialog>

    <!-- 下发确认弹窗 -->
    <ElDialog
      v-model="deployDialogVisible"
      width="420px"
      class="deploy-confirm-dialog"
      :show-title="false"
      :close-on-click-modal="false"
    >
      <div class="dialog-box">
        <div class="dialog-header">
          <div class="dialog-icon">
            <svg viewBox="0 0 24 24" width="24" height="24">
              <path fill="#fff" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
          </div>
          <div class="dialog-title">确认下发配置</div>
        </div>

        <div class="dialog-body">
          <p class="dialog-desc">即将把配置下发到选中的设备，下发后设备将应用新配置。</p>

          <div class="info-card">
            <div class="info-row">
              <span class="info-label">模板:</span>
              <span class="info-value">{{ selectedTemplate?.name }}</span>
            </div>
            <div class="count-card">
              <div class="count-number">{{ selectedMachineIds.length }}</div>
              <div class="count-label">台机器待下发</div>
            </div>
          </div>

          <div class="warning-box">
            <svg class="warning-icon" viewBox="0 0 24 24" width="20" height="20">
              <path fill="#fa8c16" d="M12 2L1 21h22L12 2zm0 3.99L19.53 19H4.47L12 5.99zM11 10v4h2v-4h-2zm0 6v2h2v-2h-2z"/>
            </svg>
            <span class="warning-text">配置下发后将立即生效，请确认配置内容正确</span>
          </div>
        </div>

        <div class="dialog-footer">
          <ElButton class="btn-cancel" @click="deployDialogVisible = false">取消</ElButton>
          <ElButton class="btn-confirm" :loading="deployLoading" @click="executeDeploy">确认下发</ElButton>
        </div>
      </div>
    </ElDialog>
  </Page>
</template>

<style scoped>
.config-page {
  display: flex;
  gap: 16px;
  height: 100%;
  padding: 20px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  font-size: 13px;
  background: #f5f5f5;
}

/* 左侧模板面板 */
.template-panel {
  display: flex;
  flex-direction: column;
  width: 280px;
  min-width: 280px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #eee;
}

.panel-title {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.loading-text,
.empty-text {
  padding: 20px;
  text-align: center;
  color: #999;
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.template-item {
  padding: 12px;
  cursor: pointer;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  transition: all 0.2s;
}

.template-item:hover {
  background: #f5f5f5;
}

.template-item.active {
  border-color: #1890ff;
  background: #e6f7ff;
}

.template-name {
  margin-bottom: 4px;
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.template-note {
  margin-bottom: 8px;
  font-size: 12px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-actions {
  display: flex;
  gap: 12px;
}

.action-link {
  font-size: 12px;
  color: #1890ff;
  cursor: pointer;
}

.action-link:hover {
  text-decoration: underline;
}

.action-link.danger {
  color: #ff4d4f;
}

/* 右侧下发面板 */
.deploy-panel {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

/* 通用卡片样式 */
.template-info-card,
.filter-card,
.preview-card {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
}

.card-header {
  padding: 16px 16px 8px;
  border-bottom: 1px solid #eee;
}

.card-header-flex {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
}

.card-title {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.card-body {
  padding: 16px;
}

/* 模板信息 */
.template-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.template-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.meta-label {
  font-size: 13px;
  color: #666;
}

.meta-value {
  font-size: 13px;
  color: #333;
}

.config-preview {
  max-height: 200px;
  padding: 12px;
  overflow: auto;
  background: #f5f5f5;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
}

.config-preview pre {
  margin: 0;
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}

.no-template {
  padding: 40px 20px;
  text-align: center;
  color: #999;
}

/* 筛选条件 */
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
}

.filter-item {
  display: flex;
  align-items: center;
}

.filter-label {
  margin-right: 8px;
  font-size: 12px;
  color: #666;
}

.reset-btn {
  color: #333;
  background: #fff;
  border: 1px solid #d9d9d9;
}

/* 统计徽章 */
.stats-badge {
  padding: 2px 8px;
  font-size: 12px;
  color: #fff;
  background: #1890ff;
  border-radius: 10px;
}

/* 表格 */
.table-wrapper {
  overflow: hidden;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
}

.preview-table {
  font-size: 13px;
}

/* 表头样式 */
.preview-table :deep(th.el-table__cell),
.preview-table :deep(.el-table__header th) {
  padding: 10px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  color: #000 !important;
  background: #fafafa !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
}

/* 表格单元格样式 */
.preview-table :deep(td.el-table__cell) {
  padding: 10px !important;
  font-size: 13px !important;
  font-weight: 400 !important;
  color: #333 !important;
  border-right: 1px solid #e8e8e8 !important;
}

/* 斑马纹交替背景 */
.preview-table :deep(.el-table__row--striped td.el-table__cell) {
  background: #fafafa !important;
}

/* 鼠标悬停样式 */
.preview-table :deep(.el-table__row:hover td.el-table__cell) {
  background: #f5f5f5 !important;
}

.select-header {
  display: flex;
  gap: 8px;
  align-items: center;
  white-space: nowrap;
}

.native-checkbox {
  width: 14px;
  height: 14px;
  accent-color: #1890ff;
  cursor: pointer;
}

.native-checkbox:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.select-label {
  font-size: 12px;
  font-weight: 500;
  color: #1890ff;
}

.ip-code {
  padding: 2px 4px;
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
  background: #f5f5f5;
  border-radius: 2px;
}

.namespace-tag {
  display: inline-block;
  padding: 2px 6px;
  font-size: 12px;
  color: #1890ff;
  background: #e6f7ff;
  border-radius: 4px;
}

.status-tag {
  display: inline-block;
  padding: 2px 6px;
  font-size: 12px;
  border-radius: 4px;
}

/* 操作按钮 */
.action-row {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

/* 模板表单 */
.template-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 13px;
  font-weight: 500;
  color: #333;
}

.required {
  color: #ff4d4f;
}

/* YAML 编辑器样式 */
.yaml-editor {
  background: #1e1e1e;
  border-radius: 4px;
  overflow: hidden;
}

.yaml-textarea {
  width: 100%;
  padding: 12px;
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: #d4d4d4;
  background: #1e1e1e;
  border: none;
  resize: vertical;
  outline: none;
}

.yaml-textarea:focus {
  background: #252526;
}

.yaml-textarea::placeholder {
  color: #6a9955;
}

/* 下发确认弹窗 */
.deploy-confirm-dialog :deep(.el-overlay-dialog) {
  background: transparent !important;
}

.dialog-box {
  overflow: hidden;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgb(0 0 0 / 15%);
}

.dialog-header {
  position: relative;
  padding: 24px 24px 20px;
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
}

.dialog-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  margin-bottom: 12px;
  background: rgb(255 255 255 / 15%);
  border-radius: 50%;
}

.dialog-title {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  letter-spacing: 0.5px;
}

.dialog-body {
  padding: 24px;
}

.dialog-desc {
  margin-bottom: 16px;
  font-size: 14px;
  line-height: 1.6;
  color: #595959;
}

.info-card {
  padding: 12px;
  margin-bottom: 16px;
  background: #fafafa;
  border-radius: 8px;
}

.info-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.info-label {
  font-size: 13px;
  color: #666;
}

.info-value {
  font-size: 13px;
  font-weight: 500;
  color: #333;
}

.count-card {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, #e6f7ff 0%, #bae7ff 100%);
  border: 1px solid #91d5ff;
  border-radius: 10px;
}

.count-number {
  font-family: 'SF Pro Display', 'Segoe UI', sans-serif;
  font-size: 32px;
  font-weight: 700;
  color: #1890ff;
  letter-spacing: -1px;
}

.count-label {
  font-size: 14px;
  font-weight: 500;
  color: #1890ff;
}

.warning-box {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 12px 16px;
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 8px;
}

.warning-icon {
  width: 20px;
  height: 20px;
}

.warning-text {
  font-size: 13px;
  line-height: 1.5;
  color: #d48806;
}

.dialog-footer {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  padding: 16px 24px;
  background: #fafafa;
}

.btn-cancel {
  padding: 10px 24px;
  font-size: 14px;
  color: #595959;
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  transition: all 0.2s;
}

.btn-cancel:hover {
  color: #1890ff;
  background: #fff;
  border-color: #1890ff;
}

.btn-confirm {
  padding: 10px 28px;
  font-size: 14px;
  font-weight: 500;
  color: #fff !important;
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%) !important;
  border: none !important;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgb(24 144 255 / 30%);
  transition: all 0.2s;
}

.btn-confirm:hover {
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%) !important;
  box-shadow: 0 4px 12px rgb(24 144 255 / 40%);
  transform: translateY(-1px);
}
</style>

<!-- 全局样式：Dialog 通过 teleport 渲染到 body 下，scoped 样式无法穿透 -->
<style>
.el-dialog.deploy-confirm-dialog {
  padding: 0 !important;
  overflow: hidden !important;
  background: transparent !important;
  border: none !important;
  border-radius: 12px !important;
  box-shadow: none !important;
}

.el-dialog.deploy-confirm-dialog .el-dialog__header {
  display: none !important;
}

.el-dialog.deploy-confirm-dialog .el-dialog__headerbtn {
  display: none !important;
}

.el-dialog.deploy-confirm-dialog .el-dialog__body {
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
}

.el-dialog.deploy-confirm-dialog .el-dialog__footer {
  padding: 0 !important;
  border: none !important;
}
</style>