<script lang="ts" setup>
import type { ConfigTemplate, ConfigPreviewResponse, DeployRequest } from '#/api/core/env-machine-config';

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElDialog,
  ElInput,
  ElMessage,
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

// 删除确认弹窗
const deleteDialogVisible = ref(false);
const deleteTargetTemplate = ref<ConfigTemplate | null>(null);
const deleteLoading = ref(false);

// 下发筛选
const filterForm = ref({
  namespace: 'all',
  device_type: 'all',
  ip: '',
});

// Namespace 选项
const NAMESPACE_OPTIONS = [
  { label: '全部', value: 'all' },
  { label: '集成验证', value: 'meeting_gamma' },
  { label: 'APP', value: 'meeting_app' },
  { label: '音视频', value: 'meeting_av' },
  { label: '公共设备', value: 'meeting_public' },
];

// Namespace 显示名称（弹窗用，只显示中文）
const NAMESPACE_OPTIONS_DIALOG = [
  { label: '全部命名空间', value: '' },
  { label: '集成验证', value: 'meeting_gamma' },
  { label: 'APP', value: 'meeting_app' },
  { label: '音视频', value: 'meeting_av' },
  { label: '公共设备', value: 'meeting_public' },
];

// Namespace 显示名称
const NAMESPACE_DISPLAY: Record<string, string> = {
  meeting_gamma: '集成验证',
  meeting_app: 'APP',
  meeting_av: '音视频',
  meeting_public: '公共设备',
};

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

// 获取模板适用命名空间的显示文本
function getTemplateNamespaceDisplay(namespace?: string): string {
  if (!namespace) return '全部命名空间';
  return NAMESPACE_DISPLAY[namespace] || namespace;
}

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
  templateDialogTitle.value = '新建配置模板';
  templateForm.value = { name: '', namespace: '', config_content: '', note: '' };
  templateDialogVisible.value = true;
}

// 编辑模板
function handleEditTemplate(template: ConfigTemplate) {
  templateDialogTitle.value = '编辑配置模板';
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
    if (templateDialogTitle.value === '新建配置模板') {
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
    ElMessage.error(templateDialogTitle.value === '新建配置模板' ? '创建失败' : '更新失败');
  } finally {
    templateFormLoading.value = false;
  }
}

// 打开删除确认弹窗
function handleDeleteTemplate(template: ConfigTemplate) {
  deleteTargetTemplate.value = template;
  deleteDialogVisible.value = true;
}

// 执行删除
async function executeDelete() {
  if (!deleteTargetTemplate.value) return;
  deleteLoading.value = true;
  try {
    await deleteConfigTemplateApi(deleteTargetTemplate.value.id);
    ElMessage.success('删除成功');
    if (selectedTemplate.value?.id === deleteTargetTemplate.value.id) {
      selectedTemplate.value = null;
    }
    deleteDialogVisible.value = false;
    await loadTemplates();
  } catch {
    ElMessage.error('删除失败');
  } finally {
    deleteLoading.value = false;
  }
}

