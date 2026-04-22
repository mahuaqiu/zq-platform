import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/device-debug/:deviceId',
    name: 'DeviceDebug',
    component: () => import('#/views/device-debug/index.vue'),
    meta: {
      title: '设备调试',
      hideInMenu: true,
    },
  },
];

export default routes;