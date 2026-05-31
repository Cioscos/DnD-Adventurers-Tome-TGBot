import Skeleton from '@/components/ui/Skeleton'

export default function AbilityScoresSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3" aria-hidden>
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="rounded-2xl border border-dnd-border bg-dnd-surface p-4 flex flex-col items-center gap-2"
        >
          <Skeleton.Line width="60px" height="10px" delay={i * 60} />
          <Skeleton.Line width="48px" height="40px" delay={i * 60 + 30} />
          <Skeleton.Line width="32px" height="24px" rounded="rounded-full" delay={i * 60 + 60} />
        </div>
      ))}
    </div>
  )
}
