# 平台后端架构重构方案：API 层下沉 / 设备状态收敛 / 后台机制统一

- 日期：2026-09-05
- 状态：**待评审**（评审通过后再写实施计划与动工）
- 范围：`zq-platform/backend-fastapi`（不动 testcase，不动前端）
- 性质：**行为不变的结构重构**——不改 API 契约、不改 Redis key、不改 DB schema、不加新锁

---

## 0. 勘察结论（方案的事实基础）

### 0.1 勘察中的新发现（先于报告原条目，影响方案优先级）

**`GUNICORN_WORKER_ID` 从未被设置，"仅主 worker"约定实际失效。**
`main.py:46` 用 `os.environ.get("GUNICORN_WORKER_ID")` 判断主 worker，`start.sh:10` 的注释声称"gunicorn 在 fork worker 之前会设置 GUNICORN_WORKER_ID"——但 gunicorn 原生**不导出**这个环境变量，仓库里也没有任何 gunicorn.conf.py 或 hook 设置它。因此：

- 单进程模式（默认 `WORKERS=1`）一切正常；
- 一旦有人把 `WORKERS` 调到 >1，**每个 worker 都判定自己是主 worker**：APScheduler 离线检测/超时释放/队列清理全部 ×N 重复执行（APScheduler 用的是 `MemoryDataStore`，`core/scheduler/service.py:626-629`，各 worker 内存里各跑一份，互相不知情），命令任务对账、导出清理、重启重载同样 ×N。
- 这正是审查报告"三套后台机制并存 + 仅 worker0 跑调度器的环境变量约定，多副本部署易踩坑"的实锤形态，且比"约定易踩坑"更严重：**现状是踩坑开关已经埋好**，只等调大 WORKERS。

### 0.2 API 层过胖的实际分布

16 个 `core/**/api.py` 共 7953 行。脂肪集中在四个文件，且性质一致——**worker 通信编排写在路由层**：

| 文件 | 行数 | 路由层里的非路由逻辑 |
|---|---|---|
| `core/env_machine/api.py` | 1437 | register 路由 ~200 行（219-418，DB/缓存对账编排内联）；debug-action 路由 ~300 行（940-1245）；21 条路由 |
| `core/performance_monitor/api.py` | 841 | SSH 连接池操作内联（253-262）；httpx 直调 ×3；3 处 BackgroundTasks 传编排闭包 |
| `core/scheduler/api.py` | 798 | 定时任务 CRUD 与 APScheduler 交互内联 |
| `core/config_template/api.py` | 778 | `_execute_command_deploy`(192) / `_execute_commands_async`(273) / `_execute_single_command`(310) / `_interpret_task_poll`(389) / `_wait_task_result`(441) 共约 400 行 worker 编排；httpx 直调 ×2 |
| `core/config_template/public_api.py` | 323 | `_execute_script_deploy_async`(189) / `_execute_single_script`(258) 脚本下发编排 |

同时项目**已有成熟的 service 层惯例**：19 个 `service.py`（performance_monitor 1832 行、env_machine 978 行、config_template 644 行……），路由调 service 是既有模式；`app/database.py:45` 的 `get_db_transaction` 事务边界工具写好了但 core/ 下**零引用**（报告第 4 条属实）。问题不是缺分层，而是**新增的 worker 通信代码没有跟着惯例走**。

### 0.3 设备状态三处分散的实际形态

三份存储：

1. **DB**：`EnvMachine.status`（online/using/offline/upgrading，`model.py:67`）+ `available` + `config_status`；
2. **Redis 池缓存**：`EnvPoolManager` 的 namespace 池 hash。缓存准入规则本身设计良好且幂等——`sync_machine_to_cache`（`pool_manager.py:213-261`）按 `available && online && !deleted && !manual` 决定加/删，是一个标准的"只可分配机器读模型"；
3. **进程内存**：`_collect_tasks` dict（`linux_collector.py:588`，带 `_task_lock`）、SSH 连接池、WebSocket 监控任务。这份只服务采集/调试自身生命周期，与机器分配状态无耦合，**不需要合并**。

真正的问题在**写路径**：全库 12+ 处直接 `machine.status = X` 后各自决定调用哪个缓存函数——`sync_machine_to_cache` / `remove_machine_from_cache` / `batch_sync_cache` 三种收尾散见各处：

| 写点 | 状态写入 | 缓存收尾 |
|---|---|---|
| allocate（`pool_manager.py:598,626`） | `="using"` | remove |
| release（`pool_manager.py:681,687`） | `="online"` | sync |
| keepusing（`api.py:491-534`） | 只更新 last_keepusing_time | — |
| register（`api.py:187-188,292-300,311,364-383,408`） | 各分支手写 | sync/remove 混用 |
| 新增/编辑/删除（`api.py:666-704,793-810,1303-1325`） | 手写 | sync/remove |
| 批量启用/停用（`api.py:1360-1425`） | 手写 | sync |
| 升级（`upgrade_api.py:95-100`、`upgrade_service.py:343,514`） | `="upgrading"` | remove |
| 离线检测（`scheduler.py:239,263,275` + `batch_sync_cache`） | 直接 `machine.status="offline"` | batch_sync |
| 超时释放（`scheduler.py:139-145`） | 复用 release_machine | sync（好例子） |

