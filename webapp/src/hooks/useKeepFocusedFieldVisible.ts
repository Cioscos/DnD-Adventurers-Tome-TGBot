import { useEffect, type RefObject } from 'react'

/**
 * Tastiera aperta su Telegram Android: la WebView si rimpicciolisce ma il browser non porta in vista
 * il campo attivo dentro lo scroll di un overlay (restava sotto la tastiera). Finché `active`, quando
 * l'altezza cala (resize) o Telegram stabilizza il viewport (`--tg-vh` può aggiornarsi solo allora),
 * centra il campo attivo dentro `ref` scorrendo il suo contenitore scrollabile più vicino.
 */
export function useKeepFocusedFieldVisible(ref: RefObject<HTMLElement>, active: boolean) {
  useEffect(() => {
    if (!active) return
    const reveal = () => requestAnimationFrame(() => {
      const el = document.activeElement
      if (!(el instanceof HTMLElement) || !ref.current?.contains(el) || !el.matches('input, textarea')) return
      // Solo il contenitore che scorre davvero: scrollIntoView sposterebbe anche i pannelli overflow-hidden.
      // overflow-x-auto rende "auto" anche overflowY: serve anche che scorra davvero in verticale.
      const scrolls = (b: HTMLElement) => /(auto|scroll)/.test(getComputedStyle(b).overflowY) && b.scrollHeight > b.clientHeight
      let box = el.parentElement
      while (box && box !== ref.current && !scrolls(box)) box = box.parentElement
      if (!box || !scrolls(box)) return
      const b = box.getBoundingClientRect()
      const r = el.getBoundingClientRect()
      box.scrollTop += r.top + r.height / 2 - (b.top + b.height / 2)
    })
    let lastHeight = window.innerHeight
    // Solo quando l'altezza cala (tastiera): rotazioni e finestre desktop che si allargano non ricentrano.
    const onResize = () => {
      const shrank = window.innerHeight < lastHeight
      lastHeight = window.innerHeight
      if (shrank) reveal()
    }
    const onViewport = (e?: { isStateStable?: boolean }) => { if (e?.isStateStable !== false) reveal() }
    const tg = window.Telegram?.WebApp
    window.addEventListener('resize', onResize)
    tg?.onEvent?.('viewportChanged', onViewport)
    return () => {
      window.removeEventListener('resize', onResize)
      tg?.offEvent?.('viewportChanged', onViewport)
    }
  }, [ref, active])
}
