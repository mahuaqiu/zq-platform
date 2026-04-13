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

// 筛选条件
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
    });
    skillList.value = res.items || [];
  } catch (error) {
    console.error('加载数据失败:', error);
    ElMessage.error('加载数据失败');
  } finally {
    loading.value = false;
  }
}

// 搜索
function handleSearch() {
  loadData();
}

// 重置
function handleReset() {
  searchKeyword.value = '';
  filterType.value = 'all';
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
  assignSkillName.value = skill.name;
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

      <!-- 卡片区域 -->
      <div v-loading="loading" class="skill-card-container">
        <template v-if="skillList.length > 0">
          <ElCard
            v-for="skill in skillList"
            :key="skill.id"
            class="skill-card"
            shadow="hover"
          >
            <template #header>
              <div class="skill-card-header">
                <div class="skill-card-title">
                  <span class="skill-id">{{ skill.id }}</span>
                  <span v-if="skill.name" class="skill-name">{{ skill.name }}</span>
                </div>
                <div class="skill-card-actions">
                  <ElButton link type="primary" @click="handleEdit(skill)">
                    编辑
                  </ElButton>
                  <ElButton link type="primary" @click="handleAssign(skill)">
                    分配
                  </ElButton>
                  <ElButton link type="danger" @click="handleDelete(skill)">
                    删除
                  </ElButton>
                </div>
              </div>
            </template>

            <div class="skill-card-body">
              <!-- 描述 -->
              <div v-if="skill.description" class="skill-description">
                {{ skill.description }}
              </div>

              <!-- 分配位置 -->
              <div class="skill-locations">
                <div class="skill-locations-label">分配位置：</div>
                <div v-if="skill.assigned_locations?.length > 0" class="skill-locations-tags">
                  <ElTag
                    v-for="loc in skill.assigned_locations"
                    :key="`${loc.jid}-${loc.profile_id}`"
                    type="primary"
                    size="small"
                    class="location-tag"
                  >
                    {{ loc.group_name || loc.jid }} / {{ loc.profile_name || loc.profile_id }}
                  </ElTag>
                </div>
                <div v-else class="skill-locations-empty">
                  未分配
                </div>
              </div>

              <!-- 更新时间 -->
              <div class="skill-meta">
                <span v-if="skill.sys_update_datetime">
                  更新：{{ skill.sys_update_datetime }}
                </span>
                <span v-else-if="skill.sys_create_datetime">
                  创建：{{ skill.sys_create_datetime }}
                </span>
              </div>
            </div>
          </ElCard>
        </template>
        <ElEmpty v-else description="暂无 Skill 数据" />
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

/* 卡片区域 */
.skill-card-container {
  flex: 1;
  padding: 0 16px 16px;
  overflow-y: auto;
}

.skill-card {
  margin-bottom: 16px;
}

.skill-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.skill-card-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.skill-id {
  padding: 2px 8px;
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 14px;
  font-weight: 600;
  color: #1890ff;
  background: #e6f7ff;
  border-radius: 4px;
}

.skill-name {
  font-size: 16px;
  font-weight: 500;
  color: #333;
}

.skill-card-actions {
  display: flex;
  gap: 8px;
}

.skill-card-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skill-description {
  color: #666;
  line-height: 1.6;
}

.skill-locations {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-start;
}

.skill-locations-label {
  flex-shrink: 0;
  font-size: 13px;
  color: #666;
}

.skill-locations-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.location-tag {
  margin: 0;
}

.skill-locations-empty {
  color: #999;
}

.skill-meta {
  font-size: 12px;
  color: #999;
}
</style>