# perfwin v0.3.0 升级后的性能监控界面设计

**日期**: 2026-05-09  
**版本**: 2.0  
**状态**: 设计方案（已补充技术细节）

## 背景

perfwin 从 v0.2.2 升级到 v0.3.0，数据结构发生重大变化：

- **v0.2.2**: 返回固定的系统指标（`cpu_usage`, `gpu_usage`, `power`, `cpu_temp` 等）+ 进程数据
- **v0.3.0**: 返回完整的 hwinfo_raw（包含 200-300 个传感器数据）+ 进程数据

**问题**: 现有界面设计基于固定字段，无法展示和对比 hwinfo_raw 的所有传感器数据。

---

## 设计目标

1. **全量存储**: 存储所有 hwinfo_raw 数据，支持任意指标的对比查询
2. **核心指标展示**: 保持 4 个核心图表（系统 CPU、系统 GPU、进程 CPU、进程 GPU）
3. **高级指标查询**: 提供 200+ 冷门指标的查询和对比功能
4. **标记功能**: 支持在图表上标记关键区间（发起共享、场景加载等）
5. **TOP10 交互**: 点击折线图切换查看不同时刻的 TOP10 进程排名
6. **时间导航**: 提供时间导航条，用户可拖拽选择时间区间
7. **界面美观**: 使用折线图（更简洁），优化布局和样式

---

## 一、数据模型设计

### 1.1 核心指标键名映射（明确定义）

**核心图表对应的 hwinfo_raw 键名**：

| 图表 | 数据来源 | hwinfo_raw 键名（主键） | 备选键名 | 说明 |
|------|----------|------------------------|----------|------|
| CPU使用率图表 | hwinfo_raw | `CPU Total Usage` | `CPU Total`, `Total CPU Usage` | 系统CPU总使用率 |
| GPU使用率图表 | hwinfo_raw | `GPU Core Usage` | `GPU Usage`, `GPU Total Usage` | GPU核心使用率 |
| 进程CPU使用率 | target_processes | - | - | 进程数据中的 cpu_usage 字段汇总 |
| 进程GPU使用率 | target_processes | - | - | 进程数据中的 gpu_usage 字段汇总 |
| 提交内存图表 | hwinfo_raw | `Commit Memory` | `Commit Memory Total` | 系统提交内存（进程提交内存需从进程数据中提取） |
| 进程内存图表 | target_processes | - | - | 进程数据中的 memory 字段汇总 |

**提取逻辑**：

```python
def extract_core_metrics(hwinfo_raw: dict, target_processes: list) -> dict:
    """从 hwinfo_raw 和进程数据中提取核心指标"""
    
    # CPU 使用率提取（尝试多个键名）
    cpu_usage = hwinfo_raw.get("CPU Total Usage", {}).get("value")
    if cpu_usage is None:
        cpu_usage = hwinfo_raw.get("CPU Total", {}).get("value")
    if cpu_usage is None:
        cpu_usage = hwinfo_raw.get("Total CPU Usage", {}).get("value")
    
    # GPU 使用率提取（尝试多个键名）
    gpu_usage = hwinfo_raw.get("GPU Core Usage", {}).get("value")
    if gpu_usage is None:
        gpu_usage = hwinfo_raw.get("GPU Usage", {}).get("value")
    
    # 提交内存提取
    commit_memory = hwinfo_raw.get("Commit Memory", {}).get("value")
    if commit_memory is None:
        commit_memory = hwinfo_raw.get("Commit Memory Total", {}).get("value")
    
    # 进程指标汇总
    process_cpu = sum(p.get("cpu_usage", 0) for p in target_processes)
    process_gpu = sum(p.get("gpu_usage", 0) for p in target_processes)
    process_memory = sum(p.get("memory", 0) for p in target_processes)
    
    return {
        "cpu_usage": cpu_usage,
        "gpu_usage": gpu_usage,
        "commit_memory": commit_memory,
        "process_cpu": process_cpu,
        "process_gpu": process_gpu,
        "process_memory": process_memory
    }
```

---

### 1.2 后端数据模型变更

#### 修改 `PerformanceData` 模型

