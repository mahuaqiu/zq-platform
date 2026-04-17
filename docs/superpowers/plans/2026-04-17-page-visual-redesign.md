# 页面视觉设计重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构三个页面（定时任务、设备监控、测试报告详情）的视觉设计，从彩色渐变改为现代极简企业风格。

**Architecture:** 纯前端 CSS 样式修改，不涉及后端。修改 Vue 组件的 `<style scoped>` 部分，统一配色规范。

**Tech Stack:** Vue 3 + Element Plus + CSS

---

## 文件结构

### 需修改的文件
| 文件 | 修改内容 |
|------|----------|
| `web/apps/web-ele/src/views/scheduler/index.vue` | 统计卡片样式、按钮样式、表格样式 |
| `web/apps/web-ele/src/views/device-monitor/index.vue` | 设备统计、申请统计、TOP10柱状图、移除Emoji |
| `web/apps/web-ele/src/views/test-report/detail/index.vue` | 页面头部、同比展示、表格样式 |
| `web/apps/web-ele/src/views/test-report/detail/components/StatsCards.vue` | 统计卡片样式 |
| `web/apps/web-ele/src/views/test-report/detail/components/RoundAnalysis.vue` | 轮次分析样式 |

---

## Task 1: 定时任务页面 - 统计卡片样式

**文件:** `web/apps/web-ele/src/views/scheduler/index.vue`

- [ ] **Step 1: 修改统计卡片背景和数字颜色**

找到 `<style scoped>` 中的统计卡片样式部分（约第480-495行），修改：

```css
/* 移除渐变背景，改为白色 */
.stat-card {
  background: #fff !important;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  border: 1px solid #e8e8e8;
}

/* 删除渐变背景类 */
.stat-card-purple,
.stat-card-green,
.stat-card-pink,
.stat-card-blue {
  background: #fff !important;
}

/* 修改标题颜色为全黑 */
.stat-label {
  font-size: 13px;
  font-weight: 600;
  color: #111;
}

/* 修改数字颜色 */
.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #3b82f6; /* 默认蓝色 */
}

/* 删除原有的 tr-xxx 颜色类，改为语义色 */
```

- [ ] **Step 2: 在模板中应用新的数字颜色**

修改模板中的统计卡片部分（约第294-317行），为每个卡片的数字添加对应的颜色 class：

```vue
<!-- 总任务数 - 蓝色 -->
<ElCard class="stat-card">
  <div class="stat-content">
    <div class="stat-label">总任务数</div>
    <div class="stat-value stat-blue">{{ statistics.total_jobs }}</div>
  </div>
</ElCard>

<!-- 启用任务 - 绿色 -->
<ElCard class="stat-card">
  <div class="stat-content">
    <div class="stat-label">启用任务</div>
    <div class="stat-value stat-green">{{ statistics.enabled_jobs }}</div>
  </div>
</ElCard>

<!-- 执行成功率 - 绿色 -->
<ElCard class="stat-card">
  <div class="stat-content">
    <div class="stat-label">执行成功率</div>
    <div class="stat-value stat-green">{{ formatSuccessRate(statistics.success_rate) }}</div>
  </div>
</ElCard>

<!-- 今天总执行 - 蓝色 -->
<ElCard class="stat-card">
  <div class="stat-content">
    <div class="stat-label">今天总执行</div>
    <div class="stat-value stat-blue">{{ statistics.total_executions }}</div>
  </div>
</ElCard>
```

- [ ] **Step 3: 添加数字颜色类**

在 `<style scoped>` 中添加：

```css
.stat-blue {
  color: #3b82f6;
}

.stat-green {
  color: #22c55e;
}

.stat-red {
  color: #ef4444;
}

.stat-orange {
  color: #f59e0b;
}
```

- [ ] **Step 4: 启动开发服务器验证**

```bash
cd web && pnpm dev
```

浏览器访问 `/scheduler` 页面，验证：
- 统计卡片为白色背景
- 标题为全黑加粗
- 数字颜色：蓝色/绿色

- [ ] **Step 5: Commit**

```bash
git add web/apps/web-ele/src/views/scheduler/index.vue
git commit -m "refactor(scheduler): 统计卡片改为白色背景+语义色数字"
```

---

## Task 2: 定时任务页面 - 按钮和表格样式

**文件:** `web/apps/web-ele/src/views/scheduler/index.vue`

- [ ] **Step 1: 修改新增任务按钮样式**

