import Skeleton from '@/components/ui/Skeleton'
import RowListSkeleton from './RowListSkeleton'

export default function ConditionsSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* Filter chip strip */}
      <div className="flex gap-2 flex-wrap">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton.Rect key={i} width="70px" height="30px" rounded="rounded-full" delay={i * 40} />
        ))}
      </div>
      {/* Condition rows */}
      <RowListSkeleton count={8} offset={120} />
    </div>
  )
}
