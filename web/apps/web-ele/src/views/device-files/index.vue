<script setup lang="ts">
import type { EnvMachine } from '#/api/core/env-machine';

import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { ElButton, ElTag } from 'element-plus';

import { getEnvMachineDetailApi } from '#/api/core/env-machine';

import { getDeviceTypeText } from '../env-machine/modules/common';
import FileBrowser from './FileBrowser.vue';

defineOptions({ name: 'DeviceFilesWindow' });

const route = useRoute();
const router = useRouter();
const deviceId = route.params.deviceId as string;
const isRemotePopup = route.query.remotePopup === '1';

const machine = ref<EnvMachine | null>(null);
const loadFailed = ref(false);

const deviceName = computed(() => {
  const m = machine.value;
  if (!m) return '';
  // 与远程窗口标题惯例一致:桌面设备 "IP - SN"
  return m.ip ? `${m.ip}${m.device_sn ? ` - ${m.device_sn}` : ''}` : m.id;
});

const STATUS_TYPE: Record<string, 'danger' | 'info' | 'success' | 'warning'> = {
  online: 'success',
  using: 'warning',
  offline: 'info',
  upgrading: 'info',
};
const STATUS_LABEL: Record<string, string> = {
  online: '在线',
  using: '使用中',
  offline: '离线',
  upgrading: '升级中',
};

onMounted(async () => {
  try {
    machine.value = await getEnvMachineDetailApi(deviceId);
    document.title = `文件管理 — ${deviceName.value}`;
  } catch {
    // 全局拦截器已提示
    loadFailed.value = true;
  }
});

function handleClose() {
  window.close();
  // 非弹窗打开(window.close 无效)时兜底回列表
  setTimeout(() => {
    router.replace({ name: 'EnvMachineList' }).catch(() => {});
  }, 200);
}
</script>

<template>
  <div class="dfw-page">
    <div class="dfw-nav">
      <span class="dfw-device-icon">💻</span>
      <div v-if="machine" class="dfw-device-info">
        <div class="dfw-name">
          {{ machine.ip }}
          <span v-if="machine.device_sn" class="dfw-name-sub">
            - {{ machine.device_sn }}
          </span>
        </div>
        <div class="dfw-meta">
          {{ getDeviceTypeText(machine.device_type) }} · Worker
          {{ machine.version || '—' }}
        </div>
      </div>
      <div v-else-if="loadFailed" class="dfw-meta">设备信息加载失败</div>
      <ElTag
        v-if="machine && STATUS_LABEL[machine.status]"
        :type="STATUS_TYPE[machine.status] ?? 'info'"
        size="small"
      >
        {{ STATUS_LABEL[machine.status] }}
      </ElTag>
      <div class="dfw-spacer"></div>
      <ElButton v-if="isRemotePopup" size="small" @click="handleClose">
        关闭
      </ElButton>
    </div>
    <div class="dfw-body">
      <FileBrowser
        v-if="machine"
        :machine-id="machine.id"
        :ip="machine.ip || ''"
        :port="machine.port || ''"
      />
      <div v-else-if="!loadFailed" class="dfw-tip">正在加载设备信息…</div>
      <div v-else class="dfw-tip">
        设备信息加载失败,请关闭窗口后从设备列表重试
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 顶部导航:复用远程窗口 TopNavbar 风格(白底 56px + 设备身份) */
.dfw-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #fff;
}

.dfw-nav {
  display: flex;
  flex-shrink: 0;
  gap: 16px;
  align-items: center;
  height: 56px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.dfw-device-icon {
  font-size: 20px;
}

.dfw-device-info {
  min-width: 0;
}

.dfw-name {
  font-size: 16px;
  font-weight: 600;
  color: #111;
}

.dfw-name-sub {
  font-weight: 400;
  color: #666;
}

.dfw-meta {
  margin-top: 2px;
  font-size: 12px;
  color: #666;
}

.dfw-spacer {
  flex: 1;
}

.dfw-body {
  flex: 1;
  padding: 12px 24px 16px;
}

.dfw-tip {
  padding: 48px 0;
  font-size: 13px;
  color: #909399;
  text-align: center;
}
</style>
