import Skeleton from '@/components/ui/Skeleton'

export default function AbilitiesSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* Add button */}
      <Skeleton.Rect height="44px" rounded="rounded-xl" />
      {/* Ability cards */}
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 space-y-2"
        >
          <div className="flex items-center justify-between">
            <Skeleton.Line width="50%" height="14px" delay={i * 80} />
            <div className="flex gap-2">
              <Skeleton.Circle width="28px" delay={i * 80 + 30} />
              <Skeleton.Circle width="28px" delay={i * 80 + 60} />
            </div>
          </div>
          <Skeleton.Line width="80%" height="10px" delay={i * 80 + 40} />
          <Skeleton.Rect height="8px" rounded="rounded-full" delay={i * 80 + 60} />
        </div>
      ))}
    </div>
  )
}