找到模板中的新增按钮（约第285-288行），修改为浅灰背景：

```vue
<ElButton class="scheduler-create-btn" @click="handleCreate">
  + 新增任务
</ElButton>
```

修改样式（约第434-440行）：

```css
.scheduler-create-btn {
  background: #f5f5f5 !important;
  color: #111 !important;
  border: 1px solid #d9d9d9 !important;
  font-weight: 500;
}
```

- [ ] **Step 2: 修改查询按钮样式**

找到模板中的查询按钮（约第280-283行），保持蓝色：

```vue
<ElButton type="primary" @click="handleSearch">查询</ElButton>
```

Element Plus 的 `type="primary"` 已是蓝色，无需修改。

- [ ] **Step 3: 修改表格样式**

找到表格样式部分（约第506-555行），确保有完整边框：

```css
.scheduler-table {
  --el-table-border-color: #e8e8e8;
}

/* 表头加粗 */
.scheduler-table :deep(th.el-table__cell) {
  font-weight: 600;
  color: #111;
  background: #fafafa;
}

/* 单元格边框 */
.scheduler-table :deep(td.el-table__cell) {
  border: 1px solid #e8e8e8;
}

/* 状态标签带边框 */
.job-status-success {
  color: #52c41a;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}

.job-status-danger {
  color: #ff4d4f;
  background: #fff1f0;
  border: 1px solid #ffa39e;
}
```

- [ ] **Step 4: 修改分页按钮样式**

确保分页按钮不是黑色，使用 Element Plus 默认样式即可。检查模板中的分页部分（约第367-376行），确保使用标准 ElPagination。

- [ ] **Step 5: 验证样式**

浏览器刷新页面，验证：
- 新增按钮：浅灰背景 + 边框
- 查询按钮：蓝色
- 表格有完整边框
- 表头加粗
- 分页按钮为白色 + 蓝色边框选中态

- [ ] **Step 6: Commit**

```bash
git add web/apps/web-ele/src/views/scheduler/index.vue
git commit -m "refactor(scheduler): 按钮和表格样式优化"
```

---

## Task 3: 设备监控页面 - 页面背景和标题

**文件:** `web/apps/web-ele/src/views/device-monitor/index.vue`

- [ ] **Step 1: 修改页面背景色**

找到 `<style scoped>` 开头（约第335-340行），修改：

```css
.device-monitor-page {
  background: #f0f2f5; /* 改为浅灰 */
  padding: 16px;
}
```

- [ ] **Step 2: 移除 Emoji 图标**

找到模板中的标题部分，移除 Emoji：
- 第161-163行：`🔴 实时状态` → `实时状态`
- 第167行：`📊 设备台数统计` → `设备台数统计`
- 第215行：`⚠️ 异步机器排查` → `异步机器排查`
- 第262行：`📈 申请次数 TOP10 标签` → `申请次数 TOP10 标签`
- 第282行：`⚠️ 资源不足 TOP10 标签` → `资源不足 TOP10 标签`
- 第303行：`⏱️ 机器占用时长 TOP20` → `机器占用时长 TOP20`

- [ ] **Step 3: 修改标题样式**

找到标题样式（约第398-408行），改为全黑加粗：

```css
.left-panel-header {
  font-size: 15px;
  font-weight: 600;
  color: #111;
  border-bottom: 2px solid #e8e8e8;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #111;
}
```

- [ ] **Step 4: 验证**

浏览器访问 `/device-monitor` 页面，验证：
- 页面背景为浅灰 `#f0f2f5`
- 无 Emoji 图标
- 标题为全黑加粗

- [ ] **Step 5: Commit**

```bash
git add web/apps/web-ele/src/views/device-monitor/index.vue
git commit -m "refactor(device-monitor): 页面背景和标题样式优化"
```

---

## Task 4: 设备监控页面 - 设备统计卡片

**文件:** `web/apps/web-ele/src/views/device-monitor/index.vue`

- [ ] **Step 1: 修改设备台数统计卡片背景**

找到模板中的设备统计部分（约第166-210行），修改为白色背景：

