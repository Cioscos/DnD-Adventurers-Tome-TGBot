import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useToast } from '@/hooks/useToast'
import { toast } from 'sonner'
import { haptic } from '@/auth/telegram'

const { sonner, hap } = vi.hoisted(() => ({
  sonner: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }),
  hap: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), light: vi.fn() },
}))
vi.mock('sonner', () => ({ toast: sonner }))
vi.mock('@/auth/telegram', () => ({ haptic: hap }))

beforeEach(() => {
  sonner.mockClear()
  sonner.success.mockClear(); sonner.error.mockClear(); sonner.warning.mockClear(); sonner.info.mockClear()
  Object.values(hap).forEach((f) => f.mockClear())
})

describe('useToast', () => {
  it('success routes to sonner.success + success haptic', () => {
    useToast().success('Salvato')
    expect(toast.success).toHaveBeenCalledWith('Salvato', expect.anything())
    expect(haptic.success).toHaveBeenCalledTimes(1)
  })

  it('error routes to sonner.error + error haptic', () => {
    useToast().error('Ops')
    expect(toast.error).toHaveBeenCalledWith('Ops', expect.anything())
    expect(haptic.error).toHaveBeenCalledTimes(1)
  })

  it('the default toast routes to sonner() with a light haptic', () => {
    useToast().toast('Ciao')
    expect(toast).toHaveBeenCalledWith('Ciao', expect.anything())
    expect(haptic.light).toHaveBeenCalledTimes(1)
  })

  it('suppresses haptic when hapticFeedback is false', () => {
    useToast().success('x', { hapticFeedback: false })
    expect(toast.success).toHaveBeenCalledTimes(1)
    expect(haptic.success).not.toHaveBeenCalled()
  })
})
