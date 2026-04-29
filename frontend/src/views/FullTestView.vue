<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import SharedExplanationCard from '@/components/SharedExplanationCard.vue'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import UnifiedTestSidebar from '@/components/UnifiedTestSidebar.vue'
import { toeicAPI } from '@/services/api'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import type { ListeningTestResponse, ReadingTestResponse, ListeningTestJobStatus, ReadingTestJobStatus, QuizFolderResponse, QuizLogSummary, TOEICQuestion } from '@/types'
import type { ExplanationChildItem, ExplanationItem, ExplanationOptionItem, ExplanationPartKey } from '@/types/explanations'
import type { FullTestSidebarLogSnapshot, SidebarFolderId, UnifiedSidebarLog } from '@/utils/testHistory'
import { SIDEBAR_DATA_UPDATED_EVENT, buildSidebarLogKey, formatDifficultyLabel, isFullTestBackendLog, isQuizBackendLog, notifySidebarDataUpdated, writeRawFullTestLogs } from '@/utils/testHistory'

const settingsStore = useSettingsStore()
const toast = useToast()
const route = useRoute()
const router = useRouter()

// ========== 類型定義 ==========

type FullTestResponse = ListeningTestResponse | ReadingTestResponse
type ListeningPartKey = 'part1' | 'part2' | 'part3' | 'part4'
type ReadingPartKey = 'part5' | 'part6' | 'part7_single' | 'part7_multiple'

// 使用者答案（統一結構）
interface Answer {
  globalNumber: number // 全局題號 1-200
  part: string
  localNumber: number // Part 內的題號
  answer: string | string[] // Part 3/4 用陣列
}

function isListeningTestData(data: FullTestResponse): data is ListeningTestResponse {
  return 'part1_questions' in data
}

function isReadingTestData(data: FullTestResponse): data is ReadingTestResponse {
  return 'part5_questions' in data
}

function isReadingPartKey(partKey: string): partKey is ReadingPartKey {
  return ['part5', 'part6', 'part7_single', 'part7_multiple'].includes(partKey)
}

function getReadingQuestions(data: ReadingTestResponse, partKey: ReadingPartKey): TOEICQuestion[] {
  switch (partKey) {
    case 'part5':
      return data.part5_questions
    case 'part6':
      return data.part6_questions
    case 'part7_single':
      return data.part7_single_questions
    case 'part7_multiple':
      return data.part7_multiple_questions
  }
}

// ========== 測驗記錄側邊欄 ==========

type TestType = 'listening' | 'reading'

type TestLog = {
  id: string
  title: string
  testType: TestType
  difficulty: 'easy' | 'medium' | 'hard'
  created_at: string
  completed_at?: string
  jobId?: string          // 生成中/失敗時保存，用於接續輪詢
  backendLogId?: string   // 後端 quiz_logs.id，用於持久化 testData
  testData: FullTestResponse | null  // 僅存於記憶體，不寫 localStorage
  answers: Map<number, Answer>
  score?: {
    correct: number
    total: number
  }
  timeElapsed?: number
  explanations?: Map<number, any>
  folder_id?: string | null
}

const sidebarOpen = ref(false)
const testLogs = ref<TestLog[]>([])
const quizSidebarLogs = ref<QuizLogSummary[]>([])
const backendQuizLogs = ref<QuizLogSummary[]>([])
const currentLogId = ref<string | null>(null)
const movingSidebarLog = ref<UnifiedSidebarLog | null>(null)
const deletingSidebarLog = ref<UnifiedSidebarLog | null>(null)

const SIDEBAR_QUERY_SOURCE = 'openHistorySource'
const SIDEBAR_QUERY_ID = 'openHistoryId'

// LocalStorage 管理
function testLogsStorageKey() {
  return 'toeic_test_logs_v2'
}

const CURRENT_JOB_KEY = 'toeic_test_current_job_v2'
const JOB_EVENT_NAME = 'full-test-job-updated'

function notifyJobUpdated() {
  window.dispatchEvent(new Event(JOB_EVENT_NAME))
}

function loadTestLogs() {
  try {
    const raw = localStorage.getItem(testLogsStorageKey())
    if (!raw) { testLogs.value = []; return }

    const logs = JSON.parse(raw)
    const recovered: TestLog[] = []
    for (const log of logs) {
      try {
        recovered.push({
          ...log,
          testData: null,  // 不存於 localStorage，需由後端取回
          answers: new Map(Object.entries(log.answers || {})),
          explanations: new Map(Object.entries(log.explanations || {}).map(([k, v]) => [Number(k), v]))
        })
      } catch {
        // 單筆損壞就跳過，不影響其他筆
      }
    }
    testLogs.value = recovered
  } catch {
    testLogs.value = []
  }
}

function saveTestLogs() {
  try {
    const logsToSave = testLogs.value.map(log => ({
      ...log,
      testData: null,  // testData 不存 localStorage（太大），由 backendLogId 取回
      answers: Object.fromEntries(log.answers),
      explanations: log.explanations ? Object.fromEntries(log.explanations) : {}
    }))
    writeRawFullTestLogs(logsToSave)
  } catch (e) {
    console.warn('測驗記錄 metadata 儲存失敗', e)
    toast.error('測驗記錄儲存失敗，可能是瀏覽器空間不足')
  }
}

function addTestLog(title: string, jobId?: string) {
  if (!testType.value) return

  const log: TestLog = {
    id: `${Date.now()}`,
    title,
    testType: testType.value,
    jobId,
    difficulty: config.value.difficulty,
    created_at: new Date().toISOString(),
    testData: null,
    answers: new Map()
  }

  currentLogId.value = log.id
  testLogs.value.unshift(log)

  // 僅保留最近 50 筆
  if (testLogs.value.length > 50) {
    testLogs.value.length = 50
  }

  saveTestLogs()
}

function updateCurrentTestLog() {
  if (!currentLogId.value) return

  const log = testLogs.value.find(l => l.id === currentLogId.value)
  if (!log) return

  log.answers = new Map(answers.value)
  log.explanations = new Map(explanations.value)
  log.completed_at = new Date().toISOString()
  log.timeElapsed = timeElapsed.value
  log.score = {
    correct: score.value.correct,
    total: score.value.total
  }

  saveTestLogs()

  // 同步分數到後端
  if (log.backendLogId) {
    toeicAPI.updateQuizLog(log.backendLogId, {
      score: { correct: log.score.correct, total: log.score.total }
    }).catch(e => console.warn('同步分數到後端失敗', e))
  }
}

async function loadTestLog(log: TestLog) {
  // 尚未生成完成但有 jobId：切回生成畫面並接續輪詢
  if (!log.testData && log.jobId) {
    stopStatusPolling()
    testType.value = log.testType
    testJobId.value = log.jobId
    currentLogId.value = log.id
    config.value.difficulty = log.difficulty
    generating.value = true
    stage.value = 'generating'
    // 重置進度顯示（輪詢後會更新）
    Object.keys(generatingProgress.value).forEach(key => {
      generatingProgress.value[key as keyof typeof generatingProgress.value] = 'pending'
    })
    partIndexMap.value = {}
    startStatusPolling()
    sidebarOpen.value = false
    return
  }

  // testData 不在記憶體中，但有 backendLogId：從後端取回
  if (!log.testData && log.backendLogId) {
    try {
      const backendLog = await toeicAPI.getQuizLog(log.backendLogId)
      if (backendLog.payload) {
        log.testData = backendLog.payload as FullTestResponse
      }
    } catch (e) {
      console.error('從後端取回測驗資料失敗', e)
      toast.error('載入測驗資料失敗，請稍後重試')
      return
    }
  }

  if (!log.testData) {
    toast.error('此測驗記錄無完整資料')
    return
  }

  stopStatusPolling()
  generating.value = false
  testData.value = log.testData
  testType.value = log.testType

  answers.value = new Map(log.answers)
  explanations.value = log.explanations ? new Map(log.explanations) : new Map()
  timeElapsed.value = log.timeElapsed || 0
  currentLogId.value = log.id

  // 如果有分數，切換到結果頁面
  if (log.score) {
    stopTimer()
    stage.value = 'result'
  } else {
    stage.value = 'quiz'
    globalQuestionNumber.value = 1
    currentPart.value = log.testType === 'listening' ? 'part1' : 'part5'
    startTimer()
  }

  sidebarOpen.value = false
}

function deleteTestLog(logId: string) {
  const index = testLogs.value.findIndex(log => log.id === logId)
  if (index !== -1) {
    const log = testLogs.value[index]
    if (!log) return
    if (log.backendLogId) {
      toeicAPI.deleteQuizLog(log.backendLogId).catch(e => console.warn('刪除後端記錄失敗', e))
    }
    testLogs.value.splice(index, 1)
    if (currentLogId.value === logId) currentLogId.value = null
    saveTestLogs()
  }
}

// ========== 資料夾系統 ==========

const quizFolders = ref<QuizFolderResponse[]>([])
const selectedFolderId = ref<string | 'all' | 'uncategorized'>('all')
const showFolderDialog = ref(false)
const folderName = ref('')
const folderColor = ref('#3B82F6')
const editingFolderId = ref<string | null>(null)
const showMoveDialog = ref(false)
const showDeleteConfirm = ref(false)

async function loadFolders() {
  try { quizFolders.value = await toeicAPI.getQuizFolders() } catch { /* ignore */ }
}

async function loadQuizSidebarLogs() {
  try {
    const logs = await toeicAPI.getQuizLogs()
    backendQuizLogs.value = logs
    quizSidebarLogs.value = logs.filter(isQuizBackendLog)
    syncBackendFullTestLogs()
  } catch {
    backendQuizLogs.value = []
    quizSidebarLogs.value = []
  }
}

function syncBackendFullTestLogs() {
  for (const backendLog of backendQuizLogs.value.filter(isFullTestBackendLog)) {
    const exactMatch = testLogs.value.find(log => log.backendLogId === backendLog.id || log.id === backendLog.id)
    if (exactMatch) continue

    const looseMatch = testLogs.value.find(log =>
      !log.backendLogId &&
      log.title === backendLog.title &&
      log.testType === (backendLog.mode === 'reading_full' ? 'reading' : 'listening') &&
      log.difficulty === (backendLog.difficulty === 'easy' || backendLog.difficulty === 'hard' ? backendLog.difficulty : 'medium')
    )

    if (looseMatch) {
      looseMatch.backendLogId = backendLog.id
      looseMatch.score = looseMatch.score ?? backendLog.score
      looseMatch.folder_id = looseMatch.folder_id ?? backendLog.folder_id ?? null
      continue
    }

    testLogs.value.push({
      id: backendLog.id,
      title: backendLog.title,
      testType: backendLog.mode === 'reading_full' ? 'reading' : 'listening',
      difficulty: backendLog.difficulty === 'easy' || backendLog.difficulty === 'hard' ? backendLog.difficulty : 'medium',
      created_at: backendLog.created_at,
      backendLogId: backendLog.id,
      testData: null,
      answers: new Map(),
      score: backendLog.score,
      folder_id: backendLog.folder_id ?? null,
    })
  }
}

const unifiedFullTestLogs = computed<UnifiedSidebarLog[]>(() => {
  return testLogs.value.map(log => ({
    key: buildSidebarLogKey('full_test', log.id),
    id: log.id,
    source: 'full_test',
    sourceLabel: '模擬測驗',
    title: log.title,
    categoryLabel: log.testType === 'listening' ? '聽力' : '閱讀',
    createdAt: formatTime(log.created_at),
    difficulty: log.difficulty,
    difficultyLabel: formatDifficultyLabel(log.difficulty),
    folderId: log.folder_id ?? null,
    status: log.score ? 'completed' : (!log.testData && log.jobId ? 'generating' : 'in_progress'),
    statusLabel: log.score ? '已完成' : (!log.testData && log.jobId ? '生成中' : '進行中'),
    scoreText: log.score ? `${log.score.correct} / ${log.score.total}` : undefined,
    secondaryText: log.timeElapsed ? `用時 ${formatDuration(log.timeElapsed)}` : (!log.testData && log.jobId ? '點擊切回生成畫面' : '點擊繼續作答'),
    canExportPdf: log.testType === 'reading' && !!(log.testData || log.backendLogId),
    testType: log.testType,
    backendLogId: log.backendLogId,
  }))
})

