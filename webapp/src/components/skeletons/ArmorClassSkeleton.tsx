import Skeleton from '@/components/ui/Skeleton'

export default function ArmorClassSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      <div className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 flex flex-col items-center gap-3">
        <Skeleton.Line width="80px" height="10px" />
        <Skeleton.Circle width="160px" />
        <Skeleton.Line width="48px" height="28px" delay={120} />
      </div>
      <div className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 space-y-3">
        <Skeleton.Line width="100%" height="40px" />
        <Skeleton.Line width="100%" height="40px" delay={60} />
        <Skeleton.Line width="100%" height="40px" delay={120} />
      </div>
    </div>
  )
}
