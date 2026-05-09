# perfwin v0.3.0 性能监控界面升级实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级性能监控模块，支持 hwinfo_raw（200-300传感器）全量存储和查询，核心图表展示 + 高级指标搜索。

**Architecture:** PostgreSQL JSON 字段存储 hwinfo_raw，后端提取核心指标填充原有字段（兼容旧数据），新增指标映射表和标记表，前端一行一个折线图布局，TOP10 点击交互，时间导航条拖拽选择。

**Tech Stack:** FastAPI + SQLAlchemy + PostgreSQL (JSON), Vue 3 + ECharts

---

## 文件结构

### 后端文件（修改/新增）

| 文件路径 | 负责内容 | 操作 |
|----------|----------|------|
| `backend-fastapi/core/performance_monitor/model.py` | 数据模型定义（新增 hwinfo_raw, PerformanceMetricMapping, PerformanceMarker） | 修改 |
| `backend-fastapi/core/performance_monitor/schema.py` | API Schema 定义（新增映射、标记、高级指标查询） | 修改 |
| `backend-fastapi/core/performance_monitor/service.py` | 业务逻辑（新增提取核心指标逻辑、映射服务、标记服务） | 修改 |
| `backend-fastapi/core/performance_monitor/api.py` | API 路由（新增映射 CRUD、标记 CRUD、高级指标查询） | 修改 |
| `backend-fastapi/core/performance_monitor/utils.py` | 辅助函数（提取核心指标、指标键名匹配） | 新增 |
| `backend-fastapi/alembic/versions/xxx_add_hwinfo_raw.py` | 数据库迁移脚本 | 新增 |
| `backend-fastapi/scripts/init_metric_mappings.py` | 初始化默认指标映射数据 | 新增 |

### 前端文件（修改/新增）

| 文件路径 | 负责内容 | 操作 |
|----------|----------|------|
| `web/apps/web-ele/src/views/performance-monitor/index.vue` | 主页面（布局调整、时间导航条、高级指标面板） | 修改 |
| `web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue` | 图表组件（改为折线图、标记圆点显示） | 修改 |
| `web/apps/web-ele/src/views/performance-monitor/components/Top10List.vue` | TOP10组件（改为水平柱状图、点击切换时刻） | 修改 |
| `web/apps/web-ele/src/views/performance-monitor/components/TimeNavigator.vue` | 时间导航条组件（拖拽区间选择） | 新增 |
| `web/apps/web-ele/src/views/performance-monitor/components/MarkerManager.vue` | 标记管理组件（添加标记表单、标记列表） | 新增 |
| `web/apps/web-ele/src/views/performance-monitor/components/AdvancedMetrics.vue` | 高级指标面板组件（搜索、分类筛选） | 新增 |
| `web/apps/web-ele/src/api/core/performance-monitor.ts` | API 定义（新增映射、标记、高级指标查询） | 修改 |
| `web/apps/web-ele/src/views/performance-monitor/types.ts` | 类型定义（新增标记、映射类型） | 修改 |

---

## Task 1: 数据模型变更

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/model.py`

- [ ] **Step 1: 在 PerformanceData 模型中新增 hwinfo_raw 字段**

```python
# 在 PerformanceData 类中添加（保留原有字段）
    # 新增：hwinfo_raw 完整数据（v0.3.0）
    hwinfo_raw = Column(JSON, nullable=True, comment="HWiNFO原始传感器数据（完整）")
```

- [ ] **Step 2: 新增 PerformanceMetricMapping 模型**

```python
class PerformanceMetricMapping(BaseModel):
    """指标映射配置表"""
    __tablename__ = "performance_metric_mapping"

    # hwinfo传感器原始名称
    hwinfo_key = Column(String(100), nullable=False, unique=True, index=True, comment="HWiNFO传感器键名")

    # 中文显示名称
    display_name = Column(String(100), nullable=False, comment="中文显示名称")

    # 指标分类
    category = Column(String(20), nullable=False, default="system", comment="指标分类")

    # 是否常用指标
    is_primary = Column(Boolean, nullable=False, default=False, comment="是否常用指标")

    # 单位
    unit = Column(String(20), nullable=True, comment="单位")

    # 排序
    sort = Column(Integer, nullable=False, default=0)
```

- [ ] **Step 3: 新增 PerformanceMarker 模型**

```python
class PerformanceMarker(BaseModel):
    """标记数据表（v0.3.0新增）"""
    __tablename__ = "performance_marker"

    # 采集记录ID
    collect_id = Column(String(21), ForeignKey("performance_collect.id"), nullable=False, index=True, comment="采集记录ID")

    # 标记名称
    name = Column(String(50), nullable=False, comment="标记名称")

    # 开始时间（相对时间，秒）
    start_time = Column(Integer, nullable=False, comment="开始时间")

    # 结束时间（相对时间，秒，可选）
    end_time = Column(Integer, nullable=True, comment="结束时间")

    # 标记颜色
    color = Column(String(10), nullable=False, default="#409eff", comment="标记颜色")

    # 备注
    note = Column(String(200), nullable=True, comment="备注信息")
```

- [ ] **Step 4: 运行数据库迁移**

```bash
cd backend-fastapi
source .venv/bin/activate  # 或 conda activate zq-fastapi
alembic revision --autogenerate -m "add hwinfo_raw and new tables"
alembic upgrade head
```

**说明**: 迁移脚本会自动生成在 `alembic/versions/xxxxxxxx_add_hwinfo_raw_and_new_tables.py`，其中 `xxxxxxxx` 是时间戳哈希。

Expected: 数据库新增 hwinfo_raw 字段、performance_metric_mapping 表、performance_marker 表

- [ ] **Step 5: Commit**

```bash
git add backend-fastapi/core/performance_monitor/model.py
git commit -m "feat(performance-monitor): add hwinfo_raw field and new models"
```

---

## Task 2: 初始化默认指标映射数据

**Files:**
- Create: `backend-fastapi/scripts/init_metric_mappings.py`

- [ ] **Step 1: 创建初始化脚本**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化默认指标映射数据
"""
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings
from core.performance_monitor.model import PerformanceMetricMapping

DEFAULT_MAPPINGS = [
    # 系统级指标（常用）
    {"hwinfo_key": "CPU Total Usage", "display_name": "CPU总使用率", "category": "system", "is_primary": True, "unit": "%"},
    {"hwinfo_key": "CPU Total", "display_name": "CPU总使用率", "category": "system", "is_primary": True, "unit": "%"},
    {"hwinfo_key": "GPU Core Usage", "display_name": "GPU核心使用率", "category": "system", "is_primary": True, "unit": "%"},
    {"hwinfo_key": "GPU Usage", "display_name": "GPU使用率", "category": "system", "is_primary": True, "unit": "%"},
    {"hwinfo_key": "Commit Memory", "display_name": "提交内存", "category": "system", "is_primary": True, "unit": "MB"},
    {"hwinfo_key": "CPU Package", "display_name": "CPU温度", "category": "system", "is_primary": True, "unit": "°C"},
    {"hwinfo_key": "CPU Package Power", "display_name": "CPU功耗", "category": "system", "is_primary": True, "unit": "W"},
    {"hwinfo_key": "GPU Temperature", "display_name": "GPU温度", "category": "system", "is_primary": True, "unit": "°C"},
    {"hwinfo_key": "GPU Power", "display_name": "GPU功耗", "category": "system", "is_primary": False, "unit": "W"},
    {"hwinfo_key": "Memory Usage", "display_name": "内存使用率", "category": "system", "is_primary": False, "unit": "%"},
]

async def init_mappings():
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        for mapping in DEFAULT_MAPPINGS:
            existing = await session.execute(
                select(PerformanceMetricMapping).where(
                    PerformanceMetricMapping.hwinfo_key == mapping["hwinfo_key"]
                )
            )
            if not existing.scalar_one_or_none():
                obj = PerformanceMetricMapping(**mapping)
                session.add(obj)
        await session.commit()
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_mappings())
```

