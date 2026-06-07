# Worker 端 H264 推流问题修复实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 worker 端 H264 推流问题：统一 BGRA 队列、消费者计数、延迟释放、降级逻辑、截图改造

**Architecture:** 统一在 `_capture_loop` 获取 BGRA，消费者从队列消费；添加消费者计数和 60s 延迟释放机制

**Tech Stack:** Python, asyncio, threading, mss

---

## 背景

当前问题：
1. mss 跨线程访问导致 `srcdc` 丢失
2. 截图直接调用 MSS，跨线程问题
3. H264 编码失败时无降级
4. BGRA 获取失败日志刷屏

---

## Task 1: 重构 ScreenManager - BGRA 队列和消费者计数

**Files:**
- Modify: `/Users/ma/Documents/autotest/worker/screen/manager.py`

### 现有代码分析

当前 `manager.py` 结构：
- `_frame_queue: Queue[bytes]` - 存储 JPEG 帧
- `_capture_loop()` - 获取 JPEG 帧并放入队列
- `get_frame()` - 从队列获取 JPEG

### 需要修改的内容

1. 新增 BGRA 队列 `_bgra_queue: Queue[bytearray]`
2. 修改 `_capture_loop` 获取 BGRA 而非 JPEG
3. 添加消费者计数 `_active_consumers`
4. 添加延迟释放定时器 `_release_timer`
5. 添加 `_ensure_capture_running()` 和 `_release_capture()` 方法
6. 修改 `get_frame_bgra()` 从 BGRA 队列获取
7. 添加 `get_frame_jpeg()` 从 BGRA 转换

- [ ] **Step 1: 添加新字段**

在 `ScreenManager.__init__()` 中添加：

```python
class ScreenManager:
    def __init__(self, frame_source: FrameSource, device_id: str = ""):
        # ... 现有字段 ...
        
        # 新增：BGRA 队列（统一存储 BGRA 帧）
        self._bgra_queue: Queue[bytearray] = Queue(maxsize=30)
        
        # 新增：消费者计数
        self._active_consumers: int = 0
        self._consumers_lock: threading.Lock = threading.Lock()
        
        # 新增：延迟释放定时器
        self._release_timer: Optional[threading.Timer] = None
        self._release_delay: float = 60.0  # 60 秒
        
        # 新增：BGRA→JPEG 转换缓存
        self._jpeg_cache: Optional[bytes] = None
        self._jpeg_cache_time: float = 0
        self._jpeg_cache_ttl: float = 0.5  # 缓存 500ms
```

- [ ] **Step 2: 修改 _capture_loop 获取 BGRA**

修改 `_capture_loop()` 方法：

```python
def _capture_loop(self) -> None:
    """后台截图循环（统一获取 BGRA）"""
    consecutive_errors = 0
    max_consecutive_errors = 10  # 连续错误阈值
    
    while self._running:
        try:
            # 统一获取 BGRA
            bgra = self._frame_source.get_frame_bgra()
            consecutive_errors = 0
            
            if self._bgra_queue.full():
                try:
                    self._bgra_queue.get_nowait()
                except Empty:
                    pass
            self._bgra_queue.put(bgra, timeout=1)
            
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors == 1:
                logger.warning(f"BGRA capture error: {e}")
            elif consecutive_errors >= max_consecutive_errors:
                logger.error(f"BGRA capture failed {max_consecutive_errors} times, stopping")
                if _on_capture_failed and self._device_id:
                    _on_capture_failed(self._device_id)
                break
            if consecutive_errors >= 3:
                time.sleep(0.5)
```

- [ ] **Step 3: 添加消费者计数方法**

添加以下方法：

```python
def _ensure_capture_running(self) -> None:
    """确保截图线程运行（消费者加入时调用）"""
    # 先取消可能的释放定时器
    if self._release_timer:
        self._release_timer.cancel()
        self._release_timer = None
        logger.info("Capture release cancelled")
    
    with self._consumers_lock:
        self._active_consumers += 1
        if self._active_consumers == 1:
            self.start_capture()

def _release_capture(self) -> None:
    """标记消费者离开，触发延迟释放"""
    with self._consumers_lock:
        self._active_consumers -= 1
        if self._active_consumers == 0:
            self._schedule_release()

def _schedule_release(self) -> None:
    """安排延迟释放"""
    if self._release_timer:
        self._release_timer.cancel()
    
    self._release_timer = threading.Timer(
        self._release_delay,
        self._do_release
    )
    self._release_timer.daemon = True
    self._release_timer.start()
    logger.info(f"Schedule capture release in {self._release_delay}s")

def _do_release(self) -> None:
    """执行释放"""
    with self._consumers_lock:
        if self._active_consumers > 0:
            return  # 已被其他消费者占用
    
    logger.info("No consumers for 60s, releasing capture resources")
    self.stop_capture()
```

