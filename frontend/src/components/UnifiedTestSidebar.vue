<script setup lang="ts">
import { computed, ref } from 'vue'
import type { QuizFolderResponse } from '@/types'
import type { SidebarFolderId, UnifiedSidebarLog } from '@/utils/testHistory'

const props = defineProps<{
  open: boolean
  logs: UnifiedSidebarLog[]
  visibleLogs: UnifiedSidebarLog[]
  folders: QuizFolderResponse[]
  selectedFolderId: SidebarFolderId
  activeLogKey?: string | null
  exporting?: boolean
  title?: string
  emptyText?: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'select-folder': [folderId: SidebarFolderId]
  'select-log': [log: UnifiedSidebarLog]
  'request-create-folder': []
  'request-edit-folder': [folder: QuizFolderResponse]
  'request-delete-folder': [folder: QuizFolderResponse]
  'request-move-log': [log: UnifiedSidebarLog]
  'request-delete-log': [log: UnifiedSidebarLog]
  'export-pdf': [log: UnifiedSidebarLog]
  'move-log-to-folder': [payload: { log: UnifiedSidebarLog; folderId: string | null }]
  'reorder-logs': [payload: { draggedLog: UnifiedSidebarLog; targetLog: UnifiedSidebarLog }]
}>()

const draggedLogKey = ref<string | null>(null)

const sidebarTitle = computed(() => props.title || '測驗記錄')
const sidebarEmptyText = computed(() => props.emptyText || '尚無測驗記錄')

function closeSidebar() {
  emit('update:open', false)
}

function getFolderLogCount(folderId: string) {
  return props.logs.filter(log => log.folderId === folderId).length
}

function getUncategorizedCount() {
  return props.logs.filter(log => !log.folderId).length
}

function onDragStart(log: UnifiedSidebarLog) {
  draggedLogKey.value = log.key
}

function onDragEnd() {
  draggedLogKey.value = null
}

function onDragOver(event: DragEvent) {
  event.preventDefault()
}

function onDrop(targetLog: UnifiedSidebarLog) {
  if (!draggedLogKey.value || draggedLogKey.value === targetLog.key) {
    draggedLogKey.value = null
    return
  }

  const draggedLog = props.logs.find(log => log.key === draggedLogKey.value)
  if (!draggedLog) {
    draggedLogKey.value = null
    return
  }

  emit('reorder-logs', { draggedLog, targetLog })
  draggedLogKey.value = null
}

function onDropToFolder(folderId: string | null) {
  if (!draggedLogKey.value) return

  const draggedLog = props.logs.find(log => log.key === draggedLogKey.value)
  if (!draggedLog) {
    draggedLogKey.value = null
    return
  }

  emit('move-log-to-folder', { log: draggedLog, folderId })
  draggedLogKey.value = null
}
</script>

