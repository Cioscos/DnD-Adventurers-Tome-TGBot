import Skeleton from '@/components/ui/Skeleton'

/** Mirrors the inline skeleton already used by History.tsx when isLoading. */
export default function HistorySkeleton() {
  return (
    <div className="space-y-2" aria-hidden>
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex gap-3 px-4 py-3 rounded-xl bg-dnd-surface border border-dnd-border">
          <Skeleton.Circle width="32px" delay={i * 80} />
          <div className="flex-1 space-y-2">
            <Skeleton.Line width="80%" height="14px" delay={i * 80} />
            <Skeleton.Line width="40%" height="10px" delay={i * 80 + 50} />
          </div>
        </div>
      ))}
    </div>
  )
}