- [ ] **Step 4: 修改 get_frame_bgra() 从队列获取**

```python
def get_frame_bgra(self, max_retries: int = 3) -> bytearray:
    """从队列获取 BGRA（供录制/H264）"""
    last_error = None
    for attempt in range(max_retries):
        try:
            return self._bgra_queue.get(timeout=1)
        except Empty:
            last_error = "Queue empty"
        except Exception as e:
            last_error = str(e)
    
    logger.error(f"get_frame_bgra failed after {max_retries} attempts: {last_error}")
    return bytearray()
```

- [ ] **Step 5: 添加 get_frame_jpeg() 方法**

```python
def get_frame_jpeg(self) -> bytes:
    """从队列获取 BGRA 并转换为 JPEG（供推流/截图）"""
    import io
    from PIL import Image
    import numpy
    
    # 获取 BGRA
    bgra = self.get_frame_bgra()
    if not bgra:
        return self._frame_source.get_blank_frame()
    
    # BGRA → PIL Image
    # BGRA 格式：每个像素 4 字节 (B, G, R, A)
    width, height = self._frame_source.get_screen_size()
    
    # 转换为 RGB（使用 numpy 避免循环）
    bgra_array = numpy.frombuffer(bgra, dtype=numpy.uint8).reshape(height, width, 4)
    rgb_array = bgra_array[:, :, 2::-1]  # BGRA → RGB
    
    # 转为 JPEG
    img = Image.fromarray(rgb_array)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()
```

- [ ] **Step 6: 修改 stop() 方法**

```python
def stop(self) -> None:
    """停止所有资源"""
    # 取消延迟释放定时器
    if self._release_timer:
        self._release_timer.cancel()
        self._release_timer = None
    
    self._running = False
    if self._capture_thread and self._capture_thread != threading.current_thread():
        self._capture_thread.join(timeout=5)
    
    # ... 其他清理 ...
```

- [ ] **Step 7: 提交**

```bash
cd /Users/ma/Documents/autotest
git add worker/screen/manager.py
git commit -m "refactor(worker): add BGRA queue and consumer counting with delayed release"
```

---

## Task 2: 修改录制/推流使用消费者计数

**Files:**
- Modify: `/Users/ma/Documents/autotest/worker/screen/manager.py:153-206`

- [ ] **Step 1: 修改 start_recording() 使用消费者计数**

```python
def start_recording(self, output_path: str, fps: int = 10, ...) -> bool:
    """启动录屏"""
    # 确保截图线程运行
    self._ensure_capture_running()
    
    # ... 原有逻辑 ...
```

- [ ] **Step 2: 修改 stop_recording() 触发释放**

```python
def stop_recording(self) -> str:
    """停止录屏"""
    # ... 原有逻辑 ...
    
    # 标记消费者离开
    self._release_capture()
    return output_path
```

- [ ] **Step 3: 修改 start_streaming() 使用消费者计数**

```python
def start_streaming(self, codec: str = "jpeg") -> "WebSocketStreamer":
    """启动 WebSocket 推流"""
    # 确保截图线程运行
    self._ensure_capture_running()
    
    # ... 原有逻辑 ...
```

- [ ] **Step 4: 修改 stop_streaming() 触发释放**

```python
def stop_streaming(self) -> None:
    """停止推流"""
    # ... 原有逻辑 ...
    
    # 标记消费者离开
    self._release_capture()
```

- [ ] **Step 5: 提交**

```bash
cd /Users/ma/Documents/autotest
git add worker/screen/manager.py
git commit -m "refactor(worker): integrate consumer counting in recording/streaming"
```

---

## Task 3: 添加 H264 降级逻辑

**Files:**
- Modify: `/Users/ma/Documents/autotest/worker/screen/h264_streamer.py`

