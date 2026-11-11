import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import BeastOrders from '@/components/character/BeastOrders'
import type { CharacterFull, Companion, TurnBlock } from '@/types'

const { list, command, toastError, notifyMutationError } = vi.hoisted(() => ({
  list: vi.fn(), command: vi.fn(), toastError: vi.fn(), notifyMutationError: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: { companions: { list, command } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('react-i18next', async (orig) => ({
  ...((await orig()) as Record<string, unknown>),
  useTranslation: () => ({ t: (k: string, o?: { n?: number }) => (o?.n !== undefined ? `${k}:${o.n}` : k), i18n: { language: 'it' } }),
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError, info: vi.fn(), success: vi.fn() }) }))
vi.mock('@/lib/mutationError', async (orig) => ({ ...(await orig<typeof import('@/lib/mutationError')>()), notifyMutationError }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const ability = (feature_key: string) => ({ id: 1, feature_key, name: feature_key }) as never
const master = (...extra: string[]) =>
  ({ id: 7, abilities: [ability('ranger.rangers_companion'), ...extra.map(ability)] }) as unknown as CharacterFull
const beast = (current_hp = 13) =>
  ({ id: 3, name: 'Pantera', feature_key: 'ranger.rangers_companion', current_hp, max_hp: 13 }) as unknown as Companion

beforeEach(() => {
  list.mockReset().mockResolvedValue([beast()])
  command.mockReset().mockResolvedValue({ command: 'attack', bonus: false, attacks_left: 1 })
  toastError.mockReset()
  notifyMutationError.mockReset()
})

describe('BeastOrders (Compagno del Ranger: ordini alla bestia)', () => {
  it('shows nothing to a character without the Beast Master companion', () => {
    const { container } = renderWithProviders(<BeastOrders char={{ id: 7, abilities: [] } as unknown as CharacterFull} />)
    expect(container).toBeEmptyDOMElement()
    expect(list).not.toHaveBeenCalled()
  })

  it('offers the five action orders and sends the chosen one with the action', async () => {
    renderWithProviders(<BeastOrders char={master()} />)
    for (const c of ['attack', 'help', 'disengage', 'dash', 'dodge']) {
      expect(await screen.findByText(`character.extras.beast.orders.${c}`)).toBeInTheDocument()
    }
    expect(screen.queryByText('character.extras.beast.bonus_orders')).toBeNull()  // niente Addestramento Straordinario
    await userEvent.click(screen.getByText('character.extras.beast.orders.dodge'))
    await waitFor(() => expect(command).toHaveBeenCalledWith(7, 3, 'dodge', false))
  })

  it('with Exceptional Training adds the four bonus action orders, never the attack', async () => {
    renderWithProviders(<BeastOrders char={master('ranger.exceptional_training')} />)
    expect(await screen.findByText('character.extras.beast.bonus_orders')).toBeInTheDocument()
    const dash = screen.getAllByText('character.extras.beast.orders.dash')
    expect(dash).toHaveLength(2)  // una con l'azione, una con l'azione bonus
    expect(screen.getAllByText('character.extras.beast.orders.attack')).toHaveLength(1)
    await userEvent.click(dash[1])
    await waitFor(() => expect(command).toHaveBeenCalledWith(7, 3, 'dash', true))
  })

  it('for the 2024 primal beast offers only the strike with an attack given up, and every order with the bonus action', async () => {
    list.mockResolvedValue([{ ...beast(), feature_key: 'ranger.primal_companion' }])
    renderWithProviders(<BeastOrders char={{ id: 7, abilities: [ability('ranger.primal_companion')] } as unknown as CharacterFull} />)
    expect(await screen.findByText('character.extras.beast.primal_action_orders')).toBeInTheDocument()
    expect(screen.getAllByText('character.extras.beast.orders.attack')).toHaveLength(2)  // rinunciando a un attacco e con l'azione bonus
    const dodge = screen.getAllByText('character.extras.beast.orders.dodge')
    expect(dodge).toHaveLength(1)  // solo con l'azione bonus
    await userEvent.click(dodge[0])
    await waitFor(() => expect(command).toHaveBeenCalledWith(7, 3, 'dodge', true))
  })

  it('tells how many attacks the beast has left this turn', async () => {
    renderWithProviders(<BeastOrders char={master()} turn={{ beast: { id: 3, attacks_left: 2 } } as unknown as TurnBlock} />)
    expect(await screen.findByText('character.extras.beast.attacks_left:2')).toBeInTheDocument()
  })

  it('explains a refused order instead of failing silently', async () => {
    const { ApiError } = await import('@/api/client')
    command.mockRejectedValue(new ApiError(409, { code: 'turn_slot_used' }))
    renderWithProviders(<BeastOrders char={master()} />)
    await userEvent.click(await screen.findByText('character.extras.beast.orders.help'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.extras.beast.errors.turn_slot_used'))
    command.mockRejectedValue(new ApiError(500, 'boom'))
    await userEvent.click(screen.getByText('character.extras.beast.orders.help'))
    await waitFor(() => expect(notifyMutationError).toHaveBeenCalled())
  })

  it('says there is no living beast and gives no order buttons', async () => {
    list.mockResolvedValue([beast(0)])
    renderWithProviders(<BeastOrders char={master()} />)
    expect(await screen.findByText('character.extras.beast.none')).toBeInTheDocument()
    expect(screen.queryByText('character.extras.beast.orders.attack')).toBeNull()
  })

  it('for the 2024 primal beast does not send the player to the Extras page when no beast is alive', async () => {
    list.mockResolvedValue([{ ...beast(0), feature_key: 'ranger.primal_companion' }])
    renderWithProviders(<BeastOrders char={{ id: 7, abilities: [ability('ranger.primal_companion')] } as unknown as CharacterFull} />)
    expect(await screen.findByText('character.extras.beast.primal_none')).toBeInTheDocument()
    expect(screen.queryByText('character.extras.beast.none')).toBeNull()
  })
})
