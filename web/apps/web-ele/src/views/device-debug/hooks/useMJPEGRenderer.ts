import { ref, onUnmounted } from 'vue';

export function useMJPEGRenderer() {
  const ctx = ref<CanvasRenderingContext2D | null>(null);
  const imageBitmap = ref<ImageBitmap | null>(null);
  const isRendering = ref(false);

  const init = (canvas: HTMLCanvasElement) => {
    ctx.value = canvas.getContext('2d');
    isRendering.value = true;
  };

  const render = async (data: ArrayBuffer) => {
    if (!ctx.value || !isRendering.value) return;

    try {
      // 创建 Blob URL
      const blob = new Blob([data], { type: 'image/jpeg' });
      const url = URL.createObjectURL(blob);

      // 加载图片并绘制到 canvas
      const img = new Image();
      img.onload = () => {
        if (ctx.value) {
          ctx.value.drawImage(img, 0, 0);
        }
        // 释放资源
        URL.revokeObjectURL(url);
        img.remove();
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
      };
      img.src = url;
    } catch (e) {
      console.error('MJPEG render error:', e);
    }
  };

  const clear = () => {
    if (ctx.value) {
      ctx.value.clearRect(0, 0, ctx.value.canvas.width, ctx.value.canvas.height);
    }
  };

  onUnmounted(() => {
    if (imageBitmap.value) {
      imageBitmap.value.close();
      imageBitmap.value = null;
    }
    isRendering.value = false;
  });

  return {
    init,
    render,
    clear,
    isRendering,
  };
}