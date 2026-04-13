import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/env-machine/upgrade',
    name: 'EnvMachineUpgrade',
    component: () => import('#/views/env-machine/upgrade.vue'),
    meta: {
      title: '升级管理',
      hideInMenu: true, // 菜单从后端获取，前端只定义组件映射
    },
  },
];

export default routes;