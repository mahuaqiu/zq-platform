import { describe, expect, it } from 'vitest';

import { filesFromDataTransfer, filesFromInput } from './upload';

function stubFile(name: string, content = 'x'): File {
  return new File([content], name, { type: 'text/plain' });
}

/** 构造 webkitdirectory 风格的 FileList(带 webkitRelativePath) */
function stubFileList(
  entries: Array<{ name: string; relPath: string }>,
): FileList {
  const files = entries.map((e) => {
    const f = stubFile(e.name);
    Object.defineProperty(f, 'webkitRelativePath', { value: e.relPath });
    return f;
  });
  return files as unknown as FileList;
}

interface FakeEntry {
  isFile: boolean;
  isDirectory: boolean;
  name: string;
  file?: File;
  children?: FakeEntry[];
  createReader?: () => {
    readEntries: (resolve: (list: FakeEntry[]) => void) => void;
  };
}

function fakeFileEntry(name: string): FakeEntry {
  // file 在真实 API 上是方法:entry.file(success, error)
  return {
    isFile: true,
    isDirectory: false,
    name,
    file: ((resolve: (f: File) => void) =>
      resolve(stubFile(name))) as unknown as File,
  };
}

function fakeDirEntry(name: string, children: FakeEntry[]): FakeEntry {
  return { isFile: false, isDirectory: true, name, children };
}

/** 构造 DataTransfer 风格的 stub:items[].webkitGetAsEntry() */
function stubDataTransfer(entries: FakeEntry[]): DataTransfer {
  return {
    items: entries.map((entry) => ({
      webkitGetAsEntry: () => entry,
    })),
  } as unknown as DataTransfer;
}

/** 让 fake dir entry 支持 createReader/readEntries 分页语义 */
function withReader(entry: FakeEntry): FakeEntry {
  if (entry.children) {
    entry.createReader = () => {
      let done = false;
      return {
        readEntries: (resolve: (list: FakeEntry[]) => void) => {
          // 首次返回全部,之后返回空,模拟浏览器分页行为
          resolve(done ? [] : (entry.children ?? []));
          done = true;
        },
      };
    };
    entry.children.forEach((child) => {
      if (child.children) withReader(child);
    });
  }
  return entry;
}

describe('文件夹上传路径解析', () => {
  it('webkitdirectory:所选目录名作为子目录,内部结构保留', () => {
    const sources = filesFromInput(
      stubFileList([
        { name: 'a.png', relPath: 'test/a.png' },
        { name: 'b.log', relPath: 'test/sub/b.log' },
      ]),
    );

    expect(sources.map((s) => ({ dir: s.dir, name: s.file.name }))).toEqual([
      { dir: 'test', name: 'a.png' },
      { dir: 'test/sub', name: 'b.log' },
    ]);
  });

  it('webkitdirectory:无相对路径的普通多选文件进当前目录', () => {
    const sources = filesFromInput(
      stubFileList([{ name: 'a.log', relPath: '' }]),
    );

    expect(sources.map((s) => ({ dir: s.dir, name: s.file.name }))).toEqual([
      { dir: '', name: 'a.log' },
    ]);
  });

  it('拖拽文件夹:文件直接落在以文件夹名为根的对应子目录,不额外套同名文件夹', async () => {
    const tree = withReader(
      fakeDirEntry('test', [
        fakeFileEntry('1.png'),
        fakeDirEntry('sub', [fakeFileEntry('b.log')]),
      ]),
    );
    const sources = await filesFromDataTransfer(stubDataTransfer([tree]));

    expect(sources.map((s) => ({ dir: s.dir, name: s.file.name }))).toEqual([
      { dir: 'test', name: '1.png' },
      { dir: 'test/sub', name: 'b.log' },
    ]);
  });

  it('拖拽单个文件:进当前目录', async () => {
    const sources = await filesFromDataTransfer(
      stubDataTransfer([fakeFileEntry('a.log')]),
    );

    expect(sources.map((s) => ({ dir: s.dir, name: s.file.name }))).toEqual([
      { dir: '', name: 'a.log' },
    ]);
  });
});
