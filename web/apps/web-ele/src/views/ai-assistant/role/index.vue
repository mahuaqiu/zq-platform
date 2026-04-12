<script lang="ts" setup>
import type { AIRole } from '#/api/core/ai-assistant';

import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPagination,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
} from 'element-plus';

import {
  deleteAIRoleApi,
  getAIRoleListApi,
  createAIRoleApi,
  updateAIRoleApi,
} from '#/api/core/ai-assistant';

defineOptions({ name: 'AIRolePage' });

// 数据
const tableData = ref<AIRole[]>([]);
const total = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);

// 筛选条件
const searchForm = ref({
  name: '',
  is_active: undefined as boolean | undefined,
});

// 弹窗
const dialogVisible = ref(false);
const dialogLoading = ref(false);
const isEdit = ref(false);
const editId = ref('');

// 表单数据
const formData = ref({
  name: '',
  description: '',
  system_prompt: '',
  avatar: '',
  is_active: true,
});

// 加载数据
async function loadData() {
  loading.value = true;
  try {
    const res = await getAIRoleListApi({
      name: searchForm.value.name || undefined,
      is_active: searchForm.value.is_active,
      page: currentPage.value,
      page_size: pageSize.value,
    });
    tableData.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    console.error('加载数据失败:', error);
    ElMessage.error('加载数据失败');
  } finally {
    loading.value = false;
  }
}

// 搜索
function handleSearch() {
  currentPage.value = 1;
  loadData();
}

// 重置
function handleReset() {
  searchForm.value = {
    name: '',
    is_active: undefined,
  };
  currentPage.value = 1;
  loadData();
}

// 分页
function handlePageChange(page: number) {
  currentPage.value = page;
  loadData();
}

function handleSizeChange(size: number) {
  pageSize.value = size;
  currentPage.value = 1;
  loadData();
}

// 新增
function handleCreate() {
  isEdit.value = false;
  editId.value = '';
  formData.value = {
    name: '',
    description: '',
    system_prompt: '',
    avatar: '',
    is_active: true,
  };
  dialogVisible.value = true;
}

// 编辑
function handleEdit(row: AIRole) {
  isEdit.value = true;
  editId.value = row.id;
  formData.value = {
    name: row.name,
    description: row.description || '',
    system_prompt: row.system_prompt || '',
    avatar: row.avatar || '',
    is_active: row.is_active,
  };
  dialogVisible.value = true;
}

// 删除
function handleDelete(row: AIRole) {
  ElMessageBox.confirm(`确定要删除角色 "${row.name}" 吗？`, '删除确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await deleteAIRoleApi(row.id);
      ElMessage.success('删除成功');
      loadData();
    } catch {
      ElMessage.error('删除失败');
    }
  });
}

// 提交表单
async function handleSubmit() {
  if (!formData.value.name) {
    ElMessage.warning('请输入角色名称');
    return;
  }

  dialogLoading.value = true;
  try {
    if (isEdit.value) {
      await updateAIRoleApi(editId.value, {
        name: formData.value.name,
        description: formData.value.description,
        system_prompt: formData.value.system_prompt,
        avatar: formData.value.avatar,
        is_active: formData.value.is_active,
      });
      ElMessage.success('更新成功');
    } else {
      await createAIRoleApi({
        name: formData.value.name,
        description: formData.value.description,
        system_prompt: formData.value.system_prompt,
        avatar: formData.value.avatar,
        is_active: formData.value.is_active,
      });
      ElMessage.success('创建成功');
    }
    dialogVisible.value = false;
    loadData();
  } catch (error: any) {
    const msg = error?.response?.data?.detail || '操作失败';
    ElMessage.error(msg);
  } finally {
    dialogLoading.value = false;
  }
}

// 初始加载
onMounted(() => {
  loadData();
});
</script>

