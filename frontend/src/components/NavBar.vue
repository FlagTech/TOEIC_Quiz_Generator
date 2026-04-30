<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute, RouterLink } from 'vue-router'

const router = useRouter()
const route = useRoute()

function navigateTo(path: string) {
  if (route.path === path) {
    router.push({ path, query: { reset: Date.now().toString() } })
  } else {
    router.push(path)
  }
}

// 完整測驗背景任務提醒
const hasOngoingFullTest = ref(false)
const CURRENT_JOB_KEY = 'toeic_test_current_job_v2'
const JOB_EVENT_NAME = 'full-test-job-updated'

function checkOngoingFullTest() {
  try {
    const raw = localStorage.getItem(CURRENT_JOB_KEY)
    if (!raw) {
      hasOngoingFullTest.value = false
      return
    }
    const saved = JSON.parse(raw) as { jobId?: string }
    hasOngoingFullTest.value = !!saved?.jobId
  } catch {
    hasOngoingFullTest.value = false
    localStorage.removeItem(CURRENT_JOB_KEY)
  }
}

onMounted(() => {
  window.addEventListener(JOB_EVENT_NAME, checkOngoingFullTest)
  checkOngoingFullTest()
})
onBeforeUnmount(() => {
  window.removeEventListener(JOB_EVENT_NAME, checkOngoingFullTest)
})
</script>

<template>
  <nav class="fixed top-0 left-0 right-0 z-50">
    <div class="backdrop-blur-xl bg-white/70 dark:bg-gray-900/80 border-b border-white/30 dark:border-white/10">
      <div class="max-w-7xl mx-auto px-4 md:px-6 py-3">
        <div class="flex items-center gap-4">
          <!-- Brand -->
          <RouterLink to="/" class="flex items-center gap-2 group">
            <span
              class="text-lg md:text-xl font-extrabold bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 bg-clip-text text-transparent"
            >
              TOEIC 測驗生成
            </span>
          </RouterLink>

          <!-- 題型測驗 -->
          <button
            @click="navigateTo('/')"
            class="px-3 py-2 rounded-xl font-semibold text-gray-700 dark:text-gray-200 hover:bg-white/60 dark:hover:bg-white/10 transition inline-flex items-center gap-2"
          >
            <span class="text-xl">🧩</span>
            <span class="hidden md:inline">題型測驗</span>
          </button>

          <!-- TOEIC 模擬測驗 -->
          <button
            @click="navigateTo('/full-test')"
            class="px-3 py-2 rounded-xl font-semibold text-gray-700 dark:text-gray-200 hover:bg-white/60 dark:hover:bg-white/10 transition inline-flex items-center gap-2"
          >
            <span class="text-xl">📄</span>
            <span class="hidden md:inline">模擬測驗</span>
          </button>

          <!-- Spacer -->
          <div class="flex-1"></div>

          <!-- 返回模擬測驗 (若有背景任務進行中) -->
          <RouterLink
            v-if="hasOngoingFullTest && router.currentRoute.value.path !== '/full-test'"
            to="/full-test"
            class="inline-flex items-center gap-2 px-2 md:px-3 py-2 rounded-xl bg-blue-600 text-white text-xs md:text-sm font-semibold shadow-sm hover:bg-blue-700 transition"
          >
            <span>⏳</span>
            <span>返回模擬測驗</span>
          </RouterLink>

          <!-- Settings -->
          <RouterLink
            to="/settings"
            class="px-3 py-2 rounded-xl hover:bg-white/60 dark:hover:bg-white/10 transition inline-flex items-center gap-2"
            aria-label="API 設定"
          >
            <span class="text-xl">⚙️</span>
            <span class="text-sm font-semibold">設定</span>
          </RouterLink>
        </div>
      </div>
    </div>
  </nav>
</template>

<style scoped>
</style>
