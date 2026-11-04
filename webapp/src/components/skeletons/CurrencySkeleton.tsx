import Skeleton from '@/components/ui/Skeleton'

// Stessa sagoma della pagina: borsa con le monete, poi transazione col tastierino.
export default function CurrencySkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      <div className="border-b border-dnd-border/60 px-1 py-3 space-y-2">
        <div className="grid grid-cols-5 gap-1.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton.Rect key={i} height="64px" rounded="rounded-xl" delay={i * 50} />
          ))}
        </div>
        <Skeleton.Rect height="44px" rounded="rounded-xl" delay={260} />
      </div>
      <div className="border-b border-dnd-border/60 px-1 py-3 grid grid-cols-3 gap-1.5">
        {Array.from({ length: 12 }).map((_, i) => (
          <Skeleton.Rect key={i} height="44px" rounded="rounded-xl" delay={300 + i * 20} />
        ))}
      </div>
    </div>
  )
}
