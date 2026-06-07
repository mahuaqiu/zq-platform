# WebCodecs H264 解码器实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用原生 WebCodecs VideoDecoder API 解码 H264 流，替代 10 年未维护的 broadway-player

**Architecture:** 
- 新建 `useWebCodecsDecoder.ts` 提供 WebCodecs 解码能力
- 收到 IDR 帧时初始化解码器（需要 SPS/PPS）
- 解码失败时自动降级到 JPEG 模式
- 移除 broadway-player 依赖

**Tech Stack:** WebCodecs VideoDecoder API, TypeScript, Vue 3

---

## Task 1: 创建 WebCodecs 解码器 Hook

**Files:**
- Create: `web/apps/web-ele/src/views/device-debug/hooks/useWebCodecsDecoder.ts`
- Reference: `web/apps/web-ele/src/views/device-debug/hooks/useH264Decoder.ts` (将被替代)
- Reference: `web/apps/web-ele/src/views/device-debug/utils/stream.ts`

- [ ] **Step 1: 创建 useWebCodecsDecoder.ts 文件**

```typescript
import { ref, onUnmounted } from 'vue';

/**
 * WebCodecs H264 解码器
 * 使用原生 VideoDecoder API 解码 H264 流
 */
export function useWebCodecsDecoder(options: {
  width: number;
  height: number;
  onReady?: () => void;
  onError?: (error: Error) => void;
  onFallback?: () => void;
}) {
  const canvasRef = ref<HTMLCanvasElement | null>(null);
  const isReady = ref(false);

  // VideoDecoder 实例
  let decoder: VideoDecoder | null = null;

  // SPS/PPS 缓存（用于初始化解码器）
  let spsData: Uint8Array | null = null;
  let ppsData: Uint8Array | null = null;
  let configWidth = 0;
  let configHeight = 0;

  // 检查浏览器支持
  function isSupported(): boolean {
    return 'VideoDecoder' in window;
  }

  // 初始化解码器
  async function initDecoder(sps: Uint8Array, pps: Uint8Array, width: number, height: number) {
    if (!isSupported()) {
      throw new Error('WebCodecs VideoDecoder not supported');
    }

    // 提取 profile/level 从 SPS
    // SPS[1] = profile_idc, SPS[2] = profile_compat, SPS[3] = level_idc
    const profileLevel = 
      toHex(sps[1]) + 
      toHex(sps[2]) + 
      toHex(sps[3]);

    const config: VideoDecoderConfig = {
      codec: `avc1.${profileLevel}`,
      codedWidth: width,
      codedHeight: height,
    };

    // 检查配置是否支持
    const support = await VideoDecoder.isConfigSupported(config);
    if (!support.supported) {
      throw new Error(`Codec ${config.codec} not supported`);
    }

    decoder = new VideoDecoder({
      output: (frame) => {
        // 渲染帧到 Canvas
        renderFrameToCanvas(frame, canvasRef.value!);
        frame.close();
      },
      error: (e) => {
        console.error('[WebCodecs] Decode error:', e);
        options.onError?.(new Error(String(e)));
        // 触发降级
        options.onFallback?.();
      }
    });

    await decoder.configure(config);
    
    // 保存 SPS/PPS
    spsData = sps;
    ppsData = pps;
    configWidth = width;
    configHeight = height;
    
    isReady.value = true;
    console.log('[WebCodecs] Decoder initialized, codec:', config.codec);
    options.onReady?.();
  }

  // 渲染 VideoFrame 到 Canvas
  function renderFrameToCanvas(frame: VideoFrame, canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = frame.codedWidth;
    canvas.height = frame.codedHeight;

    ctx.drawImage(frame, 0, 0);
  }

  // 工具：Uint8Array 转十六进制字符串
  function toHex(byte: number): string {
    return byte.toString(16).padStart(2, '0');
  }

  // 解码一帧
  function decodeFrame(data: ArrayBuffer) {
    if (!data || data.byteLength < 2) return;

    const view = new DataView(data);
    const frameType = view.getUint8(0); // 0x01=SPS/PPS, 0x02=IDR, 0x03=P
    const nalData = new Uint8Array(data, 1);

    // 提取 NAL 单元（Annex-B 格式）
    const nalUnits = extractNalUnits(nalData);

    if (frameType === 0x01) {
      // SPS/PPS: 缓存用于后续初始化
      for (const nal of nalUnits) {
        const nalType = nal[0] & 0x1F;
        if (nalType === 7) {
          spsData = nal; // SPS
        } else if (nalType === 8) {
          ppsData = nal; // PPS
        }
      }
    } else if (frameType === 0x02) {
      // IDR 关键帧: 如果未初始化则初始化
      if (!decoder && spsData && ppsData) {
        initDecoder(spsData, ppsData, configWidth || options.width, configHeight || options.height);
      }
      
      if (decoder && isReady.value) {
        // 转换为 AVCC 格式并解码
        const avccData = annexbToAvcc(nalUnits);
        const chunk = new EncodedVideoChunk({
          type: 'key',
          timestamp: 0,
          data: avccData,
        });
        decoder.decode(chunk);
      }
    } else if (frameType === 0x03) {
      // P 帧
      if (decoder && isReady.value) {
        const avccData = annexbToAvcc(nalUnits);
        const chunk = new EncodedVideoChunk({
          type: 'delta',
          timestamp: 0,
          data: avccData,
        });
        decoder.decode(chunk);
      }
    }
  }

  // 从 Annex-B 数据提取 NAL 单元数组
  function extractNalUnits(data: Uint8Array): Uint8Array[] {
    const units: Uint8Array[] = [];
    let startIdx: number | null = null;

    for (let i = 0; i < data.length - 3; i++) {
      // 检测 4 字节起始码 0x00 0x00 0x00 0x01
      if (data[i] === 0x00 && data[i+1] === 0x00 && data[i+2] === 0x00 && data[i+3] === 0x01) {
        if (startIdx !== null) {
          units.push(data.slice(startIdx, i));
        }
        startIdx = i + 4;
      }
      // 检测 3 字节起始码 0x00 0x00 0x01
      else if (data[i] === 0x00 && data[i+1] === 0x00 && data[i+2] === 0x01) {
        if (startIdx !== null) {
          units.push(data.slice(startIdx, i));
        }
        startIdx = i + 3;
      }
    }

    if (startIdx !== null) {
      units.push(data.slice(startIdx));
    }

    return units;
  }

  // Annex-B 转 AVCC 格式
  function annexbToAvcc(nalUnits: Uint8Array[]): Uint8Array {
    const totalLength = nalUnits.reduce((sum, n) => sum + n.length, 0);
    const avcc = new Uint8Array(4 + totalLength);

    let offset = 0;
    for (const nal of nalUnits) {
      // 4 字节长度前缀
      avcc[offset++] = (nal.length >> 24) & 0xFF;
      avcc[offset++] = (nal.length >> 16) & 0xFF;
      avcc[offset++] = (nal.length >> 8) & 0xFF;
      avcc[offset++] = nal.length & 0xFF;
      // NAL 数据
      avcc.set(nal, offset);
      offset += nal.length;
    }

    return avcc;
  }

  // 释放资源
  function dispose() {
    if (decoder) {
      decoder.close();
      decoder = null;
    }
    isReady.value = false;
    spsData = null;
    ppsData = null;
    console.log('[WebCodecs] Decoder disposed');
  }

  onUnmounted(dispose);

  return {
    canvasRef,
    isReady,
    isSupported,
    decodeFrame,
    dispose,
  };
}
```

