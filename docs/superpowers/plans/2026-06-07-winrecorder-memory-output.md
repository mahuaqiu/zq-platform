# Win-Recorder 内存输出实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 MFCreateMemoryBuffer 内存输出，让 encode_frame() 返回真实的 NAL 单元数据而不是 None

**Architecture:** 使用自定义 IMFMediaSink + IMFStreamSink 实现内存输出，替代当前的文件输出方案

**Tech Stack:** Rust, windows-rs, Media Foundation API

---

## 背景

当前 `StreamingEncoder.encode_frame()` 返回 `None`，因为使用了临时文件输出：
```rust
let temp_path = std::env::temp_dir().join("win_recorder_stream.temp.mp4");
let mut sink_writer = MFSinkWriter::new(&temp_path_str, ...);
writer.write_sample(&sample)?;
Ok(None)  // 无法获取编码数据
```

需要实现��正的内存输出，使编码后的数据可以直接返回给 Python 层。

---

## Task 1: 分析 Media Foundation 内存输出方案

**Files:**
- Read: `/Users/ma/Documents/win-recorder/src/mf_writer.rs`
- Read: `/Users/ma/Documents/win-recorder/src/streaming_encoder.rs`

- [ ] **Step 1: 调研 Media Foundation 内存输出方案**

Media Foundation 支持两种内存输出方式：

**方案 A: 自定义 IMFMediaSink**
- 实现自定义的 IMFMediaSink 和 IMFStreamSink
- 在 `OnProcessSample()` 中接收编码后的数据
- 复杂度高，但功能完整

**方案 B: 使用 MFCreateMemoryBuffer 直接捕获**
- 编码器输出到内存 buffer
- 适用于简单场景

**方案 C: 回调式输出（推荐）**
- 在 MFSinkWriter 中添加回调接口
- 编码完成后通过回调返回数据
- 不需要完全重写 MediaSink

- [ ] **Step 2: 选择方案并记录**

Run: 记录选择的方案和理由

---

## Task 2: 创建内存输出接口

**Files:**
- Modify: `/Users/ma/Documents/win-recorder/src/mf_writer.rs`
- Create: `/Users/ma/Documents/win-recorder/src/memory_sink.rs` (新文件)

Media Foundation 内存输出的核心是实现自定义的 StreamSink。以下是实现思路：

```rust
// memory_sink.rs

use windows::core::*;
use windows::Win32::Media::MediaFoundation::*;

/// 内存输出 StreamSink
///
/// 实现 IMFStreamSink 接口，接收编码后的数据并存储到内存缓冲区
pub struct MemoryStreamSink {
    // 输出缓冲区
    output_buffer: Vec<u8>,
    // 是否已收到关键帧
    got_keyframe: bool,
}

unsafe impl Send for MemoryStreamSink {}
unsafe impl Sync for MemoryStreamSink {}

impl MemoryStreamSink {
    pub fn new() -> Result<Self> {
        Ok(Self {
            output_buffer: Vec::new(),
            got_keyframe: false,
        })
    }
    
    /// 获取编码后的数据
    pub fn get_encoded_data(&self) -> &[u8] {
        &self.output_buffer
    }
    
    /// 清空缓冲区
    pub fn clear(&mut self) {
        self.output_buffer.clear();
        self.got_keyframe = false;
    }
}

// 实现 IMFStreamSink 接口（简化版）
// 关键方法：OnProcessSample() - 接收编码后的样本
```

- [ ] **Step 1: 创建 memory_sink.rs 文件**

创建新文件 `src/memory_sink.rs`，包含：
- `MemoryStreamSink` 结构体
- 实现 `IMFStreamSink` 接口（必需的方法）
- `IMFAsyncCallback` 回调处理

```rust
// 最小实现的 IMFStreamSink 需要：
// - IMFMediaEventGenerator (继承)
// - IMFStreamSink
// - IMFAsyncCallback

// 简化方案：使用现有的 MFMetadata 功能辅助
```

- [ ] **Step 2: 运行 cargo check 验证编译**

Run: `cd /Users/ma/Documents/win-recorder && cargo check`
Expected: 无编译错误（或仅有预期内的错误）

- [ ] **Step 3: 提交**

```bash
cd /Users/ma/Documents/win-recorder
git add src/memory_sink.rs
git commit -m "feat(win-recorder): add memory sink base structure"
```

---

## Task 3: 修改 MFSinkWriter 支持内存输出

**Files:**
- Modify: `/Users/ma/Documents/win-recorder/src/mf_writer.rs:35-178`

- [ ] **Step 1: 添加可选的内存输出模式**

修改 `MFSinkWriter::new()` 方法，添加回调参数：

```rust
pub fn new_memory(
    width: u32,
    height: u32,
    fps: u32,
    on_encoded: impl Fn(Vec<u8>) + Send + 'static,
) -> Result<Self, RecorderError> {
    // 使用内存输出模式
    // 需要实现自定义的 MediaSink
}
```