```vue
<div class="stats-card device-stats-card">
  <div class="card-title">设备台数统计</div>
  
  <!-- 汇总行 -->
  <div class="summary-row">
    <div class="summary-item">
      <div class="summary-value stat-blue">256</div>
      <div class="summary-label">总数</div>
    </div>
    <div class="summary-item">
      <div class="summary-value stat-green">198</div>
      <div class="summary-label">在线</div>
    </div>
    <div class="summary-item">
      <div class="summary-value stat-red">58</div>
      <div class="summary-label">离线</div>
    </div>
  </div>
  
  <!-- 按类型 -->
  <div class="type-row">
    <div class="type-item">
      <div class="type-value stat-blue">{{ item.total }}</div>
      <div class="type-label">{{ deviceTypeNames[item.type] }}</div>
    </div>
    <!-- ... 其他类型 -->
  </div>
</div>
```

- [ ] **Step 2: 修改样式**

找到样式部分（约第409-495行），修改：

```css
/* 设备统计卡片 */
.device-stats-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

/* 汇总项 - 移除彩色背景 */
.summary-item {
  flex: 1;
  padding: 8px;
  text-align: center;
  background: #f5f5f5;
  border-radius: 6px;
}

.summary-item.purple,
.summary-item.green,
.summary-item.red {
  background: #f5f5f5;
}

/* 数字颜色 */
.summary-value {
  font-size: 20px;
  font-weight: 600;
}

/* 类型数字 */
.type-value {
  font-size: 18px;
  font-weight: 600;
}
```

- [ ] **Step 3: 修改启用/未启用卡片**

找到模板（约第203-210行）和样式：

```vue
<div class="enabled-row">
  <div class="enabled-item enabled-green">启用 186</div>
  <div class="enabled-item enabled-red">未启用 70</div>
</div>
```

```css
.enabled-green {
  background: #dcfce7;
  color: #166534;
  border: 1px solid #86efac;
}

.enabled-red {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fecaca;
}
```

- [ ] **Step 4: 验证**

浏览器刷新，验证：
- 设备统计卡片为白色背景
- 数字颜色：蓝色（总数）、绿色（在线）、红色（离线）
- 启用/未启用有深色背景+边框

- [ ] **Step 5: Commit**

```bash
git add web/apps/web-ele/src/views/device-monitor/index.vue
git commit -m "refactor(device-monitor): 设备统计卡片样式重构"
```

---

## Task 5: 设备监控页面 - 申请统计和TOP10

**文件:** `web/apps/web-ele/src/views/device-monitor/index.vue`

- [ ] **Step 1: 修改24小时申请统计样式**

找到模板（约第235-256行）和样式：

```css
.apply-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.apply-value {
  font-size: 28px;
  font-weight: 600;
  color: #3b82f6; /* 蓝色 */
}

.detail-value.success {
  color: #22c55e;
}

.detail-value.insufficient {
  color: #f59e0b;
}

.detail-value.failed {
  color: #ef4444;
}
```

- [ ] **Step 2: 修改TOP10柱状图颜色**

找到样式（约第654-668行），将黑色改为蓝色：

```css
/* 申请次数 TOP10 - 蓝色 */
.top-bar {
  height: 14px;
  background: #3b82f6;
  border-radius: 3px;
}

/* 资源不足 TOP10 - 红色 */
.top-bar.red {
  background: #ef4444;
}
```

- [ ] **Step 3: 修改离线设备卡片**

找到模板和样式：

```css
.offline-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.offline-item {
  background: #fff5f5;
  border: 1px solid #fecaca;
  border-radius: 8px;
}
```

- [ ] **Step 4: 验证**

浏览器刷新，验证：
- 申请统计数字颜色正确
- TOP10柱状图为蓝色（非黑色）
- 离线设备卡片有浅红色背景+边框

- [ ] **Step 5: Commit**

```bash
git add web/apps/web-ele/src/views/device-monitor/index.vue
git commit -m "refactor(device-monitor): 申请统计和TOP10样式优化"
```

---

## Task 6: 测试报告 - 统计卡片组件

**文件:** `web/apps/web-ele/src/views/test-report/detail/components/StatsCards.vue`

- [ ] **Step 1: 修改卡片样式**

找到 `<style scoped>`（约第62-119行），修改：

```css
.stats-cards {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: #fff;
}

.stats-card {
  flex: 1;
  text-align: center;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  border: 1px solid #e8e8e8;
}

.stats-card :deep(.el-card__body) {
  padding: 20px;
}

.stats-value {
  font-size: 32px;
  font-weight: 600;
}

/* 标题全黑加粗 */
.stats-label {
  font-size: 14px;
  font-weight: 600;
  color: #111;
}

/* 语义色 */
.stat-blue {
  color: #3b82f6;
}

.stat-green {
  color: #22c55e;
}

.stat-red {
  color: #ef4444;
}

.stat-orange {
  color: #f59e0b;
}
```

