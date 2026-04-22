<script lang="ts" setup>
import { onMounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { ElMessage } from 'element-plus';

import { getEnvMachineDetailApi } from '#/api/core/env-machine';

import { isDesktopDevice, isMobileDevice } from './utils';
import { useWebSocket } from './hooks/useWebSocket';
import { useScreenInteraction } from './hooks/useScreenInteraction';
import { useDeviceAction } from './hooks/useDeviceAction';

import TopNavbar from './components/TopNavbar.vue';
import BottomToolbar from './components/BottomToolbar.vue';
import ScreenDisplay from './components/ScreenDisplay.vue';
import MobilePanel from './components/MobilePanel.vue';
import KeyPressDialog from './components/KeyPressDialog.vue';
import InputTextDialog from './components/InputTextDialog.vue';
import InstallAppDialog from './components/InstallAppDialog.vue';

const route = useRoute();
const router = useRouter();

const deviceId = route.params.deviceId as string;

// 设备详情
const deviceDetail = ref<any>(null);
const loading = ref(true);

// WebSocket
const {
  status: wsStatus,
  screenshotBase64,
  screenSize,
  fps,
  connect,
  disconnect,
  reconnect,
} = useWebSocket();

// 屏幕交互
const {
  mouseCoord,
  clickIndicator,
  isDragging,
  dragStart,
  dragEnd,
  handleDragStart,
  handleDragMove,
  handleDragEnd,
  // handleMouseMove - 未使用，保留备用
  handleMouseLeave,
} = useScreenInteraction(screenSize);

// 设备操作
const {
  isOperating,
  operationHistory,
  click,
  swipe,
  inputText,
  pressKey,
  unlockScreen,
} = useDeviceAction(deviceId);

// 操作统计
const clickCount = ref(0);
const swipeCount = ref(0);

// 弹窗状态
const keyPressDialogVisible = ref(false);
const inputTextDialogVisible = ref(false);
const installAppDialogVisible = ref(false);

// 全屏状态
const isFullscreen = ref(false);

// 设备类型判断
const isDesktop = computed(() => deviceDetail.value && isDesktopDevice(deviceDetail.value.device_type));
const isMobile = computed(() => deviceDetail.value && isMobileDevice(deviceDetail.value.device_type));

// 加载设备详情
async function loadDeviceDetail() {
  try {
    loading.value = true;
    const result = await getEnvMachineDetailApi(deviceId);
    deviceDetail.value = result;

    // 连接 WebSocket
    if (result.worker_host && result.worker_port && result.udid) {
      connect(result.worker_host, result.worker_port, result.udid);
    } else {
      ElMessage.error('设备缺少 Worker 连接信息');
    }
  } catch (error: any) {
    ElMessage.error('获取设备详情失败: ' + error.message);
  } finally {
    loading.value = false;
  }
}

// 返回上一页
function handleBack() {
  disconnect();
  router.back();
}

// 断开连接
function handleDisconnect() {
  disconnect();
}

// 重新连接
function handleReconnect() {
  if (deviceDetail.value?.worker_host && deviceDetail.value?.worker_port && deviceDetail.value?.udid) {
    reconnect(deviceDetail.value.worker_host, deviceDetail.value.worker_port, deviceDetail.value.udid);
  }
}

// 全屏切换
function handleFullscreen() {
  isFullscreen.value = !isFullscreen.value;
  // 实际全屏切换逻辑可通过 document fullscreen API 实现
}

// 屏幕交互事件处理
function handleScreenMouseDown(event: MouseEvent) {
  if (isOperating.value || wsStatus.value !== 'connected') return;
  handleDragStart(event);
}

function handleScreenMouseMove(event: MouseEvent) {
  handleDragMove(event);
}

async function handleScreenMouseUp(event: MouseEvent) {
  if (isOperating.value) return;
  const result = handleDragEnd(event);
  if (result) {
    if (result.type === 'click') {
      const clickParams = result.params as { x: number; y: number };
      const success = await click(clickParams.x, clickParams.y);
      if (success) clickCount.value++;
    } else if (result.type === 'swipe') {
      const swipeParams = result.params as { from_x: number; from_y: number; to_x: number; to_y: number; duration: number };
      const success = await swipe(
        swipeParams.from_x,
        swipeParams.from_y,
        swipeParams.to_x,
        swipeParams.to_y
      );
      if (success) swipeCount.value++;
    }
  }
}

function handleScreenMouseLeave() {
  handleMouseLeave();
}

// 按键操作
function handleKeyPress(key: string) {
  pressKey(key);
}

// 输入文本
function handleInputText(text: string) {
  inputText(text);
}

// 解锁屏幕
function handleUnlock(password?: string) {
  unlockScreen(password);
}

// 安装 APP
function handleInstallApp(_file: File) {
  // TODO: 实现上传安装逻辑（后端 API 待实现）
  ElMessage.info('APP 安装功能待后端支持');
}

// 截图保存
function handleScreenshot() {
  if (screenshotBase64.value) {
    const link = document.createElement('a');
    link.href = screenshotBase64.value;
    link.download = `screenshot_${Date.now()}.png`;
    link.click();
  } else {
    ElMessage.warning('暂无截图可保存');
  }
}

// 打开按键弹窗
function handleOpenKeyPressDialog() {
  keyPressDialogVisible.value = true;
}

// 打开输入文本弹窗
function handleOpenInputDialog() {
  inputTextDialogVisible.value = true;
}

// 打开安装弹窗
function handleOpenInstallDialog() {
  installAppDialogVisible.value = true;
}

onMounted(() => {
  loadDeviceDetail();
});
</script>

<template>
  <div class="device-debug-page" :class="{ fullscreen: isFullscreen }">
    <!-- 顶部导航栏 -->
    <TopNavbar
      v-if="deviceDetail"
      :device-type="deviceDetail.device_type"
      :asset-number="deviceDetail.asset_number || deviceDetail.ip"
      :device-sn="deviceDetail.device_sn"
      :ws-status="wsStatus"
      :fps="fps"
      @back="handleBack"
      @disconnect="handleDisconnect"
      @reconnect="handleReconnect"
      @fullscreen="handleFullscreen"
    />

    <!-- 主内容区 -->
    <div class="debug-content">
      <!-- 桌面端布局：单屏幕展示 -->
      <template v-if="isDesktop">
        <ScreenDisplay
          :screenshot-url="screenshotBase64"
          :screen-size="screenSize"
          :ws-status="wsStatus"
          :mouse-coord="mouseCoord"
          :click-indicator="clickIndicator"
          :is-dragging="isDragging"
          :drag-start="dragStart"
          :drag-end="dragEnd"
          @mousedown="handleScreenMouseDown"
          @mousemove="handleScreenMouseMove"
          @mouseup="handleScreenMouseUp"
          @mouseleave="handleScreenMouseLeave"
        />
      </template>

      <!-- 移动端布局：左侧屏幕 + 右侧面板 -->
      <template v-if="isMobile">
        <div class="mobile-layout">
          <div class="mobile-screen">
            <ScreenDisplay
              :screenshot-url="screenshotBase64"
              :screen-size="screenSize"
              :ws-status="wsStatus"
              :mouse-coord="mouseCoord"
              :click-indicator="clickIndicator"
              :is-dragging="isDragging"
              :drag-start="dragStart"
              :drag-end="dragEnd"
              @mousedown="handleScreenMouseDown"
              @mousemove="handleScreenMouseMove"
              @mouseup="handleScreenMouseUp"
              @mouseleave="handleScreenMouseLeave"
            />
          </div>
          <div class="mobile-right">
            <MobilePanel
              :operation-history="operationHistory"
              :udid="deviceDetail?.udid"
              @keypress="handleKeyPress"
              @input="handleInputText"
              @unlock="handleUnlock"
              @install="handleOpenInstallDialog"
              @screenshot="handleScreenshot"
            />
          </div>
        </div>
      </template>
    </div>

    <!-- 底部工具栏（桌面端） -->
    <BottomToolbar
      v-if="isDesktop"
      :device-type="deviceDetail?.device_type"
      :operation-history="operationHistory"
      :click-count="clickCount"
      :swipe-count="swipeCount"
      @keypress="handleOpenKeyPressDialog"
      @input="handleOpenInputDialog"
      @install="handleOpenInstallDialog"
      @screenshot="handleScreenshot"
    />

    <!-- 弹窗组件 -->
    <KeyPressDialog
      v-model:visible="keyPressDialogVisible"
      :disabled="isOperating"
      :device-type="deviceDetail?.device_type"
      @press="handleKeyPress"
    />

    <InputTextDialog
      v-model:visible="inputTextDialogVisible"
      @send="handleInputText"
    />

    <InstallAppDialog
      v-model:visible="installAppDialogVisible"
      :device-type="deviceDetail?.device_type"
      @upload="handleInstallApp"
    />
  </div>
</template>

<style scoped>
.device-debug-page {
  background: #f0f2f5;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.device-debug-page.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 100;
}

.debug-content {
  flex: 1;
  display: flex;
  padding: 16px;
}

/* 桌面端布局 */
.debug-content:not(.mobile-layout) {
  height: calc(100vh - 112px); /* 56px navbar + 56px toolbar */
}

/* 移动端布局 */
.mobile-layout {
  display: flex;
  gap: 16px;
  height: 100%;
}

.mobile-screen {
  flex: 1;
  max-width: 340px;
  min-width: 300px;
}

.mobile-right {
  width: 280px;
  flex-shrink: 0;
}
</style>