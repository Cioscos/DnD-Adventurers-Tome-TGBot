import Skeleton from '@/components/ui/Skeleton'

export default function DiceSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* Initiative button */}
      <Skeleton.Rect height="44px" rounded="rounded-xl" />
      {/* Dice grid 4+3 */}
      <div className="grid grid-cols-4 gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton.Rect key={i} height="56px" rounded="rounded-xl" delay={i * 40} />
        ))}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton.Rect key={i} height="56px" rounded="rounded-xl" delay={160 + i * 40} />
        ))}
      </div>
      {/* Count / preset strip */}
      <div className="flex gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton.Rect key={i} width="44px" height="36px" rounded="rounded-xl" delay={280 + i * 30} />
        ))}
      </div>
      {/* History list */}
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="flex gap-3 px-4 py-3 rounded-xl bg-dnd-surface border border-dnd-border"
          >
            <Skeleton.Circle width="32px" delay={400 + i * 80} />
            <div className="flex-1 space-y-2">
              <Skeleton.Line width="70%" height="14px" delay={420 + i * 80} />
              <Skeleton.Line width="40%" height="10px" delay={440 + i * 80} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