```python
class PerformanceData(BaseModel):
    """
    性能数据表
    """
    __tablename__ = "performance_data"

    # 采集记录ID
    collect_id = Column(String(21), ForeignKey("performance_collect.id"), nullable=False, index=True)

    # 时间字段
    timestamp = Column(DateTime, nullable=False, comment="实际时间")
    relative_time = Column(Integer, nullable=False, comment="相对时间（秒）")

    # 进程数据（保持不变）
    target_processes = Column(JSON, nullable=True, comment="目标进程数据")
    top10_cpu = Column(JSON, nullable=True, comment="CPU TOP10")
    top10_gpu = Column(JSON, nullable=True, comment="GPU TOP10")

    # 新增：hwinfo_raw 完整数据
    hwinfo_raw = Column(JSON, nullable=True, comment="HWiNFO原始传感器数据（完整）")

    # 保留：原有固定系统指标字段（兼容旧数据）
    cpu_usage = Column(Float, nullable=True, comment="CPU使用率（兼容旧数据）")
    gpu_usage = Column(Float, nullable=True, comment="GPU使用率（兼容旧数据）")
    commit_memory = Column(Float, nullable=True, comment="提交内存（兼容旧数据）")
    # 其他字段保留，允许为空
```

**Why**: 保留原有字段是为了兼容旧数据，新数据从 hwinfo_raw 中提取填充。

**数据迁移方案**：

```python
# 不删除原有字段，新增 hwinfo_raw 字段
# 新数据：Worker 上报 hwinfo_raw，后端提取核心指标填充原有字段
# 旧数据：原有字段数据保持不变，hwinfo_raw 为 null

# 数据库迁移命令
alembic revision --autogenerate -m "add hwinfo_raw to performance_data"
alembic upgrade head
```

---

#### 新增 `PerformanceMetricMapping` 模型

```python
class PerformanceMetricMapping(BaseModel):
    """指标映射配置表"""
    __tablename__ = "performance_metric_mapping"

    id = Column(String(21), primary_key=True)
    
    # hwinfo传感器原始名称（如"CPU Total Usage"）
    hwinfo_key = Column(String(100), nullable=False, unique=True, comment="HWiNFO传感器键名")

    # 中文显示名称（如"CPU总使用率"）
    display_name = Column(String(100), nullable=False, comment="中文显示名称")

    # 指标分类（用于筛选）
    category = Column(String(20), nullable=False, default="system", comment="指标分类")

    # 是否是常用指标（用于主界面展示）
    is_primary = Column(Boolean, nullable=False, default=False, comment="是否常用指标")

    # 单位
    unit = Column(String(20), nullable=True, comment="单位")

    # 排序
    sort = Column(Integer, nullable=False, default=0)
```

---

#### 新增 `PerformanceMarker` 模型（标记功能）

```python
class PerformanceMarker(BaseModel):
    """标记数据表"""
    __tablename__ = "performance_marker"

    id = Column(String(21), primary_key=True)
    
    # 采集记录ID
    collect_id = Column(String(21), ForeignKey("performance_collect.id"), nullable=False, index=True)

    # 标记名称
    name = Column(String(50), nullable=False, comment="标记名称（如：发起共享）")

    # 开始时间（相对时间，秒）
    start_time = Column(Integer, nullable=False, comment="开始时间")

    # 结束时间（相对时间，秒）
    end_time = Column(Integer, nullable=True, comment="结束时间")

    # 标记颜色
    color = Column(String(10), nullable=False, default="#409eff", comment="标记颜色")

    # 标记类型
    marker_type = Column(String(20), nullable=False, default="range", comment="标记类型：range/point")

    # 备注
    note = Column(String(200), nullable=True, comment="备注信息")
```

---

### 1.3 默认指标映射清单

**系统级指标（category: system）**：

| hwinfo_key | display_name | is_primary | unit |
|------------|--------------|------------|------|
| CPU Total Usage | CPU总使用率 | true | % |
| CPU Total | CPU总使用率 | true | % |
| GPU Core Usage | GPU核心使用率 | true | % |
| GPU Usage | GPU使用率 | true | % |
| Commit Memory | 提交内存 | true | MB |
| CPU Package | CPU温度 | true | °C |
| CPU Package Power | CPU功耗 | true | W |
| GPU Temperature | GPU温度 | true | °C |
| GPU Power | GPU功耗 | true | W |
| Memory Usage | 内存使用率 | false | % |

**硬件监控指标（category: hardware）**：

| hwinfo_key | display_name | is_primary | unit |
|------------|--------------|------------|------|
| CPU Core #1 | CPU核心1温度 | false | °C |
| CPU Core #2 | CPU核心2温度 | false | °C |
| ... | ... | false | °C |
| Fan #1 | 风扇1转速 | false | RPM |
| Fan #2 | 风扇2转速 | false | RPM |

**网络指标（category: network）**：

| hwinfo_key | display_name | is_primary | unit |
|------------|--------------|------------|------|
| Network Upload | 上传速度 | false | KB/s |
| Network Download | 下载速度 | false | KB/s |

---

## 二、后端 API 设计

### 2.1 指标映射管理 API

