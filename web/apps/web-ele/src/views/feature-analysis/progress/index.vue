<script setup lang="ts">
import { ref } from 'vue';

import { Page } from '@vben/common-ui';

import FilterBar, { type ProgressFilterParams } from './components/FilterBar.vue';
import PieCharts from './components/PieCharts.vue';
import FeatureTable from './components/FeatureTable.vue';

defineOptions({ name: 'FeatureProgress' });

const filterParams = ref<ProgressFilterParams>({});
</script>

<template>
  <Page auto-content-height>
    <div class="feature-progress p-4">
      <!-- 筛选区域 -->
      <FilterBar v-model="filterParams" />

      <!-- 饼图区域 -->
      <PieCharts :version="filterParams.version" />

      <!-- 数据表格区域 -->
      <FeatureTable :filter-params="filterParams" />
    </div>
  </Page>
</template>

<style scoped>
.feature-progress {
  height: 100%;
  overflow-y: auto;
}
</style>