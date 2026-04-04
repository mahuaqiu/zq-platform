# 设备监控页面 Namespace 筛选功能设计

## 概述

为设备监控页面添加 namespace 下拉筛选功能，支持用户选择查看特定 namespace 的数据，默认不设置 namespace 则查询所有数据。

## 现状分析

- 后端已有 `EnvMachineService.get_namespaces()` 方法可获取所有 namespace 列表
- 后端 API `/api/core/env/dashboard/stats` 已支持可选 `namespace` 参数
- 前端 API 调用 `getDashboardStatsApi(namespace?)` 已支持传入 namespace
- 前端页面缺少 namespace 下拉筛选组件

## 实现方案

### 1. 后端新增 API

**路由：** `GET /api/core/env/namespaces`

**文件：** `backend-fastapi/core/env_machine/api.py`

```python
@router.get("/namespaces", summary="获取所有机器分类")
async def get_namespaces(db: AsyncSession = Depends(get_db)) -> List[str]:
    """获取所有 namespace 列表（去重、已排序）"""
    return await EnvMachineService.get_namespaces(db)
```

### 2. 前端新增 API 接口

**文件：** `web/apps/web-ele/src/api/core/device-monitor.ts`

```typescript
export function getNamespacesApi() {
  return requestClient.get<string[]>('/api/core/env/namespaces');
}
```

### 3. 前端页面修改

**文件：** `web/apps/web-ele/src/views/device-monitor/index.vue`

**修改内容：**
- 添加 namespace 下拉筛选框（使用 Element Plus `el-select`）
- 页面加载时获取 namespace 列表
- 默认值：空（显示所有数据）
- 切换 namespace 时自动刷新看板数据

**UI 位置：** 页面顶部，左上角，与标题栏同行或独立一行

## 技术细节

1. 下拉框使用 `el-select` 组件，配置 `clearable` 属性允许清空选择
2. 选择变化时调用 `loadStats()` 重新获取数据
3. 切换时显示 loading 状态
4. 样式与现有页面风格保持一致