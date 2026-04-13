<script lang="ts" setup>
import { onMounted, ref, watch, nextTick } from 'vue';
import * as monaco from 'monaco-editor';

import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
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

// Skill ID 校验正则
const skillIdRegex = /^[a-zA-Z0-9\-]+$/;

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
        // 新增模式：清空表单
        formData.value = {
          id: '',
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
  // 校验
  if (!isEdit.value) {
    // 新增模式：校验 Skill ID
    if (!formData.value.id) {
      ElMessage.warning('请输入 Skill ID');
      return;
    }
    if (!skillIdRegex.test(formData.value.id)) {
      ElMessage.warning('Skill ID 只能包含字母、数字和短横线');
      return;
    }
  }

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
      // 新增模式
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
    :title="isEdit ? '编辑 Skill' : '新增 Skill'"
    width="800px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:visible', $event)"
    @close="handleClose"
  >
    <ElForm label-width="100px" v-loading="loading">
      <!-- Skill ID（新增时必填，编辑时只显示） -->
      <ElFormItem label="Skill ID" :required="!isEdit">
        <ElInput
          v-if="!isEdit"
          v-model="formData.id"
          placeholder="请输入 Skill ID（只能包含字母、数字和短横线）"
        />
        <div v-else class="skill-id-display">
          <code>{{ formData.id }}</code>
        </div>
      </ElFormItem>

      <!-- Skill 内容 -->
      <ElFormItem label="Skill 内容" required>
        <div class="editor-wrapper">
          <div ref="editorContainer" class="monaco-editor-container"></div>
        </div>
        <div class="editor-tip">
          提示：在内容开头使用 YAML frontmatter 定义 name 和 description，例如：<br />
          <code>---<br />name: 技能名称<br />description: 技能描述<br />---</code>
        </div>
      </ElFormItem>
    </ElForm>

    <template #footer>
      <ElButton @click="handleClose">取消</ElButton>
      <ElButton type="primary" :loading="submitLoading" @click="handleSubmit">
        确定
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.skill-id-display {
  padding: 6px 12px;
  background: #f5f5f5;
  border-radius: 4px;
}

.skill-id-display code {
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 14px;
  color: #1890ff;
}

.editor-wrapper {
  width: 100%;
  overflow: hidden;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
}

.monaco-editor-container {
  width: 100%;
  height: 400px;
}

.editor-tip {
  margin-top: 8px;
  padding: 8px 12px;
  font-size: 12px;
  line-height: 1.6;
  color: #666;
  background: #f5f5f5;
  border-radius: 4px;
}

.editor-tip code {
  display: block;
  padding: 4px 8px;
  margin-top: 4px;
  font-family: Consolas, Monaco, 'Courier New', monospace;
  white-space: pre;
  background: #e8e8e8;
  border-radius: 4px;
}
</style>