- [ ] **Step 2: 移除旧的颜色类**

删除原有的颜色类：

```css
/* 删除这些 */
.tr-blue { color: #1890ff; }
.tr-cyan { color: #13c2c2; }
.tr-green { color: #52c41a; }
.tr-red { color: #ff4d4f; }
.tr-orange { color: #faad14; }
.tr-gray { color: #999; }
```

- [ ] **Step 3: 修改模板**

找到模板部分（约第26-58行），修改每个卡片：

```vue
<ElCard class="stats-card">
  <div class="stats-label">用例总数</div>
  <div class="stats-value stat-blue">{{ summary?.totalCases ?? '--' }}</div>
</ElCard>
<ElCard class="stats-card">
  <div class="stats-label">执行总数</div>
  <div class="stats-value stat-blue">{{ summary?.executeTotal ?? '--' }}</div>
</ElCard>
<ElCard class="stats-card">
  <div class="stats-label">通过率</div>
  <div class="stats-value stat-green">{{ summary?.passRate ?? '--' }}</div>
</ElCard>
<ElCard class="stats-card">
  <div class="stats-label">失败总数</div>
  <div class="stats-value stat-red">{{ summary?.failTotal ?? '--' }}</div>
</ElCard>
<ElCard class="stats-card">
  <div class="stats-label">同比上次执行</div>
  <div class="stats-value" :class="compareDisplay.cls">{{ compareDisplay.text }}</div>
  <div class="stats-sub" v-if="compareDisplay.sub">{{ compareDisplay.sub }}</div>
</ElCard>
<ElCard class="stats-card">
  <div class="stats-label">每轮都失败</div>
  <div class="stats-value stat-orange">{{ summary?.failAlways ?? '--' }}</div>
  <div class="stats-sub" style="color: #111">重点关注</div>
</ElCard>
<ElCard class="stats-card">
  <div class="stats-label">不稳定用例</div>
  <div class="stats-value stat-blue">{{ summary?.failUnstable ?? '--' }}</div>
  <div class="stats-sub">重试后通过</div>
</ElCard>
```

- [ ] **Step 4: 验证**

浏览器访问测试报告详情页，验证：
- 卡片为白色背景
- 标题为全黑加粗
- 数字颜色：蓝色（总数）、绿色（通过）、红色（失败）、橙色（每轮都失败）

- [ ] **Step 5: Commit**

```bash
git add web/apps/web-ele/src/views/test-report/detail/components/StatsCards.vue
git commit -m "refactor(test-report): 统计卡片样式重构"
```

---

## Task 7: 测试报告 - 轮次分析组件

**文件:** `web/apps/web-ele/src/views/test-report/detail/components/RoundAnalysis.vue`

- [ ] **Step 1: 修改样式**

找到 `<style scoped>`（约第36-97行），修改：

```css
.round-analysis {
  padding: 16px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.round-title {
  font-size: 15px;
  font-weight: 600;
  color: #111;
}

.round-cards {
  display: flex;
  gap: 16px;
}

.round-card {
  padding: 16px 24px;
  background: #fff;
  border-radius: 8px;
  text-align: center;
}

/* 第一轮失败 - 红色背景 */
.round-red {
  background: #fee2e2;
  border: 1px solid #fecaca;
}
.round-red .round-value {
  color: #ef4444;
}

/* 中间轮次 - 橙色背景 */
.round-orange {
  background: #fef3c7;
  border: 1px solid #fcd34d;
}
.round-orange .round-value {
  color: #f59e0b;
}

/* 最后一轮 - 绿色背景 */
.round-green {
  background: #dcfce7;
  border: 1px solid #86efac;
}
.round-green .round-value {
  color: #22c55e;
}
```

- [ ] **Step 2: 验证**

浏览器刷新，验证：
- 标题为全黑加粗
- 第一轮失败：红色背景+边框
- 中间轮次：橙色背景+边框
- 最后一轮：绿色背景+边框

- [ ] **Step 3: Commit**

```bash
git add web/apps/web-ele/src/views/test-report/detail/components/RoundAnalysis.vue
git commit -m "refactor(test-report): 轮次分析样式优化"
```

---

## Task 8: 测试报告详情页 - 主页面样式

**文件:** `web/apps/web-ele/src/views/test-report/detail/index.vue`

- [ ] **Step 1: 修改页面头部样式**

找到模板和样式（约第72-145行），修改：