没有任何状态转移合法性校验（任意调用方可把 using 写成 online 而不经过 release 语义）；DB 提交与缓存同步是两步非原子操作，中间失败即漂移，"一致性靠约定"属实。`pool_manager.update_machine_status`（719）虽是通用写入口，但大量调用方绕过它直接改属性。

（注：此前已明确 **release/keepusing 不加锁、不做归属校验**（H-1，用户决定）。本方案尊重该决定，收敛写路径不等于引入新锁。）

### 0.4 三套后台机制的实际清单

| 机制 | 使用点 | 问题 |
|---|---|---|
| **APScheduler**（`core/scheduler/service.py` 单例，MemoryDataStore） | env_machine/scheduler.py 3 个 job（离线检测 / 超时释放 / 升级队列清理），scheduler 模块自身的定时任务 | 仅靠失效的 `is_main_worker` 防重复；MemoryDataStore 使多 worker 必然重复 |
| **手写 while True 循环** | `main.py:117-127` cleanup_export_loop（每小时，异常仅 log 不退出不重启）；`utils/permission.py:317-340` pubsub listener（有 5s 重连退避，设计尚可） | 与 APScheduler 的"周期任务"职责重叠，标准不一 |
| **spawn_background_task**（一次性） | 命令/脚本部署 ×2、重启重载、Linux 采集循环 | 用法正确（M-5 已治理），保留 |
| **FastAPI BackgroundTasks** | performance_monitor 3 条路由（collect/start、collect/stop、export/create）响应后通知 worker / 触发导出 | 用法正确（响应后轻量通知是该机制的正当用途），保留 |

四种机制里真正需要收敛的是**周期任务**：APScheduler 与手写 while True 并存；以及**选举**：is_main_worker 失效（见 0.1）。

---

## 1. 方案设计（按工作流，各带选项与推荐）

### 工作流 A：worker 通信编排下沉到 service 层

**A1（推荐）：WorkerClient + 部署编排下沉**

新建两个文件：

- `core/config_template/worker_client.py`——`WorkerClient` 类，封装对 Worker 的全部 HTTP 通信：下发命令、查询任务结果（`_interpret_task_poll` / `_wait_task_result` 原样迁入）、脚本下发、错误消息映射（`_worker_http_error_message` 迁入）。httpx.AsyncClient 只在这个文件出现。
- `core/config_template/deploy_service.py`——`CommandDeployService` / `ScriptDeployService`，编排逻辑（`_execute_commands_async` / `_execute_single_command` / `_execute_script_deploy_async` / `_execute_single_script` / `_execute_command_deploy` 的业务部分）迁入，复用现有 `command_task_service` 做任务记录。

改造路由：`api.py` 与 `public_api.py` 的路由只保留 参数解析 → 建/查任务记录（service）→ 组响应；env_machine 的 register 对账逻辑迁入 `env_machine/service.py`（该文件已 978 行，只迁 register 相关函数，不新建文件）；performance_monitor 的 SSH 测试连接编排迁入其现有 service.py。

- 兼容性：`_interpret_task_poll` 是纯函数，`tests/test_command_task_polling.py` 只改 import 路径，断言零修改——这是行为不变的锚点。
- 不做的事：不动 auth/dept/role/user 等 CRUD 模块（它们已有 service 层，不肥）；不引入 repository 基类（YAGNI）；不在本轮强推 `get_db_transaction`（事务边界统一单独立项，见 §4 待决点 2）。

