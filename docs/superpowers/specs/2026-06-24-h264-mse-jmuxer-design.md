# H264 推流改用 MSE + jmuxer 方案设计

**日期**: 2026-06-24
**状态**: 已批准

## 1. 背景

原 WebCodecs `VideoDecoder` 方案在 HTTP 内网（非 localhost）部署下始终失败。根因：**WebCodecs `VideoDecoder` 是 Secure Context-only API**（MDN/Chromium 规范），HTTP 页面下 `window.VideoDecoder` 运行时为 `undefined`，表现为 `VideoDecoder is not defined`。这是协议层硬限制，无法靠改前端代码绕过。

用户约束：本项目 HTTP 内网使用，不获取 HTTPS 证书。

**MSE（MediaSource Extensions）不是 Secure Context-only API**，HTTP（非 localhost）下可用，是正确方向。

## 2. 目标

- H264 推流在 HTTP 内网（非 localhost）下正常解码显示
- 保留 JPEG 降级兜底（MSE 初始化失败/异常场景）
- 影响最小：win-recorder 不动；worker 仅 1 处小改；前端聚焦 3-4 个文件
- 复用现有鼠标交互坐标换算

## 3. 数据流（协议几乎不变）

现有链路产出 Annex-B（带 `00 00 00 01` 起始码）H264，正是 jmuxer 原生输入：

```
win-recorder.encode_frame()  →  [1字节前缀][00 00 00 01 ...NAL]
worker WebSocket             →  [前缀][带起始码 Annex-B]
前端 useMseDecoder.feedFrame() →  payload = data.slice(1)   // 去前缀
                             →  jmuxer.feed({ video: payload })
                             →  MediaSource → <video>
```

jmuxer 内部完成：NAL 分片、avcC 封装、fMP4 打包、SPS 尺寸解析。前端省掉 WebCodecs 方案里所有易错逻辑（`annexbToAvcc`/`buildDescription`/`parseSpsDimensions` 等）。

## 4. 改动清单

| # | 项目 | 文件 | 动作 |
|---|------|------|------|
| 1 | zq-platform | `web/apps/web-ele/package.json` | 新增依赖 `jmuxer@^2.1.0`、devDep `@types/jmuxer` |
| 2 | zq-platform | `.../hooks/useMseDecoder.ts` | **新增** jmuxer 封装 hook |
| 3 | zq-platform | `.../hooks/useWebSocket.ts` | H264 分支从 WebCodecs → MSE；透传 video 元素 |
| 4 | zq-platform | `.../hooks/useWebCodecsDecoder.ts` | **删除** |
| 5 | zq-platform | `.../hooks/useScreenInteraction.ts` | `getDisplayCoords` 兼容 `<video>`（videoWidth）与 `<img>`（naturalWidth） |
| 6 | zq-platform | `.../components/ScreenDisplay.vue` | H264 渲染 `<video autoplay muted playsinline>`，JPEG 渲染 `<img>`；暴露 video ref |
| 7 | zq-platform | `.../index.vue` | 透传 codec 模式给 ScreenDisplay |
| 8 | autotest | `worker/server.py` `screen_stream` | SPS+PPS 合并成一条 WebSocket 消息发送 |

**win-recorder 完全不动。**

## 5. worker 小改细节（第 8 项）

当前 worker 分两条消息发 SPS、PPS：

```python
await websocket.send_bytes(bytes([0x01]) + h264_info['sps'])  # SPS
await websocket.send_bytes(bytes([0x01]) + h264_info['pps'])  # PPS
```

改为合并成一条（win-recorder 的 sps/pps 本身各自带 `00 00 00 01` 起始码，合并后是合法多 NAL Annex-B 序列）：

```python
combined = bytes([0x01]) + h264_info['sps'] + h264_info['pps']
await websocket.send_bytes(combined)
```

原因：jmuxer 在首个含 SPS 的包初始化解码器；SPS+PPS 同包送达避免竞态。

## 6. 前端核心：useMseDecoder.ts

