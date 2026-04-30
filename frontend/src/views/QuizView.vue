<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toeicAPI, listeningAPI } from '@/services/api'
import { useSettingsStore } from '@/stores/settings'
import type { TOEICQuestion, TOEICExplanation, Part1Question, Part2Question, Part3Question, Part4Question, QuizLogSummary } from '@/types'
import { useToast } from '@/composables/useToast'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import SharedExplanationCard from '@/components/SharedExplanationCard.vue'
import UnifiedTestSidebar from '@/components/UnifiedTestSidebar.vue'
import type { ExplanationChildItem, ExplanationItem, ExplanationOptionItem, ExplanationPartKey } from '@/types/explanations'
import type { FullTestSidebarLogSnapshot, SidebarFolderId, UnifiedSidebarLog } from '@/utils/testHistory'
import { SIDEBAR_DATA_UPDATED_EVENT, buildSidebarLogKey, formatDifficultyLabel, isQuizBackendLog, mergeFullTestSidebarLogs, notifySidebarDataUpdated, readFullTestSidebarLogs, readRawFullTestLogs, writeRawFullTestLogs } from '@/utils/testHistory'

const route = useRoute()
const router = useRouter()
const settingsStore = useSettingsStore()
const toast = useToast()

// 測驗模式（8種題型）
const testMode = ref<'part1' | 'part2' | 'part3' | 'part4' | 'part5' | 'part6' | 'part7_single' | 'part7_multiple'>('part1')

// 測驗狀態
const stage = ref<'config' | 'generating' | 'quiz' | 'result' | 'explanations'>('config')
const questions = ref<TOEICQuestion[]>([])
const part1Questions = ref<Part1Question[]>([])
const part2Questions = ref<Part2Question[]>([])
const part3Questions = ref<Part3Question[]>([])
const part4Questions = ref<Part4Question[]>([])
const userAnswers = ref<Record<number, string>>({}) // question_number -> answer
const part3Answers = ref<Record<number, string[]>>({}) // Part 3: question_number -> [answer1, answer2, answer3]
const part4Answers = ref<Record<number, string[]>>({}) // Part 4: question_number -> [answer1, answer2, answer3]
const explanations = ref<TOEICExplanation[]>([])
const currentQuestionIndex = ref(0)

// 統一配置（所有題型只需要題數和難度）
const config = ref({
  count: 10,
  difficulty: 'medium' as 'easy' | 'medium' | 'hard',
  // 聽力專用設定
  accent: null as string | null,  // null 表示隨機
  pace: 'moderate' as string
})

// 口音選項
const ACCENT_OPTIONS = [
  { label: '隨機', value: null },
  { label: '美式', value: 'American English accent' },
  { label: '英式', value: 'British English accent' },
  { label: '加拿大', value: 'Canadian English accent' },
  { label: '澳洲', value: 'Australian English accent' }
]

// 語速選項
const PACE_OPTIONS = [
  { label: '非常慢', value: 'very slow' },
  { label: '慢速', value: 'slow' },
  { label: '正常', value: 'moderate' },
  { label: '快速', value: 'fast' },
  { label: '非常快', value: 'very fast' }
]

// 判斷是否為聽力題型
const isListeningMode = computed(() => {
  return ['part1', 'part2', 'part3', 'part4'].includes(testMode.value)
})

// 載入狀態
const generating = ref(false)
const submitting = ref(false)
const loadingExplanations = ref(false)

const generatingExplanation = ref<Record<number | string, boolean>>({})
const explanationFilter = ref<'all' | 'incorrect' | 'correct'>('all')

const QUIZ_JOB_KEY = 'toeic_quiz_job_v1'
const quizJobId = ref<string | null>(null)
const quizJobKind = ref<'listening' | 'reading' | null>(null)
const quizJobMode = ref<'part1' | 'part2' | 'part3' | 'part4' | 'part5' | 'part6' | 'part7_single' | 'part7_multiple' | null>(null)
const quizJobHandled = ref(false)
let quizStatusTimer: number | null = null

const quizJobProgress = ref<{ generated: number; total: number } | null>(null)
const quizJobHasError = ref(false)
const quizJobErrorMsg = ref('')

// 音訊播放狀態
const audioPlaying = ref(false)
const currentAudio = ref<HTMLAudioElement | null>(null)

function getMediaConfig() {
  const mediaProvider = 'gemini' as const
  const mediaModel = settingsStore.settings.defaultModel || 'gemini-2.5-flash'
  const mediaApiKey = settingsStore.settings.apiKeys.gemini
  return { mediaProvider, mediaModel, mediaApiKey }
}

function getListeningConfig() {
  const textProvider = 'gemini' as const  // 固定使用 Gemini
  const textModel = settingsStore.settings.defaultModel || 'gemini-2.5-flash'
  const textApiKey = settingsStore.settings.apiKeys.gemini
  const { mediaProvider, mediaModel, mediaApiKey } = getMediaConfig()
  return {
    textProvider,
    textModel,
    textApiKey,
    ttsProvider: mediaProvider,
    ttsModel: mediaModel,
    ttsApiKey: mediaApiKey
  }
}

function saveQuizJob(jobId: string, kind: 'listening' | 'reading', mode: typeof testMode.value) {
  localStorage.setItem(
    QUIZ_JOB_KEY,
    JSON.stringify({
      jobId,
      kind,
      mode,
      config: {
        count: config.value.count,
        difficulty: config.value.difficulty
      },
      savedAt: new Date().toISOString()
    })
  )
}

function clearQuizJob() {
  localStorage.removeItem(QUIZ_JOB_KEY)
  quizJobId.value = null
  quizJobKind.value = null
  quizJobMode.value = null
  quizJobHandled.value = false
  quizJobProgress.value = null
  quizJobHasError.value = false
  quizJobErrorMsg.value = ''
}

function leaveQuizGenerating() {
  stopQuizStatusPolling()
  generating.value = false
  quizJobHasError.value = false
  quizJobErrorMsg.value = ''
  stage.value = 'config'
  // 保留 localStorage job，下次開啟會自動接續
}

async function retryQuizGeneration() {
  const mode = quizJobMode.value
  clearQuizJob()
  quizJobHasError.value = false
  quizJobErrorMsg.value = ''
  if (!mode) { stage.value = 'config'; return }
  testMode.value = mode
  if (mode === 'part1') await generatePart1Quiz()
  else if (mode === 'part2') await generatePart2Quiz()
  else if (mode === 'part3') await generatePart3Quiz()
  else if (mode === 'part4') await generatePart4Quiz()
  else if (mode === 'part5') await generateReadingQuiz('sentence')
  else if (mode === 'part6') await generateReadingQuiz('paragraph')
  else if (mode === 'part7_single') await generateReadingQuiz('single_passage')
  else if (mode === 'part7_multiple') await generateReadingQuiz('multiple_passage')
}

function stopQuizStatusPolling() {
  if (quizStatusTimer !== null) {
    window.clearInterval(quizStatusTimer)
    quizStatusTimer = null
  }
}

function startQuizStatusPolling() {
  stopQuizStatusPolling()
  checkQuizJobStatus()
  quizStatusTimer = window.setInterval(checkQuizJobStatus, 5000)
}

function applyQuizResult(mode: typeof testMode.value, payload: { questions: any[] }) {
  if (mode === 'part1') {
    part1Questions.value = payload.questions
    userAnswers.value = {}
    currentQuestionIndex.value = 0
  } else if (mode === 'part2') {
    part2Questions.value = payload.questions
    userAnswers.value = {}
    currentQuestionIndex.value = 0
  } else if (mode === 'part3') {
    part3Questions.value = payload.questions
    part3Answers.value = {}
    currentQuestionIndex.value = 0
  } else if (mode === 'part4') {
    part4Questions.value = payload.questions
    part4Answers.value = {}
    currentQuestionIndex.value = 0
  } else {
    questions.value = payload.questions
    userAnswers.value = {}
    explanations.value = []
    currentQuestionIndex.value = 0
    currentGroupIndex.value = 0
  }
}

async function checkQuizJobStatus() {
  if (!quizJobId.value || !quizJobKind.value || !quizJobMode.value) return
  if (quizJobHandled.value) return

  try {
    const status =
      quizJobKind.value === 'listening'
        ? await listeningAPI.getListeningJobStatus(quizJobId.value)
        : await toeicAPI.getReadingJobStatus(quizJobId.value)

    if (status.progress) {
      quizJobProgress.value = status.progress as { generated: number; total: number }
    }

    if (status.status === 'completed') {
      quizJobHandled.value = true
      const result =
        quizJobKind.value === 'listening'
          ? await listeningAPI.getListeningJobResult(quizJobId.value)
          : await toeicAPI.getReadingJobResult(quizJobId.value)

      testMode.value = quizJobMode.value
      applyQuizResult(quizJobMode.value, result as any)

      const typeNames = {
        part1: '照片描述',
        part2: '應答問題',
        part3: '簡短對話',
        part4: '簡短獨白',
        part5: '句子填空',
        part6: '段落填空',
        part7_single: '單篇閱讀',
        part7_multiple: '多篇閱讀'
      }

      stopQuizStatusPolling()
      generating.value = false
      stage.value = 'quiz'
      await addQuizLog(typeNames[quizJobMode.value])
      await updateCurrentQuizLog()
      clearQuizJob()
      return
    }

    if (status.status === 'error') {
      quizJobHandled.value = true
      stopQuizStatusPolling()
      generating.value = false
      quizJobHasError.value = true
      quizJobErrorMsg.value = status.message || '生成失敗，請重試'
    }
  } catch (error: any) {
    const statusCode = error?.response?.status
    if (statusCode === 404) {
      stopQuizStatusPolling()
      generating.value = false
      quizJobHasError.value = true
      quizJobErrorMsg.value = '生成任務已不存在，請重試'
      return
    }
    console.error('查詢題型測驗任務狀態失敗:', error)
  }
}

// 測驗記錄側邊欄與資料
const sidebarOpen = ref(false)
const fullTestSidebarLogs = ref<FullTestSidebarLogSnapshot[]>([])

type QuizFolder = {
  id: string
  name: string
  color: string
  created_at: string
}

type QuizLog = {
  id: string
  mode: 'part1' | 'part2' | 'part3' | 'part4' | 'part5' | 'part6' | 'part7_single' | 'part7_multiple'
  title: string
  count: number
  difficulty: 'easy' | 'medium' | 'hard'
  created_at: string
  folder_id?: string | null
  // 保存測驗資料以便重新載入
  questions?: TOEICQuestion[]
  part1Questions?: Part1Question[]
  part2Questions?: Part2Question[]
  part3Questions?: Part3Question[]
  part4Questions?: Part4Question[]
  userAnswers?: Record<number, string>
  part3Answers?: Record<number, string[]>
  part4Answers?: Record<number, string[]>
  explanations?: TOEICExplanation[]
  score?: { correct: number, total: number }
}

const QUIZ_MODES: QuizLog['mode'][] = ['part1', 'part2', 'part3', 'part4', 'part5', 'part6', 'part7_single', 'part7_multiple']
const QUIZ_DIFFICULTIES: QuizLog['difficulty'][] = ['easy', 'medium', 'hard']

function isQuizMode(value: string): value is QuizLog['mode'] {
  return QUIZ_MODES.includes(value as QuizLog['mode'])
}

function normalizeQuizLog(summary: QuizLogSummary): QuizLog | null {
  if (!isQuizMode(summary.mode)) {
    return null
  }

  return {
    ...summary,
    mode: summary.mode,
    difficulty: QUIZ_DIFFICULTIES.includes(summary.difficulty as QuizLog['difficulty'])
      ? summary.difficulty as QuizLog['difficulty']
      : 'medium',
  }
}

const quizLogs = ref<QuizLog[]>([])
const quizFolders = ref<QuizFolder[]>([])
const backendQuizLogs = ref<QuizLogSummary[]>([])
const selectedFolderId = ref<SidebarFolderId>('all')
const movingSidebarLog = ref<UnifiedSidebarLog | null>(null)

const SIDEBAR_QUERY_SOURCE = 'openHistorySource'
const SIDEBAR_QUERY_ID = 'openHistoryId'

// 當前測驗記錄 ID（生成題目時建立，提交答案時更新）
const currentLogId = ref<string | null>(null)

async function addQuizLog(title: string) {
  try {
    const log = await toeicAPI.createQuizLog({
      mode: testMode.value,
      title,
      count: config.value.count,
      difficulty: config.value.difficulty,
      folder_id: selectedFolderId.value === 'all' ? null : selectedFolderId.value
    })
    currentLogId.value = log.id
    quizLogs.value.unshift(log as any)
    if (quizLogs.value.length > 100) quizLogs.value.length = 100
    saveLastConfig()
    notifySidebarDataUpdated()
  } catch (e) {
    console.warn('測驗記錄建立失敗', e)
  }
}

