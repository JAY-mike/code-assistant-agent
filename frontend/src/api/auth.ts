import api from './client'

export interface LoginReq {
  username: string
  password: string
}

export interface RegisterReq {
  username: string
  password: string
  email?: string
}

export interface TokenRes {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserInfo {
  id: number
  username: string
  email: string
  created_at: string
}

export const authApi = {
  login(data: LoginReq) {
    return api.post<TokenRes>('/auth/login', data)
  },
  register(data: RegisterReq) {
    return api.post<TokenRes>('/auth/register', data)
  },
  refresh(refreshToken: string) {
    return api.post<TokenRes>('/auth/refresh', { refresh_token: refreshToken })
  },
  logout() {
    return api.post('/auth/logout')
  },
  me() {
    return api.get<UserInfo>('/auth/me')
  },
}
