import { describe, it, expect, beforeEach } from 'vitest'
import { enqueue, peek, dequeue, clear, pruneOlderThan, type Reward } from '@/lib/rewardQueue'

const reward = (over: Partial<Reward> = {}): Reward => ({
  message_id: 1,
  item_id: 1,
  item_name: 'Potion',
  item_quantity: 1,
  char_id: 7,
  granted_at: new Date().toISOString(),
  ...over,
})

beforeEach(() => sessionStorage.clear())

describe('rewardQueue', () => {
  it('enqueue then peek returns the head without removing it', () => {
    enqueue(reward({ message_id: 1 }))
    expect(peek()?.message_id).toBe(1)
    expect(peek()?.message_id).toBe(1)
  })

  it('dedups by message_id', () => {
    enqueue(reward({ message_id: 5 }))
    enqueue(reward({ message_id: 5 }))
    expect(dequeue()?.message_id).toBe(5)
    expect(peek()).toBeNull()
  })

  it('dequeues in FIFO order', () => {
    enqueue(reward({ message_id: 1 }))
    enqueue(reward({ message_id: 2 }))
    expect(dequeue()?.message_id).toBe(1)
    expect(dequeue()?.message_id).toBe(2)
    expect(dequeue()).toBeNull()
  })

  it('clear empties the queue', () => {
    enqueue(reward())
    clear()
    expect(peek()).toBeNull()
  })

  it('pruneOlderThan drops entries past the max age, keeping fresh ones', () => {
    enqueue(reward({ message_id: 1, granted_at: new Date(Date.now() - 10_000).toISOString() }))
    enqueue(reward({ message_id: 2, granted_at: new Date().toISOString() }))
    pruneOlderThan(5_000)
    expect(dequeue()?.message_id).toBe(2)
    expect(peek()).toBeNull()
  })
})
