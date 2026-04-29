/**
 * 設定 Store
 * 管理應用設定（主題、API 金鑰等）
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useDark, useToggle } from '@vueuse/core'
import type { AppSettings } from '@/types'

const GEMINI_KEY_STORAGE = 'gemini_api_key'

export const useSettingsStore = defineStore(
  'settings',
  () => {
    // 使用 VueUse 的深色模式
    const isDark = useDark()
    const toggleDark = useToggle(isDark)

    // 設定（簡化為只使用 Gemini）
    // API key 從 localStorage 直接讀取，避免依賴 pinia persist 的 nested object 序列化
    const settings = ref<AppSettings>({
      theme: 'auto',
      apiKeys: { gemini: localStorage.getItem(GEMINI_KEY_STORAGE) || '' },
      defaultProvider: 'gemini',  // 固定使用 Gemini
      defaultModel: 'gemini-2.5-flash',
      speechRate: 1.0,
      autoPlayAudio: false
    })

    // 設置主題
    function setTheme(theme: 'light' | 'dark' | 'auto') {
      settings.value.theme = theme
      if (theme === 'dark') {
        document.documentElement.classList.add('dark')
        document.documentElement.setAttribute('data-theme', 'dark')
        isDark.value = true
      } else if (theme === 'light') {
        document.documentElement.classList.remove('dark')
        document.documentElement.setAttribute('data-theme', 'light')
        isDark.value = false
      } else {
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
        if (prefersDark) {
          document.documentElement.classList.add('dark')
          document.documentElement.setAttribute('data-theme', 'dark')
          isDark.value = true
        } else {
          document.documentElement.classList.remove('dark')
          document.documentElement.setAttribute('data-theme', 'light')
          isDark.value = false
        }
      }
    }

    // 設置 API 金鑰（直接寫入 localStorage 確保持久化）
    function setApiKey(key: string) {
      settings.value.apiKeys.gemini = key
      localStorage.setItem(GEMINI_KEY_STORAGE, key)
    }

    function setDefaultModel(model: string) {
      settings.value.defaultModel = model
    }

    function updateSettings(partial: Partial<AppSettings>) {
      const updated: AppSettings = {
        ...settings.value,
        ...partial,
        defaultProvider: 'gemini' as const
      }
      settings.value = updated
      // API key 額外寫入 localStorage，確保跨次開啟持久化
      if (partial.apiKeys?.gemini !== undefined) {
        localStorage.setItem(GEMINI_KEY_STORAGE, partial.apiKeys.gemini)
      }
      if (partial.theme) setTheme(partial.theme)
    }

    return {
      isDark,
      toggleDark,
      settings,
      setTheme,
      setApiKey,
      setDefaultModel,
      updateSettings
    }
  },
  {
    persist: {
      pick: ['settings']
    }
  }
)
