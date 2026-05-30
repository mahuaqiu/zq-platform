<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';

import { computed } from 'vue';

import { AuthenticationLogin, z } from '@vben/common-ui';
import { $t } from '@vben/locales';

import { useAuthStore } from '#/store';

defineOptions({ name: 'Login' });

const authStore = useAuthStore();

const formSchema = computed((): VbenFormSchema[] => {
  return [
    {
      component: 'VbenInput',
      componentProps: {
        placeholder: $t('authentication.usernameTip'),
      },
      defaultValue: '',
      fieldName: 'username',
      label: $t('authentication.username'),
      rules: z.string().min(1, { message: $t('authentication.usernameTip') }),
    },
    {
      component: 'VbenInputPassword',
      componentProps: {
        placeholder: $t('authentication.password'),
      },
      defaultValue: '',
      fieldName: 'password',
      label: $t('authentication.password'),
      rules: z.string().min(1, { message: $t('authentication.passwordTip') }),
    },
  ];
});

// 游客登录
function handleGuestLogin() {
  authStore.authLogin({ username: 'guest', password: '123456' });
}
</script>

<template>
  <AuthenticationLogin
    :form-schema="formSchema"
    :loading="authStore.loginLoading"
    :show-third-party-login="false"
    @submit="authStore.authLogin"
  >
    <template #title>
      <div class="mb-7 flex items-center gap-3">
        <h2 class="text-foreground text-3xl font-bold leading-9 tracking-tight lg:text-4xl">
          {{ $t('authentication.welcomeBack') }} 👋🏻
        </h2>
        <button
          type="button"
          class="cursor-pointer rounded-md bg-primary px-3 py-1 text-xs font-medium text-white hover:bg-primary/90 transition-colors"
          :disabled="authStore.loginLoading"
          @click="handleGuestLogin"
        >
          游客
        </button>
      </div>
    </template>
  </AuthenticationLogin>
</template>