import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/performance-monitor',
    name: 'PerformanceMonitor',
    component: () => import('#/views/performance-monitor/index.vue'),
    meta: {
      title: '性能监控',
      hideInMenu: true,
      keepAlive: false,
    },
  },
];

export default routes;