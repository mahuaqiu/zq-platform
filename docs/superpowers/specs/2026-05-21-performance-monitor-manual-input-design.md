---
name: performance-monitor-manual-input
description: 性能采集支持手动输入进程名，用于监控采集开始时尚未启动的进程
---

# 性能采集手动输入进程名设计文档

## 背景

当前性能采集的进程选择只能从**当前运行的进程列表**中选择，无法指定采集开始时尚未运行的进程。

用户场景：测试任务开始采集时，目标进程（如 chrome.exe）可能还未启动，会在测试过程中打开。用户希望能够预先指定进程名，当进程启动后自动被监控。

## 技术调研结果

### perfwin 已支持

perfwin 的 `ProcessFilter::Names(Vec<String>)` 支持预先指定进程名列表：

```rust
pub enum ProcessFilter {
    Pids(Vec<u32>),
    Name(String),
    Names(Vec<String>),     // 多个进程名 ← 关键支持
    NameRegex(String),
}
```

采集循环中，每次都会获取所有进程并筛选匹配的进程名。即使进程一开始不存在，后续启动后也会被自动检测到。

**位置**：`D:\code\perfwin\src\data.rs` 第 57-62 行

### autotest worker 已支持

`TargetProcess` 模型支持进程名筛选：

```python
class TargetProcess(BaseModel):
    name: str                   # 进程名
    pids: list[int] | None      # None 表示采集该进程名下所有实例
```

`_create_monitor` 方法会根据 `pids` 是否为空选择筛选模式：
- `pids` 有值 → Pids 模式
- `pids` 为空 → Names 模式

**位置**：`D:\code\autotest\worker\performance_monitor.py` 第 190-228 行

### 结论

后端和 perfwin 已完全支持，**改动范围仅限于前端 CollectDialog.vue**。

## 设计方案

### UI 改动

在预设进程名标签下方新增手动输入区域：

```
┌─────────────────────────────────────────────┐
│ 预置进程名标签：chrome.exe node.exe python.exe│
├─────────────────────────────────────────────┤
│ ┌───────────────────────────────┐ [添加按钮] │ ← 新增
│ │ 输入进程名(逗号或分号分隔)      │           │
│ └───────────────────────────────┘           │
├─────────────────────────────────────────────┤
│ 进程列表（当前运行 + 手动输入的统一展示）      │
│ □ chrome.exe                                │
│ ☑ node.exe         (已选)                   │
│ □ 手动输入的进程.exe                         │ ← 手动输入的也在这里
│ ...                                         │
└─────────────────────────────────────────────┘
```

### 功能特性

1. **批量输入**：支持逗号 `,` 或分号 `;` 分隔多个进程名
2. **格式验证**：必须是 `.exe` 后缀或无扩展名
3. **统一展示**：手动输入和列表选择的进程名统一展示，不做区分
4. **删除方式**：取消勾选即删除（与现有逻辑一致）

## 实现细节

### 格式验证规则

```typescript
function validateProcessName(name: string): boolean {
  if (!name || name.trim() === '') return false;
  const trimmed = name.trim();
  // 允许无扩展名或 .exe 后缀
  const hasNoExtension = !trimmed.includes('.');
  const hasExeExtension = trimmed.toLowerCase().endsWith('.exe');
  return hasNoExtension || hasExeExtension;
}
```

### 添加逻辑

```typescript
function handleManualAdd() {
  const input = manualInput.value.trim();
  if (!input) return;

  // 按逗号或分号分隔
  const names = input.split(/[;,]/).map(n => n.trim()).filter(n => n);

  // 验证格式
  const invalidNames = names.filter(n => !validateProcessName(n));
  if (invalidNames.length > 0) {
    ElMessage.warning(`格式无效: ${invalidNames.join(', ')}，请使用 .exe 或无扩展名`);
    return;
  }

  // 添加到选中列表（去重）
  const newNames = names.filter(n => !selectedProcessNames.value.includes(n));
  if (newNames.length === 0) {
    ElMessage.info('所有进程名已存在');
    return;
  }

  selectedProcessNames.value.push(...newNames);
  ElMessage.success(`已添加 ${newNames.length} 个进程名`);
  manualInput.value = '';
}
```

### 合并到显示列表

修改 `uniqueProcessNames` 计算属性：

```typescript
const uniqueProcessNames = computed(() => {
  // 当前运行的进程（带实例数统计）
  const runningProcesses = ...; // 现有逻辑

  // 手动输入但未运行的进程名
  const manualProcesses = selectedProcessNames.value
    .filter(name => !runningProcesses.some(p => p.name === name))
    .map(name => ({ name, instanceCount: 0 }));

  // 合并
  return [...runningProcesses, ...manualProcesses];
});
```

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| 输入空字符串 | 忽略，不做任何操作 |
| 输入无效格式（如 `.dll`） | 显示警告提示，不添加 |
| 输入已存在的进程名 | 显示信息提示，跳过已存在的 |
| 设备未连接/进程列表加载失败 | 手动输入功能仍可用 |

## 改动文件清单

| 文件 | 改动内容 |
|------|---------|
| `web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue` | 新增手动输入功能 |

**无需改动的部分**：
- perfwin（已支持）
- autotest worker（已支持）
- zq-platform 后端 API（已支持）