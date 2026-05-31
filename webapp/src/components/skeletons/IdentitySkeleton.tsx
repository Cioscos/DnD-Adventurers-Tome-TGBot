import Skeleton from '@/components/ui/Skeleton'

export default function IdentitySkeleton() {
  return (
    <div className="space-y-4" aria-hidden>
      {/* Name / race / background fields */}
      <div className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 space-y-3">
        <Skeleton.Line width="60px" height="10px" />
        <Skeleton.Rect height="44px" rounded="rounded-xl" delay={40} />
        <Skeleton.Line width="60px" height="10px" delay={60} />
        <Skeleton.Rect height="44px" rounded="rounded-xl" delay={80} />
        <Skeleton.Line width="60px" height="10px" delay={100} />
        <Skeleton.Rect height="44px" rounded="rounded-xl" delay={120} />
      </div>
      {/* Personality traits block */}
      <div className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 space-y-3">
        <Skeleton.Line width="120px" height="10px" delay={140} />
        <Skeleton.Rect height="72px" rounded="rounded-xl" delay={160} />
      </div>
      {/* Languages / proficiencies chips */}
      <div className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 space-y-3">
        <Skeleton.Line width="80px" height="10px" delay={180} />
        <div className="flex gap-2 flex-wrap">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton.Rect key={i} width="64px" height="28px" rounded="rounded-full" delay={200 + i * 30} />
          ))}
        </div>
      </div>
      {/* Save button */}
      <Skeleton.Rect height="44px" rounded="rounded-xl" delay={320} />
    </div>
  )
}
