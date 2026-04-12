import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/ai-assistant/role',
    name: 'AIAssistantRole',
    component: () => import('#/views/ai-assistant/role/index.vue'),
    meta: {
      title: '角色管理',
    },
  },
  {
    path: '/ai-assistant/session',
    name: 'AIAssistantSession',
    component: () => import('#/views/ai-assistant/session/index.vue'),
    meta: {
      title: '会话管理',
    },
  },
  {
    path: '/ai-assistant/session/:id',
    name: 'AIAssistantSessionDetail',
    component: () => import('#/views/ai-assistant/session/detail.vue'),
    meta: {
      title: '会话详情',
      hideInMenu: true,
    },
  },
  {
    path: '/ai-assistant/group',
    name: 'AIAssistantGroup',
    component: () => import('#/views/ai-assistant/group/index.vue'),
    meta: {
      title: '群组管理',
    },
  },
];

export default routes;