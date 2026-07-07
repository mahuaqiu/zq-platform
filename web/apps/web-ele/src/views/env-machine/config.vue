<script lang="ts" setup>
import type {
  ConfigTemplate,
  ConfigPreviewResponse,
  ConfigPreviewMachine,
  DeployRequest,
  MachineSelectionTemplate,
} from '#/api/core/env-machine-config';

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
  ElTabPane,
  ElTabs,
} from 'element-plus';

import {
  getConfigTemplateListApi,
  createConfigTemplateApi,
  updateConfigTemplateApi,
  deleteConfigTemplateApi,
  getConfigPreviewApi,
  deployConfigApi,
  getMachineSelectionTemplateListApi,
  createMachineSelectionTemplateApi,
  deleteMachineSelectionTemplateApi,
} from '#/api/core/env-machine-config';

import { useNamespaceStore } from './store';
import CommandTaskHistory from './modules/CommandTaskHistory.vue';

defineOptions({ name: 'EnvMachineConfigPage' });

// 命名空间 Store
const namespaceStore = useNamespaceStore();

// Tab 切换：下发列表 / 任务历史
const activeTab = ref<'deploy' | 'history'>('deploy');

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
  type: 'config' as 'config' | 'script' | 'command',
  script_name: '',
  command: '',
  namespace: '',
  config_content: '',
  note: '',
});
const templateFormLoading = ref(false);

// IP 模板相关
const ipTemplateList = ref<MachineSelectionTemplate[]>([]);
const ipTemplateLoading = ref(false);
const saveIpTemplateVisible = ref(false);
const useIpTemplateVisible = ref(false);
const ipTemplateForm = ref({ name: '', note: '' });
const ipTemplateSaving = ref(false);

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

