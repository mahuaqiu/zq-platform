<script lang="ts" setup>
import type { AISkill } from '#/api/core/ai-assistant';

import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElEmpty,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPagination,
  ElSelect,
  ElTag,
} from 'element-plus';

import {
  deleteAISkillApi,
  getAISkillListApi,
} from '#/api/core/ai-assistant';
import SkillEditDialog from './components/SkillEditDialog.vue';
import SkillAssignDialog from './components/SkillAssignDialog.vue';

defineOptions({ name: 'AISkillPage' });

// 数据
const skillList = ref<AISkill[]>([]);
const loading = ref(false);
const total = ref(0);
const page = ref(1);
const pageSize = ref(10);

// 篮选条件
const searchKeyword = ref('');
const filterType = ref<'all' | 'assigned' | 'unassigned'>('all');

// 弹窗
const editDialogVisible = ref(false);
const editSkillId = ref<string | null>(null);
const assignDialogVisible = ref(false);
const assignSkillId = ref<string | null>(null);
const assignSkillName = ref('');

// 加载数据
async function loadData() {
  loading.value = true;
  try {
    const res = await getAISkillListApi({
      search_keyword: searchKeyword.value || undefined,
      filter_type: filterType.value === 'all' ? undefined : filterType.value,
      page: page.value,
      page_size: pageSize.value,
    });
    skillList.value = res.items || [];
    total.value = res.total;
  } catch (error) {
    console.error('加载数据失败:', error);
    ElMessage.error('加载数据失败');
  } finally {
    loading.value = false;
  }
}

// 搜索
function handleSearch() {
  page.value = 1;
  loadData();
}

// 重置
function handleReset() {
  searchKeyword.value = '';
  filterType.value = 'all';
  page.value = 1;
  loadData();
}

// 分页变化
function handlePageChange(newPage: number) {
  page.value = newPage;
  loadData();
}

function handleSizeChange(newSize: number) {
  pageSize.value = newSize;
  page.value = 1;
  loadData();
}

// 新增
function handleCreate() {
  editSkillId.value = null;
  editDialogVisible.value = true;
}

// 编辑
function handleEdit(skill: AISkill) {
  editSkillId.value = skill.id;
  editDialogVisible.value = true;
}

// 分配
function handleAssign(skill: AISkill) {
  assignSkillId.value = skill.id;
  assignSkillName.value = skill.name || skill.id;
  assignDialogVisible.value = true;
}

