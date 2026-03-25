/**
 * 消息通知 Composable
 * 集成 WebSocket 实时推送、公告 API
 */
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';

import {
  getUnreadAnnouncementCountApi,
  getUserAnnouncementListApi,
  markAnnouncementReadApi,
} from '#/api/core/announcement';

// 公告项类型
export interface AnnouncementItem {
  id: string;
  title: string;
  summary: string;
  content: string;
  date: string;
  isRead: boolean;
  priority: number;
  isTop: boolean;
  publisherName: string;
}

// WebSocket 连接状态
const wsConnected = ref(false);
const wsInstance = ref<null | WebSocket>(null);

// 公告数据
const announcements = ref<AnnouncementItem[]>([]);
const announcementUnreadCount = ref(0);

// 当前激活的 Tab
const activeTab = ref<'announcement'>('announcement');

export function useNotification() {
  const router = useRouter();

  // 总未读数量
  const totalUnreadCount = computed(() => announcementUnreadCount.value);

  // 是否显示红点
  const showDot = computed(() => totalUnreadCount.value > 0);

  // 加载公告列表
  async function loadAnnouncements() {
    try {
      const res = await getUserAnnouncementListApi({ page: 1, pageSize: 10 });
      announcements.value = (res.items || []).map((item) => ({
        id: item.id,
        title: item.title,
        summary: item.summary,
        content: item.content,
        date: formatDate(item.publish_time || ''),
        isRead: item.is_read,
        priority: item.priority,
        isTop: item.is_top,
        publisherName: item.publisher_name,
      }));
    } catch (error) {
      console.error('加载公告失败:', error);
    }
  }

  // 加载公告未读数量
  async function loadAnnouncementUnreadCount() {
    try {
      const res = await getUnreadAnnouncementCountApi();
      announcementUnreadCount.value = res.count;
    } catch (error) {
      console.error('加载公告未读数量失败:', error);
    }
  }

  // 标记公告已读
  async function markAnnouncementAsRead(item: AnnouncementItem) {
    if (item.isRead) {
      viewAnnouncementDetail(item);
      return;
    }

    try {
      await markAnnouncementReadApi(item.id);
      item.isRead = true;
      announcementUnreadCount.value = Math.max(
        0,
        announcementUnreadCount.value - 1,
      );
      viewAnnouncementDetail(item);
    } catch (error) {
      console.error('标记公告已读失败:', error);
    }
  }

  // 查看公告详情
  function viewAnnouncementDetail(_item: AnnouncementItem) {
    // 跳转到公告列表页
    router.push(`/message/announcement-list`);
  }

  // 查看全部
  function viewAllMessages() {
    router.push('/message/announcement-list');
  }

  // 连接 WebSocket（保留接口，实际不做操作）
  function connectWebSocket() {
    wsConnected.value = false;
  }

  // 断开 WebSocket
  function disconnectWebSocket() {
    if (wsInstance.value) {
      wsInstance.value.close();
      wsInstance.value = null;
    }
  }

  // 格式化日期
  function formatDate(dateStr: string): string {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 60_000) return '刚刚';
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}分钟前`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}小时前`;
    if (diff < 604_800_000) return `${Math.floor(diff / 86_400_000)}天前`;

    return date.toLocaleDateString();
  }

  // 初始化
  function init() {
    loadAnnouncements();
    loadAnnouncementUnreadCount();
  }

  // 清理
  function cleanup() {
    disconnectWebSocket();
  }

  return {
    // 公告
    announcements,
    announcementUnreadCount,
    // 通用
    activeTab,
    totalUnreadCount,
    showDot,
    wsConnected,
    // 方法
    loadAnnouncements,
    loadAnnouncementUnreadCount,
    markAnnouncementAsRead,
    viewAllMessages,
    init,
    cleanup,
  };
}