// 可选机器列表（仅 pending 状态，且设备类型为 windows/mac）
const selectableMachines = computed(() => {
  if (!previewData.value) return [];
  return previewData.value.machines.filter(m =>
    m.config_status === 'pending' &&
    (m.device_type === 'windows' || m.device_type === 'mac')
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

// 脚本类型模板：禁用设备类型筛选（已自动过滤）
const isDeviceTypeFilterDisabled = computed(() => {
  return selectedTemplate.value?.type === 'script';
});

// 脚本类型模板：显示当前筛选的目标系统
const deviceTypeFilterHint = computed(() => {
  if (selectedTemplate.value?.type === 'script' && selectedTemplate.value?.script_name) {
    const targetOs = getTargetOsDisplay(selectedTemplate.value.script_name);
    return `已自动筛选 ${targetOs} 设备`;
  }
  return '';
});

// 下发按钮文案
const deployButtonText = computed(() => {
  if (selectedTemplate.value?.type === 'script') {
    return '下发脚本';
  }
  if (selectedTemplate.value?.type === 'command') {
    return '运行命令';
  }
  return '下发配置';
});

// 当前模板是否为运行命令类型
const isCommandTemplate = computed(() => selectedTemplate.value?.type === 'command');

// 获取模板适用命名空间的显示文本
function getTemplateNamespaceDisplay(namespace?: string): string {
  if (!namespace) return '全部命名空间';
  return namespaceStore.getNamespaceText(namespace);
}

// 根据脚本扩展名获取目标系统显示
function getTargetOsDisplay(scriptName?: string): string {
  if (!scriptName) return '';
  const ext = scriptName.toLowerCase().split('.').pop();
  if (ext === 'ps1' || ext === 'bat') return 'Windows';
  if (ext === 'sh') return 'Mac';
  return '';
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
  templateDialogTitle.value = '新建模板';
  selectedTemplate.value = null;
  templateForm.value = {
    name: '',
    type: 'config',
    script_name: '',
    command: '',
    namespace: '',
    config_content: '',
    note: '',
  };
  templateDialogVisible.value = true;
}

// 编辑模板
function handleEditTemplate(template: ConfigTemplate) {
  templateDialogTitle.value = '编辑模板';
  templateForm.value = {
    name: template.name,
    type: template.type || 'config',
    script_name: template.script_name || '',
    command: template.command || '',
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

  // 脚本类型校验
  if (templateForm.value.type === 'script') {
    if (!templateForm.value.script_name.trim()) {
      ElMessage.warning('请输入脚本名称');
      return;
    }
    const ext = templateForm.value.script_name.toLowerCase().split('.').pop();
    if (ext && !['ps1', 'bat', 'sh'].includes(ext)) {
      ElMessage.warning('脚本扩展名必须是 .ps1, .bat 或 .sh');
      return;
    }
  }

  // 运行命令类型校验
  if (templateForm.value.type === 'command') {
    if (!templateForm.value.command.trim()) {
      ElMessage.warning('请输入命令内容');
      return;
    }
  }

  // 配置/脚本类型必须有内容；命令类型 config_content 可为空
  if (templateForm.value.type !== 'command' && !templateForm.value.config_content.trim()) {
    ElMessage.warning('请输入配置内容');
    return;
  }

  const isNewTemplate = selectedTemplate.value === null;
  templateFormLoading.value = true;
  try {
    const payload: Partial<ConfigTemplate> = {
      name: templateForm.value.name,
      type: templateForm.value.type,
      script_name: templateForm.value.type === 'script' ? templateForm.value.script_name : undefined,
      command: templateForm.value.type === 'command' ? templateForm.value.command : undefined,
      namespace: templateForm.value.namespace || undefined,
      config_content: templateForm.value.type === 'command' ? '' : templateForm.value.config_content,
      note: templateForm.value.note,
    };
    if (isNewTemplate) {
      await createConfigTemplateApi(payload);
      ElMessage.success('创建成功');
    } else {
      await updateConfigTemplateApi(selectedTemplate.value!.id, payload);
      ElMessage.success('更新成功');
    }
    templateDialogVisible.value = false;
    await loadTemplates();
  } catch (error) {
    ElMessage.error(isNewTemplate ? '创建失败' : '更新失败');
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
      {
        namespace: filterForm.value.namespace === 'all' ? undefined : filterForm.value.namespace,
        device_type: filterForm.value.device_type === 'all' ? undefined : filterForm.value.device_type,
        ip: filterForm.value.ip || undefined,
      }
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

// 判断是否可选（仅 pending 状态，且设备类型为 windows/mac）
function isSelectable(configStatus: string, deviceType: string): boolean {
  // 只有 windows 和 mac 设备才能下发配置
  if (deviceType !== 'windows' && deviceType !== 'mac') {
    return false;
  }
  // 只有 pending 状态（需要更新）才可选，synced（已是最新）不可选
  return configStatus === 'pending';
}

// 获取显示版本（根据模板类型）
function getDisplayVersion(row: ConfigPreviewMachine): string {
  if (!selectedTemplate.value) return row.config_version || '-';

  // 脚本模板：显示脚本版本
  if (selectedTemplate.value.type === 'script' && selectedTemplate.value.script_name) {
    const scriptVersion = row.scripts?.[selectedTemplate.value.script_name];
    return scriptVersion || '-';
  }

  // 配置模板：显示配置版本
  return row.config_version || '-';
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
      // 运行命令类型：带上模板中的命令内容（允许后端覆盖）
      command: selectedTemplate.value.type === 'command' ? selectedTemplate.value.command : undefined,
    };
    const result = await deployConfigApi(params);

    // 运行命令类型：后端异步执行，返回 task_id，跳转到任务历史
    if (selectedTemplate.value.type === 'command') {
      ElMessage.success(`命令已提交执行，共 ${selectedMachineIds.value.length} 台机器，请到“任务历史”查看进度`);
      deployDialogVisible.value = false;
      activeTab.value = 'history';
      return;
    }

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
    ElMessage.error(selectedTemplate.value.type === 'command' ? '命令提交失败' : '下发失败');
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
  return namespaceStore.getNamespaceText(namespace);
}

// ========== IP 模板相关 ==========

// 加载 IP 模板列表
async function loadIpTemplates() {
  ipTemplateLoading.value = true;
  try {
    const data = await getMachineSelectionTemplateListApi({ page: 1, page_size: 100 });
    ipTemplateList.value = data.items || [];
  } catch (error) {
    ElMessage.error('加载 IP 模板失败');
  } finally {
    ipTemplateLoading.value = false;
  }
}

// 打开"保存为 IP 模板"弹窗
function openSaveIpTemplate() {
  if (selectedMachineIds.value.length === 0) {
    ElMessage.warning('请先选择要保存的机器');
    return;
  }
  ipTemplateForm.value = { name: '', note: '' };
  saveIpTemplateVisible.value = true;
}

// 确认保存 IP 模板
async function confirmSaveIpTemplate() {
  if (!ipTemplateForm.value.name.trim()) {
    ElMessage.warning('请输入模板名称');
    return;
  }
  ipTemplateSaving.value = true;
  try {
    await createMachineSelectionTemplateApi({
      name: ipTemplateForm.value.name,
      machine_ids: [...selectedMachineIds.value],
      note: ipTemplateForm.value.note || undefined,
    });
    ElMessage.success('IP 模板保存成功');
    saveIpTemplateVisible.value = false;
    await loadIpTemplates();
  } catch (error) {
    ElMessage.error('保存 IP 模板失败');
  } finally {
    ipTemplateSaving.value = false;
  }
}

// 打开"使用 IP 模板"弹窗
async function openUseIpTemplate() {
  if (ipTemplateList.value.length === 0) {
    await loadIpTemplates();
  }
  useIpTemplateVisible.value = true;
}

// 应用某个 IP 模板到当前选中机器
function applyIpTemplate(template: MachineSelectionTemplate) {
  if (!template.machine_ids || template.machine_ids.length === 0) {
    ElMessage.warning('该 IP 模板没有保存机器列表');
    return;
  }
  // 只选中当前预览列表中实际存在的机器
  const allMachineIds = previewData.value?.machines.map(m => m.id) || [];
  const validIds = template.machine_ids.filter(id => allMachineIds.includes(id));
  selectedMachineIds.value = validIds;
  ElMessage.success(`已应用 IP 模板“${template.name}”，选中 ${validIds.length} 台机器`);
  useIpTemplateVisible.value = false;
}

// 删除 IP 模板
async function handleDeleteIpTemplate(template: MachineSelectionTemplate) {
  try {
    await ElMessageBox.confirm(`确定要删除 IP 模板“${template.name}”吗？`, '提示', {
      type: 'warning',
    });
    await deleteMachineSelectionTemplateApi(template.id);
    ElMessage.success('删除成功');
    await loadIpTemplates();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败');
    }
  }
}

// 初始化
onMounted(async () => {
  // 加载命名空间配置
  await namespaceStore.loadNamespaceConfig();
  // 加载模板和预览
  await loadTemplates();
  await loadPreview();
});
</script>

<template>
  <Page auto-content-height>
    <ElTabs v-model="activeTab" class="config-tabs">
      <ElTabPane label="下发列表" name="deploy">
        <div class="config-page">
      <!-- 左侧：模板列表 -->
      <div class="template-panel">
        <div class="panel-header">
          <span class="panel-title">📝 下发列表</span>
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
                <div class="template-name">
                  <span class="template-type-tag" :class="`type-tag-${item.type}`">
                    {{ item.type === 'script' ? '脚本' : item.type === 'command' ? '命令' : '配置' }}
                  </span>
                  <span>{{ item.name }}</span>
                </div>
                <div class="template-meta">适用：{{ getTemplateNamespaceDisplay(item.namespace) }}</div>

                <!-- 脚本类型：显示脚本名称和目标系统 -->
                <div v-if="item.type === 'script'" class="template-script-info">
                  <span class="script-name">{{ item.script_name }}</span>
                  <span class="script-os">{{ getTargetOsDisplay(item.script_name) }}</span>
                </div>

                <!-- 运行命令类型：显示命令内容预览 -->
                <div v-if="item.type === 'command'" class="template-script-info">
                  <code class="script-name command-preview">{{ item.command }}</code>
                </div>

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
                  <ElOption v-for="opt in namespaceStore.namespaceOptionsWithAll" :key="opt.value" :label="opt.label" :value="opt.value" />
                </ElSelect>
              </div>
              <div class="filter-item">
                <label class="filter-label">设备类型:</label>
                <ElSelect
                  v-model="filterForm.device_type"
                  style="width: 100px"
                  :disabled="isDeviceTypeFilterDisabled"
                >
                  <ElOption v-for="opt in DEVICE_TYPE_FILTER_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </ElSelect>
                <span v-if="deviceTypeFilterHint" class="filter-hint">{{ deviceTypeFilterHint }}</span>
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
              <span class="stats-item stats-updating"><strong>下发更新中:</strong> {{ previewData.updating_count }}台</span>
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
                max-height="400"
              >
                <ElTableColumn :width="50" label="选择" align="center">
                  <template #header>
                    <input
                      type="checkbox"
                      class="native-checkbox"
                      :checked="isAllSelected"
                      :indeterminate.prop="isIndeterminate"
                      @change="handleSelectAllChange(($event.target as HTMLInputElement).checked)"
                    />
                  </template>
                  <template #default="{ row }">
                    <input
                      type="checkbox"
                      class="native-checkbox"
                      :checked="selectedMachineIds.includes(row.id)"
                      :disabled="!isSelectable(row.config_status, row.device_type)"
                      @change="handleCheckboxChange(row.id, ($event.target as HTMLInputElement).checked)"
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
                    {{ row.device_type === 'windows' ? 'Windows' : row.device_type === 'mac' ? 'Mac' : row.device_type }}
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="status" label="机器状态" min-width="100">
                  <template #default="{ row }">
                    <span :style="{ color: getStatusColor(row.status) }">
                      {{ getStatusText(row.status) }}
                    </span>
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="config_status" label="下发状态" min-width="100">
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
                <ElTableColumn prop="config_version" label="下发版本" min-width="140">
                  <template #default="{ row }">
                    <span :style="{ color: getConfigVersionColor(row.config_status) }">
                      {{ getDisplayVersion(row) }}
                    </span>
                  </template>
                </ElTableColumn>
              </ElTable>
            </div>

            <!-- 操作按钮 -->
            <div class="action-row">
              <div class="selected-count">已选择 <strong class="count-num">{{ selectedMachineIds.length }}</strong> 台机器</div>
              <div class="action-buttons">
                <button class="ip-btn ip-btn-save" @click="openSaveIpTemplate" :disabled="selectedMachineIds.length === 0">
                  <svg class="ip-btn-icon" viewBox="0 0 24 24" width="15" height="15">
                    <path fill="currentColor" d="M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z"/>
                  </svg>
                  <span>保存为IP模板</span>
                </button>
                <button class="ip-btn ip-btn-use" @click="openUseIpTemplate">
                  <svg class="ip-btn-icon" viewBox="0 0 24 24" width="15" height="15">
                    <path fill="currentColor" d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-2 10h-4v4h-2v-4H7v-2h4V7h2v4h4v2z"/>
                  </svg>
                  <span>使用IP模板</span>
                </button>
                <ElButton type="primary" @click="openDeployDialog">{{ deployButtonText }}</ElButton>
              </div>
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
                  <label class="form-label">模板类型 <span class="required">*</span></label>
                  <ElSelect v-model="templateForm.type" style="width: 100%">
                    <ElOption label="配置" value="config" />
                    <ElOption label="脚本" value="script" />
                    <ElOption label="运行命令" value="command" />
                  </ElSelect>
                </div>
              </div>

              <!-- 脚本名称：仅脚本类型显示 -->
              <div v-if="templateForm.type === 'script'" class="form-row">
                <div class="form-col-full">
                  <label class="form-label">脚本名称 <span class="required">*</span></label>
                  <ElInput
                    v-model="templateForm.script_name"
                    placeholder="如 play_ppt.ps1，扩展名仅支持 .ps1/.bat/.sh"
                  />
                </div>
              </div>

              <!-- 命令内容：仅运行命令类型显示 -->
              <div v-if="templateForm.type === 'command'" class="form-row">
                <div class="form-col-full">
                  <label class="form-label">命令内容 <span class="required">*</span></label>
                  <ElInput
                    v-model="templateForm.command"
                    type="textarea"
                    :rows="3"
                    placeholder="如：dir C:\\Users 或 ipconfig /all"
                  />
                </div>
              </div>

              <div class="form-row">
                <div class="form-col">
                  <label class="form-label">适用命名空间</label>
                  <ElSelect v-model="templateForm.namespace" placeholder="全部命名空间" clearable style="width: 100%">
                    <ElOption v-for="opt in namespaceStore.namespaceOptionsDialog" :key="opt.value" :label="opt.label" :value="opt.value" />
                  </ElSelect>
                </div>
                <div class="form-col">
                  <label class="form-label">备注说明</label>
                  <ElInput v-model="templateForm.note" placeholder="模板用途说明" />
                </div>
              </div>
            </div>
          </div>

          <!-- 配置内容/脚本内容（运行命令类型不需要） -->
          <div v-if="templateForm.type !== 'command'" class="form-section">
            <div class="section-title">
              {{ templateForm.type === 'config' ? '配置内容 (YAML)' : '脚本内容' }}
            </div>
            <div class="section-content">
              <div class="yaml-editor">
                <textarea
                  v-model="templateForm.config_content"
                  class="yaml-textarea"
                  :placeholder="templateForm.type === 'config' ? '在此编辑 YAML 配置文件...' : '在此编辑脚本内容...'"
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
          <div class="dialog-title">
            {{ isCommandTemplate ? '确认运行命令' : selectedTemplate?.type === 'script' ? '确认下发脚本' : '确认下发配置' }}
          </div>
        </div>

        <div class="dialog-body">
          <p class="dialog-desc">
            {{ isCommandTemplate
              ? '即将在选中的设备上执行命令，命令可能改变设备状态，请确认命令内容。'
              : selectedTemplate?.type === 'script'
                ? '即将把脚本下发到选中的设备，下发后设备将保存脚本文件。'
                : '即将把配置下发到选中的设备，下发后设备将应用新配置。'
            }}
          </p>

          <div class="info-card">
            <div class="info-row">
              <span class="info-label">模板:</span>
              <span class="info-value">{{ selectedTemplate?.name }}</span>
            </div>
            <div v-if="isCommandTemplate && selectedTemplate?.command" class="info-row">
              <span class="info-label">命令:</span>
              <code class="info-value command-code">{{ selectedTemplate.command }}</code>
            </div>
            <div class="count-card">
              <div class="count-number">{{ selectedMachineIds.length }}</div>
              <div class="count-label">台机器待执行</div>
            </div>
          </div>

          <div class="warning-box">
            <svg class="warning-icon" viewBox="0 0 24 24" width="20" height="20">
              <path fill="#fa8c16" d="M12 2L1 21h22L12 2zm0 3.99L19.53 19H4.47L12 5.99zM11 10v4h2v-4h-2zm0 6v2h2v-2h-2z"/>
            </svg>
            <span class="warning-text">
              {{ isCommandTemplate ? '命令将在设备上实时执行，请确认命令内容安全' : selectedTemplate?.type === 'script' ? '脚本下发后将保存到设备，请确认脚本内容正确' : '配置下发后将立即生效，请确认配置内容正确' }}
            </span>
          </div>
        </div>

        <div class="dialog-footer">
          <ElButton class="btn-cancel" @click="deployDialogVisible = false">取消</ElButton>
          <ElButton class="btn-confirm" :loading="deployLoading" @click="executeDeploy">
            {{ isCommandTemplate ? '确认执行' : '确认下发' }}
          </ElButton>
        </div>
      </div>
    </ElDialog>
      </ElTabPane>

      <!-- 任务历史 Tab -->
      <ElTabPane label="任务历史" name="history">
        <CommandTaskHistory v-if="activeTab === 'history'" />
      </ElTabPane>
    </ElTabs>

    <!-- 保存为 IP 模板弹窗 -->
    <ElDialog
      v-model="saveIpTemplateVisible"
      title="保存为 IP 模板"
      width="440px"
      :close-on-click-modal="false"
    >
      <div class="ip-template-dialog-body">
        <div class="ip-form-row">
          <label class="ip-form-label">模板名称 <span class="required">*</span></label>
          <ElInput v-model="ipTemplateForm.name" placeholder="如：全部测试机" />
        </div>
        <div class="ip-form-row">
          <label class="ip-form-label">备注</label>
          <ElInput v-model="ipTemplateForm.note" placeholder="选填，模板用途说明" />
        </div>
        <div class="ip-preview">
          预览：已选择 <strong>{{ selectedMachineIds.length }}</strong> 台机器
        </div>
      </div>
      <template #footer>
        <ElButton @click="saveIpTemplateVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="ipTemplateSaving" @click="confirmSaveIpTemplate">保存</ElButton>
      </template>
    </ElDialog>

    <!-- 使用 IP 模板弹窗 -->
    <ElDialog
      v-model="useIpTemplateVisible"
      title="使用 IP 模板"
      width="560px"
      :close-on-click-modal="false"
    >
      <div v-loading="ipTemplateLoading" class="ip-template-list">
        <div v-if="ipTemplateList.length === 0 && !ipTemplateLoading" class="ip-empty">
          暂无 IP 模板，请先在下方机器列表选择机器后“保存为IP模板”
        </div>
        <div
          v-for="tpl in ipTemplateList"
          :key="tpl.id"
          class="ip-template-item"
        >
          <div class="ip-template-info">
            <div class="ip-template-name">{{ tpl.name }}</div>
            <div class="ip-template-meta">
              包含 {{ tpl.machine_ids?.length || 0 }} 台机器
              <span v-if="tpl.note"> · {{ tpl.note }}</span>
            </div>
          </div>
          <div class="ip-template-actions">
            <ElButton size="small" type="primary" @click="applyIpTemplate(tpl)">使用</ElButton>
            <ElButton size="small" type="danger" plain @click="handleDeleteIpTemplate(tpl)">删除</ElButton>
          </div>
        </div>
      </div>
      <template #footer>
        <ElButton @click="useIpTemplateVisible = false">关闭</ElButton>
      </template>
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

.template-script-info {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 12px;
}

.script-name {
  color: #1890ff;
}

.script-os {
  color: #666;
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
  overflow-x: auto;
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

.filter-hint {
  font-size: 12px;
  color: #faad14;
  margin-left: 8px;
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
  overflow-x: auto;
}

.preview-table {
  font-size: 13px;
}

/* 表头样式 */
.preview-table :deep(.el-table__header-wrapper th.el-table__cell) {
  padding: 10px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  color: #000 !important;
  background: #fafafa !important;
  border-bottom: 1px solid #e8e8e8 !important;
}

/* 表格单元格样式 */
.preview-table :deep(.el-table__body-wrapper td.el-table__cell) {
  padding: 10px !important;
  font-size: 13px !important;
  color: #333 !important;
}

/* 边框样式 - ElTable border 属性 */
.preview-table.el-table--border :deep(.el-table__cell) {
  border-right: 1px solid #e8e8e8 !important;
}

.preview-table.el-table--border :deep(th.el-table__cell) {
  border-bottom: 1px solid #e8e8e8 !important;
}

/* 斑马纹 */
.preview-table :deep(.el-table__row--striped td.el-table__cell) {
  background: #fafafa !important;
}

/* hover 效果 */
.preview-table :deep(.el-table__row:hover td.el-table__cell) {
  background: #f5f5f5 !important;
}

/* 修复单元格内部容器 overflow */
.preview-table :deep(.el-table__cell .cell) {
  overflow: visible !important;
}

/* checkbox 样式 */
.native-checkbox {
  width: 14px;
  height: 14px;
  accent-color: #1890ff;
  cursor: pointer;
  vertical-align: middle;
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

/* Tab 容器 */
.config-tabs {
  height: 100%;
}

.config-tabs :deep(.el-tabs__content) {
  height: calc(100% - 40px);
  overflow: auto;
}

.config-tabs :deep(.el-tab-pane) {
  height: 100%;
}

/* 模板类型标签 */
.template-type-tag {
  display: inline-block;
  padding: 1px 6px;
  margin-right: 6px;
  font-size: 11px;
  border-radius: 3px;
  vertical-align: middle;
}

.type-tag-config {
  background: #e6f7ff;
  color: #1890ff;
}

.type-tag-script {
  background: #f6ffed;
  color: #52c41a;
}

.type-tag-command {
  background: #fff7e6;
  color: #fa8c16;
}

.command-preview {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #fa8c16;
}

/* 操作按钮行 */
.action-buttons {
  display: flex;
  gap: 10px;
  align-items: center;
}

/* IP 模板按钮通用样式 */
.ip-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  font-size: 13px;
  font-weight: 500;
  line-height: 1;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  white-space: nowrap;
  user-select: none;
  outline: none;
}

.ip-btn-icon {
  flex-shrink: 0;
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 保存为IP模板 - Default 风格（描边型） */
.ip-btn-save {
  color: #1890ff;
  background: #fff;
  border: 1px solid #91d5ff;
  box-shadow: 0 1px 2px rgb(24 144 255 / 8%);
}

.ip-btn-save:hover {
  color: #096dd9;
  background: #e6f7ff;
  border-color: #69c0ff;
  box-shadow: 0 2px 6px rgb(24 144 255 / 15%);
  transform: translateY(-1px);
}

.ip-btn-save:active {
  color: #0050b3;
  background: #bae7ff;
  border-color: #40a9ff;
  box-shadow: 0 0 0 rgb(24 144 255 / 0%);
  transform: translateY(0);
}

.ip-btn-save:disabled {
  color: #bfbfbf;
  background: #f5f5f5;
  border-color: #d9d9d9;
  box-shadow: none;
  cursor: not-allowed;
  transform: none;
}

.ip-btn-save:disabled .ip-btn-icon {
  opacity: 0.4;
}

/* 使用IP模板 - 轻量 Primary 风格（渐变浅底） */
.ip-btn-use {
  color: #fff;
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
  border: none;
  box-shadow: 0 2px 6px rgb(24 144 255 / 25%);
}

.ip-btn-use:hover {
  background: linear-gradient(135deg, #40a9ff 0%, #1890ff 100%);
  box-shadow: 0 4px 12px rgb(24 144 255 / 35%);
  transform: translateY(-1px);
}

.ip-btn-use:active {
  background: linear-gradient(135deg, #096dd9 0%, #0050b3 100%);
  box-shadow: 0 0 0 rgb(24 144 255 / 0%);
  transform: translateY(0);
}

.ip-btn-use:hover .ip-btn-icon {
  transform: scale(1.1);
}

/* 下发确认弹窗中的命令代码 */
.command-code {
  display: block;
  padding: 6px 8px;
  margin-top: 4px;
  background: #f5f5f5;
  border-radius: 3px;
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  word-break: break-all;
}

/* IP 模板弹窗 */
.ip-template-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ip-form-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ip-form-label {
  font-size: 13px;
  color: #333;
}

.ip-form-label .required {
  color: #ff4d4f;
}

.ip-preview {
  padding: 8px 12px;
  background: #f0f5ff;
  border-radius: 4px;
  color: #1890ff;
  font-size: 13px;
}

.ip-template-list {
  max-height: 360px;
  overflow-y: auto;
}

.ip-empty {
  padding: 32px;
  text-align: center;
  color: #999;
}

.ip-template-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: #fafafa;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
}

.ip-template-name {
  font-size: 13px;
  font-weight: 500;
  color: #333;
}

.ip-template-meta {
  margin-top: 2px;
  font-size: 12px;
  color: #999;
}

.ip-template-actions {
  display: flex;
  gap: 8px;
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