```python
# GET /api/core/performance-metric-mapping/list
# 查询映射列表
# Query: keyword, category, is_primary
# Response: { items: [{ id, hwinfo_key, display_name, category, is_primary, unit }] }

# POST /api/core/performance-metric-mapping
# 创建映射
# Body: { hwinfo_key, display_name, category, is_primary, unit }

# PUT /api/core/performance-metric-mapping/{id}
# 更新映射

# DELETE /api/core/performance-metric-mapping/{id}
# 删除映射

# POST /api/core/performance-metric-mapping/batch-import
# 批量导入（从 hwinfo_raw 自动提取未映射的传感器）
# Body: { collect_id }
# Response: { imported_count, sensors: [{ hwinfo_key, unit }] }
```

### 2.2 高级指标查询 API

```python
# GET /api/core/performance-data/metrics
# 查询指定指标的时序数据
# Query: collect_id, metric_keys (逗号分隔), start_time, end_time
# Response: {
#   metrics: {
#     "CPU Total Usage": [{ relative_time, value, unit }],
#     "GPU Temperature": [{ relative_time, value, unit }]
#   }
# }
```

### 2.3 标记管理 API

```python
# GET /api/core/performance-marker/list
# 查询标记列表
# Query: collect_id

# POST /api/core/performance-marker
# 创建标记
# Body: { collect_id, name, start_time, end_time, color, note }

# PUT /api/core/performance-marker/{id}
# 更新标记

# DELETE /api/core/performance-marker/{id}
# 删除标记
```

---

## 三、界面设计

### 3.1 整体布局结构

```
实时监控页面
├── 顶部控制区
│   ├── 设备选择（下拉）
│   ├── 采集状态显示（在线、已采集时长）
│   └── 控制按钮（开始采集、停止采集、查看历史）
│
├── 时间筛选和标记面板
│   ├── 时间导航条（拖拽区间选择）
│   └── 标记管理（已添加标记列表 + 添加标记按钮）
│
├── 核心图表区（一行一个图表）
│   ├── CPU使用率图表（折线图 + TOP10 + 标记圆点）
│   ├── GPU使用率图表（折线图 + TOP10 + 标记圆点）
│   ├── TOP10 进程排名（独立一行）
│   ├── 提交内存图表（折线图 + 标记圆点）
│   └── 进程内存图表（折线图 + 标记圆点）
│
└── 高级指标面板（默认折叠）
    ├── 搜索框（搜索中文指标名称）
    ├── 分类筛选（下拉）
    └── 展示模式切换（卡片模式 / 图表模式）
```

---

### 3.2 时间导航条设计

**布局**:
```
┌────────────────────────────────────────────────────┐
│ 时间导航            采集时长: 180s             │
├────────────────────────────────────────────────────┤
│  0s   30s   60s   90s   120s  150s  180s          │
│  |     |     |     |     |     |     |            │
│  ├──────────────────────────────┤                 │ ← 用户选中的区间
│  ┌─┐                          ┌─┐                 │ ← 左右拖拽手柄
│  └─┘                          └─┘                 │
│  0s                          90s                  │ ← 时间标签
└────────────────────────────────────────────────────┘
```

**交互设计**:
- 左右拖动手柄选择时间区间
- 拖动时时间标签实时更新
- 标记区域不在时间轴上显示（只在图表折线上显示圆点）
- 鼠标样式: `ew-resize`（↔）

**状态管理**:
- 拖拽完成后，前端从已加载的数据中过滤显示（不重新请求后端）
- 区间选择作为筛选条件，传递给图表组件

---

### 3.3 核心图表设计

**图表样式**:
- **折线图**（直线连接点，不是平滑曲线）
- 高度: 180px
- 渐变填充区域（rgba 半透明）
- 边框: 1px solid #eee
- 圆角: 8px

**图表元素**:
- 系统折线（蓝色 #409eff）+ 进程折线（绿色 #67c23a）
- 点击指示点（黄色 #ffc107）+ 垂直虚线
- 标记圆点（在折线数据点上）

---

### 3.4 标记显示设计

**标记圆点位置**: 在折线数据点坐标上（cx=时间，cy=折线Y值）

**显示规则**:
- 只显示起点圆点，不显示终点
- 圆点颜色与标记列表颜色一致
- 圆点上方显示标记名称（如"发起共享@0s"）

**添加标记交互**:
- 点击"添加标记"按钮，弹出表单
- 表单字段：标记名称、开始时间、结束时间、颜色、备注
- 提交后保存到后端，刷新标记列表和图表显示

---

### 3.5 TOP10 进程排名设计

**布局**: 独立一行，双列布局（左列 TOP1-5，右列 TOP6-10）

