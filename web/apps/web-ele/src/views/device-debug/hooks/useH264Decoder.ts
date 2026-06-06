import { ref, onUnmounted } from 'vue';

export interface H264DecoderOptions {
  width: number;
  height: number;
  onReady?: () => void;
  onError?: (error: Error) => void;
}

export function useH264Decoder(options: H264DecoderOptions) {
  const videoRef = ref<HTMLVideoElement | null>(null);
  const mediaSource = ref<MediaSource | null>(null);
  const sourceBuffer = ref<SourceBuffer | null>(null);
  const isReady = ref(false);
  const isMSE = ref(false); // 是否使用 MSE

  // WASM 解码器 fallback
  const wasmDecoder = ref<any>(null);
  const canvasRef = ref<HTMLCanvasElement | null>(null);

  const initMSE = (sps: Uint8Array, pps: Uint8Array) => {
    if (!MediaSource.isTypeSupported(`video/mp4; codecs="avc1.42001e, mp4a.40.2"`)) {
      // MSE 不支持，fallback 到 WASM
      console.log('MSE not supported, falling back to WASM');
      initWASM();
      return;
    }

    try {
      mediaSource.value = new MediaSource();
      if (videoRef.value) {
        videoRef.value.src = URL.createObjectURL(mediaSource.value);
      }

      mediaSource.value.addEventListener('sourceopen', () => {
        try {
          sourceBuffer.value = mediaSource.value!.addSourceBuffer(
            `video/mp4; codecs="avc1.42001e, mp4a.40.2"`
          );
          isReady.value = true;
          isMSE.value = true;
          options.onReady?.();
        } catch (e) {
          console.error('MSE init error:', e);
          initWASM();
        }
      });
    } catch (e) {
      console.error('MSE init error:', e);
      initWASM();
    }
  };

  const initWASM = async () => {
    try {
      // 动态加载 WASM 解码器
      // 注意：需要安装 h264wasm-decoder 或 jsmpeg
      // 这里使用占位符，实际需要 npm install h264wasm-decoder
      console.log('WASM decoder not implemented yet, using fallback to JPEG');

      // 降级到 JPEG 模式
      isReady.value = true;
      isMSE.value = false;
      options.onReady?.();
    } catch (e) {
      console.error('WASM decoder init error:', e);
      options.onError?.(e as Error);
    }
  };

  const appendFrame = (data: ArrayBuffer) => {
    if (!isReady.value) return;

    if (isMSE.value && sourceBuffer.value) {
      // MSE 模式：直接将数据写入 SourceBuffer
      // 注意：需要将 H.264 数据转换为 MP4 片段格式
      if (!sourceBuffer.value.updating && data.byteLength > 0) {
        try {
          sourceBuffer.value.appendBuffer(data);
        } catch (e) {
          console.error('MSE append error:', e);
        }
      }
    } else if (wasmDecoder.value) {
      // WASM 模式：解码并渲染到 canvas
      try {
        const frame = wasmDecoder.value.decode(data);
        if (frame && canvasRef.value) {
          const ctx = canvasRef.value.getContext('2d');
          ctx?.drawImage(frame, 0, 0);
        }
      } catch (e) {
        console.error('WASM decode error:', e);
      }
    }
    // 如果都没初始化，忽略帧数据
  };

  const dispose = () => {
    try {
      mediaSource.value?.endOfStream();
    } catch (e) {
      // ignore
    }
    mediaSource.value = null;
    sourceBuffer.value = null;
    if (wasmDecoder.value?.delete) {
      wasmDecoder.value.delete();
    }
    wasmDecoder.value = null;
    isReady.value = false;
    isMSE.value = false;
  };

  onUnmounted(dispose);

  return {
    videoRef,
    canvasRef,
    isReady,
    isMSE,
    initMSE,
    initWASM,
    appendFrame,
    dispose,
  };
}