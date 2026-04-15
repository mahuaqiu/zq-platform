import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/env-machine/list',
    name: 'EnvMachineList',
    component: () => import('#/views/env-machine/list.vue'),
    meta: {
      title: '设备列表',
      hideInMenu: true, // 菜单从后端获取，前端只定义组件映射
    },
  },
];

export default routes;