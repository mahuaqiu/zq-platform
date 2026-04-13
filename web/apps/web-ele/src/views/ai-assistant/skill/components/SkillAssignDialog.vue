<script lang="ts" setup>
import type { AIGroup, SkillAssignmentInfo } from '#/api/core/ai-assistant';

import { onMounted, ref, watch, computed } from 'vue';

import {
  ElButton,
  ElDialog,
  ElMessage,
  ElTree,
} from 'element-plus';

import {
  getAIGroupListApi,
  getAISkillAssignmentsApi,
  assignSkillToProfileApi,
  removeSkillFromProfileApi,
} from '#/api/core/ai-assistant';

const props = defineProps<{
  visible: boolean;
  skillId: string | null;
  skillName: string;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'success'): void;
}>();

defineOptions({ name: 'SkillAssignDialog' });

// 数据
const loading = ref(false);
const submitLoading = ref(false);

// 群组列表（包含角色信息）
const groupList = ref<AIGroup[]>([]);

// 当前已分配的位置
const currentAssignments = ref<SkillAssignmentInfo[]>([]);

// Tree 数据
const treeData = computed(() => {
  return groupList.value.map((group) => ({
    id: group.id,
    label: group.group_name || group.group_id,
    children: group.roles?.map((role) => ({
      id: `${group.group_id}_${role.id}`,
      label: role.name,
      jid: group.group_id,
      profileId: role.id,
    })) || [],
    isGroup: true,
    jid: group.group_id,
  }));
});

// 选中的节点
const checkedNodes = ref<string[]>([]);

// Tree 引用
const treeRef = ref<InstanceType<typeof ElTree> | null>(null);

// 监听 visible 变化
watch(
  () => props.visible,
  async (newVisible) => {
    if (newVisible) {
      await loadData();
      await loadCurrentAssignments();
    }
  },
);

// 加载群组列表
async function loadData() {
  loading.value = true;
  try {
    const res = await getAIGroupListApi({
      page: 1,
      page_size: 1000,
    });
    groupList.value = res.items || [];
  } catch (error) {
    console.error('加载群组列表失败:', error);
    ElMessage.error('加载群组列表失败');
  } finally {
    loading.value = false;
  }
}

// 加载当前分配信息
async function loadCurrentAssignments() {
  if (!props.skillId) return;
  try {
    const res = await getAISkillAssignmentsApi(props.skillId);
    currentAssignments.value = res || [];

    // 设置已选中的节点
    const checkedKeys = res.map(
      (item) => `${item.jid}_${item.profile_id}`,
    );
    checkedNodes.value = checkedKeys;

    // 等待 Tree 组件渲染后设置选中状态
    await new Promise((resolve) => setTimeout(resolve, 100));
    if (treeRef.value) {
      treeRef.value.setCheckedKeys(checkedKeys, false);
    }
  } catch (error) {
    console.error('加载分配信息失败:', error);
    ElMessage.error('加载分配信息失败');
  }
}

// 提交分配
async function handleSubmit() {
  if (!props.skillId) return;

  submitLoading.value = true;
  try {
    // 获取当前选中的节点数据
    const checkedNodesData = treeRef.value?.getCheckedNodes(false, false) || [];

    // 找出角色节点（非群组节点）
    const newAssignments: { jid: string; profileId: string }[] = [];
    for (const node of checkedNodesData as any[]) {
      if (!node.isGroup && node.jid && node.profileId) {
        newAssignments.push({
          jid: node.jid,
          profileId: node.profileId,
        });
      }
    }

    // 计算需要添加和移除的分配
    const oldAssignments = currentAssignments.value.map(
      (item) => `${item.jid}_${item.profile_id}`,
    );
    const newAssignmentKeys = newAssignments.map(
      (item) => `${item.jid}_${item.profileId}`,
    );

    const toAdd = newAssignments.filter(
      (item) => !oldAssignments.includes(`${item.jid}_${item.profileId}`),
    );
    const toRemove = currentAssignments.value.filter(
      (item) => !newAssignmentKeys.includes(`${item.jid}_${item.profile_id}`),
    );

    // 执行添加操作
    for (const item of toAdd) {
      await assignSkillToProfileApi(props.skillId, {
        jid: item.jid,
        profile_id: item.profileId,
      });
    }

    // 执行移除操作
    for (const item of toRemove) {
      await removeSkillFromProfileApi(props.skillId, {
        jid: item.jid,
        profile_id: item.profile_id,
      });
    }

    ElMessage.success('分配更新成功');
    emit('success');
  } catch (error: any) {
    const msg = error?.response?.data?.detail || '操作失败';
    ElMessage.error(msg);
  } finally {
    submitLoading.value = false;
  }
}

// 关闭弹窗
function handleClose() {
  emit('update:visible', false);
}

// 初始化
onMounted(() => {
  // 数据会在 visible 变化时加载
});
</script>

<template>
  <ElDialog
    :model-value="props.visible"
    :title="`分配 Skill - ${props.skillName}`"
    width="500px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:visible', $event)"
    @close="handleClose"
  >
    <div v-loading="loading" class="assign-dialog-content">
      <div class="assign-tip">
        选择要分配此 Skill 的群组和角色组合：
      </div>
      <ElTree
        ref="treeRef"
        :data="treeData"
        show-checkbox
        node-key="id"
        :props="{
          children: 'children',
          label: 'label',
        }"
        default-expand-all
        check-strictly
        class="assign-tree"
      />
      <div class="assign-info">
        <div>当前已分配 {{ currentAssignments.length }} 个位置</div>
      </div>
    </div>

    <template #footer>
      <ElButton @click="handleClose">取消</ElButton>
      <ElButton type="primary" :loading="submitLoading" @click="handleSubmit">
        保存
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.assign-dialog-content {
  min-height: 300px;
}

.assign-tip {
  margin-bottom: 16px;
  color: #666;
}

.assign-tree {
  max-height: 400px;
  overflow-y: auto;
}

.assign-info {
  margin-top: 16px;
  padding: 8px 12px;
  font-size: 12px;
  color: #999;
  background: #f5f5f5;
  border-radius: 4px;
}
</style>