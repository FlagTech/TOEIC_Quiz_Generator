/**
 * 設定 Store
 * 管理應用設定（主題、API 金鑰等）
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AppSettings } from '@/types'

const STORAGE_NAMESPACE = 'toeic_quiz_generator:v1'
const SAFE_SETTINGS_STORAGE = `${STORAGE_NAMESPACE}:settings`
const GEMINI_KEY_STORAGE = `${STORAGE_NAMESPACE}:gemini_api_key`
const LEGACY_GEMINI_KEY_STORAGE = 'gemini_api_key'
const LEGACY_PINIA_SETTINGS_STORAGE = 'settings'

type SafeSettings = Omit<AppSettings, 'apiKeys'>

const defaultSafeSettings: SafeSettings = {
  theme: 'light',
  defaultProvider: 'gemini',
  defaultModel: 'gemini-2.5-flash',
  speechRate: 1.0,
  autoPlayAudio: false
}

function pickSafeSettings(value: Partial<AppSettings> | Partial<SafeSettings> | null): SafeSettings {
  return {
    ...defaultSafeSettings,
    theme: value?.theme ?? defaultSafeSettings.theme,
    defaultProvider: 'gemini',
    defaultModel: value?.defaultModel ?? defaultSafeSettings.defaultModel,
    speechRate: value?.speechRate ?? defaultSafeSettings.speechRate,
    autoPlayAudio: value?.autoPlayAudio ?? defaultSafeSettings.autoPlayAudio
  }
}

function loadSafeSettings(): SafeSettings {
  let safeSettings = defaultSafeSettings

  const current = localStorage.getItem(SAFE_SETTINGS_STORAGE)
  if (current) {
    try {
      safeSettings = pickSafeSettings(JSON.parse(current))
    } catch {
      safeSettings = defaultSafeSettings
    }
  }

  const legacy = localStorage.getItem(LEGACY_PINIA_SETTINGS_STORAGE)
  if (!current && legacy) {
    try {
      const parsed = JSON.parse(legacy)
      safeSettings = pickSafeSettings(parsed?.settings ?? parsed)
    } catch {
      safeSettings = defaultSafeSettings
    }
  }

  // Remove old Pinia persisted settings because they may contain apiKeys.
  localStorage.removeItem(LEGACY_PINIA_SETTINGS_STORAGE)

  return safeSettings
}

function loadGeminiKey(): string {
  const savedKey = localStorage.getItem(GEMINI_KEY_STORAGE)
  const legacyKey = localStorage.getItem(LEGACY_GEMINI_KEY_STORAGE)
  const key = savedKey ?? legacyKey ?? ''

  if (!savedKey && legacyKey) {
    localStorage.setItem(GEMINI_KEY_STORAGE, key)
  }
  localStorage.removeItem(LEGACY_GEMINI_KEY_STORAGE)

  return key
}

function saveSafeSettings(settings: AppSettings) {
  localStorage.setItem(
    SAFE_SETTINGS_STORAGE,
    JSON.stringify(pickSafeSettings(settings))
  )
}

export const useSettingsStore = defineStore(
  'settings',
  () => {
    const safeSettings = loadSafeSettings()

    // API key is stored only in this user's browser localStorage, never in source files.
    const settings = ref<AppSettings>({
      ...safeSettings,
      theme: 'light',
      apiKeys: { gemini: loadGeminiKey() }
    })

    // 強制淺色模式，清除任何殘留的 dark class
    document.documentElement.classList.remove('dark')
    document.documentElement.setAttribute('data-theme', 'light')

    // 固定淺色模式：移除 dark class，忽略 theme 參數
    function setTheme(_theme: 'light' | 'dark' | 'auto') {
      settings.value.theme = 'light'
      document.documentElement.classList.remove('dark')
      document.documentElement.setAttribute('data-theme', 'light')
    }

    // 設置 API 金鑰：只儲存在使用者自己的瀏覽器 localStorage，不會進入 Git。
    function setApiKey(key: string) {
      settings.value.apiKeys.gemini = key
      localStorage.setItem(GEMINI_KEY_STORAGE, key)
      localStorage.removeItem(LEGACY_GEMINI_KEY_STORAGE)
      localStorage.removeItem(LEGACY_PINIA_SETTINGS_STORAGE)
    }

    function setDefaultModel(model: string) {
      settings.value.defaultModel = model
      saveSafeSettings(settings.value)
    }

    function updateSettings(partial: Partial<AppSettings>) {
      const updated: AppSettings = {
        ...settings.value,
        ...partial,
        defaultProvider: 'gemini' as const
      }
      settings.value = updated
      if (partial.apiKeys?.gemini !== undefined) {
        localStorage.setItem(GEMINI_KEY_STORAGE, partial.apiKeys.gemini)
        localStorage.removeItem(LEGACY_GEMINI_KEY_STORAGE)
        localStorage.removeItem(LEGACY_PINIA_SETTINGS_STORAGE)
      }
      if (partial.theme) setTheme(partial.theme)
      saveSafeSettings(settings.value)
    }

    return {
      settings,
      setTheme,
      setApiKey,
      setDefaultModel,
      updateSettings
    }
  }
)
