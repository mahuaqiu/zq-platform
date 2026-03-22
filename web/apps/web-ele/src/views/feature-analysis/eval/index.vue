<script setup lang="ts">
import { ref } from 'vue';

import { Page } from '@vben/common-ui';

import FilterBar, { type FilterParams } from './components/FilterBar.vue';
import QualityTable from './components/QualityTable.vue';

defineOptions({ name: 'FeatureQualityEval' });

const filterParams = ref<FilterParams>({});
</script>

<template>
  <Page auto-content-height>
    <div class="feature-quality-eval p-4">
      <!-- 筛选区域 -->
      <FilterBar v-model="filterParams" />

      <!-- 数据表格区域 -->
      <div class="mt-4">
        <QualityTable :filter-params="filterParams" />
      </div>
    </div>
  </Page>
</template>

<style scoped>
.feature-quality-eval {
  height: 100%;
  overflow-y: auto;
}
</style>