<script setup lang="ts">
interface ProcessInfo {
  versionName: string;
  versionColor: string;
  processName: string;
  pid: number;
  currentValue: number;
  unit: string;
}

defineProps<{
  processData: ProcessInfo[];
}>();
</script>

<template>
  <div class="version-process-panel">
    <div class="title">版本进程详情（悬停显示）</div>
    <div class="process-list">
      <div
        v-for="item in processData"
        :key="item.versionName"
        class="process-card"
        :style="{ borderLeftColor: item.versionColor }"
      >
        <div class="version-name" :style="{ color: item.versionColor }">
          {{ item.versionName }}
        </div>
        <div class="process-detail">
          {{ item.processName }} PID:{{ item.pid }} {{ item.currentValue.toFixed(1) }}{{ item.unit }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.version-process-panel {
  width: 280px;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
}

.title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #333;
}

.process-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.process-card {
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  border-left: 3px solid #409eff;
}

.version-name {
  font-weight: 600;
  font-size: 12px;
}

.process-detail {
  color: #666;
  font-size: 10px;
  margin-top: 4px;
}
</style>