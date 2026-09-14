/**
 * 剪贴板复制工具
 *
 * navigator.clipboard 仅在安全上下文（HTTPS / localhost）可用；
 * 平台只支持 HTTP 部署，非安全上下文下必须降级为
 * document.execCommand('copy')（隐藏 textarea 选中后复制）。
 */

function fallbackCopyText(text: string): boolean {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  // 移出可视区域但仍需可聚焦可选中，不能 display:none（否则无法选中）
  textarea.style.position = 'fixed';
  textarea.style.top = '-9999px';
  textarea.style.opacity = '0';
  document.body.append(textarea);
  textarea.focus();
  textarea.select();
  try {
    return document.execCommand('copy');
  } catch {
    return false;
  } finally {
    textarea.remove();
  }
}

/**
 * 复制文本到剪贴板，兼容 HTTP 部署。
 * 返回是否复制成功，失败时由调用方提示。
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (window.isSecureContext && navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // 权限被拒等异常时继续走降级路径
    }
  }
  return fallbackCopyText(text);
}
