import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/system/config-center',
    name: 'SystemConfigCenter',
    component: () => import('#/views/config-center/index.vue'),
    meta: {
      title: '配置中心',
      hideInMenu: true, // 菜单从后端获取，前端只定义组件映射
    },
  },
];

export default routes;
