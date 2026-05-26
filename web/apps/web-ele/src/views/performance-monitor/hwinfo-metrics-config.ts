/**
 * HWiNFO 传感器指标中英文映射配置
 * key: 英文键名（对应 hwinfo_raw 中的键）
 * label: 中文显示名称
 */

export interface HwinfoMetric {
  key: string;
  label: string;
  unit?: string;
}

/**
 * Linux 系统指标（通过 SSH 采集）
 */
export const LINUX_SYSTEM_METRICS: HwinfoMetric[] = [
  // CPU 指标（百分比）
  { key: 'Linux CPU User', label: 'CPU 用户态', unit: '%' },
  { key: 'Linux CPU System', label: 'CPU 内核态', unit: '%' },
  { key: 'Linux CPU Idle', label: 'CPU 空闲', unit: '%' },
  { key: 'Linux CPU Wait', label: 'CPU I/O等待', unit: '%' },
  { key: 'Linux CPU Steal', label: 'CPU 虚拟化开销', unit: '%' },
  { key: 'Linux CPU Hi', label: 'CPU 硬中断', unit: '%' },
  { key: 'Linux CPU Si', label: 'CPU 软中断', unit: '%' },
  { key: 'Linux CPU Nice', label: 'CPU 低优先级进程', unit: '%' },
  { key: 'Linux CPU Usage', label: 'CPU 总使用率', unit: '%' },

  // 内存指标（MB）
  { key: 'Linux Memory Total', label: '内存总量', unit: 'MB' },
  { key: 'Linux Memory Free', label: '内存空闲', unit: 'MB' },
  { key: 'Linux Memory Available', label: '内存可用', unit: 'MB' },
  { key: 'Linux Memory Buffers', label: '内存缓冲区', unit: 'MB' },
  { key: 'Linux Memory Cached', label: '内存缓存', unit: 'MB' },
  { key: 'Linux Memory Usage', label: '内存使用量', unit: 'MB' },

  // Swap 指标（MB）
  { key: 'Linux Swap Total', label: 'Swap总量', unit: 'MB' },
  { key: 'Linux Swap Free', label: 'Swap空闲', unit: 'MB' },
  { key: 'Linux Swap Used', label: 'Swap使用量', unit: 'MB' },
];

/**
 * 常用指标（主要显示）
 */
