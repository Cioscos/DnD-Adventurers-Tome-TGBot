import{r as i,a as A,j as d}from"./dice-scene-CgTzdl6m.js";import{m as R,s as k,bi as z,bj as D}from"./index-Dz5NczTa.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const L=(...e)=>e.filter((r,t,a)=>!!r&&r.trim()!==""&&a.indexOf(r)===t).join(" ").trim();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const F=e=>e.replace(/([a-z0-9])([A-Z])/g,"$1-$2").toLowerCase();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const I=e=>e.replace(/^([A-Z])|[\s-_]+(\w)/g,(r,t,a)=>a?a.toUpperCase():t.toLowerCase());/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const S=e=>{const r=I(e);return r.charAt(0).toUpperCase()+r.slice(1)};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */var y={xmlns:"http://www.w3.org/2000/svg",width:24,height:24,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:2,strokeLinecap:"round",strokeLinejoin:"round"};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const U=e=>{for(const r in e)if(r.startsWith("aria-")||r==="role"||r==="title")return!0;return!1},Z=i.createContext({}),H=()=>i.useContext(Z),K=i.forwardRef(({color:e,size:r,strokeWidth:t,absoluteStrokeWidth:a,className:n="",children:s,iconNode:h,...c},l)=>{const{size:o=24,strokeWidth:u=2,absoluteStrokeWidth:b=!1,color:g="currentColor",className:x=""}=H()??{},m=a??b?Number(t??u)*24/Number(r??o):t??u;return i.createElement("svg",{ref:l,...y,width:r??o??y.width,height:r??o??y.height,stroke:e??g,strokeWidth:m,className:L("lucide",x,n),...!s&&!U(c)&&{"aria-hidden":"true"},...c},[...h.map(([f,w])=>i.createElement(f,w)),...Array.isArray(s)?s:[s]])});/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const J=(e,r)=>{const t=i.forwardRef(({className:a,...n},s)=>i.createElement(K,{ref:s,iconNode:r,className:L(`lucide-${F(S(e))}`,`lucide-${e}`,a),...n}));return t.displayName=S(e),t};function M(e){switch(e){case"elevated":return"bg-dnd-surface-raised border border-dnd-gold-dim/50 shadow-parchment-lg";case"tome":return"bg-gradient-parchment border border-dnd-border-strong shadow-parchment-xl surface-parchment";case"parchment":return"bg-gradient-parchment border border-dnd-border shadow-parchment-md surface-parchment";case"arcane":return"bg-gradient-arcane-mist border border-dnd-arcane/40 shadow-halo-arcane";case"ember":return"bg-dnd-surface border border-dnd-crimson/50 shadow-halo-danger";case"sigil":return"bg-gradient-parchment border border-dnd-gold/40 shadow-parchment-xl surface-parchment";case"flat":default:return"bg-dnd-surface border border-transparent"}}function O({children:e,className:r="",variant:t="flat",ornamented:a=!1,interactive:n=!1,asMotion:s=!1,layoutId:h,onClick:c,style:l,tabIndex:o,role:u,"aria-label":b}){const g="relative rounded-2xl p-4 transition-shadow duration-300",x=n||c?"cursor-pointer active:scale-[0.98] will-change-transform":"",m=`${g} ${M(t)} ${x} ${r}`,f=d.jsx("div",{className:a?"relative z-[1] pt-3 px-2 pb-2":"contents",children:e});return s||h?d.jsx(R.div,{layoutId:h,className:m,onClick:c,style:l,tabIndex:o,role:u,"aria-label":b,whileTap:n||c?{scale:.98}:void 0,transition:k.press,children:f}):d.jsx("div",{className:m,onClick:c,style:l,tabIndex:o,role:u,"aria-label":b,children:f})}const Q=A.memo(O);function P(e){switch(e){case"primary":return"bg-gradient-gold text-dnd-ink shadow-engrave";case"secondary":return"bg-dnd-surface-raised text-dnd-text border border-dnd-gold-dim/30 hover:border-dnd-gold/70";case"danger":return"bg-dnd-crimson/15 text-dnd-crimson-bright border border-dnd-crimson/40 hover:bg-dnd-crimson/25 hover:border-dnd-crimson/60";case"arcane":return"bg-gradient-to-r from-dnd-arcane-deep to-dnd-arcane text-dnd-parchment border border-dnd-arcane-bright/40 shadow-halo-arcane";case"ghost":return"bg-transparent text-dnd-gold hover:text-dnd-gold-bright border border-transparent"}}function X(e){switch(e){case"sm":return"min-h-[40px] px-3 py-2 text-xs";case"lg":return"min-h-[56px] px-5 py-3.5 text-base";case"md":default:return"min-h-[48px] px-4 py-3 text-sm"}}function Y({variant:e="primary",size:r="md",loading:t=!1,disabled:a=!1,icon:n,iconPosition:s="left",fullWidth:h=!1,haptic:c="light",children:l,onClick:o,className:u="",type:b="button",title:g,"aria-label":x}){const m=a||t,[f,w]=i.useState([]),v=i.useRef(null),N=p=>{if(!m){if(D(c),e==="primary"&&v.current){const j=v.current.getBoundingClientRect(),B=p.clientX-j.left,E=p.clientY-j.top,$=Date.now()+Math.random();w(C=>[...C,{id:$,x:B,y:E}]),setTimeout(()=>w(C=>C.filter(T=>T.id!==$)),400)}o==null||o(p)}},W=`relative overflow-hidden rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors duration-150 disabled:opacity-40 disabled:pointer-events-none ${X(r)} ${P(e)} ${h?"w-full":""} ${u}`;return d.jsxs(R.button,{ref:v,type:b,onClick:N,disabled:m,className:W,title:g,"aria-label":x,whileTap:{scale:.97},transition:k.press,children:[f.map(p=>d.jsx("span",{className:"absolute rounded-full bg-dnd-parchment/30 pointer-events-none",style:{left:p.x,top:p.y,width:8,height:8,marginLeft:-4,marginTop:-4,animation:"ink-spread 320ms ease-out forwards"}},p.id)),t?d.jsxs(d.Fragment,{children:[d.jsx(z,{}),l]}):d.jsxs(d.Fragment,{children:[n&&s==="left"&&n,l,n&&s==="right"&&n]})]})}const V=A.memo(Y);export{V as B,Q as S,J as c};
