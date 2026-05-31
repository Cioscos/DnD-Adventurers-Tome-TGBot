import Skeleton from '@/components/ui/Skeleton'

export default function SpellsSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* Search bar */}
      <Skeleton.Rect height="44px" rounded="rounded-xl" />
      {/* Spell level group */}
      <div className="space-y-1.5">
        <Skeleton.Line width="80px" height="12px" delay={40} />
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="rounded-2xl border border-dnd-border bg-dnd-surface px-3 py-2 flex items-center gap-3 min-h-[52px]"
          >
            <Skeleton.Circle width="36px" delay={60 + i * 60} />
            <div className="flex-1 space-y-1.5">
              <Skeleton.Line width="55%" height="12px" delay={80 + i * 60} />
              <Skeleton.Line width="35%" height="10px" delay={100 + i * 60} />
            </div>
            <Skeleton.Line width="24px" height="24px" delay={80 + i * 60} />
          </div>
        ))}
      </div>
      {/* Another level group */}
      <div className="space-y-1.5">
        <Skeleton.Line width="80px" height="12px" delay={200} />
        {Array.from({ length: 2 }).map((_, i) => (
          <div
            key={i}
            className="rounded-2xl border border-dnd-border bg-dnd-surface px-3 py-2 flex items-center gap-3 min-h-[52px]"
          >
            <Skeleton.Circle width="36px" delay={220 + i * 60} />
            <div className="flex-1 space-y-1.5">
              <Skeleton.Line width="50%" height="12px" delay={240 + i * 60} />
              <Skeleton.Line width="30%" height="10px" delay={260 + i * 60} />
            </div>
            <Skeleton.Line width="24px" height="24px" delay={240 + i * 60} />
          </div>
        ))}
      </div>
    </div>
  )
}