- [ ] **Step 1: 添加降级相关字段**

```python
class H264Streamer:
    def __init__(self, frame_source, fps: int = 10, bitrate: int = 2000000):
        # ... 现有字段 ...
        
        # 新增：降级相关
        self._consecutive_failures: int = 0
        self._max_failures: int = 30  # 连续 30 帧失败（约3秒）触发降级
        self._fallback_triggered: bool = False
        self._on_fallback: Optional[Callable[[], None]] = None
```

- [ ] **Step 2: 添加设置回调方法**

```python
def set_fallback_callback(self, callback: Callable[[], None]) -> None:
    """设置降级回调"""
    self._on_fallback = callback
```

- [ ] **Step 3: 修改 get_frame() 添加降级检测**

```python
def get_frame(self) -> Optional[bytes]:
    """获取编码帧"""
    if not self._encoder:
        self._consecutive_failures += 1
        self._check_fallback()
        return None
    
    # 获取 BGRA
    try:
        bgra = self.frame_source.get_frame_bgra()
        if not bgra:
            self._consecutive_failures += 1
            self._check_fallback()
            return None
    except Exception as e:
        logger.warning(f"Failed to get BGRA frame: {e}")
        self._consecutive_failures += 1
        self._check_fallback()
        return None
    
    # 编码
    try:
        encoded = self._encoder.encode_frame(bytes(bgra))
        if encoded:
            self._consecutive_failures = 0  # 成功后重置
            return encoded
        else:
            # encode_frame 返回 None（编码器未输出）
            self._consecutive_failures += 1
            self._check_fallback()
            return None
    except Exception as e:
        logger.error(f"Failed to encode frame: {e}")
        self._consecutive_failures += 1
        self._check_fallback()
        return None

def _check_fallback(self) -> None:
    """检查是否需要降级"""
    if self._fallback_triggered:
        return
    
    if self._consecutive_failures >= self._max_failures:
        self._fallback_triggered = True
        logger.warning(
            f"H264 encoding failed {self._consecutive_failures} times "
            f"(max={self._max_failures}), triggering fallback to JPEG"
        )
        if self._on_fallback:
            self._on_fallback()
```

- [ ] **Step 4: 修改 stop() 方法**

```python
def stop(self):
    """停止编码器"""
    # ... 原有逻辑 ...
    
    # 重置降级状态
    self._consecutive_failures = 0
    self._fallback_triggered = False
```

- [ ] **Step 5: 提交**

```bash
cd /Users/ma/Documents/autotest
git add worker/screen/h264_streamer.py
git commit -m "feat(worker): add H264 fallback logic when encoding fails"
```

---

## Task 4: 修改 WebSocketStreamer 支持降级回调

**Files:**
- Modify: `/Users/ma/Documents/autotest/worker/screen/streamer.py`

- [ ] **Step 1: 修改 start() 方法**

```python
def start(self, codec: str = "jpeg", on_fallback: Optional[Callable[[], None]] = None) -> None:
    """启动推流"""
    self._running = True
    self.codec = codec
    
    if codec == "h264":
        try:
            from worker.screen.h264_streamer import H264Streamer
            self._h264_streamer = H264Streamer(
                self.screen_manager._frame_source,
                fps=10
            )
            # 设置降级回调
            self._h264_streamer.set_fallback_callback(
                on_fallback or self._default_fallback
            )
            self._h264_streamer.start()
            logger.info("H.264 encoder started for streaming")
        except Exception as e:
            logger.error(f"Failed to start H.264 encoder: {e}, falling back to JPEG")
            self.codec = "jpeg"
```

- [ ] **Step 2: 添加默认降级处理**

```python
def _default_fallback(self) -> None:
    """默认降级处理：切换到 JPEG"""
    logger.warning("Falling back to JPEG mode")
    self.codec = "jpeg"
    # 可以通过其他方式通知前端
```

- [ ] **Step 3: 修改 stop() 方法**

```python
def stop(self) -> None:
    """停止推流"""
    self._running = False
    if self._h264_streamer:
        self._h264_streamer.stop()
        self._h264_streamer = None
    logger.info("WebSocket streamer stopped")
```

- [ ] **Step 4: 提交**

```bash
cd /Users/ma/Documents/autotest
git add worker/screen/streamer.py
git commit -m "feat(worker): add fallback callback support in WebSocketStreamer"
```