export const PRIMARY_HWINFO_METRICS: HwinfoMetric[] = [
  // CPU 温度相关
  { key: 'CPU Package', label: 'CPU 封装温度', unit: '°C' },
  { key: 'Core Max', label: '核心最高温度', unit: '°C' },
  { key: 'CPU IA Cores', label: 'CPU IA 核心温度', unit: '°C' },
  { key: 'CPU GT Cores (Graphics)', label: 'CPU GT 核心温度', unit: '°C' },
  { key: 'CPU Socket', label: 'CPU 插槽温度', unit: '°C' },
  { key: 'PCH Temperature', label: 'PCH 温度', unit: '°C' },

  // CPU 使用率相关
  { key: 'Total CPU Usage', label: 'CPU 总使用率', unit: '%' },
  { key: 'Total CPU Utility', label: 'CPU 总效用', unit: '%' },
  { key: 'Max CPU/Thread Usage', label: '最大线程使用率', unit: '%' },
  { key: 'CPU Busy (avg)', label: 'CPU 平均繁忙度', unit: '%' },
  { key: 'CPU Wait (avg)', label: 'CPU 平均等待', unit: '%' },

  // CPU 频率相关
  { key: 'Core 0 Clock', label: '核心0 频率', unit: 'MHz' },
  { key: 'Core 1 Clock', label: '核心1 频率', unit: 'MHz' },
  { key: 'Core 2 Clock', label: '核心2 频率', unit: 'MHz' },
  { key: 'Core 3 Clock', label: '核心3 频率', unit: 'MHz' },
  { key: 'Core 4 Clock', label: '核心4 频率', unit: 'MHz' },
  { key: 'Core 5 Clock', label: '核心5 频率', unit: 'MHz' },
  { key: 'Average Effective Clock', label: '平均有效频率', unit: 'MHz' },
  { key: 'Bus Clock', label: '总线频率', unit: 'MHz' },
  { key: 'Ring/LLC Clock', label: 'Ring/LLC 频率', unit: 'MHz' },
  { key: 'System Agent Clock', label: '系统代理频率', unit: 'MHz' },
  { key: 'Memory Clock', label: '内存频率', unit: 'MHz' },

  // CPU 功耗相关
  { key: 'CPU Package Power', label: 'CPU 封装功耗', unit: 'W' },
  { key: 'IA Cores Power', label: 'IA 核心功耗', unit: 'W' },
  { key: 'Total DRAM Power', label: '内存总功耗', unit: 'W' },
  { key: 'Rest-of-Chip Power', label: '其余芯片功耗', unit: 'W' },
  { key: 'PL1 Power Limit (Static)', label: 'PL1 功耗限制', unit: 'W' },
  { key: 'PL2 Power Limit (Static)', label: 'PL2 功耗限制', unit: 'W' },

  // GPU 温度相关
  { key: 'GPU Temperature', label: 'GPU 温度', unit: '°C' },
  { key: 'GPU Hot Spot Temperature', label: 'GPU 热点温度', unit: '°C' },
  { key: 'GPU Thermal Limit', label: 'GPU 温度限制', unit: '°C' },

  // GPU 使用率相关
  { key: 'GPU D3D Usage', label: 'GPU D3D 使用率', unit: '%' },
  { key: 'GPU Core Load', label: 'GPU 核心负载', unit: '%' },
  { key: 'GPU Memory Controller Load', label: 'GPU 显存控制器负载', unit: '%' },
  { key: 'GPU Memory Usage', label: 'GPU 显存使用率', unit: '%' },
  { key: 'GPU Bus Load', label: 'GPU 总线负载', unit: '%' },
  { key: 'GPU Video Engine Load', label: 'GPU 视频引擎负载', unit: '%' },
  { key: 'GPU Busy (avg)', label: 'GPU 平均繁忙度', unit: '%' },
  { key: 'GPU Wait (avg)', label: 'GPU 平均等待', unit: '%' },

  // GPU 频率相关
  { key: 'GPU Clock', label: 'GPU 核心频率', unit: 'MHz' },
  { key: 'GPU Memory Clock', label: 'GPU 显存频率', unit: 'MHz' },
  { key: 'GPU Video Clock', label: 'GPU 视频频率', unit: 'MHz' },
  { key: 'GPU Effective Clock', label: 'GPU 有效频率', unit: 'MHz' },

  // GPU 功耗相关
  { key: 'GPU Power', label: 'GPU 功耗', unit: 'W' },
  { key: 'Total GPU Power [% of TDP]', label: 'GPU 总功耗(TDP百分比)', unit: '%' },
  { key: 'Total GPU Power (normalized) [% of TDP]', label: 'GPU 标准化功耗(TDP百分比)', unit: '%' },

  // GPU 显存相关
  { key: 'GPU Memory Allocated', label: 'GPU 显存分配', unit: 'MB' },
  { key: 'GPU Memory Available', label: 'GPU 显存可用', unit: 'MB' },
  { key: 'GPU D3D Memory Dedicated', label: 'GPU D3D 专用显存', unit: 'MB' },
  { key: 'GPU D3D Memory Dynamic', label: 'GPU D3D 动态显存', unit: 'MB' },

  // GPU 视频编解码
  { key: 'GPU Video Decode 0 Usage', label: 'GPU 视频解码0使用率', unit: '%' },
  { key: 'GPU Video Encode 0 Usage', label: 'GPU 视频编码0使用率', unit: '%' },
  { key: 'GPU Video Encode 1 Usage', label: 'GPU 视频编码1使用率', unit: '%' },

  // 内存相关
  { key: 'Physical Memory Available', label: '物理内存可用', unit: 'MB' },
  { key: 'Physical Memory Used', label: '物理内存已用', unit: 'MB' },
  { key: 'Physical Memory Load', label: '物理内存负载', unit: '%' },
  { key: 'Virtual Memory Available', label: '虚拟内存可用', unit: 'MB' },
  { key: 'Virtual Memory Committed', label: '虚拟内存提交', unit: 'MB' },
  { key: 'Virtual Memory Load', label: '虚拟内存负载', unit: '%' },
  { key: 'Page File Total', label: '页面文件总量', unit: 'MB' },
  { key: 'Page File Usage', label: '页面文件使用率', unit: '%' },
  { key: 'Page File Used', label: '页面文件已用', unit: 'MB' },

  // 网络相关
  { key: 'Current DL rate', label: '当前下载速率', unit: 'KB/s' },
  { key: 'Current UP rate', label: '当前上传速率', unit: 'KB/s' },
  { key: 'Total DL', label: '总下载量', unit: 'KB' },
  { key: 'Total UP', label: '总上传量', unit: 'KB' },

  // 磁盘相关
  { key: 'Drive Temperature', label: '硬盘温度', unit: '°C' },
  { key: 'Drive Temperature #2', label: '硬盘温度2', unit: '°C' },
  { key: 'Drive Airflow Temperature', label: '硬盘气流温度', unit: '°C' },
  { key: 'Drive Remaining Life', label: '硬盘剩余寿命', unit: '%' },
  { key: 'Read Rate', label: '读取速率', unit: 'MB/s' },
  { key: 'Write Rate', label: '写入速率', unit: 'MB/s' },
  { key: 'Read Total', label: '读取总量', unit: 'GB' },
  { key: 'Write Total', label: '写入总量', unit: 'GB' },

  // 电压相关
  { key: 'Vcore', label: 'CPU 核心电压', unit: 'V' },
  { key: 'CPU Core Voltage', label: 'CPU 核心电压', unit: 'V' },
  { key: 'GPU Core Voltage', label: 'GPU 核心电压', unit: 'V' },
  { key: '+12V', label: '+12V 电压', unit: 'V' },
  { key: '+5V', label: '+5V 电压', unit: 'V' },
  { key: '+3.3V (3VCC)', label: '+3.3V 主电压', unit: 'V' },
  { key: '+3.3V (AVCC)', label: '+3.3V 辅助电压', unit: 'V' },
  { key: 'VBAT', label: '电池电压', unit: 'V' },
  { key: 'VTT', label: 'VTT 电压', unit: 'V' },

  // 风扇相关
  { key: 'GPU Fan', label: 'GPU 风扇', unit: 'RPM' },
  { key: 'GPU Fan #2', label: 'GPU 风扇2', unit: 'RPM' },

  // 帧率相关
  { key: 'Framerate Displayed (avg)', label: '显示帧率(平均)', unit: 'FPS' },
  { key: 'Framerate Displayed (1%)', label: '显示帧率(1%)', unit: 'FPS' },
  { key: 'Framerate Displayed (0.1%)', label: '显示帧率(0.1%)', unit: 'FPS' },
  { key: 'Framerate Presented (avg)', label: '呈现帧率(平均)', unit: 'FPS' },

  // 系统温度
  { key: 'System', label: '系统温度', unit: '°C' },
  { key: 'MOS', label: 'MOS 温度', unit: '°C' },
];

