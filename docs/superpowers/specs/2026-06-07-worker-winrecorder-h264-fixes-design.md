# Worker + Win-Recorder H264 推流问题修复设计

**日期**: 2026-06-07
**状态**: 已批准

## 1. 问题汇总

| # | 问题 | 根因 | 影响 |
|---|------|------|------|
| 1 | encode_frame() 返回 None | 未实现内存输出，MFCreateMemoryBuffer | 前端无 H264 数据 |
| 2 | mss 跨线程访问失败 | mss 内部使用 thread.local()，跨线程 srcdc 丢失 | BGRA 获取失败 |
| 3 | 前端未降级到 JPEG | encode_frame() 返回 None 时没有触发降级 | 无画面显示 |
| 4 | BGRA 错误日志刷屏 | get_frame_bgra() 无重试限制，直接抛异常 | 日志污染 |
| 5 | MSS 复用问题 | 跨线程访问导致 | 资源浪费 |

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      ScreenManager                              │
│                                                                  │
│  消费者计数: _active_consumers                                  │
│                                                                  │
│  _capture_loop (单一线程，按需启动)                              │
│         │                                                       │
│         └── get_frame_bgra() → BGRA                            │
│                    │                                            │
│                    ├── 队列: BGRA                               │
│                           │                                     │
│         ┌────────────────┼────────────────┐                    │
│         │                │                │                    │
│         ▼                ▼                ▼                    │
│    录制消费          推流消费          截图消费                  │
│    (录制线程)       (WS线程)         (HTTP线程)                 │
│                                                                  │
│  延迟释放机制:                                                    │
│  - 消费者离开后启动 60s 定时器                                   │
│  - 60s 内有新消费者加入 → 取消定时器                             │
│  - 60s 后无消费者 → 停止 _capture_loop，释放 MSS                │
└─────────────────────────────────────────────────────────────────┘
```

## 3. 解决方案

### 问题 1: encode_frame() 返回 None

**方案**: 实现 MFCreateMemoryBuffer 内存输出

**需要修改的文件**:
- `win-recorder/src/mf_writer.rs`: 添加内存输出接口
- `win-recorder/src/streaming_encoder.rs`: 使用内存输出替代临时文件

**核心改动**:
```rust
// 使用 IMFMediaBuffer + MFCreateMemoryBuffer
let buffer: IMFMediaBuffer = MFCreateMemoryBuffer(output_size)?;
// 将编码数据写入内存 buffer
// 返回编码数据给 Python 层
```

### 问题 2 & 5: mss 跨线程访问 + MSS 复用

**方案**: 统一在 `_capture_loop` 获取 BGRA，其他线程从队列消费

**需要修改的文件**:
- `worker/screen/manager.py`: 
  - 新增 BGRA 队列
  - 统一获取 BGRA
  - 添加消费者计数
  - 添加延迟释��机制

**核心改动**:
```python
class ScreenManager:
    def __init__(self, frame_source, device_id):
        self._bgra_queue: Queue[bytearray] = Queue(maxsize=30)
        self._active_consumers = 0
        self._release_timer = None
        self._release_delay = 60
        
    def _ensure_capture_running(self):
        self._cancel_release()
        with self._consumers_lock:
            self._active_consumers += 1
            if self._active_consumers == 1:
                self.start_capture()
                
    def _release_capture(self):
        with self._consumers_lock:
            self._active_consumers -= 1
            if self._active_consumers == 0:
                self._schedule_release()
```

### 问题 3: 前端降级到 JPEG

**方案**: worker 检测 H264 编码失败，连续 N 次后降级

**需要修改的文件**:
- `worker/screen/h264_streamer.py`: 添加降级逻辑和回调
- `worker/screen/streamer.py`: 添加降级回调处理

**核心改动**:
```python
class H264Streamer:
    def __init__(self, ...):
        self._consecutive_failures = 0
        self._max_failures = 30  # 连续 30 帧失败（约3秒）触发降级
        self._on_fallback = None
        
    def get_frame(self):
        # ... 编码逻辑
        if not encoded:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._max_failures:
                self._trigger_fallback()
                
    def _trigger_fallback(self):
        if self._on_fallback:
            self._on_fallback()
```

### 问题 4: BGRA 获取失败日志刷屏

**方案**: 
1. 在 `get_frame_bgra()` 添加重试计数
2. 在 `_capture_loop` 添加熔断机制

**核心改动**:
```python
def _capture_loop(self):
    consecutive_errors = 0
    max_errors = 10  # 连续 10 次失败则停止
    
    while self._running:
        try:
            bgra = self._frame_source.get_frame_bgra()
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors >= max_errors:
                logger.error(f"Capture failed {max_errors} times, stopping")
                break
            time.sleep(0.5)  # 错误后延迟
```

## 4. 文件变更清单

| 文件 | 变更 |
|------|------|
| `win-recorder/src/mf_writer.rs` | 修改：添加内存 buffer 接口 |
| `win-recorder/src/streaming_encoder.rs` | 修改：实现 MFCreateMemoryBuffer 内存输出 |
| `worker/screen/manager.py` | 修改：BGRA 队列、消���者计数、延迟释放、重试熔断 |
| `worker/screen/h264_streamer.py` | 修改：降级逻辑 |
| `worker/screen/streamer.py` | 修改：降级回调 |
| `worker/platforms/windows.py` | 修改：截图改走 ScreenManager |
| `worker/platforms/mac.py` | 修改：截图改走 ScreenManager |
| `worker/platforms/ios.py` | 修改：截图改走 ScreenManager |
| `worker/platforms/android.py` | 修改：截图改走 ScreenManager |

## 5. 预期效果

| 指标 | 改进前 | 改进后 |
|------|--------|--------|
| H264 推流 | 无数据（返回 None） | 正常推送 H264 流 |
| mss 跨线程 | 报错 srcdc 丢失 | 单一线程，无跨线程问题 |
| 前端降级 | 无降级，卡住 | 连续失败后自动降级 JPEG |
| 错误日志 | 刷屏 | 限制频率，有熔断 |
| 资源释放 | 无 | 60s 延迟释放 |
| 截图 | 直接调用 MSS（跨线程） | 走队列（无跨线程） |