async function updateCurrentQuizLog() {
  // 提交答案後更新測驗記錄
  if (!currentLogId.value) return

  const log = quizLogs.value.find(l => l.id === currentLogId.value)
  if (!log) return

  // 更新完整資料
  log.questions = isReadingMode.value ? [...questions.value] : undefined
  log.part1Questions = testMode.value === 'part1' ? [...part1Questions.value] : undefined
  log.part2Questions = testMode.value === 'part2' ? [...part2Questions.value] : undefined
  log.part3Questions = testMode.value === 'part3' ? [...part3Questions.value] : undefined
  log.part4Questions = testMode.value === 'part4' ? [...part4Questions.value] : undefined
  log.userAnswers = { ...userAnswers.value }
  log.part3Answers = { ...part3Answers.value }
  log.part4Answers = { ...part4Answers.value }
  log.explanations = [...explanations.value]
  log.score = {
    correct: correctCount.value,
    total: totalQuestions.value
  }

  try {
    const response = await toeicAPI.updateQuizLog(log.id, {
      payload: {
        questions: log.questions,
        part1Questions: log.part1Questions,
        part2Questions: log.part2Questions,
        part3Questions: log.part3Questions,
        part4Questions: log.part4Questions,
        userAnswers: log.userAnswers,
        part3Answers: log.part3Answers,
        part4Answers: log.part4Answers,
        explanations: log.explanations
      },
      score: log.score
    })
    const index = quizLogs.value.findIndex(item => item.id === log.id)
    if (index !== -1) {
      quizLogs.value[index] = response as any
    }
    notifySidebarDataUpdated()
  } catch (e) {
    console.warn('測驗記錄更新失敗', e)
  }
}