**交互设计**:
- 默认显示最新时刻的 TOP10
- 点击折线图切换时刻（黄色指示点显示选中时刻）
- CPU/GPU 切换按钮
- 标题旁显示当前选中的时刻（如"时刻: 90s"）

**实现逻辑**:
- 点击图表时，记录选中时刻（relative_time）
- 从已加载的 top10_cpu/top10_gpu 数据中，查找该时刻的数据
- 如果找不到精确时刻，找最近时刻的数据
- 前端过滤，不需要重新请求后端

---

### 3.6 Tooltip 设计

**样式**: 保持原有 ChartPanel.vue 实现样式

**内容**:
- 相对时间（秒）
- 实际时间（timestamp）
- 曲线值（系统/进程使用率）
- 进程明细（折叠显示）

**折叠逻辑**:
- 折叠状态：显示进程名 + 实例数量（chrome.exe 3个实例）
- 展开状态：显示每个实例的 PID 和使用率
- 保持原有字体和布局样式

---

### 3.7 高级指标面板设计

**默认状态**: 折叠，只显示搜索入口

**展开状态**: 用户输入搜索内容后，显示匹配的指标卡片

**交互设计**:
- 默认不显示指标列表（避免信息过载）
- 搜索后从后端查询映射表，匹配中文名称
- 卡片模式：迷你趋势线 + 当前值
- 图表模式：完整曲线图

---

## 四、性能优化方案

### 4.1 数据库优化

```sql
-- 为 JSON 字段查询创建 GIN 索引
CREATE INDEX idx_performance_data_hwinfo_raw ON performance_data USING GIN (hwinfo_raw);

-- 为常用查询创建复合索引
CREATE INDEX idx_performance_data_collect_time ON performance_data (collect_id, relative_time);
```

### 4.2 查询优化

```python
# 查询指定指标时，只提取需要的字段
SELECT 
    relative_time,
    hwinfo_raw->>'CPU Total Usage' as cpu_usage,
    hwinfo_raw->>'GPU Core Usage' as gpu_usage
FROM performance_data
WHERE collect_id = :collect_id
AND relative_time BETWEEN :start_time AND :end_time
ORDER BY relative_time;
```

### 4.3 前端数据加载

- 初始加载：只加载核心指标数据（从 hwinfo_raw 提取）
- 高级指标：用户搜索时按需加载
- 时间区间过滤：前端过滤已加载的数据

---

## 五、实现优先级

### Phase 1（核心功能）

1. **数据模型变更**
   - 修改 PerformanceData 模型（增加 hwinfo_raw，保留原有字段）
   - 新增 PerformanceMetricMapping 模型
   - 新增 PerformanceMarker 模型
   - 数据库迁移
   - 初始化默认指标映射数据

2. **后端 API 实现**
   - Worker 上报 API 接收 hwinfo_raw，提取核心指标填充原有字段
   - 指标映射 CRUD API
   - 标记 CRUD API
   - 高级指标查询 API

3. **前端界面调整**
   - 保持 4 个核心图表（从 hwinfo_raw 提取 CPU/GPU 使用率）
   - 一行一个图表布局
   - 改用折线图样式
   - 标记圆点显示

### Phase 2（交互功能）

4. **时间导航条**
   - 拖拽区间选择功能
   - 前端数据过滤

5. **标记管理**
   - 标记添加表单
   - 标记编辑/删除

6. **TOP10 交互**
   - 点击折线图切换时刻
   - TOP10 柱状图展示
   - CPU/GPU 切换

### Phase 3（高级功能）

7. **高级指标面板**
   - 搜索和分类筛选
   - 指标卡片展示
   - 指标图表对比

8. **指标映射管理页面**
   - 映射 CRUD 界面
   - 批量导入功能

9. **版本对比扩展**
   - 高级指标对比面板

---

## 六、验收标准

### 功能验收

1. Worker 上报 hwinfo_raw 数据成功存储，核心指标正确提取填充
2. 核心图表正确展示（从 hwinfo_raw 提取 CPU/GPU 使用率）
3. 时间导航条拖拽功能正常，前端数据过滤生效
4. 标记圆点在折线上正确显示，标记管理功能正常
5. TOP10 交互切换功能正常（前端过滤）
6. 高级指标搜索和展示功能正常
7. 指标映射管理功能正常

### 性能验收

1. 数据查询响应时间 < 1秒（测试数据量：180 条采样记录）
2. 折线图渲染流畅（渲染时间 < 500ms）
3. TOP10 切换响应及时（前端过滤，响应时间 < 100ms）
4. 前端加载 180 条 hwinfo_raw 数据，渲染无明显卡顿

---

**设计状态**: 已补充技术细节  
**下一步**: 用户确认后，进入实现阶段