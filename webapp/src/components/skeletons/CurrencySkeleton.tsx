import Skeleton from '@/components/ui/Skeleton'

export default function CurrencySkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* 5 coin rows */}
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="rounded-2xl border border-dnd-border bg-dnd-surface px-4 py-3 flex items-center gap-3"
        >
          <Skeleton.Circle width="44px" delay={i * 60} />
          <div className="flex-1 space-y-1.5">
            <Skeleton.Line width="40px" height="10px" delay={i * 60 + 20} />
            <Skeleton.Line width="60px" height="24px" delay={i * 60 + 40} />
          </div>
          <Skeleton.Rect width="80px" height="40px" rounded="rounded-xl" delay={i * 60 + 30} />
        </div>
      ))}
      {/* Save button */}
      <Skeleton.Rect height="44px" rounded="rounded-xl" delay={320} />
    </div>
  )
}