const unifiedQuizLogs = computed<UnifiedSidebarLog[]>(() => {
  return quizSidebarLogs.value.map(log => ({
    key: buildSidebarLogKey('quiz', log.id),
    id: log.id,
    source: 'quiz',
    sourceLabel: '題型測驗',
    title: log.title,
    categoryLabel: getQuizModeLabel(log.mode),
    createdAt: formatTime(log.created_at),
    difficulty: (log.difficulty === 'easy' || log.difficulty === 'hard' ? log.difficulty : 'medium'),
    difficultyLabel: formatDifficultyLabel(log.difficulty),
    folderId: log.folder_id ?? null,
    status: log.score ? 'completed' : 'in_progress',
    statusLabel: log.score ? '已完成' : '進行中',
    scoreText: log.score ? `${log.score.correct} / ${log.score.total}` : undefined,
    secondaryText: log.score ? undefined : '點擊載入題型測驗',
    canExportPdf: false,
    mode: log.mode,
  }))
})

const sidebarLogs = computed(() => {
  return [...unifiedFullTestLogs.value, ...unifiedQuizLogs.value]
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
})

const visibleSidebarLogs = computed(() => {
  if (selectedFolderId.value === 'all') return sidebarLogs.value
  if (selectedFolderId.value === 'uncategorized') return sidebarLogs.value.filter(log => !log.folderId)
  return sidebarLogs.value.filter(log => log.folderId === selectedFolderId.value)
})

const activeSidebarLogKey = computed(() => {
  return currentLogId.value ? buildSidebarLogKey('full_test', currentLogId.value) : null
})

function openAddFolderDialog() {
  editingFolderId.value = null; folderName.value = ''; folderColor.value = '#3B82F6'
  showFolderDialog.value = true
}
function openEditFolderDialog(folder: QuizFolderResponse) {
  editingFolderId.value = folder.id; folderName.value = folder.name; folderColor.value = folder.color
  showFolderDialog.value = true
}

async function submitFolder() {
  if (!folderName.value.trim()) { toast.error('請輸入資料夾名稱'); return }
  try {
    if (editingFolderId.value) {
      const updated = await toeicAPI.updateQuizFolder(editingFolderId.value, { name: folderName.value.trim(), color: folderColor.value })
      const idx = quizFolders.value.findIndex(f => f.id === editingFolderId.value)
      if (idx !== -1) quizFolders.value[idx] = updated
    } else {
      const created = await toeicAPI.createQuizFolder({ name: folderName.value.trim(), color: folderColor.value })
      quizFolders.value.push(created)
    }
    showFolderDialog.value = false
    notifySidebarDataUpdated()
  } catch { toast.error('操作失敗') }
}

async function deleteFolder(folderId: string, name: string) {
  if (!confirm(`確定要刪除「${name}」資料夾嗎？資料夾內的記錄會移到未分類。`)) return
  try {
    await toeicAPI.deleteQuizFolder(folderId)
    quizFolders.value = quizFolders.value.filter(f => f.id !== folderId)
    testLogs.value.forEach(l => { if (l.folder_id === folderId) l.folder_id = undefined })
    saveTestLogs()
    if (selectedFolderId.value === folderId) selectedFolderId.value = 'all'
    notifySidebarDataUpdated()
  } catch { toast.error('刪除失敗') }
}

function openMoveDialog(item: UnifiedSidebarLog) {
  movingSidebarLog.value = item
  showMoveDialog.value = true
}

async function moveToFolder(folderId: string | null) {
  const item = movingSidebarLog.value
  if (!item) return

  if (item.source === 'full_test') {
    const log = testLogs.value.find(l => l.id === item.id)
    if (!log) return
    log.folder_id = folderId ?? undefined
    saveTestLogs()
    if (log.backendLogId) {
      toeicAPI.updateQuizLog(log.backendLogId, { folder_id: folderId }).catch(e => console.warn(e))
    }
  } else {
    try {
      await toeicAPI.updateQuizLog(item.id, { folder_id: folderId })
      const log = quizSidebarLogs.value.find(l => l.id === item.id)
      if (log) log.folder_id = folderId
      notifySidebarDataUpdated()
    } catch (e) {
      console.warn('移動題型測驗記錄失敗', e)
      toast.error('移動記錄失敗')
      return
    }
  }

  showMoveDialog.value = false
  movingSidebarLog.value = null
}

async function onSidebarMoveLogToFolder(payload: { log: UnifiedSidebarLog; folderId: string | null }) {
  if (payload.log.source === 'full_test') {
    const log = testLogs.value.find(l => l.id === payload.log.id)
    if (!log) return
    log.folder_id = payload.folderId ?? undefined
    saveTestLogs()
    if (log.backendLogId) {
      toeicAPI.updateQuizLog(log.backendLogId, { folder_id: payload.folderId }).catch(e => console.warn(e))
    }
  } else {
    try {
      await toeicAPI.updateQuizLog(payload.log.id, { folder_id: payload.folderId })
      const log = quizSidebarLogs.value.find(l => l.id === payload.log.id)
      if (log) log.folder_id = payload.folderId
      notifySidebarDataUpdated()
    } catch (e) {
      console.warn('移動題型測驗記錄失敗', e)
      toast.error('移動記錄失敗')
      return
    }
  }

}

function onSidebarReorderLogs(payload: { draggedLog: UnifiedSidebarLog; targetLog: UnifiedSidebarLog }) {
  if (payload.draggedLog.source !== payload.targetLog.source) return

  if (payload.draggedLog.source === 'full_test') {
    const fromIdx = testLogs.value.findIndex(l => l.id === payload.draggedLog.id)
    const toIdx = testLogs.value.findIndex(l => l.id === payload.targetLog.id)
    if (fromIdx === -1 || toIdx === -1) return
    const [moved] = testLogs.value.splice(fromIdx, 1)
    if (!moved) return
    testLogs.value.splice(toIdx, 0, moved)
    saveTestLogs()
    return
  }

  const fromIdx = quizSidebarLogs.value.findIndex(l => l.id === payload.draggedLog.id)
  const toIdx = quizSidebarLogs.value.findIndex(l => l.id === payload.targetLog.id)
  if (fromIdx === -1 || toIdx === -1) return
  const [moved] = quizSidebarLogs.value.splice(fromIdx, 1)
  if (!moved) return
  quizSidebarLogs.value.splice(toIdx, 0, moved)
}

function confirmDeleteTestLog(item: UnifiedSidebarLog) {
  deletingSidebarLog.value = item
  showDeleteConfirm.value = true
}

async function executeDeleteTestLog() {
  const item = deletingSidebarLog.value
  if (!item) return

  if (item.source === 'full_test') {
    deleteTestLog(item.id)
  } else {
    try {
      await toeicAPI.deleteQuizLog(item.id)
      quizSidebarLogs.value = quizSidebarLogs.value.filter(log => log.id !== item.id)
      notifySidebarDataUpdated()
    } catch (e) {
      console.warn('刪除題型測驗記錄失敗', e)
      toast.error('測驗記錄刪除失敗')
    }
  }

  showDeleteConfirm.value = false
  deletingSidebarLog.value = null
}

function handleSidebarDataUpdated() {
  loadTestLogs()
  loadFolders()
  loadQuizSidebarLogs()
}

function formatTime(ts: string) {
  const d = new Date(ts)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${hh}:${mm}`
}

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${mins}m`
}

function getQuizModeLabel(mode: string) {
  const labels: Record<string, string> = {
    part1: 'Part 1',
    part2: 'Part 2',
    part3: 'Part 3',
    part4: 'Part 4',
    part5: 'Part 5',
    part6: 'Part 6',
    part7_single: 'Part 7 單篇',
    part7_multiple: 'Part 7 多篇',
  }

  return labels[mode] || mode
}

// ========== 狀態管理 ==========

// 測驗階段
const stage = ref<'config' | 'generating' | 'quiz' | 'result' | 'explanations'>('config')

// 測驗類型
const testType = ref<TestType | null>(null)

// 配置
const config = ref({
  difficulty: 'medium' as 'easy' | 'medium' | 'hard',
  provider: settingsStore.settings.defaultProvider,
  model: settingsStore.settings.defaultModel || 'gpt-4o-mini',
  apiKey: settingsStore.settings.apiKeys[settingsStore.settings.defaultProvider] || '',
  // 媒體功能 provider（圖片、語音生成）
  mediaProvider: 'gemini' as 'gemini',
  mediaApiKey: (settingsStore.settings.apiKeys.gemini_media || settingsStore.settings.apiKeys.gemini) || ''
})

// 測驗資料
const testData = ref<ListeningTestResponse | ReadingTestResponse | null>(null)

// 生成進度
const generatingProgress = ref({
  part1: 'pending' as 'pending' | 'generating' | 'completed' | 'error',
  part2: 'pending' as 'pending' | 'generating' | 'completed' | 'error',
  part3: 'pending' as 'pending' | 'generating' | 'completed' | 'error',
  part4: 'pending' as 'pending' | 'generating' | 'completed' | 'error',
  part5: 'pending' as 'pending' | 'generating' | 'completed' | 'error',
  part6: 'pending' as 'pending' | 'generating' | 'completed' | 'error',
  part7_single: 'pending' as 'pending' | 'generating' | 'completed' | 'error',
  part7_multiple: 'pending' as 'pending' | 'generating' | 'completed' | 'error'
})

// 每個 Part 的細部題數進度（聽力用 partX_index，閱讀無細部追蹤）
const partIndexMap = ref<Record<string, number>>({})

const PART_TOTALS: Record<string, number> = {
  part1: 6, part2: 25, part3: 13, part4: 10,
  part5: 30, part6: 16, part7_single: 29, part7_multiple: 25
}

function getPartProgressPct(partKey: string): number {
  const status = generatingProgress.value[partKey as keyof typeof generatingProgress.value]
  if (status === 'completed') return 100
  if (status === 'pending') return 0
  const idx = partIndexMap.value[partKey] ?? 0
  const total = PART_TOTALS[partKey] ?? 1
  return idx > 0 ? Math.min(Math.round((idx / total) * 100), 99) : 0
}

const overallProgress = computed(() => {
  const parts = testType.value === 'listening'
    ? ['part1', 'part2', 'part3', 'part4']
    : ['part5', 'part6', 'part7_single', 'part7_multiple']
  const completed = parts.filter(k => generatingProgress.value[k as keyof typeof generatingProgress.value] === 'completed').length
  const total = parts.length
  return { completed, total, pct: Math.round((completed / total) * 100) }
})

// ========== 作答相關 ==========

// 當前 Part 和題號（全局題號，1-200）
const currentPart = ref<'part1' | 'part2' | 'part3' | 'part4' | 'part5' | 'part6' | 'part7_single' | 'part7_multiple'>('part1')
const globalQuestionNumber = ref(1) // 1-200

// 使用者答案
const answers = ref<Map<number, Answer>>(new Map())

// 計時器
const timeElapsed = ref(0) // 秒
let timerInterval: ReturnType<typeof setInterval> | null = null
const showTimer = ref(true)

// 詳解相關
const explanations = ref<Map<number, any>>(new Map())
const generatingExplanation = ref<Map<number, boolean>>(new Map())
const explanationFilter = ref<'all' | 'wrong' | 'correct'>('all')
const explanationFilters = [
  { value: 'all', label: '全部題目' },
  { value: 'wrong', label: '僅錯題' },
  { value: 'correct', label: '僅答對' }
] as const

// 側邊欄
const showSidebar = ref(true)
const showAnswerSheet = ref(false)

// Part 資訊與題號範圍（聽力和閱讀各自從 1 開始）
const partInfo = [
  { key: 'part1', name: 'Part 1 照片描述', count: 6, start: 1, end: 6 },
  { key: 'part2', name: 'Part 2 應答問題', count: 25, start: 7, end: 31 },
  { key: 'part3', name: 'Part 3 簡短對話', count: 39, start: 32, end: 70 },
  { key: 'part4', name: 'Part 4 簡短獨白', count: 30, start: 71, end: 100 },
  { key: 'part5', name: 'Part 5 句子填空', count: 30, start: 1, end: 30 },
  { key: 'part6', name: 'Part 6 段落填空', count: 16, start: 31, end: 46 },
  { key: 'part7_single', name: 'Part 7 單篇閱讀', count: 29, start: 47, end: 75 },
  { key: 'part7_multiple', name: 'Part 7 多篇閱讀', count: 25, start: 76, end: 100 }
]

