/** Parsing del parametro startapp dei deep link t.me/<bot>?startapp=… */

export type StartParamAction =
  | { kind: 'join'; code: string }
  | { kind: 'share'; token: string }

const JOIN_RE = /^join_([a-z0-9]{6})$/i
// Token generato con secrets.token_urlsafe lato API: [A-Za-z0-9_-], case-sensitive
const SHARE_RE = /^shr_([A-Za-z0-9_-]{8,64})$/

export function parseStartParam(param: string | null | undefined): StartParamAction | null {
  if (!param) return null
  const trimmed = param.trim()
  const join = JOIN_RE.exec(trimmed)
  if (join) return { kind: 'join', code: join[1].toUpperCase() }
  const share = SHARE_RE.exec(trimmed)
  if (share) return { kind: 'share', token: share[1] }
  return null
}
