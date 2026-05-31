import Skeleton from '@/components/ui/Skeleton'

/** Generic page skeleton — used when a page has no bespoke skeleton yet. */
export default function GenericPageSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      <Skeleton.Rect height="160px" />
      <Skeleton.Rect height="80px" delay={80} />
      <Skeleton.Rect height="80px" delay={160} />
    </div>
  )
}
