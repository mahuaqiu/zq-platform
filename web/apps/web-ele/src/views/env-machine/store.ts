import { acceptHMRUpdate, defineStore } from 'pinia';

import { getNamespaceConfigApi } from '#/api/core/env-machine';

interface NamespaceState {
  /**
   * 命名空间配置映射
   * 格式: {"meeting_gamma": "集成验证", "meeting_app": "APP", ...}
   */
  namespaceMap: Record<string, string>;
  /**
   * 是否已加载
   */
  loaded: boolean;
}

/**
 * 命名空间配置选项类型
 */
export interface NamespaceOption {
  label: string;
  value: string;
}

/**
 * 命名空间配置 Store
 * 统一管理命名空间配置，从后端动态获取，避免前端多环境配置不一致
 */
export const useNamespaceStore = defineStore('namespace-config', {
  actions: {
    /**
     * 从后端加载命名空间配置
     */
    async loadNamespaceConfig() {
      if (this.loaded) return;

      try {
        this.namespaceMap = await getNamespaceConfigApi();
        this.loaded = true;
      } catch (error) {
        console.error('加载命名空间配置失败:', error);
        // 加载失败时使用空对象，避免阻塞页面
        this.namespaceMap = {};
        this.loaded = true;
      }
    },

    /**
     * 重置状态（用于重新加载）
     */
    reset() {
      this.namespaceMap = {};
      this.loaded = false;
    },
  },

  getters: {
    /**
     * 命名空间选项（用于筛选下拉框，第一项为空值"全部"）
     */
    namespaceOptions(): NamespaceOption[] {
      return [
        { label: '全部', value: '' },
        ...Object.entries(this.namespaceMap).map(([value, label]) => ({
          label: String(label),
          value,
        })),
      ];
    },

    /**
     * 命名空间选项（带全部选项，value='all'）
     */
    namespaceOptionsWithAll(): NamespaceOption[] {
      return [
        { label: '全部', value: 'all' },
        ...Object.entries(this.namespaceMap).map(([value, label]) => ({
          label: String(label),
          value,
        })),
      ];
    },

    /**
     * 命名空间选项（弹窗用，第一项为"全部命名空间"）
     */
    namespaceOptionsDialog(): NamespaceOption[] {
      return [
        { label: '全部命名空间', value: '' },
        ...Object.entries(this.namespaceMap).map(([value, label]) => ({
          label: String(label),
          value,
        })),
      ];
    },

    /**
     * 获取命名空间显示文本
     */
    getNamespaceText(): (namespace: string) => string {
      return (namespace: string) => this.namespaceMap[namespace] || namespace;
    },
  },

  state: (): NamespaceState => ({
    namespaceMap: {},
    loaded: false,
  }),
});

// 解决热更新问题
const hot = import.meta.hot;
if (hot) {
  hot.accept(acceptHMRUpdate(useNamespaceStore, hot));
}