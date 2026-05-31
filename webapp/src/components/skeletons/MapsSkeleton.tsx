import Skeleton from '@/components/ui/Skeleton'

export default function MapsSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* Upload button */}
      <Skeleton.Rect height="44px" rounded="rounded-xl" />
      {/* Zone groups */}
      {Array.from({ length: 2 }).map((_, g) => (
        <div key={g} className="space-y-2">
          <Skeleton.Line width="80px" height="12px" delay={g * 120} />
          <div className="grid grid-cols-2 gap-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div
                key={i}
                className="rounded-2xl border border-dnd-border bg-dnd-surface overflow-hidden"
              >
                <Skeleton.Rect height="100px" rounded="rounded-none" delay={g * 120 + i * 60} />
                <div className="p-2">
                  <Skeleton.Line width="70%" height="10px" delay={g * 120 + i * 60 + 40} />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
