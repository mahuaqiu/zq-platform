import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/device-files-window/:deviceId',
    name: 'DeviceFilesWindow',
    component: () => import('#/views/device-files/index.vue'),
    meta: {
      title: '文件管理',
      hideInMenu: true,
      hideInTab: true,
      noBasicLayout: true,
    },
  },
];

export default routes;
