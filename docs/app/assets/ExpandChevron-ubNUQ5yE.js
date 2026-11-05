import{r as c,j as s}from"./react-vendor-BGC0LuHo.js";import{c as d,g as u,i as l,j as o,m,k as p}from"./index-DuUmh4US.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const x=[["path",{d:"m6 9 6 6 6-6",key:"qrunsl"}]],h=d("chevron-down",x),A=new Set(["d4","d6","d8","d10","d12","d20"]);function j(){const t=u(),e=l(n=>n.animate3d),a=o();return c.useCallback(async(n,i)=>!e||a||!A.has(n)?void 0:(await t.playAndCollect([{kind:n,count:i}])).map(r=>r.value),[e,t,a])}const k=t=>{var e;return((e=t.attack_save)==null?void 0:e.trim().toUpperCase())==="ATK"};function D({open:t,size:e=16,className:a="text-dnd-gold-dim"}){const n=o();return s.jsx(m.span,{"aria-hidden":!0,className:`inline-flex shrink-0 ${a}`,animate:{rotate:t?180:0},transition:n?{duration:0}:p.snappy,children:s.jsx(h,{size:e})})}export{h as C,D as E,k as i,j as u};