- [ ] **Step 2: 运行初始化脚本**

```bash
cd backend-fastapi
source .venv/bin/activate
python scripts/init_metric_mappings.py
```

Expected: 数据库插入默认指标映射数据

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/scripts/init_metric_mappings.py
git commit -m "feat(performance-monitor): add default metric mappings init script"
```

---

## Task 3: 新增辅助函数（提取核心指标）

**Files:**
- Create: `backend-fastapi/core/performance_monitor/utils.py`

- [ ] **Step 1: 创建 utils.py 文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控辅助函数
"""
from typing import Dict, Any, Optional, List


def extract_core_metrics(hwinfo_raw: Optional[Dict[str, Any]], target_processes: Optional[List[Dict[str, Any]]]) -> Dict[str, Optional[float]]:
    """
    从 hwinfo_raw 和进程数据中提取核心指标
    
    Args:
        hwinfo_raw: HWiNFO原始传感器数据（字典格式）
        target_processes: 目标进程列表
    
    Returns:
        包含核心指标的字典：cpu_usage, gpu_usage, commit_memory, process_cpu, process_gpu, process_memory
    """
    result = {
        "cpu_usage": None,
        "gpu_usage": None,
        "commit_memory": None,
        "process_cpu": None,
        "process_gpu": None,
        "process_memory": None,
    }
    
    # 从 hwinfo_raw 提取系统指标（尝试多个键名）
    if hwinfo_raw:
        # CPU 使用率
        for key in ["CPU Total Usage", "CPU Total", "Total CPU Usage"]:
            if key in hwinfo_raw:
                value = hwinfo_raw[key].get("value")
                if value is not None:
                    result["cpu_usage"] = float(value)
                    break
        
        # GPU 使用率
        for key in ["GPU Core Usage", "GPU Usage", "GPU Total Usage"]:
            if key in hwinfo_raw:
                value = hwinfo_raw[key].get("value")
                if value is not None:
                    result["gpu_usage"] = float(value)
                    break
        
        # 提交内存
        for key in ["Commit Memory", "Commit Memory Total"]:
            if key in hwinfo_raw:
                value = hwinfo_raw[key].get("value")
                unit = hwinfo_raw[key].get("unit", "MB")
                if value is not None:
                    # 根据单位转换（统一为 GB）
                    if unit == "MB":
                        result["commit_memory"] = float(value) / 1024
                    elif unit == "GB":
                        result["commit_memory"] = float(value)
                    else:
                        result["commit_memory"] = float(value)
                    break
    
    # 从进程数据汇总进程指标
    if target_processes:
        result["process_cpu"] = sum(float(p.get("total_cpu", 0)) for p in target_processes)
        result["process_gpu"] = sum(float(p.get("total_gpu", 0)) for p in target_processes)
        result["process_memory"] = sum(float(p.get("total_memory", 0)) for p in target_processes)
    
    return result
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/performance_monitor/utils.py
git commit -m "feat(performance-monitor): add extract_core_metrics utility"
```

---

## Task 4: 新增 Schema 定义

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/schema.py`

- [ ] **Step 1: 新增 HwinfoRawReport Schema（Worker上报）**

```python
# 兼容旧版本的 SystemReport（用于回退）
class SystemReport(BaseModel):
    """系统性能数据（兼容旧版本Worker）"""
    cpu_usage: Optional[float] = Field(None, ge=0, le=100, description="CPU使用率 %")
    gpu_usage: Optional[float] = Field(None, ge=0, le=100, description="GPU使用率 %")
    commit_memory: Optional[float] = Field(None, ge=0, description="提交内存 GB")
    memory_usage: Optional[float] = Field(None, ge=0, description="内存使用 GB")
    power: Optional[float] = Field(None, ge=0, description="功耗 W")
    cpu_speed: Optional[float] = Field(None, ge=0, description="CPU速度 GHz")
    cpu_temp: Optional[float] = Field(None, description="CPU温度 °C")
    process_handles: Optional[int] = Field(None, ge=0, description="进程句柄数")
    upload_speed: Optional[float] = Field(None, ge=0, description="上传速度 KB/s")
    download_speed: Optional[float] = Field(None, ge=0, description="下载速度 KB/s")


class PerformanceSampleReportV3(BaseModel):
    """单个性能样本上报 Schema（v0.3.0）"""
    timestamp: datetime = Field(..., description="实际时间")
    relative_time: int = Field(..., ge=0, description="相对时间（秒）")
    hwinfo_raw: Optional[Dict[str, Any]] = Field(None, description="HWiNFO原始传感器数据")
    system: Optional[SystemReport] = Field(None, description="系统性能数据（兼容旧版本，回退使用）")
    target_processes: List[TargetProcessReport] = Field(default_factory=list, description="目标进程")
    top10_cpu: List[Top10ProcessReport] = Field(default_factory=list, description="CPU TOP10")
    top10_gpu: List[Top10ProcessReport] = Field(default_factory=list, description="GPU TOP10")


class WorkerReportRequestV3(BaseModel):
    """Worker 上报数据请求 Schema（v0.3.0）"""
    collect_id: str = Field(..., description="采集记录ID")
    device_id: str = Field(..., description="设备ID")
    samples: List[PerformanceSampleReportV3] = Field(default_factory=list, description="性能样本列表")
