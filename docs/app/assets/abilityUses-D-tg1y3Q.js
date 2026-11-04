import{r as d,j as o}from"./react-vendor-BGC0LuHo.js";import{f as c,g as u,i as a,m,j as l}from"./index-r-9tXmTR.js";import{c as p}from"./gi-icon_GiCutDiamond-qpEtxXvA.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const f=[["path",{d:"m6 9 6 6 6-6",key:"qrunsl"}]],x=p("chevron-down",f),h=new Set(["d4","d6","d8","d10","d12","d20"]);function A(){const e=c(),t=u(n=>n.animate3d),s=a();return d.useCallback(async(n,i)=>!t||s||!h.has(n)?void 0:(await e.playAndCollect([{kind:n,count:i}])).map(r=>r.value),[t,e,s])}function C({open:e,size:t=16,className:s="text-dnd-gold-dim"}){const n=a();return o.jsx(m.span,{"aria-hidden":!0,className:`inline-flex shrink-0 ${s}`,animate:{rotate:e?180:0},transition:n?{duration:0}:l.snappy,children:o.jsx(x,{size:t})})}function D(e){return e.is_class_feature&&!e.is_passive&&e.max_uses==null&&e.restoration_type!=="none"}export{x as C,C as E,D as i,A as u};
