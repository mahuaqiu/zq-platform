<script lang="ts" setup>
import type { AnnouncementItem } from '#/composables/useNotification';

import { computed } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { Bell } from '@vben/icons';

import { ElBadge } from 'element-plus';

import NotificationDrawer from './NotificationDrawer.vue';

interface Props {
  // 是否显示红点
  dot?: boolean;
  // 公告列表
  announcements?: AnnouncementItem[];
  // 公告未读数
  announcementUnreadCount?: number;
}

defineOptions({ name: 'NotificationPopup' });

const props = withDefaults(defineProps<Props>(), {
  dot: false,
  announcements: () => [],
  announcementUnreadCount: 0,
});

const emit = defineEmits<{
  readAnnouncement: [AnnouncementItem];
  viewAll: [];
}>();

// 使用 Drawer
const [Drawer, drawerApi] = useVbenDrawer({
  connectedComponent: NotificationDrawer,
});

// 传递给 Drawer 的属性
const drawerAttrs = computed(() => ({
  announcements: props.announcements,
  announcementUnreadCount: props.announcementUnreadCount,
}));

// 传递给 Drawer 的事件
const drawerListeners = {
  readAnnouncement: (item: AnnouncementItem) => emit('readAnnouncement', item),
  viewAll: () => {
    emit('viewAll');
    drawerApi.close();
  },
};

function openDrawer() {
  drawerApi.open();
}
</script>

<template>
  <div>
    <Drawer v-bind="drawerAttrs" v-on="drawerListeners" />

    <div class="notification-trigger" @click="openDrawer">
      <ElBadge :is-dot="dot" :hidden="!dot">
        <Bell
          class="size-5 cursor-pointer text-[var(--el-text-color-regular)] hover:text-[var(--el-color-primary)]"
        />
      </ElBadge>
    </div>
  </div>
</template>

<style scoped>
.notification-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  margin-right: 8px;
}
</style>