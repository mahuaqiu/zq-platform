# 性能采集手动输入进程名实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在性能采集弹窗中新增手动输入进程名功能，支持用户输入采集开始时尚未运行的进程名。

**Architecture:** 仅修改前端 CollectDialog.vue，在进程名模式下新增输入框和添加按钮，将手动输入的进程名合并到显示列表中。

**Tech Stack:** Vue 3 + Element Plus + TypeScript

**Spec:** `docs/superpowers/specs/2026-05-21-performance-monitor-manual-input-design.md`

---

## 改动文件结构

| 文件 | 改动类型 | 职责 |
|------|---------|------|
| `web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue` | 修改 | 新增手动输入功能 |

---

### Task 1: 新增模板区域（输入框 + 添加按钮）

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue:258-268` (在 preset-tags 区域后)

- [ ] **Step 1: 添加输入框和按钮模板**

在 `<div class="preset-tags">` 区域后添加：

```vue
<!-- 手动输入进程名 -->
<div class="manual-input-wrapper">
  <el-input
    v-model="manualInput"
    placeholder="输入进程名(逗号或分号分隔)"
    size="small"
    clearable
    style="flex: 1"
  />
  <button class="add-btn" @click="handleManualAdd">添加</button>
</div>
```

位置：第 268 行（`</div>` preset-tags 结束标签）后

- [ ] **Step 2: 添加样式**

在 `<style scoped>` 区域添加：

```css
.manual-input-wrapper {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}
.add-btn {
  padding: 0 12px;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
  height: 24px;
  line-height: 24px;
}
.add-btn:hover {
  background: #66b1ff;
}
```

位置：第 518 行（`.start-btn:disabled` 后）

- [ ] **Step 3: 本地验证模板渲染**

启动前端开发服务器：
```bash
cd D:/code/zq-platform/web && pnpm dev
```

打开浏览器访问性能监控页面，点击开始采集弹窗，确认输入框和按钮显示正常。

---

### Task 2: 新增 script 变量和函数

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue:37-42` (script 变量区域)

- [ ] **Step 1: 添加 manualInput ref 变量**

在第 42 行（`const presetProcesses = ...`）后添加：

```typescript
// 手动输入的进程名
const manualInput = ref('');
```

- [ ] **Step 2: 添加格式验证函数**

在第 147 行（`isProcessSelected` 函数后）添加：

```typescript
/**
 * 验证进程名格式
 * 允许：chrome.exe、chrome、app.exe
 * 拒绝：chrome.dll、app.txt、空字符串
 */
function validateProcessName(name: string): boolean {
  if (!name || name.trim() === '') return false;
  const trimmed = name.trim();
  // 允许无扩展名或 .exe 后缀
  const hasNoExtension = !trimmed.includes('.');
  const hasExeExtension = trimmed.toLowerCase().endsWith('.exe');
  return hasNoExtension || hasExeExtension;
}
```

- [ ] **Step 3: 添加 handleManualAdd 函数**

在 `validateProcessName` 函数后添加：

```typescript
/**
 * 处理手动添加进程名
 * 1. 按逗号或分号分隔
 * 2. 验证每个进程名格式
 * 3. 过滤已存在的进程名（避免重复）
 * 4. 添加到选中列表
 */
function handleManualAdd() {
  const input = manualInput.value.trim();
  if (!input) return;

  // 按逗号或分号分隔
  const names = input.split(/[;,]/).map((n) => n.trim()).filter((n) => n);

  // 验证格式
  const invalidNames = names.filter((n) => !validateProcessName(n));
  if (invalidNames.length > 0) {
    ElMessage.warning(`格式无效: ${invalidNames.join(', ')}，请使用 .exe 或无扩展名`);
    return;
  }

  // 添加到选中列表（去重）
  const newNames = names.filter((n) => !selectedProcessNames.value.includes(n));
  if (newNames.length === 0) {
    ElMessage.info('所有进程名已存在');
    return;
  }

  selectedProcessNames.value.push(...newNames);
  ElMessage.success(`已添加 ${newNames.length} 个进程名`);
  manualInput.value = '';
}
```

---

