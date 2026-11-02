import { Reorder, useDragControls } from 'framer-motion'
import { GripVertical } from 'lucide-react'
import Pressable from '@/components/ui/Pressable'

// File a parte e caricato in lazy: Reorder usa motion.* (non m.*) e si porta dietro
// tutto framer-motion, che serve solo a editor delle azioni rapide aperto.

function OrderRow({ id, label, handleLabel, onDragEnd }: {
  id: string; label: string; handleLabel: string; onDragEnd: () => void
}) {
  const controls = useDragControls()
  return (
    <Reorder.Item
      value={id}
      dragListener={false}
      dragControls={controls}
      onDragEnd={onDragEnd}
      className="flex items-center gap-2 pl-3 rounded-xl border bg-dnd-surface border-dnd-border list-none"
    >
      <span className="flex-1 min-w-0 truncate text-sm font-body text-dnd-text">{label}</span>
      <Pressable
        type="button"
        aria-label={handleLabel}
        onPointerDown={(e) => controls.start(e)}
        className="w-11 h-11 flex items-center justify-center shrink-0 text-dnd-text-muted touch-none cursor-grab"
      >
        <GripVertical size={18} />
      </Pressable>
    </Reorder.Item>
  )
}

export default function QuickActionsOrderList({ items, handleLabel, onReorder, onDragEnd }: {
  items: { key: string; label: string }[]
  handleLabel: string
  onReorder: (keys: string[]) => void
  onDragEnd: () => void
}) {
  return (
    <Reorder.Group
      axis="y"
      as="ul"
      values={items.map((i) => i.key)}
      onReorder={onReorder}
      className="space-y-1 p-0 m-0"
    >
      {items.map(({ key, label }) => (
        <OrderRow key={key} id={key} label={label} handleLabel={handleLabel} onDragEnd={onDragEnd} />
      ))}
    </Reorder.Group>
  )
}
