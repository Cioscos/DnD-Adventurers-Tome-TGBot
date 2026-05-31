import Skeleton from '@/components/ui/Skeleton'

export default function ExperienceSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* XP hero card */}
      <div className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="space-y-1.5">
            <Skeleton.Line width="80px" height="10px" />
            <Skeleton.Line width="100px" height="40px" delay={40} />
          </div>
          <div className="space-y-1.5 items-end flex flex-col">
            <Skeleton.Line width="50px" height="10px" delay={20} />
            <Skeleton.Line width="40px" height="28px" delay={60} />
          </div>
        </div>
        <Skeleton.Rect height="12px" rounded="rounded-full" delay={80} />
        <Skeleton.Line width="60%" height="10px" delay={100} />
      </div>
      {/* Quick-add preset chips */}
      <div className="flex gap-2 flex-wrap">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton.Rect key={i} width="60px" height="36px" rounded="rounded-xl" delay={120 + i * 30} />
        ))}
      </div>
      {/* Add XP input row */}
      <div className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 flex gap-2 items-end">
        <Skeleton.Rect className="flex-1" height="44px" rounded="rounded-xl" delay={240} />
        <Skeleton.Rect width="80px" height="44px" rounded="rounded-xl" delay={280} />
      </div>
    </div>
  )
}
