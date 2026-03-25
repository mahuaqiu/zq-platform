<script lang="ts" setup>
import type { AnnouncementItem } from '#/composables/useNotification';

import { computed } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { Megaphone } from '@vben/icons';

import { ElButton, ElEmpty, ElScrollbar, ElTooltip } from 'element-plus';

interface Props {
  // 公告列表
  announcements?: AnnouncementItem[];
  // 公告未读数
  announcementUnreadCount?: number;
}

defineOptions({ name: 'NotificationDrawer' });

const props = withDefaults(defineProps<Props>(), {
  announcements: () => [],
  announcementUnreadCount: 0,
});

const emit = defineEmits<{
  readAnnouncement: [AnnouncementItem];
  viewAll: [];
}>();

const [Drawer] = useVbenDrawer();

const announcementTabLabel = computed(
  () =>
    `公告 ${props.announcementUnreadCount > 0 ? `(${props.announcementUnreadCount})` : ''}`,
);

function handleViewAll() {
  emit('viewAll');
}

function handleAnnouncementClick(item: AnnouncementItem) {
  emit('readAnnouncement', item);
}

// 优先级样式
function getPriorityClass(priority: number): string {
  if (priority === 2) return 'border-l-4 border-l-red-500';
  if (priority === 1) return 'border-l-4 border-l-orange-500';
  return '';
}
</script>

<template>
  <div>
    <Drawer title="公告中心" class="sm:max-w-md" :footer="false">
      <template #extra>
        <ElTooltip content="查看全部" placement="bottom">
          <ElButton link @click="handleViewAll">
            <span class="text-xs">全部</span>
          </ElButton>
        </ElTooltip>
      </template>

      <div class="flex h-full flex-col">
        <!-- Tab 标题 -->
        <div class="mb-4 text-sm font-medium text-[var(--el-text-color-primary)]">
          {{ announcementTabLabel }}
        </div>

        <!-- 公告列表 -->
        <ElScrollbar v-if="announcements.length > 0" class="flex-1">
          <ul class="flex w-full flex-col gap-2">
            <template v-for="item in announcements" :key="item.id">
              <li
                class="relative flex w-full cursor-pointer flex-col gap-2 rounded-lg border border-[var(--el-border-color)] p-3 transition-colors hover:bg-[var(--el-fill-color-light)]"
                :class="getPriorityClass(item.priority)"
                @click="handleAnnouncementClick(item)"
              >
                <span
                  v-if="!item.isRead"
                  class="absolute right-2 top-2 h-2 w-2 rounded-full bg-[var(--el-color-danger)]"
                ></span>

                <div class="flex items-center gap-2">
                  <span
                    v-if="item.isTop"
                    class="rounded bg-[var(--el-color-danger)] px-1.5 py-0.5 text-xs text-white"
                  >
                    置顶
                  </span>
                  <span
                    v-if="item.priority === 2"
                    class="rounded bg-[var(--el-color-danger)] px-1.5 py-0.5 text-xs text-white"
                  >
                    紧急
                  </span>
                  <span
                    v-else-if="item.priority === 1"
                    class="rounded bg-[var(--el-color-warning)] px-1.5 py-0.5 text-xs text-white"
                  >
                    重要
                  </span>
                  <p class="flex-1 truncate text-sm font-medium">
                    {{ item.title }}
                  </p>
                </div>
                <p
                  class="line-clamp-2 text-xs text-[var(--el-text-color-secondary)]"
                >
                  {{ item.summary || item.content }}
                </p>
                <div
                  class="flex items-center justify-between text-xs text-[var(--el-text-color-placeholder)]"
                >
                  <span>{{ item.publisherName }}</span>
                  <span>{{ item.date }}</span>
                </div>
              </li>
            </template>
          </ul>
        </ElScrollbar>

        <template v-else>
          <div class="flex flex-1 items-center justify-center">
            <ElEmpty description="暂无公告">
              <template #image>
                <Megaphone
                  class="size-16 text-[var(--el-text-color-placeholder)]"
                />
              </template>
            </ElEmpty>
          </div>
        </template>
      </div>
    </Drawer>
  </div>
</template>