<template>
  <Page auto-content-height>
    <div class="flex h-full flex-col">
      <!-- 搜索区域 -->
      <div class="env-search-area">
        <div class="env-search-form">
          <div class="env-search-item">
            <label class="env-search-label">角色名称</label>
            <ElInput
              v-model="searchForm.name"
              placeholder="搜索角色名称"
              clearable
              style="width: 180px"
            />
          </div>
          <div class="env-search-item">
            <label class="env-search-label">状态</label>
            <ElSelect
              v-model="searchForm.is_active"
              placeholder="全部"
              clearable
              style="width: 100px"
            >
              <ElOption label="启用" :value="true" />
              <ElOption label="禁用" :value="false" />
            </ElSelect>
          </div>

          <div class="env-search-buttons">
            <ElButton type="primary" @click="handleSearch">查询</ElButton>
            <ElButton @click="handleReset">重置</ElButton>
          </div>

          <!-- 新增按钮 -->
          <ElButton type="success" class="env-create-btn" @click="handleCreate">
            + 新增角色
          </ElButton>
        </div>
      </div>

      <!-- 表格区域 -->
      <div class="env-table-wrapper">
        <ElTable :data="tableData" v-loading="loading" class="env-table" border>
          <ElTableColumn prop="name" label="角色名称" min-width="120">
            <template #default="{ row }">
              {{ row.name }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="description" label="描述" min-width="200">
            <template #default="{ row }">
              {{ row.description || '-' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="is_active" label="状态" min-width="80" align="center">
            <template #default="{ row }">
              <span :class="row.is_active ? 'env-status-success' : 'env-status-danger'">
                {{ row.is_active ? '启用' : '禁用' }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="sys_create_datetime" label="创建时间" min-width="160">
            <template #default="{ row }">
              {{ row.sys_create_datetime || '-' }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" min-width="120">
            <template #default="{ row }">
              <span class="nowrap">
                <a class="env-link" @click="handleEdit(row)">编辑</a>
                <a class="env-link env-link-danger" @click="handleDelete(row)">删除</a>
              </span>
            </template>
          </ElTableColumn>
        </ElTable>

        <!-- 分页 -->
        <div class="env-pagination">
          <ElPagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="handlePageChange"
            @size-change="handleSizeChange"
          />
        </div>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <ElDialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑角色' : '新增角色'"
      width="600px"
      :close-on-click-modal="false"
    >
      <ElForm label-width="100px">
        <!-- 角色名称 -->
        <ElFormItem label="角色名称" :required="!isEdit">
          <ElInput
            v-model="formData.name"
            placeholder="请输入角色名称，触发词格式 @角色名称"
          />
        </ElFormItem>

        <!-- 角色描述 -->
        <ElFormItem label="角色描述">
          <ElInput
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入角色描述"
          />
        </ElFormItem>

        <!-- 系统提示词 -->
        <ElFormItem label="系统提示词">
          <ElInput
            v-model="formData.system_prompt"
            type="textarea"
            :rows="4"
            placeholder="请输入系统提示词（AI角色的核心配置）"
          />
        </ElFormItem>

        <!-- 角色头像 -->
        <ElFormItem label="角色头像">
          <ElInput v-model="formData.avatar" placeholder="请输入头像URL" />
        </ElFormItem>

        <!-- 启用状态 -->
        <ElFormItem label="启用状态">
          <ElSwitch v-model="formData.is_active" />
        </ElFormItem>
      </ElForm>

      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="dialogLoading" @click="handleSubmit">
          确定
        </ElButton>
      </template>
    </ElDialog>
  </Page>
</template>

<style scoped>
/* 搜索区域 */
.env-search-area {
  padding: 16px;
  margin-bottom: 16px;
  background: #fafafa;
  border-radius: 4px;
}

.env-search-form {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-end;
}

.env-search-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.env-search-label {
  display: block;
  font-size: 12px;
  color: #666;
}

.env-search-buttons {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.env-create-btn {
  font-weight: 500;
  color: #fff !important;
  background: #52c41a !important;
  border-color: #52c41a !important;
}

/* 表格区域 */
.env-table-wrapper {
  flex: 1;
  padding: 16px;
  overflow: auto;
  background: #fff;
  border-radius: 4px;
}

/* 表格支持水平滚动 */
.env-table-wrapper :deep(.el-table__body-wrapper) {
  overflow-x: auto;
}

/* 带边框表格样式 */
.env-table {
  --el-table-border-color: #e8e8e8;
  --el-table-header-bg-color: #fafafa;
  --el-table-tr-bg-color: #fff;
  --el-table-row-hover-bg-color: #fafafa;
  --el-table-text-color: #333;
  --el-table-header-text-color: #333;
}

/* 确保表格有外边框 */
.env-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.env-table :deep(.el-table__border-left-patch) {
  background-color: #e8e8e8 !important;
}

/* 表头样式 */
.env-table :deep(th.el-table__cell) {
  padding: 12px 10px !important;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  white-space: nowrap;
  background: #fafafa !important;
  border-color: #e8e8e8 !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
}

/* 表格单元格样式 */
.env-table :deep(td.el-table__cell) {
  padding: 12px 10px !important;
  font-size: 13px;
  color: #333;
  border-color: #e8e8e8 !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
}

.env-dash {
  color: #999;
}

/* 状态样式 */
.env-status-success {
  color: #52c41a;
}

.env-status-warning {
  color: #faad14;
}

.env-status-danger {
  color: #ff4d4f;
}

/* 操作链接 */
.env-link {
  margin-right: 12px;
  color: #1890ff;
  text-decoration: none;
  cursor: pointer;
}

.env-link:hover {
  text-decoration: underline;
}

.env-link-danger {
  margin-right: 0;
  color: #ff4d4f;
}

/* 分页 */
.env-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0 0;
}

/* 不换行 - 用于操作列 */
.nowrap {
  white-space: nowrap;
}
</style>