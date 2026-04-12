import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/ai-assistant',
    name: 'AIAssistant',
    component: () => import('#/layouts/default/index.vue'),
    redirect: '/ai-assistant/session',
    children: [
      {
        path: 'session',
        name: 'AIAssistantSession',
        component: () => import('#/views/ai-assistant/session/index.vue'),
        meta: {
          title: '会话管理',
        },
      },
      {
        path: 'session/:id',
        name: 'AIAssistantSessionDetail',
        component: () => import('#/views/ai-assistant/session/detail.vue'),
        meta: {
          title: '会话详情',
          hideInMenu: true,
        },
      },
      {
        path: 'group',
        name: 'AIAssistantGroup',
        component: () => import('#/views/ai-assistant/group/index.vue'),
        meta: {
          title: '群组管理',
        },
      },
    ],
  },
];

export default routes;