import{r as c,j as s}from"./react-vendor-BGC0LuHo.js";import{f as d,g as u,i as o,m,j as p}from"./index-BQgaGRX8.js";import{c as l}from"./gi-icon_GiLightningTrio-DUQ-0WOv.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const x=[["path",{d:"m6 9 6 6 6-6",key:"qrunsl"}]],f=l("chevron-down",x),h=new Set(["d4","d6","d8","d10","d12","d20"]);function D(){const t=d(),e=u(n=>n.animate3d),a=o();return c.useCallback(async(n,i)=>!e||a||!h.has(n)?void 0:(await t.playAndCollect([{kind:n,count:i}])).map(r=>r.value),[e,t,a])}const E=t=>{var e;return((e=t.attack_save)==null?void 0:e.trim().toUpperCase())==="ATK"};function g({open:t,size:e=16,className:a="text-dnd-gold-dim"}){const n=o();return s.jsx(m.span,{"aria-hidden":!0,className:`inline-flex shrink-0 ${a}`,animate:{rotate:t?180:0},transition:n?{duration:0}:p.snappy,children:s.jsx(f,{size:e})})}export{f as C,g as E,E as i,D as u};
