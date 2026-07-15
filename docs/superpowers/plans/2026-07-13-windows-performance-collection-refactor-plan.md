# Windows 性能采集重构详细实施计划

## 目标与边界

一次性完成 Windows 性能采集链路重构，不考虑老版本 Worker 过渡。系统 CPU/GPU 由 Rust 主采集，HWiNFO 保留为 GPU 运行时回退和温度、功耗、频率等扩展传感器。采样横轴由 Rust `Instant` 生成的 `elapsed_ms` 驱动，平台不再依赖跨机器墙上时钟。

涉及仓库：`D:\code\perfwin`、`D:\code\autotest`、`D:\code\zq-platform`。

## 已完成的代码改造

### A. Rust/perfwin

- 版本统一为 `0.4.0`。
- `Sample` 增加 `sequence`、`elapsed_ms`、`system`。
- 系统 CPU 使用 `sysinfo.global_cpu_usage()`。
- PDH 使用 GPU Engine 利用率计数器，按 PID/适配器/引擎聚合进程 GPU，按适配器聚合系统 GPU。
- DXGI 枚举适配器名称并按 LUID 关联。
- PDH 正常空闲返回 0；连续失败后 HWiNFO GPU 回退；完全不可用返回 null。
- PyO3 和 Worker 字典输出保持字段一致。

### B. Worker/autotest

- 启动冲突、启动异常、停止 ID 不匹配映射为明确 HTTP 业务错误。
- 正常停止、超时、采集线程异常发送平台终态事件。
- 停止时不在锁内等待采集线程，增加 stopping 状态防止新任务覆盖。
- 样本透传 `sample_key/sequence/elapsed_ms/system`。
- JSONL spool 增加 fsync、原子替换、重启扫描和批量重试。

### C. 平台后端与前端

- 采集状态、心跳、失败信息和最后序号字段已补齐。
- 样本按 `sample_key` 幂等，按 `elapsed_ms` 查询和排序，校验设备归属。
- 新增 Worker 终态事件 API 和 `f9b0c1d2e3f4` 迁移。
- CPU/GPU 图表使用 Rust 系统指标，null 显示为 `-`，GPU 来源可见。
- 主图/目标进程/TOP10 做了响应式排版调整。

## 下一阶段执行计划

### 阶段 1：数据库与发布物

1. 确认 `backend-fastapi` 实际数据库连接目标和测试库备份。已确认开发库目标。
2. 在开发库执行 `upgrade head`。已完成。
3. 核对采集记录数、样本数、历史回填 sequence 和毫秒时间。待补数据核对。
4. 在开发库执行 downgrade/upgrade 回归。待执行。
5. 在 `perfwin` 构建 release wheel，检查包版本和 PyO3 输出。已完成。
6. 安装到 `D:\code\autotest\venv`，确认实际 import 路径和版本为 0.4.0。已完成。

### 阶段 2：Windows GPU 硬件矩阵

按以下顺序验证，每台机器保存原始样本、GPU 来源和适配器信息：

1. Intel 核显单显卡。
2. AMD 核显单显卡。
3. NVIDIA 独显。
4. AMD 独显。
5. 核显加 NVIDIA/AMD 独显混合机器。
6. 空闲 GPU：确认 PDH 来源仍有效且值为 0。
7. 3D、视频解码、视频编码、Compute 负载：确认适配器和引擎聚合不超过 100。
8. 禁用/缺失 PDH：确认 HWiNFO 回退。
9. PDH 和 HWiNFO 都不可用：确认系统 GPU 为 null 且页面显示不可用。

重点记录：显卡名称、LUID、物理索引、`gpu_source`、适配器列表、负载类型和任务管理器对照值。

### 阶段 3：采集流程端到端

1. 前端开始采集，确认平台 `starting`、Worker 接受后首批样本和平台 `running`。
2. 重复提交相同 `collect_id`，确认幂等；提交不同任务，确认 409 冲突。
3. 重复上报同一批次，确认样本数不增加。
4. 乱序上报，确认查询按 `elapsed_ms` 排序且最后序号不回退。
5. 用户停止，确认平台 `stopping -> stopped`。
6. Monitor 超时，确认平台 `timed_out`。
7. Worker 采集线程异常，确认平台 `failed`。
8. 采集中断网，确认 JSONL spool 留存；恢复网络后补传无重复。
9. Worker 重启，确认 spool 扫描和平台终态不永久卡住。
10. 平台与 Worker 时钟相差至少 10 分钟，确认图表横轴仍从 0 开始。
11. 采集中修改系统时间，确认 `elapsed_ms` 单调不跳变。

### 阶段 4：页面验收与后续 UI 改版

1. 在 1920x1080、1440x900、1280x720、1024x768、390x844 截图。
2. 检查顶部设备/任务控制不溢出，主图和底部面板不遮挡。
3. 检查 Rust PDH、HWiNFO 回退、不可用、等待首样本和终态错误显示。
4. 检查 CPU/GPU null 点 tooltip、详情面板和比较页摘要显示 `-` 或空点。
5. 若历史弹窗仍影响连续操作，再实施可折叠历史侧栏；否则保持当前改动，避免扩大范围。

## 自动化验证清单

- `perfwin`：`cargo check`、`cargo test`、`cargo fmt --check`、release wheel。
- `autotest`：激活 `venv` 后执行 Python 语法检查和性能采集专项测试。
- `backend-fastapi`：激活 `.venv` 后执行性能模块测试、迁移 upgrade/downgrade/upgrade。
- `web`：执行性能监控页面相关 typecheck、构建和浏览器截图检查。

## 当前明确阻塞项

- 开发库 Alembic upgrade 已完成，downgrade/upgrade 回归尚未执行。
- 当前环境没有核显/混合显卡硬件矩阵可供验证。
- release wheel 已构建，Worker venv 已安装并确认版本为 0.4.0。
- Worker spool 仍是 JSONL，SQLite 确认队列、磁盘上限、连续确认和指数退避属于后续增强项。
- 全仓库前端存在与性能监控无关的既有 typecheck 错误，需单独治理。