<script setup lang="ts">
import { ref } from 'vue';

import { Page } from '@vben/common-ui';

import FilterBar, { type ProgressFilterParams } from './components/FilterBar.vue';
import StatsCards from './components/StatsCards.vue';
import FeatureTable from './components/FeatureTable.vue';

defineOptions({ name: 'FeatureProgress' });

const filterParams = ref<ProgressFilterParams>({});
</script>

<template>
  <Page auto-content-height>
    <div class="feature-page">
      <!-- 筛选区域 -->
      <FilterBar v-model="filterParams" />

      <!-- 统计卡片区域 -->
      <StatsCards :version="filterParams.version" />

      <!-- 数据表格区域 -->
      <div class="table-wrapper">
        <FeatureTable :filter-params="filterParams" />
      </div>
    </div>
  </Page>
</template>

<style scoped>
.feature-page {
  height: 100%;
  padding: 16px;
  overflow-y: auto;
}

.table-wrapper {
  margin-top: 16px;
}
</style>