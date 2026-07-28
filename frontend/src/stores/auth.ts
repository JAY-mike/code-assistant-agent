import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi, type UserInfo } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserInfo | null>(null)
  const isLoggedIn = ref(!!localStorage.getItem('access_token'))

  async function login(username: string, password: string) {
    const { data } = await authApi.login({ username, password })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    isLoggedIn.value = true
    return data
  }

  async function register(username: string, password: string, email?: string) {
    const { data } = await authApi.register({ username, password, email })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    isLoggedIn.value = true
    return data
  }

  async function fetchUser() {
    try {
      const { data } = await authApi.me()
      user.value = data
    } catch {
      user.value = null
    }
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch {
      // ignore
    }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    user.value = null
    isLoggedIn.value = false
  }

  return { user, isLoggedIn, login, register, fetchUser, logout }
})
