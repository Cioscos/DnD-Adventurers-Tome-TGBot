import{r as d,R as W,j as r,a as M}from"./react-vendor-BGC0LuHo.js";import{m as C,j as A,S as P,l as _,a2 as F,ac as G,a as I,a6 as O,a7 as H,c2 as K,A as U,G as X}from"./index-l3fEjaD9.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const $=(...e)=>e.filter((t,o,s)=>!!t&&t.trim()!==""&&s.indexOf(t)===o).join(" ").trim();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Z=e=>e.replace(/([a-z0-9])([A-Z])/g,"$1-$2").toLowerCase();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const q=e=>e.replace(/^([A-Z])|[\s-_]+(\w)/g,(t,o,s)=>s?s.toUpperCase():o.toLowerCase());/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const N=e=>{const t=q(e);return t.charAt(0).toUpperCase()+t.slice(1)};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */var j={xmlns:"http://www.w3.org/2000/svg",width:24,height:24,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:2,strokeLinecap:"round",strokeLinejoin:"round"};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const V=e=>{for(const t in e)if(t.startsWith("aria-")||t==="role"||t==="title")return!0;return!1},Y=d.createContext({}),J=()=>d.useContext(Y),Q=d.forwardRef(({color:e,size:t,strokeWidth:o,absoluteStrokeWidth:s,className:n="",children:a,iconNode:g,...h},c)=>{const{size:i=24,strokeWidth:p=2,absoluteStrokeWidth:b=!1,color:y="currentColor",className:x=""}=J()??{},f=s??b?Number(o??p)*24/Number(t??i):o??p;return d.createElement("svg",{ref:c,...j,width:t??i??j.width,height:t??i??j.height,stroke:e??y,strokeWidth:f,className:$("lucide",x,n),...!a&&!V(h)&&{"aria-hidden":"true"},...h},[...g.map(([l,u])=>d.createElement(l,u)),...Array.isArray(a)?a:[a]])});/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const R=(e,t)=>{const o=d.forwardRef(({className:s,...n},a)=>d.createElement(Q,{ref:a,iconNode:t,className:$(`lucide-${Z(N(e))}`,`lucide-${e}`,s),...n}));return o.displayName=N(e),o};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const ee=[["path",{d:"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3",key:"wmoenq"}],["path",{d:"M12 9v4",key:"juzpu7"}],["path",{d:"M12 17h.01",key:"p32p05"}]],le=R("triangle-alert",ee);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const te=[["path",{d:"M18 6 6 18",key:"1bl5f8"}],["path",{d:"m6 6 12 12",key:"d8bk6v"}]],E=R("x",te);function re(e){switch(e){case"primary":return"bg-dnd-gold text-dnd-ink hover:bg-dnd-gold-bright";case"secondary":return"bg-dnd-surface-raised text-dnd-text border border-dnd-gold-dim/30 hover:border-dnd-gold/70";case"danger":return"bg-dnd-crimson/10 text-dnd-crimson-bright border border-dnd-crimson/40 hover:bg-dnd-crimson/20 hover:border-dnd-crimson/60";case"arcane":return"bg-gradient-to-r from-dnd-arcane-deep to-dnd-arcane text-dnd-parchment border border-dnd-arcane-bright/40 shadow-halo-arcane";case"ghost":return"bg-transparent text-dnd-gold hover:text-dnd-gold-bright border border-transparent"}}function ne(e){switch(e){case"sm":return"min-h-11 px-3 py-2 text-xs";case"lg":return"min-h-[56px] px-5 py-3.5 text-base";case"md":default:return"min-h-[48px] px-4 py-3 text-sm"}}function ae({variant:e="primary",size:t="md",loading:o=!1,disabled:s=!1,icon:n,iconPosition:a="left",fullWidth:g=!1,haptic:h="light",children:c,onClick:i,className:p="",type:b="button",title:y,"aria-label":x}){const f=s||o,[l,u]=d.useState([]),v=d.useRef(null),S=m=>{if(!f){if(_(h),e==="primary"&&v.current){const k=v.current.getBoundingClientRect(),D=m.clientX-k.left,B=m.clientY-k.top,L=Date.now()+Math.random();u(w=>[...w,{id:L,x:D,y:B}]),setTimeout(()=>u(w=>w.filter(T=>T.id!==L)),400)}i==null||i(m)}},z=`relative overflow-hidden rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors duration-150 disabled:opacity-40 disabled:pointer-events-none ${ne(t)} ${re(e)} ${g?"w-full":""} ${p}`;return r.jsxs(C.button,{ref:v,type:b,onClick:S,disabled:f,className:z,title:y,"aria-label":x,whileTap:{scale:.97},transition:A.press,children:[l.map(m=>r.jsx("span",{className:"absolute rounded-full bg-dnd-parchment/30 pointer-events-none",style:{left:m.x,top:m.y,width:8,height:8,marginLeft:-4,marginTop:-4,animation:"ink-spread 320ms ease-out forwards"}},m.id)),o?r.jsxs(r.Fragment,{children:[r.jsx(P,{}),c]}):r.jsxs(r.Fragment,{children:[n&&a==="left"&&n,c,n&&a==="right"&&n]})]})}const ce=W.memo(ae),oe=d.createContext(null);function ue({open:e,onClose:t,children:o,title:s,dismissible:n=!0,centered:a=!1,className:g="",zClassName:h="z-50"}){const c=F(),i=d.useRef(null),{blurStyle:p,onEntranceComplete:b,entered:y}=G(e),{t:x}=I();O(e),H(e,t,n),K(i,e),d.useEffect(()=>{if(!e)return;const l=document.body.style.overflow;return document.body.style.overflow="hidden",()=>{document.body.style.overflow=l}},[e]);const f=(l,u)=>{(u.offset.y>120||u.velocity.y>800)&&n&&t()};return M.createPortal(r.jsx(U,{children:e&&r.jsx(C.div,{className:`fixed inset-0 ${h} flex items-end md:items-center justify-center`,style:{background:"var(--dnd-overlay)",...p},initial:{opacity:0,pointerEvents:"none"},animate:{opacity:1,pointerEvents:"auto"},exit:{opacity:0,pointerEvents:"none"},transition:{duration:.2},onAnimationComplete:b,onClick:n?t:void 0,children:r.jsxs(C.div,{ref:i,className:`
              relative w-full bg-gradient-parchment surface-parchment
              border-t border-dnd-border-strong md:border
              rounded-t-3xl md:rounded-3xl md:max-w-md
              md:shadow-parchment-2xl
              max-h-[calc(var(--tg-vh,100vh)*0.85)] overflow-hidden
              ${a?"md:self-center":""}
              ${g}
            `,initial:a?{opacity:0,scale:.96}:{y:"100%"},animate:a?{opacity:1,scale:1}:{y:0},exit:a?{opacity:0,scale:.98}:{y:"100%"},transition:A.swipe,drag:n&&!a?"y":!1,dragConstraints:{top:0,bottom:0},dragElastic:{top:0,bottom:.4},dragControls:c,dragListener:!1,onDragEnd:f,onClick:l=>l.stopPropagation(),children:[r.jsx("div",{className:"flex justify-center py-2 cursor-grab active:cursor-grabbing md:hidden touch-none",onPointerDown:l=>c.start(l),children:r.jsx("div",{className:"w-10 h-1 rounded-full bg-dnd-gold-dim/50"})}),s?r.jsxs("div",{className:"relative px-5 pb-3 border-b border-dnd-border/50",children:[r.jsx("h2",{className:"font-display text-xl font-bold text-dnd-gold-bright text-center px-8",children:s}),n&&r.jsx("button",{type:"button",onClick:t,"aria-label":x("common.close"),className:"absolute -top-1 right-2 w-11 h-11 flex items-center justify-center rounded-full text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface-raised transition-colors",children:r.jsx(E,{size:18})})]}):n&&r.jsx("div",{className:"flex justify-end px-2 -mt-2",children:r.jsx("button",{type:"button",onClick:t,"aria-label":x("common.close"),className:"w-11 h-11 flex items-center justify-center rounded-full text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface-raised transition-colors",children:r.jsx(E,{size:18})})}),r.jsx("div",{className:"overflow-y-auto overflow-x-hidden overscroll-contain pb-safe-lg",style:{maxHeight:"calc(var(--tg-vh, 100vh) * 0.85 - 60px)"},children:r.jsx(oe.Provider,{value:y,children:o})})]})},"sheet-backdrop")}),document.body)}function me(e){return X({attr:{viewBox:"0 0 512 512"},child:[{tag:"path",attr:{d:"M292.53 20.5l19 40.594L66.314 28.75 362.03 158.125l-18.967-40.594 149.218 15.282L292.53 20.5zm-252 23.375L318.314 413.97 312.906 348l184.97 146.5L294 186.656l5.406 65.97L40.53 43.875zM20.907 76.22l36.5 316.405L83.03 351.75l68.095 139.344-9.594-241.125-25.624 40.843-95-214.594z"},child:[]}]})(e)}export{ce as B,me as G,ue as S,le as T,E as X,oe as a,R as c};
