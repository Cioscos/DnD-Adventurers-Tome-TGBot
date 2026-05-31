import Skeleton from '@/components/ui/Skeleton'

export default function NotesSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {/* Add / record buttons */}
      <div className="flex gap-2">
        <Skeleton.Rect className="flex-1" height="44px" rounded="rounded-xl" />
        <Skeleton.Rect width="44px" height="44px" rounded="rounded-xl" delay={40} />
      </div>
      {/* Note cards */}
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 space-y-2"
        >
          <div className="flex items-center justify-between">
            <Skeleton.Line width="55%" height="14px" delay={60 + i * 80} />
            <Skeleton.Line width="50px" height="10px" delay={80 + i * 80} />
          </div>
          <Skeleton.Line width="90%" height="10px" delay={100 + i * 80} />
          <Skeleton.Line width="70%" height="10px" delay={120 + i * 80} />
        </div>
      ))}
    </div>
  )
}
