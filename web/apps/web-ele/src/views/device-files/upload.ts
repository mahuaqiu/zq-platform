export interface UploadSource {
  /** 相对当前目录的目标子目录,'' 表示当前目录 */
  dir: string;
  file: File;
}

/**
 * input[webkitdirectory] 的文件都带 webkitRelativePath:
 * "所选目录名/子目录/文件名"。首段即所选目录名,在当前目录下按该名字
 * 重建整棵结构;普通多选文件(无相对路径)进当前目录。
 */
export function filesFromInput(files: FileList): UploadSource[] {
  return [...files].map((file) => {
    const rel =
      (file as File & { webkitRelativePath?: string }).webkitRelativePath ||
      file.name;
    const segments = rel.split('/');
    segments.pop();
    return { dir: segments.join('/'), file };
  });
}

/** 拖拽:文件进当前目录;文件夹以其名称为子目录,保留内部结构 */
export async function filesFromDataTransfer(
  dt: DataTransfer,
): Promise<UploadSource[]> {
  const out: UploadSource[] = [];
  for (const item of dt.items || []) {
    const entry = (item as any).webkitGetAsEntry?.();
    if (!entry) continue;
    if (entry.isFile) {
      const file: File = await new Promise((resolve, reject) =>
        entry.file(resolve, reject),
      );
      out.push({ dir: '', file });
    } else if (entry.isDirectory) {
      // 拖入文件夹:以其名称为子目录,内部结构原样保留。
      // 注意 prefix 是"文件所在的父目录",文件自己的名字只作上传名,
      // 不能再拼进目录,否则每个文件都会被套进一层同名文件夹
      await walkDir(entry, entry.name);
    }
  }
  return out;

  async function walkDir(dirEntry: any, base: string): Promise<void> {
    const reader = dirEntry.createReader();
    // readEntries 每次最多返回 100 条,读到空为止
    const readAll = async (): Promise<any[]> => {
      const batch: any[] = await new Promise((resolve, reject) =>
        reader.readEntries(resolve, reject),
      );
      return batch.length > 0 ? [...batch, ...(await readAll())] : [];
    };
    for (const child of await readAll()) {
      if (child.isFile) {
        const file: File = await new Promise((resolve, reject) =>
          child.file(resolve, reject),
        );
        out.push({ dir: base, file });
      } else if (child.isDirectory) {
        await walkDir(child, `${base}/${child.name}`);
      }
    }
  }
}
