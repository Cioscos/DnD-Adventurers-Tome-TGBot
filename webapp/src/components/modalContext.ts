import { createContext, useContext, type ReactNode } from 'react'

export interface ModalOptions {
  content: ReactNode
  dismissible?: boolean
}

export interface ModalContextValue {
  openModal: (options: ModalOptions) => void
  closeModal: () => void
  isModalOpen: boolean
}

export const ModalContext = createContext<ModalContextValue | null>(null)

export function useModal() {
  const ctx = useContext(ModalContext)
  if (!ctx) throw new Error('useModal must be used within ModalProvider')
  return ctx
}
