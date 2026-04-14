<script lang="ts" setup>
import { onMounted, ref, watch, nextTick } from 'vue';
import * as monaco from 'monaco-editor';

import {
  ElButton,
  ElDialog,
  ElMessage,
} from 'element-plus';

import {
  createAISkillApi,
  getAISkillDetailApi,
  updateAISkillApi,
} from '#/api/core/ai-assistant';

const props = defineProps<{
  visible: boolean;
  skillId: string | null;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'success'): void;
}>();

defineOptions({ name: 'SkillEditDialog' });

// 数据
const loading = ref(false);
const submitLoading = ref(false);

// 表单数据
const formData = ref({
  id: '',
  content: '',
});

// Monaco Editor 实例
let editorInstance: monaco.editor.IStandaloneCodeEditor | null = null;
const editorContainer = ref<HTMLElement | null>(null);

// 是否为编辑模式
const isEdit = ref(false);

// 监听 visible 变化
watch(
  () => props.visible,
  async (newVisible) => {
    if (newVisible) {
      isEdit.value = !!props.skillId;
      if (isEdit.value) {
        // 编辑模式：加载 Skill 详情
        await loadSkillDetail();
      } else {
        // 新增模式：生成随机 ID，清空内容
        formData.value = {
          id: generateUUID(),
          content: '',
        };
      }
      // 等待 DOM 更新后初始化编辑器
      await nextTick();
      initEditor();
    } else {
      // 关闭时销毁编辑器
      destroyEditor();
    }
  },
);

// 生成 UUID
function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// 加载 Skill 详情
async function loadSkillDetail() {
  if (!props.skillId) return;
  loading.value = true;
  try {
    const res = await getAISkillDetailApi(props.skillId);
    formData.value = {
      id: res.id,
      content: res.content,
    };
  } catch (error) {
    console.error('加载 Skill 详情失败:', error);
    ElMessage.error('加载 Skill 详情失败');
  } finally {
    loading.value = false;
  }
}

// 初始化 Monaco Editor
function initEditor() {
  if (!editorContainer.value) return;

  // 如果已存在实例，先销毁
  destroyEditor();

  editorInstance = monaco.editor.create(editorContainer.value, {
    value: formData.value.content,
    language: 'markdown',
    theme: 'vs-dark',
    lineNumbers: 'on',
    minimap: { enabled: false },
    fontSize: 14,
    scrollBeyondLastLine: false,
    automaticLayout: true,
    wordWrap: 'on',
    wrappingStrategy: 'advanced',
    tabSize: 2,
  });

  // 监听内容变化
  editorInstance.onDidChangeModelContent(() => {
    formData.value.content = editorInstance?.getValue() || '';
  });
}

// 销毁编辑器
function destroyEditor() {
  if (editorInstance) {
    editorInstance.dispose();
    editorInstance = null;
  }
}

// 提交表单
async function handleSubmit() {
  // 校验内容
  if (!formData.value.content) {
    ElMessage.warning('请输入 Skill 内容');
    return;
  }

  submitLoading.value = true;
  try {
    if (isEdit.value) {
      // 编辑模式
      await updateAISkillApi(props.skillId!, {
        content: formData.value.content,
      });
      ElMessage.success('更新成功');
    } else {
      // 新增模式：使用自动生成的 UUID 作为 Skill ID
      await createAISkillApi({
        id: formData.value.id,
        content: formData.value.content,
      });
      ElMessage.success('创建成功');
    }
    emit('success');
  } catch (error: any) {
    const msg = error?.response?.data?.detail || '操作失败';
    ElMessage.error(msg);
  } finally {
    submitLoading.value = false;
  }
}

// 关闭弹窗
function handleClose() {
  emit('update:visible', false);
}

// 初始化
onMounted(() => {
  // 编辑器会在 visible 变化时初始化
});
</script>

<template>
  <ElDialog
    :model-value="props.visible"
    width="650px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:visible', $event)"
    @close="handleClose"
  >
    <!-- 自定义标题栏 -->
    <template #header>
      <div class="dialog-header">
        <span class="dialog-title">
          {{ isEdit ? `编辑 Skill: ${formData.id}` : '新增 Skill' }}
        </span>
      </div>
    </template>

    <div v-loading="loading" class="editor-wrapper">
      <div ref="editorContainer" class="monaco-editor-container"></div>
    </div>

    <template #footer>
      <ElButton @click="handleClose">取消</ElButton>
      <ElButton type="primary" :loading="submitLoading" @click="handleSubmit">
        保存
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.dialog-header {
  padding: 12px 16px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dialog-title {
  font-weight: 600;
  font-size: 14px;
}

.editor-wrapper {
  width: 100%;
  overflow: hidden;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  margin: 12px 0;
}

.monaco-editor-container {
  width: 100%;
  height: 350px;
}
</style>