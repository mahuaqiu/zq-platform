# H264 流式传输实现方案

> **创建日期**: 2026-06-07
> **状态**: 待用户审批

## 1. 背景与目标

### 1.1 项目背景

需要在设备调试页面实现 H.264 实时推流功能，支持：
- 默认使用 H264 编码
- H264 失败时自动回退到 JPEG
- 详细的日志便于问题排查

### 1.2 技术选型

- **编码方案**: IMFByteStream 内存输出（Media Foundation）
- **推流服务**: 集成到 autotest/worker
- **前端解码**: WASM (Broadway/h264bsd) - 专为实时流设计，低延迟
- **传输协议**: WebSocket + codec 参数

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              前端                                        │
│  ┌─────────────────┐    ┌───��─────────────┐    ┌──────────────────┐   │
│  │  index.vue      │───▶│ useWebSocket    │───▶│ useH264Decoder   │   │
│  │  - currentCodec │    │ - connect()     │    │ - WASM 解码     │   │
│  │  - 自动回退逻辑 │    │ - codec 参数    │    │ - Canvas 渲染    │   │
│  └─────────────────┘    └─────────────────┘    └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ WebSocket + codec 参数
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         autotest/worker                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────────┐   │
│  │  WebSocket 端点 │───▶│ StreamingEncoder│───▶│ IMFByteStream    │   │
│  │  /ws/screen     │    │ - encode_frame()│    │ - 内存缓冲区     │   │
│  │  - codec 参数   │    │ - 提取 NAL 单元 │    │ - 无临时文件     │   │
│  └─────────────────┘    └─────────────────┘    └──────────────────┘   │
│                                    │                                     │
│                                    ▼                                     │
│                         ┌─────────────────┐                              │
│                         │ MFSinkWriter    │                              │
│                         │ H.264 编码器    │                              │
│                         └─────────────────┘                              │
└──────���──────────────────────────────────────────────────────────────────┘
```

## 3. 各组件职责

| 组件 | 路径 | 职责 |
|------|------|------|
| **index.vue** | `web/apps/web-ele/src/views/device-debug/index.vue` | 管理 `currentCodec` 状态，H264 失败时自动切换到 JPEG |
| **useWebSocket** | `web/apps/web-ele/src/views/device-debug/hooks/useWebSocket.ts` | 传递 codec 参数，记录连接状态用于重连 |
| **useH264Decoder** | `web/apps/web-ele/src/views/device-debug/hooks/useH264Decoder.ts` | WASM 解码 H264 流（使用 Broadway/h264bsd），渲染到 Canvas |
| **StreamingEncoder** | `win-recorder/src/streaming_encoder.rs` | Rust 核心编码器，实现 IMFByteStream 内存输出 |
| **IMFByteStream** | `win-recorder/src/memory_byte_stream.rs` | 自定义内存流接口，直接获取编码数据 |

## 4. 详细实现

### 4.1 IMFByteStream 实现

```rust
// 核心思路：实现 IMFByteStream 接口，将数据写入 Vec<u8>
// MFSinkWriter 可以输出到自定义 byte stream 而非文件
struct MemoryByteStream {
    buffer: Vec<u8>,
    position: u64,
    is_valid: bool,
}

impl MemoryByteStream {
    fn new() -> Self {
        Self {
            buffer: Vec::new(),
            position: 0,
            is_valid: true,
        }
    }
    
    fn get_buffer(&self) -> &[u8] {
        &self.buffer[self.position as usize..]
    }
}

impl IMFByteStream for MemoryByteStream {
    fn Read(&mut self, pb: &mut [u8], cb: u32, pcbRead: &mut u32) -> HRESULT {
        let available = (self.buffer.len() as u64 - self.position) as u32;
        let to_read = cb.min(available);
        pb[..to_read as usize].copy_from_slice(&self.buffer[self.position as usize..][..to_read as usize]);
        self.position += to_read as u64;
        *pcbRead = to_read;
        S_OK
    }
    
    fn Write(&mut self, pb: &[u8], cb: u32, pcbWritten: &mut u32) -> HRESULT {
        self.buffer.extend_from_slice(&pb[..cb as usize]);
        *pcbWritten = cb;
        S_OK
    }
    
    fn Seek(&mut self, SeekOrigin, llSeekOffset: i64, pllNewPosition: &mut u64) -> HRESULT {
        // 实现 seek 逻辑
    }
    
