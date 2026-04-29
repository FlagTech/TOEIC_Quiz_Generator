/**
 * TypeScript 類型定義
 */

// ========== 單字相關類型 ==========

export interface Word {
  id: string
  english_word: string
  chinese_definition?: string
  star_rating?: number
  category?: string
  parts_of_speech?: string // JSON 字串
  word_forms?: string // JSON 字串
  examples?: string // JSON 字串
  ai_insights?: string // AI 解說
  source: 'database' | 'custom'
  created_at: string
}

export interface WordsQuery {
  skip?: number
  limit?: number
  star_rating?: number
  category?: string
  search?: string
}

// ========== 學習進度類型 ==========

export interface LearningProgress {
  id: number
  word_id: string
  user_id: string
  status: 'not_learned' | 'learning' | 'mastered' | 'review'
  review_count: number
  last_reviewed?: string
  next_review?: string
  ease_factor: number
  interval_days: number
  custom_tags?: string // JSON 字串
  personal_note?: string
}

export interface ReviewRequest {
  word_id: string
  quality: number // 0-5
}

// ========== 統計相關類型 ==========

export interface StatsOverview {
  today_count: number
  week_count: number
  total_count: number
  total_words: number
  mastered_count: number
  learning_count: number
  review_count: number
  not_learned_count: number
  mastery_rate: number
}

export interface CategoryStats {
  category: string
  total: number
  mastered: number
  learning: number
  not_learned: number
  mastery_rate: number
}

export interface DailyChartData {
  date: string
  count: number
}

export interface ChartData {
  labels: string[]
  datasets: {
    label: string
    data: number[]
  }[]
}

// ========== AI 生成類型 ==========

export interface GenerateRequest {
  word: string
  provider: 'ollama' | 'openai' | 'gemini'
  api_key?: string
  fields_to_fill?: {
    chinese_definition?: boolean
    category?: boolean
    parts_of_speech?: boolean
    word_forms?: boolean
    examples?: boolean
  }
}

export interface GenerateResponse {
  word_data: Partial<Word>
  provider: string
  model: string
}

// ========== 學習模式類型 ==========

export type LearningMode = 'browse' | 'quiz' | 'review' | 'random'

// ========== 主題類型 ==========

export type Theme = 'light' | 'dark' | 'auto'

// ========== 設定類型 ==========

export interface AppSettings {
  theme: Theme
  apiKeys: {
    gemini?: string  // 統一使用 Gemini API Key
    gemini_media?: string // Gemini 專用於媒體功能
  }
  defaultProvider: 'gemini'  // 固定使用 Gemini
  defaultModel?: string
  speechRate: number
  autoPlayAudio: boolean
}

// ========== TOEIC 測驗類型 ==========

export interface TOEICOption {
  label: string // A, B, C, D
  text: string
}

export interface TOEICQuestion {
  question_number: number
  question_type: 'sentence' | 'paragraph' | 'single_passage' | 'multiple_passage'
  passage_style?: string
  passage?: string // 單篇文章
  passages?: string[] // 多篇文章
  question_text: string
  blank_position?: number
  options: TOEICOption[]
  correct_answer: string // A, B, C, or D
  explanation?: string
}

export interface TOEICGenerateRequest {
  question_type: 'sentence' | 'paragraph' | 'single_passage' | 'multiple_passage'
  count: number
  difficulty?: 'easy' | 'medium' | 'hard'
  provider: 'ollama' | 'openai' | 'gemini'
  model: string
  api_key?: string
}

export interface TOEICQuizResponse {
  questions: TOEICQuestion[]
  question_type: string
  total_count: number
}

export interface TOEICAnswerSubmit {
  question_number: number
  user_answer: string | string[]
  correct_answer: string | string[]
  question_type?: string
  question_text: string
  passage_style?: string
  passage?: string
  passages?: string[]
  options: TOEICOption[]
}

export interface TOEICExplainRequest {
  answers: TOEICAnswerSubmit[]
  provider: 'ollama' | 'openai' | 'gemini'
  model: string
  api_key?: string
}

export interface TOEICExplanation {
  question_number: number
  is_correct: boolean
  explanation: string
  sub_question_index?: number
}

// ========== TOEIC Part 1 聽力測驗類型 ==========

export interface Part1Question {
  question_number: number
  image_url: string
  audio_urls: string[] // [A, B, C, D] 四個音檔 URL
  correct_answer: string // A, B, C, D
}

export interface Part1Request {
  count: number // 通常是 6 題
  difficulty: 'easy' | 'medium' | 'hard'
  provider?: 'gemini'
  model?: string
  api_key: string // Gemini API key
  accent?: string | null // 口音設定（null 表示隨機）
  pace?: string // 語速設定
}

export interface Part1Response {
  questions: Part1Question[]
}

// ========== TOEIC Part 2 應答問題類型 ==========

export interface Part2Question {
  question_number: number
  question_audio_url: string // 問句音檔
  option_audio_urls: string[] // [A, B, C] 三個選項音檔
  correct_answer: string // A, B, C
  question_text?: string // 問句文字（供答題後檢視）
  option_texts?: string[] // 選項文字（供答題後檢視）
}

export interface Part2Request {
  count: number // 通常是 25 題
  difficulty: 'easy' | 'medium' | 'hard'
  provider?: 'openai' | 'gemini'
  model?: string
  api_key: string // Gemini API key
  text_api_key?: string
  text_provider?: 'ollama' | 'openai' | 'gemini'
  text_model?: string
  tts_provider?: 'gemini'
  tts_api_key?: string
  accent?: string | null // 口音設定（null 表示隨機）
  pace?: string // 語速設定
}

