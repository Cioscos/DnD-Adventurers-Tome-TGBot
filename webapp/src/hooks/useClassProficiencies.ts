import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'

/** Competenze che la classe dà (tabella per edizione); `skills_count` è quante abilità vanno scelte. */
export function useClassProficiencies(edition: string, className: string | null, asMulticlass: boolean) {
  return useQuery({
    queryKey: ['rules', 'proficiencies', edition, className, asMulticlass],
    queryFn: () => api.rules.proficiencies(edition, className as string, asMulticlass),
    enabled: !!className,
    staleTime: Infinity,
  })
}
