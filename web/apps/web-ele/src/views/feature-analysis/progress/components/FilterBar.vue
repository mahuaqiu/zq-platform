<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElSelect, ElOption } from 'element-plus';

import { getVersionListApi } from '#/api/core/feature-analysis';

defineOptions({ name: 'FilterBar' });

const props = defineProps<{
  modelValue?: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: string | undefined];
}>();

const versions = ref<string[]>([]);
const selectedVersion = ref<string | undefined>(props.modelValue);
const loading = ref(false);

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

// 版本变更
function handleVersionChange(value: string | undefined) {
  emit('update:modelValue', value);
}

watch(
  () => props.modelValue,
  (val) => {
    selectedVersion.value = val;
  }
);

onMounted(() => {
  loadVersions();
});
</script>

<template>
  <div class="filter-bar flex items-center gap-4">
    <span class="text-sm text-gray-600">版本：</span>
    <ElSelect
      v-model="selectedVersion"
      placeholder="请选择版本"
      clearable
      :loading="loading"
      style="width: 200px"
      @change="handleVersionChange"
    >
      <ElOption
        v-for="version in versions"
        :key="version"
        :label="version"
        :value="version"
      />
    </ElSelect>
  </div>
</template>

<style scoped>
.filter-bar {
  padding: 12px 0;
}
</style>