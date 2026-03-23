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
    <div class="feature-bug-intro p-4">
      <!-- 筛选区域 -->
      <FilterBar v-model="filterParams" />

      <!-- 数据表格区域 -->
      <div class="mt-4">
        <IssuesTable :filter-params="filterParams" />
      </div>
    </div>
  </Page>
</template>

<style scoped>
.feature-bug-intro {
  height: 100%;
  overflow-y: auto;
}
</style>