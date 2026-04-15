import { useTranslation } from 'react-i18next'
import Card from '@/components/Card'
import DndInput from '@/components/DndInput'
import DndButton from '@/components/DndButton'
import { haptic } from '@/auth/telegram'

type HPOp = 'damage' | 'heal' | 'set_max' | 'set_current' | 'set_temp'

interface HpOperationFormProps {
  activeOp: HPOp
  setActiveOp: (op: HPOp) => void
  value: string
  setValue: (v: string) => void
  onApply: () => void
  isPending: boolean
  hpMutate: (args: { op: HPOp; val: number }) => void
}

const ops: { key: HPOp; label_key: string; color: string }[] = [
  { key: 'damage',      label_key: 'character.hp.damage',      color: 'bg-red-500/80' },
  { key: 'heal',        label_key: 'character.hp.heal',         color: 'bg-green-500/80' },
  { key: 'set_current', label_key: 'character.hp.set_current',  color: 'bg-blue-500/80' },
  { key: 'set_max',     label_key: 'character.hp.set_max',      color: 'bg-orange-500/80' },
  { key: 'set_temp',    label_key: 'character.hp.set_temp',     color: 'bg-cyan-500/80' },
]

export default function HpOperationForm({
  activeOp,
  setActiveOp,
  value,
  setValue,
  onApply,
  isPending,
  hpMutate,
}: HpOperationFormProps) {
  const { t } = useTranslation()

  return (
    <>
      {/* Op selector */}
      <div className="w-full flex flex-wrap gap-1">
        {ops.map((op) => (
          <button
            key={op.key}
            onClick={() => setActiveOp(op.key)}
            className={`px-3 py-1.5 rounded-xl text-sm font-medium transition-all
              ${activeOp === op.key ? op.color + ' text-white' : 'bg-dnd-surface'}`}
          >
            {t(op.label_key)}
          </button>
        ))}
      </div>

      {/* Number input */}
      <Card>
        <div className="flex flex-col gap-2">
          <DndInput
            type="number"
            min={0}
            value={value}
            onChange={setValue}
            placeholder="0"
            className="text-xl font-bold text-center"
          />
          <DndButton
            onClick={onApply}
            disabled={!value || isPending}
            loading={isPending}
            className="w-full text-lg"
          >
            {'\u2713'}
          </DndButton>
        </div>
      </Card>

      {/* Quick heal / damage shortcuts */}
      <div className="grid grid-cols-4 gap-2">
        {[1, 5, 10, 20].map((n) => (
          <button
            key={n}
            onClick={() => {
              hpMutate({ op: activeOp, val: n })
              haptic.light()
            }}
            className="py-2 rounded-xl bg-dnd-surface text-sm font-medium active:opacity-70"
          >
            {activeOp === 'damage' ? `-${n}` : activeOp === 'heal' ? `+${n}` : String(n)}
          </button>
        ))}
      </div>
    </>
  )
}