function formatTime(ts: string) {
  const normalized = ts.endsWith('Z') || ts.includes('+') ? ts : ts + 'Z'
  const d = new Date(normalized)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${hh}:${mm}`
}

// 本機儲存（對齊 DictationPracticeView 的收藏記憶做法）
function lastConfigStorageKey() {
  return 'toeic_quiz_last_config_v1'
}

async function loadQuizLogs() {
  try {
    const logs = await toeicAPI.getQuizLogs()
    backendQuizLogs.value = logs
    quizLogs.value = logs
      .filter(isQuizBackendLog)
      .map(normalizeQuizLog)
      .filter((log): log is QuizLog => log !== null)
    loadFullTestSidebarLogs()
  } catch (e) {
    console.warn('測驗記錄讀取失敗', e)
    backendQuizLogs.value = []
    quizLogs.value = []
    loadFullTestSidebarLogs()
  }
}

async function loadQuizFolders() {
  try {
    quizFolders.value = await toeicAPI.getQuizFolders()
  } catch (e) {
    console.warn('資料夾讀取失敗', e)
    quizFolders.value = []
  }
}

function loadFullTestSidebarLogs() {
  fullTestSidebarLogs.value = mergeFullTestSidebarLogs(readFullTestSidebarLogs(), backendQuizLogs.value)
}

function updateStoredFullTestLog(logId: string, updater: (log: Record<string, any>) => void) {
  const logs = readRawFullTestLogs()
  const target = logs.find((log: Record<string, any>) => log.id === logId)
  if (!target) return false
  updater(target)
  writeRawFullTestLogs(logs)
  loadFullTestSidebarLogs()
  return true
}

function reorderStoredFullTestLogs(draggedId: string, targetId: string) {
  const logs = readRawFullTestLogs()
  const draggedIndex = logs.findIndex((log: Record<string, any>) => log.id === draggedId)
  const targetIndex = logs.findIndex((log: Record<string, any>) => log.id === targetId)
  if (draggedIndex === -1 || targetIndex === -1) return false
  const [draggedLog] = logs.splice(draggedIndex, 1)
  logs.splice(targetIndex, 0, draggedLog)
  writeRawFullTestLogs(logs)
  loadFullTestSidebarLogs()
  return true
}

// 資料夾管理
const showFolderDialog = ref(false)
const folderName = ref('')
const folderColor = ref('#3B82F6')
const editingFolderId = ref<string | null>(null)

function openAddFolderDialog() {
  folderName.value = ''
  folderColor.value = '#3B82F6'
  editingFolderId.value = null
  showFolderDialog.value = true
}

function openEditFolderDialog(folder: QuizFolder) {
  folderName.value = folder.name
  folderColor.value = folder.color
  editingFolderId.value = folder.id
  showFolderDialog.value = true
}

async function submitFolder() {
  if (!folderName.value.trim()) {
    toast.error('請輸入資料夾名稱')
    return
  }

  try {
    if (editingFolderId.value) {
      const updated = await toeicAPI.updateQuizFolder(editingFolderId.value, {
        name: folderName.value.trim(),
        color: folderColor.value
      })
      const index = quizFolders.value.findIndex(f => f.id === editingFolderId.value)
      if (index !== -1) {
        quizFolders.value[index] = updated as any
      }
    } else {
      const created = await toeicAPI.createQuizFolder({
        name: folderName.value.trim(),
        color: folderColor.value
      })
      quizFolders.value.push(created as any)
    }

    showFolderDialog.value = false
    notifySidebarDataUpdated()
  } catch (e) {
    console.warn('資料夾操作失敗', e)
    toast.error('資料夾操作失敗')
  }
}

async function deleteFolder(folderId: string, folderName: string) {
  if (!confirm(`確定要刪除「${folderName}」資料夾嗎？資料夾內的測驗記錄會移出資料夾，仍可在「全部」中查看。`)) {
    return
  }

  try {
    await toeicAPI.deleteQuizFolder(folderId)
    const index = quizFolders.value.findIndex(f => f.id === folderId)
    if (index !== -1) {
      quizFolders.value.splice(index, 1)
    }
    quizLogs.value = quizLogs.value.map(log => ({
      ...log,
      folder_id: log.folder_id === folderId ? null : log.folder_id
    }))
    if (selectedFolderId.value === folderId) {
      selectedFolderId.value = 'all'
    }
    notifySidebarDataUpdated()
  } catch (e) {
    console.warn('刪除資料夾失敗', e)
    toast.error('刪除資料夾失敗')
  }
}

function loadLastConfig() {
  try {
    const raw = localStorage.getItem(lastConfigStorageKey())
    if (!raw) return
    const data = JSON.parse(raw)
    if (data && typeof data === 'object') {
      if (data.mode && ['part1','part2','part3','part4','part5','part6','part7_single','part7_multiple'].includes(data.mode)) {
        testMode.value = data.mode
      }
      if (typeof data.count === 'number') {
        config.value.count = Math.min(20, Math.max(3, data.count))
      }
      if (['easy','medium','hard'].includes(data.difficulty)) {
        config.value.difficulty = data.difficulty
      }
    }
  } catch {
    /* ignore */
  }
}

function saveLastConfig() {
  try {
    const data = {
      mode: testMode.value,
      count: config.value.count,
      difficulty: config.value.difficulty
    }
    localStorage.setItem(lastConfigStorageKey(), JSON.stringify(data))
  } catch (e) {
    console.warn('設定儲存失敗', e)
  }
}

// 刪除測驗記錄
async function deleteQuizLog(logId: string) {
  try {
    await toeicAPI.deleteQuizLog(logId)
    quizLogs.value = quizLogs.value.filter(log => log.id !== logId)
    if (currentLogId.value === logId) {
      currentLogId.value = null
    }
    notifySidebarDataUpdated()
  } catch (e) {
    console.warn('刪除測驗記錄失敗', e)
    toast.error('測驗記錄刪除失敗')
  }
}

async function deleteFullTestSidebarLog(logId: string) {
  const rawLogs = readRawFullTestLogs()
  const targetLog = rawLogs.find(log => log?.id === logId)
  const sidebarLog = fullTestSidebarLogs.value.find(log => log.id === logId)
  if (!targetLog) {
    if (sidebarLog?.backendLogId) {
      try {
        await toeicAPI.deleteQuizLog(sidebarLog.backendLogId)
        backendQuizLogs.value = backendQuizLogs.value.filter(log => log.id !== sidebarLog.backendLogId)
      } catch (e) {
        console.warn('刪除模擬測驗後端記錄失敗', e)
      }
    }
    fullTestSidebarLogs.value = fullTestSidebarLogs.value.filter(log => log.id !== logId)
    return
  }

  if (targetLog.backendLogId) {
    try {
      await toeicAPI.deleteQuizLog(targetLog.backendLogId)
      backendQuizLogs.value = backendQuizLogs.value.filter(log => log.id !== targetLog.backendLogId)
    } catch (e) {
      console.warn('刪除模擬測驗後端記錄失敗', e)
    }
  }

  writeRawFullTestLogs(rawLogs.filter(log => log?.id !== logId))
  loadFullTestSidebarLogs()
}

async function handleSidebarDeleteLog(item: UnifiedSidebarLog) {
  if (item.source === 'quiz') {
    await deleteQuizLog(item.id)
    return
  }

  await deleteFullTestSidebarLog(item.id)
}

// 移動測驗到資料夾
const showMoveDialog = ref(false)

function openMoveDialog(item: UnifiedSidebarLog) {
  movingSidebarLog.value = item
  showMoveDialog.value = true
}

async function moveToFolder(folderId: string | null) {
  if (!movingSidebarLog.value) return

  if (movingSidebarLog.value.source === 'quiz') {
    const log = quizLogs.value.find(l => l.id === movingSidebarLog.value?.id)
    if (log) {
      try {
        await toeicAPI.updateQuizLog(log.id, { folder_id: folderId })
        log.folder_id = folderId
        notifySidebarDataUpdated()
      } catch (e) {
        console.warn('移動測驗失敗', e)
        toast.error('移動測驗失敗')
      }
    }
  } else {
    const log = fullTestSidebarLogs.value.find(l => l.id === movingSidebarLog.value?.id)
    if (log) {
      updateStoredFullTestLog(log.id, storedLog => {
        storedLog.folder_id = folderId
      })
      if (log.backendLogId) {
        toeicAPI.updateQuizLog(log.backendLogId, { folder_id: folderId }).catch(e => console.warn(e))
      }
    }
  }

  showMoveDialog.value = false
  movingSidebarLog.value = null
}

// 拖曳移動到資料夾
async function onSidebarMoveLogToFolder(payload: { log: UnifiedSidebarLog; folderId: string | null }) {
  if (payload.log.source === 'quiz') {
    const log = quizLogs.value.find(l => l.id === payload.log.id)
    if (log) {
      try {
        await toeicAPI.updateQuizLog(log.id, { folder_id: payload.folderId })
        log.folder_id = payload.folderId
        notifySidebarDataUpdated()
      } catch (e) {
        console.warn('移動測驗失敗', e)
        toast.error('移動測驗失敗')
        return
      }
    }
  } else {
    const log = fullTestSidebarLogs.value.find(l => l.id === payload.log.id)
    if (log) {
      updateStoredFullTestLog(log.id, storedLog => {
        storedLog.folder_id = payload.folderId
      })
      if (log.backendLogId) {
        toeicAPI.updateQuizLog(log.backendLogId, { folder_id: payload.folderId }).catch(e => console.warn(e))
      }
    }
  }

}

// 載入測驗記錄
async function loadQuizLog(log: QuizLog) {
  try {
    const detail = await toeicAPI.getQuizLog(log.id)
    const payload = detail.payload || {}
    if (!payload.questions && !payload.part1Questions && !payload.part2Questions && !payload.part3Questions && !payload.part4Questions) {
      toast.error('此測驗記錄無完整資料')
      return
    }

    testMode.value = detail.mode as any
    if (payload.questions) questions.value = payload.questions
    if (payload.part1Questions) part1Questions.value = payload.part1Questions
    if (payload.part2Questions) part2Questions.value = payload.part2Questions
    if (payload.part3Questions) part3Questions.value = payload.part3Questions
    if (payload.part4Questions) part4Questions.value = payload.part4Questions
    if (payload.userAnswers) userAnswers.value = payload.userAnswers
    if (payload.part3Answers) part3Answers.value = payload.part3Answers
    if (payload.part4Answers) part4Answers.value = payload.part4Answers
    if (payload.explanations) explanations.value = payload.explanations

    currentLogId.value = detail.id
    stage.value = detail.score ? 'result' : 'quiz'
    currentQuestionIndex.value = 0
    currentGroupIndex.value = 0

  } catch (e) {
    console.warn('載入測驗記錄失敗', e)
    toast.error('載入測驗記錄失敗')
  }
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

const unifiedQuizLogs = computed<UnifiedSidebarLog[]>(() => {
  return quizLogs.value.map(log => ({
    key: buildSidebarLogKey('quiz', log.id),
    id: log.id,
    source: 'quiz',
    sourceLabel: '題型測驗',
    title: log.title,
    categoryLabel: getQuizModeLabel(log.mode),
    createdAt: formatTime(log.created_at),
    difficulty: log.difficulty,
    difficultyLabel: formatDifficultyLabel(log.difficulty),
    folderId: log.folder_id ?? null,
    status: log.score ? 'completed' : 'in_progress',
    statusLabel: log.score ? '已完成' : '進行中',
    scoreText: log.score ? `${log.score.correct} / ${log.score.total}` : undefined,
    secondaryText: log.score ? undefined : '點擊繼續作答',
    canExportPdf: false,
    mode: log.mode,
  }))
})

const unifiedFullTestLogs = computed<UnifiedSidebarLog[]>(() => {
  return fullTestSidebarLogs.value.map(log => ({
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
    status: log.score ? 'completed' : (log.jobId ? 'generating' : 'in_progress'),
    statusLabel: log.score ? '已完成' : (log.jobId ? '生成中' : '進行中'),
    scoreText: log.score ? `${log.score.correct} / ${log.score.total}` : undefined,
    secondaryText: log.score ? undefined : (log.jobId ? '點擊切回模擬測驗' : '點擊載入模擬測驗'),
    canExportPdf: log.testType === 'reading' && !!log.backendLogId,
    testType: log.testType,
    backendLogId: log.backendLogId,
  }))
})

const sidebarLogs = computed(() => {
  return [...unifiedQuizLogs.value, ...unifiedFullTestLogs.value]
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
})

const visibleSidebarLogs = computed(() => {
  let logs = sidebarLogs.value

  if (selectedFolderId.value !== 'all') {
    logs = logs.filter(log => log.folderId === selectedFolderId.value)
  }

  return logs
})

const activeSidebarLogKey = computed(() => {
  return currentLogId.value ? buildSidebarLogKey('quiz', currentLogId.value) : null
})

function onSidebarReorderLogs(payload: { draggedLog: UnifiedSidebarLog; targetLog: UnifiedSidebarLog }) {
  if (payload.draggedLog.source !== payload.targetLog.source) return

  if (payload.draggedLog.source === 'quiz') {
    const draggedIndex = quizLogs.value.findIndex(log => log.id === payload.draggedLog.id)
    const targetIndex = quizLogs.value.findIndex(log => log.id === payload.targetLog.id)
    if (draggedIndex !== -1 && targetIndex !== -1) {
      const [draggedLog] = quizLogs.value.splice(draggedIndex, 1)
      if (!draggedLog) return
      quizLogs.value.splice(targetIndex, 0, draggedLog)
    }
    return
  }

  const draggedIndex = fullTestSidebarLogs.value.findIndex(log => log.id === payload.draggedLog.id)
  const targetIndex = fullTestSidebarLogs.value.findIndex(log => log.id === payload.targetLog.id)
  if (draggedIndex !== -1 && targetIndex !== -1) {
    reorderStoredFullTestLogs(payload.draggedLog.id, payload.targetLog.id)
  }
}

async function handleSidebarSelectLog(item: UnifiedSidebarLog) {
  if (item.source === 'quiz') {
    const log = quizLogs.value.find(entry => entry.id === item.id)
    if (!log) {
      toast.error('找不到題型測驗記錄')
      return
    }
    await loadQuizLog(log)
    sidebarOpen.value = false
    return
  }

  await router.push({
    name: 'full-test',
    query: {
      [SIDEBAR_QUERY_SOURCE]: 'full_test',
      [SIDEBAR_QUERY_ID]: item.id,
    },
  })
}

async function handleSidebarExportPdf(item: UnifiedSidebarLog) {
  if (item.source !== 'full_test' || !item.backendLogId) return

  try {
    const backendLog = await toeicAPI.getQuizLog(item.backendLogId)
    if (!backendLog.payload) {
      toast.error('此模擬測驗記錄無完整資料')
      return
    }

    const blob = await toeicAPI.exportPDF({
      test_data: backendLog.payload,
      export_mode: 'both',
    })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `toeic_pdf_${new Date().toISOString().slice(0, 10)}.zip`
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    console.error('匯出 PDF 失敗:', e)
    toast.error('匯出 PDF 失敗')
  }
}

async function consumePendingSidebarSelection() {
  const source = route.query[SIDEBAR_QUERY_SOURCE]
  const id = route.query[SIDEBAR_QUERY_ID]

  if (source !== 'quiz' || typeof id !== 'string') return

  const log = quizLogs.value.find(entry => entry.id === id)
  if (!log) return

  await loadQuizLog(log)

  const nextQuery = { ...route.query }
  delete nextQuery[SIDEBAR_QUERY_SOURCE]
  delete nextQuery[SIDEBAR_QUERY_ID]
  await router.replace({ query: nextQuery })
}

function handleSidebarDataUpdated() {
  loadQuizLogs()
  loadQuizFolders()
  loadFullTestSidebarLogs()
}

onMounted(() => {
  loadQuizLogs()
  loadQuizFolders()
  loadFullTestSidebarLogs()
  loadLastConfig()
  consumePendingSidebarSelection()
  selectedFolderId.value = 'all'
  window.addEventListener(SIDEBAR_DATA_UPDATED_EVENT, handleSidebarDataUpdated)

  const raw = localStorage.getItem(QUIZ_JOB_KEY)
  if (raw) {
    try {
      const saved = JSON.parse(raw) as {
        jobId?: string
        kind?: 'listening' | 'reading'
        mode?: typeof testMode.value
        config?: { count?: number; difficulty?: 'easy' | 'medium' | 'hard' }
      }
      if (saved.jobId && saved.kind && saved.mode) {
        quizJobId.value = saved.jobId
        quizJobKind.value = saved.kind
        quizJobMode.value = saved.mode
        quizJobHandled.value = false
        if (saved.config?.count) {
          config.value.count = saved.config.count
        }
        if (saved.config?.difficulty) {
          config.value.difficulty = saved.config.difficulty
        }
        stage.value = 'generating'
        generating.value = true
        startQuizStatusPolling()
      }
    } catch {
      clearQuizJob()
    }
  }
})

onBeforeUnmount(() => {
  stopQuizStatusPolling()
  window.removeEventListener(SIDEBAR_DATA_UPDATED_EVENT, handleSidebarDataUpdated)
})

watch(() => [config.value.count, config.value.difficulty, testMode.value], () => {
  saveLastConfig()
})

// 監聽路由變化，點擊導航欄「測驗」時回到主畫面
watch(() => route.query.reset, (newValue) => {
  // 當有 reset 查詢參數時，重置回主畫面
  if (newValue && stage.value !== 'config') {
    restart()
  }
})

watch(
  () => [route.query[SIDEBAR_QUERY_SOURCE], route.query[SIDEBAR_QUERY_ID], quizLogs.value.length] as const,
  () => {
    consumePendingSidebarSelection()
  }
)

// 當前題目（閱讀測驗：Part 5-7）
const currentQuestion = computed(() => {
  if (!['part5', 'part6', 'part7_single', 'part7_multiple'].includes(testMode.value)) return null
  return questions.value[currentQuestionIndex.value]
})

const currentPart1Question = computed(() => {
  if (testMode.value !== 'part1') return null
  return part1Questions.value[currentQuestionIndex.value]
})

const currentPart2Question = computed(() => {
  if (testMode.value !== 'part2') return null
  return part2Questions.value[currentQuestionIndex.value]
})

const currentPart3Question = computed(() => {
  if (testMode.value !== 'part3') return null
  return part3Questions.value[currentQuestionIndex.value]
})

const currentPart4Question = computed(() => {
  if (testMode.value !== 'part4') return null
  return part4Questions.value[currentQuestionIndex.value]
})

// 總題數
const totalQuestions = computed(() => {
  switch (testMode.value) {
    case 'part1': return part1Questions.value.length
    case 'part2': return part2Questions.value.length
    case 'part3': return part3Questions.value.length * 3 // 每組對話 3 題
    case 'part4': return part4Questions.value.length * 3 // 每段獨白 3 題
    case 'part5':
    case 'part6':
    case 'part7_single':
    case 'part7_multiple':
      return questions.value.length
    default: return 0
  }
})

// 進度
const progress = computed(() => {
  if (totalQuestions.value === 0) return 0

  let answeredCount = 0
  if (testMode.value === 'part3') {
    answeredCount = Object.values(part3Answers.value).filter(answers => answers.length === 3).length * 3
  } else if (testMode.value === 'part4') {
    answeredCount = Object.values(part4Answers.value).filter(answers => answers.length === 3).length * 3
  } else {
    answeredCount = Object.keys(userAnswers.value).length
  }

  return Math.round((answeredCount / totalQuestions.value) * 100)
})

// 答對題數
const correctCount = computed(() => {
  // Part 5-7 閱讀測驗：直接比對答案，不依賴詳解
  if (isReadingMode.value) {
    return questions.value.filter(q => userAnswers.value[q.question_number] === q.correct_answer).length
  }

  // Part 1 聽力
  if (testMode.value === 'part1') {
    return part1Questions.value.filter(q =>
      userAnswers.value[q.question_number] === q.correct_answer
    ).length
  }

  // Part 2 聽力
  if (testMode.value === 'part2') {
    return part2Questions.value.filter(q =>
      userAnswers.value[q.question_number] === q.correct_answer
    ).length
  }

  // Part 3 聽力
  if (testMode.value === 'part3') {
    let correct = 0
    part3Questions.value.forEach(q => {
      const answers = part3Answers.value[q.question_number] || []
      answers.forEach((answer, index) => {
        if (answer === q.correct_answers[index]) correct++
      })
    })
    return correct
  }

  if (testMode.value === 'part4') {
    let correct = 0
    part4Questions.value.forEach(q => {
      const answers = part4Answers.value[q.question_number] || []
      answers.forEach((answer, index) => {
        if (answer === q.correct_answers[index]) correct++
      })
    })
    return correct
  }

  return 0
})

// 答錯題數
const incorrectCount = computed(() => {
  return totalQuestions.value - correctCount.value
})

// 分數
const score = computed(() => {
  if (totalQuestions.value === 0) return 0
  return Math.round((correctCount.value / totalQuestions.value) * 100)
})

// 是否為閱讀測驗模式
const isReadingMode = computed(() => {
  return ['part5', 'part6', 'part7_single', 'part7_multiple'].includes(testMode.value)
})

// 詳解頁過濾：閱讀題目
const filteredReadingQuestions = computed(() => {
  const f = explanationFilter.value
  if (f === 'all') return questions.value
  return questions.value.filter(q => {
    const ok = userAnswers.value[q.question_number] === q.correct_answer
    return f === 'correct' ? ok : !ok
  })
})

// 詳解頁過濾：聽力題目（回傳對應 part 的 array）
const filteredListeningItems = computed((): any[] => {
  const f = explanationFilter.value
  if (testMode.value === 'part1') {
    if (f === 'all') return part1Questions.value
    return part1Questions.value.filter(q => {
      const ok = userAnswers.value[q.question_number] === q.correct_answer
      return f === 'correct' ? ok : !ok
    })
  }
  if (testMode.value === 'part2') {
    if (f === 'all') return part2Questions.value
    return part2Questions.value.filter(q => {
      const ok = userAnswers.value[q.question_number] === q.correct_answer
      return f === 'correct' ? ok : !ok
    })
  }
  if (testMode.value === 'part3') {
    if (f === 'all') return part3Questions.value
    return part3Questions.value.filter(q => {
      const answers = part3Answers.value[q.question_number] || []
      const hasError = q.correct_answers.some((ca, i) => answers[i] !== ca)
      return f === 'correct' ? !hasError : hasError
    })
  }
  if (testMode.value === 'part4') {
    if (f === 'all') return part4Questions.value
    return part4Questions.value.filter(q => {
      const answers = part4Answers.value[q.question_number] || []
      const hasError = q.correct_answers.some((ca, i) => answers[i] !== ca)
      return f === 'correct' ? !hasError : hasError
    })
  }
  return []
})

// 判斷是否應該顯示文章（只在同組文章的第一題顯示）
function shouldShowPassage(index: number): boolean {
  if (index === 0) return true // 第一題一定顯示

  const current = questions.value[index]
  const previous = questions.value[index - 1]

  if (!current || !previous) return true

  // 單篇閱讀：比較 passage
  if (current.passage && previous.passage) {
    return current.passage !== previous.passage
  }

  // 多篇閱讀：比較 passages 陣列
  if (current.passages && previous.passages) {
    if (current.passages.length !== previous.passages.length) return true
    // 比較每篇文章的內容
    for (let i = 0; i < current.passages.length; i++) {
      if (current.passages[i] !== previous.passages[i]) return true
    }
    return false // 完全相同，不顯示
  }

  return true // 預設顯示
}

// 計算題目分組（根據文章內容自動分組）
const questionGroups = computed(() => {
  if (questions.value.length === 0) return []

  // Part 5 句子填空：每題一組
  if (testMode.value === 'part5') {
    return questions.value.map((q, index) => ({
      startIndex: index,
      endIndex: index,
      questions: [q]
    }))
  }

  // Part 6 和 Part 7：根據文章內容分組
  const groups: Array<{
    startIndex: number
    endIndex: number
    questions: TOEICQuestion[]
  }> = []

  const firstQuestion = questions.value[0]
  if (!firstQuestion) return groups

  let currentGroup: TOEICQuestion[] = [firstQuestion]
  let groupStartIndex = 0

  for (let i = 1; i < questions.value.length; i++) {
    const question = questions.value[i]
    if (!question) continue

    if (shouldShowPassage(i)) {
      // 新文章開始，結束當前組
      groups.push({
        startIndex: groupStartIndex,
        endIndex: i - 1,
        questions: currentGroup
      })
      currentGroup = [question]
      groupStartIndex = i
    } else {
      // 同一文章，加入當前組
      currentGroup.push(question)
    }
  }

  // 加入最後一組
  groups.push({
    startIndex: groupStartIndex,
    endIndex: questions.value.length - 1,
    questions: currentGroup
  })

  return groups
})

// 當前組索引
const currentGroupIndex = ref(0)

// 當前組的題目
const currentGroup = computed(() => {
  return questionGroups.value[currentGroupIndex.value] || null
})

const currentGroupLeadQuestion = computed(() => {
  return currentGroup.value?.questions?.[0] ?? null
})

const currentGroupPrimaryPassage = computed(() => {
  const leadQuestion = currentGroupLeadQuestion.value
  if (!leadQuestion) return ''

  if (typeof leadQuestion.passage === 'string' && leadQuestion.passage.trim()) {
    return leadQuestion.passage
  }

  if (testMode.value === 'part6' && typeof leadQuestion.question_text === 'string') {
    return leadQuestion.question_text
  }

  return ''
})

const currentGroupPassages = computed(() => {
  const leadQuestion = currentGroupLeadQuestion.value
  return Array.isArray(leadQuestion?.passages) ? leadQuestion.passages : []
})

function getGroupLabel(group: { questions: TOEICQuestion[] }) {
  if (!group?.questions?.length) return ''
  const firstQuestion = group.questions[0]
  const lastQuestion = group.questions[group.questions.length - 1]
  if (!firstQuestion || !lastQuestion) return ''
  const start = firstQuestion.question_number
  const end = lastQuestion.question_number
  const style = firstQuestion.passage_style || 'text'
  return `Questions ${start}-${end} refer to the following ${style}.`
}

function getGroupLabelForIndex(index: number) {
  const group = questionGroups.value.find(g => index >= g.startIndex && index <= g.endIndex)
  return group ? getGroupLabel(group) : ''
}

// 是否為分組模式（Part 6、Part 7）
const isGroupMode = computed(() => {
  return ['part6', 'part7_single', 'part7_multiple'].includes(testMode.value)
})

// 生成考題
async function generateQuiz() {
  switch (testMode.value) {
    case 'part1':
      await generatePart1Quiz()
      break
    case 'part2':
      await generatePart2Quiz()
      break
    case 'part3':
      await generatePart3Quiz()
      break
    case 'part4':
      await generatePart4Quiz()
      break
    case 'part5':
      await generateReadingQuiz('sentence')
      break
    case 'part6':
      await generateReadingQuiz('paragraph')
      break
    case 'part7_single':
      await generateReadingQuiz('single_passage')
      break
    case 'part7_multiple':
      await generateReadingQuiz('multiple_passage')
      break
  }
}

// 生成閱讀測驗（Part 5-7）
async function generateReadingQuiz(questionType: 'sentence' | 'paragraph' | 'single_passage' | 'multiple_passage') {
  generating.value = true

  try {
    const provider = 'gemini'  // 固定使用 Gemini
    const model = settingsStore.settings.defaultModel || 'gemini-2.5-flash'
    const apiKey = settingsStore.settings.apiKeys.gemini
    const response = await toeicAPI.startReadingJob({
      question_type: questionType,
      count: config.value.count,
      difficulty: config.value.difficulty,
      provider: provider,
      model: model,
      api_key: apiKey
    })

    const typeNames = {
      sentence: '句子填空',
      paragraph: '段落填空',
      single_passage: '單篇閱讀',
      multiple_passage: '多篇閱讀'
    }
    const modeMap = {
      sentence: 'part5',
      paragraph: 'part6',
      single_passage: 'part7_single',
      multiple_passage: 'part7_multiple'
    } as const
    quizJobId.value = response.job_id
    quizJobKind.value = 'reading'
    quizJobMode.value = modeMap[questionType]
    quizJobHandled.value = false
    stage.value = 'generating'
    saveQuizJob(response.job_id, 'reading', modeMap[questionType])
    startQuizStatusPolling()
  } catch (error: any) {
    console.error('生成失敗:', error)
    const errorMsg = error?.response?.data?.detail || '生成失敗'
    toast.error(errorMsg)
    generating.value = false
  } finally {
    // 交由背景任務完成後關閉 generating
  }
}

// 生成 Part 1 聽力測驗（照片描述）
async function generatePart1Quiz() {
  generating.value = true

  try {
    const { mediaProvider, mediaModel, mediaApiKey } = getMediaConfig()

    if (!mediaApiKey) {
      toast.error('請先在設定頁面中填入 Gemini API Key（用於圖片生成）')
      generating.value = false
      return
    }

    const response = await listeningAPI.startPart1Job({
      count: config.value.count,
      difficulty: config.value.difficulty,
      provider: mediaProvider,
      model: mediaModel,
      api_key: mediaApiKey,
      accent: config.value.accent,
      pace: config.value.pace
    })

    quizJobId.value = response.job_id
    quizJobKind.value = 'listening'
    quizJobMode.value = 'part1'
    quizJobHandled.value = false
    stage.value = 'generating'
    saveQuizJob(response.job_id, 'listening', 'part1')
    startQuizStatusPolling()
  } catch (error: any) {
    console.error('生成失敗:', error)
    const errorMsg = error?.response?.data?.detail || '生成失敗，請檢查 API Key 是否有效'
    toast.error(errorMsg)
    generating.value = false
  } finally {
    // 交由背景任務完成後關閉 generating
  }
}

// 生成 Part 2 聽力測驗（應答問題）
async function generatePart2Quiz() {
  generating.value = true

  try {
    const { textProvider, textModel, textApiKey, ttsProvider, ttsApiKey } = getListeningConfig()

    if (!ttsApiKey) {
      toast.error('請先在設定頁面中填入語音生成 API Key')
      generating.value = false
      return
    }

    const response = await listeningAPI.startPart2Job({
      count: config.value.count,
      difficulty: config.value.difficulty,
      provider: textProvider,
      model: textModel,
      api_key: ttsApiKey,
      text_api_key: textApiKey,
      text_provider: textProvider,
      text_model: textModel,
      tts_provider: ttsProvider,
      tts_api_key: ttsApiKey,
      accent: config.value.accent,
      pace: config.value.pace
    })

    quizJobId.value = response.job_id
    quizJobKind.value = 'listening'
    quizJobMode.value = 'part2'
    quizJobHandled.value = false
    stage.value = 'generating'
    saveQuizJob(response.job_id, 'listening', 'part2')
    startQuizStatusPolling()
  } catch (error: any) {
    console.error('生成失敗:', error)
    const errorMsg = error?.response?.data?.detail || '生成失敗，請檢查 API Key 是否有效'
    toast.error(errorMsg)
    generating.value = false
  } finally {
    // 交由背景任務完成後關閉 generating
  }
}

// 生成 Part 3 聽力測驗（簡短對話）
async function generatePart3Quiz() {
  generating.value = true

  try {
    const { textProvider, textModel, textApiKey, ttsProvider, ttsApiKey } = getListeningConfig()

    if (!ttsApiKey) {
      toast.error('請先在設定頁面中填入語音生成 API Key')
      generating.value = false
      return
    }

    const response = await listeningAPI.startPart3Job({
      count: config.value.count,
      difficulty: config.value.difficulty,
      provider: textProvider,
      model: textModel,
      api_key: ttsApiKey,
      text_api_key: textApiKey,
      text_provider: textProvider,
      text_model: textModel,
      tts_provider: ttsProvider,
      tts_api_key: ttsApiKey,
      accent: config.value.accent,
      pace: config.value.pace
    })

    quizJobId.value = response.job_id
    quizJobKind.value = 'listening'
    quizJobMode.value = 'part3'
    quizJobHandled.value = false
    stage.value = 'generating'
    saveQuizJob(response.job_id, 'listening', 'part3')
    startQuizStatusPolling()
  } catch (error: any) {
    console.error('生成失敗:', error)
    const errorMsg = error?.response?.data?.detail || '生成失敗，請檢查 API Key 是否有效'
    toast.error(errorMsg)
    generating.value = false
  } finally {
    // 交由背景任務完成後關閉 generating
  }
}

// 生成 Part 4 聽力測驗（簡短獨白）
async function generatePart4Quiz() {
  generating.value = true

  try {
    const { textProvider, textModel, textApiKey, ttsProvider, ttsApiKey } = getListeningConfig()

    if (!ttsApiKey) {
      toast.error('請先在設定頁面中填入語音生成 API Key')
      generating.value = false
      return
    }

    const response = await listeningAPI.startPart4Job({
      count: config.value.count,
      difficulty: config.value.difficulty,
      provider: textProvider,
      model: textModel,
      api_key: ttsApiKey,
      text_api_key: textApiKey,
      text_provider: textProvider,
      text_model: textModel,
      tts_provider: ttsProvider,
      tts_api_key: ttsApiKey,
      accent: config.value.accent,
      pace: config.value.pace
    })

    quizJobId.value = response.job_id
    quizJobKind.value = 'listening'
    quizJobMode.value = 'part4'
    quizJobHandled.value = false
    stage.value = 'generating'
    saveQuizJob(response.job_id, 'listening', 'part4')
    startQuizStatusPolling()
  } catch (error: any) {
    console.error('生成失敗:', error)
    const errorMsg = error?.response?.data?.detail || '生成失敗，請檢查 API Key 是否有效'
    toast.error(errorMsg)
    generating.value = false
  } finally {
    // 交由背景任務完成後關閉 generating
  }
}

// 選擇答案（Part 1, 2, 5-7）
function selectAnswer(questionNumberOrAnswer: number | string, answerOrUndefined?: string) {
  let questionNumber: number
  let answer: string

  // 支援兩種調用方式：
  // 1. selectAnswer(questionNumber, answer) - 直接指定題號
  // 2. selectAnswer(answer) - 自動偵測當前題號
  if (typeof questionNumberOrAnswer === 'number' && answerOrUndefined) {
    questionNumber = questionNumberOrAnswer
    answer = answerOrUndefined
  } else {
    answer = questionNumberOrAnswer as string

    if (isReadingMode.value) {
      questionNumber = currentQuestion.value?.question_number as number
    } else if (testMode.value === 'part1') {
      questionNumber = currentPart1Question.value?.question_number as number
    } else if (testMode.value === 'part2') {
      questionNumber = currentPart2Question.value?.question_number as number
    } else {
      return
    }
  }

  if (!questionNumber) return
  userAnswers.value[questionNumber] = answer
}

// 為特定題目選擇答案（用於分組模式）
function selectAnswerForQuestion(questionNumber: number, answer: string) {
  userAnswers.value[questionNumber] = answer
}

// 選擇 Part 3/4 的單個問題答案
function selectPart34Answer(questionIndex: number, answer: string) {
  const currentQ = testMode.value === 'part3' ? currentPart3Question.value : currentPart4Question.value
  if (!currentQ) return

  const answersRef = testMode.value === 'part3' ? part3Answers : part4Answers
  const currentAnswers = answersRef.value[currentQ.question_number] ?? []
  currentAnswers[questionIndex] = answer
  answersRef.value[currentQ.question_number] = currentAnswers
}

// Part 3 輔助函數
function selectPart3Answer(questionNumber: number, questionIndex: number, answer: string) {
  if (!part3Answers.value[questionNumber]) {
    part3Answers.value[questionNumber] = []
  }
  part3Answers.value[questionNumber][questionIndex] = answer
}

function getPart3Answer(questionNumber: number, questionIndex: number): string {
  return part3Answers.value[questionNumber]?.[questionIndex] || ''
}

// Part 4 輔助函數
function selectPart4Answer(questionNumber: number, questionIndex: number, answer: string) {
  if (!part4Answers.value[questionNumber]) {
    part4Answers.value[questionNumber] = []
  }
  part4Answers.value[questionNumber][questionIndex] = answer
}

function getPart4Answer(questionNumber: number, questionIndex: number): string {
  return part4Answers.value[questionNumber]?.[questionIndex] || ''
}

function getListeningExplanation(questionNumber: number, subIndex: number) {
  return explanations.value.find(exp =>
    exp.question_number === questionNumber &&
    ((exp as any).sub_question_index ?? 0) === subIndex
  )
}

function buildOptionItems(options: any[] | undefined, correctAnswer: string, userAnswer: string): ExplanationOptionItem[] {
  return (options || []).map((option: any) => ({
    label: option.label,
    text: option.text,
    isCorrect: option.label === correctAnswer,
    isUserAnswer: option.label === userAnswer && option.label !== correctAnswer,
  }))
}

function getReadingBlankPosition(question: TOEICQuestion) {
  const explicitPosition = (question as any).blank_position
  if (explicitPosition != null) return explicitPosition

  const questionIndex = questions.value.findIndex(q => q.question_number === question.question_number)
  return questionIndex >= 0 ? (questionIndex % 4) + 1 : null
}

function buildReadingExplanationItem(question: TOEICQuestion): ExplanationItem {
  const userAnswer = userAnswers.value[question.question_number] || ''

  return {
    id: `quiz-${testMode.value}-${question.question_number}`,
    questionNumber: question.question_number,
    partKey: testMode.value as ExplanationPartKey,
    title: `題目 ${question.question_number}`,
    isCorrect: userAnswer === question.correct_answer,
    userAnswer,
    correctAnswer: question.correct_answer,
    explanation: explanations.value.find(exp => exp.question_number === question.question_number)?.explanation,
    canGenerateExplanation: true,
    isGenerating: !!generatingExplanation.value[question.question_number],
    passage: question.passage,
    passages: question.passages,
    questionText: testMode.value === 'part6' ? '' : question.question_text,
    blankPosition: testMode.value === 'part6' ? getReadingBlankPosition(question) : null,
    options: buildOptionItems(question.options, question.correct_answer, userAnswer),
  }
}

function buildPart1ExplanationItem(question: Part1Question): ExplanationItem {
  const userAnswer = userAnswers.value[question.question_number] || ''

  return {
    id: `quiz-part1-${question.question_number}`,
    questionNumber: question.question_number,
    partKey: 'part1',
    title: `題目 ${question.question_number}`,
    isCorrect: userAnswer === question.correct_answer,
    userAnswer,
    correctAnswer: question.correct_answer,
    staticHint: '📷 照片描述題：請播放各選項音檔，比對圖片內容，選出最符合照片的描述。',
    canGenerateExplanation: false,
    media: {
      imageUrl: question.image_url,
      audioOptions: question.audio_urls.map((url, index) => {
        const label = String.fromCharCode(65 + index)
        return {
          label,
          url,
          text: (question as any).option_texts?.[index],
          isCorrect: label === question.correct_answer,
          isUserAnswer: label === userAnswer && label !== question.correct_answer,
        }
      }),
    },
  }
}

function buildPart2ExplanationItem(question: Part2Question): ExplanationItem {
  const userAnswer = userAnswers.value[question.question_number] || ''

  return {
    id: `quiz-part2-${question.question_number}`,
    questionNumber: question.question_number,
    partKey: 'part2',
    title: `題目 ${question.question_number}`,
    isCorrect: userAnswer === question.correct_answer,
    userAnswer,
    correctAnswer: question.correct_answer,
    explanation: explanations.value.find(exp => exp.question_number === question.question_number)?.explanation,
    canGenerateExplanation: true,
    isGenerating: !!generatingExplanation.value[question.question_number],
    media: {
      audioLabel: '問題',
      audioUrl: question.question_audio_url,
      audioText: question.question_text,
      audioOptions: question.option_audio_urls.map((url, index) => {
        const label = String.fromCharCode(65 + index)
        return {
          label,
          url,
          text: question.option_texts?.[index],
          isCorrect: label === question.correct_answer,
          isUserAnswer: label === userAnswer && label !== question.correct_answer,
        }
      }),
    },
  }
}

function buildPart3ExplanationItem(question: Part3Question): ExplanationItem {
  const answers = part3Answers.value[question.question_number] || []
  const children: ExplanationChildItem[] = question.questions.map((subQuestion, index) => {
    const userAnswer = answers[index] || ''
    const correctAnswer = question.correct_answers[index] || ''
    return {
      id: `quiz-part3-${question.question_number}-${index}`,
      index: index + 1,
      questionText: subQuestion.question_text,
      userAnswer,
      correctAnswer,
      isCorrect: userAnswer === correctAnswer,
      options: buildOptionItems(subQuestion.options, correctAnswer, userAnswer),
      explanation: getListeningExplanation(question.question_number, index)?.explanation,
    }
  })

  return {
    id: `quiz-part3-${question.question_number}`,
    questionNumber: question.question_number,
    partKey: 'part3',
    title: `對話 ${question.question_number}`,
    isCorrect: children.every(child => child.isCorrect),
    canGenerateExplanation: true,
    isGenerating: !!generatingExplanation.value[question.question_number],
    media: {
      audioLabel: '對話音檔',
      audioUrl: question.conversation_audio_url,
      transcript: question.transcript,
    },
    children,
  }
}

function buildPart4ExplanationItem(question: Part4Question): ExplanationItem {
  const answers = part4Answers.value[question.question_number] || []
  const children: ExplanationChildItem[] = question.questions.map((subQuestion, index) => {
    const userAnswer = answers[index] || ''
    const correctAnswer = question.correct_answers[index] || ''
    return {
      id: `quiz-part4-${question.question_number}-${index}`,
      index: index + 1,
      questionText: subQuestion.question_text,
      userAnswer,
      correctAnswer,
      isCorrect: userAnswer === correctAnswer,
      options: buildOptionItems(subQuestion.options, correctAnswer, userAnswer),
      explanation: getListeningExplanation(question.question_number, index)?.explanation,
    }
  })

  return {
    id: `quiz-part4-${question.question_number}`,
    questionNumber: question.question_number,
    partKey: 'part4',
    title: `獨白 ${question.question_number}`,
    isCorrect: children.every(child => child.isCorrect),
    canGenerateExplanation: true,
    isGenerating: !!generatingExplanation.value[question.question_number],
    media: {
      audioLabel: '獨白音檔',
      audioUrl: question.talk_audio_url,
      transcript: question.transcript,
    },
    children,
  }
}

function buildQuizExplanationItem(item: TOEICQuestion | Part1Question | Part2Question | Part3Question | Part4Question): ExplanationItem {
  if (isReadingMode.value) {
    return buildReadingExplanationItem(item as TOEICQuestion)
  }
  if (testMode.value === 'part1') {
    return buildPart1ExplanationItem(item as Part1Question)
  }
  if (testMode.value === 'part2') {
    return buildPart2ExplanationItem(item as Part2Question)
  }
  if (testMode.value === 'part3') {
    return buildPart3ExplanationItem(item as Part3Question)
  }
  return buildPart4ExplanationItem(item as Part4Question)
}

function hasGeneratedExplanation(item: ExplanationItem) {
  return !!(item.explanation || item.children?.some(child => !!child.explanation))
}

const allQuizExplanationItems = computed(() => {
  if (isReadingMode.value) {
    return questions.value.map(question => buildReadingExplanationItem(question))
  }
  if (testMode.value === 'part1') {
    return part1Questions.value.map(question => buildPart1ExplanationItem(question))
  }
  if (testMode.value === 'part2') {
    return part2Questions.value.map(question => buildPart2ExplanationItem(question))
  }
  if (testMode.value === 'part3') {
    return part3Questions.value.map(question => buildPart3ExplanationItem(question))
  }
  return part4Questions.value.map(question => buildPart4ExplanationItem(question))
})

const quizExplanationItems = computed(() => {
  if (isReadingMode.value) {
    return filteredReadingQuestions.value.map(question => buildQuizExplanationItem(question))
  }
  return filteredListeningItems.value.map(question => buildQuizExplanationItem(question))
})

const totalQuizExplanationItems = computed(() => allQuizExplanationItems.value.length)

const generatedQuizExplanationCount = computed(() => {
  return allQuizExplanationItems.value.filter(item => hasGeneratedExplanation(item)).length
})

const quizExplanationSummary = computed(() => {
  if (testMode.value === 'part1') {
    return `共 ${totalQuizExplanationItems.value} 題詳解`
  }
  return `已生成 ${generatedQuizExplanationCount.value} / ${totalQuizExplanationItems.value} 題詳解`
})

// 播放音訊
async function playAudio(audioUrl: string) {
  // 停止當前播放的音訊
  if (currentAudio.value) {
    currentAudio.value.pause()
    currentAudio.value = null
  }

  return new Promise<void>((resolve, reject) => {
    const audio = new Audio(audioUrl)
    currentAudio.value = audio
    audioPlaying.value = true

    audio.onended = () => {
      audioPlaying.value = false
      currentAudio.value = null
      resolve()
    }

    audio.onerror = (e) => {
      audioPlaying.value = false
      currentAudio.value = null
      toast.error('音訊載入失敗')
      reject(e)
    }

    audio.play().catch((e) => {
      audioPlaying.value = false
      currentAudio.value = null
      toast.error('音訊播放失敗')
      reject(e)
    })
  })
}

// 播放選項音訊並選擇
async function playOptionAndSelect(index: number, audioUrl: string) {
  const answer = String.fromCharCode(65 + index) // A, B, C, D
  selectAnswer(answer)
  await playAudio(audioUrl)
}

// 依序播放所有選項（Part 1）
async function playAllOptions() {
  if (!currentPart1Question.value) return

  const audioUrls = currentPart1Question.value.audio_urls
  audioPlaying.value = true
  for (let i = 0; i < audioUrls.length; i++) {
    const audioUrl = audioUrls[i]
    if (!audioUrl) continue
    try {
      await new Promise(resolve => setTimeout(resolve, 500))
      await playAudio(audioUrl)
      await new Promise(resolve => setTimeout(resolve, 800))
    } catch (e) {
      console.error('播放失敗:', e)
      break
    }
  }
  audioPlaying.value = false
}

// 播放 Part 2 問句
async function playPart2Question() {
  if (!currentPart2Question.value) return
  await playAudio(currentPart2Question.value.question_audio_url)
}

// 播放 Part 3 對話
async function playPart3Conversation() {
  if (!currentPart3Question.value) return
  await playAudio(currentPart3Question.value.conversation_audio_url)
}

// 播放 Part 4 獨白
async function playPart4Talk() {
  if (!currentPart4Question.value) return
  await playAudio(currentPart4Question.value.talk_audio_url)
}

// 上一題
function previousQuestion() {
  if (currentQuestionIndex.value > 0) {
    currentQuestionIndex.value--
  }
}

// 下一題
function nextQuestion() {
  let maxIndex = 0

  if (isReadingMode.value) {
    maxIndex = questions.value.length - 1
  } else if (testMode.value === 'part1') {
    maxIndex = part1Questions.value.length - 1
  } else if (testMode.value === 'part2') {
    maxIndex = part2Questions.value.length - 1
  } else if (testMode.value === 'part3') {
    maxIndex = part3Questions.value.length - 1
  } else if (testMode.value === 'part4') {
    maxIndex = part4Questions.value.length - 1
  }

  if (currentQuestionIndex.value < maxIndex) {
    currentQuestionIndex.value++
  }
}

// 上一組（用於分組模式）
function previousGroup() {
  if (currentGroupIndex.value > 0) {
    currentGroupIndex.value--
  }
}

// 下一組（用於分組模式）
function nextGroup() {
  if (currentGroupIndex.value < questionGroups.value.length - 1) {
    currentGroupIndex.value++
  }
}

// 跳到指定題目
function goToQuestion(index: number) {
  currentQuestionIndex.value = index
}

// 提交答案
async function submitAnswers() {
  if (isReadingMode.value) {
    await submitReadingAnswers()
  } else {
    await submitListeningAnswers()
  }
}

// 提交閱讀測驗答案
async function submitReadingAnswers() {
  // 檢查是否所有題目都已作答
  const unanswered = questions.value.filter(q => !userAnswers.value[q.question_number])
  if (unanswered.length > 0) {
    const confirm = window.confirm(`還有 ${unanswered.length} 題未作答，確定要提交嗎？`)
    if (!confirm) return
  }

  submitting.value = true
  loadingExplanations.value = false  // 確保不顯示載入狀態

  try {
    // 直接進入結果頁面，不生成詳解
    stage.value = 'result'

    // 更新測驗記錄
    await updateCurrentQuizLog()

  } catch (error: any) {
    console.error('提交失敗:', error)
    const errorMsg = error?.response?.data?.detail || '提交失敗'
    toast.error(errorMsg)
  } finally {
    submitting.value = false
  }
}

// 提交聽力測驗答案
async function submitListeningAnswers() {
  // 檢查是否所有題目都已作答
  let unansweredCount = 0

  switch (testMode.value) {
    case 'part1':
      unansweredCount = part1Questions.value.filter(q => !userAnswers.value[q.question_number]).length
      break
    case 'part2':
      unansweredCount = part2Questions.value.filter(q => !userAnswers.value[q.question_number]).length
      break
    case 'part3':
      unansweredCount = part3Questions.value.filter(q => (part3Answers.value[q.question_number]?.length ?? 0) < 3).length * 3
      break
    case 'part4':
      unansweredCount = part4Questions.value.filter(q => (part4Answers.value[q.question_number]?.length ?? 0) < 3).length * 3
      break
  }

  if (unansweredCount > 0) {
    const confirm = window.confirm(`還有 ${unansweredCount} 題未作答，確定要提交嗎？`)
    if (!confirm) return
  }

  submitting.value = true
  loadingExplanations.value = false  // 確保不顯示載入狀態

  try {
    // 準備答案資料
    const answersData: any[] = []

    if (testMode.value === 'part1') {
      // Part 1: 照片描述題
      for (const q of part1Questions.value) {
        answersData.push({
          question_number: q.question_number,
          user_answer: userAnswers.value[q.question_number] || '',
          correct_answer: q.correct_answer
        })
      }
    } else if (testMode.value === 'part2') {
      // Part 2: 應答問題
      for (const q of part2Questions.value) {
        answersData.push({
          question_number: q.question_number,
          user_answer: userAnswers.value[q.question_number] || '',
          correct_answer: q.correct_answer,
          question_text: (q as any).question_text,
          option_texts: (q as any).option_texts
        })
      }
    } else if (testMode.value === 'part3') {
      // Part 3: 簡短對話
      for (const q of part3Questions.value) {
        answersData.push({
          question_number: q.question_number,
          questions: q.questions,
          correct_answers: q.correct_answers,
          user_answers: part3Answers.value[q.question_number] || [],
          transcript: (q as any).transcript
        })
      }
    } else if (testMode.value === 'part4') {
      // Part 4: 簡短獨白
      for (const q of part4Questions.value) {
        answersData.push({
          question_number: q.question_number,
          questions: q.questions,
          correct_answers: q.correct_answers,
          user_answers: part4Answers.value[q.question_number] || [],
          transcript: (q as any).transcript
        })
      }
    }

    // 直接進入結果頁面，不生成詳解
    stage.value = 'result'

    // 更新測驗記錄
    await updateCurrentQuizLog()

  } catch (error: any) {
    console.error('提交失敗:', error)
    const errorMsg = error?.response?.data?.detail || '提交失敗'
    toast.error(errorMsg)
  } finally {
    submitting.value = false
  }
}

// 生成單題詳解
async function generateSingleExplanation(questionNumber: number, subIndex?: number) {
  const key = subIndex !== undefined ? `${questionNumber}-${subIndex}` : questionNumber
  generatingExplanation.value[key] = true

  try {
    const provider = 'gemini'  // 固定使用 Gemini
    const model = settingsStore.settings.defaultModel || 'gemini-2.5-flash'
    const apiKey = settingsStore.settings.apiKeys.gemini

    if (isReadingMode.value) {
      // 閱讀測驗單題
      const q = questions.value.find(q => q.question_number === questionNumber)
      if (!q) {
        toast.error('找不到題目')
        return
      }

        const answersData = [{
          question_number: q.question_number,
          user_answer: userAnswers.value[q.question_number] || '',
          correct_answer: q.correct_answer,
          question_type: q.question_type,
          question_text: q.question_text,
          passage_style: q.passage_style,
          passage: q.passage,
          passages: q.passages,
          options: q.options
        }]

      const exps = await toeicAPI.generateExplanations({
        answers: answersData,
        provider: provider,
        model: model,
        api_key: apiKey
      })

      if (exps && exps.length > 0) {
        const firstExplanation = exps[0]
        if (!firstExplanation) return

        // 更新或新增該題詳解
        const existingIndex = explanations.value.findIndex(e => e.question_number === questionNumber)
        if (existingIndex >= 0) {
          explanations.value[existingIndex] = firstExplanation
        } else {
          explanations.value.push(firstExplanation)
        }
      }
    } else {
      // 聽力測驗單題
      let answersData: any = null

      if (testMode.value === 'part1') {
        const q = part1Questions.value.find(q => q.question_number === questionNumber)
        if (!q) {
          toast.error('找不到題目')
          return
        }
        answersData = {
          question_number: q.question_number,
          user_answer: userAnswers.value[q.question_number] || '',
          correct_answer: q.correct_answer
        }
      } else if (testMode.value === 'part2') {
        const q = part2Questions.value.find(q => q.question_number === questionNumber)
        if (!q) {
          toast.error('找不到題目')
          return
        }
        answersData = {
          question_number: q.question_number,
          user_answer: userAnswers.value[q.question_number] || '',
          correct_answer: q.correct_answer,
          question_text: (q as any).question_text,
          option_texts: (q as any).option_texts
        }
      } else if (testMode.value === 'part3') {
        const q = part3Questions.value.find(q => q.question_number === questionNumber)
        if (!q) {
          toast.error('找不到題目')
          return
        }
        answersData = {
          question_number: q.question_number,
          questions: q.questions,
          correct_answers: q.correct_answers,
          user_answers: part3Answers.value[q.question_number] || [],
          transcript: (q as any).transcript
        }
      } else if (testMode.value === 'part4') {
        const q = part4Questions.value.find(q => q.question_number === questionNumber)
        if (!q) {
          toast.error('找不到題目')
          return
        }
        answersData = {
          question_number: q.question_number,
          questions: q.questions,
          correct_answers: q.correct_answers,
          user_answers: part4Answers.value[q.question_number] || [],
          transcript: (q as any).transcript
        }
      }

      const exps = await listeningAPI.generateListeningExplanations({
        test_mode: testMode.value,
        answers: [answersData],
        provider: provider,
        model: model,
        api_key: apiKey
      })

      if (exps && exps.length > 0) {
        // 對於 Part 3/4，可能返回多個子題的詳解
        exps.forEach(exp => {
          const existingIndex = explanations.value.findIndex(e =>
            e.question_number === exp.question_number &&
            e.sub_question_index === exp.sub_question_index
          )
          if (existingIndex >= 0) {
            explanations.value[existingIndex] = exp
          } else {
            explanations.value.push(exp)
          }
        })
      }
    }

    // 更新測驗記錄
    await updateCurrentQuizLog()
  } catch (error: any) {
    console.error('生成詳解失敗:', error)
    const errorMsg = error?.response?.data?.detail || '生成詳解失敗'
    toast.error(errorMsg)
  } finally {
    generatingExplanation.value[key] = false
  }
}

// 再測一次：保留題目與詳解，清空作答並回到作答頁
async function retakeQuiz() {
  if (totalQuestions.value === 0) {
    restart()
    return
  }

  stopQuizStatusPolling()
  clearQuizJob()
  generating.value = false
  submitting.value = false

  userAnswers.value = {}
  part3Answers.value = {}
  part4Answers.value = {}
  currentQuestionIndex.value = 0
  currentGroupIndex.value = 0
  loadingExplanations.value = false
  generatingExplanation.value = {}
  explanationFilter.value = 'all'

  if (currentAudio.value) {
    currentAudio.value.pause()
    currentAudio.value = null
  }
  audioPlaying.value = false

  stage.value = 'quiz'

  const log = quizLogs.value.find(l => l.id === currentLogId.value)
  if (log) {
    log.questions = isReadingMode.value ? [...questions.value] : undefined
    log.part1Questions = testMode.value === 'part1' ? [...part1Questions.value] : undefined
    log.part2Questions = testMode.value === 'part2' ? [...part2Questions.value] : undefined
    log.part3Questions = testMode.value === 'part3' ? [...part3Questions.value] : undefined
    log.part4Questions = testMode.value === 'part4' ? [...part4Questions.value] : undefined
    log.userAnswers = {}
    log.part3Answers = {}
    log.part4Answers = {}
    log.explanations = [...explanations.value]
    log.score = undefined

    try {
      await toeicAPI.updateQuizLog(log.id, {
        payload: {
          questions: isReadingMode.value ? [...questions.value] : undefined,
          part1Questions: testMode.value === 'part1' ? [...part1Questions.value] : undefined,
          part2Questions: testMode.value === 'part2' ? [...part2Questions.value] : undefined,
          part3Questions: testMode.value === 'part3' ? [...part3Questions.value] : undefined,
          part4Questions: testMode.value === 'part4' ? [...part4Questions.value] : undefined,
          userAnswers: {},
          part3Answers: {},
          part4Answers: {},
          explanations: log.explanations
        },
        score: null
      })
      notifySidebarDataUpdated()
    } catch (e) {
      console.warn('重置測驗記錄失敗', e)
    }
  }
}

// 重新開始
function restart() {
  stage.value = 'config'
  stopQuizStatusPolling()
  clearQuizJob()
  generating.value = false
  questions.value = []
  part1Questions.value = []
  part2Questions.value = []
  part3Questions.value = []
  part4Questions.value = []
  userAnswers.value = {}
  part3Answers.value = {}
  part4Answers.value = {}
  explanations.value = []
  currentQuestionIndex.value = 0
  currentLogId.value = null

  // 重置載入狀態
  loadingExplanations.value = false
  generatingExplanation.value = {}

  // 停止播放音訊
  if (currentAudio.value) {
    currentAudio.value.pause()
    currentAudio.value = null
  }
  audioPlaying.value = false
}

// 題型名稱
function getTypeName(type: string): string {
  const names: Record<string, string> = {
    sentence: '句子填空',
    paragraph: '段落填空',
    single_passage: '單篇閱讀',
    multiple_passage: '多篇閱讀'
  }
  return names[type] || type
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-gray-900 dark:via-blue-900/20 dark:to-purple-900/20 p-6">
    <div class="max-w-4xl mx-auto">
      <UnifiedTestSidebar
        v-model:open="sidebarOpen"
        :logs="sidebarLogs"
        :visible-logs="visibleSidebarLogs"
        :folders="quizFolders"
        :selected-folder-id="selectedFolderId"
        :active-log-key="activeSidebarLogKey"
        empty-text="此資料夾無測驗記錄"
        @select-folder="selectedFolderId = $event"
        @select-log="handleSidebarSelectLog"
        @request-create-folder="openAddFolderDialog"
        @request-edit-folder="openEditFolderDialog"
        @request-delete-folder="deleteFolder($event.id, $event.name)"
        @request-move-log="openMoveDialog"
        @request-delete-log="handleSidebarDeleteLog"
        @export-pdf="handleSidebarExportPdf"
        @move-log-to-folder="onSidebarMoveLogToFolder"
        @reorder-logs="onSidebarReorderLogs"
      />

      <!-- 資料夾對話框 -->
      <div
        v-if="showFolderDialog"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm z-[60] flex items-center justify-center p-4"
        @click.self="showFolderDialog = false"
      >
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl p-6 w-full max-w-md">
          <h3 class="text-xl font-bold mb-4 text-gray-800 dark:text-white">
            {{ editingFolderId ? '編輯資料夾' : '新增資料夾' }}
          </h3>

          <div class="space-y-4">
            <div>
              <label class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">資料夾名稱</label>
              <input
                v-model="folderName"
                type="text"
                class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-white focus:ring-2 focus:ring-blue-500"
                placeholder="例如：模擬考、文法練習"
              />
            </div>

            <div>
              <label class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">顏色</label>
              <div class="flex gap-2">
                <input
                  v-model="folderColor"
                  type="color"
                  class="w-16 h-10 rounded-lg cursor-pointer"
                />
                <input
                  v-model="folderColor"
                  type="text"
                  class="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-white"
                  placeholder="#3B82F6"
                />
              </div>
            </div>
          </div>

          <div class="flex gap-3 mt-6">
            <button
              @click="showFolderDialog = false"
              class="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              取消
            </button>
            <button
              @click="submitFolder"
              class="flex-1 px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
            >
              {{ editingFolderId ? '更新' : '建立' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 移動測驗對話框 -->
      <div
        v-if="showMoveDialog"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm z-[60] flex items-center justify-center p-4"
        @click.self="showMoveDialog = false"
      >
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl p-6 w-full max-w-md">
          <h3 class="text-xl font-bold mb-4 text-gray-800 dark:text-white">移動到資料夾</h3>

          <div class="space-y-2 max-h-96 overflow-y-auto">
            <button
              @click="moveToFolder(null)"
              class="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left"
            >
              <span class="text-lg"></span>
              <span class="font-semibold text-gray-700 dark:text-gray-200">不放入資料夾</span>
            </button>

            <button
              v-for="folder in quizFolders"
              :key="folder.id"
              @click="moveToFolder(folder.id)"
              class="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left"
            >
              <div
                class="w-4 h-4 rounded-full"
                :style="{ backgroundColor: folder.color }"
              ></div>
              <span class="font-semibold text-gray-700 dark:text-gray-200">{{ folder.name }}</span>
            </button>
          </div>

          <div class="mt-6">
            <button
              @click="showMoveDialog = false"
              class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              取消
            </button>
          </div>
        </div>
      </div>

      <!-- ========== 配置階段 ========== -->
      <div v-if="stage === 'config'" class="max-w-3xl mx-auto px-4 py-8">
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8">
          <div class="text-center mb-6">
            <h1 class="text-3xl md:text-4xl font-black bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 bg-clip-text text-transparent">
              <span class="block">TOEIC 題型測驗</span>
              <span class="block text-sm md:text-base font-semibold text-gray-600 dark:text-gray-400">
                AI 生成的 TOEIC 練習題
              </span>
            </h1>
          </div>

          <h2 class="text-xl font-bold text-gray-800 dark:text-white mb-6">測驗設定</h2>

          <div class="space-y-8">
          <!-- 聽力測驗選項 -->
          <div>
            <h3 class="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-3"> 聽力測驗</h3>
            <div class="grid grid-cols-2 gap-3">
              <button
                v-for="part in ['part1', 'part2', 'part3', 'part4']"
                :key="part"
                @click="testMode = part as any"
                :class="[
                  'p-4 rounded-lg border-2 transition-all',
                  testMode === part ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30' : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                ]"
              >
                <div class="font-bold text-sm">
                  {{ part === 'part1' ? '照片描述' : part === 'part2' ? '應答問題' : part === 'part3' ? '簡短對話' : '簡短獨白' }}
                </div>
                <div class="text-xs text-gray-500">Part {{ part.slice(-1) }}</div>
              </button>
            </div>
          </div>

          <!-- 閱讀測驗選項 -->
          <div>
            <h3 class="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-3"> 閱讀測驗</h3>
            <div class="grid grid-cols-2 gap-3">
              <button
                @click="testMode = 'part5'"
                :class="[
                  'p-4 rounded-lg border-2 transition-all',
                  testMode === 'part5' ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30' : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                ]"
              >
                <div class="font-bold text-sm">句子填空</div>
                <div class="text-xs text-gray-500">Part 5</div>
              </button>
              <button
                @click="testMode = 'part6'"
                :class="[
                  'p-4 rounded-lg border-2 transition-all',
                  testMode === 'part6' ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30' : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                ]"
              >
                <div class="font-bold text-sm">段落填空</div>
                <div class="text-xs text-gray-500">Part 6</div>
              </button>
              <button
                @click="testMode = 'part7_single'"
                :class="[
                  'p-4 rounded-lg border-2 transition-all',
                  testMode === 'part7_single' ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30' : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                ]"
              >
                <div class="font-bold text-sm">單篇閱讀</div>
                <div class="text-xs text-gray-500">Part 7</div>
              </button>
              <button
                @click="testMode = 'part7_multiple'"
                :class="[
                  'p-4 rounded-lg border-2 transition-all',
                  testMode === 'part7_multiple' ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30' : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                ]"
              >
                <div class="font-bold text-sm">多篇閱讀</div>
                <div class="text-xs text-gray-500">Part 7</div>
              </button>
            </div>
          </div>

          <!-- 題數配置 -->
          <div>
            <label class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
              題數: {{ config.count }}
            </label>
            <input
              v-model.number="config.count"
              type="range"
              min="3"
              max="20"
              step="1"
              class="w-full"
            />
            <div class="flex justify-between text-xs text-gray-500 mt-1">
              <span>3 題</span><span>20 題</span>
            </div>
          </div>

          <!-- 難度配置 -->
          <div>
            <label class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
              難度等級
            </label>
            <div class="grid grid-cols-3 gap-4">
              <button
                @click="config.difficulty = 'easy'"
                :class="[
                  'px-4 py-3 rounded-lg border-2 transition-all font-semibold',
                  config.difficulty === 'easy'
                    ? 'border-green-500 bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                    : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:border-gray-400'
                ]"
              >
                 簡單
              </button>
              <button
                @click="config.difficulty = 'medium'"
                :class="[
                  'px-4 py-3 rounded-lg border-2 transition-all font-semibold',
                  config.difficulty === 'medium'
                    ? 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300'
                    : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:border-gray-400'
                ]"
              >
                 中等
              </button>
              <button
                @click="config.difficulty = 'hard'"
                :class="[
                  'px-4 py-3 rounded-lg border-2 transition-all font-semibold',
                  config.difficulty === 'hard'
                    ? 'border-red-500 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                    : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:border-gray-400'
                ]"
              >
                 困難
              </button>
            </div>
          </div>

          <!-- 聽力專用：口音選擇 -->
          <div v-if="isListeningMode">
            <label class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
              🎙️ 口音設定
            </label>
            <div class="grid grid-cols-3 gap-3">
              <button
                v-for="option in ACCENT_OPTIONS"
                :key="option.label"
                @click="config.accent = option.value"
                :class="[
                  'px-3 py-2 rounded-lg border-2 transition-all text-sm font-semibold',
                  config.accent === option.value
                    ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300'
                    : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:border-gray-400'
                ]"
              >
                {{ option.label }}
              </button>
            </div>
          </div>

          <!-- 聽力專用：語速選擇 -->
          <div v-if="isListeningMode">
            <label class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
              ⏱️ 語速設定
            </label>
            <div class="grid grid-cols-5 gap-2">
              <button
                v-for="option in PACE_OPTIONS"
                :key="option.value"
                @click="config.pace = option.value"
                :class="[
                  'px-2 py-2 rounded-lg border-2 transition-all text-xs font-semibold',
                  config.pace === option.value
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                    : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:border-gray-400'
                ]"
              >
                {{ option.label }}
              </button>
            </div>
          </div>

          <!-- 生成按鈕 -->
          <button
            @click="generateQuiz"
            :disabled="generating"
            class="w-full px-8 py-4 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white text-lg font-bold rounded-lg disabled:opacity-50 transition-all transform hover:scale-105"
          >
            <span v-if="generating">... 生成中...</span>
            <span v-else>* 開始生成考題</span>
          </button>
        </div>
      </div>
      </div>

      <!-- ========== 生成階段 ========== -->
      <div v-if="stage === 'generating'" class="max-w-3xl mx-auto px-4 py-8">
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8">
          <h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-6">
            {{ quizJobHasError ? '⚠️ 生成中斷' : '正在生成題目...' }}
          </h2>

          <!-- Part 進度卡 -->
          <div
            :class="[
              'p-5 rounded-xl border-2 transition-all',
              quizJobHasError
                ? 'bg-red-50 border-red-200'
                : 'bg-blue-50 border-blue-200'
            ]"
          >
            <div class="flex items-center gap-4">
              <!-- 狀態圖示 -->
              <div class="flex-shrink-0 w-10 h-10 flex items-center justify-center">
                <span v-if="quizJobHasError" class="text-red-500 text-3xl">❌</span>
                <svg v-else class="animate-spin h-8 w-8 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>

              <!-- 題型與進度 -->
              <div class="flex-1">
                <div class="flex items-center justify-between mb-2">
                  <span class="font-semibold text-gray-900">
                    {{
                      quizJobMode === 'part1' ? 'Part 1 照片描述' :
                      quizJobMode === 'part2' ? 'Part 2 應答問題' :
                      quizJobMode === 'part3' ? 'Part 3 簡短對話' :
                      quizJobMode === 'part4' ? 'Part 4 簡短獨白' :
                      quizJobMode === 'part5' ? 'Part 5 句子填空' :
                      quizJobMode === 'part6' ? 'Part 6 段落填空' :
                      quizJobMode === 'part7_single' ? 'Part 7 單篇閱讀' :
                      quizJobMode === 'part7_multiple' ? 'Part 7 多篇閱讀' : '題目生成'
                    }}
                  </span>
                  <span :class="quizJobHasError ? 'text-red-600' : 'text-blue-600'" class="text-sm font-medium">
                    <template v-if="quizJobHasError">失敗</template>
                    <template v-else-if="quizJobProgress">
                      {{ quizJobProgress.generated }} / {{ quizJobProgress.total }} 題
                    </template>
                    <template v-else>生成中...</template>
                  </span>
                </div>

                <!-- 進度條 -->
                <div class="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                  <div
                    v-if="quizJobHasError"
                    class="h-2 rounded-full bg-red-500"
                    style="width: 100%"
                  ></div>
                  <div
                    v-else-if="quizJobProgress && quizJobProgress.total > 0 && quizJobProgress.generated > 0"
                    class="h-2 rounded-full bg-blue-500 transition-all duration-500"
                    :style="{ width: Math.round((quizJobProgress.generated / quizJobProgress.total) * 100) + '%' }"
                  ></div>
                  <!-- 不確定進度時：全寬流動動畫 -->
                  <div
                    v-else
                    class="h-2 rounded-full bg-blue-500"
                    style="width: 40%; animation: slide-indeterminate 1.5s ease-in-out infinite"
                  ></div>
                </div>
              </div>
            </div>
          </div>

          <!-- 錯誤訊息 -->
          <div v-if="quizJobHasError && quizJobErrorMsg" class="mt-4 text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">
            {{ quizJobErrorMsg }}
          </div>

          <!-- 操作按鈕 -->
          <div class="mt-6 flex items-center justify-center gap-3 flex-wrap">
            <button
              v-if="quizJobHasError"
              @click="retryQuizGeneration"
              class="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              🔄 重試生成
            </button>
            <button
              @click="leaveQuizGenerating"
              class="px-5 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-sm font-medium transition-colors"
            >
              ← 返回設定
            </button>
          </div>

          <p v-if="!quizJobHasError" class="mt-4 text-xs text-gray-400 text-center">
            生成於背景進行，離開後返回此頁面會自動恢復進度。
          </p>
        </div>
      </div>

      <!-- ========== 答題階段 ========== -->
      <div v-if="stage === 'quiz'" class="space-y-6">
        <!-- 進度條 -->
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">
              作答進度: {{ progress }}%
            </span>
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">
              <span v-if="isReadingMode && isGroupMode">
                第 {{ currentGroupIndex + 1 }} 組 / 共 {{ questionGroups.length }} 組
              </span>
              <span v-else-if="isReadingMode">
                第 {{ currentGroupIndex + 1 }} 題 / 共 {{ questions.length }} 題
              </span>
              <span v-else>
                {{ currentQuestionIndex + 1 }} / {{ totalQuestions }}
              </span>
            </span>
          </div>
          <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
            <div
              class="h-3 rounded-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-300"
              :style="{ width: progress + '%' }"
            ></div>
          </div>
        </div>

        <!-- 閱讀測驗題目 (Part 5-7) -->
        <div v-if="isReadingMode && currentGroup" class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8">
          <!-- 單篇文章內容 -->
          <div v-if="currentGroupPrimaryPassage" class="mb-8 bg-gray-50 dark:bg-gray-700 rounded-lg p-6">
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">
              {{ getGroupLabel(currentGroup) }}
            </p>
            <MarkdownRenderer :content="currentGroupPrimaryPassage" :plain-surface="true" />
          </div>

          <!-- 多篇文章內容 -->
          <div v-if="currentGroupPassages.length > 0" class="mb-8 space-y-4">
            <div
              v-for="(passage, index) in currentGroupPassages"
              :key="index"
              class="bg-gray-50 dark:bg-gray-700 rounded-lg p-6"
            >
              <h4 class="text-sm font-bold text-gray-600 dark:text-gray-400 mb-3"> 文章 {{ index + 1 }}</h4>
              <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">
                {{ getGroupLabel(currentGroup) }}
              </p>
              <MarkdownRenderer :content="passage" :plain-surface="true" />
            </div>
          </div>

          <!-- 題目卡片列表 -->
          <div class="space-y-6">
            <div
              v-for="question in currentGroup.questions"
              :key="question.question_number"
              class="p-6 bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 rounded-lg"
            >
              <!-- 題目 + 狀態 -->
              <div class="flex items-start justify-between mb-4 gap-4">
                <div class="flex-1">
                  <p v-if="testMode === 'part6'" class="font-semibold text-gray-800 dark:text-gray-200">
                    {{ question.question_number }}. (Blank {{ getReadingBlankPosition(question) }})
                  </p>
                  <p v-else class="font-semibold text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
                    {{ question.question_number }}. {{ question.question_text }}
                  </p>
                </div>
                <span
                  v-if="userAnswers[question.question_number]"
                  class="px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full text-sm font-medium shrink-0"
                >
                  已作答
                </span>
                <span
                  v-else
                  class="px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded-full text-sm font-medium shrink-0"
                >
                  未作答
                </span>
              </div>

              <!-- 選項 -->
              <div class="space-y-2">
                <button
                  v-for="option in question.options"
                  :key="option.label"
                  @click="selectAnswerForQuestion(question.question_number, option.label)"
                  :class="[
                    'w-full p-3 rounded-lg border-2 text-left transition-all',
                    userAnswers[question.question_number] === option.label
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-900 dark:text-blue-100 font-semibold'
                      : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 text-gray-800 dark:text-gray-200'
                  ]"
                >
                  <span class="font-bold">{{ option.label }}.</span>
                  <span class="ml-2">{{ option.text }}</span>
                </button>
              </div>
            </div>
          </div>

          <!-- 導航按鈕 -->
          <div class="flex items-center justify-between mt-8">
            <button
              @click="previousGroup"
              :disabled="currentGroupIndex === 0"
              class="px-6 py-3 bg-gray-500 text-white font-bold rounded-lg hover:bg-gray-600 disabled:opacity-50 transition-all"
            >
              <span v-if="isGroupMode">< 上一組</span>
              <span v-else>< 上一題</span>
            </button>

            <button
              v-if="currentGroupIndex === questionGroups.length - 1"
              @click="submitAnswers"
              :disabled="submitting"
              class="px-8 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white font-bold rounded-lg hover:from-green-600 hover:to-emerald-600 disabled:opacity-50 transition-all"
            >
              <span v-if="submitting">... 提交中...</span>
              <span v-else>✅ 提交答案</span>
            </button>

            <button
              v-else
              @click="nextGroup"
              class="px-6 py-3 bg-gray-500 text-white font-bold rounded-lg hover:bg-gray-600 transition-all"
            >
              <span v-if="isGroupMode">下一組 ></span>
              <span v-else>下一題 ></span>
            </button>
          </div>
        </div>

        <!-- 聽力測驗題目 (Part 1-4) -->
        <div v-if="!isReadingMode" class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8">
          <!-- Part 1: 照片描述 -->
          <div v-if="testMode === 'part1' && currentPart1Question">
            <p class="font-semibold text-gray-900 dark:text-white mb-4">{{ currentPart1Question.question_number }}. 請依序播放下方音檔，選擇最符合圖片的描述</p>

            <!-- 圖片 -->
            <div class="mb-6 flex justify-center">
              <img
                :src="currentPart1Question.image_url"
                alt="Question Image"
                class="max-w-full max-h-96 rounded-lg shadow-lg"
              />
            </div>

            <!-- 選項 (A, B, C, D) -->
            <div class="space-y-3">
              <div
                v-for="(audioUrl, index) in currentPart1Question.audio_urls"
                :key="index"
                @click="selectAnswer(currentPart1Question.question_number, String.fromCharCode(65 + index))"
                :class="[
                  'p-4 rounded-lg border-2 cursor-pointer transition-all flex items-center gap-4',
                  userAnswers[currentPart1Question.question_number] === String.fromCharCode(65 + index)
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                    : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                ]"
              >
                <div class="font-bold text-lg">{{ String.fromCharCode(65 + index) }}.</div>
                <audio :src="audioUrl" controls class="flex-1"></audio>
              </div>
            </div>

            <!-- 導航按鈕 -->
            <div class="flex items-center justify-between mt-8">
              <button
                @click="previousQuestion"
                :disabled="currentQuestionIndex === 0"
                class="px-6 py-3 bg-gray-500 text-white font-bold rounded-lg hover:bg-gray-600 disabled:opacity-50 transition-all"
              >
                < 上一題
              </button>

              <button
                v-if="currentQuestionIndex === part1Questions.length - 1"
                @click="submitAnswers"
                :disabled="submitting"
                class="px-8 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white font-bold rounded-lg hover:from-green-600 hover:to-emerald-600 disabled:opacity-50 transition-all"
              >
                <span v-if="submitting">... 提交中...</span>
                <span v-else>✅ 提交答案</span>
              </button>

              <button
                v-else
                @click="nextQuestion"
                class="px-6 py-3 bg-gray-500 text-white font-bold rounded-lg hover:bg-gray-600 transition-all"
              >
                下一題 >
              </button>
            </div>
          </div>

          <!-- Part 2: 應答問題 -->
          <div v-if="testMode === 'part2' && currentPart2Question">
            <p class="font-semibold text-gray-900 dark:text-white mb-4">{{ currentPart2Question.question_number }}. 請先聽問題，再選擇回應</p>

            <!-- 問句音檔 -->
            <div class="bg-purple-50 dark:bg-purple-900/20 p-6 rounded-lg mb-6">
              <div class="flex items-center gap-3 mb-3">
                <h4 class="font-bold text-gray-800 dark:text-white">問題</h4>
              </div>
              <audio :src="currentPart2Question.question_audio_url" controls class="w-full"></audio>
            </div>

            <!-- 回答選項音檔 (A, B, C) -->
            <div class="space-y-3">
              <div
                v-for="(audioUrl, index) in currentPart2Question.option_audio_urls"
                :key="index"
                @click="selectAnswer(currentPart2Question.question_number, String.fromCharCode(65 + index))"
                :class="[
                  'p-4 rounded-lg border-2 cursor-pointer transition-all flex items-center gap-4',
                  userAnswers[currentPart2Question.question_number] === String.fromCharCode(65 + index)
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                    : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                ]"
              >
                <div class="font-bold text-lg">{{ String.fromCharCode(65 + index) }}.</div>
                <audio :src="audioUrl" controls class="flex-1"></audio>
              </div>
            </div>

            <!-- 導航按鈕 -->
            <div class="flex items-center justify-between mt-8">
              <button
                @click="previousQuestion"
                :disabled="currentQuestionIndex === 0"
                class="px-6 py-3 bg-gray-500 text-white font-bold rounded-lg hover:bg-gray-600 disabled:opacity-50 transition-all"
              >
                < 上一題
              </button>

              <button
                v-if="currentQuestionIndex === part2Questions.length - 1"
                @click="submitAnswers"
                :disabled="submitting"
                class="px-8 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white font-bold rounded-lg hover:from-green-600 hover:to-emerald-600 disabled:opacity-50 transition-all"
              >
                <span v-if="submitting">... 提交中...</span>
                <span v-else>✅ 提交答案</span>
              </button>

              <button
                v-else
                @click="nextQuestion"
                class="px-6 py-3 bg-gray-500 text-white font-bold rounded-lg hover:bg-gray-600 transition-all"
              >
                下一題 >
              </button>
            </div>
          </div>

          <!-- Part 3: 簡短對話 -->
          <div v-if="testMode === 'part3' && currentPart3Question">
            <!-- 對話音檔 -->
            <div class="bg-green-50 dark:bg-green-900/20 p-6 rounded-lg mb-6">
              <div class="flex items-center gap-3 mb-3">
                <div class="text-2xl"></div>
                <h4 class="font-bold text-gray-800 dark:text-white">對話</h4>
              </div>
              <audio :src="currentPart3Question.conversation_audio_url" controls class="w-full"></audio>
            </div>

            <!-- 3 個問題 -->
            <div class="space-y-6">
              <div
                v-for="(q, qIndex) in currentPart3Question.questions"
                :key="qIndex"
                class="bg-white dark:bg-gray-700 p-5 rounded-lg border border-gray-200 dark:border-gray-600"
              >
                <h5 class="font-bold text-gray-800 dark:text-white mb-3">
                  {{ qIndex + 1 }}. {{ q.question_text }}
                </h5>
                <div class="space-y-2">
                  <div
                    v-for="option in q.options"
                    :key="option.label"
                    @click="selectPart3Answer(currentPart3Question.question_number, qIndex, option.label)"
                    :class="[
                      'p-3 rounded-lg border cursor-pointer transition-all',
                      getPart3Answer(currentPart3Question.question_number, qIndex) === option.label
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                        : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                    ]"
                  >
                    <span class="font-semibold">{{ option.label }}.</span> {{ option.text }}
                  </div>
                </div>
              </div>
            </div>

            <!-- 導航按鈕 -->
            <div class="flex items-center justify-between mt-8">
              <button
                @click="previousQuestion"
                :disabled="currentQuestionIndex === 0"
                class="px-6 py-3 bg-gray-500 text-white font-bold rounded-lg hover:bg-gray-600 disabled:opacity-50 transition-all"
              >
                < 上一組
              </button>

              <button
                v-if="currentQuestionIndex === part3Questions.length - 1"
                @click="submitAnswers"
                :disabled="submitting"
                class="px-8 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white font-bold rounded-lg hover:from-green-600 hover:to-emerald-600 disabled:opacity-50 transition-all"
              >
                <span v-if="submitting">... 提交中...</span>
                <span v-else>✅ 提交答案</span>
              </button>

              <button
                v-else
                @click="nextQuestion"
                class="px-6 py-3 bg-gray-500 text-white font-bold rounded-lg hover:bg-gray-600 transition-all"
              >
                下一組 >
              </button>
            </div>
          </div>

          <!-- Part 4: 簡短獨白 -->
          <div v-if="testMode === 'part4' && currentPart4Question">
            <!-- 獨白音檔 -->
            <div class="bg-orange-50 dark:bg-orange-900/20 p-6 rounded-lg mb-6">
              <div class="flex items-center gap-3 mb-3">
                <div class="text-2xl"></div>
                <h4 class="font-bold text-gray-800 dark:text-white">獨白</h4>
              </div>
              <audio :src="currentPart4Question.talk_audio_url" controls class="w-full"></audio>
            </div>

            <!-- 3 個問題 -->
            <div class="space-y-6">
              <div
                v-for="(q, qIndex) in currentPart4Question.questions"
                :key="qIndex"
                class="bg-white dark:bg-gray-700 p-5 rounded-lg border border-gray-200 dark:border-gray-600"
              >
                <h5 class="font-bold text-gray-800 dark:text-white mb-3">
                  {{ qIndex + 1 }}. {{ q.question_text }}
                </h5>
                <div class="space-y-2">
                  <div
                    v-for="option in q.options"
                    :key="option.label"
                    @click="selectPart4Answer(currentPart4Question.question_number, qIndex, option.label)"
                    :class="[
                      'p-3 rounded-lg border cursor-pointer transition-all',
                      getPart4Answer(currentPart4Question.question_number, qIndex) === option.label
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                        : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                    ]"
                  >
                    <span class="font-semibold">{{ option.label }}.</span> {{ option.text }}
                  </div>
                </div>
              </div>
            </div>

            <!-- 導航按鈕 -->
            <div class="flex items-center justify-between mt-8">
              <button
                @click="previousQuestion"
                :disabled="currentQuestionIndex === 0"
                class="px-6 py-3 bg-gray-500 text-white font-bold rounded-lg hover:bg-gray-600 disabled:opacity-50 transition-all"
              >
                < 上一段
              </button>

              <button
                v-if="currentQuestionIndex === part4Questions.length - 1"
                @click="submitAnswers"
                :disabled="submitting"
                class="px-8 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white font-bold rounded-lg hover:from-green-600 hover:to-emerald-600 disabled:opacity-50 transition-all"
              >
                <span v-if="submitting">... 提交中...</span>
                <span v-else>✅ 提交答案</span>
              </button>

              <button
                v-else
                @click="nextQuestion"
                class="px-6 py-3 bg-gray-500 text-white font-bold rounded-lg hover:bg-gray-600 transition-all"
              >
                下一段 >
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- ========== 結果階段 ========== -->
      <div v-if="stage === 'result'" class="flex justify-center px-4 py-8">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 text-center w-full max-w-lg">
          <div class="text-6xl mb-4">
            {{ score >= 80 ? '🏆' : score >= 60 ? '👍' : '📚' }}
          </div>
          <h2 class="text-3xl font-bold text-gray-800 dark:text-white mb-4">測驗完成！</h2>
          <div class="text-5xl font-black bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-6">
            {{ score }} 分
          </div>
          <div class="flex justify-center gap-8 text-lg mb-8">
            <div>
              <span class="text-green-600 font-bold">✅ {{ correctCount }}</span>
              <span class="text-gray-600 dark:text-gray-400 ml-1">答對</span>
            </div>
            <div>
              <span class="text-red-600 font-bold">❌ {{ incorrectCount }}</span>
              <span class="text-gray-600 dark:text-gray-400 ml-1">答錯</span>
            </div>
          </div>
          <div class="flex gap-3 justify-center flex-wrap">
            <button
              @click="stage = 'explanations'; explanationFilter = 'all'"
              class="px-8 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white font-bold rounded-lg transition-all transform hover:scale-105"
            >
              📖 查看詳解
            </button>
            <button
              @click="retakeQuiz"
              class="px-8 py-3 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 font-bold rounded-lg transition-all"
            >
              🔄 再測一次
            </button>
          </div>
        </div>
      </div>

      <!-- ========== 詳解階段 ========== -->
      <div v-if="stage === 'explanations'" class="max-w-6xl mx-auto px-4 py-8">
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8">
          <div class="flex items-center justify-between mb-6 gap-4 flex-wrap">
            <div>
              <h2 class="text-3xl font-bold text-gray-900 dark:text-white mb-2">
                📚 題目詳解
              </h2>
              <p class="text-sm text-gray-600 dark:text-gray-400">
                {{ quizExplanationSummary }}
              </p>
            </div>
            <div class="flex gap-3 flex-wrap">
              <button
                @click="stage = 'result'"
                class="px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg font-medium transition-all"
              >
                ← 返回結果
              </button>
            </div>
          </div>

          <div class="mb-6 flex gap-3 flex-wrap">
            <button
              v-for="f in [{ value: 'all', label: '全部題目' }, { value: 'incorrect', label: '僅答錯' }, { value: 'correct', label: '僅答對' }]"
              :key="f.value"
              @click="explanationFilter = (f.value as any)"
              :class="[
                'px-4 py-2 rounded-lg font-medium transition-all',
                explanationFilter === f.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              ]"
            >
              {{ f.label }}
            </button>
          </div>

          <div v-if="quizExplanationItems.length" class="space-y-4">
            <SharedExplanationCard
              v-for="item in quizExplanationItems"
              :key="item.id"
              :item="item"
              @generate="generateSingleExplanation"
            />
          </div>
          <div
            v-else
            class="rounded-xl border border-dashed border-gray-300 dark:border-gray-600 px-6 py-10 text-center text-sm text-gray-500 dark:text-gray-400"
          >
            目前沒有符合篩選條件的題目。
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes slide-indeterminate {
  0%   { transform: translateX(-100%); }
  60%  { transform: translateX(250%); }
  100% { transform: translateX(250%); }
}
</style>
