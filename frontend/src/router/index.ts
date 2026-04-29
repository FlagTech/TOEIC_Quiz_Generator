import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // 首頁 - 題型測驗選擇
    {
      path: '/',
      name: 'quiz',
      component: () => import('../views/QuizView.vue'),
      meta: { title: '題型測驗 - TOEIC 測驗生成' }
    },
    // TOEIC 完整模擬測驗
    {
      path: '/full-test',
      name: 'full-test',
      component: () => import('../views/FullTestView.vue'),
      meta: { title: 'TOEIC 模擬測驗 - TOEIC 測驗生成' }
    },
    // 設定頁面（API Keys 等）
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue'),
      meta: { title: '設定 - TOEIC 測驗生成' }
    },
  ],
})

// 設定頁面標題
router.beforeEach((to, _from, next) => {
  document.title = (to.meta.title as string) || 'TOEIC 測驗生成'
  next()
})

export default router
