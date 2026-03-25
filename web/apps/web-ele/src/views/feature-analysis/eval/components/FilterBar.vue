<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElSelect, ElOption, ElInput, ElButton } from 'element-plus';

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

// 重置筛选条件
function handleReset() {
  localParams.value = {};
  emit('update:modelValue', {});
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
  <div class="filter-area">
    <div class="filter-item">
      <label class="filter-label">版本</label>
      <ElSelect
        v-model="localParams.version"
        placeholder="请选择"
        clearable
        :loading="loading"
        style="width: 150px"
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

    <div class="filter-item">
      <label class="filter-label">FE编号</label>
      <ElInput
        v-model="localParams.featureId"
        placeholder="请输入FE编号"
        clearable
        style="width: 150px"
        @blur="() => emit('update:modelValue', { ...localParams })"
        @clear="() => updateFilter('featureId', undefined)"
      />
    </div>

    <div class="filter-item">
      <label class="filter-label">FE名称</label>
      <ElInput
        v-model="localParams.featureDesc"
        placeholder="请输入FE名称"
        clearable
        style="width: 200px"
        @blur="() => emit('update:modelValue', { ...localParams })"
        @clear="() => updateFilter('featureDesc', undefined)"
      />
    </div>

    <div class="filter-buttons">
      <ElButton type="primary" @click="() => emit('update:modelValue', { ...localParams })">查询</ElButton>
      <ElButton @click="handleReset">重置</ElButton>
    </div>
  </div>
</template>

<style scoped>
.filter-area {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: #fafafa;
  border-radius: 4px;
  flex-wrap: wrap;
  align-items: flex-end;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.filter-label {
  font-size: 12px;
  color: #666;
}

.filter-buttons {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
</style>