<template>
  <button
    v-if="!open"
    @click="emit('update:open', true)"
    class="fixed top-20 left-6 z-40 p-4 bg-white/70 dark:bg-gray-800/70 backdrop-blur-xl border border-white/20 rounded-2xl shadow-lg hover:scale-110 transition-all duration-300"
    title="開啟測驗記錄"
  >
    <span class="text-2xl">📋</span>
  </button>

  <transition
    enter-active-class="transition-opacity duration-300"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-300"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="open"
      @click="closeSidebar"
      class="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
    ></div>
  </transition>

  <transition
    enter-active-class="transition-transform duration-300"
    enter-from-class="-translate-x-full"
    enter-to-class="translate-x-0"
    leave-active-class="transition-transform duration-300"
    leave-from-class="translate-x-0"
    leave-to-class="-translate-x-full"
  >
    <div
      v-if="open"
      class="fixed left-0 top-0 h-full w-96 bg-white/90 dark:bg-gray-900/90 backdrop-blur-2xl border-r border-white/20 shadow-2xl z-50 overflow-hidden flex flex-col"
    >
      <div class="p-4 border-b border-white/20">
        <div class="flex items-center justify-between mb-1">
          <h2 class="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            {{ sidebarTitle }}
          </h2>
          <div class="flex items-center gap-2">
            <button
              @click="emit('request-create-folder')"
              class="text-xs px-2 py-1 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-all"
            >
              + 新增
            </button>
            <button
              @click="closeSidebar"
              class="p-2 hover:bg-gray-200/50 dark:hover:bg-white/10 rounded-xl transition-all"
            >
              <span class="text-lg text-gray-700 dark:text-gray-300">✕</span>
            </button>
          </div>
        </div>
        <p class="text-xs text-gray-500 dark:text-gray-400">共 {{ logs.length }} 筆記錄</p>
        <div class="mt-3">
          <slot name="header-controls" />
        </div>
      </div>

      <div class="p-3 border-b border-white/20 space-y-1">
        <div class="flex items-center justify-between mb-1">
          <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">資料夾</span>
        </div>

        <button
          @click="emit('select-folder', 'all')"
          @dragover="onDragOver"
          @drop="onDropToFolder(null)"
          :class="['w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all', selectedFolderId === 'all' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-semibold' : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300']"
        >
          <span>📋 全部</span>
          <span class="px-2 py-0.5 rounded-full bg-gray-200 dark:bg-gray-700 text-xs">{{ logs.length }}</span>
        </button>

        <button
          @click="emit('select-folder', 'uncategorized')"
          @dragover="onDragOver"
          @drop="onDropToFolder(null)"
          :class="['w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all', selectedFolderId === 'uncategorized' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-semibold' : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300']"
        >
          <span>📁 未分類</span>
          <span class="px-2 py-0.5 rounded-full bg-gray-200 dark:bg-gray-700 text-xs">{{ getUncategorizedCount() }}</span>
        </button>

        <div
          v-for="folder in folders"
          :key="folder.id"
          @dragover="onDragOver"
          @drop="onDropToFolder(folder.id)"
          :class="['w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all group/folder', selectedFolderId === folder.id ? 'bg-blue-100 dark:bg-blue-900/30' : 'hover:bg-gray-100 dark:hover:bg-gray-800']"
        >
          <button @click="emit('select-folder', folder.id)" class="flex-1 flex items-center gap-2 min-w-0">
            <span class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ backgroundColor: folder.color }"></span>
            <span class="truncate text-gray-700 dark:text-gray-300" :class="selectedFolderId === folder.id ? 'font-semibold text-blue-700 dark:text-blue-300' : ''">{{ folder.name }}</span>
            <span class="ml-auto px-2 py-0.5 rounded-full bg-gray-200 dark:bg-gray-700 text-xs shrink-0">{{ getFolderLogCount(folder.id) }}</span>
          </button>
          <button @click.stop="emit('request-edit-folder', folder)" class="opacity-0 group-hover/folder:opacity-100 p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-all" title="編輯">✏️</button>
          <button @click.stop="emit('request-delete-folder', folder)" class="opacity-0 group-hover/folder:opacity-100 p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-all" title="刪除">🗑️</button>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto p-3 space-y-2">
        <div v-if="visibleLogs.length === 0" class="text-center text-gray-500 dark:text-gray-400 py-10 text-sm">
          {{ sidebarEmptyText }}
        </div>

        <div
          v-for="log in visibleLogs"
          :key="log.key"
          draggable="true"
          @dragstart="onDragStart(log)"
          @dragend="onDragEnd"
          @dragover="onDragOver"
          @drop.stop="onDrop(log)"
          :class="[
            'backdrop-blur-sm rounded-xl p-3 border hover:shadow-lg transition-all cursor-pointer group',
            log.key === activeLogKey
              ? 'bg-blue-50/80 dark:bg-blue-900/30 border-blue-300 dark:border-blue-600 shadow-md'
              : 'bg-white/50 dark:bg-gray-800/50 border-white/20',
            draggedLogKey === log.key ? 'opacity-40' : ''
          ]"
          @click="emit('select-log', log)"
        >
          <div class="flex items-start gap-2 mb-2">
            <span class="text-gray-300 dark:text-gray-600 cursor-grab mt-0.5 shrink-0 select-none" title="拖曳排序">⋮⋮</span>

            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <h3 class="font-semibold text-sm text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors truncate">
                  {{ log.title }}
                </h3>
                <span v-if="log.status === 'generating'" class="flex-shrink-0">
                  <svg class="animate-spin h-3 w-3 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                </span>
              </div>
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ log.createdAt }}</p>
            </div>

            <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all shrink-0">
              <button @click.stop="emit('request-move-log', log)" class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg" title="移動到資料夾">📁</button>
              <button @click.stop="emit('request-delete-log', log)" class="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg" title="刪除">🗑️</button>
            </div>
          </div>

          <div class="space-y-1.5 pl-5">
            <div class="flex items-center gap-1.5 text-xs flex-wrap">
              <span class="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
                {{ log.sourceLabel }}
              </span>
              <span class="px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                {{ log.categoryLabel }}
              </span>
              <span class="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                {{ log.difficultyLabel }}
              </span>
              <span
                :class="[
                  'px-2 py-0.5 rounded-full',
                  log.status === 'completed'
                    ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                    : log.status === 'generating'
                      ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                      : 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300'
                ]"
              >
                {{ log.statusLabel }}
              </span>
            </div>

            <div v-if="log.scoreText || log.secondaryText" class="text-xs space-y-0.5">
              <div v-if="log.scoreText" class="flex items-center justify-between">
                <span class="text-gray-500 dark:text-gray-400">成績</span>
                <span class="font-bold text-gray-900 dark:text-white">{{ log.scoreText }}</span>
              </div>
              <div v-if="log.secondaryText" class="text-gray-500 dark:text-gray-400">
                {{ log.secondaryText }}
              </div>
            </div>

            <button
              v-if="log.canExportPdf"
              @click.stop="emit('export-pdf', log)"
              :disabled="exporting"
              class="w-full flex items-center justify-center gap-1.5 mt-1 px-3 py-1.5 bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-900/50 text-blue-700 dark:text-blue-300 text-xs font-semibold rounded-lg border border-blue-200 dark:border-blue-700 transition-all disabled:opacity-50"
            >
              <span>📦</span>
              <span>{{ exporting ? '匯出中...' : '匯出 PDF（題本 + 答案卡）' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>