```css
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: #111;
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* 导出报告按钮 */
.header-actions .el-button:first-child {
  background: #fff;
  color: #1890ff;
  border: 1px solid #1890ff;
}

/* 返回列表按钮 */
.header-actions .el-button:last-child {
  background: #f5f5f5;
  color: #666;
  border: 1px solid #d9d9d9;
}
```

- [ ] **Step 2: 修改同比上次执行展示**

找到模板中的 AI 分析区前的同比部分，重新设计为一行展示：

```vue
<!-- 同比变化 -->
<div class="compare-section">
  <div class="compare-title">同比上次执行</div>
  <div class="compare-content">
    <div class="compare-item">
      <div class="compare-value compare-red">{{ summary?.lastFailTotal ?? 73 }}</div>
      <div class="compare-label">上次失败</div>
    </div>
    <div class="compare-arrow">
      <div class="arrow-icon">→</div>
      <div class="arrow-badge">
        <span>↓{{ summary?.compareChange ?? 12 }}</span>
      </div>
    </div>
    <div class="compare-item">
      <div class="compare-value compare-red">{{ summary?.failTotal ?? 61 }}</div>
      <div class="compare-label">本次失败</div>
    </div>
  </div>
</div>
```

添加样式：

```css
.compare-section {
  padding: 24px;
  background: #fff;
  border-radius: 12px;
  margin-bottom: 24px;
}

.compare-title {
  font-size: 15px;
  font-weight: 600;
  color: #111;
  margin-bottom: 16px;
}

.compare-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
}

.compare-item {
  text-align: center;
}

.compare-value {
  font-size: 48px;
  font-weight: 600;
}

.compare-red {
  color: #ef4444;
}

.compare-green {
  color: #22c55e;
}

.compare-label {
  font-size: 14px;
  color: #666;
}

.compare-arrow {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0 40px;
}

.arrow-icon {
  font-size: 24px;
  color: #22c55e;
  margin-bottom: 4px;
}

.arrow-badge {
  background: #f0fdf4;
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid #86efac;
}

.arrow-badge span {
  font-size: 14px;
  font-weight: 600;
  color: #22c55e;
}
```

- [ ] **Step 3: 修改表格样式**

确保表格有完整边框：

```css
.fail-table {
  --el-table-border-color: #e8e8e8;
}

.fail-table :deep(th.el-table__cell) {
  font-weight: 600;
  color: #111;
  background: #fafafa;
}
```

- [ ] **Step 4: 验证**

浏览器刷新，验证：
- 页面头部按钮样式正确
- 同比为一行展示，数字放大居中
- 表格有完整边框

- [ ] **Step 5: Commit**

```bash
git add web/apps/web-ele/src/views/test-report/detail/index.vue
git commit -m "refactor(test-report): 主页面样式优化"
```

---

## Task 9: 最终验收

- [ ] **Step 1: 启动开发服务器**

```bash
cd web && pnpm dev
```

- [ ] **Step 2: 验收三个页面**

逐个访问页面，检查验收标准：

| 检查项 | 定时任务 | 设备监控 | 测试报告 |
|--------|----------|----------|----------|
| 页面背景 #f0f2f5 | ☐ | ☐ | ☐ |
| 卡片白色背景 | ☐ | ☐ | ☐ |
| 无 Emoji 图标 | ☐ | ☐ | ☐ |
| 无彩色渐变 | ☐ | ☐ | ☐ |
| 标题全黑加粗 | ☐ | ☐ | ☐ |
| 数字语义色 | ☐ | ☐ | ☐ |
| 表格有边框 | ☐ | ☐ | ☐ |
| 按钮样式统一 | ☐ | ☐ | ☐ |

- [ ] **Step 3: Final Commit**

```bash
git add -A
git commit -m "refactor: 三个页面视觉设计重构完成

- 定时任务页面：统计卡片白色背景+语义色数字
- 设备监控页面：移除Emoji，统一配色
- 测试报告详情页：统计卡片和轮次分析样式优化

设计风格：现代极简企业风格，统一配色规范"
```

---

## 验收标准

1. ✅ 三个页面风格统一
2. ✅ 无彩色渐变背景
3. ✅ 无 Emoji 图标
4. ✅ 数字颜色遵循语义色规范（蓝/绿/橙/红）
5. ✅ 标题全黑加粗 `#111`
6. ✅ 表格有完整边框
7. ✅ 按钮样式统一（蓝色主要、白色次要）