/**
 * CPU 核心详细指标
 */
export const CPU_CORE_METRICS: HwinfoMetric[] = [
  // 核心 0-5 温度
  { key: 'Core 0', label: '核心0 温度', unit: '°C' },
  { key: 'Core 1', label: '核心1 温度', unit: '°C' },
  { key: 'Core 2', label: '核心2 温度', unit: '°C' },
  { key: 'Core 3', label: '核心3 温度', unit: '°C' },
  { key: 'Core 4', label: '核心4 温度', unit: '°C' },
  { key: 'Core 5', label: '核心5 温度', unit: '°C' },

  // 核心关键温度
  { key: 'Core 0 Critical Temperature', label: '核心0 关键温度', unit: '°C' },
  { key: 'Core 1 Critical Temperature', label: '核心1 关键温度', unit: '°C' },
  { key: 'Core 2 Critical Temperature', label: '核心2 关键温度', unit: '°C' },
  { key: 'Core 3 Critical Temperature', label: '核心3 关键温度', unit: '°C' },
  { key: 'Core 4 Critical Temperature', label: '核心4 关键温度', unit: '°C' },
  { key: 'Core 5 Critical Temperature', label: '核心5 关键温度', unit: '°C' },

  // 核心距离 TJMAX
  { key: 'Core 0 Distance to TjMAX', label: '核心0 距离TjMAX', unit: '°C' },
  { key: 'Core 1 Distance to TjMAX', label: '核心1 距离TjMAX', unit: '°C' },
  { key: 'Core 2 Distance to TjMAX', label: '核心2 距离TjMAX', unit: '°C' },
  { key: 'Core 3 Distance to TjMAX', label: '核心3 距离TjMAX', unit: '°C' },
  { key: 'Core 4 Distance to TjMAX', label: '核心4 距离TjMAX', unit: '°C' },
  { key: 'Core 5 Distance to TjMAX', label: '核心5 距离TjMAX', unit: '°C' },

  // 核心频率倍率
  { key: 'Core 0 Ratio', label: '核心0 倍率', unit: '' },
  { key: 'Core 1 Ratio', label: '核心1 倍率', unit: '' },
  { key: 'Core 2 Ratio', label: '核心2 倍率', unit: '' },
  { key: 'Core 3 Ratio', label: '核心3 倍率', unit: '' },
  { key: 'Core 4 Ratio', label: '核心4 倍率', unit: '' },
  { key: 'Core 5 Ratio', label: '核心5 倍率', unit: '' },

  // 核心VID电压
  { key: 'Core 0 VID', label: '核心0 VID电压', unit: 'V' },
  { key: 'Core 1 VID', label: '核心1 VID电压', unit: 'V' },
  { key: 'Core 2 VID', label: '核心2 VID电压', unit: 'V' },
  { key: 'Core 3 VID', label: '核心3 VID电压', unit: 'V' },
  { key: 'Core 4 VID', label: '核心4 VID电压', unit: 'V' },
  { key: 'Core 5 VID', label: '核心5 VID电压', unit: 'V' },

  // 核心线程使用率
  { key: 'Core 0 T0 Usage', label: '核心0线程0使用率', unit: '%' },
  { key: 'Core 0 T1 Usage', label: '核心0线程1使用率', unit: '%' },
  { key: 'Core 1 T0 Usage', label: '核心1线程0使用率', unit: '%' },
  { key: 'Core 1 T1 Usage', label: '核心1线程1使用率', unit: '%' },
  { key: 'Core 2 T0 Usage', label: '核心2线程0使用率', unit: '%' },
  { key: 'Core 2 T1 Usage', label: '核心2线程1使用率', unit: '%' },
  { key: 'Core 3 T0 Usage', label: '核心3线程0使用率', unit: '%' },
  { key: 'Core 3 T1 Usage', label: '核心3线程1使用率', unit: '%' },
  { key: 'Core 4 T0 Usage', label: '核心4线程0使用率', unit: '%' },
  { key: 'Core 4 T1 Usage', label: '核心4线程1使用率', unit: '%' },
  { key: 'Core 5 T0 Usage', label: '核心5线程0使用率', unit: '%' },
  { key: 'Core 5 T1 Usage', label: '核心5线程1使用率', unit: '%' },

  // 核心线程有效频率
  { key: 'Core 0 T0 Effective Clock', label: '核心0线程0有效频率', unit: 'MHz' },
  { key: 'Core 0 T1 Effective Clock', label: '核心0线程1有效频率', unit: 'MHz' },
  { key: 'Core 1 T0 Effective Clock', label: '核心1线程0有效频率', unit: 'MHz' },
  { key: 'Core 1 T1 Effective Clock', label: '核心1线程1有效频率', unit: 'MHz' },
  { key: 'Core 2 T0 Effective Clock', label: '核心2线程0有效频率', unit: 'MHz' },
  { key: 'Core 2 T1 Effective Clock', label: '核心2线程1有效频率', unit: 'MHz' },
  { key: 'Core 3 T0 Effective Clock', label: '核心3线程0有效频率', unit: 'MHz' },
  { key: 'Core 3 T1 Effective Clock', label: '核心3线程1有效频率', unit: 'MHz' },
  { key: 'Core 4 T0 Effective Clock', label: '核心4线程0有效频率', unit: 'MHz' },
  { key: 'Core 4 T1 Effective Clock', label: '核心4线程1有效频率', unit: 'MHz' },
  { key: 'Core 5 T0 Effective Clock', label: '核心5线程0有效频率', unit: 'MHz' },
  { key: 'Core 5 T1 Effective Clock', label: '核心5线程1有效频率', unit: 'MHz' },

  // 核心热节流状态
  { key: 'Core 0 Thermal Throttling', label: '核心0 热节流', unit: '' },
  { key: 'Core 1 Thermal Throttling', label: '核心1 热节流', unit: '' },
  { key: 'Core 2 Thermal Throttling', label: '核心2 热节流', unit: '' },
  { key: 'Core 3 Thermal Throttling', label: '核心3 热节流', unit: '' },
  { key: 'Core 4 Thermal Throttling', label: '核心4 热节流', unit: '' },
  { key: 'Core 5 Thermal Throttling', label: '核心5 热节流', unit: '' },

  // 核心C状态驻留
  { key: 'Core 0 C3 Residency', label: '核心0 C3驻留', unit: '%' },
  { key: 'Core 0 C7 Residency', label: '核心0 C7驻留', unit: '%' },
  { key: 'Core 1 C3 Residency', label: '核心1 C3驻留', unit: '%' },
  { key: 'Core 1 C7 Residency', label: '核心1 C7驻留', unit: '%' },
  { key: 'Core 2 C3 Residency', label: '核心2 C3驻留', unit: '%' },
  { key: 'Core 2 C7 Residency', label: '核心2 C7驻留', unit: '%' },
  { key: 'Core 3 C3 Residency', label: '核心3 C3驻留', unit: '%' },
  { key: 'Core 3 C7 Residency', label: '核心3 C7驻留', unit: '%' },
  { key: 'Core 4 C3 Residency', label: '核心4 C3驻留', unit: '%' },
  { key: 'Core 4 C7 Residency', label: '核心4 C7驻留', unit: '%' },
  { key: 'Core 5 C3 Residency', label: '核心5 C3驻留', unit: '%' },
  { key: 'Core 5 C7 Residency', label: '核心5 C7驻留', unit: '%' },
];

