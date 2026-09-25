import type { ComputedRef } from 'vue';

import { computed, reactive } from 'vue';

export class Store<T extends Record<string, any>> {
  public state: T;

  private callbacks = new Set<() => void>();

  constructor(initialState: T, options?: { onUpdate?: () => void }) {
    this.state = reactive(initialState) as T;
    if (options?.onUpdate) {
      this.callbacks.add(options.onUpdate);
    }
  }

  setState(updater: (prev: T) => Partial<T>) {
    const newState = updater(this.state);
    Object.assign(this.state, newState);
    this.callbacks.forEach((cb) => cb());
  }
}

export function useStore<T extends Record<string, any>, U = T>(
  store: Store<T>,
  selector?: (state: T) => U,
): ComputedRef<U> {
  // 无 selector 时 U 默认等于 T，断言只是收窄三元两个分支的联合类型
  return computed(() => {
    return selector ? selector(store.state) : store.state;
  }) as ComputedRef<U>;
}
