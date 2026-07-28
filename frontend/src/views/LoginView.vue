<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <div class="login-logo">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="16 3 21 3 21 8" />
            <line x1="4" y1="20" x2="21" y2="3" />
            <polyline points="21 16 21 21 16 21" />
            <line x1="15" y1="15" x2="21" y2="21" />
            <line x1="4" y1="4" x2="9" y2="9" />
          </svg>
        </div>
        <h1 class="login-title">Code Assistant Agent</h1>
        <p class="login-desc">AI 驱动的代码分析助手</p>
      </div>

      <form @submit.prevent="handleSubmit" class="login-form">
        <div v-if="errorMsg" class="form-error">{{ errorMsg }}</div>

        <div class="form-group">
          <label class="form-label">用户名</label>
          <input v-model="form.username" class="input" placeholder="请输入用户名" required autocomplete="username" />
        </div>

        <div class="form-group">
          <label class="form-label">密码</label>
          <input v-model="form.password" class="input" type="password" placeholder="请输入密码" required autocomplete="current-password" />
        </div>

        <div class="form-group" v-if="isRegister">
          <label class="form-label">邮箱（可选）</label>
          <input v-model="form.email" class="input" type="email" placeholder="用于找回密码" />
        </div>

        <button type="submit" class="btn btn-primary btn-submit" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          {{ isRegister ? '注册并登录' : '登录' }}
        </button>
      </form>

      <div class="login-footer">
        <button class="btn btn-ghost btn-sm" @click="toggleMode">
          {{ isRegister ? '已有账号？去登录' : '没有账号？去注册' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const isRegister = ref(false)
const loading = ref(false)
const errorMsg = ref('')

const form = reactive({
  username: '',
  password: '',
  email: '',
})

async function handleSubmit() {
  loading.value = true
  errorMsg.value = ''
  try {
    if (isRegister.value) {
      await auth.register(form.username, form.password, form.email || undefined)
    } else {
      await auth.login(form.username, form.password)
    }
    router.push('/chat')
  } catch (err: any) {
    errorMsg.value = err.response?.data?.detail || '操作失败，请重试'
  } finally {
    loading.value = false
  }
}

function toggleMode() {
  isRegister.value = !isRegister.value
  errorMsg.value = ''
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 40px 32px;
}

.login-header { text-align: center; margin-bottom: 32px; }
.login-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: var(--primary-subtle);
  color: var(--primary-hover);
  margin-bottom: 16px;
}
.login-title { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.03em; }
.login-desc { margin-top: 6px; font-size: 0.9rem; color: var(--text-secondary); }

.login-form { display: flex; flex-direction: column; gap: 16px; }
.form-error {
  padding: 10px 14px;
  background: var(--error-subtle);
  border: 1px solid rgba(239,68,68,0.2);
  border-radius: var(--radius-sm);
  color: var(--error);
  font-size: 0.85rem;
}
.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-label { font-size: 0.85rem; font-weight: 500; color: var(--text-secondary); }
.btn-submit { width: 100%; padding: 12px; margin-top: 8px; }

.login-footer { text-align: center; margin-top: 20px; }

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
