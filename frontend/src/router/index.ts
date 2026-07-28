import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/LoginView.vue'),
    },
    {
      path: '/',
      component: () => import('@/components/AppLayout.vue'),
      redirect: '/chat',
      children: [
        {
          path: 'chat',
          name: 'Chat',
          component: () => import('@/views/ChatView.vue'),
        },
        {
          path: 'chat/:sessionId',
          name: 'ChatSession',
          component: () => import('@/views/ChatView.vue'),
        },
        {
          path: 'rag',
          name: 'RagDashboard',
          component: () => import('@/views/RagDashboard.vue'),
        },
        {
          path: 'index',
          name: 'IndexManage',
          component: () => import('@/views/IndexManage.vue'),
        },
        {
          path: 'upload',
          name: 'Upload',
          component: () => import('@/views/UploadView.vue'),
        },
        {
          path: 'feedback',
          name: 'Feedback',
          component: () => import('@/views/FeedbackView.vue'),
        },
      ],
    },
  ],
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' })
  } else {
    next()
  }
})

export default router
