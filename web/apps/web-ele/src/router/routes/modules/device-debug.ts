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
  {
    path: '/device-debug-window/:deviceId',
    name: 'DeviceDebugWindow',
    component: () => import('#/views/device-debug/index.vue'),
    meta: {
      title: '设备远程操作',
      hideInMenu: true,
      hideInTab: true,
      noBasicLayout: true,
    },
  },
];

export default routes;