### Task 3: 修改 uniqueProcessNames 计算属性

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue:59-79`

- [ ] **Step 1: 修改 uniqueProcessNames 计算属性**

将原有的 `uniqueProcessNames` 计算属性替换为：

```typescript
// 进程名模式下的唯一进程名列表（带实例数统计）
const uniqueProcessNames = computed(() => {
  // 先过滤搜索结果
  const filtered = searchQuery.value
    ? processList.value.filter((p) =>
        p.name.toLowerCase().includes(searchQuery.value.toLowerCase()),
      )
    : processList.value;

  // 统计每个进程名的实例数
  const nameCountMap = new Map<string, number>();
  for (const p of filtered) {
    nameCountMap.set(p.name, (nameCountMap.get(p.name) || 0) + 1);
  }

  // 当前运行的进程（带实例数统计）
  const runningProcesses = Array.from(nameCountMap.entries()).map(([name, count]) => ({
    name,
    instanceCount: count,
  }));

  // 手动输入但未运行的进程名（从选中列表中筛选）
  const manualProcesses = selectedProcessNames.value
    .filter((name) => !runningProcesses.some((p) => p.name === name))
    .map((name) => ({ name, instanceCount: 0 }));

  // 合并：运行的 + 手动输入的
  return [...runningProcesses, ...manualProcesses];
});
```

---

### Task 4: 验证和提交

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue`

- [ ] **Step 1: 类型检查**

```bash
cd D:/code/zq-platform/web && pnpm check:type
```

Expected: 无类型错误

- [ ] **Step 2: 功能测试**

启动前端开发服务器：
```bash
cd D:/code/zq-platform/web && pnpm dev
```

测试场景：
1. 打开性能监控页面，点击开始采集
2. 选择"按进程名采集"模式
3. 在输入框输入 `chrome.exe,notepad.exe`，点击添加
4. 确认进程名添加到选中列表，显示成功提示
5. 测试无效格式 `test.dll`，确认显示警告提示
6. 测试重复添加，确认显示信息提示
7. 取消勾选手动添加的进程名，确认可删除

- [ ] **Step 3: 提交代码**

```bash
cd D:/code/zq-platform
git add web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue
git commit -m "feat(performance-monitor): 支持手动输入进程名进行采集"
```

---

## 完整代码改动摘要

### 模板改动（第 268 行后）

```vue
<!-- 手动输入进程名 -->
<div class="manual-input-wrapper">
  <el-input
    v-model="manualInput"
    placeholder="输入进程名(逗号或分号分隔)"
    size="small"
    clearable
    style="flex: 1"
  />
  <button class="add-btn" @click="handleManualAdd">添加</button>
</div>
```

### Script 改动

**新增变量（第 42 行后）：**
```typescript
const manualInput = ref('');
```

**新增函数（第 147 行后）：**
```typescript
function validateProcessName(name: string): boolean {
  if (!name || name.trim() === '') return false;
  const trimmed = name.trim();
  const hasNoExtension = !trimmed.includes('.');
  const hasExeExtension = trimmed.toLowerCase().endsWith('.exe');
  return hasNoExtension || hasExeExtension;
}

function handleManualAdd() {
  const input = manualInput.value.trim();
  if (!input) return;
  const names = input.split(/[;,]/).map((n) => n.trim()).filter((n) => n);
  const invalidNames = names.filter((n) => !validateProcessName(n));
  if (invalidNames.length > 0) {
    ElMessage.warning(`格式无效: ${invalidNames.join(', ')}，请使用 .exe 或无扩展名`);
    return;
  }
  const newNames = names.filter((n) => !selectedProcessNames.value.includes(n));
  if (newNames.length === 0) {
    ElMessage.info('所有进程名已存在');
    return;
  }
  selectedProcessNames.value.push(...newNames);
  ElMessage.success(`已添加 ${newNames.length} 个进程名`);
  manualInput.value = '';
}
```

**修改计算属性（替换第 59-79 行）：**
```typescript
const uniqueProcessNames = computed(() => {
  const filtered = searchQuery.value
    ? processList.value.filter((p) =>
        p.name.toLowerCase().includes(searchQuery.value.toLowerCase()),
      )
    : processList.value;

  const nameCountMap = new Map<string, number>();
  for (const p of filtered) {
    nameCountMap.set(p.name, (nameCountMap.get(p.name) || 0) + 1);
  }

  const runningProcesses = Array.from(nameCountMap.entries()).map(([name, count]) => ({
    name,
    instanceCount: count,
  }));

  const manualProcesses = selectedProcessNames.value
    .filter((name) => !runningProcesses.some((p) => p.name === name))
    .map((name) => ({ name, instanceCount: 0 }));

  return [...runningProcesses, ...manualProcesses];
});
```

### Style 改动（第 518 行后）

```css
.manual-input-wrapper {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}
.add-btn {
  padding: 0 12px;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
  height: 24px;
  line-height: 24px;
}
.add-btn:hover {
  background: #66b1ff;
}
```