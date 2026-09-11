<script lang="ts" setup>
import type { ConfigCenterItem, KeyValuePair } from '#/api/core/config-center';

import { computed, ref } from 'vue';

import { ZqDrawer } from '#/components/zq-drawer';

import {
  ElAlert,
  ElButton,
  ElDialog,
  ElFormItem,
  ElInput,
  ElMessage,
  ElTable,
  ElTableColumn,
} from 'element-plus';

import {
  buildConfigValue,
  createConfigItemApi,
  updateConfigItemApi,
} from '#/api/core/config-center';

const emit = defineEmits<{
  success: [];
}>();

const visible = ref(false);
const confirmLoading = ref(false);
const formData = ref<{ id?: string; key: string; remark: string }>({
  key: '',
  remark: '',
});
const pairs = ref<KeyValuePair[]>([{ key: '', value: '' }]);
const keyError = ref('');

// 批量粘贴导入
const pasteVisible = ref(false);
const pasteText = ref('');

const isEdit = computed(() => !!formData.value.id);
const drawerTitle = computed(() => (isEdit.value ? '编辑配置' : '新增配置'));

function emptyPair(): KeyValuePair {
  return { key: '', value: '' };
}

function open(data?: ConfigCenterItem) {
  visible.value = true;
  keyError.value = '';
  if (data) {
    formData.value = { id: data.id, key: data.key, remark: data.remark ?? '' };
    try {
      const parsed = JSON.parse(data.value) as Record<string, string>;
      const list = Object.entries(parsed).map(([k, v]) => ({
        key: k,
        value: String(v),
      }));
      pairs.value = list.length > 0 ? list : [emptyPair()];
    } catch {
      pairs.value = [emptyPair()];
    }
  } else {
    formData.value = { key: '', remark: '' };
    pairs.value = [emptyPair()];
  }
}

defineExpose({ open });

function addPair() {
  pairs.value.push(emptyPair());
}

function removePair(index: number) {
  if (pairs.value.length === 1) {
    pairs.value = [emptyPair()];
    return;
  }
  pairs.value.splice(index, 1);
}

function openPasteDialog() {
  pasteText.value = '';
  pasteVisible.value = true;
}

/**
 * 解析批量粘贴文本：每行一条，分隔符支持 = , ， Tab → ->
 */
function parsePasteLines(text: string): KeyValuePair[] {
  const result: KeyValuePair[] = [];
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim();
    if (!line) continue;
    const matched = line.match(/^(.+?)(?:=|,|，|\t|→|->)(.+)$/);
    if (!matched) continue;
    const k = matched[1]?.trim() ?? '';
    const v = matched[2]?.trim() ?? '';
    if (k && v) result.push({ key: k, value: v });
  }
  return result;
}

function confirmPaste() {
  const parsed = parsePasteLines(pasteText.value);
  if (parsed.length === 0) {
    ElMessage.warning('未解析到有效的键值对，每行格式：键=值');
    return;
  }
  // 清掉整行为空的占位行
  pairs.value = pairs.value.filter((p) => p.key.trim() || p.value.trim());
  const existing = new Set(pairs.value.map((p) => p.key.trim()));
  let added = 0;
  for (const pair of parsed) {
    if (existing.has(pair.key)) continue; // 跳过与现有重复的键
    pairs.value.push(pair);
    existing.add(pair.key);
    added += 1;
  }
  if (pairs.value.length === 0) pairs.value = [emptyPair()];
  pasteVisible.value = false;
  ElMessage.success(`已导入 ${added} 对（重复键已跳过）`);
}

/**
 * 表单校验，返回错误信息；空串表示通过
 */
function validateForm(): string {
  const key = formData.value.key.trim();
  if (!key) {
    keyError.value = '请输入配置键';
    return keyError.value;
  }
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(key)) {
    keyError.value = '配置键只能是字母、数字、下划线、中划线，且不超过 64 字符';
    return keyError.value;
  }
  keyError.value = '';
  const filled = pairs.value.filter((p) => p.key.trim() || p.value.trim());
  if (filled.length === 0) return '请至少添加一对键值';
  const seen = new Set<string>();
  for (const pair of filled) {
    if (!pair.key.trim()) return '键不能为空';
    if (!pair.value.trim()) return `键「${pair.key.trim()}」的值不能为空`;
    if (seen.has(pair.key.trim())) return `键「${pair.key.trim()}」重复`;
    seen.add(pair.key.trim());
  }
  return '';
}