// 删除
function handleDelete(skill: AISkill) {
  ElMessageBox.confirm(
    `确定要删除 Skill "${skill.name || skill.id}" 吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    },
  ).then(async () => {
    try {
      await deleteAISkillApi(skill.id);
      ElMessage.success('删除成功');
      loadData();
    } catch {
      ElMessage.error('删除失败');
    }
  });
}

// 弹窗关闭后刷新
function handleEditSuccess() {
  editDialogVisible.value = false;
  loadData();
}

function handleAssignSuccess() {
  assignDialogVisible.value = false;
  loadData();
}

// 初始加载
onMounted(() => {
  loadData();
});
</script>

<template>
  <Page auto-content-height>
    <div class="skill-page">
      <!-- 搜索区域 -->
      <div class="skill-search-area">
        <div class="skill-search-form">
          <div class="skill-search-item">
            <label class="skill-search-label">关键词</label>
            <ElInput
              v-model="searchKeyword"
              placeholder="搜索 Skill ID 或名称"
              clearable
              style="width: 220px"
              @keyup.enter="handleSearch"
            />
          </div>
          <div class="skill-search-item">
            <label class="skill-search-label">筛选</label>
            <ElSelect v-model="filterType" style="width: 140px">
              <ElOption label="全部" value="all" />
              <ElOption label="已分配" value="assigned" />
              <ElOption label="未分配" value="unassigned" />
            </ElSelect>
          </div>

          <div class="skill-search-buttons">
            <ElButton type="primary" @click="handleSearch">查询</ElButton>
            <ElButton @click="handleReset">重置</ElButton>
          </div>

          <!-- 新增按钮 -->
          <ElButton type="success" class="skill-create-btn" @click="handleCreate">
            + 新增 Skill
          </ElButton>
        </div>
      </div>

      <!-- 卡片网格区域 -->
      <div v-loading="loading" class="skill-card-grid">
        <template v-if="skillList.length > 0">
          <ElCard
            v-for="skill in skillList"
            :key="skill.id"
            class="skill-card"
            shadow="hover"
          >
            <div class="skill-card-title">
              <span class="skill-id">{{ skill.id }}</span>
              <span v-if="skill.name && skill.name !== skill.id" class="skill-name">{{ skill.name }}</span>
            </div>

            <div v-if="skill.description" class="skill-description">
              {{ skill.description }}
            </div>

            <!-- 分配角色标签 -->
            <div class="skill-roles">
              <template v-if="skill.assigned_locations?.length > 0">
                <ElTag
                  v-for="loc in skill.assigned_locations.slice(0, 3)"
                  :key="`${loc.jid}-${loc.profile_id}`"
                  type="primary"
                  size="small"
                  class="role-tag"
                >
                  角色: {{ loc.profile_name || loc.profile_id }}
                </ElTag>
                <ElTag
                  v-if="skill.assigned_locations.length > 3"
                  type="info"
                  size="small"
                >
                  +{{ skill.assigned_locations.length - 3 }}
                </ElTag>
              </template>
              <span v-else class="skill-roles-empty">未分配给任何角色</span>
            </div>

            <!-- 操作按钮 -->
            <div class="skill-card-actions">
              <ElButton link type="primary" @click="handleEdit(skill)">编辑</ElButton>
              <ElButton link type="primary" @click="handleAssign(skill)">分配角色</ElButton>
              <ElButton link type="danger" @click="handleDelete(skill)">删除</ElButton>
            </div>
          </ElCard>
        </template>
        <ElEmpty v-else description="暂无 Skill 数据" />
      </div>

      <!-- 分页 -->
      <div class="skill-pagination">
        <ElPagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <SkillEditDialog
      v-model:visible="editDialogVisible"
      :skill-id="editSkillId"
      @success="handleEditSuccess"
    />

    <!-- 分配弹窗 -->
    <SkillAssignDialog
      v-model:visible="assignDialogVisible"
      :skill-id="assignSkillId"
      :skill-name="assignSkillName"
      @success="handleAssignSuccess"
    />
  </Page>
</template>

<style scoped>
.skill-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* 搜索区域 */
.skill-search-area {
  padding: 16px;
  margin-bottom: 16px;
  background: #fafafa;
  border-radius: 4px;
}

.skill-search-form {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-end;
}

.skill-search-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.skill-search-label {
  display: block;
  font-size: 12px;
  color: #666;
}

.skill-search-buttons {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.skill-create-btn {
  font-weight: 500;
  color: #fff !important;
  background: #52c41a !important;
  border-color: #52c41a !important;
}

/* 2列网格布局 */
.skill-card-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  padding: 0 16px;
  overflow-y: auto;
  align-content: start;
}

.skill-card {
  border: 1px solid #e8e8e8;
}

.skill-card :deep(.el-card__body) {
  padding: 12px;
}

.skill-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.skill-id {
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.skill-name {
  font-size: 14px;
  color: #666;
}

.skill-description {
  color: #666;
  font-size: 12px;
  line-height: 1.5;
  margin-bottom: 8px;
}

/* 角色标签 */
.skill-roles {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.role-tag {
  background: #e6f7ff;
  color: #1890ff;
}

.skill-roles-empty {
  color: #999;
  font-size: 11px;
}

/* 操作按钮 */
.skill-card-actions {
  display: flex;
  gap: 8px;
  font-size: 12px;
}

/* 分页 */
.skill-pagination {
  padding: 16px;
  display: flex;
  justify-content: center;
  background: #fafafa;
  border-top: 1px solid #e8e8e8;
}
</style>