```typescript
import JMuxer from 'jmuxer';
import { onUnmounted } from 'vue';
import type { Ref } from 'vue';

export interface MseDecoderOptions {
  videoEl: Ref<HTMLVideoElement | null>;
  fps?: number;
  onReady?: () => void;
  onError?: (e: unknown) => void;
  onFallback?: () => void;
}

export function useMseDecoder(options: MseDecoderOptions) {
  // 关键：经 window. 缓存，避免打包器把全局标识符当模块绑定（WebCodecs 方案的同类教训）
  const _MediaSource = (window as any).MediaSource as typeof MediaSource | undefined;
  let jmuxer: JMuxer | null = null;
  let fallback = false;

  // jmuxer types 未声明 onUnsupportedCodec，构造时用 as 断言补齐
  function init() {
    if (fallback) return;
    if (typeof _MediaSource === 'undefined') {
      console.warn('[MSEDecoder] 浏览器不支持 MediaSource，触发降级');
      fallback = true;
      options.onFallback?.();
      return;
    }
    const el = options.videoEl.value;
    if (!el) return;
    jmuxer = new JMuxer({
      node: el,
      mode: 'video',
      flushingTime: 0,      // 实时推流：立即 flush
      clearBuffer: true,    // 自动清理已播放 buffer，防内存暴涨
      fps: options.fps ?? 10,
      debug: false,
      onReady: () => options.onReady?.(),
      onError: (data: unknown) => {
        console.error('[MSEDecoder] jmuxer error:', data);
        options.onError?.(data);
      },
      onUnsupportedCodec: () => {
        console.error('[MSEDecoder] 不支持的 codec，触发降级');
        options.onFallback?.();
      },
    } as ConstructorParameters<typeof JMuxer>[0]);
  }

  // 帧类型前缀：0x01=SPS/PPS, 0x02=IDR, 0x03=P
  function feedFrame(data: ArrayBuffer): void {
    if (!data || data.byteLength < 2) return;
    if (!jmuxer) return;
    const payload = new Uint8Array(data, 1);  // 去前缀
    jmuxer.feed({ video: payload });
  }

  function dispose(): void {
    if (jmuxer) {
      try { jmuxer.destroy(); } catch { /* 忽略 */ }
      jmuxer = null;
    }
    fallback = false;
  }

  onUnmounted(dispose);
  return { init, feedFrame, dispose };
}
```

关键决策：
- `flusingTime: 0` 实时推流最低延迟
- `clearBuffer: true` 长时间推流内存稳定
- 不传 codec/尺寸——jmuxer 从 SPS 自动解析
- 经 `window.` 缓存 `MediaSource`，规避打包 tree-shaking

## 7. useScreenInteraction.ts 兼容改造

`getDisplayCoords` / `getDeviceCoords` 原先 `event.currentTarget as HTMLImageElement` + `img.naturalWidth`。改为：

```typescript
const media = event.currentTarget as HTMLImageElement | HTMLVideoElement;
const naturalW = 'naturalWidth' in media ? media.naturalWidth : media.videoWidth;
const naturalH = 'naturalHeight' in media ? media.naturalHeight : media.videoHeight;
```

`utils.ts` 的 `calculateContainRenderArea`/`convertToDeviceCoords` 是纯函数，无需改动。

## 8. ScreenDisplay.vue 双模渲染

新增 prop `videoMode: boolean`（H264→true，JPEG→false）。内部条件渲染：

- `videoMode === true`：渲染 `<video ref autoplay muted playsinline>`，事件绑定与 `<img>` 相同（mousedown/mousemove/mouseup/mouseleave/touch/contextmenu）。
- `videoMode === false`：保留现有 `<img :src="screenshotUrl">`。

`object-fit: contain` 对 `<video>` 同样有效，渲染区域计算复用。

## 9. 降级链

```
连接 → H264 模式
  ├─ MediaSource 不存在 → onFallback → reconnect jpeg
  ├─ jmuxer onUnsupportedCodec → onFallback → reconnect jpeg
  └─ 正常 → <video> 实时播放
```

`useWebSocket.ts` 的 `onFallback` 复用现有 `reconnect(..., 'jpeg')`。

## 10. 不做什么（YAGNI）

- 不碰 win-recorder（Annex-B 已对）
- 不删 JPEG/MJPEG 分支（保留降级 + 移动端）
- 不重构 WebSocket 状态机
- 不手写 fMP4 封装（jmuxer 已做）
- 不保留 SPS 手解析逻辑（jmuxer 内部处理）

## 11. 验证标准

1. HTTP 内网（非 localhost）打开设备调试页 → H264 推流成功显示，控制台无 `VideoDecoder is not defined`
2. MSE 初始化失败时自动切 JPEG（devtools 手动删 `MediaSource` 模拟）
3. 双屏切换（monitor 1/2）正常，分辨率自适应（jmuxer 从 SPS 读尺寸，无 1088 黑边）
4. 鼠标点击/拖拽坐标在 `<video>` 上准确（对比 `<img>` 模式）
5. 长时间推流（>10 分钟）内存稳定（clearBuffer 生效）
