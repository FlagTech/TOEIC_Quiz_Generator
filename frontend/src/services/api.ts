/**
 * API 服務層 - TOEIC Quiz Generator
 * 只包含測驗生成相關的 API 調用
 */
import axios, { type AxiosInstance } from 'axios'
import type {
  TOEICGenerateRequest,
  TOEICQuizResponse,
  TOEICExplainRequest,
  TOEICExplanation,
  Part1Request,
  Part1Response,
  Part2Request,
  Part2Response,
  Part3Request,
  Part3Response,
  Part4Request,
  Part4Response,
  ListeningTestJobStatus,
  ListeningTestResponse,
  ReadingTestJobStatus,
  ReadingTestResponse,
  QuizJobStatus,
  QuizJobResult,
  QuizFolderResponse,
  QuizLogSummary,
  QuizLogDetail
} from '@/types'

// 創建一個包裝的 API 實例，讓 TypeScript 知道返回的是 data 而不是 AxiosResponse
interface ApiInstance extends AxiosInstance {
  get<T = unknown>(url: string, config?: Parameters<AxiosInstance['get']>[1]): Promise<T>
  post<T = unknown>(url: string, data?: unknown, config?: Parameters<AxiosInstance['post']>[2]): Promise<T>
  put<T = unknown>(url: string, data?: unknown, config?: Parameters<AxiosInstance['put']>[2]): Promise<T>
  delete<T = unknown>(url: string, config?: Parameters<AxiosInstance['delete']>[1]): Promise<T>
}

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
}) as ApiInstance

// 請求攔截器
api.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 響應攔截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

// ========== TOEIC 閱讀測驗 API (Part 5-7) ==========

export const toeicAPI = {
  /**
   * 生成 TOEIC 考題（需要較長時間，設置 120 秒超時）
   */
  generateQuestions: (data: TOEICGenerateRequest) =>
    api.post<TOEICQuizResponse>('/toeic/generate', data, {
      timeout: 120000
    }),
  
  // 背景任務 API
  startReadingJob: (data: TOEICGenerateRequest) =>
    api.post<QuizJobStatus>('/toeic/generate-job', data),
  getReadingJobStatus: (jobId: string) =>
    api.get<QuizJobStatus>(`/toeic/generate-job/${jobId}`),
  getReadingJobResult: (jobId: string) =>
    api.get<QuizJobResult>(`/toeic/generate-job/${jobId}/result`),

  /**
   * 生成考題詳解
   */
  generateExplanations: (data: TOEICExplainRequest) =>
    api.post<TOEICExplanation[]>('/toeic/explain', data, {
      timeout: 120000
    }),
  
  // 資料夾管理
  getQuizFolders: () =>
    api.get<QuizFolderResponse[]>('/toeic/quiz-folders'),
  createQuizFolder: (data: { name: string; color: string }) =>
    api.post<QuizFolderResponse>('/toeic/quiz-folders', data),
  updateQuizFolder: (folderId: string, data: { name?: string; color?: string }) =>
    api.put<QuizFolderResponse>(`/toeic/quiz-folders/${folderId}`, data),
  deleteQuizFolder: (folderId: string) =>
    api.delete<{ message: string }>(`/toeic/quiz-folders/${folderId}`),
  
  // 測驗記錄管理
  getQuizLogs: () =>
    api.get<QuizLogSummary[]>('/toeic/quiz-logs'),
  createQuizLog: (data: { mode: string; title: string; count: number; difficulty: string; folder_id?: string | null }) =>
    api.post<QuizLogSummary>('/toeic/quiz-logs', data),
  getQuizLog: (logId: string) =>
    api.get<QuizLogDetail>(`/toeic/quiz-logs/${logId}`),
  updateQuizLog: (logId: string, data: { title?: string; folder_id?: string | null; payload?: Record<string, any>; score?: Record<string, any> | null }) =>
    api.put<QuizLogDetail>(`/toeic/quiz-logs/${logId}`, data),
  deleteQuizLog: (logId: string) =>
    api.delete<{ message: string }>(`/toeic/quiz-logs/${logId}`),

  /**
   * 聽力測驗完整模擬
   */
  startListeningTestJob: (data: any) =>
    api.post<ListeningTestJobStatus>('/toeic/listening-test/job', data),
  resumeListeningTestJob: (jobId: string, data: any) =>
    api.post<ListeningTestJobStatus>(`/toeic/listening-test/job/${jobId}/resume`, data),
  getListeningTestJobStatus: (jobId: string) =>
    api.get<ListeningTestJobStatus>(`/toeic/listening-test/job/${jobId}`),
  getListeningTestJobResult: (jobId: string) =>
    api.get<ListeningTestResponse>(`/toeic/listening-test/job/${jobId}/result`),
  cancelListeningTestJob: (jobId: string) =>
    api.delete<{ message: string }>(`/toeic/listening-test/job/${jobId}`),

  /**
   * 匯出 PDF（題目本 / 答案卡）
   */
  exportPDF: (data: { test_data: any; export_mode: 'questions_only' | 'answer_key' | 'both'; include_user_answers?: boolean }) =>
    axios.post('/api/toeic/export-pdf', data, {
      responseType: 'blob',
      timeout: 120000,
    }).then(res => res.data as Blob),

  /**
   * 閱讀測驗完整模擬
   */
  startReadingTestJob: (data: any) =>
    api.post<ReadingTestJobStatus>('/toeic/reading-test/job', data),
  resumeReadingTestJob: (jobId: string, data: any) =>
    api.post<ReadingTestJobStatus>(`/toeic/reading-test/job/${jobId}/resume`, data),
  getReadingTestJobStatus: (jobId: string) =>
    api.get<ReadingTestJobStatus>(`/toeic/reading-test/job/${jobId}`),
  getReadingTestJobResult: (jobId: string) =>
    api.get<ReadingTestResponse>(`/toeic/reading-test/job/${jobId}/result`),
  cancelReadingTestJob: (jobId: string) =>
    api.delete<{ message: string }>(`/toeic/reading-test/job/${jobId}`)
}