```

- [ ] **Step 2: 新增 MetricMapping Schema**

```python
class MetricMappingCreate(BaseModel):
    """创建指标映射请求"""
    hwinfo_key: str = Field(..., max_length=100, description="HWiNFO传感器键名")
    display_name: str = Field(..., max_length=100, description="中文显示名称")
    category: str = Field(default="system", description="指标分类")
    is_primary: bool = Field(default=False, description="是否常用指标")
    unit: Optional[str] = Field(None, max_length=20, description="单位")


class MetricMappingUpdate(BaseModel):
    """更新指标映射请求"""
    display_name: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None)
    is_primary: Optional[bool] = Field(None)
    unit: Optional[str] = Field(None)


class MetricMappingResponse(BaseModel):
    """指标映射响应"""
    id: str
    hwinfo_key: str
    display_name: str
    category: str
    is_primary: bool
    unit: Optional[str]
    sort: int
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 3: 新增 Marker Schema**

```python
class MarkerCreate(BaseModel):
    """创建标记请求"""
    collect_id: str = Field(..., description="采集记录ID")
    name: str = Field(..., max_length=50, description="标记名称")
    start_time: int = Field(..., ge=0, description="开始时间（秒）")
    end_time: Optional[int] = Field(None, ge=0, description="结束时间（秒）")
    color: str = Field(default="#409eff", description="标记颜色")
    note: Optional[str] = Field(None, max_length=200, description="备注")


class MarkerUpdate(BaseModel):
    """更新标记请求"""
    name: Optional[str] = Field(None, max_length=50)
    start_time: Optional[int] = Field(None, ge=0)
    end_time: Optional[int] = Field(None, ge=0)
    color: Optional[str] = Field(None)
    note: Optional[str] = Field(None)


class MarkerResponse(BaseModel):
    """标记响应"""
    id: str
    collect_id: str
    name: str
    start_time: int
    end_time: Optional[int]
    color: str
    note: Optional[str]
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: 新增高级指标查询 Schema**

```python
class AdvancedMetricsQuery(BaseModel):
    """高级指标查询请求"""
    collect_id: str = Field(..., description="采集记录ID")
    metric_keys: List[str] = Field(..., min_length=1, description="指标键名列表")
    start_time: Optional[int] = Field(None, ge=0, description="起始时间（秒）")
    end_time: Optional[int] = Field(None, ge=0, description="结束时间（秒）")


class MetricTimeSeries(BaseModel):
    """指标时序数据"""
    hwinfo_key: str
    display_name: Optional[str]
    unit: Optional[str]
    data: List[Dict[str, Any]]  # [{ relative_time, value }]


class AdvancedMetricsResponse(BaseModel):
    """高级指标查询响应"""
    metrics: Dict[str, MetricTimeSeries]  # key: hwinfo_key
```

- [ ] **Step 5: Commit**

```bash
git add backend-fastapi/core/performance_monitor/schema.py
git commit -m "feat(performance-monitor): add new schemas for v0.3.0"
```

---

## Task 5: 新增 Service 业务逻辑

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/service.py`

- [ ] **Step 1: 导入新模型和辅助函数**

```python
from core.performance_monitor.model import PerformanceCollect, PerformanceData, PerformanceTag, PerformanceVersion, PerformanceMetricMapping, PerformanceMarker
from core.performance_monitor.utils import extract_core_metrics
```

- [ ] **Step 2: 修改 PerformanceDataService.report_data 方法**

```python
@classmethod
async def report_data(cls, db: AsyncSession, request: WorkerReportRequestV3) -> bool:
    """接收 Worker 上报数据（v0.3.0）"""
    for sample in request.samples:
        timestamp_naive = sample.timestamp.replace(tzinfo=None) if sample.timestamp.tzinfo else sample.timestamp
        
        # 提取核心指标
        core_metrics = extract_core_metrics(sample.hwinfo_raw, sample.target_processes)
        
        data = PerformanceData(
            collect_id=request.collect_id,
            timestamp=timestamp_naive,
            relative_time=sample.relative_time,
            # 核心指标（从 hwinfo_raw 提取）
            cpu_usage=core_metrics["cpu_usage"] or sample.system.cpu_usage,
            gpu_usage=core_metrics["gpu_usage"] or sample.system.gpu_usage,
            commit_memory=core_metrics["commit_memory"] or sample.system.commit_memory,
            memory_usage=sample.system.memory_usage,
            power=sample.system.power,
            cpu_speed=sample.system.cpu_speed,
            cpu_temp=sample.system.cpu_temp,
            process_handles=sample.system.process_handles,
            upload_speed=sample.system.upload_speed,
            download_speed=sample.system.download_speed,
            # 进程数据
            target_processes=[p.model_dump() for p in sample.target_processes],
            top10_cpu=[p.model_dump() for p in sample.top10_cpu],
            top10_gpu=[p.model_dump() for p in sample.top10_gpu],
            # 新增：hwinfo_raw 完整数据
            hwinfo_raw=sample.hwinfo_raw,
        )
        db.add(data)
    await db.commit()
    return True
```

- [ ] **Step 3: 新增 MetricMappingService（包含 update_mapping 和 delete_mapping 方法）**

