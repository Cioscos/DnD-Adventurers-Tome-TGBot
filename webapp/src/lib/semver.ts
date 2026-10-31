const parse = (v: string): number[] => v.split('.').map((n) => parseInt(n, 10) || 0)

export function compareSemver(a: string, b: string): -1 | 0 | 1 {
  const pa = parse(a)
  const pb = parse(b)
  for (let i = 0; i < 3; i++) {
    const d = (pa[i] ?? 0) - (pb[i] ?? 0)
    if (d !== 0) return d < 0 ? -1 : 1
  }
  return 0
}

/** True solo se il server è indietro di major/minor rispetto al client (la patch si ignora). */
export function isServerBehind(client: string, server: string | null): boolean {
  if (!server) return false
  const [cMaj, cMin] = parse(client)
  const [sMaj, sMin] = parse(server)
  return compareSemver(`${sMaj}.${sMin}.0`, `${cMaj}.${cMin}.0`) < 0
}
