export const pad = (n: number) => String(n).padStart(2, '0')
/** Giorno locale come YYYY-MM-DD (formato di <input type="date">). */
export const dateKey = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
/** Il server manda UTC naive (senza Z): la Z si aggiunge solo se manca un fuso. */
export const fromServer = (iso: string) => new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`)
