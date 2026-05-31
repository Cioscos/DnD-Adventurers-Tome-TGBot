import Skeleton from '@/components/ui/Skeleton'

export default function SpellSlotsSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* Mode banner */}
      <div className="rounded-2xl border border-dnd-border bg-dnd-surface px-4 py-3 flex items-start gap-2.5">
        <Skeleton.Circle width="20px" delay={0} />
        <Skeleton.Line width="80%" height="12px" delay={40} />
      </div>
      {/* Slot level rows */}
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="rounded-2xl border border-dnd-border bg-dnd-surface px-4 py-3 space-y-2"
        >
          <div className="flex items-center justify-between">
            <Skeleton.Line width="60px" height="12px" delay={i * 60} />
            <div className="flex gap-2">
              <Skeleton.Circle width="32px" delay={i * 60 + 30} />
              <Skeleton.Circle width="32px" delay={i * 60 + 60} />
              <Skeleton.Circle width="32px" delay={i * 60 + 90} />
            </div>
          </div>
          <Skeleton.Rect height="8px" rounded="rounded-full" delay={i * 60 + 40} />
        </div>
      ))}
    </div>
  )
}