// ========== 計算屬性 ==========

// 當前 Part 資訊
const currentPartInfo = computed(() => {
  return partInfo.find(p => p.key === currentPart.value)
})

// 當前題目資料
const currentQuestion = computed(() => {
  if (!testData.value) return null

  const partData = currentPartInfo.value
  if (!partData) return null

  const localIndex = globalQuestionNumber.value - partData.start
  const data = testData.value

  switch (currentPart.value) {
    case 'part1':
      return isListeningTestData(data) ? data.part1_questions[localIndex] ?? null : null
    case 'part2':
      return isListeningTestData(data) ? data.part2_questions[localIndex] ?? null : null
    case 'part3': {
      if (!isListeningTestData(data)) return null
      // Part 3: 每組對話有 3 題
      const groupIndex = Math.floor(localIndex / 3)
      const subIndex = localIndex % 3
      const group = data.part3_questions[groupIndex]
      return group ? { ...group, subIndex } : null
    }
    case 'part4': {
      if (!isListeningTestData(data)) return null
      // Part 4: 每段獨白有 3 題
      const groupIndex = Math.floor(localIndex / 3)
      const subIndex = localIndex % 3
      const group = data.part4_questions[groupIndex]
      return group ? { ...group, subIndex } : null
    }
    case 'part5':
    case 'part6':
    case 'part7_single':
    case 'part7_multiple':
      return isReadingTestData(data) ? getReadingQuestions(data, currentPart.value)[localIndex] ?? null : null
    default:
      return null
  }
})

const currentReadingGroup = computed(() => {
  if (!testData.value) return null
  if (!['part6', 'part7_single', 'part7_multiple'].includes(currentPart.value)) return null
  if (!isReadingTestData(testData.value) || !isReadingPartKey(currentPart.value)) return null

  const part = partInfo.find(p => p.key === currentPart.value)
  if (!part) return null
  const questions = getReadingQuestions(testData.value, currentPart.value)
  const localIndex = globalQuestionNumber.value - part.start
  if (!questions || localIndex < 0 || localIndex >= questions.length) return null

  const getKey = (q: any) => {
    if (currentPart.value === 'part6') {
      return q.question_text || ''
    }
    if (currentPart.value === 'part7_single') {
      return q.passage || ''
    }
    return JSON.stringify(q.passages || [])
  }

  const currentKey = getKey(questions[localIndex])
  let startIndex = localIndex
  let endIndex = localIndex

  while (startIndex > 0 && getKey(questions[startIndex - 1]) === currentKey) {
    startIndex -= 1
  }
  while (endIndex < questions.length - 1 && getKey(questions[endIndex + 1]) === currentKey) {
    endIndex += 1
  }

  return {
    start: part.start + startIndex,
    end: part.start + endIndex,
    style: questions[startIndex]?.passage_style || questions[localIndex]?.passage_style
  }
})

const readingGroupLabel = computed(() => {
  const group = currentReadingGroup.value
  if (!group) return ''
  const style = group.style || 'text'
  return `Questions ${group.start}-${group.end} refer to the following ${style}.`
})

const currentReadingPassage = computed(() => {
  const question = currentQuestion.value as any
  if (!question) return ''

  if (typeof question.passage === 'string' && question.passage.trim()) {
    return question.passage
  }

  if (currentPart.value === 'part6' && typeof question.question_text === 'string') {
    return question.question_text
  }

  return ''
})

const currentReadingPassages = computed<string[]>(() => {
  const question = currentQuestion.value as any
  return Array.isArray(question?.passages) ? question.passages : []
})

const currentReadingQuestionText = computed(() => {
  const question = currentQuestion.value as any
  if (!question) return ''
  if (currentPart.value === 'part6' && currentReadingPassage.value) return ''
  return typeof question.question_text === 'string' ? question.question_text : ''
})

const currentReadingBlankPosition = computed<number | null>(() => {
  if (currentPart.value !== 'part6') return null

  const question = currentQuestion.value as any
  const explicitPosition = question?.blank_position
  if (typeof explicitPosition === 'number') return explicitPosition
  if (typeof explicitPosition === 'string' && explicitPosition.trim()) return Number(explicitPosition)

  const partData = currentPartInfo.value
  if (!partData) return null

  const localIndex = globalQuestionNumber.value - partData.start
  return localIndex >= 0 ? (localIndex % 4) + 1 : null
})

// 進度統計
const activeParts = computed(() => {
  if (testType.value === 'listening') return partInfo.slice(0, 4)
  if (testType.value === 'reading') return partInfo.slice(4)
  return partInfo
})

const progress = computed(() => {
  const total = activeParts.value.reduce((sum, p) => sum + p.count, 0)
  const answered = Array.from(answers.value.values()).filter(a =>
    activeParts.value.some(p => a.globalNumber >= p.start && a.globalNumber <= p.end)
  ).length
  return {
    answered,
    total,
    percentage: total > 0 ? Math.round((answered / total) * 100) : 0
  }
})

// 各 Part 進度
const partProgress = computed(() => {
  return activeParts.value.map(part => {
    const partAnswers = Array.from(answers.value.values()).filter(
      a => a.globalNumber >= part.start && a.globalNumber <= part.end
    )
    return {
      ...part,
      answered: partAnswers.length,
      percentage: Math.round((partAnswers.length / part.count) * 100)
    }
  })
})

// 計分
const score = computed(() => {
  const total = activeParts.value.reduce((sum, p) => sum + p.count, 0)
  if (!testData.value || stage.value !== 'result') {
    return { correct: 0, total, percentage: 0, byPart: [] }
  }

  let correct = 0
  const byPart: any[] = []

  activeParts.value.forEach(part => {
    let partCorrect = 0
    const partTotal = part.count

    for (let i = part.start; i <= part.end; i++) {
      const answer = answers.value.get(i)
      if (!answer) continue

      const isCorrect = checkAnswer(i, answer.answer)
      if (isCorrect) {
        correct++
        partCorrect++
      }
    }

    byPart.push({
      ...part,
      correct: partCorrect,
      total: partTotal,
      percentage: Math.round((partCorrect / partTotal) * 100)
    })
  })

  return {
    correct,
    total,
    percentage: total > 0 ? Math.round((correct / total) * 100) : 0,
    byPart
  }
})

// ========== 核心函數 ==========

// 檢查答案是否正確
function checkAnswer(globalNum: number, userAnswer: string | string[]): boolean {
  if (!testData.value) return false

  const part = activeParts.value.find(p => globalNum >= p.start && globalNum <= p.end)
  if (!part) return false

  const localIndex = globalNum - part.start
  const data = testData.value

  switch (part.key) {
    case 'part1': {
      if (!isListeningTestData(data)) return false
      const q = data.part1_questions[localIndex]
      return !!(q && userAnswer === q.correct_answer)
    }
    case 'part2': {
      if (!isListeningTestData(data)) return false
      const q = data.part2_questions[localIndex]
      return !!(q && userAnswer === q.correct_answer)
    }
    case 'part3': {
      if (!isListeningTestData(data)) return false
      const groupIndex = Math.floor(localIndex / 3)
      const subIndex = localIndex % 3
      const group = data.part3_questions[groupIndex]
      return !!(group && userAnswer === group.correct_answers[subIndex])
    }
    case 'part4': {
      if (!isListeningTestData(data)) return false
      const groupIndex = Math.floor(localIndex / 3)
      const subIndex = localIndex % 3
      const group = data.part4_questions[groupIndex]
      return !!(group && userAnswer === group.correct_answers[subIndex])
    }
    case 'part5':
    case 'part6':
    case 'part7_single':
    case 'part7_multiple': {
      if (!isReadingTestData(data)) return false
      const questions = getReadingQuestions(data, part.key)
      const q = questions[localIndex]
      return !!(q && userAnswer === q.correct_answer)
    }
    default:
      return false
  }
}

// API Key 提醒 modal
const showApiKeyModal = ref(false)

// 生成測驗 - 使用後端背景任務 + 輪詢
const generating = ref(false)
const testJobId = ref<string | null>(null)
let statusPollingTimer: number | null = null

async function generateTest() {
  if (!testType.value) {
    toast.error('請先選擇測驗類型')
    return
  }

  // 同步設定頁面的最新配置（固定使用 Gemini）
  config.value.provider = 'gemini'
  config.value.model = settingsStore.settings.defaultModel || 'gemini-2.5-flash'
  config.value.apiKey = settingsStore.settings.apiKeys.gemini || ''
  config.value.mediaProvider = 'gemini'
  config.value.mediaApiKey = settingsStore.settings.apiKeys.gemini || ''

  const textProvider = config.value.provider
  const textModel = config.value.model
  const textApiKey = config.value.apiKey
  const mediaProvider = config.value.mediaProvider
  const mediaModel = config.value.model
  const mediaApiKey = config.value.mediaApiKey

  // 檢查必要的 API Keys
  if (!textApiKey || (testType.value === 'listening' && !mediaApiKey)) {
    showApiKeyModal.value = true
    return
  }

  generating.value = true
  stage.value = 'generating'

  // 重置進度
  Object.keys(generatingProgress.value).forEach(key => {
    generatingProgress.value[key as keyof typeof generatingProgress.value] = 'pending'
  })
  partIndexMap.value = {}

  const testTypeName = testType.value === 'listening' ? '聽力' : '閱讀'

  try {
    let job: any

    if (testType.value === 'listening') {
      job = await toeicAPI.startListeningTestJob({
        difficulty: config.value.difficulty,
        provider: textProvider,
        model: textModel,
        api_key: textApiKey,
        text_provider: textProvider,
        text_model: textModel,
        text_api_key: textApiKey,
        media_provider: mediaProvider,
        media_model: mediaModel,
        media_api_key: mediaApiKey
      })
    } else {
      job = await toeicAPI.startReadingTestJob({
        difficulty: config.value.difficulty,
        provider: textProvider,
        model: textModel,
        api_key: textApiKey
      })
    }

    testJobId.value = job.job_id

    // 建立側邊欄記錄（生成開始時就建立，testData 之後填入）
    const testTypeName2 = testType.value === 'listening' ? '聽力' : '閱讀'
    const diffName2 = config.value.difficulty === 'easy' ? '簡單' : config.value.difficulty === 'medium' ? '中等' : '困難'
    addTestLog(`${testTypeName2}測驗 - ${diffName2}`, job.job_id)

    // 記住當前任務
    localStorage.setItem(
      CURRENT_JOB_KEY,
      JSON.stringify({
        jobId: job.job_id,
        testType: testType.value,
        config: config.value,
        startedAt: new Date().toISOString()
      })
    )
    notifyJobUpdated()

    // 套用初始進度
    if (job.progress) {
      updateProgressFromJobStatus(job.progress)
    }

    startStatusPolling()
  } catch (error: any) {
    console.error('啟動測驗任務失敗:', error)
    toast.error(error?.message || '啟動測驗任務失敗，請稍後重試')
    generating.value = false
  }
}


function updateProgressFromJobStatus(progress: any) {
  const mapped: Record<string, 'pending' | 'generating' | 'completed' | 'error'> = {
    part1: 'pending',
    part2: 'pending',
    part3: 'pending',
    part4: 'pending',
    part5: 'pending',
    part6: 'pending',
    part7_single: 'pending',
    part7_multiple: 'pending'
  }
  for (const [key, value] of Object.entries(progress as Record<string, string>)) {
    if (!(key in mapped)) continue
    if (value === 'running') {
      mapped[key] = 'generating'
    } else if (value === 'completed' || value === 'error' || value === 'pending') {
      mapped[key] = value as any
    } else {
      mapped[key] = 'pending'
    }
  }
  generatingProgress.value = mapped as any

  // Capture per-part index for progress bars
  const indexKeys = ['part1_index', 'part2_index', 'part3_index', 'part4_index',
                     'part5_index', 'part6_index', 'part7_single_index', 'part7_multiple_index']
  for (const key of indexKeys) {
    if (key in (progress as any)) {
      const partKey = key.replace('_index', '')
      partIndexMap.value[partKey] = (progress as any)[key]
    }
  }
}