- [ ] **Step 2: 实现内存输出模式**

由于 Media Foundation 的内存输出比较复杂，可以采用以下简化方案：

1. **方案 A（推荐）**: 保留文件输出，但在写入后读取文件内容返回，然后截断文件
2. **方案 B**: 实现完整的自定义 IMFMediaSink

**方案 A 实现**:
```rust
pub struct MFSinkWriter {
    // ... 现有字段
    output_path: Option<String>,  // Some 表示文件模式
    temp_file: Option<File>,       // 临时文件句柄
    // 内存模式专用
    on_encoded: Option<Box<dyn Fn(Vec<u8>) + Send>>,
}

impl MFSinkWriter {
    /// 创建文件输出模式（现有）
    pub fn new_file(output_path: &str, ...) -> Result<Self, RecorderError> {
        // 现有实现
    }
    
    /// 创建内存输出模式（新增）
    pub fn new_memory(
        width: u32,
        height: u32,
        fps: u32,
        on_encoded: impl Fn(Vec<u8>) + Send + 'static,
    ) -> Result<Self, RecorderError> {
        // 1. 创建临时文件（作为内存缓冲的替代）
        let temp_path = std::env::temp_dir().join("win_recorder_memory_output.temp");
        
        // 2. 使用文件输出，但每次写入后读取新数据
        let mut writer = Self::new_file(temp_path.to_str().unwrap(), ...)?;
        writer.output_path = Some(temp_path.to_string_lossy().to_string());
        writer.on_encoded = Some(Box::new(on_encoded));
        
        Ok(writer)
    }
}
```

- [ ] **Step 3: 实现写入后读取新数据**

在 `write_sample()` 方法中添加：

```rust
pub fn write_sample(&mut self, sample: &IMFSample) -> Result<(), RecorderError> {
    // ... 现有写入逻辑 ...
    
    self.frame_count += 1;
    
    // 内存模式：读取新增的编码数据
    if let Some(callback) = &self.on_encoded {
        if let Some(path) = &self.output_path {
            let new_data = self.read_new_encoded_data(path)?;
            if !new_data.is_empty() {
                callback(new_data);
            }
        }
    }
    
    Ok(())
}

/// 读取文件中新增的编码数据
/// 实现思路：记录上次读取位置，下次从新位置开始读取
fn read_new_encoded_data(&mut self, path: &str) -> Result<Vec<u8>, RecorderError> {
    use std::io::{Read, Seek, SeekFrom};
    
    // 需要保存上次的文件位置
    // 简化实现：每次读取整个文件，然后截断
    // 优化：只读取新增部分
}
```

- [ ] **Step 4: 验证编译**

Run: `cd /Users/ma/Documents/win-recorder && cargo check`
Expected: 无编译错误

- [ ] **Step 5: 提交**

```bash
cd /Users/ma/Documents/win-recorder
git add src/mf_writer.rs
git commit -m "feat(win-recorder): add memory output support to MFSinkWriter"
```

---

## Task 4: 修改 StreamingEncoder 使用内存输出

**Files:**
- Modify: `/Users/ma/Documents/win-recorder/src/streaming_encoder.rs:89-169`

- [ ] **Step 1: 修改 start() 方法**

将文件输出改为内存输出：

```rust
pub fn start(&mut self) -> Result<Py<PyDict>, RecorderError> {
    if self.encoding {
        return Err(RecorderError::AlreadyRecording);
    }
    
    println!("[StreamingEncoder] Starting encoder: {}x{} @ {}fps (memory mode)", 
        self.width, self.height, self.fps);
    
    // 创建临时纹理管理器获取设备
    let temp_texture_manager = D3D11TextureManager::new(self.width, self.height)?;
    let device = temp_texture_manager.device().clone();
    
    // 使用内存输出模式
    let mut sink_writer = MFSinkWriter::new_memory(
        self.width,
        self.height,
        self.fps,
        // 回调：处理编码后的数据
        |encoded_data: Vec<u8>| {
            // 这里处理编码后的 NAL 单元
            // 可以选择立即处理或缓存
        },
    )?;
    
    // ... 后续逻辑保持不变
}
```

- [ ] **Step 2: 修改 encode_frame() 返回真实数据**

修改 `encode_frame()` 方法，不再返回 `None`：