/**
 * GPU 详细指标
 */
export const GPU_DETAIL_METRICS: HwinfoMetric[] = [
  { key: 'GPU 6-pin #1 Input Power', label: 'GPU 6针脚1输入功耗', unit: 'W' },
  { key: 'GPU 6-pin #1 Input Voltage', label: 'GPU 6针脚1输入电压', unit: 'V' },
  { key: 'GPU Core (NVVDD) Input Power (sum)', label: 'GPU核心输入功耗总和', unit: 'W' },
  { key: 'GPU Core (NVVDD) Output Power', label: 'GPU核心输出功耗', unit: 'W' },
  { key: 'GPU PCIe +12V Input Power', label: 'GPU PCIe 12V输入功耗', unit: 'W' },
  { key: 'GPU PCIe +12V Input Voltage', label: 'GPU PCIe 12V输入电压', unit: 'V' },
  { key: 'GPU Input PP Source Power (sum)', label: 'GPU PP源功耗总和', unit: 'W' },
  { key: 'GPU VR Usage', label: 'GPU VR使用率', unit: '%' },
];

/**
 * 内存时序指标
 */
export const MEMORY_TIMING_METRICS: HwinfoMetric[] = [
  { key: 'Memory Clock Ratio', label: '内存频率倍率', unit: '' },
  { key: 'Command Rate', label: '命令速率', unit: 'T' },
  { key: 'Tcas', label: 'CAS延迟', unit: 'T' },
  { key: 'Trcd', label: 'RCD延迟', unit: 'T' },
  { key: 'Trp', label: 'RP延迟', unit: 'T' },
  { key: 'Tras', label: 'RAS延迟', unit: 'T' },
  { key: 'Trc', label: 'RC延迟', unit: 'T' },
  { key: 'Trfc', label: 'RFC延迟', unit: 'T' },
];

