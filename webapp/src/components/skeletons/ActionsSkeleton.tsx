import Skeleton from '@/components/ui/Skeleton'

export default function ActionsSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      <div className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 flex items-center gap-3">
        <Skeleton.Circle width="32px" />
        <div className="flex-1 space-y-1.5">
          <Skeleton.Line width="55%" height="14px" />
          <Skeleton.Line width="75%" height="10px" delay={60} />
        </div>
        <Skeleton.Rect width="84px" height="44px" rounded="rounded-lg" delay={120} />
      </div>
      {[0, 1].map((i) => (
        <div key={i} className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 flex items-center gap-3">
          <Skeleton.Circle width="24px" />
          <Skeleton.Line width="50%" height="14px" delay={i * 60} />
          <div className="flex-1" />
          <Skeleton.Rect width="84px" height="44px" rounded="rounded-lg" delay={i * 60 + 60} />
        </div>
      ))}
    </div>
  )
}
