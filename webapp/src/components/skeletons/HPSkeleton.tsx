import Skeleton from '@/components/ui/Skeleton'

export default function HPSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* Hero HP card */}
      <div className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 space-y-3">
        <div className="flex items-end justify-between gap-4">
          <div className="space-y-2">
            <Skeleton.Line width="80px" height="10px" />
            <Skeleton.Line width="72px" height="60px" delay={60} />
            <Skeleton.Line width="48px" height="16px" delay={120} />
          </div>
          <Skeleton.Rect width="64px" height="48px" rounded="rounded-xl" delay={80} />
        </div>
        <Skeleton.Rect height="12px" rounded="rounded-full" delay={160} />
      </div>
      {/* Operation form */}
      <div className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 space-y-3">
        <Skeleton.Rect height="44px" rounded="rounded-xl" delay={80} />
        <div className="grid grid-cols-3 gap-2">
          <Skeleton.Rect height="36px" rounded="rounded-xl" delay={100} />
          <Skeleton.Rect height="36px" rounded="rounded-xl" delay={140} />
          <Skeleton.Rect height="36px" rounded="rounded-xl" delay={180} />
        </div>
      </div>
      {/* Rest buttons */}
      <div className="grid grid-cols-2 gap-2">
        <Skeleton.Rect height="44px" rounded="rounded-xl" delay={200} />
        <Skeleton.Rect height="44px" rounded="rounded-xl" delay={240} />
      </div>
    </div>
  )
}
