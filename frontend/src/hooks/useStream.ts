/**
 * 连接全局 StreamStore 的 React Hook
 */

import { useSyncExternalStore } from 'react'
import { streamStore, type StreamState } from '../stores/streamStore'

export function useStream(): StreamState {
  return useSyncExternalStore(
    (callback) => streamStore.subscribe(callback),
    () => streamStore.getState(),
  )
}