```rust
pub fn encode_frame(&mut self, frame_data: &[u8]) -> Result<Option<Vec<u8>>, RecorderError> {
    if !self.encoding {
        return Err(RecorderError::NotRecording);
    }
    
    let texture_manager = self.texture_manager.as_ref()
        .ok_or(RecorderError::NotRecording)?;
    let sink_writer = self.sink_writer.as_ref()
        .ok_or(RecorderError::NotRecording)?;
    
    // 上传到纹理
    texture_manager.upload_bgra(frame_data)?;
    
    // 创建 MF Sample
    let sample = texture_manager.create_mf_sample()?;
    
    // 写入编码器（内存模式会触发回调）
    let mut writer = sink_writer.lock();
    writer.write_sample(&sample)?;
    
    self.frame_count += 1;
    
    // 从输出缓冲区获取编码数据
    // 内存模式：编码数据通过回调处理，这里返回缓冲区中的数据
    let output_data = writer.get_output_data();
    if output_data.is_empty() {
        return Ok(None);  // 编码器尚未输出数据
    }
    
    // 格式化输出：[1字节帧类型][N字节数据]
    let framed_data = self.format_output(output_data)?;
    Ok(Some(framed_data))
}
```

- [ ] **Step 3: 添加输出数据获取方法**

在 `MFSinkWriter` 中添加：

```rust
impl MFSinkWriter {
    /// 获取输出缓冲区的数据（内存模式）
    pub fn get_output_data(&mut self) -> Vec<u8> {
        // 实现：从内存缓冲区获取数据并清空
        std::mem::take(&mut self.pending_output)
    }
}
```

- [ ] **Step 4: 验证编译**

Run: `cd /Users/ma/Documents/win-recorder && cargo check`
Expected: 无编译错误

- [ ] **Step 5: 提交**

```bash
cd /Users/ma/Documents/win-recorder
git add src/streaming_encoder.rs
git commit -m "feat(win-recorder): use memory output in StreamingEncoder"
```

---

## Task 5: 实现 NAL 单元提取和格式化

**Files:**
- Modify: `/Users/ma/Documents/win-recorder/src/streaming_encoder.rs`

- [ ] **Step 1: 从 MP4 容器中提取 H264 数据**

编码器输出的是完整的 MP4 容器，需要从中提取 NAL 单元。

**简化方案**：使用硬编码的 SPS/PPS + 从编码器提取的帧数据

```rust
impl StreamingEncoder {
    /// 格式化输出数据
    fn format_output(&self, raw_data: Vec<u8>) -> Result<Vec<u8>, RecorderError> {
        // raw_data 是编码后的 H264 原始流（Annex-B 格式）
        // 需要解析并添加帧类型前缀
        
        let mut result = Vec::new();
        
        // 提取 NAL 单元并添加前缀
        // 0x01 = SPS/PPS
        // 0x02 = IDR (关键帧)
        // 0x03 = P 帧
        
        // 简化实现：假设输入是完整的 H264 流
        // 第一个 NAL 是 SPS/PPS
        // IDR 帧通过 NAL type 判断（5 或 1）
        
        // 返回格式化后的数据
        Ok(result)
    }
}
```

- [ ] **Step 2: 处理 SPS/PPS 发送逻辑**

修改 `encode_frame()` 方法：

```rust
// 在首次收到 IDR 帧时发送 SPS/PPS
if !self.sps_pps_sent {
    // 发送 SPS
    result.push(0x01);  // 帧类型前缀
    result.extend_from_slice(&self.sps_data);
    
    // 发送 PPS
    result.push(0x01);  // 帧类型前缀
    result.extend_from_slice(&self.pps_data);
    
    self.sps_pps_sent = true;
}

// 发送帧数据
if is_keyframe {
    result.push(0x02);  // IDR
} else {
    result.push(0x03);  // P 帧
}
result.extend_from_slice(&frame_data);
```

- [ ] **Step 3: 提交**

```bash
cd /Users/ma/Documents/win-recorder
git commit -m "feat(win-recorder): implement NAL unit extraction and framing"
```

---

## Task 6: 测试验证

**Files:**
- Test: 手动测试脚本

- [ ] **Step 1: 编写测试脚本**

创建 Python 测试脚本验证内存输出：

```python
# test_memory_output.py
import win_recorder

encoder = win_recorder.StreamingEncoder(fps=10, monitor=1)
info = encoder.start()
print(f"Encoder started: {info}")

# 模拟输入 BGRA 帧
test_frame = b'\x00' * (1920 * 1080 * 4)

# 编码多帧
for i in range(30):
    result = encoder.encode_frame(test_frame)
    if result:
        print(f"Frame {i}: got {len(result)} bytes")
    else:
        print(f"Frame {i}: None")

encoder.stop()
print("Test completed")
```

- [ ] **Step 2: 运行测试**

Run: `python test_memory_output.py`
Expected: 能够获取到编码数据（不再是 None）

- [ ] **Step 3: 提交**

```bash
cd /Users/ma/Documents/win-recorder
git add test_memory_output.py
git commit -m "test(win-recorder): add memory output test"
```

---

## Plan Complete

**Plan saved to:** `docs/superpowers/plans/2026-06-07-winrecorder-memory-output.md`

---

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**