import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    name: 'SchedulerLog',
    path: '/scheduler/log',
    component: () => import('#/views/scheduler/log.vue'),
    meta: {
      hideInMenu: true,
      title: '执行日志',
    },
  },
];

export default routes;