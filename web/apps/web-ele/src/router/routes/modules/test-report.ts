import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    name: 'TestReportDetail',
    path: '/test-report/detail/:task_id',
    component: () => import('#/views/test-report/detail/index.vue'),
    meta: {
      hideInMenu: true,
      title: '测试报告详情',
    },
  },
];

export default routes;