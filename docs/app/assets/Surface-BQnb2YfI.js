import{r as n,a as S,j as i}from"./dice-scene-vKP0wyrV.js";import{m as j,s as A,aS as $}from"./index-CjlwiXYO.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const C=(...e)=>e.filter((r,t,a)=>!!r&&r.trim()!==""&&a.indexOf(r)===t).join(" ").trim();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const k=e=>e.replace(/([a-z0-9])([A-Z])/g,"$1-$2").toLowerCase();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const W=e=>e.replace(/^([A-Z])|[\s-_]+(\w)/g,(r,t,a)=>a?a.toUpperCase():t.toLowerCase());/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const w=e=>{const r=W(e);return r.charAt(0).toUpperCase()+r.slice(1)};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */var x={xmlns:"http://www.w3.org/2000/svg",width:24,height:24,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:2,strokeLinecap:"round",strokeLinejoin:"round"};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const L=e=>{for(const r in e)if(r.startsWith("aria-")||r==="role"||r==="title")return!0;return!1},E=n.createContext({}),N=()=>n.useContext(E),R=n.forwardRef(({color:e,size:r,strokeWidth:t,absoluteStrokeWidth:a,className:c="",children:s,iconNode:u,...o},h)=>{const{size:d=24,strokeWidth:l=2,absoluteStrokeWidth:m=!1,color:f="currentColor",className:g=""}=N()??{},p=a??m?Number(t??l)*24/Number(r??d):t??l;return n.createElement("svg",{ref:h,...x,width:r??d??x.width,height:r??d??x.height,stroke:e??f,strokeWidth:p,className:C("lucide",g,c),...!s&&!L(o)&&{"aria-hidden":"true"},...o},[...u.map(([b,v])=>n.createElement(b,v)),...Array.isArray(s)?s:[s]])});/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const P=(e,r)=>{const t=n.forwardRef(({className:a,...c},s)=>n.createElement(R,{ref:s,iconNode:r,className:C(`lucide-${k(w(e))}`,`lucide-${e}`,a),...c}));return t.displayName=w(e),t};function y(e){switch(e){case"elevated":return"bg-dnd-surface-raised border border-dnd-gold-dim/50 shadow-parchment-lg";case"tome":return"bg-gradient-parchment border border-dnd-border-strong shadow-parchment-xl surface-parchment";case"parchment":return"bg-gradient-parchment border border-dnd-border shadow-parchment-md surface-parchment";case"arcane":return"bg-gradient-arcane-mist border border-dnd-arcane/40 shadow-halo-arcane";case"ember":return"bg-dnd-surface border border-dnd-crimson/50 shadow-halo-danger";case"sigil":return"bg-gradient-parchment border border-dnd-gold/40 shadow-parchment-xl surface-parchment";case"flat":default:return"bg-dnd-surface border border-transparent"}}function z({children:e,className:r="",variant:t="flat",ornamented:a=!1,interactive:c=!1,asMotion:s=!1,layoutId:u,onClick:o,style:h,tabIndex:d,role:l,"aria-label":m}){const f="relative rounded-2xl p-4 transition-shadow duration-300",g=c||o?"cursor-pointer active:scale-[0.98] will-change-transform":"",p=`${f} ${y(t)} ${g} ${r}`,b=i.jsxs(i.Fragment,{children:[a&&i.jsx($,{}),i.jsx("div",{className:a?"relative z-[1] pt-3 px-2 pb-2":"contents",children:e})]});return s||u?i.jsx(j.div,{layoutId:u,className:p,onClick:o,style:h,tabIndex:d,role:l,"aria-label":m,whileTap:c||o?{scale:.98}:void 0,transition:A.press,children:b}):i.jsx("div",{className:p,onClick:o,style:h,tabIndex:d,role:l,"aria-label":m,children:b})}const U=S.memo(z);export{U as S,P as c};