```python
class MetricMappingService(BaseService):
    """指标映射服务"""
    model = PerformanceMetricMapping

    @classmethod
    async def get_mappings(cls, db: AsyncSession, keyword: Optional[str] = None, category: Optional[str] = None) -> List[PerformanceMetricMapping]:
        """获取映射列表"""
        conditions = [PerformanceMetricMapping.is_deleted == False]
        if keyword:
            conditions.append(
                or_(
                    PerformanceMetricMapping.hwinfo_key.ilike(f"%{keyword}%"),
                    PerformanceMetricMapping.display_name.ilike(f"%{keyword}%")
                )
            )
        if category:
            conditions.append(PerformanceMetricMapping.category == category)
        
        stmt = select(PerformanceMetricMapping).where(and_(*conditions)).order_by(PerformanceMetricMapping.sort)
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def create_mapping(cls, db: AsyncSession, request: MetricMappingCreate) -> str:
        """创建映射"""
        mapping = PerformanceMetricMapping(**request.model_dump())
        db.add(mapping)
        await db.commit()
        await db.refresh(mapping)
        return mapping.id

    @classmethod
    async def update_mapping(cls, db: AsyncSession, mapping_id: str, request: MetricMappingUpdate) -> bool:
        """更新映射"""
        mapping = await db.get(PerformanceMetricMapping, mapping_id)
        if mapping:
            for key, value in request.model_dump(exclude_unset=True).items():
                if value is not None:
                    setattr(mapping, key, value)
            await db.commit()
            return True
        return False

    @classmethod
    async def delete_mapping(cls, db: AsyncSession, mapping_id: str) -> bool:
        """删除映射"""
        mapping = await db.get(PerformanceMetricMapping, mapping_id)
        if mapping:
            await db.delete(mapping)
            await db.commit()
            return True
        return False

    @classmethod
    async def batch_import(cls, db: AsyncSession, collect_id: str) -> Dict[str, Any]:
        """批量导入（从 hwinfo_raw 自动提取未映射的传感器）"""
        # 获取该采集的所有 hwinfo_raw 键名
        stmt = select(PerformanceData.hwinfo_raw).where(
            PerformanceData.collect_id == collect_id,
            PerformanceData.hwinfo_raw.isnot(None)
        ).limit(1)
        result = await db.execute(stmt)
        hwinfo_raw = result.scalar_one_or_none()
        
        if not hwinfo_raw:
            return {"imported_count": 0, "sensors": []}
        
        imported = []
        for key in hwinfo_raw.keys():
            # 检查是否已存在映射
            existing = await db.execute(
                select(PerformanceMetricMapping).where(PerformanceMetricMapping.hwinfo_key == key)
            )
            if not existing.scalar_one_or_none():
                unit = hwinfo_raw[key].get("unit")
                mapping = PerformanceMetricMapping(
                    hwinfo_key=key,
                    display_name=key,  # 默认使用键名作为显示名称
                    category="hardware",
                    is_primary=False,
                    unit=unit
                )
                db.add(mapping)
                imported.append({"hwinfo_key": key, "unit": unit})
        
        await db.commit()
        return {"imported_count": len(imported), "sensors": imported}
```

- [ ] **Step 4: 新增 MarkerService**

```python
class MarkerService(BaseService):
    """标记服务"""
    model = PerformanceMarker

    @classmethod
    async def get_markers(cls, db: AsyncSession, collect_id: str) -> List[PerformanceMarker]:
        """获取标记列表"""
        stmt = select(PerformanceMarker).where(
            PerformanceMarker.collect_id == collect_id,
            PerformanceMarker.is_deleted == False
        ).order_by(PerformanceMarker.start_time)
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def create_marker(cls, db: AsyncSession, request: MarkerCreate) -> str:
        """创建标记"""
        marker = PerformanceMarker(**request.model_dump())
        db.add(marker)
        await db.commit()
        await db.refresh(marker)
        return marker.id

    @classmethod
    async def update_marker(cls, db: AsyncSession, marker_id: str, request: MarkerUpdate) -> bool:
        """更新标记"""
        marker = await db.get(PerformanceMarker, marker_id)
        if marker:
            for key, value in request.model_dump(exclude_unset=True).items():
                if value is not None:
                    setattr(marker, key, value)
            await db.commit()
            return True
        return False

    @classmethod
    async def delete_marker(cls, db: AsyncSession, marker_id: str) -> bool:
        """删除标记"""
        marker = await db.get(PerformanceMarker, marker_id)
        if marker:
            await db.delete(marker)
            await db.commit()
            return True
        return False
```

- [ ] **Step 5: 新增高级指标查询方法**

```python
@classmethod
async def query_advanced_metrics(cls, db: AsyncSession, request: AdvancedMetricsQuery) -> Dict[str, Any]:
    """查询高级指标"""
    conditions = [PerformanceData.collect_id == request.collect_id]
    if request.start_time:
        conditions.append(PerformanceData.relative_time >= request.start_time)
    if request.end_time:
        conditions.append(PerformanceData.relative_time <= request.end_time)
    
    stmt = select(PerformanceData).where(and_(*conditions)).order_by(PerformanceData.relative_time)
    result = await db.execute(stmt)
    data_list = result.scalars().all()
    
    # 获取映射信息
    mappings = await MetricMappingService.get_mappings(db)
    mapping_dict = {m.hwinfo_key: m for m in mappings}
    
    metrics = {}
    for key in request.metric_keys:
        time_series = []
        mapping = mapping_dict.get(key)
        
        for data in data_list:
            if data.hwinfo_raw and key in data.hwinfo_raw:
                value = data.hwinfo_raw[key].get("value")
                if value is not None:
                    time_series.append({
                        "relative_time": data.relative_time,
                        "value": value
                    })
        
        metrics[key] = {
            "hwinfo_key": key,
            "display_name": mapping.display_name if mapping else key,
            "unit": mapping.unit if mapping else None,
            "data": time_series
        }
    
    return {"metrics": metrics}
```

- [ ] **Step 6: Commit**

```bash
git add backend-fastapi/core/performance_monitor/service.py
git commit -m "feat(performance-monitor): add new services for v0.3.0"
```

---

## Task 6: 新增 API 路由

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/api.py`

- [ ] **Step 1: 导入新 Schema 和 Service**

```python
from fastapi import Query  # 新增 Query 导入
from core.performance_monitor.schema import (
    ...,  # 原有导入
    WorkerReportRequestV3, MetricMappingCreate, MetricMappingUpdate, MetricMappingResponse,
    MarkerCreate, MarkerUpdate, MarkerResponse, AdvancedMetricsQuery, AdvancedMetricsResponse
)
from core.performance_monitor.service import (
    ...,  # 原有导入
    MetricMappingService, MarkerService
)
```

- [ ] **Step 2: 修改 report_data API（支持 v0.3.0）**

```python
@router.post("/report")
async def report_data(request: WorkerReportRequestV3, db: AsyncSession = Depends(get_db)):
    """Worker 上报数据（v0.3.0）"""
    success = await PerformanceDataService.report_data(db, request)
    return {"status": "success" if success else "failed"}
```

- [ ] **Step 3: 新增指标映射 API**

```python
# ===== 指标映射管理 =====

