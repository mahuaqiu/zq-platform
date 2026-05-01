import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/performance-monitor/compare',
    name: 'PerformanceMonitorCompare',
    component: () => import('#/views/performance-monitor/compare.vue'),
    meta: {
      title: '版本对比',
      hideInMenu: true,
    },
  },
];

export default routes;