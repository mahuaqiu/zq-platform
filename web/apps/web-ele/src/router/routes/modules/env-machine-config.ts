import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/env-machine/config',
    name: 'EnvMachineConfig',
    component: () => import('#/views/env-machine/config.vue'),
    meta: {
      title: '设备配置',
      hideInMenu: true, // 菜单从后端获取，前端只定义组件映射
    },
  },
];

export default routes;