@router.get("/metric-mapping/list")
async def get_metric_mappings(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取指标映射列表"""
    mappings = await MetricMappingService.get_mappings(db, keyword, category)
    return {"items": [MetricMappingResponse.model_validate(m) for m in mappings]}


@router.post("/metric-mapping")
async def create_metric_mapping(request: MetricMappingCreate, db: AsyncSession = Depends(get_db)):
    """创建指标映射"""
    mapping_id = await MetricMappingService.create_mapping(db, request)
    return {"id": mapping_id, "status": "created"}


@router.put("/metric-mapping/{mapping_id}")
async def update_metric_mapping(mapping_id: str, request: MetricMappingUpdate, db: AsyncSession = Depends(get_db)):
    """更新指标映射"""
    success = await MetricMappingService.update_mapping(db, mapping_id, request)
    return {"status": "updated" if success else "not_found"}


@router.delete("/metric-mapping/{mapping_id}")
async def delete_metric_mapping(mapping_id: str, db: AsyncSession = Depends(get_db)):
    """删除指标映射"""
    success = await MetricMappingService.delete_mapping(db, mapping_id)
    return {"status": "deleted" if success else "not_found"}


@router.post("/metric-mapping/batch-import")
async def batch_import_mappings(
    collect_id: str = Query(..., description="采集记录ID"),
    db: AsyncSession = Depends(get_db)
):
    """批量导入未映射的传感器"""
    result = await MetricMappingService.batch_import(db, collect_id)
    return result
```

- [ ] **Step 4: 新增标记 API**

```python
# ===== 标记管理（v0.3.0）=====

@router.get("/marker/list")
async def get_markers(collect_id: str, db: AsyncSession = Depends(get_db)):
    """获取标记列表"""
    markers = await MarkerService.get_markers(db, collect_id)
    return {"items": [MarkerResponse.model_validate(m) for m in markers]}


@router.post("/marker")
async def create_marker(request: MarkerCreate, db: AsyncSession = Depends(get_db)):
    """创建标记"""
    marker_id = await MarkerService.create_marker(db, request)
    return {"id": marker_id, "status": "created"}


@router.put("/marker/{marker_id}")
async def update_marker(marker_id: str, request: MarkerUpdate, db: AsyncSession = Depends(get_db)):
    """更新标记"""
    success = await MarkerService.update_marker(db, marker_id, request)
    return {"status": "updated" if success else "not_found"}


@router.delete("/marker/{marker_id}")
async def delete_marker(marker_id: str, db: AsyncSession = Depends(get_db)):
    """删除标记"""
    success = await MarkerService.delete_marker(db, marker_id)
    return {"status": "deleted" if success else "not_found"}
```

- [ ] **Step 5: 新增高级指标查询 API**

```python
# ===== 高级指标查询 =====

@router.post("/metrics/query")
async def query_advanced_metrics(request: AdvancedMetricsQuery, db: AsyncSession = Depends(get_db)):
    """查询高级指标"""
    result = await PerformanceDataService.query_advanced_metrics(db, request)
    return result
```

- [ ] **Step 6: Commit**

```bash
git add backend-fastapi/core/performance_monitor/api.py
git commit -m "feat(performance-monitor): add new API routes for v0.3.0"
```

---

## Task 6.5: 后端单元测试

**Files:**
- Create: `backend-fastapi/tests/test_performance_monitor_utils.py`

- [ ] **Step 1: 创建测试文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控辅助函数单元测试
"""
import pytest
from core.performance_monitor.utils import extract_core_metrics


class TestExtractCoreMetrics:
    """测试核心指标提取函数"""

    def test_extract_cpu_usage_with_main_key(self):
        """测试使用主键名提取 CPU 使用率"""
        hwinfo_raw = {
            "CPU Total Usage": {"value": 45.2, "unit": "%"},
        }
        result = extract_core_metrics(hwinfo_raw, [])
        assert result["cpu_usage"] == 45.2

    def test_extract_cpu_usage_with_fallback_key(self):
        """测试使用备选键名提取 CPU 使用率"""
        hwinfo_raw = {
            "CPU Total": {"value": 50.0, "unit": "%"},
        }
        result = extract_core_metrics(hwinfo_raw, [])
        assert result["cpu_usage"] == 50.0

    def test_extract_gpu_usage(self):
        """测试提取 GPU 使用率"""
        hwinfo_raw = {
            "GPU Core Usage": {"value": 78.6, "unit": "%"},
        }
        result = extract_core_metrics(hwinfo_raw, [])
        assert result["gpu_usage"] == 78.6

    def test_extract_commit_memory_mb_unit(self):
        """测试提交内存提取（MB单位转换）"""
        hwinfo_raw = {
            "Commit Memory": {"value": 1024, "unit": "MB"},
        }
        result = extract_core_metrics(hwinfo_raw, [])
        assert result["commit_memory"] == 1.0  # 1024MB = 1GB

    def test_extract_commit_memory_gb_unit(self):
        """测试提交内存提取（GB单位）"""
        hwinfo_raw = {
            "Commit Memory": {"value": 2.5, "unit": "GB"},
        }
        result = extract_core_metrics(hwinfo_raw, [])
        assert result["commit_memory"] == 2.5

    def test_extract_process_metrics(self):
        """测试进程指标汇总"""
        hwinfo_raw = {}
        target_processes = [
            {"total_cpu": 10.0, "total_gpu": 5.0, "total_memory": 100},
            {"total_cpu": 15.0, "total_gpu": 3.0, "total_memory": 200},
        ]
        result = extract_core_metrics(hwinfo_raw, target_processes)
        assert result["process_cpu"] == 25.0
        assert result["process_gpu"] == 8.0
        assert result["process_memory"] == 300

    def test_extract_with_none_input(self):
        """测试空输入"""
        result = extract_core_metrics(None, None)
        assert result["cpu_usage"] is None
        assert result["gpu_usage"] is None
        assert result["commit_memory"] is None
```

- [ ] **Step 2: 运行测试**

```bash
cd backend-fastapi
source .venv/bin/activate
pytest tests/test_performance_monitor_utils.py -v
```

Expected: 所有测试通过

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/tests/test_performance_monitor_utils.py
git commit -m "test(performance-monitor): add unit tests for extract_core_metrics"
```

---

## Task 7: 前端 API 定义更新

**Files:**
- Modify: `web/apps/web-ele/src/api/core/performance-monitor.ts`

- [ ] **Step 1: 新增标记相关 API**

```typescript
// 标记 API
export function getMarkers(collectId: string) {
  return requestClient.get<MarkerResponse[]>(`/core/performance-monitor/marker/list`, { params: { collect_id: collectId } });
}

export function createMarker(data: MarkerCreate) {
  return requestClient.post<{ id: string; status: string }>(`/core/performance-monitor/marker`, data);
}

export function updateMarker(markerId: string, data: MarkerUpdate) {
  return requestClient.put<{ status: string }>(`/core/performance-monitor/marker/${markerId}`, data);
}

export function deleteMarker(markerId: string) {
  return requestClient.delete<{ status: string }>(`/core/performance-monitor/marker/${markerId}`);
}
```

- [ ] **Step 2: 新增指标映射 API**

```typescript
// 指标映射 API
export function getMetricMappings(keyword?: string, category?: string) {
  return requestClient.get<MetricMappingResponse[]>(`/core/performance-monitor/metric-mapping/list`, {
    params: { keyword, category }
  });
}

export function createMetricMapping(data: MetricMappingCreate) {
  return requestClient.post<{ id: string; status: string }>(`/core/performance-monitor/metric-mapping`, data);
}

export function updateMetricMapping(mappingId: string, data: MetricMappingUpdate) {
  return requestClient.put<{ status: string }>(`/core/performance-monitor/metric-mapping/${mappingId}`, data);
}

export function deleteMetricMapping(mappingId: string) {
  return requestClient.delete<{ status: string }>(`/core/performance-monitor/metric-mapping/${mappingId}`);
}

export function batchImportMappings(collectId: string) {
  return requestClient.post<{ imported_count: number; sensors: any[] }>(
    `/core/performance-monitor/metric-mapping/batch-import`,
    null,
    { params: { collect_id: collectId } }
  );
}
```

- [ ] **Step 3: 新增高级指标查询 API**

```typescript
// 高级指标查询
export function queryAdvancedMetrics(data: AdvancedMetricsQuery) {
  return requestClient.post<AdvancedMetricsResponse>(`/core/performance-monitor/metrics/query`, data);
}
```

- [ ] **Step 4: 新增类型定义（添加 export）**

```typescript
// 标记类型
export interface MarkerCreate {
  collect_id: string;
  name: string;
  start_time: number;
  end_time?: number;
  color: string;
  note?: string;
}

export interface MarkerUpdate {
  name?: string;
  start_time?: number;
  end_time?: number;
  color?: string;
  note?: string;
}

export interface MarkerResponse {
  id: string;
  collect_id: string;
  name: string;
  start_time: number;
  end_time?: number;
  color: string;
  note?: string;
}

// 指标映射类型
export interface MetricMappingCreate {
  hwinfo_key: string;
  display_name: string;
  category: string;
  is_primary: boolean;
  unit?: string;
}

export interface MetricMappingResponse {
  id: string;
  hwinfo_key: string;
  display_name: string;
  category: string;
  is_primary: boolean;
  unit?: string;
}

// 高级指标查询
export interface AdvancedMetricsQuery {
  collect_id: string;
  metric_keys: string[];
  start_time?: number;
  end_time?: number;
}

export interface MetricTimeSeries {
  hwinfo_key: string;
  display_name?: string;
  unit?: string;
  data: { relative_time: number; value: number }[];
}

export interface AdvancedMetricsResponse {
  metrics: Record<string, MetricTimeSeries>;
}
```

- [ ] **Step 5: Commit**

```bash
git add web/apps/web-ele/src/api/core/performance-monitor.ts
git commit -m "feat(performance-monitor): add frontend API definitions for v0.3.0"
```

---

## Task 8: ChartPanel 组件调整

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue`

- [ ] **Step 1: 改用折线图（去掉 smooth）**

```typescript
const seriesConfig = props.series.map((s) => ({
  name: s.name,
  type: 'line',
  data: s.data.map((d) => d.value),
  lineStyle: { color: s.color, width: 2 },
  itemStyle: { color: s.color },
  smooth: false,  // 改为 false，使用折线图
  symbol: 'none',
}));
```

- [ ] **Step 2: 新增标记圆点显示逻辑**

```typescript
// 在 seriesConfig 中添加标记圆点
props.markers?.forEach((marker) => {
  // 找到标记起点对应的 dataIndex
  const dataIndex = props.series[0]?.data.findIndex((d) => d.time === marker.start_time);
  if (dataIndex !== undefined && dataIndex >= 0) {
    // 在第一个 series 上添加标记点
    if (seriesConfig.length > 0) {
      seriesConfig[0].markPoint = {
        data: [
          {
            coord: [dataIndex, props.series[0].data[dataIndex].value],
            symbol: 'circle',
            symbolSize: 10,
            itemStyle: { color: marker.color, borderColor: 'white', borderWidth: 2 },
            label: {
              show: true,
              formatter: marker.name,
              position: 'top',
              color: marker.color,
              fontSize: 10,
            },
          },
        ],
      };
    }
  }
});
```

- [ ] **Step 3: 新增 Props（markers）**

```typescript
interface Props {
  // ... 原有 props
  markers?: MarkerResponse[]; // 标记列表（v0.3.0）
}
```

- [ ] **Step 4: Commit**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue
git commit -m "feat(performance-monitor): ChartPanel use line chart and show marker dots"
```

---

## Task 9: TOP10 组件调整

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/components/Top10List.vue`

- [ ] **Step 1: 改为水平柱状图布局**

```vue
<template>
  <div class="top10-list">
    <div class="top10-header">
      <span class="top10-title">进程 TOP10 排名</span>
      <span class="top10-time">时刻: {{ currentTime }}s</span>
    </div>
    <div class="top10-content">
      <div class="top10-column">
        <div v-for="(item, idx) in top5" :key="idx" class="top10-item">
          <span class="process-name">{{ item.name }}</span>
          <div class="bar-container">
            <div class="bar-fill" :style="{ width: item.percent + '%', background: item.color }">
              <span class="bar-value">{{ item.value }}%</span>
            </div>
          </div>
        </div>
      </div>
      <div class="top10-column">
        <div v-for="(item, idx) in top6to10" :key="idx" class="top10-item small">
          <span class="process-name">{{ item.name }}</span>
          <div class="bar-container">
            <div class="bar-fill" :style="{ width: item.percent + '%', background: item.color }"></div>
          </div>
          <span class="bar-value-right">{{ item.value }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.top10-list {
  background: #fff;
  border-radius: 8px;
  padding: 12px;
}
.top10-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
}
.bar-container {
  flex: 1;
  height: 20px;
  background: #f0f0f0;
  border-radius: 4px;
}
.bar-fill {
  height: 100%;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 5px;
}
.bar-value {
  color: white;
  font-size: 11px;
  font-weight: bold;
}
</style>
```

- [ ] **Step 2: 新增点击切换时刻逻辑**

```typescript
const currentTime = ref<number>(0);

// 监听父组件传入的点击时刻
watch(() => props.clickedTime, (time) => {
  if (time !== undefined) {
    currentTime.value = time;
    // 从 props.data 中找到该时刻的 TOP10
    updateTop10Data(time);
  }
});

function updateTop10Data(time: number) {
  // 找到最接近的数据
  const closestData = props.data.find((d) => d.relative_time === time) || 
    props.data.reduce((prev, curr) => 
      Math.abs(curr.relative_time - time) < Math.abs(prev.relative_time - time) ? curr : prev
    );
  
  if (closestData) {
    top5.value = closestData.top10_cpu.slice(0, 5);
    top6to10.value = closestData.top10_cpu.slice(5, 10);
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/Top10List.vue
git commit -m "feat(performance-monitor): Top10List use horizontal bar chart and click switch"
```

---

## Task 10: 时间导航条组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/TimeNavigator.vue`

- [ ] **Step 1: 创建组件**

```vue
<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';

interface Props {
  duration: number; // 总时长
  startTime?: number; // 选中的开始时间
  endTime?: number; // 选中的结束时间
}

const props = withDefaults(defineProps<Props>(), {
  startTime: 0,
  endTime: 0,
});

const emit = defineEmits<{
  (e: 'range-change', range: [number, number]): void;
}>();

const navigatorRef = ref<HTMLDivElement>();
const isDraggingLeft = ref(false);
const isDraggingRight = ref(false);
const localStartTime = ref(props.startTime);
const localEndTime = ref(props.endTime);

// 时间刻度
const timeLabels = computed(() => {
  const step = Math.ceil(props.duration / 6);
  return Array.from({ length: 7 }, (_, i) => i * step);
});

// 计算选中区间位置
const leftPercent = computed(() => (localStartTime.value / props.duration) * 100);
const rightPercent = computed(() => (localEndTime.value / props.duration) * 100);

function handleMouseDown(e: MouseEvent, side: 'left' | 'right') {
  e.preventDefault();
  if (side === 'left') {
    isDraggingLeft.value = true;
  } else {
    isDraggingRight.value = true;
  }
}

function handleMouseMove(e: MouseEvent) {
  if (!navigatorRef.value) return;
  if (!isDraggingLeft.value && !isDraggingRight.value) return;

  const rect = navigatorRef.value.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const percent = Math.max(0, Math.min(100, (x / rect.width) * 100));
  const time = Math.round((percent / 100) * props.duration);

  if (isDraggingLeft.value) {
    localStartTime.value = Math.min(time, localEndTime.value - 5);
  } else if (isDraggingRight.value) {
    localEndTime.value = Math.max(time, localStartTime.value + 5);
  }
}

function handleMouseUp() {
  if (isDraggingLeft.value || isDraggingRight.value) {
    emit('range-change', [localStartTime.value, localEndTime.value]);
    isDraggingLeft.value = false;
    isDraggingRight.value = false;
  }
}

onMounted(() => {
  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
});

onUnmounted(() => {
  document.removeEventListener('mousemove', handleMouseMove);
  document.removeEventListener('mouseup', handleMouseUp);
});

watch(() => props.startTime, (v) => localStartTime.value = v);
watch(() => props.endTime, (v) => localEndTime.value = v);
</script>

<template>
  <div class="time-navigator">
    <div class="navigator-header">
      <span class="navigator-title">时间导航</span>
      <span class="navigator-duration">采集时长: {{ duration }}s</span>
    </div>
    <div ref="navigatorRef" class="navigator-track">
      <div class="time-labels">
        <span v-for="t in timeLabels" :key="t" class="time-label">{{ t }}s</span>
      </div>
      <div class="track-background"></div>
      <div class="selected-range" :style="{ left: leftPercent + '%', width: (rightPercent - leftPercent) + '%' }">
        <div class="handle left" @mousedown="handleMouseDown($event, 'left')">
          <div class="handle-inner"></div>
        </div>
        <div class="handle right" @mousedown="handleMouseDown($event, 'right')">
          <div class="handle-inner"></div>
        </div>
      </div>
      <div class="time-tags">
        <span class="time-tag" :style="{ left: leftPercent + '%' }">{{ localStartTime }}s</span>
        <span class="time-tag" :style="{ left: rightPercent + '%' }">{{ localEndTime }}s</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.time-navigator {
  background: white;
  border: 1px solid #ddd;
  border-radius: 12px;
  padding: 15px;
}
.navigator-track {
  position: relative;
  height: 50px;
  background: linear-gradient(90deg, #f0f9ff 0%, #fff 50%, #f0f9ff 100%);
  border: 1px solid #ddd;
  border-radius: 8px;
}
.selected-range {
  position: absolute;
  top: 20px;
  height: 20px;
  background: rgba(64, 158, 255, 0.25);
  border-left: 4px solid #409eff;
  border-right: 4px solid #409eff;
  border-radius: 2px;
}
.handle {
  position: absolute;
  top: 2px;
  width: 16px;
  height: 16px;
  background: white;
  border: 2px solid #409eff;
  border-radius: 8px;
  cursor: ew-resize;
}
.handle.left { left: -8px; }
.handle.right { right: -8px; }
.handle-inner {
  width: 6px;
  height: 10px;
  background: #409eff;
  border-radius: 2px;
  margin: 2px auto;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/TimeNavigator.vue
git commit -m "feat(performance-monitor): add TimeNavigator component"
```

---

## Task 11: 标记管理组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/MarkerManager.vue`

- [ ] **Step 1: 创建组件**

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { ElDialog, ElInput, ElButton } from 'element-plus';
import { createMarker, deleteMarker, getMarkers } from '#/api/core/performance-monitor';

interface Props {
  collectId: string;
  markers: MarkerResponse[];
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'refresh'): void;
}>();

const showAddDialog = ref(false);
const newMarker = ref({
  name: '',
  start_time: 0,
  end_time: 0,
  color: '#409eff',
  note: '',
});

async function handleAddMarker() {
  await createMarker({
    collect_id: props.collectId,
    name: newMarker.value.name,
    start_time: newMarker.value.start_time,
    end_time: newMarker.value.end_time,
    color: newMarker.value.color,
    note: newMarker.value.note,
  });
  showAddDialog.value = false;
  emit('refresh');
}

async function handleDeleteMarker(markerId: string) {
  await deleteMarker(markerId);
  emit('refresh');
}
</script>

<template>
  <div class="marker-manager">
    <span class="marker-label">标记：</span>
    <span v-for="marker in markers" :key="marker.id" class="marker-tag" :style="{ borderColor: marker.color, color: marker.color }">
      {{ marker.name }} ({{ marker.start_time }}s)
      <button class="marker-delete" @click="handleDeleteMarker(marker.id)">×</button>
    </span>
    <button class="add-marker-btn" @click="showAddDialog = true">+ 添加标记</button>
    
    <ElDialog v-model="showAddDialog" title="添加标记" width="400px">
      <ElInput v-model="newMarker.name" placeholder="标记名称" />
      <ElInput v-model.number="newMarker.start_time" placeholder="开始时间（秒）" type="number" />
      <ElInput v-model="newMarker.color" placeholder="颜色（如 #409eff）" />
      <template #footer>
        <ElButton @click="showAddDialog = false">取消</ElButton>
        <ElButton type="primary" @click="handleAddMarker">确定</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.marker-manager {
  display: flex;
  align-items: center;
  gap: 10px;
}
.marker-tag {
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 12px;
  border: 1px solid;
}
.add-marker-btn {
  background: white;
  border: 1px solid #409eff;
  color: #409eff;
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 12px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/MarkerManager.vue
git commit -m "feat(performance-monitor): add MarkerManager component"
```

---

## Task 12: 高级指标面板组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/AdvancedMetrics.vue`

- [ ] **Step 1: 创建组件**

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { ElInput, ElSelect, ElButton } from 'element-plus';
import { getMetricMappings, queryAdvancedMetrics } from '#/api/core/performance-monitor';

interface Props {
  collectId: string;
}

const props = defineProps<Props>();

const keyword = ref('');
const category = ref('all');
const results = ref<MetricMappingResponse[]>([]);
const metricsData = ref<AdvancedMetricsResponse | null>(null);

async function handleSearch() {
  const cat = category.value === 'all' ? undefined : category.value;
  const mappings = await getMetricMappings(keyword.value, cat);
  results.value = mappings;
}

async function handleShowMetric(hwinfoKey: string) {
  const data = await queryAdvancedMetrics({
    collect_id: props.collectId,
    metric_keys: [hwinfoKey],
  });
  metricsData.value = data;
}
</script>

<template>
  <div class="advanced-metrics">
    <div class="metrics-header">
      <span class="metrics-title">高级指标 (hwinfo_raw 200+传感器)</span>
      <div class="metrics-controls">
        <ElInput v-model="keyword" placeholder="搜索指标" width="220px" />
        <ElSelect v-model="category">
          <ElOption label="全部分类" value="all" />
          <ElOption label="系统" value="system" />
          <ElOption label="硬件" value="hardware" />
          <ElOption label="网络" value="network" />
        </ElSelect>
        <ElButton type="primary" @click="handleSearch">搜索</ElButton>
      </div>
    </div>
    <div class="metrics-results" v-if="results.length">
      <div v-for="m in results" :key="m.id" class="metric-item" @click="handleShowMetric(m.hwinfo_key)">
        <span class="metric-name">{{ m.display_name }}</span>
        <span class="metric-unit">{{ m.unit }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.advanced-metrics {
  background: linear-gradient(135deg, #f0f9ff 0%, #e8f4ff 100%);
  border: 1px solid #409eff;
  border-radius: 8px;
  padding: 12px;
}
.metrics-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.metrics-results {
  margin-top: 10px;
  display: flex;
  gap: 10px;
}
.metric-item {
  background: white;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/AdvancedMetrics.vue
git commit -m "feat(performance-monitor): add AdvancedMetrics component"
```

---

## Task 13: 主页面布局调整

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/index.vue`

- [ ] **Step 1: 导入新组件**

```typescript
import TimeNavigator from './components/TimeNavigator.vue';
import MarkerManager from './components/MarkerManager.vue';
import AdvancedMetrics from './components/AdvancedMetrics.vue';
```

- [ ] **Step 2: 调整布局结构**

```vue
<template>
  <div class="performance-monitor">
    <!-- 顶部控制区 -->
    <div class="control-panel">...</div>
    
    <!-- 时间导航条 -->
    <TimeNavigator :duration="duration" :start-time="rangeStart" :end-time="rangeEnd" @range-change="handleRangeChange" />
    
    <!-- 标记管理 -->
    <MarkerManager :collect-id="collectId" :markers="markers" @refresh="loadMarkers" />
    
    <!-- CPU 使用率图表（一行一个） -->
    <ChartPanel title="CPU使用率" :series="cpuSeries" :markers="markers" :raw-data="rawData" chart-type="cpu" />
    
    <!-- GPU 使用率图表 -->
    <ChartPanel title="GPU使用率" :series="gpuSeries" :markers="markers" :raw-data="rawData" chart-type="gpu" />
    
    <!-- TOP10 进程排名 -->
    <Top10List :data="rawData" :clicked-time="clickedTime" />
    
    <!-- 提交内存图表 -->
    <ChartPanel title="提交内存" :series="commitMemorySeries" :markers="markers" :raw-data="rawData" chart-type="commitMemory" />
    
    <!-- 进程内存图表 -->
    <ChartPanel title="进程内存" :series="processMemorySeries" :markers="markers" :raw-data="rawData" chart-type="memory" />
    
    <!-- 高级指标面板 -->
    <AdvancedMetrics :collect-id="collectId" />
  </div>
</template>
```

- [ ] **Step 3: 新增点击图表切换时刻逻辑**

```typescript
const clickedTime = ref<number>(0);

function handlePointClick(data: { time: number; collectId: string }) {
  clickedTime.value = data.time;
}
```

- [ ] **Step 4: 新增标记加载逻辑**

```typescript
const markers = ref<MarkerResponse[]>([]);

async function loadMarkers() {
  if (collectId.value) {
    const res = await getMarkers(collectId.value);
    markers.value = res;
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add web/apps/web-ele/src/views/performance-monitor/index.vue
git commit -m "feat(performance-monitor): adjust layout to one chart per row"
```

---

## Task 14: 验收测试

- [ ] **Step 1: 启动后端服务**

```bash
cd backend-fastapi
source .venv/bin/activate
python main.py
```

Expected: 后端服务启动成功，API 可访问

- [ ] **Step 2: 启动前端服务**

```bash
cd web
pnpm dev
```

Expected: 前端服务启动成功，页面可访问

- [ ] **Step 3: 测试 Worker 上报 hwinfo_raw**

使用 Postman 或 curl 测试：
```bash
curl -X POST http://localhost:8000/api/core/performance-monitor/report \
  -H "Content-Type: application/json" \
  -d '{"collect_id":"xxx","device_id":"xxx","samples":[{"timestamp":"2026-05-09T10:00:00Z","relative_time":0,"hwinfo_raw":{"CPU Total Usage":{"value":45.2,"unit":"%"}},...}]}'
```

Expected: 数据成功存储，hwinfo_raw 字段有值

- [ ] **Step 4: 测试核心指标提取**

查询数据库：
```sql
SELECT cpu_usage, gpu_usage FROM performance_data WHERE collect_id = 'xxx' LIMIT 1;
```

Expected: cpu_usage 和 gpu_usage 字段有值（从 hwinfo_raw 提取）

- [ ] **Step 5: 测试前端界面**

打开浏览器访问 http://localhost:5173/performance-monitor
Expected: 
- 时间导航条可拖拽
- 图表使用折线图样式
- 标记圆点显示在折线上
- TOP10 柱状图布局
- 高级指标面板可搜索

---

## Task 15: 最终 Commit

```bash
git add -A
git commit -m "feat(performance-monitor): complete v0.3.0 upgrade - hwinfo_raw storage and UI redesign"
```