// 选择模板
function handleSelectTemplate(template: ConfigTemplate) {
  selectedTemplate.value = template;
  loadPreview();
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

// 获取状态文本
function getStatusText(status: string): string {
  const textMap: Record<string, string> = {
    online: '在线',
    offline: '离线',
    using: '使用中',
    config_updating: '配置更新中',
  };
  return textMap[status] || status;
}

// 获取状态颜色
function getStatusColor(status: string): string {
  const colorMap: Record<string, string> = {
    online: '#52c41a',
    offline: '#ff4d4f',
    using: '#faad14',
    config_updating: '#722ed1',
  };
  return colorMap[status] || '#666';
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

// 获取配置版本颜色
function getConfigVersionColor(configStatus: string): string {
  const colorMap: Record<string, string> = {
    synced: '#52c41a',
    pending: '#faad14',
    updating: '#722ed1',
    offline: '#999',
  };
  return colorMap[configStatus] || '#999';
}

// 获取命名空间显示名称
function getNamespaceDisplay(namespace: string): string {
  return NAMESPACE_DISPLAY[namespace] || namespace;
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
          <span class="panel-title">📝 配置模板</span>
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
              <div class="template-info">
                <div class="template-name">{{ item.name }}</div>
                <div class="template-meta">适用：{{ getTemplateNamespaceDisplay(item.namespace) }}</div>
                <div class="template-version">版本：{{ item.version }}</div>
              </div>
              <div class="template-actions">
                <a class="action-link" @click.stop="handleEditTemplate(item)">编辑</a>
                <a class="action-link danger" @click.stop="handleDeleteTemplate(item)">删除</a>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：下发配置区 -->
      <div class="deploy-panel">
        <div class="deploy-card">
          <div class="deploy-header">🚀 下发配置</div>
          <div class="deploy-body">
            <!-- 筛选条件行 -->
            <div class="filter-row">
              <div class="filter-item">
                <label class="filter-label">命名空间:</label>
                <ElSelect v-model="filterForm.namespace" style="width: 140px">
                  <ElOption v-for="opt in NAMESPACE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </ElSelect>
              </div>
              <div class="filter-item">
                <label class="filter-label">设备类型:</label>
                <ElSelect v-model="filterForm.device_type" style="width: 100px">
                  <ElOption v-for="opt in DEVICE_TYPE_FILTER_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </ElSelect>
              </div>
              <div class="filter-item">
                <label class="filter-label">IP搜索:</label>
                <ElInput v-model="filterForm.ip" placeholder="输入IP筛选" clearable style="width: 140px" />
              </div>
              <ElButton type="primary" @click="loadPreview">查询预览</ElButton>
              <ElButton class="reset-btn" @click="handleReset">重置</ElButton>
            </div>

            <!-- 当前模板提示条 -->
            <div v-if="selectedTemplate" class="template-tip">
              <span class="tip-label">📦 当前模板：</span>
              <span class="tip-name">{{ selectedTemplate.name }}</span>
              <span class="tip-version">（v{{ selectedTemplate.version }}）</span>
              <span class="tip-hint">点击左侧切换</span>
            </div>

            <!-- 统计信息 -->
            <div v-if="previewData" class="stats-row">
              <span class="stats-item stats-deployable"><strong>可下发:</strong> {{ previewData.deployable_count }}台</span>
              <span class="stats-item stats-updating"><strong>配置更新中:</strong> {{ previewData.updating_count }}台</span>
              <span class="stats-item stats-offline"><strong>离线:</strong> {{ previewData.offline_count }}台</span>
            </div>

            <!-- 机器列表表格 -->
            <div class="table-wrapper">
              <ElTable
                :data="previewData?.machines || []"
                v-loading="previewLoading"
                border
                stripe
                class="preview-table"
              >
                <ElTableColumn :width="40" label="选择" align="center">
                  <template #header>
                    <input
                      type="checkbox"
                      class="native-checkbox"
                      :checked="isAllSelected"
                      :indeterminate.prop="isIndeterminate"
                      @change="handleSelectAllChange($event.target.checked)"
                    />
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
                <ElTableColumn prop="namespace" label="命名空间" min-width="100">
                  <template #default="{ row }">
                    {{ getNamespaceDisplay(row.namespace) }}
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="device_type" label="设备类型" min-width="80">
                  <template #default="{ row }">
                    {{ row.device_type === 'windows' ? 'Windows' : 'Mac' }}
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="status" label="机器状态" min-width="100">
                  <template #default="{ row }">
                    <span :style="{ color: getStatusColor(row.status) }">
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
                    <span :style="{ color: getConfigVersionColor(row.config_status) }">
                      {{ row.config_version || '-' }}
                    </span>
                  </template>
                </ElTableColumn>
              </ElTable>
            </div>

            <!-- 操作按钮 -->
            <div class="action-row">
              <div class="selected-count">已选择 <strong class="count-num">{{ selectedMachineIds.length }}</strong> 台机器</div>
              <ElButton type="primary" @click="openDeployDialog">下发配置</ElButton>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建/编辑模板弹窗 -->
    <ElDialog
      v-model="templateDialogVisible"
      width="720px"
      class="template-dialog"
      :show-title="false"
      :close-on-click-modal="false"
    >
      <div class="template-dialog-box">
        <!-- 弹窗头部 -->
        <div class="template-dialog-header">
          <span class="template-dialog-title">📝 {{ templateDialogTitle }}</span>
          <span class="template-dialog-close" @click="templateDialogVisible = false">✕</span>
        </div>

        <!-- 弹窗内容 -->
        <div class="template-dialog-body">
          <!-- 基本信息 -->
          <div class="form-section">
            <div class="section-title">基本信息</div>
            <div class="section-content">
              <div class="form-row">
                <div class="form-col">
                  <label class="form-label">模板名称 <span class="required">*</span></label>
                  <ElInput v-model="templateForm.name" placeholder="如：默认配置模板" />
                </div>
                <div class="form-col">
                  <label class="form-label">适用命名空间</label>
                  <ElSelect v-model="templateForm.namespace" placeholder="全部命名空间" clearable style="width: 100%">
                    <ElOption v-for="opt in NAMESPACE_OPTIONS_DIALOG" :key="opt.value" :label="opt.label" :value="opt.value" />
                  </ElSelect>
                </div>
              </div>
              <div class="form-row">
                <div class="form-col-full">
                  <label class="form-label">备注说明</label>
                  <ElInput v-model="templateForm.note" placeholder="模板用途说明" />
                </div>
              </div>
            </div>
          </div>

          <!-- 配置内容 -->
          <div class="form-section">
            <div class="section-title">配置内容 (YAML)</div>
            <div class="section-content">
              <div class="yaml-editor">
                <textarea
                  v-model="templateForm.config_content"
                  class="yaml-textarea"
                  placeholder="在此编辑 YAML 配置文件..."
                  rows="18"
                ></textarea>
              </div>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="template-dialog-footer">
          <ElButton class="btn-cancel" @click="templateDialogVisible = false">取消</ElButton>
          <ElButton class="btn-save" type="primary" :loading="templateFormLoading" @click="handleSaveTemplate">保存模板</ElButton>
        </div>
      </div>
    </ElDialog>

    <!-- 删除确认弹窗 -->
    <ElDialog
      v-model="deleteDialogVisible"
      width="400px"
      class="delete-dialog"
      :show-title="false"
      :close-on-click-modal="false"
    >
      <div class="delete-dialog-box">
        <div class="delete-dialog-body">
          <div class="delete-icon">
            <svg viewBox="0 0 24 24" width="24" height="24">
              <path fill="#ff4d4f" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
            </svg>
          </div>
          <div class="delete-title">确定删除模板？</div>
          <div class="delete-desc">删除后将无法恢复，已下发的配置不受影响</div>
          <div class="delete-template-name">
            <strong>模板名称：</strong>{{ deleteTargetTemplate?.name }}
          </div>
        </div>
        <div class="delete-dialog-footer">
          <ElButton class="btn-cancel" @click="deleteDialogVisible = false">取消</ElButton>
          <ElButton class="btn-delete" :loading="deleteLoading" @click="executeDelete">确认删除</ElButton>
        </div>
      </div>
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
  width: 300px;
  min-width: 300px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
}

.panel-title {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
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
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  transition: all 0.2s;
}

.template-item:hover {
  background: #f5f5f5;
}

.template-item.active {
  border: 2px solid #1890ff;
  background: #e6f7ff;
}

.template-info {
  margin-bottom: 8px;
}

.template-name {
  font-size: 13px;
  font-weight: 500;
  color: #333;
}

.template-item.active .template-name {
  color: #1890ff;
}

.template-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #666;
}

.template-version {
  margin-top: 4px;
  font-size: 11px;
  color: #999;
}

.template-actions {
  display: flex;
  gap: 8px;
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
  flex: 1;
  min-width: 0;
}

.deploy-card {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
}

.deploy-header {
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.deploy-body {
  padding: 16px;
}

/* 筛选条件行 */
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 4px;
  margin-bottom: 16px;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 12px;
  color: #666;
}

.reset-btn {
  color: #333;
  background: #fff;
  border: 1px solid #d9d9d9;
}

/* 当前模板提示条 */
.template-tip {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: 10px 12px;
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 4px;
  margin-bottom: 12px;
}

.tip-label {
  font-size: 13px;
  color: #d48806;
}

.tip-name {
  font-size: 13px;
  font-weight: 500;
  color: #333;
}

.tip-version {
  font-size: 12px;
  color: #666;
}

.tip-hint {
  font-size: 12px;
  color: #999;
  margin-left: 8px;
}

/* 统计信息行 */
.stats-row {
  display: flex;
  gap: 16px;
  padding: 8px 12px;
  background: #e6f7ff;
  border: 1px solid #91d5ff;
  border-radius: 4px;
  margin-bottom: 12px;
  font-size: 12px;
}

.stats-item {
  color: #1890ff;
}

.stats-updating {
  color: #722ed1;
}

.stats-offline {
  color: #ff4d4f;
}

/* 表格 */
.table-wrapper {
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  overflow: hidden;
}

.preview-table {
  font-size: 13px;
}

.preview-table :deep(th.el-table__cell) {
  padding: 10px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  color: #000 !important;
  background: #fafafa !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
}

.preview-table :deep(td.el-table__cell) {
  padding: 10px !important;
  font-size: 13px !important;
  color: #333 !important;
  border-right: 1px solid #e8e8e8 !important;
}

.preview-table :deep(.el-table__row--striped td.el-table__cell) {
  background: #fafafa !important;
}

.preview-table :deep(.el-table__row:hover td.el-table__cell) {
  background: #f5f5f5 !important;
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

.ip-code {
  padding: 2px 4px;
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
  background: #f5f5f5;
  border-radius: 2px;
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
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
}

.selected-count {
  font-size: 13px;
  color: #666;
}

.count-num {
  color: #1890ff;
}

/* 模板编辑弹窗 */
.template-dialog-box {
  overflow: hidden;
  background: #fff;
  border-radius: 8px;
}

.template-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
}

.template-dialog-title {
  color: #fff;
  font-size: 16px;
  font-weight: 500;
}

.template-dialog-close {
  color: #fff;
  cursor: pointer;
  font-size: 18px;
}

.template-dialog-close:hover {
  opacity: 0.8;
}

.template-dialog-body {
  padding: 20px;
}

.form-section {
  margin-bottom: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 500;
  color: #333;
  padding-bottom: 8px;
  margin-bottom: 12px;
  border-bottom: 1px solid #eee;
}

.section-content {
  /* 内容区域 */
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 12px;
}

.form-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-col-full {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 12px;
  color: #666;
}

.required {
  color: #ff4d4f;
}

.yaml-editor {
  background: #1e1e1e;
  border-radius: 4px;
  padding: 16px;
}

.yaml-textarea {
  width: 100%;
  min-height: 320px;
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #d4d4d4;
  background: transparent;
  border: none;
  resize: vertical;
  outline: none;
}

.yaml-textarea::placeholder {
  color: #6a9955;
}

.template-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #eee;
}

