import Skeleton from '@/components/ui/Skeleton'

/** Reusable row skeleton used by saves/conditions/other list-of-rows pages. */
export function RowListSkeleton({ count = 6, offset = 0 }: { count?: number; offset?: number }) {
  return (
    <div className="flex flex-col gap-1.5" aria-hidden>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-2xl border border-dnd-border bg-dnd-surface px-3 py-2 flex items-center gap-3 min-h-[56px]"
        >
          <Skeleton.Circle width="40px" delay={offset + i * 60} />
          <div className="flex-1 space-y-1.5">
            <Skeleton.Line width="60%" height="12px" delay={offset + i * 60 + 20} />
            <Skeleton.Line width="40%" height="10px" delay={offset + i * 60 + 40} />
          </div>
          <Skeleton.Line width="32px" height="28px" delay={offset + i * 60 + 30} />
        </div>
      ))}
    </div>
  )
}

export default function SavingThrowsSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* Prof bonus pill */}
      <div className="rounded-2xl border border-dnd-border bg-dnd-surface px-3 py-2 flex items-center justify-between">
        <Skeleton.Line width="100px" height="12px" />
        <Skeleton.Line width="36px" height="24px" delay={40} />
      </div>
      {/* 6 ability rows */}
      <RowListSkeleton count={6} />
    </div>
  )
}
