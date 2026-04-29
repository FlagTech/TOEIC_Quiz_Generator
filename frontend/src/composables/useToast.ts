/**
 * Toast 通知 Composable
 * 提供簡單的 toast 通知功能
 */
import { useToast as useToastification } from 'vue-toastification'

export interface ToastOptions {
  message: string
  type?: 'success' | 'error' | 'info' | 'warning'
  duration?: number
}

export function useToast() {
  const toast = useToastification()

  const show = (options: ToastOptions | string) => {
    const opts: ToastOptions = typeof options === 'string'
      ? { message: options, type: 'info' }
      : options

    const message = opts.message
    const type = opts.type || 'info'
    const duration = opts.duration || 3000
    toast[type](message, { timeout: duration })
  }

  return {
    success: (message: string, duration?: number) => show({ message, type: 'success', duration }),
    error: (message: string, duration?: number) => show({ message, type: 'error', duration }),
    warning: (message: string, duration?: number) => show({ message, type: 'warning', duration }),
    info: (message: string, duration?: number) => show({ message, type: 'info', duration }),
    show
  }
}
