import Skeleton from '@/components/ui/Skeleton'

export default function MulticlassSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* Class card */}
      {Array.from({ length: 2 }).map((_, i) => (
        <div
          key={i}
          className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 space-y-3"
        >
          <div className="flex items-center justify-between">
            <div className="space-y-1.5">
              <Skeleton.Line width="80px" height="14px" delay={i * 80} />
              <Skeleton.Line width="120px" height="10px" delay={i * 80 + 30} />
            </div>
            <Skeleton.Line width="36px" height="28px" delay={i * 80 + 20} />
          </div>
          {/* Resource bar */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Skeleton.Line width="60%" height="10px" delay={i * 80 + 40} />
              <Skeleton.Line width="30px" height="10px" delay={i * 80 + 60} />
            </div>
            <Skeleton.Rect height="8px" rounded="rounded-full" delay={i * 80 + 60} />
          </div>
        </div>
      ))}
      {/* Add class button */}
      <Skeleton.Rect height="44px" rounded="rounded-xl" delay={200} />
    </div>
  )
}
