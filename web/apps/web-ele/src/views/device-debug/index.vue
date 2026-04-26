<script lang="ts" setup>
import { onMounted, onUnmounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { ElMessage } from 'element-plus';
import { useTabs } from '@vben/hooks';

import { getEnvMachineDetailApi } from '#/api/core/env-machine';

import { isDesktopDevice, isMobileDevice, formatDeviceDebugTitle } from './utils';
import { useWebSocket } from './hooks/useWebSocket';
import { useScreenInteraction } from './hooks/useScreenInteraction';
import { useDeviceAction } from './hooks/useDeviceAction';

import TopNavbar from './components/TopNavbar.vue';
import ScreenDisplay from './components/ScreenDisplay.vue';
import MobilePanel from './components/MobilePanel.vue';
import KeyPressDialog from './components/KeyPressDialog.vue';
import InputTextDialog from './components/InputTextDialog.vue';
import InstallAppDialog from './components/InstallAppDialog.vue';

const route = useRoute();
const router = useRouter();
const { setTabTitle } = useTabs();

const deviceId = route.params.deviceId as string;

// 设备详情
const deviceDetail = ref<any>(null);
const loading = ref(true);

// 导航栏固定状态
const navbarFixed = ref(false);

// WebSocket
const {
  status: wsStatus,
  screenshotBase64,
  screenSize,
  fps,
  connect,
  disconnect,
  reconnect,
  resetActivityTime,
} = useWebSocket();

// 屏幕交互
const {
  mouseCoord,
  isInScreen,
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
  rightClick,
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

// 屏幕选择
const currentScreenIndex = ref(0);
const screenCount = computed(() => {
  if (!deviceDetail.value || !isDesktop.value) return 1;
  const extra = deviceDetail.value.extra_message;
  // 从设备扩展信息获取屏幕数量
  if (extra?.screen_count) return extra.screen_count;
  if (extra?.monitor_count) return extra.monitor_count;
  // 桌面端设备默认支持多屏幕选择（显示2个选项）
  return 2;
});

// 设备类型判断
const isDesktop = computed(() => deviceDetail.value && isDesktopDevice(deviceDetail.value.device_type));
const isMobile = computed(() => deviceDetail.value && isMobileDevice(deviceDetail.value.device_type));

// 设备分辨率显示
const deviceResolution = computed(() => {
  if (!deviceDetail.value) return '';
  // 优先使用 WebSocket 获取的屏幕尺寸
  if (screenSize.value.width && screenSize.value.height) {
    return `${screenSize.value.width}×${screenSize.value.height}`;
  }
  // 其次使用 extra_message 中的分辨率
  const extra = deviceDetail.value.extra_message;
  if (extra) {
    if (extra.resolution) return extra.resolution;
    if (extra.screen_width && extra.screen_height) {
      return `${extra.screen_width}×${extra.screen_height}`;
    }
  }
  return '';
});

// 加载设备详情
async function loadDeviceDetail() {
  try {
    loading.value = true;
    const result = await getEnvMachineDetailApi(deviceId);
    deviceDetail.value = result;

    // 设置 Tab 标题
    const title = formatDeviceDebugTitle(
      result.ip || '',
      result.device_sn || '',
      result.device_type
    );
    setTabTitle(title);

    // 连接 WebSocket（使用现有字段：ip、port、device_sn、device_type）
    const workerHost = result.ip;
    const workerPort = parseInt(result.port, 10);
    const udid = result.device_sn; // 移动设备 udid = device_sn
    const deviceType = result.device_type;

    if (workerHost && workerPort && deviceType) {
      connect(workerHost, workerPort, udid || '', deviceType, currentScreenIndex.value);
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
  if (deviceDetail.value?.ip && deviceDetail.value?.port && deviceDetail.value?.device_type) {
    const workerHost = deviceDetail.value.ip;
    const workerPort = parseInt(deviceDetail.value.port, 10);
    const udid = deviceDetail.value.device_sn || '';
    const deviceType = deviceDetail.value.device_type;
    reconnect(workerHost, workerPort, udid, deviceType, currentScreenIndex.value);
  }
}

// 屏幕切换
function handleScreenChange(screenIndex: number) {
  currentScreenIndex.value = screenIndex;
  // 重连 WebSocket 到新屏幕
  if (deviceDetail.value?.ip && deviceDetail.value?.port && deviceDetail.value?.device_type) {
    reconnect(
      deviceDetail.value.ip,
      parseInt(deviceDetail.value.port, 10),
      deviceDetail.value.device_sn || '',
      deviceDetail.value.device_type,
      screenIndex
    );
  }
}

// 屏幕交互事件处理
function handleScreenMouseDown(event: MouseEvent) {
  if (isOperating.value || wsStatus.value !== 'connected') return;
  // 如果点击在屏幕之外，返回 null，不开始操作
  const coords = handleDragStart(event);
  if (coords === null) {
    // 点击在屏幕之外，不做任何操作
  }
}

function handleScreenMouseMove(event: MouseEvent) {
  handleDragMove(event);
}

async function handleScreenMouseUp(event: MouseEvent) {
  if (isOperating.value) return;
  // 重置活动时间（用户有操作）
  resetActivityTime();
  const result = handleDragEnd(event);
  if (result) {
    // 桌面端设备传递 monitor 参数（从 1 开始：1=主屏幕，2=副屏幕）
    const monitor = isDesktop.value ? currentScreenIndex.value + 1 : undefined;
    if (result.type === 'click') {
      const clickParams = result.params as { x: number; y: number };
      const success = await click(clickParams.x, clickParams.y, monitor);
      if (success) clickCount.value++;
    } else if (result.type === 'swipe') {
      const swipeParams = result.params as { from_x: number; from_y: number; to_x: number; to_y: number; duration: number };
      const success = await swipe(
        swipeParams.from_x,
        swipeParams.from_y,
        swipeParams.to_x,
        swipeParams.to_y,
        swipeParams.duration,
        monitor
      );
      if (success) swipeCount.value++;
    }
  }
}

function handleScreenMouseLeave() {
  handleMouseLeave();
}

// 右键菜单处理：Windows/Mac 透传右键，iOS/Android 忽略
// 同样需要检查点击是否在屏幕区域内
async function handleScreenContextMenu(event: MouseEvent) {
  if (isOperating.value || wsStatus.value !== 'connected') return;

  // iOS/Android 不支持右键，忽略
  if (isMobile.value) return;

  // Windows/Mac 透传右键点击到设备
  if (isDesktop.value) {
    const img = event.target as HTMLImageElement;
    const rect = img.getBoundingClientRect();

    // 防止图片尚未加载完成
    if (img.naturalWidth === 0 || img.naturalHeight === 0) {
      return;
    }

    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    // 计算 object-fit: contain 的实际渲染区域
    const { convertToDeviceCoords, calculateContainRenderArea } = await import('./utils');
    const renderInfo = calculateContainRenderArea(
      rect.width,
      rect.height,
      img.naturalWidth,
      img.naturalHeight,
      mouseX,
      mouseY
    );

    // 如果点击不在屏幕区域内，不发送操作
    if (!renderInfo.isValidClick) {
      return;
    }

    // 转换为设备坐标（使用实际渲染尺寸）
    const coords = convertToDeviceCoords(
      renderInfo.adjustedX,
      renderInfo.adjustedY,
      renderInfo.renderedWidth,
      renderInfo.renderedHeight,
      screenSize.value.width || img.naturalWidth,
      screenSize.value.height || img.naturalHeight
    );

    // 发送右键点击（桌面端传递 monitor 参数）
    const monitor = currentScreenIndex.value + 1;
    await rightClick(coords.x, coords.y, monitor);
    clickCount.value++;
  }
}

// 按键操作
function handleKeyPress(key: string) {
  resetActivityTime();
  pressKey(key);
}

// 输入文本
function handleInputText(text: string) {
  resetActivityTime();
  inputText(text);
}

// 解锁屏幕
function handleUnlock(password?: string) {
  resetActivityTime();
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

// 监听页面滚动
function handlePageScroll() {
  navbarFixed.value = window.scrollY > 56;
}

onMounted(() => {
  loadDeviceDetail();
  window.addEventListener('scroll', handlePageScroll, { passive: true });
});

onUnmounted(() => {
  window.removeEventListener('scroll', handlePageScroll);
});
</script>

<template>
  <div class="device-debug-page">
    <!-- 顶部导航栏 -->
    <TopNavbar
      v-if="deviceDetail"
      :device-type="deviceDetail.device_type"
      :asset-number="deviceDetail.asset_number || deviceDetail.ip"
      :device-sn="deviceDetail.device_sn"
      :resolution="deviceResolution"
      :ws-status="wsStatus"
      :fps="fps"
      :screen-count="screenCount"
      :current-screen="currentScreenIndex"
      :mouse-coord="mouseCoord"
      :navbar-fixed="navbarFixed"
      @back="handleBack"
      @disconnect="handleDisconnect"
      @reconnect="handleReconnect"
      @keypress="handleOpenKeyPressDialog"
      @input="handleOpenInputDialog"
      @install="handleOpenInstallDialog"
      @screenshot="handleScreenshot"
      @screen-change="handleScreenChange"
    />

    <!-- 主内容区 -->
    <div class="debug-content" :class="{ 'content-padded': navbarFixed }">
      <!-- 桌面端布局：单屏幕展示 -->
      <template v-if="isDesktop">
        <ScreenDisplay
          :screenshot-url="screenshotBase64"
          :screen-size="screenSize"
          :ws-status="wsStatus"
          :mouse-coord="mouseCoord"
          :is-in-screen="isInScreen"
          :click-indicator="clickIndicator"
          :is-dragging="isDragging"
          :drag-start="dragStart"
          :drag-end="dragEnd"
          @mousedown="handleScreenMouseDown"
          @mousemove="handleScreenMouseMove"
          @mouseup="handleScreenMouseUp"
          @mouseleave="handleScreenMouseLeave"
          @contextmenu="handleScreenContextMenu"
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
              :is-in-screen="isInScreen"
              :click-indicator="clickIndicator"
              :is-dragging="isDragging"
              :drag-start="dragStart"
              :drag-end="dragEnd"
              @mousedown="handleScreenMouseDown"
              @mousemove="handleScreenMouseMove"
              @mouseup="handleScreenMouseUp"
              @mouseleave="handleScreenMouseLeave"
              @contextmenu="handleScreenContextMenu"
            />
          </div>
          <div class="mobile-right">
            <MobilePanel
              :operation-history="operationHistory"
              :udid="deviceDetail?.device_sn"
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
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.debug-content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  background: #f0f2f5;
  overflow: visible;
  min-height: 0;
}

.debug-content.content-padded {
  padding-top: 56px;
}

/* 桌面端布局 - ScreenDisplay直接在debug-content内，已居中 */
.debug-content > :not(.mobile-layout) {
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* 移动端布局 - 屏幕+面板整体居中 */
.mobile-layout {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  height: 100%;
  width: 100%;
  min-height: 0;
}

.mobile-screen {
  width: 380px;
  height: 100%;
  max-height: 720px;
  flex-shrink: 0;
  overflow: hidden;
  position: relative;
}

/* 移动端屏幕内部样式覆盖 - 直角无边框 */
.mobile-screen :deep(.screen-display) {
  padding: 0;
  background: #fff;
  border-radius: 0;
  box-shadow: none;
}

.mobile-screen :deep(.screen-card) {
  width: 100%;
  height: 100%;
  border-radius: 0;
  box-shadow: none;
}

.mobile-screen :deep(.screen-wrapper) {
  border-radius: 0;
}

.mobile-screen :deep(.coord-display) {
  top: 12px;
  left: 12px;
  right: auto;
  bottom: auto;
  font-size: 11px;
  padding: 4px 10px;
  background: rgba(0, 0, 0, 0.6);
}

.mobile-right {
  flex: 1;
  max-width: 400px;
  height: 100%;
}
</style>