    // ... 其他接口方法 (GetLength, SetLength, Commit, Revert, LockRegion, UnlockRegion)
}
```

### 4.2 StreamingEncoder 修改

```rust
pub struct StreamingEncoder {
    // ... 现有字段
    output_buffer: Vec<u8>,  // 内存输出缓冲区
}

impl StreamingEncoder {
    pub fn encode_frame(&mut self, frame_data: &[u8]) -> Result<Option<Vec<u8>>, RecorderError> {
        // 现有编码逻辑...
        
        // 从内存输出流获取编码数据
        if let Some(writer) = &mut self.sink_writer {
            let encoded_data = writer.get_encoded_data();
            if !encoded_data.is_empty() {
                return Ok(Some(encoded_data));
            }
        }
        
        Ok(None)
    }
}
```

### 4.3 前端 H264 解码方案（WASM）

使用 **Broadway** (h264bsd) WASM 解码器，专为实时流设计：

```typescript
// useH264Decoder.ts
import { ref, onUnmounted } from 'vue';

export function useH264Decoder(options: H264DecoderOptions) {
  const canvasRef = ref<HTMLCanvasElement | null>(null);
  const isReady = ref(false);
  const decoder = ref<any>(null);

  // 动态加载 Broadway WASM 解码器
  const initDecoder = async () => {
    try {
      // 加载 WASM 解码器
      const Broadway = await import('broadway_decoder');
      decoder.value = new Broadway.Decoder({
        canvas: canvasRef.value!,
        output: 'rgb'
      });
      
      await decoder.value.ready;
      isReady.value = true;
      console.log('[H264Decoder] ✅ Broadway WASM decoder ready');
      options.onReady?.();
    } catch (e) {
      console.error('[H264Decoder] ❌ WASM decoder init failed:', e);
      options.onError?.(e as Error);
    }
  };

  const appendFrame = (data: ArrayBuffer) => {
    if (!isReady.value || !decoder.value) return;

    try {
      // 解码 H.264 NAL 单元并渲染到 canvas
      decoder.value.decode(new Uint8Array(data));
    } catch (e) {
      console.error('[H264Decoder] ❌ Decode error:', e);
    }
  };

  const dispose = () => {
    decoder.value?.delete();
    decoder.value = null;
    isReady.value = false;
  };

  onUnmounted(dispose);

  return { canvasRef, isReady, initDecoder, appendFrame, dispose };
}
```

**为什么选择 Broadway (h264bsd)**：
- 纯 WASM 实现，无外部依赖
- 解码延迟 < 5ms
- 支持 Annex-B 格式（win-recorder 输出格式）
- 适合实时推流场景

### 4.4 前端自动回退逻辑

```typescript
// useWebSocket.ts
ws.onclose = (event) => {
  // 非正常关闭且当前使用 H264
  if (event.code !== 1000 && savedCodec === 'h264') {
    console.log(`[WebSocket] H264 connection failed (code=${event.code}), falling back to JPEG`);
    // 触发回退
    setTimeout(() => {
      reconnect(savedHost, savedPort, savedUdid, savedDeviceType, savedScreenIndex, 'jpeg');
    }, RETRY_INTERVAL);
  }
};
```

### 4.4 NAL 单元提取

H.264 编码器输出的是 ES (Elementary Stream)，需要提取 NAL 单元：

| NAL 类型 | 字节 | 说明 |
|----------|------|------|
| SPS | 0x67 | 序列参数集 |
| PPS | 0x68 | 图像参数集 |
| IDR | 0x65 | 立即刷新帧 (关键帧) |
| non-IDR | 0x41 | 非关键帧 |

```rust
fn extract_nal_units(data: &[u8]) -> Vec<Vec<u8>> {
    let mut nal_units = Vec::new();
    let mut start = None;
    
    for i in 0..data.len() - 3 {
        // 检测 NAL 单元起始码: 0x00 0x00 0x00 0x01 或 0x00 0x00 0x01
        if data[i] == 0x00 && data[i+1] == 0x00 && 
           (data[i+2] == 0x01 || (data[i+2] == 0x00 && data[i+3] == 0x01)) {
            if let Some(start_idx) = start {
                nal_units.push(data[start_idx..i].to_vec());
            }
            start = Some(i + 4);
        }
    }
    
    if let Some(start_idx) = start {
        nal_units.push(data[start_idx..].to_vec());
    }
    
    nal_units
}
```

## 5. 日志规范

### 5.1 前端日志（Console）

```typescript
// 连接阶段
console.log(`[WebSocket] Connecting: ${host}:${port}, codec=${codec}, device=${udid}`);
console.log(`[WebSocket] WS URL: ${url}`);

