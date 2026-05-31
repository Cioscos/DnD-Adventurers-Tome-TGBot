import Skeleton from '@/components/ui/Skeleton'

export default function InventorySkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* Weight/capacity bar */}
      <div className="rounded-2xl border border-dnd-border bg-dnd-surface px-4 py-3 space-y-2">
        <div className="flex items-center justify-between">
          <Skeleton.Line width="80px" height="10px" />
          <Skeleton.Line width="60px" height="10px" delay={40} />
        </div>
        <Skeleton.Rect height="8px" rounded="rounded-full" delay={60} />
      </div>
      {/* Item type sections */}
      {Array.from({ length: 3 }).map((_, g) => (
        <div key={g} className="space-y-1.5">
          <Skeleton.Line width="80px" height="12px" delay={g * 100} />
          {Array.from({ length: 2 }).map((_, i) => (
            <div
              key={i}
              className="rounded-2xl border border-dnd-border bg-dnd-surface px-3 py-2 flex items-center gap-3 min-h-[52px]"
            >
              <Skeleton.Circle width="36px" delay={g * 100 + i * 60 + 20} />
              <div className="flex-1 space-y-1.5">
                <Skeleton.Line width="55%" height="12px" delay={g * 100 + i * 60 + 40} />
                <Skeleton.Line width="35%" height="10px" delay={g * 100 + i * 60 + 60} />
              </div>
              <Skeleton.Circle width="28px" delay={g * 100 + i * 60 + 40} />
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
