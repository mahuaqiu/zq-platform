<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElSelect, ElOption, ElInput } from 'element-plus';

import { getVersionListApi } from '#/api/core/feature-analysis';

defineOptions({ name: 'EvalFilterBar' });

export interface FilterParams {
  version?: string;
  featureId?: string;
  featureDesc?: string;
}

const props = defineProps<{
  modelValue: FilterParams;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: FilterParams];
}>();

const versions = ref<string[]>([]);
const loading = ref(false);

const localParams = ref<FilterParams>({ ...props.modelValue });

// 加载版本列表
async function loadVersions() {
  loading.value = true;
  try {
    const res = await getVersionListApi();
    versions.value = res.items || [];
  } catch (error) {
    console.error('加载版本列表失败:', error);
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
  loadVersions();
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
      <span class="text-sm text-gray-600">FE编号：</span>
      <ElInput
        v-model="localParams.featureId"
        placeholder="请输入FE编号"
        clearable
        style="width: 180px"
        @blur="() => emit('update:modelValue', { ...localParams })"
        @clear="() => updateFilter('featureId', undefined)"
      />
    </div>

    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-600">FE名称：</span>
      <ElInput
        v-model="localParams.featureDesc"
        placeholder="请输入FE名称"
        clearable
        style="width: 200px"
        @blur="() => emit('update:modelValue', { ...localParams })"
        @clear="() => updateFilter('featureDesc', undefined)"
      />
    </div>
  </div>
</template>

<style scoped>
.filter-bar {
  padding: 12px 0;
}
</style>