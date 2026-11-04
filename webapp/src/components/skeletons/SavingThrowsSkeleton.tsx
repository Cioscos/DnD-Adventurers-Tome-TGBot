import Skeleton from '@/components/ui/Skeleton'
import RowListSkeleton from './RowListSkeleton'

export default function SavingThrowsSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* Prof bonus pill */}
      <div className="border-b border-dnd-border/60 px-1 py-2 flex items-center justify-between">
        <Skeleton.Line width="100px" height="12px" />
        <Skeleton.Line width="36px" height="24px" delay={40} />
      </div>
      {/* 6 ability rows */}
      <RowListSkeleton count={6} />
    </div>
  )
}
