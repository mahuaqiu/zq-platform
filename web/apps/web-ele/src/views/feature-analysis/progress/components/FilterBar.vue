<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElSelect, ElOption, ElInput } from 'element-plus';

import { getVersionListApi, getOwnerListApi, getTaskServiceListApi } from '#/api/core/feature-analysis';

defineOptions({ name: 'FilterBar' });

export interface ProgressFilterParams {
  version?: string;
  featureIdFather?: string;
  featureId?: string;
  featureOwner?: string;
  featureTaskService?: string;
}

const props = defineProps<{
  modelValue: ProgressFilterParams;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: ProgressFilterParams];
}>();

const versions = ref<string[]>([]);
const owners = ref<string[]>([]);
const taskServices = ref<string[]>([]);
const loading = ref(false);

const localParams = ref<ProgressFilterParams>({ ...props.modelValue });

// 加载下拉选项数据
async function loadOptions() {
  loading.value = true;
  try {
    const [versionRes, ownerRes, taskServiceRes] = await Promise.all([
      getVersionListApi(),
      getOwnerListApi(),
      getTaskServiceListApi(),
    ]);
    versions.value = versionRes.items || [];
    owners.value = ownerRes.items || [];
    taskServices.value = taskServiceRes.items || [];
  } catch (error) {
    console.error('加载筛选选项失败:', error);
  } finally {
    loading.value = false;
  }
}

// 更新筛选条件
function updateFilter(key: keyof ProgressFilterParams, value: string | undefined) {
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
        style="width: 160px"
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
      <span class="text-sm text-gray-600">EP编号：</span>
      <ElInput
        v-model="localParams.featureIdFather"
        placeholder="请输入EP编号"
        clearable
        style="width: 150px"
        @blur="() => emit('update:modelValue', { ...localParams })"
        @clear="() => updateFilter('featureIdFather', undefined)"
      />
    </div>

    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">FE编号：</span>
      <ElInput
        v-model="localParams.featureId"
        placeholder="请输入FE编号"
        clearable
        style="width: 150px"
        @blur="() => emit('update:modelValue', { ...localParams })"
        @clear="() => updateFilter('featureId', undefined)"
      />
    </div>

    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">测试责任人：</span>
      <ElSelect
        v-model="localParams.featureOwner"
        placeholder="请选择"
        clearable
        filterable
        :loading="loading"
        style="width: 120px"
        @change="(val: string | undefined) => updateFilter('featureOwner', val)"
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
      <span class="text-sm text-gray-600">测试归属：</span>
      <ElSelect
        v-model="localParams.featureTaskService"
        placeholder="请选择"
        clearable
        filterable
        :loading="loading"
        style="width: 140px"
        @change="(val: string | undefined) => updateFilter('featureTaskService', val)"
      >
        <ElOption
          v-for="service in taskServices"
          :key="service"
          :label="service"
          :value="service"
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