/**
 * PCIe 和错误计数指标
 */
export const PCIE_ERROR_METRICS: HwinfoMetric[] = [
  { key: 'PCIe Link Speed', label: 'PCIe链路速度', unit: 'GT/s' },
  { key: 'Uncore Ratio', label: 'Uncore倍率', unit: '' },

  // PCIe 错误
  { key: 'PCIe Lane 0 Errors', label: 'PCIe通道0错误', unit: '' },
  { key: 'PCIe Lane 1 Errors', label: 'PCIe通道1错误', unit: '' },
  { key: 'PCIe Lane 2 Errors', label: 'PCIe通道2错误', unit: '' },
  { key: 'PCIe Lane 3 Errors', label: 'PCIe通道3错误', unit: '' },

  // 其他错误计数
  { key: 'Correctable Error Count', label: '可纠正错误计数', unit: '' },
  { key: 'Fatal Error Count', label: '致命错误计数', unit: '' },
  { key: 'Non-Fatal Error Count', label: '非致命错误计数', unit: '' },
  { key: 'Total Errors', label: '总错误数', unit: '' },
  { key: 'Bad DLLP Count', label: 'DLLP错误计数', unit: '' },
  { key: 'Bad TLP Count', label: 'TLP错误计数', unit: '' },
  { key: 'LCRC Error Count', label: 'LCRC错误计数', unit: '' },
  { key: 'NAKs Received Count', label: 'NAK接收计数', unit: '' },
  { key: 'NAKs Sent Count', label: 'NAK发送计数', unit: '' },
  { key: 'Receiver Errors', label: '接收器错误', unit: '' },
  { key: 'Replay Count', label: '重播计数', unit: '' },
  { key: 'Replay Rollover Count', label: '重播翻转计数', unit: '' },
  { key: 'Recovery Count', label: '恢复计数', unit: '' },
  { key: 'Unsupported Request Count', label: '不支持请求计数', unit: '' },
];