function stopStatusPolling() {
  if (statusPollingTimer !== null) {
    window.clearInterval(statusPollingTimer)
    statusPollingTimer = null
  }
}

async function checkTestJobStatus() {
  if (!testJobId.value || !testType.value) return

  try {
    let status: any

    if (testType.value === 'listening') {
      status = await toeicAPI.getListeningTestJobStatus(testJobId.value)
    } else {
      status = await toeicAPI.getReadingTestJobStatus(testJobId.value)
    }

    // 更新進度
    if (status.progress) {
      updateProgressFromJobStatus(status.progress)
    }

    // 若任何 Part 發生錯誤，停止輪詢並讓使用者手動接續
    if (hasGenerationError.value && status.status !== 'completed') {
      stopStatusPolling()
      generating.value = false
      return
    }

    if (status.status === 'completed') {
      try {
        let result: any

        if (testType.value === 'listening') {
          result = await toeicAPI.getListeningTestJobResult(testJobId.value)
        } else {
          result = await toeicAPI.getReadingTestJobResult(testJobId.value)
        }

        testData.value = result

        // 更新現有記錄的 testData（生成完成）
        const completedLog = testLogs.value.find(l => l.id === currentLogId.value)
        if (completedLog) {
          completedLog.testData = result
          completedLog.jobId = undefined

          // 將 testData 持久化到後端 SQLite（避免 localStorage 空間不足）
          try {
            const testTypeName3 = testType.value === 'listening' ? '聽力' : '閱讀'
            const diffName3 = config.value.difficulty === 'easy' ? '簡單' : config.value.difficulty === 'medium' ? '中等' : '困難'
            const backendLog = await toeicAPI.createQuizLog({
              mode: testType.value === 'listening' ? 'listening_full' : 'reading_full',
              title: completedLog.title || `${testTypeName3}測驗 - ${diffName3}`,
              count: 100,
              difficulty: config.value.difficulty,
            })
            await toeicAPI.updateQuizLog(backendLog.id, { payload: result as Record<string, any> })
            completedLog.backendLogId = backendLog.id
          } catch (e) {
            console.warn('儲存測驗資料到後端失敗，資料僅存於記憶體', e)
          }

          saveTestLogs()
        }

        // 標記所有 Part 為完成
        Object.keys(generatingProgress.value).forEach(key => {
          const partKey = key as keyof typeof generatingProgress.value
          if (testType.value === 'listening' && ['part1', 'part2', 'part3', 'part4'].includes(key)) {
            generatingProgress.value[partKey] = 'completed'
          } else if (testType.value === 'reading' && ['part5', 'part6', 'part7_single', 'part7_multiple'].includes(key)) {
            generatingProgress.value[partKey] = 'completed'
          }
        })

        stopStatusPolling()
        generating.value = false
        stage.value = 'quiz'
        globalQuestionNumber.value = 1
        currentPart.value = testType.value === 'listening' ? 'part1' : 'part5'

        // 清除任務記錄
        localStorage.removeItem(CURRENT_JOB_KEY)
        notifyJobUpdated()

        // 開始計時
        startTimer()

      } catch (error: any) {
        console.error('獲取測驗結果失敗:', error)
        toast.error('獲取測驗結果失敗')
        stopStatusPolling()
        generating.value = false
      }
    } else if (status.status === 'error') {
      stopStatusPolling()
      generating.value = false
      toast.error(status.message || '測驗生成失敗')
    }
  } catch (error: any) {
    console.error('查詢測驗狀態失敗:', error)
  }
}

function startStatusPolling() {
  isPaused.value = false
  stopStatusPolling()
  checkTestJobStatus()
  statusPollingTimer = window.setInterval(checkTestJobStatus, 2000) // 每 2 秒查詢一次
}

// 暫停生成（停止前端輪詢，後端繼續跑，可接續）
const isPaused = ref(false)

function pauseGeneration() {
  stopStatusPolling()
  isPaused.value = true
}

function resumePolling() {
  isPaused.value = false
  startStatusPolling()
}

// 暫時離開生成畫面（背景繼續跑，可從側邊欄切回）
function leaveGenerating() {
  stopStatusPolling()
  isPaused.value = false
  generating.value = false
  stage.value = 'config'
  // 保留 testJobId / currentLogId / localStorage，稍後可從側邊欄接續
}

// 接續生成測驗
const hasGenerationError = computed(() => {
  return Object.values(generatingProgress.value).includes('error')
})

async function resumeFullTest() {
  if (!testJobId.value || !testType.value) {
    const raw = localStorage.getItem(CURRENT_JOB_KEY)
    if (raw) {
      try {
        const saved = JSON.parse(raw) as { jobId?: string; testType?: TestType }
        if (saved.jobId && saved.testType) {
          testJobId.value = saved.jobId
          testType.value = saved.testType
        }
      } catch {
        localStorage.removeItem(CURRENT_JOB_KEY)
        notifyJobUpdated()
      }
    }
  }

  if (!testJobId.value || !testType.value) {
    toast.error('找不到可接續的測驗任務')
    return
  }

  // 同步設定頁面的最新配置（固定使用 Gemini）
  config.value.provider = 'gemini'
  config.value.model = settingsStore.settings.defaultModel || 'gemini-2.5-flash'
  config.value.apiKey = settingsStore.settings.apiKeys.gemini || ''
  config.value.mediaProvider = 'gemini'
  config.value.mediaApiKey = settingsStore.settings.apiKeys.gemini || ''

  const textProvider = config.value.provider
  const textModel = config.value.model
  const textApiKey = config.value.apiKey
  const mediaProvider = config.value.mediaProvider
  const mediaModel = config.value.model
  const mediaApiKey = config.value.mediaApiKey

  // 檢查必要的 API Keys
  if (!textApiKey || (testType.value === 'listening' && !mediaApiKey)) {
    showApiKeyModal.value = true
    return
  }

  generating.value = true
  stage.value = 'generating'

  try {
    let job: any

    if (testType.value === 'listening') {
      job = await toeicAPI.resumeListeningTestJob(testJobId.value, {
        difficulty: config.value.difficulty,
        provider: textProvider,
        model: textModel,
        api_key: textApiKey,
        text_provider: textProvider,
        text_model: textModel,
        text_api_key: textApiKey,
        media_provider: mediaProvider,
        media_model: mediaModel,
        media_api_key: mediaApiKey
      })
    } else {
      job = await toeicAPI.resumeReadingTestJob(testJobId.value, {
        difficulty: config.value.difficulty,
        provider: textProvider,
        model: textModel,
        api_key: textApiKey
      })
    }

    localStorage.setItem(
      CURRENT_JOB_KEY,
      JSON.stringify({
        jobId: testJobId.value,
        testType: testType.value,
        config: config.value,
        startedAt: new Date().toISOString()
      })
    )
    notifyJobUpdated()

    if (job.progress) {
      updateProgressFromJobStatus(job.progress)
    }

    startStatusPolling()
    const testTypeName = testType.value === 'listening' ? '聽力' : '閱讀'
  } catch (error: any) {
    console.error('接續測驗任務失敗:', error)
    toast.error(error?.message || '接續測驗任務失敗，請稍後重試')
    generating.value = false
  }
}

// 選擇答案
function selectAnswer(answer: string, questionIndex: number = 0) {
  if (stage.value !== 'quiz') return

  const partData = currentPartInfo.value
  if (!partData) return

  // 對於 Part 3/4 的grouped questions，questionIndex 表示組內第幾題 (0, 1, 2)
  // 對於其他 Part，questionIndex 為 0（使用 globalQuestionNumber）
  const targetQuestionNumber = globalQuestionNumber.value + questionIndex

  answers.value.set(targetQuestionNumber, {
    globalNumber: targetQuestionNumber,
    part: currentPart.value,
    localNumber: targetQuestionNumber - partData.start + 1,
    answer
  })
}

// 導航
function goToQuestion(globalNum: number) {
  if (globalNum < 1 || globalNum > 100) return

  globalQuestionNumber.value = globalNum

  // 更新當前 Part（只在 activeParts 中搜尋，避免聽力/閱讀範圍重疊誤判）
  const part = activeParts.value.find(p => globalNum >= p.start && globalNum <= p.end)
  if (part) {
    currentPart.value = part.key as any
  }
}

function nextQuestion() {
  if (globalQuestionNumber.value < 100) {
    goToQuestion(globalQuestionNumber.value + 1)
  }
}

function prevQuestion() {
  if (globalQuestionNumber.value > 1) {
    goToQuestion(globalQuestionNumber.value - 1)
  }
}

function goToPart(partKey: string) {
  const part = partInfo.find(p => p.key === partKey)
  if (part) {
    goToQuestion(part.start)
  }
}

// 提交測驗
function submitTest() {
  if (!confirm('確定要提交測驗嗎？提交後將無法修改答案。')) return

  stopTimer()
  stage.value = 'result'

  // 更新測驗記錄
  updateCurrentTestLog()

}

// 獲取題目資料（根據題號）
function getQuestionData(questionNumber: number) {
  if (!testData.value) return null

  const part = activeParts.value.find(p => questionNumber >= p.start && questionNumber <= p.end)
  if (!part) return null

  const localIndex = questionNumber - part.start
  let questionText = ''
  let options: any[] = []
  let correctAnswer = ''
  let questionType: string | undefined
  let passage: string | undefined
  let passages: string[] | undefined
  let passageStyle: string | undefined
  const data = testData.value

  switch (part.key) {
    case 'part1': {
      if (!isListeningTestData(data)) return null
      const q = data.part1_questions[localIndex]
      if (!q) return null
      correctAnswer = q.correct_answer
      questionText = `Part 1 - 照片描述題 ${questionNumber}`
      options = [
        { label: 'A', text: 'Option A' },
        { label: 'B', text: 'Option B' },
        { label: 'C', text: 'Option C' },
        { label: 'D', text: 'Option D' }
      ]
      break
    }
    case 'part2': {
      if (!isListeningTestData(data)) return null
      const q = data.part2_questions[localIndex]
      if (!q) return null
      correctAnswer = q.correct_answer
      questionText = `Part 2 - 應答問題 ${questionNumber}`
      options = [
        { label: 'A', text: 'Option A' },
        { label: 'B', text: 'Option B' },
        { label: 'C', text: 'Option C' }
      ]
      break
    }
    case 'part3': {
      if (!isListeningTestData(data)) return null
      const groupIndex = Math.floor(localIndex / 3)
      const subIndex = localIndex % 3
      const group = data.part3_questions[groupIndex]
      if (!group) return null
      const q = group.questions[subIndex]
      if (!q) return null
      const subCorrectAnswer = group.correct_answers[subIndex]
      if (!subCorrectAnswer) return null
      correctAnswer = subCorrectAnswer
      questionText = q.question_text
      options = q.options
      break
    }
    case 'part4': {
      if (!isListeningTestData(data)) return null
      const groupIndex = Math.floor(localIndex / 3)
      const subIndex = localIndex % 3
      const group = data.part4_questions[groupIndex]
      if (!group) return null
      const q = group.questions[subIndex]
      if (!q) return null
      const subCorrectAnswer = group.correct_answers[subIndex]
      if (!subCorrectAnswer) return null
      correctAnswer = subCorrectAnswer
      questionText = q.question_text
      options = q.options
      break
    }
    case 'part5':
    case 'part6':
    case 'part7_single':
    case 'part7_multiple': {
      if (!isReadingTestData(data)) return null
      const questions = getReadingQuestions(data, part.key)
      const q = questions[localIndex]
      if (!q) return null
      correctAnswer = q.correct_answer
      questionType = q.question_type
      questionText = q.question_text
      options = q.options
      passage = q.passage
      passages = q.passages
      passageStyle = q.passage_style
      const blankPosition: number | undefined = part.key === 'part6' ? ((q as any).blank_position ?? (localIndex % 4) + 1) : undefined
      if (part.key === 'part6') {
        // Resolve passage from this question or first question in the group
        const groupStart = Math.floor(localIndex / 4) * 4
        const resolvedPassage = (passage && passage !== '[同一篇文章]')
          ? passage
          : (questions[groupStart]?.passage || questions[groupStart]?.question_text || '')
        const userAnswer2 = answers.value.get(questionNumber)?.answer || ''
        return {
          question_number: questionNumber,
          user_answer: userAnswer2,
          correct_answer: correctAnswer,
          question_type: questionType,
          question_text: '',   // passage already shown via passage field; no separate question_text for Part 6
          passage_style: passageStyle,
          passage: resolvedPassage,
          passages: undefined,
          options,
          blank_position: blankPosition
        }
      }
      break  // part5 / part7_single / part7_multiple — fall to general return below
    }
    default:
      return null
  }

  const userAnswer = answers.value.get(questionNumber)?.answer || ''

  return {
    question_number: questionNumber,
    user_answer: userAnswer,
    correct_answer: correctAnswer,
    question_type: questionType,
    question_text: questionText,
    passage_style: passageStyle,
    passage,
    passages,
    options: options
  }
}