// 帧处理 - 每 30 帧打印一次，避免刷屏
if (frameCount % 30 === 0) {
  console.log(`[WebSocket] Frame: type=${frameType}, size=${dataSize}bytes, totalFrames=${frameCount}`);
}

// 解码状态
console.log(`[H264Decoder] Decoder ready, mode=WASM`);
console.log(`[H264Decoder] Decode error: ${error.message}`);

// 错误处理
console.error(`[WebSocket] Error:`, event);
console.error(`[WebSocket] Connection failed: code=${event.code}, reason=${event.reason}`);

// 回退逻辑 - 关键日志
console.warn(`[WebSocket] ⚠️ H264 failed (code=${event.code}), falling back to JPEG`);
console.log(`[WebSocket] → Reconnecting with codec=jpeg`);
```

### 5.2 Worker 日志（Python）

```python
import logging

logger = logging.getLogger("streaming")
logger.setLevel(logging.INFO)

# 连接日志
logger.info(f"[Streaming] New connection: codec={codec}, device={udid}, monitor={monitor}")
logger.info(f"[Streaming] WS endpoint: /ws/screen/{platform}/{device_id}")

# 编码日志 - 每 30 帧打印一次
if frame_count % 30 == 0:
    logger.info(f"[Streaming] Encode frame #{frame_count}: size={size}, codec={codec}, fps={fps}")

# 错误日志
logger.error(f"[Streaming] Encode error: {type(e).__name__}: {e}")
logger.warning(f"[Streaming] ⚠️ H264 not supported, falling back to JPEG")

# 性能日志
logger.info(f"[Streaming] Performance: fps={fps}, bitrate={bitrate}kbps, resolution={width}x{height}")
```

### 5.3 win-recorder 日志（Rust）

```rust
use log::{info, warn, error};

// 连接日志
info!("[StreamingEncoder] Starting: {}x{} @ {}fps, codec={}", width, height, fps, codec);
info!("[StreamingEncoder] IMFByteStream initialized, buffer capacity: {} bytes", capacity);

// 编码日志 - 每 30 帧打印一次
if frame_count % 30 == 0 {
    info!("[StreamingEncoder] Frame encoded: #{}, type={:?}, size={}bytes", 
          frame_count, frame_type, size);
}

// 错误日志
error!("[StreamingEncoder] IMFByteStream init failed: {}", error);
error!("[StreamingEncoder] Encoding failed: {}", error);
warn!("[StreamingEncoder] ⚠️ H264 encoding not available, falling back to JPEG");

// 性能日志
info!("[StreamingEncoder] Performance: fps={}, encoded_frames={}", fps, encoded_frames);
```

### 5.4 日志级别使用规范

| 级别 | 前端 | Worker | win-recorder |
|------|------|--------|--------------|
| `DEBUG` | 详细帧数据、NAL 单元内容 | 内部状态详情 | 内部调试信息 |
| `INFO` | 连接状态、帧处理 | 连接、帧编码、关键事件 | 启动、编码、停止 |
| `WARN` | 性能警告 | 性能降级 | 性能问题 |
| `ERROR` | 连接失败、解码错误 | 编码失败、崩溃 | 致命错误 |

## 6. 错误处理

| 错误场景 | 处理方式 |
|----------|----------|
| IMFByteStream 初始化失败 | 回退到 JPEG，记录 `ERROR` 日志 |
| 编码器启动失败 | 回退到 JPEG，记录 `ERROR` 日志 |
| WebSocket 连接 H264 失败 | 自动重连 3 次后回退到 JPEG，记录 `WARN` |
| 解码器初始化失败 | 回退到 JPEG，记录 `ERROR` |
| H264 流断开 | 自动回退，记录 `WARN` |

## 7. 版本升级

win-recorder 修改完成后，需要升级以下版本号：

| 文件 | 当前版本 | 目标版本 |
|------|----------|----------|
| `win-recorder/Cargo.toml` | 0.2.1 | 0.3.0 |
| `backend-fastapi/core/env_machine/...` | - | 更新 pywinrecorder 版本 |

## 8. 验证清单

- [ ] win-recorder 编译通过 (`cargo build`)
- [ ] IMFByteStream 正确获取编码数据
- [ ] Worker WebSocket 正确传递 codec 参数
- [ ] 前端 WebSocket 正确传递 codec 参数
- [ ] H264 流正常解码播放
- [ ] H264 失败自动回退到 JPEG
- [ ] 日志正常输出（前端 Console + Worker 日志）
- [ ] 帧率正常 (目标 10-15fps)
- [ ] 版本号已更新