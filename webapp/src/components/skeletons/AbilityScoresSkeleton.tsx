import Skeleton from '@/components/ui/Skeleton'

export default function AbilityScoresSkeleton() {
  return (
    <div className="border-y border-dnd-border divide-y divide-dnd-border/60" aria-hidden>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex min-h-[56px] items-center justify-between gap-3 px-1">
          <Skeleton.Line width="110px" height="10px" delay={i * 60} />
          <Skeleton.Line width="56px" height="24px" delay={i * 60 + 30} />
        </div>
      ))}
    </div>
  )
}
