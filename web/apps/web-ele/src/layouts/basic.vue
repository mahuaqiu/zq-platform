<script lang="ts" setup>
import { computed, onMounted, onUnmounted, watch } from 'vue';

import { AuthenticationLoginExpiredModal } from '@vben/common-ui';
import { VBEN_DOC_URL, VBEN_GITHUB_URL } from '@vben/constants';
import { useWatermark } from '@vben/hooks';
import { BookOpenText, CircleHelp, SvgGithubIcon } from '@vben/icons';
import { BasicLayout, LockScreen, UserDropdown } from '@vben/layouts';
import { preferences } from '@vben/preferences';
import { useAccessStore, useUserStore } from '@vben/stores';
import { openWindow } from '@vben/utils';

import NotificationPopup from '#/components/notification/NotificationPopup.vue';
import { useNotification } from '#/composables/useNotification';
import { $t } from '#/locales';
import { useAuthStore } from '#/store';
import LoginForm from '#/views/_core/authentication/login.vue';

// 使用消息通知 composable
const {
  announcements,
  announcementUnreadCount,
  showDot,
  markAnnouncementAsRead,
  viewAllMessages,
  init: initNotification,
  cleanup: cleanupNotification,
} = useNotification();

const userStore = useUserStore();
const authStore = useAuthStore();
const accessStore = useAccessStore();
const { destroyWatermark, updateWatermark } = useWatermark();

// 初始化消息通知
onMounted(() => {
  initNotification();
});

onUnmounted(() => {
  cleanupNotification();
});

const menus = computed(() => [
  {
    handler: () => {
      openWindow(VBEN_DOC_URL, {
        target: '_blank',
      });
    },
    icon: BookOpenText,
    text: $t('ui.widgets.document'),
  },
  {
    handler: () => {
      openWindow(VBEN_GITHUB_URL, {
        target: '_blank',
      });
    },
    icon: SvgGithubIcon,
    text: 'GitHub',
  },
  {
    handler: () => {
      openWindow(`${VBEN_GITHUB_URL}/issues`, {
        target: '_blank',
      });
    },
    icon: CircleHelp,
    text: $t('ui.widgets.qa'),
  },
]);

const avatar = computed(() => {
  const avatarPath = userStore.userInfo?.avatar;
  if (avatarPath) {
    // 直接使用头像路径
    return avatarPath;
  }
  return preferences.app.defaultAvatar;
});

async function handleLogout() {
  await authStore.logout(false);
}

function handleAnnouncementRead(item: any) {
  markAnnouncementAsRead(item);
}

function handleViewAll() {
  viewAllMessages();
}

watch(
  () => ({
    enable: preferences.app.watermark,
    content: preferences.app.watermarkContent,
  }),
  async ({ enable, content }) => {
    if (enable) {
      await updateWatermark({
        content:
          content ||
          `${userStore.userInfo?.username} - ${userStore.userInfo?.realName}`,
      });
    } else {
      destroyWatermark();
    }
  },
  {
    immediate: true,
  },
);
</script>

<template>
  <BasicLayout @clear-preferences-and-logout="handleLogout">
    <template #user-dropdown>
      <UserDropdown
        :avatar
        :menus
        :text="userStore.userInfo?.realName"
        description="jiangzhikj@outlook.com"
        tag-text="Pro"
        @logout="handleLogout"
      />
    </template>
    <template #notification>
      <NotificationPopup
        :dot="showDot"
        :announcements="announcements"
        :announcement-unread-count="announcementUnreadCount"
        @read-announcement="handleAnnouncementRead"
        @view-all="handleViewAll"
      />
    </template>
    <template #extra>
      <AuthenticationLoginExpiredModal
        v-model:open="accessStore.loginExpired"
        :avatar
      >
        <LoginForm />
      </AuthenticationLoginExpiredModal>
    </template>
    <template #lock-screen>
      <LockScreen :avatar @to-login="handleLogout" />
    </template>
  </BasicLayout>
</template>