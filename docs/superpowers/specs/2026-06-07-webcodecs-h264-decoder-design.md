# WebCodecs H264 解码方案设计

**日期**: 2026-06-07
**状态**: 已批准

## 1. 背景

原方案使用 broadway-player (WASM 解码器)，但该包已 10 年未维护，不适合生产部署。现改用 WebCodecs API 解码 H264 流。

## 2. 目标

- 使用原生 WebCodecs VideoDecoder API 解码 H264 流
- 支持 Chromium/Edge 桌面浏览器
- 浏览器不支持时自动降级到 JPEG 模式

## 3. 技术方案

### 3.1 数据格式

| 字段 | 说明 |
|------|------|
| 帧类型前缀 | 1 字节：`0x01=SPS/PPS, 0x02=IDR, 0x03=P帧` |
| 数据格式 | Annex-B 格式（起始码 `0x00 0x00 0x00 0x01`） |

### 3.2 解码器初始化

```typescript
// 首次收到 IDR 帧时初始化 VideoDecoder
async initDecoder(sps: Uint8Array, pps: Uint8Array, width: number, height: number) {
  // Annex-B 转 AVCC 格式
  const avccConfig = annexbToAvcc(sps, pps);

  const config = {
    codec: `avc1.${avccConfig.profileLevel}`,
    codedWidth: width,
    codedHeight: height,
  };

  this.decoder = new VideoDecoder({
    output: (frame) => {
      renderToCanvas(frame, this.canvas);
      frame.close();
    },
    error: (e) => this.onError(e)
  });

  await this.decoder.configure(config);
}
```

### 3.3 Annex-B 到 AVCC 转换

WebCodecs 需要 AVCC 格式（4 字节长度前缀），需要转换：

```typescript
function annexbToAvcc(annexbData: Uint8Array): Uint8Array {
  const nalUnits = extractNalUnits(annexbData);
  const avcc = new Uint8Array(4 + nalUnits.reduce((s, n) => s + n.length, 0));

  let offset = 0;
  for (const nal of nalUnits) {
    avcc[offset++] = (nal.length >> 24) & 0xFF;
    avcc[offset++] = (nal.length >> 16) & 0xFF;
    avcc[offset++] = (nal.length >> 8) & 0xFF;
    avcc[offset++] = nal.length & 0xFF;
    avcc.set(nal, offset);
    offset += nal.length;
  }
  return avcc;
}
```

### 3.4 降级策略

```typescript
// 错误回调触发降级
onError(error: Error) {
  console.error('[WebCodecs] Decode failed, falling back to JPEG');
  this.dispose();
  this.onFallback?.(); // 通知上层切换到 JPEG 模式
}

// 能力检测
function isWebCodecsSupported(): boolean {
  return 'VideoDecoder' in window;
}
```

## 4. 架构设计

```
WebSocket 数据流
       │
       ▼
┌──────────────────┐
│  帧类型检测      │
│  0x01/0x02/0x03  │
└──────────────────┘
       │
       ├── 0x01 (SPS/PPS) ──────▶ 缓存
       │
       ├── 0x02 (IDR) ──────────▶ 初始化 VideoDecoder → 解码
       │
       └── 0x03 (P帧) ──────────▶ 解码
              │
              ▼
       ┌──────────────┐
       │ 解码失败     │─────────▶ 降级到 JPEG
       └──────────────┘
```

## 5. 性能优化

| 优化点 | 方案 |
|--------|------|
| 内存管理 | 每帧 `frame.close()` 释放 |
| 渲染同步 | `requestAnimationFrame` 批量渲染 |
| 错误恢复 | 解码错误时重置解码器 |

## 6. 变更文件

| 文件 | 变更 |
|------|------|
| `hooks/useWebCodecsDecoder.ts` | 新建，替代 useH264Decoder.ts |
| `hooks/useWebSocket.ts` | 无变更 |
| `utils/stream.ts` | 添加 Annex-B 转换函数 |
| `package.json` | 移除 broadway-player 依赖 |

## 7. 兼容性

- Chrome 94+ / Edge 94+ / Opera 80+
- 不支持时自动降级到 JPEG（已有机制）