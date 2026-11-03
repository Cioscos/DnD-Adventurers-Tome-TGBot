import{r as l,R as E,j as t,a as P}from"./react-vendor-BGC0LuHo.js";import{m as j,f as C,S as T,g as B,ad as O,Y as F,u as $,W as G,X as U,bV as I,U as K,bW as X,P as V,G as Y}from"./index-CsVvQfQR.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const _=(...e)=>e.filter((r,s,a)=>!!r&&r.trim()!==""&&a.indexOf(r)===s).join(" ").trim();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Z=e=>e.replace(/([a-z0-9])([A-Z])/g,"$1-$2").toLowerCase();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Q=e=>e.replace(/^([A-Z])|[\s-_]+(\w)/g,(r,s,a)=>a?a.toUpperCase():s.toLowerCase());/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const M=e=>{const r=Q(e);return r.charAt(0).toUpperCase()+r.slice(1)};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */var N={xmlns:"http://www.w3.org/2000/svg",width:24,height:24,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:2,strokeLinecap:"round",strokeLinejoin:"round"};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const J=e=>{for(const r in e)if(r.startsWith("aria-")||r==="role"||r==="title")return!0;return!1},q=l.createContext({}),ee=()=>l.useContext(q),te=l.forwardRef(({color:e,size:r,strokeWidth:s,absoluteStrokeWidth:a,className:n="",children:o,iconNode:u,...i},c)=>{const{size:d=24,strokeWidth:h=2,absoluteStrokeWidth:x=!1,color:g="currentColor",className:b=""}=ee()??{},f=a??x?Number(s??h)*24/Number(r??d):s??h;return l.createElement("svg",{ref:c,...N,width:r??d??N.width,height:r??d??N.height,stroke:e??g,strokeWidth:f,className:_("lucide",b,n),...!o&&!J(i)&&{"aria-hidden":"true"},...i},[...u.map(([m,p])=>l.createElement(m,p)),...Array.isArray(o)?o:[o]])});/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const w=(e,r)=>{const s=l.forwardRef(({className:a,...n},o)=>l.createElement(te,{ref:o,iconNode:r,className:_(`lucide-${Z(M(e))}`,`lucide-${e}`,a),...n}));return s.displayName=M(e),s};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const re=[["circle",{cx:"12",cy:"12",r:"10",key:"1mglay"}],["path",{d:"M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3",key:"1u773s"}],["path",{d:"M12 17h.01",key:"p32p05"}]],ae=w("circle-question-mark",re);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const ne=[["rect",{width:"12",height:"12",x:"2",y:"10",rx:"2",ry:"2",key:"6agr2n"}],["path",{d:"m17.92 14 3.5-3.5a2.24 2.24 0 0 0 0-3l-5-4.92a2.24 2.24 0 0 0-3 0L10 6",key:"1o487t"}],["path",{d:"M6 18h.01",key:"uhywen"}],["path",{d:"M10 14h.01",key:"ssrbsk"}],["path",{d:"M15 6h.01",key:"cblpky"}],["path",{d:"M18 9h.01",key:"2061c0"}]],ve=w("dices",ne);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const se=[["path",{d:"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3",key:"wmoenq"}],["path",{d:"M12 9v4",key:"juzpu7"}],["path",{d:"M12 17h.01",key:"p32p05"}]],we=w("triangle-alert",se);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const oe=[["path",{d:"M12 20h.01",key:"zekei9"}],["path",{d:"M8.5 16.429a5 5 0 0 1 7 0",key:"1bycff"}],["path",{d:"M5 12.859a10 10 0 0 1 5.17-2.69",key:"1dl1wf"}],["path",{d:"M19 12.859a10 10 0 0 0-2.007-1.523",key:"4k23kn"}],["path",{d:"M2 8.82a15 15 0 0 1 4.177-2.643",key:"1grhjp"}],["path",{d:"M22 8.82a15 15 0 0 0-11.288-3.764",key:"z3jwby"}],["path",{d:"m2 2 20 20",key:"1ooewy"}]],de=w("wifi-off",oe);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const ie=[["path",{d:"M18 6 6 18",key:"1bl5f8"}],["path",{d:"m6 6 12 12",key:"d8bk6v"}]],D=w("x",ie);function ce(e){switch(e){case"primary":return"bg-gradient-gold text-dnd-ink shadow-engrave";case"secondary":return"bg-dnd-surface-raised text-dnd-text border border-dnd-gold-dim/30 hover:border-dnd-gold/70";case"danger":return"bg-dnd-crimson/15 text-dnd-crimson-bright border border-dnd-crimson/40 hover:bg-dnd-crimson/25 hover:border-dnd-crimson/60";case"arcane":return"bg-gradient-to-r from-dnd-arcane-deep to-dnd-arcane text-dnd-parchment border border-dnd-arcane-bright/40 shadow-halo-arcane";case"ghost":return"bg-transparent text-dnd-gold hover:text-dnd-gold-bright border border-transparent"}}function le(e){switch(e){case"sm":return"min-h-11 px-3 py-2 text-xs";case"lg":return"min-h-[56px] px-5 py-3.5 text-base";case"md":default:return"min-h-[48px] px-4 py-3 text-sm"}}function he({variant:e="primary",size:r="md",loading:s=!1,disabled:a=!1,icon:n,iconPosition:o="left",fullWidth:u=!1,haptic:i="light",children:c,onClick:d,className:h="",type:x="button",title:g,"aria-label":b}){const f=a||s,[m,p]=l.useState([]),v=l.useRef(null),R=y=>{if(!f){if(B(i),e==="primary"&&v.current){const S=v.current.getBoundingClientRect(),L=y.clientX-S.left,H=y.clientY-S.top,z=Date.now()+Math.random();p(k=>[...k,{id:z,x:L,y:H}]),setTimeout(()=>p(k=>k.filter(W=>W.id!==z)),400)}d==null||d(y)}},A=`relative overflow-hidden rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors duration-150 disabled:opacity-40 disabled:pointer-events-none ${le(r)} ${ce(e)} ${u?"w-full":""} ${h}`;return t.jsxs(j.button,{ref:v,type:x,onClick:R,disabled:f,className:A,title:g,"aria-label":b,whileTap:{scale:.97},transition:C.press,children:[m.map(y=>t.jsx("span",{className:"absolute rounded-full bg-dnd-parchment/30 pointer-events-none",style:{left:y.x,top:y.y,width:8,height:8,marginLeft:-4,marginTop:-4,animation:"ink-spread 320ms ease-out forwards"}},y.id)),s?t.jsxs(t.Fragment,{children:[t.jsx(T,{}),c]}):t.jsxs(t.Fragment,{children:[n&&o==="left"&&n,c,n&&o==="right"&&n]})]})}const je=E.memo(he),me=l.createContext(null);function ue({open:e,onClose:r,children:s,title:a,dismissible:n=!0,centered:o=!1,className:u="",zClassName:i="z-50"}){const c=O(),d=l.useRef(null),{blurStyle:h,onEntranceComplete:x,entered:g}=F(e),{t:b}=$();G(e),U(e,r,n),I(d,e),l.useEffect(()=>{if(!e)return;const m=document.body.style.overflow;return document.body.style.overflow="hidden",()=>{document.body.style.overflow=m}},[e]);const f=(m,p)=>{(p.offset.y>120||p.velocity.y>800)&&n&&r()};return P.createPortal(t.jsx(K,{children:e&&t.jsx(j.div,{className:`fixed inset-0 ${i} flex items-end md:items-center justify-center`,style:{background:"var(--dnd-overlay)",...h},initial:{opacity:0,pointerEvents:"none"},animate:{opacity:1,pointerEvents:"auto"},exit:{opacity:0,pointerEvents:"none"},transition:{duration:.2},onAnimationComplete:x,onClick:n?r:void 0,children:t.jsxs(j.div,{ref:d,className:`
              relative w-full bg-gradient-parchment surface-parchment
              border-t border-dnd-border-strong md:border
              rounded-t-3xl md:rounded-3xl md:max-w-md
              md:shadow-parchment-2xl
              max-h-[calc(var(--tg-vh,100vh)*0.85)] overflow-hidden
              ${o?"md:self-center":""}
              ${u}
            `,initial:o?{opacity:0,scale:.96}:{y:"100%"},animate:o?{opacity:1,scale:1}:{y:0},exit:o?{opacity:0,scale:.98}:{y:"100%"},transition:C.swipe,drag:n&&!o?"y":!1,dragConstraints:{top:0,bottom:0},dragElastic:{top:0,bottom:.4},dragControls:c,dragListener:!1,onDragEnd:f,onClick:m=>m.stopPropagation(),children:[t.jsx("div",{className:"flex justify-center py-2 cursor-grab active:cursor-grabbing md:hidden touch-none",onPointerDown:m=>c.start(m),children:t.jsx("div",{className:"w-10 h-1 rounded-full bg-dnd-gold-dim/50"})}),a?t.jsxs("div",{className:"relative px-5 pb-3 border-b border-dnd-border/50",children:[t.jsx("h2",{className:"font-display text-xl font-bold text-dnd-gold-bright text-center pr-8",children:a}),n&&t.jsx("button",{type:"button",onClick:r,"aria-label":b("common.close"),className:"absolute -top-1 right-2 w-11 h-11 flex items-center justify-center rounded-full text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface-raised transition-colors",children:t.jsx(D,{size:18})})]}):n&&t.jsx("div",{className:"flex justify-end px-2 -mt-2",children:t.jsx("button",{type:"button",onClick:r,"aria-label":b("common.close"),className:"w-11 h-11 flex items-center justify-center rounded-full text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface-raised transition-colors",children:t.jsx(D,{size:18})})}),t.jsx("div",{className:"overflow-y-auto overflow-x-hidden overscroll-contain pb-safe-lg",style:{maxHeight:"calc(var(--tg-vh, 100vh) * 0.85 - 60px)"},children:t.jsx(me.Provider,{value:g,children:s})})]})},"sheet-backdrop")}),document.body)}function pe(e,r){const s=new Date(e),a=s.toDateString()===new Date().toDateString();return s.toLocaleString(r,{...a?{}:{day:"2-digit",month:"2-digit"},hour:"2-digit",minute:"2-digit",hourCycle:"h23"})}function ke({query:e,className:r=""}){const{t:s,i18n:a}=$(),n=e.isRefetchError?e.error:e.isFetching?e.failureReason:null;if(e.data===void 0||!n)return null;const o=X(n)?"common.offline_data_from":"common.stale_data_from";return t.jsxs("p",{role:"status",className:`flex items-center gap-1.5 rounded-lg border border-dnd-amber/40 bg-dnd-amber/10 px-3 py-1.5 text-xs font-body tabular-nums text-dnd-text ${r}`,children:[t.jsx(de,{size:14,className:"shrink-0 text-dnd-amber"}),t.jsx("span",{className:"min-w-0",children:s(o,{time:pe(e.dataUpdatedAt,a.language)})})]})}function fe(e){switch(e){case"elevated":return"bg-dnd-surface-raised border border-dnd-gold-dim/50 shadow-parchment-lg";case"tome":return"bg-gradient-parchment border border-dnd-border-strong shadow-parchment-xl surface-parchment";case"parchment":return"bg-gradient-parchment border border-dnd-border shadow-parchment-md surface-parchment";case"arcane":return"bg-gradient-arcane-mist border border-dnd-arcane/40 shadow-halo-arcane";case"ember":return"bg-dnd-surface border border-dnd-crimson/50 shadow-halo-danger";case"sigil":return"bg-gradient-parchment border border-dnd-gold/40 shadow-parchment-xl surface-parchment";case"flat":default:return"bg-dnd-surface border border-transparent"}}function xe({children:e,className:r="",variant:s="flat",ornamented:a=!1,interactive:n=!1,asMotion:o=!1,layoutId:u,onClick:i,style:c,tabIndex:d,role:h,"aria-label":x}){const g="relative rounded-2xl p-4 transition-shadow duration-300",b=n||i?"cursor-pointer active:scale-[0.98] will-change-transform":"",f=`${g} ${fe(s)} ${b} ${r}`,m=r.split(/\s+/).filter(v=>/^(space-[xy]-|divide-)/.test(v)).join(" "),p=a?t.jsx("div",{className:`relative z-[1] pt-3 px-2 pb-2 ${m}`,children:e}):e;return o||u?t.jsx(j.div,{layoutId:u,className:f,onClick:i,style:c,tabIndex:d,role:h,"aria-label":x,whileTap:n||i?{scale:.98}:void 0,transition:C.press,children:p}):t.jsx("div",{className:f,onClick:i,style:c,tabIndex:d,role:h,"aria-label":x,children:p})}const Ne=E.memo(xe);function Ce({helpKey:e,title:r,className:s="w-11 h-11"}){const{t:a}=$(),[n,o]=l.useState(!1),u=`help.${e}.summary`;if(a(u)===u)return null;const i=n?a(`help.${e}`,{returnObjects:!0}):null,c=typeof i=="object"?i:null;return t.jsxs(t.Fragment,{children:[t.jsx(V,{onClick:()=>o(!0),className:`${s} shrink-0 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30`,"aria-label":a("help.open"),whileTap:{scale:.9},whileHover:{boxShadow:"var(--halo-gold)"},children:t.jsx(ae,{size:20,className:"text-dnd-gold-bright"})}),t.jsx(ue,{open:n,onClose:()=>o(!1),title:a("help.title",{page:r}),children:c&&t.jsxs("div",{className:"px-5 py-4 space-y-5 font-body text-dnd-text",children:[t.jsx("p",{className:"text-sm leading-relaxed text-dnd-text-muted",children:c.summary}),c.sections.map(d=>t.jsxs("section",{className:"space-y-2",children:[t.jsx("h3",{className:"font-display font-bold text-dnd-gold-bright",children:d.title}),t.jsx("ul",{className:"list-disc pl-5 space-y-1.5 text-sm leading-relaxed marker:text-dnd-gold-dim",children:d.items.map(h=>t.jsx("li",{children:h},h))})]},d.title))]})})]})}function $e(e){return Y({attr:{viewBox:"0 0 512 512"},child:[{tag:"path",attr:{d:"M92.906 94.813l60.438 79.75 78.125-79.75H92.905zm189.25 0L359.25 173.5l58.688-78.688H282.155zm-25.344.843l-84.718 86.47H341.53l-84.717-86.47zm177.907 7.906l-58.626 78.563H494.53l-59.81-78.563zm-358.064.75l-57.78 77.813h116.78l-59-77.813zm-58.5 96.5L226.562 429.22 143.344 200.81H18.156zm145.063 0l93.593 256.844 93.593-256.844H163.22zm207.06 0L287.064 429.22 495.469 200.81H370.28z"},child:[]}]})(e)}export{je as B,ve as D,$e as G,ke as O,Ce as P,ue as S,we as T,de as W,D as X,Ne as a,me as b,w as c};