async function onSubmit() {
  const error = validateForm();
  if (error) {
    ElMessage.warning(error);
    return;
  }
  confirmLoading.value = true;
  const filled = pairs.value.filter((p) => p.key.trim() || p.value.trim());
  const payload = {
    value: buildConfigValue(
      filled.map((p) => ({ key: p.key.trim(), value: p.value.trim() })),
    ),
    remark: formData.value.remark || undefined,
  };
  try {
    if (isEdit.value && formData.value.id) {
      await updateConfigItemApi(formData.value.id, payload);
    } else {
      await createConfigItemApi({ key: formData.value.key.trim(), ...payload });
    }
    visible.value = false;
    emit('success');
  } catch {
    // 请求失败由请求层全局拦截器统一弹错
  } finally {
    confirmLoading.value = false;
  }
}
</script>

<template>
  <ZqDrawer
    v-model="visible"
    :title="drawerTitle"
    :confirm-loading="confirmLoading"
    size="700px"
    @confirm="onSubmit"
  >
    <div class="mx-4 flex flex-col gap-4">
      <div class="flex gap-4">
        <ElFormItem label="配置键" required class="flex-1">
          <ElInput
            v-model="formData.key"
            :disabled="isEdit"
            placeholder="字母/数字/下划线/中划线，≤64字符"
            maxlength="64"
          />
          <div v-if="keyError" class="text-xs text-[#f56c6c]">{{ keyError }}</div>
        </ElFormItem>
        <ElFormItem label="备注" class="flex-1">
          <ElInput
            v-model="formData.remark"
            placeholder="配置用途说明"
            maxlength="200"
          />
        </ElFormItem>
      </div>

      <div>
        <div class="mb-2 flex items-center justify-between">
          <div class="text-sm">
            配置值（键值对）
            <span class="text-xs text-[#909399]">
              至少 1 对；键不能为空、不能重复
            </span>
          </div>
          <div class="flex gap-2">
            <ElButton size="small" plain type="primary" @click="openPasteDialog">
              批量粘贴导入
            </ElButton>
            <ElButton size="small" plain type="primary" @click="addPair">
              ＋添加
            </ElButton>
          </div>
        </div>

        <ElTable :data="pairs" border size="small" max-height="480">
          <ElTableColumn label="键" min-width="40%">
            <template #default="{ $index }">
              <ElInput
                v-model="pairs[$index]!.key"
                placeholder="键"
                maxlength="200"
              />
            </template>
          </ElTableColumn>
          <ElTableColumn width="40" align="center">
            <template #default>→</template>
          </ElTableColumn>
          <ElTableColumn label="值" min-width="45%">
            <template #default="{ $index }">
              <ElInput
                v-model="pairs[$index]!.value"
                placeholder="值"
                maxlength="500"
              />
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="70" align="center">
            <template #default="{ $index }">
              <ElButton
                link
                type="danger"
                size="small"
                @click="removePair($index)"
              >
                删除
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>
    </div>

    <!-- 批量粘贴导入 -->
    <ElDialog
      v-model="pasteVisible"
      title="批量粘贴导入"
      width="560px"
      append-to-body
    >
      <ElAlert type="info" :closable="false" class="mb-2">
        每行一条「键=值」，分隔符支持 = , ， Tab → ->；与现有键重复的行会被跳过。
      </ElAlert>
      <ElInput
        v-model="pasteText"
        type="textarea"
        :rows="10"
        placeholder="充许=允许&#10;聊关=聊天&#10;己经=已经"
      />
      <template #footer>
        <ElButton @click="pasteVisible = false">取消</ElButton>
        <ElButton type="primary" @click="confirmPaste">导入</ElButton>
      </template>
    </ElDialog>
  </ZqDrawer>
</template>
