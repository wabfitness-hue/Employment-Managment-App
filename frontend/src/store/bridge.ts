import { create } from 'zustand'
import type { BridgeState } from '../types'

export interface PrintTarget {
  target_type: 'os' | 'zebra'
  target: string
}

interface PendingPrint {
  resolve: () => void
  reject: (err: Error) => void
}

interface BridgeStore extends BridgeState {
  ws: WebSocket | null
  connect: (secret: string) => void
  disconnect: () => void
  /** Resolves when the bridge confirms the print, rejects with the bridge's error message otherwise. */
  sendPrint: (pdfB64: string, requestId: string, copies?: number, printer?: PrintTarget) => Promise<void>
  sendReadOnce: (requestId: string) => void
  onTap?: (uid: string) => void
  setOnTap: (cb: ((uid: string) => void) | undefined) => void
}

export const useBridgeStore = create<BridgeStore>((set, get) => {
  const pendingPrints = new Map<string, PendingPrint>()

  return {
    status: 'disconnected',
    nfc: { available: false, reader: null },
    printer: { available: false, name: null, type: 'unknown' },
    ws: null,
    onTap: undefined,

    setOnTap: (cb) => set({ onTap: cb }),

    connect: (secret: string) => {
      const existing = get().ws
      if (existing) existing.close()

      set({ status: 'connecting' })
      const ws = new WebSocket('ws://127.0.0.1:8765')

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'auth', secret }))
      }

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data)
          switch (msg.type) {
            case 'auth_ok':
              set({ status: 'connected' })
              ws.send(JSON.stringify({ type: 'status' }))
              break
            case 'auth_fail':
              set({ status: 'error' })
              ws.close()
              break
            case 'status':
              set({ nfc: msg.nfc, printer: msg.printer })
              break
            case 'nfc_tap':
              if (typeof msg.uid === 'string' && msg.uid.length > 0 && msg.uid.length <= 64) {
                set({ lastTap: msg.uid })
                get().onTap?.(msg.uid)
              }
              break
            case 'print_ok': {
              const pending = pendingPrints.get(msg.request_id)
              if (pending) { pending.resolve(); pendingPrints.delete(msg.request_id) }
              break
            }
            case 'print_error': {
              const pending = pendingPrints.get(msg.request_id)
              if (pending) {
                pending.reject(new Error(msg.error || 'Print failed.'))
                pendingPrints.delete(msg.request_id)
              }
              break
            }
          }
        } catch { /* ignore parse errors */ }
      }

      ws.onclose = () => set({ status: 'disconnected', ws: null })
      ws.onerror = () => set({ status: 'error' })

      set({ ws })
    },

    disconnect: () => {
      get().ws?.close()
      set({ status: 'disconnected', ws: null })
    },

    sendPrint: (pdfB64, requestId, copies = 1, printer) => {
      const ws = get().ws
      if (!ws || get().status !== 'connected') {
        return Promise.reject(new Error('Bridge is not connected.'))
      }
      return new Promise<void>((resolve, reject) => {
        pendingPrints.set(requestId, { resolve, reject })
        ws.send(JSON.stringify({ type: 'print_card', request_id: requestId, pdf_b64: pdfB64, copies, printer }))
        setTimeout(() => {
          if (pendingPrints.has(requestId)) {
            pendingPrints.delete(requestId)
            reject(new Error('Print request timed out.'))
          }
        }, 30000)
      })
    },

    sendReadOnce: (requestId) => {
      get().ws?.send(JSON.stringify({ type: 'read_nfc_once', request_id: requestId }))
    },
  }
})