// 生成單題詳解
async function generateSingleExplanation(questionNumber: number) {
  if (!testData.value) return

  const questionData = getQuestionData(questionNumber)
  if (!questionData) {
    toast.error('無法獲取題目資料')
    return
  }

  generatingExplanation.value.set(questionNumber, true)
  try {
    const provider = 'gemini'  // 固定使用 Gemini
    const model = settingsStore.settings.defaultModel || 'gemini-2.5-flash'
    const apiKey = settingsStore.settings.apiKeys.gemini

    // 呼叫 API 生成單題詳解
    const exps = await toeicAPI.generateExplanations({
      answers: [questionData],
      provider: provider,
      model: model,
      api_key: apiKey
    })

    if (exps && exps.length > 0) {
      explanations.value.set(questionNumber, exps[0])

      // 更新測驗記錄
      updateCurrentTestLog()
    }
  } catch (error: any) {
    console.error('生成詳解失敗:', error)
    const errorMsg = error?.response?.data?.detail || '生成詳解失敗'
    toast.error(errorMsg)
  } finally {
    generatingExplanation.value.set(questionNumber, false)
  }
}

// 查看詳解頁面
function viewExplanations() {
  stage.value = 'explanations'
}

// 取得 Part 的題號列表（根據篩選條件）
function getPartQuestions(part: typeof partInfo[0]): number[] {
  const questions: number[] = []
  for (let i = part.start; i <= part.end; i++) {
    const userAnswer = answers.value.get(i)?.answer || ''
    const isCorrect = checkAnswer(i, userAnswer)

    if (explanationFilter.value === 'all') {
      questions.push(i)
    } else if (explanationFilter.value === 'wrong' && !isCorrect) {
      questions.push(i)
    } else if (explanationFilter.value === 'correct' && isCorrect) {
      questions.push(i)
    }
  }
  return questions
}

function buildOptionItems(options: any[] | undefined, correctAnswer: string, userAnswer: string): ExplanationOptionItem[] {
  return (options || []).map((option: any) => ({
    label: option.label,
    text: option.text,
    isCorrect: option.label === correctAnswer,
    isUserAnswer: option.label === userAnswer && option.label !== correctAnswer,
  }))
}

function getPartKeyForQuestion(questionNumber: number): ExplanationPartKey | null {
  const part = activeParts.value.find(p => questionNumber >= p.start && questionNumber <= p.end)
  return (part?.key as ExplanationPartKey | undefined) || null
}

function buildFullTestExplanationItem(questionNum: number): ExplanationItem | null {
  const partKey = getPartKeyForQuestion(questionNum)
  if (!partKey) return null

  const answerValue = answers.value.get(questionNum)?.answer
  const normalizedAnswer = Array.isArray(answerValue) ? '' : (answerValue || '')
  const questionData = getQuestionData(questionNum)
  const isCorrect = checkAnswer(questionNum, answerValue || '')

  if (partKey === 'part1') {
    const raw = getPart1RawData(questionNum)
    if (!raw) return null
    return {
      id: `full-${partKey}-${questionNum}`,
      questionNumber: questionNum,
      partKey,
      title: `題目 ${questionNum}`,
      isCorrect,
      userAnswer: normalizedAnswer,
      correctAnswer: raw.correct_answer,
      canGenerateExplanation: false,
      isGenerating: generatingExplanation.value.get(questionNum) || false,
      staticHint: '📷 照片描述題：請播放各選項音檔，比對圖片內容，選出最符合照片的描述。',
      media: {
        imageUrl: raw.image_url,
        audioOptions: (raw.audio_urls || []).map((url: string, index: number) => {
          const label = String.fromCharCode(65 + index)
          return {
            label,
            url,
            text: raw.option_texts?.[index],
            isCorrect: label === raw.correct_answer,
            isUserAnswer: label === normalizedAnswer && label !== raw.correct_answer,
          }
        }),
      },
    }
  }

  if (partKey === 'part2') {
    const raw = getPart2RawData(questionNum)
    if (!raw) return null
    return {
      id: `full-${partKey}-${questionNum}`,
      questionNumber: questionNum,
      partKey,
      title: `題目 ${questionNum}`,
      isCorrect,
      userAnswer: normalizedAnswer,
      correctAnswer: raw.correct_answer,
      explanation: explanations.value.get(questionNum)?.explanation,
      canGenerateExplanation: true,
      isGenerating: generatingExplanation.value.get(questionNum) || false,
      media: {
        audioLabel: '問題',
        audioUrl: raw.question_audio_url,
        audioText: raw.question_text,
        audioOptions: (raw.option_audio_urls || []).map((url: string, index: number) => {
          const label = String.fromCharCode(65 + index)
          return {
            label,
            url,
            text: raw.option_texts?.[index],
            isCorrect: label === raw.correct_answer,
            isUserAnswer: label === normalizedAnswer && label !== raw.correct_answer,
          }
        }),
      },
    }
  }

  if (partKey === 'part3') {
    const raw = getPart3RawGroup(questionNum)
    const current = questionData
    if (!raw || !current) return null

    const child: ExplanationChildItem = {
      id: `full-${partKey}-${questionNum}-1`,
      index: 1,
      questionText: current.question_text || '',
      userAnswer: normalizedAnswer,
      correctAnswer: current.correct_answer,
      isCorrect,
      options: buildOptionItems(current.options, current.correct_answer, normalizedAnswer),
      explanation: explanations.value.get(questionNum)?.explanation,
    }

    return {
      id: `full-${partKey}-${questionNum}`,
      questionNumber: questionNum,
      partKey,
      title: `對話 ${questionNum}`,
      isCorrect,
      canGenerateExplanation: true,
      isGenerating: generatingExplanation.value.get(questionNum) || false,
      media: raw.subIndex === 0 ? {
        audioLabel: '對話音檔',
        audioUrl: raw.group?.conversation_audio_url,
        transcript: raw.group?.transcript,
      } : undefined,
      children: [child],
    }
  }

  if (partKey === 'part4') {
    const raw = getPart4RawGroup(questionNum)
    const current = questionData
    if (!raw || !current) return null

    const child: ExplanationChildItem = {
      id: `full-${partKey}-${questionNum}-1`,
      index: 1,
      questionText: current.question_text || '',
      userAnswer: normalizedAnswer,
      correctAnswer: current.correct_answer,
      isCorrect,
      options: buildOptionItems(current.options, current.correct_answer, normalizedAnswer),
      explanation: explanations.value.get(questionNum)?.explanation,
    }

    return {
      id: `full-${partKey}-${questionNum}`,
      questionNumber: questionNum,
      partKey,
      title: `獨白 ${questionNum}`,
      isCorrect,
      canGenerateExplanation: true,
      isGenerating: generatingExplanation.value.get(questionNum) || false,
      media: raw.subIndex === 0 ? {
        audioLabel: '獨白音檔',
        audioUrl: raw.group?.talk_audio_url,
        transcript: raw.group?.transcript,
      } : undefined,
      children: [child],
    }
  }

  if (!questionData) return null

  return {
    id: `full-${partKey}-${questionNum}`,
    questionNumber: questionNum,
    partKey,
    title: `題目 ${questionNum}`,
    isCorrect,
    userAnswer: normalizedAnswer,
    correctAnswer: questionData.correct_answer,
    explanation: explanations.value.get(questionNum)?.explanation,
    canGenerateExplanation: true,
    isGenerating: generatingExplanation.value.get(questionNum) || false,
    passage: questionData.passage,
    passages: questionData.passages,
    questionText: questionData.question_text?.startsWith('Part ') ? '' : questionData.question_text,
    blankPosition: (questionData as any)?.blank_position ?? null,
    options: buildOptionItems(questionData.options, questionData.correct_answer, normalizedAnswer),
  }
}

const explanationSections = computed(() => {
  return activeParts.value.map(part => ({
    ...part,
    items: getPartQuestions(part)
      .map(questionNum => buildFullTestExplanationItem(questionNum))
      .filter((item): item is ExplanationItem => item !== null),
  }))
})

const totalExplainableQuestions = computed(() => {
  return activeParts.value.reduce((sum, part) => sum + part.count, 0)
})

// 取得聽力各 Part 的原始題目資料（用於詳解頁面顯示音檔/圖片）
function getPart1RawData(questionNum: number): any {
  if (!testData.value) return null
  const part = activeParts.value.find(p => p.key === 'part1')
  if (!part) return null
  return (testData.value as any).part1_questions?.[questionNum - part.start] || null
}

function getPart2RawData(questionNum: number): any {
  if (!testData.value) return null
  const part = activeParts.value.find(p => p.key === 'part2')
  if (!part) return null
  return (testData.value as any).part2_questions?.[questionNum - part.start] || null
}

function getPart3RawGroup(questionNum: number): { group: any; subIndex: number } | null {
  if (!testData.value) return null
  const part = activeParts.value.find(p => p.key === 'part3')
  if (!part) return null
  const localIndex = questionNum - part.start
  const group = (testData.value as any).part3_questions?.[Math.floor(localIndex / 3)]
  if (!group) return null
  return { group, subIndex: localIndex % 3 }
}

function getPart4RawGroup(questionNum: number): { group: any; subIndex: number } | null {
  if (!testData.value) return null
  const part = activeParts.value.find(p => p.key === 'part4')
  if (!part) return null
  const localIndex = questionNum - part.start
  const group = (testData.value as any).part4_questions?.[Math.floor(localIndex / 3)]
  if (!group) return null
  return { group, subIndex: localIndex % 3 }
}

