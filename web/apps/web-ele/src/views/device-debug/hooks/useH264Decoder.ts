import { ref, onUnmounted } from 'vue';

export interface H264DecoderOptions {
  width: number;
  height: number;
  onReady?: () => void;
  onError?: (error: Error) => void;
}

export function useH264Decoder(options: H264DecoderOptions) {
  const canvasRef = ref<HTMLCanvasElement | null>(null);
  const isReady = ref(false);

  // WASM 解码器 (Broadway/h264bsd)
  const decoder = ref<any>(null);

  const initDecoder = async () => {
    try {
      console.log('[H264Decoder] Initializing WASM decoder...');

      // 动态加载 Broadway WASM 解码器
      // 注意：需要安装 broadway_decoder 或使用其他 H.264 WASM 解码器
      // 这里使用占位符，实际需要 npm install broadway_decoder
      const Broadway = await import('broadway_decoder');

      decoder.value = new Broadway.Decoder({
        canvas: canvasRef.value!,
        output: 'rgb',
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
    if (!isReady.value || !decoder.value) {
      // 解码器未就绪，忽略帧
      return;
    }

    try {
      // 解码 H.264 NAL 单元并渲染到 canvas
      decoder.value.decode(new Uint8Array(data));
    } catch (e) {
      console.error('[H264Decoder] ❌ Decode error:', e);
    }
  };

  const dispose = () => {
    if (decoder.value?.delete) {
      decoder.value.delete();
    }
    decoder.value = null;
    isReady.value = false;
    console.log('[H264Decoder] Decoder disposed');
  };

  onUnmounted(dispose);

  return {
    canvasRef,
    isReady,
    initDecoder,
    appendFrame,
    dispose,
  };
}