import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/env-machine/upgrade',
    name: 'EnvMachineUpgrade',
    component: () => import('#/views/env-machine/upgrade.vue'),
    meta: {
      title: '升级管理',
      icon: 'ant-design:cloud-upload-outlined',
    },
  },
];

export default routes;