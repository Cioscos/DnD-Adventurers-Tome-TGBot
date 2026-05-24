const ROMANS = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX']

export function toRoman(n: number): string {
  if (n < 1 || n > 9) return String(n)
  return ROMANS[n]
}