- [ ] **Step 2: 验证文件创建成功**

Run: `ls -la web/apps/web-ele/src/views/device-debug/hooks/useWebCodecsDecoder.ts`
Expected: 文件存在

- [ ] **Step 3: 提交**

```bash
git add web/apps/web-ele/src/views/device-debug/hooks/useWebCodecsDecoder.ts
git commit -m "feat(web): add WebCodecs H264 decoder hook"
```

---

## Task 2: 更新 useWebSocket.ts 使用新解码器

**Files:**
- Modify: `web/apps/web-ele/src/views/device-debug/hooks/useWebSocket.ts:8`
- Reference: `web/apps/web-ele/src/views/device-debug/hooks/useWebCodecsDecoder.ts`

- [ ] **Step 1: 修改导入语句**

将：
```typescript
import { useH264Decoder } from './useH264Decoder';
```

改为：
```typescript
import { useWebCodecsDecoder } from './useWebCodecsDecoder';
```

- [ ] **Step 2: 修改解码器初始化**

将：
```typescript
// H.264 解码器
const h264Decoder = useH264Decoder({
  width: 1920,
  height: 1080,
  onReady: () => console.log('H264 decoder ready'),
  onError: (e) => console.error('H264 error:', e),
});
```

改为：
```typescript
// H.264 解码器 (WebCodecs)
const h264Decoder = useWebCodecsDecoder({
  width: 1920,
  height: 1080,
  onReady: () => console.log('[WebSocket] H264 decoder ready (WebCodecs)'),
  onError: (e) => console.error('[WebSocket] H264 decode error:', e),
  onFallback: () => {
    console.warn('[WebSocket] H264 failed, falling back to JPEG');
    // 重新连接使用 JPEG 模式
    reconnect(savedHost, savedPort, savedUdid, savedDeviceType, savedScreenIndex, 'jpeg');
  },
});
```

- [ ] **Step 3: 更新 h264Decoder.appendFrame 调用**

将 `h264Decoder.appendFrame(arrayBuffer)` 改为 `h264Decoder.decodeFrame(arrayBuffer)`

- [ ] **Step 4: 验证修改**

Run: `grep -n "useWebCodecsDecoder\|decodeFrame\|onFallback" web/apps/web-ele/src/views/device-debug/hooks/useWebSocket.ts`
Expected: 看到新的调用

- [ ] **Step 5: 提交**

```bash
git add web/apps/web-ele/src/views/device-debug/hooks/useWebSocket.ts
git commit -m "refactor(web): switch to WebCodecs decoder in useWebSocket"
```

---

## Task 3: 移除 broadway-player 依赖

**Files:**
- Modify: `web/apps/web-ele/package.json:45`
- Delete: 无需删除，使用 pnpm 清理

- [ ] **Step 1: 移除 broadway-player 依赖**

从 `package.json` 中删除：
```json
"broadway-player": "^0.1.1",
```

- [ ] **Step 2: 执行 pnpm install 清理**

Run: `cd web && pnpm install`
Expected: broadway-player 从 node_modules 移除

- [ ] **Step 3: 提交**

```bash
git add web/apps/web-ele/package.json
git commit -m "chore(web): remove deprecated broadway-player dependency"
```

---

## Task 4: 清理旧文件

**Files:**
- Delete: `web/apps/web-ele/src/views/device-debug/hooks/useH264Decoder.ts`

- [ ] **Step 1: 删除旧文件**

```bash
rm web/apps/web-ele/src/views/device-debug/hooks/useH264Decoder.ts
```

- [ ] **Step 2: 验证**

Run: `ls web/apps/web-ele/src/views/device-debug/hooks/useH264Decoder.ts`
Expected: No such file or directory

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "refactor(web): remove old broadway-based H264 decoder"
```

---

## Plan Complete

**Plan saved to:** `docs/superpowers/plans/2026-06-07-webcodecs-h264-decoder.md`

---

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**