import{r as i,a as N,j as c}from"./dice-scene-CgTzdl6m.js";import{m as R,s as k,i as w}from"./index-D6tyxagr.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const L=(...e)=>e.filter((r,t,n)=>!!r&&r.trim()!==""&&n.indexOf(r)===t).join(" ").trim();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const D=e=>e.replace(/([a-z0-9])([A-Z])/g,"$1-$2").toLowerCase();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const F=e=>e.replace(/^([A-Z])|[\s-_]+(\w)/g,(r,t,n)=>n?n.toUpperCase():t.toLowerCase());/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const A=e=>{const r=F(e);return r.charAt(0).toUpperCase()+r.slice(1)};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */var j={xmlns:"http://www.w3.org/2000/svg",width:24,height:24,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:2,strokeLinecap:"round",strokeLinejoin:"round"};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const I=e=>{for(const r in e)if(r.startsWith("aria-")||r==="role"||r==="title")return!0;return!1},U=i.createContext({}),Z=()=>i.useContext(U),M=i.forwardRef(({color:e,size:r,strokeWidth:t,absoluteStrokeWidth:n,className:s="",children:o,iconNode:b,...a},l)=>{const{size:d=24,strokeWidth:u=2,absoluteStrokeWidth:p=!1,color:g="currentColor",className:x=""}=Z()??{},m=n??p?Number(t??u)*24/Number(r??d):t??u;return i.createElement("svg",{ref:l,...j,width:r??d??j.width,height:r??d??j.height,stroke:e??g,strokeWidth:m,className:L("lucide",x,s),...!o&&!I(a)&&{"aria-hidden":"true"},...a},[...b.map(([f,v])=>i.createElement(f,v)),...Array.isArray(o)?o:[o]])});/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const J=(e,r)=>{const t=i.forwardRef(({className:n,...s},o)=>i.createElement(M,{ref:o,iconNode:r,className:L(`lucide-${D(A(e))}`,`lucide-${e}`,n),...s}));return t.displayName=A(e),t};function O(e){switch(e){case"elevated":return"bg-dnd-surface-raised border border-dnd-gold-dim/50 shadow-parchment-lg";case"tome":return"bg-gradient-parchment border border-dnd-border-strong shadow-parchment-xl surface-parchment";case"parchment":return"bg-gradient-parchment border border-dnd-border shadow-parchment-md surface-parchment";case"arcane":return"bg-gradient-arcane-mist border border-dnd-arcane/40 shadow-halo-arcane";case"ember":return"bg-dnd-surface border border-dnd-crimson/50 shadow-halo-danger";case"sigil":return"bg-gradient-parchment border border-dnd-gold/40 shadow-parchment-xl surface-parchment";case"flat":default:return"bg-dnd-surface border border-transparent"}}function P({children:e,className:r="",variant:t="flat",ornamented:n=!1,interactive:s=!1,asMotion:o=!1,layoutId:b,onClick:a,style:l,tabIndex:d,role:u,"aria-label":p}){const g="relative rounded-2xl p-4 transition-shadow duration-300",x=s||a?"cursor-pointer active:scale-[0.98] will-change-transform":"",m=`${g} ${O(t)} ${x} ${r}`,f=c.jsx("div",{className:n?"relative z-[1] pt-3 px-2 pb-2":"contents",children:e});return o||b?c.jsx(R.div,{layoutId:b,className:m,onClick:a,style:l,tabIndex:d,role:u,"aria-label":p,whileTap:s||a?{scale:.98}:void 0,transition:k.press,children:f}):c.jsx("div",{className:m,onClick:a,style:l,tabIndex:d,role:u,"aria-label":p,children:f})}const Q=N.memo(P);function X(e){switch(e){case"primary":return"bg-gradient-gold text-dnd-ink shadow-engrave";case"secondary":return"bg-dnd-surface-raised text-dnd-text border border-dnd-gold-dim/30 hover:border-dnd-gold/70";case"danger":return"bg-dnd-crimson/15 text-dnd-crimson-bright border border-dnd-crimson/40 hover:bg-dnd-crimson/25 hover:border-dnd-crimson/60";case"arcane":return"bg-gradient-to-r from-dnd-arcane-deep to-dnd-arcane text-dnd-parchment border border-dnd-arcane-bright/40 shadow-halo-arcane";case"ghost":return"bg-transparent text-dnd-gold hover:text-dnd-gold-bright border border-transparent"}}function Y(e){switch(e){case"sm":return"min-h-[40px] px-3 py-2 text-xs";case"lg":return"min-h-[56px] px-5 py-3.5 text-base";case"md":default:return"min-h-[48px] px-4 py-3 text-sm"}}function _({variant:e="primary",size:r="md",loading:t=!1,disabled:n=!1,icon:s,iconPosition:o="left",fullWidth:b=!1,haptic:a="light",children:l,onClick:d,className:u="",type:p="button",title:g,"aria-label":x}){const m=n||t,[f,v]=i.useState([]),C=i.useRef(null),W=h=>{if(!m){if(a!=="none"&&(a==="success"?w.success():a==="error"?w.error():a==="warning"?w.warning():a==="medium"?w.medium():w.light()),e==="primary"&&C.current){const $=C.current.getBoundingClientRect(),E=h.clientX-$.left,T=h.clientY-$.top,S=Date.now()+Math.random();v(y=>[...y,{id:S,x:E,y:T}]),setTimeout(()=>v(y=>y.filter(z=>z.id!==S)),400)}d==null||d(h)}},B=`relative overflow-hidden rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors duration-150 disabled:opacity-40 disabled:pointer-events-none ${Y(r)} ${X(e)} ${b?"w-full":""} ${u}`;return c.jsxs(R.button,{ref:C,type:p,onClick:W,disabled:m,className:B,title:g,"aria-label":x,whileTap:{scale:.97},transition:k.press,children:[f.map(h=>c.jsx("span",{className:"absolute rounded-full bg-dnd-parchment/30 pointer-events-none",style:{left:h.x,top:h.y,width:8,height:8,marginLeft:-4,marginTop:-4,animation:"ink-spread 320ms ease-out forwards"}},h.id)),t?c.jsxs(c.Fragment,{children:[c.jsx("span",{className:"w-4 h-4 border-2 border-current/30 border-t-current rounded-full animate-spin"}),l]}):c.jsxs(c.Fragment,{children:[s&&o==="left"&&s,l,s&&o==="right"&&s]})]})}const V=N.memo(_);export{V as B,Q as S,J as c};