export interface Part2Response {
  questions: Part2Question[]
}

// ========== TOEIC Part 3 簡短對話類型 ==========

export interface Part3QuestionSet {
  question_text: string
  options: TOEICOption[] // [A, B, C, D]
}

export interface Part3Question {
  question_number: number // 第幾組對話（1-13）
  conversation_audio_url: string // 對話音檔
  scenario: string // 場景描述
  questions: Part3QuestionSet[] // 3 個問題
  correct_answers: string[] // [A/B/C/D, A/B/C/D, A/B/C/D]
  transcript?: string // 對話逐字稿（供答題後檢視）
}

export interface Part3Request {
  count: number // 通常是 13 組對話（39 題）
  difficulty: 'easy' | 'medium' | 'hard'
  provider?: 'openai' | 'gemini'
  model?: string
  api_key: string // Gemini API key
  text_api_key?: string
  text_provider?: 'ollama' | 'openai' | 'gemini'
  text_model?: string
  tts_provider?: 'gemini'
  tts_api_key?: string
  accent?: string | null // 口音設定（null 表示隨機）
  pace?: string // 語速設定
}

export interface Part3Response {
  questions: Part3Question[]
}

// ========== TOEIC Part 4 簡短獨白類型 ==========

export interface Part4QuestionSet {
  question_text: string
  options: TOEICOption[] // [A, B, C, D]
}

export interface Part4Question {
  question_number: number // 第幾段獨白（1-10）
  talk_audio_url: string // 獨白音檔
  questions: Part4QuestionSet[] // 3 個問題
  correct_answers: string[] // [A/B/C/D, A/B/C/D, A/B/C/D]
  transcript?: string // 獨白逐字稿（供答題後檢視）
}

export interface Part4Request {
  count: number // 通常是 10 段獨白（30 題）
  difficulty: 'easy' | 'medium' | 'hard'
  provider?: 'openai' | 'gemini'
  model?: string
  api_key: string // Gemini API key
  text_api_key?: string
  text_provider?: 'ollama' | 'openai' | 'gemini'
  text_model?: string
  tts_provider?: 'gemini'
  tts_api_key?: string
  accent?: string | null // 口音設定（null 表示隨機）
  pace?: string // 語速設定
}

export interface Part4Response {
  questions: Part4Question[]
}

// ========== 聽力測驗類型 ==========

export interface ListeningTestGenerateRequest {
  difficulty?: 'easy' | 'medium' | 'hard'
  provider: 'ollama' | 'openai' | 'gemini'
  model: string
  api_key?: string
  text_provider?: 'ollama' | 'openai' | 'gemini'
  text_model?: string
  text_api_key?: string
  media_provider?: 'gemini'
  media_model?: string
  media_api_key?: string
}

export interface ListeningTestResponse {
  part1_questions: Part1Question[] // 6題照片描述
  part2_questions: Part2Question[] // 25題應答問題
  part3_questions: Part3Question[] // 13組對話 (39題)
  part4_questions: Part4Question[] // 10段獨白 (30題)
  difficulty: string
  total_count: number // 總題數 (應為 100)
}

export interface ListeningTestJobProgress {
  part1: 'pending' | 'running' | 'completed' | 'error'
  part2: 'pending' | 'running' | 'completed' | 'error'
  part3: 'pending' | 'running' | 'completed' | 'error'
  part4: 'pending' | 'running' | 'completed' | 'error'
  part1_index?: number
  part2_index?: number
  part3_index?: number
  part4_index?: number
}

export interface ListeningTestJobStatus {
  job_id: string
  status: 'pending' | 'running' | 'completed' | 'error'
  progress: ListeningTestJobProgress
  message?: string
  created_at: string
  completed_at?: string
}

// ========== 閱讀測驗類型 ==========

export interface ReadingTestGenerateRequest {
  difficulty?: 'easy' | 'medium' | 'hard'
  provider: 'ollama' | 'openai' | 'gemini'
  model: string
  api_key?: string
}

export interface ReadingTestResponse {
  part5_questions: TOEICQuestion[] // 30題句子填空
  part6_questions: TOEICQuestion[] // 16題段落填空
  part7_single_questions: TOEICQuestion[] // 29題單篇閱讀
  part7_multiple_questions: TOEICQuestion[] // 25題多篇閱讀
  difficulty: string
  total_count: number // 總題數 (應為 100)
}

export interface ReadingTestJobProgress {
  part5: 'pending' | 'running' | 'completed' | 'error'
  part6: 'pending' | 'running' | 'completed' | 'error'
  part7_single: 'pending' | 'running' | 'completed' | 'error'
  part7_multiple: 'pending' | 'running' | 'completed' | 'error'
}

export interface ReadingTestJobStatus {
  job_id: string
  status: 'pending' | 'running' | 'completed' | 'error'
  progress: ReadingTestJobProgress
  message?: string
  created_at: string
  completed_at?: string
}

// ========== 題型測驗背景任務類型 ==========

export interface QuizJobStatus {
  job_id: string
  status: 'pending' | 'running' | 'completed' | 'error'
  progress: {
    generated: number
    total: number
  }
  message?: string
  created_at: string
  completed_at?: string
}

export interface QuizJobResult {
  questions: any[]
}

export interface QuizFolderResponse {
  id: string
  name: string
  color: string
  created_at: string
}

export interface QuizLogSummary {
  id: string
  mode: string
  title: string
  count: number
  difficulty: string
  folder_id?: string | null
  created_at: string
  score?: { correct: number; total: number }
}

export interface QuizLogDetail extends QuizLogSummary {
  payload?: Record<string, any>
}