// ========== TOEIC 聽力測驗 API (Part 1-4) ==========

export const listeningAPI = {
  /**
   * Part 1: 照片描述題（使用 DALL-E 3 生成圖片）
   */
  generatePart1: (data: Part1Request) =>
    api.post<Part1Response>('/listening/generate-part1', data, {
      timeout: 180000
    }),
  startPart1Job: (data: Part1Request) =>
    api.post<QuizJobStatus>('/listening/generate-part1-job', data),

  /**
   * Part 2: 應答問題
   */
  generatePart2: (data: Part2Request) =>
    api.post<Part2Response>('/listening/generate-part2', data, {
      timeout: 120000
    }),
  startPart2Job: (data: Part2Request) =>
    api.post<QuizJobStatus>('/listening/generate-part2-job', data),

  /**
   * Part 3: 簡短對話
   */
  generatePart3: (data: Part3Request) =>
    api.post<Part3Response>('/listening/generate-part3', data, {
      timeout: 180000
    }),
  startPart3Job: (data: Part3Request) =>
    api.post<QuizJobStatus>('/listening/generate-part3-job', data),

  /**
   * Part 4: 簡短獨白
   */
  generatePart4: (data: Part4Request) =>
    api.post<Part4Response>('/listening/generate-part4', data, {
      timeout: 180000
    }),
  startPart4Job: (data: Part4Request) =>
    api.post<QuizJobStatus>('/listening/generate-part4-job', data),
  
  // 背景任務狀態查詢
  getListeningJobStatus: (jobId: string) =>
    api.get<QuizJobStatus>(`/listening/generate-job/${jobId}`),
  getListeningJobResult: (jobId: string) =>
    api.get<QuizJobResult>(`/listening/generate-job/${jobId}/result`),

  /**
   * 生成聽力測驗詳解
   */
  generateListeningExplanations: (data: {
    test_mode: string
    answers: any[]
    provider: string
    model: string
    api_key?: string
  }) =>
    api.post<any[]>('/listening/explain', data, {
      timeout: 120000
    })
}

export default api
