import { ref } from 'vue'
import JSZip from 'jszip'
import { toeicAPI } from '@/services/api'
import { notifySidebarDataUpdated } from '@/utils/testHistory'
import { useToast } from '@/composables/useToast'
import type { QuizFolderResponse, QuizLogDetail } from '@/types'

const APP_NAME = 'TOEIC Quiz Generator' as const
const EXPORT_VERSION = '1.0' as const

interface ExportData {
  version: typeof EXPORT_VERSION
  exported_at: string
  app: typeof APP_NAME
  folders: QuizFolderResponse[]
  logs: QuizLogDetail[]
}

function collectMediaUrls(obj: unknown, found = new Set<string>()): Set<string> {
  if (!obj) return found
  if (typeof obj === 'string') {
    if (obj.startsWith('/audio/') || obj.startsWith('/images/part1/')) found.add(obj)
    return found
  }
  if (Array.isArray(obj)) { obj.forEach(v => collectMediaUrls(v, found)); return found }
  if (typeof obj === 'object') { Object.values(obj as Record<string, unknown>).forEach(v => collectMediaUrls(v, found)) }
  return found
}

export function useExportImport() {
  const toast = useToast()
  const isExporting = ref(false)
  const isImporting = ref(false)
  const exportProgress = ref('')
  const importProgress = ref('')

  async function exportAll() {
    if (isExporting.value) return
    isExporting.value = true
    exportProgress.value = '讀取記錄中...'
    try {
      const [folders, summaries] = await Promise.all([
        toeicAPI.getQuizFolders(),
        toeicAPI.getQuizLogs(),
      ])
      if (summaries.length === 0) {
        toast.warning('目前沒有任何測驗記錄可以匯出')
        return
      }

      exportProgress.value = '讀取題目內容中...'
      const results = await Promise.allSettled(summaries.map(s => toeicAPI.getQuizLog(s.id)))
      const logs: QuizLogDetail[] = results.map((r, i) =>
        r.status === 'fulfilled' ? r.value : (summaries[i] as QuizLogDetail)
      )

      const zip = new JSZip()

      const exportData: ExportData = {
        version: EXPORT_VERSION,
        exported_at: new Date().toISOString(),
        app: APP_NAME,
        folders,
        logs,
      }
      zip.file('data.json', JSON.stringify(exportData, null, 2))

      const mediaUrls = collectMediaUrls(logs)
      const urlArr = Array.from(mediaUrls)

      let downloaded = 0
      for (const url of urlArr) {
        exportProgress.value = `打包媒體檔案... ${++downloaded}/${urlArr.length}`
        try {
          const res = await fetch(url)
          if (!res.ok) continue
          const blob = await res.blob()
          const zipPath = url.startsWith('/') ? url.slice(1) : url
          zip.file(zipPath, blob)
        } catch {
          // skip unavailable files
        }
      }

      exportProgress.value = '壓縮中...'
      const blob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE' })

      const blobUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = `toeic_records_${new Date().toISOString().slice(0, 10)}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)

      toast.success(`匯出成功！共 ${logs.length} 筆記錄、${downloaded} 個媒體檔案`)
    } catch (e) {
      console.error('Export failed:', e)
      toast.error('匯出失敗，請稍後再試')
    } finally {
      isExporting.value = false
      exportProgress.value = ''
    }
  }

  async function importAll(file: File) {
    if (isImporting.value) return
    isImporting.value = true
    importProgress.value = '讀取檔案中...'
    try {
      const zip = await JSZip.loadAsync(file)

      const jsonFile = zip.file('data.json')
      if (!jsonFile) { toast.error('無效的匯入檔案：找不到 data.json'); return }
      let data: ExportData
      try {
        data = JSON.parse(await jsonFile.async('string'))
      } catch {
        toast.error('無效的匯入檔案：data.json 格式錯誤')
        return
      }
      if (data.app !== APP_NAME || data.version !== EXPORT_VERSION) {
        toast.error('無效的匯入檔案：不是 TOEIC Quiz Generator 的匯出檔')
        return
      }
      if (!Array.isArray(data.folders) || !Array.isArray(data.logs)) {
        toast.error('無效的匯入檔案：資料結構不正確')
        return
      }

      const mediaFiles = Object.keys(zip.files).filter(p =>
        (p.startsWith('audio/') || p.startsWith('images/')) && !zip.files[p]?.dir
      )
      let uploadedMedia = 0
      for (const zipPath of mediaFiles) {
        importProgress.value = `上傳媒體檔案... ${++uploadedMedia}/${mediaFiles.length}`
        try {
          const zipEntry = zip.files[zipPath]
          if (!zipEntry) continue
          const blob = await zipEntry.async('blob')
          const filename = zipPath.split('/').pop()!
          const fileObj = new File([blob], filename)
          if (zipPath.startsWith('audio/')) {
            await toeicAPI.uploadAudio(fileObj)
          } else {
            await toeicAPI.uploadImage(fileObj)
          }
        } catch (e) {
          console.warn(`Failed to upload media ${zipPath}:`, e)
        }
      }

      importProgress.value = '匯入資料夾中...'
      const existingFolders = await toeicAPI.getQuizFolders()
      const byName = new Map(existingFolders.map(f => [f.name, f]))
      const folderIdMap = new Map<string, string>()

      for (const folder of data.folders) {
        const existing = byName.get(folder.name)
        if (existing) {
          folderIdMap.set(folder.id, existing.id)
        } else {
          try {
            const created = await toeicAPI.createQuizFolder({ name: folder.name, color: folder.color })
            folderIdMap.set(folder.id, created.id)
            byName.set(folder.name, created)
          } catch (e) {
            console.warn(`Failed to create folder "${folder.name}":`, e)
          }
        }
      }

      const existingIds = new Set((await toeicAPI.getQuizLogs()).map(l => l.id))

      const total = data.logs.length
      let created = 0, skipped = 0, failed = 0
      for (let i = 0; i < data.logs.length; i++) {
        const log = data.logs[i]!
        importProgress.value = `匯入題目記錄... ${i + 1}/${total}`

        if (existingIds.has(log.id)) {
          skipped++
          continue
        }

        const remappedFolderId = log.folder_id ? (folderIdMap.get(log.folder_id) ?? null) : null
        try {
          const newLog = await toeicAPI.createQuizLog({
            id: log.id,
            mode: log.mode,
            title: log.title,
            count: log.count,
            difficulty: log.difficulty,
            folder_id: remappedFolderId,
          })
          const hasPayload = log.payload && Object.keys(log.payload).length > 0
          if (hasPayload || log.score != null) {
            await toeicAPI.updateQuizLog(newLog.id, {
              payload: log.payload,
              score: log.score ?? undefined,
            })
          }
          created++
        } catch (e) {
          console.warn(`Failed to import log "${log.title}":`, e)
          failed++
        }
      }

      notifySidebarDataUpdated()

      if (created === 0 && skipped > 0 && failed === 0) {
        toast.warning(`所有 ${skipped} 筆記錄已存在，略過匯入`)
      } else if (failed === 0) {
        const skipNote = skipped > 0 ? `，${skipped} 筆已略過` : ''
        toast.success(`匯入完成！${created} 筆記錄、${uploadedMedia} 個媒體檔案${skipNote}`)
      } else {
        toast.warning(`匯入部分完成：${created} 筆成功，${skipped} 筆略過，${failed} 筆失敗`)
      }
    } catch (e) {
      console.error('Import failed:', e)
      toast.error('匯入失敗，請確認檔案是否為有效的 .zip 格式')
    } finally {
      isImporting.value = false
      importProgress.value = ''
    }
  }

  return { isExporting, isImporting, exportProgress, importProgress, exportAll, importAll }
}