.btn-cancel {
  padding: 8px 20px;
  font-size: 14px;
  color: #333;
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
}

.btn-cancel:hover {
  color: #1890ff;
  border-color: #1890ff;
}

.btn-save {
  padding: 8px 20px;
  font-size: 14px;
  color: #fff;
  background: #1890ff;
  border: none;
  border-radius: 4px;
}

/* 删除确认弹窗 */
.delete-dialog-box {
  overflow: hidden;
  background: #fff;
  border-radius: 8px;
}

.delete-dialog-body {
  padding: 24px;
  text-align: center;
}

.delete-icon {
  width: 48px;
  height: 48px;
  background: #fff1f0;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.delete-title {
  font-size: 16px;
  font-weight: 500;
  color: #333;
  margin-bottom: 8px;
}

.delete-desc {
  font-size: 13px;
  color: #666;
  margin-bottom: 16px;
}

.delete-template-name {
  padding: 12px;
  background: #f5f5f5;
  border-radius: 4px;
  font-size: 13px;
}

.delete-dialog-footer {
  padding: 16px 24px;
  background: #fafafa;
  display: flex;
  justify-content: center;
  gap: 12px;
}

.btn-delete {
  padding: 8px 24px;
  font-size: 14px;
  color: #fff;
  background: #ff4d4f;
  border: none;
  border-radius: 4px;
}

.btn-delete:hover {
  background: #ff7875;
}

/* 下发确认弹窗 */
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
.el-dialog.template-dialog {
  padding: 0 !important;
  overflow: hidden !important;
  background: transparent !important;
  border: none !important;
  border-radius: 8px !important;
  box-shadow: none !important;
}

.el-dialog.template-dialog .el-dialog__header {
  display: none !important;
}

.el-dialog.template-dialog .el-dialog__headerbtn {
  display: none !important;
}

.el-dialog.template-dialog .el-dialog__body {
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
}

.el-dialog.template-dialog .el-dialog__footer {
  padding: 0 !important;
  border: none !important;
}

.el-dialog.delete-dialog {
  padding: 0 !important;
  overflow: hidden !important;
  background: transparent !important;
  border: none !important;
  border-radius: 8px !important;
  box-shadow: none !important;
}

.el-dialog.delete-dialog .el-dialog__header {
  display: none !important;
}

.el-dialog.delete-dialog .el-dialog__headerbtn {
  display: none !important;
}

.el-dialog.delete-dialog .el-dialog__body {
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
}

.el-dialog.delete-dialog .el-dialog__footer {
  padding: 0 !important;
  border: none !important;
}

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