/**
 * 磁盘详细指标
 */
export const DISK_DETAIL_METRICS: HwinfoMetric[] = [
  { key: 'Read Activity', label: '读取活动', unit: '%' },
  { key: 'Write Activity', label: '写入活动', unit: '%' },
  { key: 'Total Activity', label: '总活动', unit: '%' },
  { key: 'Read Activity #2', label: '读取活动2', unit: '%' },
  { key: 'Write Activity #2', label: '写入活动2', unit: '%' },
  { key: 'Total Activity #2', label: '总活动2', unit: '%' },
  { key: 'Read Rate #2', label: '读取速率2', unit: 'MB/s' },
  { key: 'Write Rate #2', label: '写入速率2', unit: 'MB/s' },
  { key: 'Read Total #2', label: '读取总量2', unit: 'GB' },
  { key: 'Write Total #2', label: '写入总量2', unit: 'GB' },
  { key: 'Total Host Reads', label: '主机读取总量', unit: '' },
  { key: 'Total Host Writes', label: '主机写入总量', unit: '' },
  { key: 'Total NAND Writes', label: 'NAND写入总量', unit: '' },
  { key: 'Drive Failure', label: '硬盘故障', unit: '' },
  { key: 'Drive Warning', label: '硬盘警告', unit: '' },
];

