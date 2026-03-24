<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElSelect, ElOption, ElInput } from 'element-plus';

import {
  getIssuesVersionsApi,
  getIssuesOwnersApi,
  getIssuesSeveritiesApi,
} from '#/api/core/issues-analysis';

defineOptions({ name: 'BugIntroFilterBar' });

export interface FilterParams {
  version?: string;
  featureDesc?: string;
  issuesOwner?: string;
  issuesSeverity?: string;
}

const props = defineProps<{
  modelValue: FilterParams;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: FilterParams];
}>();

const versions = ref<string[]>([]);
const owners = ref<string[]>([]);
const severities = ref<string[]>([]);
const loading = ref(false);

const localParams = ref<FilterParams>({ ...props.modelValue });

// 加载下拉选项
async function loadOptions() {
  loading.value = true;
  try {
    const [versionsRes, ownersRes, severitiesRes] = await Promise.all([
      getIssuesVersionsApi(),
      getIssuesOwnersApi(),
      getIssuesSeveritiesApi(),
    ]);
    versions.value = versionsRes.items || [];
    owners.value = ownersRes.items || [];
    severities.value = severitiesRes.items || [];
  } catch (error) {
    console.error('加载选项失败:', error);
  } finally {
    loading.value = false;
  }
}

// 更新筛选条件
function updateFilter(key: keyof FilterParams, value: string | undefined) {
  localParams.value = { ...localParams.value, [key]: value || undefined };
  emit('update:modelValue', localParams.value);
}

watch(
  () => props.modelValue,
  (val) => {
    localParams.value = { ...val };
  },
  { deep: true }
);

onMounted(() => {
  loadOptions();
});
</script>

<template>
  <div class="filter-bar flex flex-wrap items-center gap-4">
    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">版本：</span>
      <ElSelect
        v-model="localParams.version"
        placeholder="请选择版本"
        clearable
        :loading="loading"
        style="width: 180px"
        @change="(val: string | undefined) => updateFilter('version', val)"
      >
        <ElOption
          v-for="version in versions"
          :key="version"
          :label="version"
          :value="version"
        />
      </ElSelect>
    </div>

    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">需求标题：</span>
      <ElInput
        v-model="localParams.featureDesc"
        placeholder="请输入需求标题"
        clearable
        style="width: 180px"
        @blur="() => emit('update:modelValue', { ...localParams })"
        @clear="() => updateFilter('featureDesc', undefined)"
      />
    </div>

    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">责任人：</span>
      <ElSelect
        v-model="localParams.issuesOwner"
        placeholder="请选择责任人"
        clearable
        :loading="loading"
        style="width: 150px"
        @change="(val: string | undefined) => updateFilter('issuesOwner', val)"
      >
        <ElOption
          v-for="owner in owners"
          :key="owner"
          :label="owner"
          :value="owner"
        />
      </ElSelect>
    </div>

    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">严重程度：</span>
      <ElSelect
        v-model="localParams.issuesSeverity"
        placeholder="请选择严重程度"
        clearable
        :loading="loading"
        style="width: 150px"
        @change="(val: string | undefined) => updateFilter('issuesSeverity', val)"
      >
        <ElOption
          v-for="severity in severities"
          :key="severity"
          :label="severity"
          :value="severity"
        />
      </ElSelect>
    </div>
  </div>
</template>

<style scoped>
.filter-bar {
  padding: 12px 0;
}
</style>