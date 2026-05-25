import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/env-machine/list',
    name: 'EnvMachineList',
    component: () => import('#/views/env-machine/list.vue'),
    meta: {
      title: '设备列表',
      hideInMenu: true, // 菜单从后端获取，前端只定义组件映射
      keepAlive: true, // 保持组件缓存，切换 tab 时保留筛选条件
    },
  },
];

export default routes;