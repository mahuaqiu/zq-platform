<script setup lang="ts">
import { ref } from 'vue';

import { Page } from '@vben/common-ui';

import FilterBar, { type FilterParams } from './components/FilterBar.vue';
import IssuesTable from './components/IssuesTable.vue';

defineOptions({ name: 'FeatureBugIntro' });

const filterParams = ref<FilterParams>({});
</script>

<template>
  <Page auto-content-height>
    <div class="feature-page">
      <!-- 筛选区域 -->
      <FilterBar v-model="filterParams" />

      <!-- 数据表格区域 -->
      <div class="table-wrapper">
        <IssuesTable :filter-params="filterParams" />
      </div>
    </div>
  </Page>
</template>

<style scoped>
.feature-page {
  height: 100%;
  overflow-y: auto;
  padding: 16px;
}

.table-wrapper {
  margin-top: 16px;
}
</style>