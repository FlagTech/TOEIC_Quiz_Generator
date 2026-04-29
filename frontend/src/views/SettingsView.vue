<script setup lang="ts">
import { ref } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'

const settingsStore = useSettingsStore()
const toast = useToast()

// Gemini 模型選擇（固定使用 Gemini）
const modelGroups = [
  {
    label: 'Gemini 3 系列（Preview）',
    models: [
      { id: 'gemini-3.1-pro-preview', name: 'Gemini 3.1 Pro Preview' },
      { id: 'gemini-3-flash-preview', name: 'Gemini 3 Flash Preview' },
      { id: 'gemini-3.1-flash-lite-preview', name: 'Gemini 3.1 Flash-Lite Preview' },
    ]
  },
  {
    label: 'Gemini 2.5 系列（穩定）',
    models: [
      { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro' },
      { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash（推薦）' },
      { id: 'gemini-2.5-flash-lite', name: 'Gemini 2.5 Flash-Lite' },
    ]
  },
]

const model = ref<string>(settingsStore.settings.defaultModel || 'gemini-2.5-flash')
const geminiKey = ref(settingsStore.settings.apiKeys.gemini || '')
const showKey = ref(false)

function onKeyChange() {
  settingsStore.setApiKey(geminiKey.value)
}

function save() {
  settingsStore.updateSettings({
    defaultProvider: 'gemini',
    defaultModel: model.value,
    apiKeys: {
      gemini: geminiKey.value
    }
  })
  toast.success('設定已儲存')
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 md:px-6 py-8 space-y-8">
    <h1 class="text-4xl md:text-5xl font-black bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 bg-clip-text text-transparent text-center">設定</h1>

    <!-- Google Gemini API 設定 -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 space-y-5">
      <div class="border-b border-gray-200 dark:border-gray-700 pb-3 mb-4">
        <h2 class="text-2xl font-bold !text-gray-900 dark:!text-white flex items-center gap-2">
          🤖 Google Gemini API 設定
        </h2>
        <p class="text-sm !text-gray-600 dark:!text-gray-400 mt-2">
          本系統使用 Google Gemini API 提供所有 AI 功能，包括 TOEIC 測驗生成（Part 1-7）、圖片生成、語音合成等。
        </p>
      </div>

      <!-- API Key 輸入 -->
      <div class="space-y-3">
        <label class="block text-sm font-medium !text-gray-700 dark:!text-gray-300">
          Google Gemini API Key <span class="text-red-500">*</span>
        </label>
        <div class="flex gap-2">
          <input
            :type="showKey ? 'text' : 'password'"
            v-model="geminiKey"
            placeholder="AIza..."
            class="flex-1 px-4 py-2 rounded-xl bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 font-mono text-sm !text-gray-900 dark:!text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
            @change="onKeyChange"
          />
          <button
            class="px-4 py-2 rounded-xl bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 !text-gray-900 dark:!text-white text-xs whitespace-nowrap transition-all"
            @click="showKey = !showKey"
          >
            {{ showKey ? '隱藏' : '顯示' }}
          </button>
        </div>
        <p class="text-xs !text-gray-500 dark:!text-gray-400">
          取得 API Key：前往 <a href="https://aistudio.google.com/app/apikey" target="_blank" class="!text-purple-600 dark:!text-purple-400 underline hover:!text-purple-700">Google AI Studio</a> 建立新的 API Key
        </p>
      </div>

      <!-- 模型選擇 -->
      <div>
        <label class="block text-sm font-medium !text-gray-700 dark:!text-gray-300 mb-2">Gemini 模型</label>
        <select
          v-model="model"
          class="w-full px-3 py-2 rounded-xl bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 !text-gray-900 dark:!text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
        >
          <optgroup v-for="group in modelGroups" :key="group.label" :label="group.label">
            <option v-for="m in group.models" :key="m.id" :value="m.id">{{ m.name }}</option>
          </optgroup>
        </select>
        <p class="text-xs !text-gray-500 dark:!text-gray-400 mt-2">
          建議使用 <strong>gemini-2.5-flash</strong>（速度快、成本低）或 <strong>gemini-3-flash-preview</strong>（最新一代）
        </p>
      </div>

      <!-- 功能說明 -->
      <div class="bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 p-4 rounded-xl border border-purple-200 dark:border-purple-800">
        <h3 class="font-bold !text-purple-800 dark:!text-purple-300 mb-2">✨ 支援功能</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm !text-purple-700 dark:!text-purple-400">
          <div>
            <div class="font-semibold mb-1">📝 文字生成</div>
            <ul class="text-xs space-y-1 list-disc list-inside">
              <li>TOEIC 閱讀測驗（Part 5-7）</li>
              <li>TOEIC 聽力題目（Part 2-4）</li>
              <li>題目詳解與解析</li>
            </ul>
          </div>
          <div>
            <div class="font-semibold mb-1">🎨 多媒體生成</div>
            <ul class="text-xs space-y-1 list-disc list-inside">
              <li>圖像生成（Part 1）</li>
              <li>TTS 語音合成（Part 1-4）</li>
            </ul>
          </div>
        </div>
      </div>

      <div class="pt-2">
        <button
          class="px-6 py-3 rounded-2xl !text-white bg-gradient-to-r from-purple-500 via-pink-500 to-indigo-500 gradient-shift hover:shadow-lg transition-all"
          @click="save"
        >
          💾 儲存設定
        </button>
      </div>
    </div>

  </div>
</template>
