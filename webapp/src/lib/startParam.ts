/** Parsing del parametro startapp dei deep link t.me/<bot>?startapp=… */

export type StartParamAction = { kind: 'join'; code: string }

const JOIN_RE = /^join_([a-z0-9]{6})$/i

export function parseStartParam(param: string | null | undefined): StartParamAction | null {
  if (!param) return null
  const m = JOIN_RE.exec(param.trim())
  return m ? { kind: 'join', code: m[1].toUpperCase() } : null
}