/**
 * 帧率详细指标
 */
export const FRAMERATE_METRICS: HwinfoMetric[] = [
  { key: 'Frame Time Displayed (0.1% high)', label: '帧时间显示(0.1%高)', unit: 'ms' },
  { key: 'Frame Time Displayed (1% high)', label: '帧时间显示(1%高)', unit: 'ms' },
  { key: 'Frame Time Presented (0.1%)', label: '帧时间呈现(0.1%)', unit: 'ms' },
  { key: 'Frame Time Presented (1%)', label: '帧时间呈现(1%)', unit: 'ms' },
  { key: 'Frame Time Presented (99%)', label: '帧时间呈现(99%)', unit: 'ms' },
  { key: 'Frame Time Presented (avg)', label: '帧时间呈现(平均)', unit: 'ms' },
  { key: 'Framerate Displayed (0.1% low)', label: '帧率显示(0.1%低)', unit: 'FPS' },
  { key: 'Framerate Displayed (1% low)', label: '帧率显示(1%低)', unit: 'FPS' },
  { key: 'Framerate Displayed (99%)', label: '帧率显示(99%)', unit: 'FPS' },
  { key: 'Framerate Presented (0.1% low)', label: '帧率呈现(0.1%低)', unit: 'FPS' },
  { key: 'Framerate Presented (1% low)', label: '帧率呈现(1%低)', unit: 'FPS' },
  { key: 'Framerate Presented (99%)', label: '帧率呈现(99%)', unit: 'FPS' },
  { key: 'Animation Error (avg)', label: '动画错误(平均)', unit: '' },
];

/**
 * 其他电压和杂项指标
 */
export const MISC_VOLTAGE_METRICS: HwinfoMetric[] = [
  { key: '3VSB', label: '3V待机电压', unit: 'V' },
  { key: 'VIN2', label: '电压输入2', unit: 'V' },
  { key: 'VIN3', label: '电压输入3', unit: 'V' },
  { key: 'VIN5', label: '电压输入5', unit: 'V' },
  { key: 'VIN7', label: '电压输入7', unit: 'V' },
  { key: 'VIN8', label: '电压输入8', unit: 'V' },
  { key: 'VR VCC Current (SVID IOUT)', label: 'VR VCC电流', unit: 'A' },
  { key: 'On-Demand Clock Modulation', label: '按需时钟调制', unit: '' },
  { key: 'Chassis Intrusion', label: '机箱入侵', unit: '' },
  { key: 'iGPU', label: '集成显卡温度', unit: '°C' },
  { key: 'CPU I/O', label: 'CPU I/O温度', unit: '°C' },
  { key: 'CPU Core', label: 'CPU核心温度', unit: '°C' },
  { key: 'CPU Package #2', label: 'CPU封装温度2', unit: '°C' },
];

/**
 * 所有指标合并列表
 */
export const ALL_HWINFO_METRICS: HwinfoMetric[] = [
  ...LINUX_SYSTEM_METRICS,
  ...PRIMARY_HWINFO_METRICS,
  ...CPU_CORE_METRICS,
  ...GPU_DETAIL_METRICS,
  ...MEMORY_TIMING_METRICS,
  ...PCIE_ERROR_METRICS,
  ...DISK_DETAIL_METRICS,
  ...FRAMERATE_METRICS,
  ...MISC_VOLTAGE_METRICS,
];

/**
 * 获取指标的中文显示名称
 */
export function getMetricLabel(key: string): string {
  const metric = ALL_HWINFO_METRICS.find(m => m.key === key);
  return metric?.label || key;
}

/**
 * 获取指标的单位
 */
export function getMetricUnit(key: string): string | undefined {
  const metric = ALL_HWINFO_METRICS.find(m => m.key === key);
  return metric?.unit;
}