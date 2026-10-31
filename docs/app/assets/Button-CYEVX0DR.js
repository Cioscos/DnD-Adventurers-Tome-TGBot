import{r as c,j as o,a as $}from"./react-vendor-CPSJdvAW.js";import{u as D,bT as E,m as N,s as R,bS as z,bB as O}from"./index-wGDjkejS.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const A=(...e)=>e.filter((t,r,a)=>!!t&&t.trim()!==""&&a.indexOf(t)===r).join(" ").trim();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const F=e=>e.replace(/([a-z0-9])([A-Z])/g,"$1-$2").toLowerCase();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const U=e=>e.replace(/^([A-Z])|[\s-_]+(\w)/g,(t,r,a)=>a?a.toUpperCase():r.toLowerCase());/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const S=e=>{const t=U(e);return t.charAt(0).toUpperCase()+t.slice(1)};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */var k={xmlns:"http://www.w3.org/2000/svg",width:24,height:24,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:2,strokeLinecap:"round",strokeLinejoin:"round"};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const I=e=>{for(const t in e)if(t.startsWith("aria-")||t==="role"||t==="title")return!0;return!1},K=c.createContext({}),X=()=>c.useContext(K),Z=c.forwardRef(({color:e,size:t,strokeWidth:r,absoluteStrokeWidth:a,className:n="",children:s,iconNode:p,...i},l)=>{const{size:d=24,strokeWidth:m=2,absoluteStrokeWidth:f=!1,color:g="currentColor",className:x=""}=X()??{},u=a??f?Number(r??m)*24/Number(t??d):r??m;return c.createElement("svg",{ref:l,...k,width:t??d??k.width,height:t??d??k.height,stroke:e??g,strokeWidth:u,className:A("lucide",x,n),...!s&&!I(i)&&{"aria-hidden":"true"},...i},[...p.map(([b,w])=>c.createElement(b,w)),...Array.isArray(s)?s:[s]])});/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const W=(e,t)=>{const r=c.forwardRef(({className:a,...n},s)=>c.createElement(Z,{ref:s,iconNode:t,className:A(`lucide-${F(S(e))}`,`lucide-${e}`,a),...n}));return r.displayName=S(e),r};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const H=[["path",{d:"M12 20h.01",key:"zekei9"}],["path",{d:"M8.5 16.429a5 5 0 0 1 7 0",key:"1bycff"}],["path",{d:"M5 12.859a10 10 0 0 1 5.17-2.69",key:"1dl1wf"}],["path",{d:"M19 12.859a10 10 0 0 0-2.007-1.523",key:"4k23kn"}],["path",{d:"M2 8.82a15 15 0 0 1 4.177-2.643",key:"1grhjp"}],["path",{d:"M22 8.82a15 15 0 0 0-11.288-3.764",key:"z3jwby"}],["path",{d:"m2 2 20 20",key:"1ooewy"}]],P=W("wifi-off",H);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Y=[["path",{d:"M18 6 6 18",key:"1bl5f8"}],["path",{d:"m6 6 12 12",key:"d8bk6v"}]],ne=W("x",Y);function G(e,t){const r=new Date(e),a=r.toDateString()===new Date().toDateString();return r.toLocaleString(t,{...a?{}:{day:"2-digit",month:"2-digit"},hour:"2-digit",minute:"2-digit",hourCycle:"h23"})}function se({query:e,className:t=""}){const{t:r,i18n:a}=D(),n=e.isRefetchError?e.error:e.isFetching?e.failureReason:null;if(e.data===void 0||!n)return null;const s=E(n)?"common.offline_data_from":"common.stale_data_from";return o.jsxs("p",{role:"status",className:`flex items-center gap-1.5 rounded-lg border border-dnd-amber/40 bg-dnd-amber/10 px-3 py-1.5 text-xs font-body tabular-nums text-dnd-text ${t}`,children:[o.jsx(P,{size:14,className:"shrink-0 text-dnd-amber"}),o.jsx("span",{className:"min-w-0",children:r(s,{time:G(e.dataUpdatedAt,a.language)})})]})}function J(e){switch(e){case"elevated":return"bg-dnd-surface-raised border border-dnd-gold-dim/50 shadow-parchment-lg";case"tome":return"bg-gradient-parchment border border-dnd-border-strong shadow-parchment-xl surface-parchment";case"parchment":return"bg-gradient-parchment border border-dnd-border shadow-parchment-md surface-parchment";case"arcane":return"bg-gradient-arcane-mist border border-dnd-arcane/40 shadow-halo-arcane";case"ember":return"bg-dnd-surface border border-dnd-crimson/50 shadow-halo-danger";case"sigil":return"bg-gradient-parchment border border-dnd-gold/40 shadow-parchment-xl surface-parchment";case"flat":default:return"bg-dnd-surface border border-transparent"}}function Q({children:e,className:t="",variant:r="flat",ornamented:a=!1,interactive:n=!1,asMotion:s=!1,layoutId:p,onClick:i,style:l,tabIndex:d,role:m,"aria-label":f}){const g="relative rounded-2xl p-4 transition-shadow duration-300",x=n||i?"cursor-pointer active:scale-[0.98] will-change-transform":"",u=`${g} ${J(r)} ${x} ${t}`,b=o.jsx("div",{className:a?"relative z-[1] pt-3 px-2 pb-2":"contents",children:e});return s||p?o.jsx(N.div,{layoutId:p,className:u,onClick:i,style:l,tabIndex:d,role:m,"aria-label":f,whileTap:n||i?{scale:.98}:void 0,transition:R.press,children:b}):o.jsx("div",{className:u,onClick:i,style:l,tabIndex:d,role:m,"aria-label":f,children:b})}const oe=$.memo(Q);function V(e){switch(e){case"primary":return"bg-gradient-gold text-dnd-ink shadow-engrave";case"secondary":return"bg-dnd-surface-raised text-dnd-text border border-dnd-gold-dim/30 hover:border-dnd-gold/70";case"danger":return"bg-dnd-crimson/15 text-dnd-crimson-bright border border-dnd-crimson/40 hover:bg-dnd-crimson/25 hover:border-dnd-crimson/60";case"arcane":return"bg-gradient-to-r from-dnd-arcane-deep to-dnd-arcane text-dnd-parchment border border-dnd-arcane-bright/40 shadow-halo-arcane";case"ghost":return"bg-transparent text-dnd-gold hover:text-dnd-gold-bright border border-transparent"}}function q(e){switch(e){case"sm":return"min-h-11 px-3 py-2 text-xs";case"lg":return"min-h-[56px] px-5 py-3.5 text-base";case"md":default:return"min-h-[48px] px-4 py-3 text-sm"}}function ee({variant:e="primary",size:t="md",loading:r=!1,disabled:a=!1,icon:n,iconPosition:s="left",fullWidth:p=!1,haptic:i="light",children:l,onClick:d,className:m="",type:f="button",title:g,"aria-label":x}){const u=a||r,[b,w]=c.useState([]),y=c.useRef(null),_=h=>{if(!u){if(O(i),e==="primary"&&y.current){const C=y.current.getBoundingClientRect(),M=h.clientX-C.left,T=h.clientY-C.top,j=Date.now()+Math.random();w(v=>[...v,{id:j,x:M,y:T}]),setTimeout(()=>w(v=>v.filter(B=>B.id!==j)),400)}d==null||d(h)}},L=`relative overflow-hidden rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors duration-150 disabled:opacity-40 disabled:pointer-events-none ${q(t)} ${V(e)} ${p?"w-full":""} ${m}`;return o.jsxs(N.button,{ref:y,type:f,onClick:_,disabled:u,className:L,title:g,"aria-label":x,whileTap:{scale:.97},transition:R.press,children:[b.map(h=>o.jsx("span",{className:"absolute rounded-full bg-dnd-parchment/30 pointer-events-none",style:{left:h.x,top:h.y,width:8,height:8,marginLeft:-4,marginTop:-4,animation:"ink-spread 320ms ease-out forwards"}},h.id)),r?o.jsxs(o.Fragment,{children:[o.jsx(z,{}),l]}):o.jsxs(o.Fragment,{children:[n&&s==="left"&&n,l,n&&s==="right"&&n]})]})}const de=$.memo(ee);export{de as B,se as O,oe as S,P as W,ne as X,W as c};
