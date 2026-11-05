import{r as d,j as a}from"./react-vendor-BGC0LuHo.js";import{c,g as u,i as l,j as i,m,k as p}from"./index-CiR0HgnO.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const x=[["path",{d:"m6 9 6 6 6-6",key:"qrunsl"}]],f=c("chevron-down",x),h=new Set(["d4","d6","d8","d10","d12","d20"]);function y(){const e=u(),t=l(n=>n.animate3d),s=i();return d.useCallback(async(n,o)=>!t||s||!h.has(n)?void 0:(await e.playAndCollect([{kind:n,count:o}])).map(r=>r.value),[t,e,s])}function A({open:e,size:t=16,className:s="text-dnd-gold-dim"}){const n=i();return a.jsx(m.span,{"aria-hidden":!0,className:`inline-flex shrink-0 ${s}`,animate:{rotate:e?180:0},transition:n?{duration:0}:p.snappy,children:a.jsx(f,{size:t})})}function C(e){return e.is_class_feature&&!e.is_passive&&e.max_uses==null&&e.restoration_type!=="none"}export{f as C,A as E,C as i,y as u};