---

## Task 5: 修改各平台截图使用 ScreenManager

**Files:**
- Modify: 
  - `/Users/ma/Documents/autotest/worker/platforms/windows.py`
  - `/Users/ma/Documents/autotest/worker/platforms/mac.py`
  - `/Users/ma/Documents/autotest/worker/platforms/ios.py`
  - `/Users/ma/Documents/autotest/worker/platforms/android.py`

### Windows 平台

- [ ] **Step 1: 修改 take_screenshot() 方法**

查找 `windows.py` 中的 `take_screenshot()` 方法，修改为使用 ScreenManager：

```python
def take_screenshot(self, context: Optional[Any] = None) -> bytes:
    """截图（使用 ScreenManager）"""
    from worker.screen.manager import get_screen_manager
    
    # 获取或创建 ScreenManager
    screen_manager = get_screen_manager(self.device_id, self._frame_source)
    
    # 从 BGRA 队列获取并转换为 JPEG
    return screen_manager.get_frame_jpeg()
```

### 其他平台

- [ ] **Step 2: 修改 mac.py 截图方法**

```python
def take_screenshot(self, context: Optional[Any] = None) -> bytes:
    """截图（使用 ScreenManager）"""
    from worker.screen.manager import get_screen_manager
    
    screen_manager = get_screen_manager(self.device_id, self._frame_source)
    return screen_manager.get_frame_jpeg()
```

- [ ] **Step 3: 修改 ios.py 截图方法**

```python
def take_screenshot(self, context: Optional[Any] = None) -> bytes:
    """截图（使用 ScreenManager）"""
    from worker.screen.manager import get_screen_manager
    
    screen_manager = get_screen_manager(self.device_id, self._frame_source)
    return screen_manager.get_frame_jpeg()
```

- [ ] **Step 4: 修改 android.py 截图方法**

```python
def take_screenshot(self, context: Optional[Any] = None) -> bytes:
    """截图（使用 ScreenManager）"""
    from worker.screen.manager import get_screen_manager
    
    screen_manager = get_screen_manager(self.device_id, self._frame_source)
    return screen_manager.get_frame_jpeg()
```

- [ ] **Step 5: 提交**

```bash
cd /Users/ma/Documents/autotest
git add worker/platforms/windows.py worker/platforms/mac.py worker/platforms/ios.py worker/platforms/android.py
git commit -m "refactor(worker): use ScreenManager for screenshots across all platforms"
```

---

## Task 6: 测试验证

**Files:**
- Test: 手动测试

- [ ] **Step 1: 测试推流功能**

启动 Windows 设备推流，验证：
- H264 模式正常工作
- JPEG 模式正常工作
- 切换 codec 正常工作

```bash
# 启动推流测试
python -c "
from worker.screen.manager import get_screen_manager, close_all_screen_managers
from worker.screen.frame_source import WindowsFrameSource

# 创建 FrameSource
fs = WindowsFrameSource(fps=10, monitor=1)

# 获取 ScreenManager
sm = get_screen_manager('test-device', fs)

# 测试获取 JPEG
jpeg = sm.get_frame_jpeg()
print(f'Got JPEG: {len(jpeg)} bytes')

# 清理
close_all_screen_managers()
print('Test passed')
"
```

- [ ] **Step 2: 测试消费者计数和延迟释放**

验证：最后一个消费者离开后 60 秒才释放资源

```python
# 测试伪代码
sm = get_screen_manager('test', fs)

# 启动推流
streamer = sm.start_streaming(codec='jpeg')
print(f'Consumers: {sm._active_consumers}')  # 应该是 1

# 停止推流
streamer.stop()
print(f'Consumers: {sm._active_consumers}')  # 应该是 0
# 等待 10 秒，验证 _capture_loop 仍在运行
time.sleep(10)
# 等待 55 秒后（超过 60s），验证已释放
```

- [ ] **Step 3: 测试 H264 降级**

模拟编码器返回 None，验证连续 30 次后触发降级

- [ ] **Step 4: 提交**

```bash
cd /Users/ma/Documents/autotest
git add -A
git commit -m "test(worker): add integration tests for BGRA queue and fallback"
```

---

## Plan Complete

**Plan saved to:** `docs/superpowers/plans/2026-06-07-worker-h264-fixes.md`

---

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**