// 滾動到指定 Part
function scrollToPart(partKey: string) {
  const element = document.getElementById(`part-${partKey}`)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

// 計時器
function startTimer() {
  if (timerInterval) clearInterval(timerInterval)
  timeElapsed.value = 0
  timerInterval = setInterval(() => {
    timeElapsed.value++
  }, 1000)
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
}

function formatTimeSeconds(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// 重新測驗（保留題目與詳解，清空作答，原地覆寫同一筆記錄）
function retakeTest() {
  if (!testData.value) return

  stopTimer()

  // 清空作答與生成中狀態；詳解保留
  answers.value.clear()
  generatingExplanation.value.clear()

  // 重置測驗狀態
  globalQuestionNumber.value = 1
  currentPart.value = testType.value === 'listening' ? 'part1' : 'part5'
  timeElapsed.value = 0

  // 原地重置同一筆記錄：清除成績，保留題目與現有詳解
  const log = testLogs.value.find(l => l.id === currentLogId.value)
  if (log) {
    log.score = undefined
    log.answers = new Map()
    log.explanations = new Map(explanations.value)
    log.timeElapsed = 0
    saveTestLogs()
  }

  stage.value = 'quiz'
  startTimer()

}

// PDF 匯出
const exporting = ref(false)

async function exportPDF() {
  if (!testData.value) return
  await _doExportPDF('both', testData.value)
}

// 從側邊欄直接匯出特定 log 的 PDF（自動從後端載入資料，不關閉側邊欄）
async function exportPDFForLog(log: TestLog) {
  if (exporting.value) return

  let data: FullTestResponse | null = log.testData

  if (!data && log.backendLogId) {
    try {
      const backendLog = await toeicAPI.getQuizLog(log.backendLogId)
      if (backendLog.payload) {
        data = backendLog.payload as FullTestResponse
        log.testData = data
      }
    } catch {
      toast.error('載入測驗資料失敗')
      return
    }
  }

  if (!data) { toast.error('無法取得測驗資料'); return }
  await _doExportPDF('both', data)
}

async function handleSidebarSelectLog(item: UnifiedSidebarLog) {
  if (item.source === 'full_test') {
    const log = testLogs.value.find(entry => entry.id === item.id)
    if (!log) {
      toast.error('找不到模擬測驗記錄')
      return
    }
    await loadTestLog(log)
    return
  }

  await router.push({
    name: 'quiz',
    query: {
      [SIDEBAR_QUERY_SOURCE]: 'quiz',
      [SIDEBAR_QUERY_ID]: item.id,
    },
  })
}

async function handleSidebarExportPdf(item: UnifiedSidebarLog) {
  if (item.source !== 'full_test') return

  const log = testLogs.value.find(entry => entry.id === item.id)
  if (!log) {
    toast.error('找不到模擬測驗記錄')
    return
  }

  await exportPDFForLog(log)
}

async function consumePendingSidebarSelection() {
  const source = route.query[SIDEBAR_QUERY_SOURCE]
  const id = route.query[SIDEBAR_QUERY_ID]

  if (source !== 'full_test' || typeof id !== 'string') return

  const log = testLogs.value.find(entry => entry.id === id)
  if (!log) return

  await loadTestLog(log)

  const nextQuery = { ...route.query }
  delete nextQuery[SIDEBAR_QUERY_SOURCE]
  delete nextQuery[SIDEBAR_QUERY_ID]
  await router.replace({ query: nextQuery })
}

async function _doExportPDF(mode: 'questions_only' | 'answer_key' | 'both', data: FullTestResponse) {
  exporting.value = true
  try {
    const blob = await toeicAPI.exportPDF({
      test_data: data,
      export_mode: mode,
      include_user_answers: false
    })
    const isZip = mode === 'both'
    const ext = isZip ? 'zip' : 'pdf'
    const date = new Date().toISOString().slice(0, 10)
    const filename = isZip ? `TOEIC_Export_${date}.zip` : `TOEIC_${mode}_${date}.pdf`
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (error: any) {
    console.error('匯出 PDF 失敗:', error)
    toast.error('匯出失敗')
  } finally {
    exporting.value = false
  }
}


// 生命週期
onMounted(() => {
  // 載入測驗記錄與資料夾
  loadTestLogs()
  loadFolders()
  loadQuizSidebarLogs()
  window.addEventListener(SIDEBAR_DATA_UPDATED_EVENT, handleSidebarDataUpdated)
  consumePendingSidebarSelection()

  // 檢查是否有尚未完成的測驗生成任務
  const raw = localStorage.getItem(CURRENT_JOB_KEY)
  if (raw) {
    try {
      const saved = JSON.parse(raw) as { jobId: string; testType: TestType; config: any }
      if (saved.jobId && saved.testType) {
        testJobId.value = saved.jobId
        testType.value = saved.testType
        stage.value = 'generating'
        generating.value = true

        // 先全部設為 pending，實際狀態由下一次輪詢更新
        Object.keys(generatingProgress.value).forEach(key => {
          generatingProgress.value[key as keyof typeof generatingProgress.value] = 'pending'
        })

        startStatusPolling()
      }
    } catch {
      localStorage.removeItem(CURRENT_JOB_KEY)
      notifyJobUpdated()
    }
  }
})

onBeforeUnmount(() => {
  stopTimer()
  window.removeEventListener(SIDEBAR_DATA_UPDATED_EVENT, handleSidebarDataUpdated)
})

watch(
  () => [route.query[SIDEBAR_QUERY_SOURCE], route.query[SIDEBAR_QUERY_ID], testLogs.value.length] as const,
  () => {
    consumePendingSidebarSelection()
  }
)
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-gray-900 dark:via-blue-900/20 dark:to-purple-900/20">
    <UnifiedTestSidebar
      v-model:open="sidebarOpen"
      :logs="sidebarLogs"
      :visible-logs="visibleSidebarLogs"
      :folders="quizFolders"
      :selected-folder-id="selectedFolderId"
      :active-log-key="activeSidebarLogKey"
      :exporting="exporting"
      @select-folder="selectedFolderId = $event"
      @select-log="handleSidebarSelectLog"
      @request-create-folder="openAddFolderDialog"
      @request-edit-folder="openEditFolderDialog"
      @request-delete-folder="deleteFolder($event.id, $event.name)"
      @request-move-log="openMoveDialog"
      @request-delete-log="confirmDeleteTestLog"
      @export-pdf="handleSidebarExportPdf"
      @move-log-to-folder="onSidebarMoveLogToFolder"
      @reorder-logs="onSidebarReorderLogs"
    />

        <!-- 配置頁面 -->
    <div v-if="stage === 'config'" class="max-w-5xl mx-auto px-4 py-8">
      <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8">
        <div class="text-center mb-8">
          <h1 class="text-3xl md:text-4xl font-black bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 bg-clip-text text-transparent mb-2">
            TOEIC 模擬測驗
          </h1>
          <p class="text-sm md:text-base font-semibold text-gray-600 dark:text-gray-400">
            選擇測驗類型開始練習
          </p>
        </div>

        <!-- 測驗類型選擇 -->
        <div class="mb-8">
          <h2 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">選擇測驗類型</h2>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- 聽力測驗卡片 -->
            <button
              @click="testType = 'listening'"
              :class="[
                'group relative overflow-hidden rounded-2xl p-8 transition-all duration-300 border-2',
                testType === 'listening'
                  ? 'border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/30 dark:to-indigo-900/30 shadow-lg scale-105'
                  : 'border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600 hover:shadow-md'
              ]"
            >
              <div class="text-center">
                <div class="text-5xl mb-4">🎧</div>
                <h3 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">聽力測驗</h3>
                <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">Part 1-4 • 100 題 • 45 分鐘</p>
                <div class="text-xs text-gray-500 dark:text-gray-500 space-y-1">
                  <div>照片描述 • 應答問題</div>
                  <div>簡短對話 • 簡短獨白</div>
                </div>
              </div>
              <div v-if="testType === 'listening'" class="absolute top-4 right-4">
                <span class="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-500 text-white">✓</span>
              </div>
            </button>

            <!-- 閱讀測驗卡片 -->
            <button
              @click="testType = 'reading'"
              :class="[
                'group relative overflow-hidden rounded-2xl p-8 transition-all duration-300 border-2',
                testType === 'reading'
                  ? 'border-purple-500 bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-900/30 dark:to-pink-900/30 shadow-lg scale-105'
                  : 'border-gray-200 dark:border-gray-700 hover:border-purple-300 dark:hover:border-purple-600 hover:shadow-md'
              ]"
            >
              <div class="text-center">
                <div class="text-5xl mb-4">📖</div>
                <h3 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">閱讀測驗</h3>
                <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">Part 5-7 • 100 題 • 75 分鐘</p>
                <div class="text-xs text-gray-500 dark:text-gray-500 space-y-1">
                  <div>句子填空 • 段落填空</div>
                  <div>單篇閱讀 • 多篇閱讀</div>
                </div>
              </div>
              <div v-if="testType === 'reading'" class="absolute top-4 right-4">
                <span class="inline-flex items-center justify-center w-8 h-8 rounded-full bg-purple-500 text-white">✓</span>
              </div>
            </button>
          </div>
        </div>

        <!-- 配置選項（選擇測驗類型後顯示）-->
        <div v-if="testType" class="space-y-6">
          <!-- 難度 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              難度
            </label>
            <div class="flex gap-3">
              <button
                v-for="level in ['easy', 'medium', 'hard']"
                :key="level"
                @click="config.difficulty = level as any"
                :class="[
                  'flex-1 px-4 py-3 rounded-lg font-medium transition-all',
                  config.difficulty === level
                    ? 'bg-blue-600 text-white shadow-lg'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                ]"
              >
                {{ level === 'easy' ? '簡單' : level === 'medium' ? '中等' : '困難' }}
              </button>
            </div>
          </div>

          <!-- 配置說明 -->
          <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <p class="text-sm text-blue-800 dark:text-blue-200">
              ℹ️ 測驗配置說明<br>
              • <strong>AI 模型</strong>：使用 Gemini（題目生成、圖片生成、語音合成）<br>
              • 生成時間：{{ testType === 'listening' ? '10-15 分鐘' : '5-10 分鐘' }}<br>
              <span class="text-xs">💡 如需修改 API 配置，請前往「設定」頁面</span>
            </p>
          </div>

          <!-- 生成按鈕 -->
          <button
            @click="generateTest"
            :disabled="generating"
            class="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-semibold py-4 px-6 rounded-xl shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ generating ? '生成中...' : `開始生成${testType === 'listening' ? '聽力' : '閱讀'}測驗` }}
          </button>
        </div>
      </div>
    </div>

    <!-- 生成中頁面 -->
    <div v-else-if="stage === 'generating'" class="max-w-4xl mx-auto px-4 py-8">
      <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8">
        <h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          正在生成{{ testType === 'listening' ? '聽力' : '閱讀' }}測驗...
        </h2>

        <!-- 整體進度條 -->
        <div class="mb-6">
          <div class="flex justify-between items-center mb-1">
            <span class="text-sm text-gray-500 dark:text-gray-400">整體進度</span>
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">
              {{ overallProgress.completed }} / {{ overallProgress.total }} 大題完成
            </span>
          </div>
          <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 overflow-hidden">
            <div
              class="h-3 rounded-full transition-all duration-500"
              :class="overallProgress.pct === 100 ? 'bg-green-500' : 'bg-blue-500'"
              :style="{ width: overallProgress.pct + '%' }"
            ></div>
          </div>
        </div>

        <div class="space-y-4">
          <div
            v-for="part in (testType === 'listening' ? partInfo.slice(0, 4) : partInfo.slice(4))"
            :key="part.key"
            :class="[
              'p-4 rounded-lg transition-all',
              generatingProgress[part.key as keyof typeof generatingProgress] === 'completed'
                ? 'bg-green-50 dark:bg-green-900/20 border-2 border-green-200 dark:border-green-800'
                : generatingProgress[part.key as keyof typeof generatingProgress] === 'generating'
                ? 'bg-blue-50 dark:bg-blue-900/20 border-2 border-blue-200 dark:border-blue-800'
                : generatingProgress[part.key as keyof typeof generatingProgress] === 'error'
                ? 'bg-red-50 dark:bg-red-900/20 border-2 border-red-200 dark:border-red-800'
                : 'bg-gray-50 dark:bg-gray-700'
            ]"
          >
            <div class="flex items-center gap-4">
              <!-- 狀態圖標 -->
              <div class="flex-shrink-0 w-8 h-8 flex items-center justify-center">
                <span v-if="generatingProgress[part.key as keyof typeof generatingProgress] === 'completed'" class="text-green-500 text-2xl">✅</span>
                <span v-else-if="generatingProgress[part.key as keyof typeof generatingProgress] === 'generating'" class="text-blue-500">
                  <svg class="animate-spin h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                </span>
                <span v-else-if="generatingProgress[part.key as keyof typeof generatingProgress] === 'error'" class="text-red-500 text-2xl">❌</span>
                <span v-else class="text-gray-400 text-2xl">⏳</span>
              </div>

              <!-- Part 資訊 -->
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between">
                  <span class="font-medium text-gray-900 dark:text-white">{{ part.name }}</span>
                  <span
                    :class="[
                      'text-sm font-medium',
                      generatingProgress[part.key as keyof typeof generatingProgress] === 'completed' ? 'text-green-600 dark:text-green-400' :
                      generatingProgress[part.key as keyof typeof generatingProgress] === 'generating' ? 'text-blue-600 dark:text-blue-400' :
                      generatingProgress[part.key as keyof typeof generatingProgress] === 'error' ? 'text-red-600 dark:text-red-400' :
                      'text-gray-400 dark:text-gray-500'
                    ]"
                  >
                    <template v-if="generatingProgress[part.key as keyof typeof generatingProgress] === 'completed'">完成</template>
                    <template v-else-if="generatingProgress[part.key as keyof typeof generatingProgress] === 'generating'">
                      {{ (partIndexMap[part.key] ?? 0) }} / {{ PART_TOTALS[part.key] }}
                    </template>
                    <template v-else-if="generatingProgress[part.key as keyof typeof generatingProgress] === 'error'">失敗</template>
                    <template v-else>等待中</template>
                  </span>
                </div>

                <!-- 每題進度條 -->
                <div class="mt-2 w-full bg-gray-200 dark:bg-gray-600 rounded-full h-1.5 overflow-hidden">
                  <div
                    class="h-1.5 rounded-full transition-all duration-300"
                    :class="
                      generatingProgress[part.key as keyof typeof generatingProgress] === 'completed' ? 'bg-green-500' :
                      generatingProgress[part.key as keyof typeof generatingProgress] === 'error' ? 'bg-red-500' :
                      'bg-blue-500'
                    "
                    :style="{ width: getPartProgressPct(part.key) + '%' }"
                  ></div>
                </div>
              </div>

              <div v-if="generatingProgress[part.key as keyof typeof generatingProgress] === 'error'" class="flex-shrink-0">
                <span class="text-xs text-red-600 dark:text-red-400">待接續</span>
              </div>
            </div>
          </div>
        </div>

        <div class="mt-6 text-center">
          <div class="text-sm text-gray-500 dark:text-gray-400 mb-4">
            請稍候，預計需要 {{ testType === 'listening' ? '10-15' : '5-10' }} 分鐘...
          </div>
          <div class="flex items-center justify-center gap-3 flex-wrap">
            <button
              v-if="hasGenerationError || isPaused"
              @click="hasGenerationError ? resumeFullTest() : resumePolling()"
              :disabled="generating && !isPaused && !hasGenerationError"
              class="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              接續生成
            </button>
            <button
              v-if="!isPaused && !hasGenerationError"
              @click="pauseGeneration"
              class="px-5 py-2.5 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium transition-colors"
            >
              暫停生成
            </button>
            <button
              @click="leaveGenerating"
              class="px-5 py-2.5 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 rounded-lg text-sm font-medium transition-colors"
            >
              離開（可從記錄切回）
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 作答頁面 -->
    <div v-else-if="stage === 'quiz'" class="flex h-screen pt-16 bg-gray-50 dark:bg-gray-900">
      <!-- 左側 Part 導航 -->
      <div v-show="showSidebar" class="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 overflow-y-auto">
        <div class="p-4">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-semibold text-gray-900 dark:text-white">測驗導航</h3>
            <button @click="showSidebar = false" class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
              <
            </button>
          </div>

          <!-- 計時器 -->
          <div v-if="showTimer" class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 mb-4">
            <div class="text-sm text-blue-600 dark:text-blue-400 mb-1">已用時間</div>
            <div class="text-2xl font-mono font-bold text-blue-900 dark:text-blue-100">
              {{ formatTimeSeconds(timeElapsed) }}
            </div>
          </div>

          <!-- 進度 -->
          <div class="mb-4">
            <div class="flex justify-between text-sm mb-1">
              <span class="text-gray-600 dark:text-gray-400">總進度</span>
              <span class="font-semibold text-gray-900 dark:text-white">{{ progress.answered }}/{{ progress.total }}</span>
            </div>
            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div class="bg-blue-600 h-2 rounded-full transition-all" :style="{ width: progress.percentage + '%' }"></div>
            </div>
          </div>

          <!-- Part 列表 -->
          <div class="space-y-2">
            <button
              v-for="part in partProgress"
              :key="part.key"
              @click="goToPart(part.key)"
              :class="[
                'w-full text-left p-3 rounded-lg transition-all',
                currentPart === part.key
                  ? 'bg-blue-100 dark:bg-blue-900/30 border-2 border-blue-500'
                  : 'bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600'
              ]"
            >
              <div class="font-medium text-sm text-gray-900 dark:text-white mb-1">
                {{ part.name }}
              </div>
              <div class="flex items-center gap-2">
                <div class="flex-1 bg-gray-200 dark:bg-gray-600 rounded-full h-1.5">
                  <div class="bg-blue-600 h-1.5 rounded-full transition-all" :style="{ width: part.percentage + '%' }"></div>
                </div>
                <span class="text-xs text-gray-600 dark:text-gray-400">{{ part.answered }}/{{ part.count }}</span>
              </div>
            </button>
          </div>
        </div>
      </div>

      <!-- 主要作答區 -->
      <div class="flex-1 overflow-y-auto">
        <div class="max-w-4xl mx-auto p-6">
          <!-- 頂部工具列 -->
          <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 mb-6 flex items-center justify-between">
            <div class="flex items-center gap-4">
              <button v-if="!showSidebar" @click="showSidebar = true" class="px-3 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600">
                🧭 導航
              </button>
              <span class="text-lg font-semibold text-gray-900 dark:text-white">
                題號 {{ globalQuestionNumber }} / 100
              </span>
              <span class="text-sm text-gray-600 dark:text-gray-400">
                {{ currentPartInfo?.name }}
              </span>
            </div>
            <div class="flex items-center gap-2">
              <button @click="showAnswerSheet = !showAnswerSheet" class="px-3 py-2 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-lg hover:bg-blue-200 dark:hover:bg-blue-900/50">
                {{ showAnswerSheet ? '隱藏' : '顯示' }}答題卡
              </button>
              <button @click="submitTest" class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium">
                提交測驗
              </button>
            </div>
          </div>

          <!-- 題目內容區 -->
          <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
            <!-- 這裡需要根據不同 Part 顯示不同的題目格式 -->
            <div v-if="currentQuestion" class="prose dark:prose-invert max-w-none">

              <!-- Part 1: 照片描述 -->
              <template v-if="currentPart === 'part1'">
                <div class="mb-6">
                  <p class="font-semibold text-gray-900 dark:text-white mb-4">{{ globalQuestionNumber }}. 請點擊選項按鈕播放音檔，選擇最符合照片的描述</p>

                  <!-- 圖片顯示 -->
                  <div v-if="(currentQuestion as any).image_url" class="mb-6 flex justify-center">
                    <img
                      :src="(currentQuestion as any).image_url"
                      :alt="`Question ${globalQuestionNumber}`"
                      class="max-w-lg rounded-lg shadow-lg"
                    />
                  </div>

                  <!-- 選項 (A/B/C/D) with audio players -->
                  <div v-if="(currentQuestion as any).audio_urls" class="grid grid-cols-2 gap-4">
                    <div
                      v-for="(opt, idx) in ['A', 'B', 'C', 'D']"
                      :key="opt"
                      @click="selectAnswer(opt)"
                      :class="[
                        'p-4 rounded-lg border-2 transition-all cursor-pointer',
                        answers.get(globalQuestionNumber)?.answer === opt
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                          : 'border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600'
                      ]"
                    >
                      <!-- 選項標籤和音檔播放器 -->
                      <div class="flex flex-col gap-2">
                        <span class="text-xl font-semibold text-gray-700 dark:text-gray-300">{{ opt }}</span>
                        <audio controls class="w-full" :key="(currentQuestion as any).audio_urls[idx]" @click.stop>
                          <source :src="(currentQuestion as any).audio_urls[idx]">
                        </audio>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- Part 2: 應答問題 -->
              <template v-else-if="currentPart === 'part2'">
                <div class="mb-6">
                  <p class="font-semibold text-gray-900 dark:text-white mb-4">{{ globalQuestionNumber }}. 請先聽問題，再點擊選項播放回應</p>

                  <!-- 問題音檔播放器 -->
                  <div v-if="(currentQuestion as any).question_audio_url" class="mb-6 bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg">
                    <div class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">🎧 問題音檔</div>
                    <audio controls class="w-full">
                      <source :src="(currentQuestion as any).question_audio_url">
                    </audio>
                  </div>

                  <!-- 選項 (A/B/C) with audio players -->
                  <div v-if="(currentQuestion as any).option_audio_urls" class="grid grid-cols-3 gap-4">
                    <div
                      v-for="(opt, idx) in ['A', 'B', 'C']"
                      :key="opt"
                      @click="selectAnswer(opt)"
                      :class="[
                        'p-4 rounded-lg border-2 transition-all cursor-pointer',
                        answers.get(globalQuestionNumber)?.answer === opt
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                          : 'border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600'
                      ]"
                    >
                      <!-- 選項標籤和音檔播放器 -->
                      <div class="flex flex-col gap-2">
                        <span class="text-2xl font-semibold text-gray-700 dark:text-gray-300">{{ opt }}</span>
                        <audio controls class="w-full" :key="(currentQuestion as any).option_audio_urls[idx]" @click.stop>
                          <source :src="(currentQuestion as any).option_audio_urls[idx]">
                        </audio>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- Part 3: 簡短對話 -->
              <template v-else-if="currentPart === 'part3'">
                <div class="mb-6">
                  <div class="text-center mb-4">
                    <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">請聽對話，回答以下問題</p>
                  </div>

                  <!-- 對話音檔播放器 -->
                  <div v-if="(currentQuestion as any).conversation_audio_url" class="mb-6 bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg">
                    <div class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">🎧 對話音檔</div>
                    <audio controls class="w-full">
                      <source :src="(currentQuestion as any).conversation_audio_url">
                    </audio>
                  </div>

                  <!-- 顯示當前對話組的三個問題 -->
                  <div v-if="(currentQuestion as any).questions" class="space-y-6">
                    <div
                      v-for="(q, idx) in (currentQuestion as any).questions"
                      :key="idx"
                      class="border-l-4 border-blue-500 pl-4"
                    >
                      <div class="font-semibold text-gray-900 dark:text-white mb-3">
                        {{ globalQuestionNumber + Number(idx) }}. {{ q.question_text }}
                      </div>

                      <!-- 選項 -->
                      <div class="space-y-2">
                        <button
                          v-for="option in q.options"
                          :key="option.label"
                          @click="selectAnswer(option.label, Number(idx))"
                          :class="[
                            'w-full text-left p-3 rounded-lg border-2 transition-all',
                            answers.get(globalQuestionNumber + Number(idx))?.answer === option.label
                              ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                              : 'border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600'
                          ]"
                        >
                          <span class="font-semibold">{{ option.label }}.</span> {{ option.text }}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- Part 4: 簡短獨白 -->
              <template v-else-if="currentPart === 'part4'">
                <div class="mb-6">
                  <div class="text-center mb-4">
                    <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">請聽獨白，回答以下問題</p>
                  </div>

                  <!-- 獨白音檔播放器 -->
                  <div v-if="(currentQuestion as any).talk_audio_url" class="mb-6 bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg">
                    <div class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">🎧 獨白音檔</div>
                    <audio controls class="w-full">
                      <source :src="(currentQuestion as any).talk_audio_url">
                    </audio>
                  </div>

                  <!-- 顯示當前獨白組的三個問題 -->
                  <div v-if="(currentQuestion as any).questions" class="space-y-6">
                    <div
                      v-for="(q, idx) in (currentQuestion as any).questions"
                      :key="idx"
                      class="border-l-4 border-purple-500 pl-4"
                    >
                      <div class="font-semibold text-gray-900 dark:text-white mb-3">
                        {{ globalQuestionNumber + Number(idx) }}. {{ q.question_text }}
                      </div>

                      <!-- 選項 -->
                      <div class="space-y-2">
                        <button
                          v-for="option in q.options"
                          :key="option.label"
                          @click="selectAnswer(option.label, Number(idx))"
                          :class="[
                            'w-full text-left p-3 rounded-lg border-2 transition-all',
                            answers.get(globalQuestionNumber + Number(idx))?.answer === option.label
                              ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                              : 'border-gray-200 dark:border-gray-700 hover:border-purple-300 dark:hover:border-purple-600'
                          ]"
                        >
                          <span class="font-semibold">{{ option.label }}.</span> {{ option.text }}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- Part 5/6/7 閱讀題 -->
              <template v-else-if="['part5', 'part6', 'part7_single', 'part7_multiple'].includes(currentPart)">
                <p v-if="readingGroupLabel" class="text-xs text-gray-500 dark:text-gray-400 mb-3">
                  {{ readingGroupLabel }}
                </p>

                <div v-if="currentReadingPassage" class="mb-6 bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                  <MarkdownRenderer :content="currentReadingPassage" :plain-surface="true" />
                </div>

                <div v-if="currentReadingPassages.length > 0" class="mb-6 space-y-3">
                  <div
                    v-for="(passage, index) in currentReadingPassages"
                    :key="`full-passages-${index}`"
                    class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4"
                  >
                      <div class="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">Passage {{ Number(index) + 1 }}</div>
                    <MarkdownRenderer :content="passage" :plain-surface="true" />
                  </div>
                </div>

                <div v-if="currentPart === 'part6' && currentReadingBlankPosition !== null" class="font-semibold text-gray-900 dark:text-white mb-6">
                  {{ globalQuestionNumber }}. (Blank {{ currentReadingBlankPosition }})
                </div>

                <div v-else-if="currentReadingQuestionText" class="font-semibold text-gray-900 dark:text-white mb-6">
                  {{ globalQuestionNumber }}. {{ currentReadingQuestionText }}
                </div>

                <!-- 選項 -->
                <div class="space-y-3">
                  <button
                    v-for="option in (currentQuestion as any).options"
                    :key="option.label"
                    @click="selectAnswer(option.label)"
                    :class="[
                      'w-full text-left p-4 rounded-lg border-2 transition-all',
                      answers.get(globalQuestionNumber)?.answer === option.label
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                        : 'border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600'
                    ]"
                  >
                    <span class="font-semibold">{{ option.label }}.</span> {{ option.text }}
                  </button>
                </div>
              </template>
            </div>
          </div>

          <!-- 導航按鈕 -->
          <div class="flex justify-between">
            <button
              @click="prevQuestion"
              :disabled="globalQuestionNumber === 1"
              class="px-6 py-3 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              < 上一題
            </button>
            <button
              @click="nextQuestion"
              :disabled="globalQuestionNumber === 100"
              class="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              下一題 >
            </button>
          </div>
        </div>
      </div>

      <!-- 右側答題卡 -->
      <div v-show="showAnswerSheet" class="w-80 bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 overflow-y-auto">
        <div class="p-4">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-semibold text-gray-900 dark:text-white">答題卡</h3>
            <button @click="showAnswerSheet = false" class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
              >
            </button>
          </div>

          <div class="grid grid-cols-5 gap-2">
            <button
              v-for="num in 100"
              :key="num"
              @click="goToQuestion(num)"
              :class="[
                'aspect-square flex items-center justify-center rounded text-sm font-medium transition-all',
                num === globalQuestionNumber
                  ? 'bg-blue-600 text-white ring-2 ring-blue-400'
                  : answers.has(num)
                  ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
              ]"
            >
              {{ num }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 結果頁面 -->
    <div v-else-if="stage === 'result'" class="max-w-6xl mx-auto px-4 py-8">
      <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8">
        <h2 class="text-3xl font-bold text-gray-900 dark:text-white mb-8 text-center">
          測驗結果
        </h2>

        <!-- 總分統計 -->
        <div class="bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 p-8 rounded-lg mb-8">
          <div class="text-center mb-6">
            <div class="text-6xl font-bold text-blue-600 dark:text-blue-400 mb-2">
              {{ score.correct }} / {{ score.total }}
            </div>
            <div class="text-2xl text-gray-600 dark:text-gray-400">
              正確率: {{ score.percentage }}%
            </div>
            <div class="text-sm text-gray-500 dark:text-gray-500 mt-2">
              用時: {{ formatTimeSeconds(timeElapsed) }}
            </div>
          </div>

          <!-- 聽力 / 閱讀 成績摘要 -->
          <div :class="testType === 'listening' || testType === 'reading' ? 'grid grid-cols-1' : 'grid grid-cols-2 gap-6'">
            <div v-if="testType === 'listening'" class="bg-white dark:bg-gray-800 rounded-lg p-4">
              <div class="text-center">
                <div class="text-sm text-gray-600 dark:text-gray-400 mb-2">聽力測驗</div>
                <div class="text-3xl font-bold text-blue-600 dark:text-blue-400">
                  {{ score.correct }} / {{ score.total }}
                </div>
                <div class="text-sm text-gray-500 dark:text-gray-500">{{ score.percentage }}%</div>
              </div>
            </div>
            <div v-else-if="testType === 'reading'" class="bg-white dark:bg-gray-800 rounded-lg p-4">
              <div class="text-center">
                <div class="text-sm text-gray-600 dark:text-gray-400 mb-2">閱讀測驗</div>
                <div class="text-3xl font-bold text-purple-600 dark:text-purple-400">
                  {{ score.correct }} / {{ score.total }}
                </div>
                <div class="text-sm text-gray-500 dark:text-gray-500">{{ score.percentage }}%</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 各 Part 詳細成績 -->
        <div class="mb-8">
          <h3 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">各 Part 成績</h3>
          <div class="grid grid-cols-2 gap-4">
            <div v-for="part in score.byPart" :key="part.key" class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
              <div class="flex items-center justify-between mb-2">
                <span class="font-medium text-gray-900 dark:text-white">{{ part.name }}</span>
                <span class="text-lg font-semibold" :class="part.percentage >= 70 ? 'text-green-600 dark:text-green-400' : 'text-orange-600 dark:text-orange-400'">
                  {{ part.percentage }}%
                </span>
              </div>
              <div class="flex items-center gap-2">
                <div class="flex-1 bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                  <div class="bg-blue-600 h-2 rounded-full transition-all" :style="{ width: part.percentage + '%' }"></div>
                </div>
                <span class="text-sm text-gray-600 dark:text-gray-400">{{ part.correct }}/{{ part.total }}</span>
              </div>
            </div>
          </div>
        </div>


        <!-- 操作按鈕 -->
        <div class="grid grid-cols-2 gap-3">
          <button
            @click="viewExplanations"
            class="px-4 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white rounded-lg font-medium transition-all"
          >
            📚 查看詳解
          </button>
          <button
            @click="retakeTest"
            class="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-all"
          >
            🔁 重新測驗
          </button>
        </div>
      </div>
    </div>

    <!-- 詳解頁面 -->
    <div v-else-if="stage === 'explanations'" class="max-w-6xl mx-auto px-4 py-8">
      <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8">
        <!-- 頂部導航 -->
        <div class="flex items-center justify-between mb-6">
          <div>
            <h2 class="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              📚 題目詳解
            </h2>
            <p class="text-sm text-gray-600 dark:text-gray-400">
              已生成 {{ explanations.size }} / {{ totalExplainableQuestions }} 題詳解
            </p>
          </div>
          <button
            @click="stage = 'result'"
            class="px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg font-medium transition-all"
          >
            ← 返回結果
          </button>
        </div>

        <!-- 篩選器 -->
        <div class="mb-6 flex gap-3">
          <button
            v-for="filter in explanationFilters"
            :key="filter.value"
            @click="explanationFilter = filter.value"
            :class="[
              'px-4 py-2 rounded-lg font-medium transition-all',
              explanationFilter === filter.value
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
            ]"
          >
            {{ filter.label }}
          </button>
        </div>

        <!-- Part 導航 -->
        <div class="mb-6 grid grid-cols-4 gap-2">
          <button
            v-for="part in activeParts"
            :key="part.key"
            @click="scrollToPart(part.key)"
            class="px-3 py-2 text-sm bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg transition-all"
          >
            {{ part.name }}
          </button>
        </div>

        <!-- 題目列表 -->
        <div class="space-y-6">
          <div
            v-for="part in explanationSections"
            :key="part.key"
            :id="`part-${part.key}`"
            class="bg-gray-50 dark:bg-gray-700/50 rounded-xl p-6"
          >
            <h3 class="text-xl font-bold text-gray-900 dark:text-white mb-4">
              {{ part.name }} ({{ part.start }}-{{ part.end }})
            </h3>

            <div class="space-y-4">
              <div
                v-for="item in part.items"
                :key="item.id"
              >
                <SharedExplanationCard
                  :item="item"
                  @generate="generateSingleExplanation"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 資料夾 新增/編輯 Dialog -->
    <Teleport to="body">
      <div v-if="showFolderDialog" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4" @click.self="showFolderDialog = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-sm p-6 flex flex-col gap-4">
          <h3 class="text-lg font-bold text-gray-900 dark:text-white">{{ editingFolderId ? '編輯資料夾' : '新增資料夾' }}</h3>
          <div class="flex flex-col gap-2">
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300">名稱</label>
            <input v-model="folderName" type="text" class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-white focus:ring-2 focus:ring-blue-500" placeholder="例如：模擬考、文法練習" @keyup.enter="submitFolder" />
          </div>
          <div class="flex flex-col gap-2">
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300">顏色</label>
            <div class="flex items-center gap-2">
              <input v-model="folderColor" type="color" class="w-10 h-10 rounded cursor-pointer border-0" />
              <input v-model="folderColor" type="text" class="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-white" placeholder="#3B82F6" />
            </div>
          </div>
          <div class="flex gap-3 pt-1">
            <button @click="showFolderDialog = false" class="flex-1 px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition">取消</button>
            <button @click="submitFolder" class="flex-1 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold transition">{{ editingFolderId ? '更新' : '建立' }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 移動到資料夾 Dialog -->
    <Teleport to="body">
      <div v-if="showMoveDialog" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4" @click.self="showMoveDialog = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-sm p-6 flex flex-col gap-3">
          <h3 class="text-lg font-bold text-gray-900 dark:text-white">移動到資料夾</h3>
          <button @click="moveToFolder(null)" class="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition text-left">
            <span>📁</span><span class="text-gray-700 dark:text-gray-300">未分類</span>
          </button>
          <button
            v-for="folder in quizFolders"
            :key="folder.id"
            @click="moveToFolder(folder.id)"
            class="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition text-left"
          >
            <span class="w-3 h-3 rounded-full" :style="{ backgroundColor: folder.color }"></span>
            <span class="text-gray-700 dark:text-gray-300">{{ folder.name }}</span>
          </button>
          <button @click="showMoveDialog = false" class="w-full px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition">取消</button>
        </div>
      </div>
    </Teleport>

    <!-- 刪除確認 Dialog -->
    <Teleport to="body">
      <div v-if="showDeleteConfirm" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4" @click.self="showDeleteConfirm = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-sm p-6 flex flex-col gap-4">
          <div class="flex items-center gap-3">
            <span class="text-3xl">🗑️</span>
            <h3 class="text-lg font-bold text-gray-900 dark:text-white">確認刪除</h3>
          </div>
          <p class="text-sm text-gray-600 dark:text-gray-300">確定要刪除這筆測驗記錄嗎？此操作無法復原。</p>
          <div class="flex gap-3 pt-1">
            <button @click="showDeleteConfirm = false" class="flex-1 px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition">取消</button>
            <button @click="executeDeleteTestLog" class="flex-1 px-4 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-white font-semibold transition">刪除</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- API Key 未設定提醒 Modal -->
    <Teleport to="body">
      <div
        v-if="showApiKeyModal"
        class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4"
        @click.self="showApiKeyModal = false"
      >
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-sm p-6 flex flex-col gap-4">
          <div class="flex items-center gap-3">
            <span class="text-3xl">🔑</span>
            <h3 class="text-lg font-bold text-gray-900 dark:text-white">尚未設定 API Key</h3>
          </div>
          <p class="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
            生成測驗需要 <strong>Gemini API Key</strong>。<br>
            請前往「設定」頁面輸入 API Key 後再開始生成。
          </p>
          <p class="text-xs text-gray-400 dark:text-gray-500">
            可至 <span class="font-mono">aistudio.google.com/app/apikey</span> 免費取得
          </p>
          <div class="flex gap-3 pt-1">
            <button
              @click="showApiKeyModal = false"
              class="flex-1 px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 font-medium hover:bg-gray-50 dark:hover:bg-gray-700 transition"
            >
              關閉
            </button>
            <RouterLink
              to="/settings"
              @click="showApiKeyModal = false"
              class="flex-1 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-center transition"
            >
              前往設定
            </RouterLink>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* 確保滾動流暢 */
.overflow-y-auto {
  scrollbar-width: thin;
  scrollbar-color: rgba(156, 163, 175, 0.5) transparent;
}

.overflow-y-auto::-webkit-scrollbar {
  width: 8px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: transparent;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background-color: rgba(156, 163, 175, 0.5);
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background-color: rgba(156, 163, 175, 0.7);
}
</style>
