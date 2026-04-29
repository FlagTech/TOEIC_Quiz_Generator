import type { QuizLogSummary } from '@/types'

export type SidebarLogSource = 'quiz' | 'full_test'
export type SidebarFolderId = 'all' | 'uncategorized' | string

export interface FullTestSidebarLogSnapshot {
  id: string
  title: string
  testType: 'listening' | 'reading'
  difficulty: 'easy' | 'medium' | 'hard'
  created_at: string
  completed_at?: string
  jobId?: string
  backendLogId?: string
  score?: {
    correct: number
    total: number
  }
  timeElapsed?: number
  folder_id?: string | null
}

export interface UnifiedSidebarLog {
  key: string
  id: string
  source: SidebarLogSource
  sourceLabel: string
  title: string
  categoryLabel: string
  createdAt: string
  difficulty: 'easy' | 'medium' | 'hard'
  difficultyLabel: string
  folderId?: string | null
  status: 'completed' | 'generating' | 'in_progress'
  statusLabel: string
  scoreText?: string
  secondaryText?: string
  canExportPdf: boolean
  mode?: QuizLogSummary['mode']
  testType?: FullTestSidebarLogSnapshot['testType']
  backendLogId?: string
}

export const FULL_TEST_LOGS_STORAGE_KEY = 'toeic_test_logs_v2'
export const SIDEBAR_DATA_UPDATED_EVENT = 'toeic-sidebar-data-updated'

const FULL_TEST_MODES = ['reading_full', 'listening_full'] as const
const QUIZ_MODES = ['part1', 'part2', 'part3', 'part4', 'part5', 'part6', 'part7_single', 'part7_multiple'] as const

export function buildSidebarLogKey(source: SidebarLogSource, id: string) {
  return `${source}:${id}`
}

export function formatDifficultyLabel(difficulty: string) {
  switch (difficulty) {
    case 'easy':
      return '簡單'
    case 'hard':
      return '困難'
    default:
      return '中等'
  }
}

export function readFullTestSidebarLogs(): FullTestSidebarLogSnapshot[] {
  return readRawFullTestLogs()
    .filter((log): log is FullTestSidebarLogSnapshot => !!log?.id && !!log?.title && !!log?.testType)
    .map(log => ({
      id: String(log.id),
      title: String(log.title),
      testType: log.testType === 'reading' ? 'reading' : 'listening',
      difficulty: log.difficulty === 'easy' || log.difficulty === 'hard' ? log.difficulty : 'medium',
      created_at: String(log.created_at),
      completed_at: log.completed_at,
      jobId: log.jobId,
      backendLogId: log.backendLogId,
      score: log.score,
      timeElapsed: log.timeElapsed,
      folder_id: log.folder_id ?? null,
    }))
}

export function isFullTestBackendLog(log: QuizLogSummary) {
  return FULL_TEST_MODES.includes(log.mode as (typeof FULL_TEST_MODES)[number])
}

export function isQuizBackendLog(log: QuizLogSummary) {
  return QUIZ_MODES.includes(log.mode as (typeof QUIZ_MODES)[number])
}

export function fullTestSnapshotFromBackendLog(log: QuizLogSummary): FullTestSidebarLogSnapshot {
  return {
    id: log.id,
    title: log.title,
    testType: log.mode === 'reading_full' ? 'reading' : 'listening',
    difficulty: log.difficulty === 'easy' || log.difficulty === 'hard' ? log.difficulty : 'medium',
    created_at: log.created_at,
    backendLogId: log.id,
    score: log.score,
    folder_id: log.folder_id ?? null,
  }
}

export function mergeFullTestSidebarLogs(
  localLogs: FullTestSidebarLogSnapshot[],
  backendLogs: QuizLogSummary[],
): FullTestSidebarLogSnapshot[] {
  const merged = new Map<string, FullTestSidebarLogSnapshot>()

  for (const backendLog of backendLogs.filter(isFullTestBackendLog)) {
    const snapshot = fullTestSnapshotFromBackendLog(backendLog)
    merged.set(snapshot.backendLogId || snapshot.id, snapshot)
  }

  for (const localLog of localLogs) {
    const matchedBackend = !localLog.backendLogId
      ? Array.from(merged.values()).find(log =>
        log.title === localLog.title &&
        log.testType === localLog.testType &&
        log.difficulty === localLog.difficulty
      )
      : null

    const enrichedLocalLog: FullTestSidebarLogSnapshot = matchedBackend
      ? {
        ...localLog,
        backendLogId: matchedBackend.backendLogId,
        score: localLog.score ?? matchedBackend.score,
        folder_id: localLog.folder_id ?? matchedBackend.folder_id ?? null,
      }
      : localLog

    if (matchedBackend) {
      merged.delete(matchedBackend.backendLogId || matchedBackend.id)
    }

    merged.set(enrichedLocalLog.backendLogId || enrichedLocalLog.id, enrichedLocalLog)
  }

  return Array.from(merged.values())
}

export function readRawFullTestLogs(): any[] {
  if (typeof window === 'undefined') return []

  try {
    const raw = localStorage.getItem(FULL_TEST_LOGS_STORAGE_KEY)
    if (!raw) return []

    const logs = JSON.parse(raw)
    if (!Array.isArray(logs)) return []
    return logs
  } catch {
    return []
  }
}

export function writeRawFullTestLogs(logs: any[]) {
  if (typeof window === 'undefined') return
  localStorage.setItem(FULL_TEST_LOGS_STORAGE_KEY, JSON.stringify(logs))
  notifySidebarDataUpdated()
}

export function notifySidebarDataUpdated() {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new Event(SIDEBAR_DATA_UPDATED_EVENT))
}
