import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    name: 'DeviceMonitor',
    path: '/overview/device-monitor',
    component: () => import('#/views/device-monitor/index.vue'),
    meta: {
      hideInMenu: true,
      title: '设备监控',
    },
  },
];

export default routes;