**A2（放弃）：全模块统一仓储/CQRS 层** —— 收益不匹配改动面，纯 CRUD 模块没有编排可下沉。
**A3（放弃）：私有函数平移到 utils/** —— 治标，httpx 依赖与任务记录事务仍散在调用方。

### 工作流 B：设备状态写路径收敛（唯一写入口）

**B1（推荐）：MachineStateService.transition() 唯一写入口**

新建 `core/env_machine/state_service.py`：

```
transition(db, machine, to_status, *, source) -> TransitionResult
```

- 内置**状态转移表**（唯一新增的业务规则）：online→using（allocate）、using→online（release/超时释放）、online/offline→upgrading、upgrading→online/offline、online→offline（离线检测）、任意→offline 之外不允许的转移直接拒绝并告警日志。转移表本身是纯数据，先写测试。
- 内部流程：校验转移合法性 → 写 `machine.status` → **统一调用 `sync_machine_to_cache`**（其幂等规则现成，加/删一个函数搞定，不再区分三个收尾函数）→ 结构化日志（from_status/to_status/source）。
- 改造全部 12+ 写点为调用 transition（对应 0.3 表格逐条迁移）；`pool_manager.update_machine_status` 保留签名、内部委托 transition（外部调用方零感知），直接赋值从此只存在于 state_service.py。
- 明确不加锁：transition 不引入分布式锁，release/keepusing 并发语义与现状完全一致（尊重 H-1 决定）；它消除的是"忘同步缓存/转移非法"这类约定漂移，不是并发竞争。
- 进程内 `_collect_tasks` 等内存态**不纳入**（0.3 已论证无耦合）。

**B2（放弃）：事件溯源/outbox 保证 DB-Redis 原子** —— 引入基础设施，收益不成比例。
**B3（放弃）：只补测试不改结构** —— 散写点继续增长，约定继续漂移。

### 工作流 C：后台机制统一 + 主 worker 选举修复

**C1（推荐）：Redis 领导权租约 + 周期任务归一**

1. **选举修复（本工作流的核心，可独立先行）**：删掉 `GUNICORN_WORKER_ID` 约定。`scheduler_service.init_scheduler()` 启动前先经 `LockManager`（M-3 已实现 SET NX + Lua 续期，直接复用）抢**调度器领导权锁**：抢到 → 启动 APScheduler 并持有租约；未抢到 → 本 worker 不启动 job 并记日志；租约丢失（续期失败）→ 自动 stop 调度器。单进程 / 多 worker / 跨机多副本通吃，无需 gunicorn hook 配合。
2. **cleanup_export_loop 改造成 APScheduler 小时级 job**（消灭一个手写 while True；命令任务对账本来就是启动一次性逻辑，保留 spawn_background_task 不动）。
3. **permission pubsub listener 保留**专用循环（长连接监听不是周期任务，已有重连退避），仅在 `utils/background_tasks.py` 补一个"常驻循环守护"注释规范。
4. **四种机制选用准则写进 `docs/backend-background-tasks.md`**：周期任务=APScheduler（须持领导权锁）；请求触发一次性编排=spawn_background_task；响应后轻量通知=BackgroundTasks；长连接监听=专用 listener 模块。

**C2（放弃）：引入 arq/celery 任务队列** —— 运维成本与规模不匹配。
**C3（放弃）：只补 gunicorn.conf.py 修正环境变量** —— 治标：跨机多副本部署依旧重复；且续期/失联自愈能力为零。

---

## 2. 实施顺序与风险控制

| Phase | 内容 | 风险 | 控制手段 |
|---|---|---|---|
| 1 | C-1 领导权租约 + C-2 导出清理归一 | 低（只影响启动路径，单 worker 行为不变） | 日志验证"仅一个调度器启动"；单进程冒烟 + 模拟双进程抢锁测试 |
| 2 | A 编排下沉 | 低（机械搬家，纯函数测试锚定） | test_command_task_polling 零断言修改；新增 WorkerClient 错误映射测试 |
| 3 | B 状态收敛 | 中（触碰分配/释放路径） | 转移表先测后接；逐写点迁移逐写点验证；全量回归 + 手工冒烟 allocate/release/register/离线检测 |

- 每个 Phase 独立提交（`refactor:` 前缀 + 中文描述），可独立回滚。
- 全程不改 API 契约、Redis key、DB schema；现有 62 个测试 + 新增测试全绿；`python -c "import main"` 冒烟。

## 3. 验收标准

1. `core/**/api.py` 中不再出现 `httpx.AsyncClient` 直调；`_execute_*` / `_wait_task_result` 等编排函数不在路由文件中。
2. `machine.status` 直接赋值仅存在于 `state_service.py`（`pool_manager.update_machine_status` 委托 transition，不含直接赋值）；grep 可验证。
3. 多 worker 模式下 APScheduler job、命令对账、导出清理各自仅一份在执行（领导权日志可查）。
4. 状态转移表有覆盖全转移的回归测试；全量测试通过。

## 4. 待评审决策点

1. **B 的写点迁移范围**：是否包含 `env_machine/api.py` 的 debug-action（~300 行，属 A 范畴但体量大）？建议本轮一并下沉（A、B 都要动它附近代码，一次到位）。
2. **事务边界**（报告第 4 条）：本轮仅将 service 层统一为"service 提交、路由不 commit"的约定并在新代码遵守，存量路由不动；还是完全不动？建议前者。
3. **重启重载单 session 问题**（报告 Low#4，`scheduler.py:438-565` 数分钟占连接）：建议纳入 Phase 1 顺手分批化（改动小、与领导权同文件），或明确不做。
4. **领导权锁 TTL/续期参数**：建议 TTL 30s / 续期间隔 10s，与 M-3 业务锁一致。
