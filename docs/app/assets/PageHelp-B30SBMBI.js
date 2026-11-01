import{r as h,j as t,a as _,b as W}from"./react-vendor-CPSJdvAW.js";import{u as C,bS as B,m as v,s as $,bT as O,bF as F,at as H,aC as U,aA as I,aB as K,aD as X,P as Z}from"./index-DidCo9LG.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const A=(...e)=>e.filter((r,n,s)=>!!r&&r.trim()!==""&&s.indexOf(r)===n).join(" ").trim();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Q=e=>e.replace(/([a-z0-9])([A-Z])/g,"$1-$2").toLowerCase();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Y=e=>e.replace(/^([A-Z])|[\s-_]+(\w)/g,(r,n,s)=>s?s.toUpperCase():n.toLowerCase());/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const M=e=>{const r=Y(e);return r.charAt(0).toUpperCase()+r.slice(1)};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */var N={xmlns:"http://www.w3.org/2000/svg",width:24,height:24,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:2,strokeLinecap:"round",strokeLinejoin:"round"};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const G=e=>{for(const r in e)if(r.startsWith("aria-")||r==="role"||r==="title")return!0;return!1},J=h.createContext({}),V=()=>h.useContext(J),q=h.forwardRef(({color:e,size:r,strokeWidth:n,absoluteStrokeWidth:s,className:a="",children:o,iconNode:m,...d},c)=>{const{size:i=24,strokeWidth:u=2,absoluteStrokeWidth:f=!1,color:b="currentColor",className:x=""}=V()??{},l=s??f?Number(n??u)*24/Number(r??i):n??u;return h.createElement("svg",{ref:c,...N,width:r??i??N.width,height:r??i??N.height,stroke:e??b,strokeWidth:l,className:A("lucide",x,a),...!o&&!G(d)&&{"aria-hidden":"true"},...d},[...m.map(([p,w])=>h.createElement(p,w)),...Array.isArray(o)?o:[o]])});/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const y=(e,r)=>{const n=h.forwardRef(({className:s,...a},o)=>h.createElement(q,{ref:o,iconNode:r,className:A(`lucide-${Q(M(e))}`,`lucide-${e}`,s),...a}));return n.displayName=M(e),n};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const ee=[["circle",{cx:"12",cy:"12",r:"10",key:"1mglay"}],["path",{d:"M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3",key:"1u773s"}],["path",{d:"M12 17h.01",key:"p32p05"}]],te=y("circle-question-mark",ee);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const re=[["rect",{width:"12",height:"12",x:"2",y:"10",rx:"2",ry:"2",key:"6agr2n"}],["path",{d:"m17.92 14 3.5-3.5a2.24 2.24 0 0 0 0-3l-5-4.92a2.24 2.24 0 0 0-3 0L10 6",key:"1o487t"}],["path",{d:"M6 18h.01",key:"uhywen"}],["path",{d:"M10 14h.01",key:"ssrbsk"}],["path",{d:"M15 6h.01",key:"cblpky"}],["path",{d:"M18 9h.01",key:"2061c0"}]],xe=y("dices",re);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const ae=[["path",{d:"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3",key:"wmoenq"}],["path",{d:"M12 9v4",key:"juzpu7"}],["path",{d:"M12 17h.01",key:"p32p05"}]],ge=y("triangle-alert",ae);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const ne=[["path",{d:"M12 20h.01",key:"zekei9"}],["path",{d:"M8.5 16.429a5 5 0 0 1 7 0",key:"1bycff"}],["path",{d:"M5 12.859a10 10 0 0 1 5.17-2.69",key:"1dl1wf"}],["path",{d:"M19 12.859a10 10 0 0 0-2.007-1.523",key:"4k23kn"}],["path",{d:"M2 8.82a15 15 0 0 1 4.177-2.643",key:"1grhjp"}],["path",{d:"M22 8.82a15 15 0 0 0-11.288-3.764",key:"z3jwby"}],["path",{d:"m2 2 20 20",key:"1ooewy"}]],se=y("wifi-off",ne);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const oe=[["path",{d:"M18 6 6 18",key:"1bl5f8"}],["path",{d:"m6 6 12 12",key:"d8bk6v"}]],E=y("x",oe);function de(e,r){const n=new Date(e),s=n.toDateString()===new Date().toDateString();return n.toLocaleString(r,{...s?{}:{day:"2-digit",month:"2-digit"},hour:"2-digit",minute:"2-digit",hourCycle:"h23"})}function ye({query:e,className:r=""}){const{t:n,i18n:s}=C(),a=e.isRefetchError?e.error:e.isFetching?e.failureReason:null;if(e.data===void 0||!a)return null;const o=B(a)?"common.offline_data_from":"common.stale_data_from";return t.jsxs("p",{role:"status",className:`flex items-center gap-1.5 rounded-lg border border-dnd-amber/40 bg-dnd-amber/10 px-3 py-1.5 text-xs font-body tabular-nums text-dnd-text ${r}`,children:[t.jsx(se,{size:14,className:"shrink-0 text-dnd-amber"}),t.jsx("span",{className:"min-w-0",children:n(o,{time:de(e.dataUpdatedAt,s.language)})})]})}function ie(e){switch(e){case"elevated":return"bg-dnd-surface-raised border border-dnd-gold-dim/50 shadow-parchment-lg";case"tome":return"bg-gradient-parchment border border-dnd-border-strong shadow-parchment-xl surface-parchment";case"parchment":return"bg-gradient-parchment border border-dnd-border shadow-parchment-md surface-parchment";case"arcane":return"bg-gradient-arcane-mist border border-dnd-arcane/40 shadow-halo-arcane";case"ember":return"bg-dnd-surface border border-dnd-crimson/50 shadow-halo-danger";case"sigil":return"bg-gradient-parchment border border-dnd-gold/40 shadow-parchment-xl surface-parchment";case"flat":default:return"bg-dnd-surface border border-transparent"}}function ce({children:e,className:r="",variant:n="flat",ornamented:s=!1,interactive:a=!1,asMotion:o=!1,layoutId:m,onClick:d,style:c,tabIndex:i,role:u,"aria-label":f}){const b="relative rounded-2xl p-4 transition-shadow duration-300",x=a||d?"cursor-pointer active:scale-[0.98] will-change-transform":"",l=`${b} ${ie(n)} ${x} ${r}`,p=t.jsx("div",{className:s?"relative z-[1] pt-3 px-2 pb-2":"contents",children:e});return o||m?t.jsx(v.div,{layoutId:m,className:l,onClick:d,style:c,tabIndex:i,role:u,"aria-label":f,whileTap:a||d?{scale:.98}:void 0,transition:$.press,children:p}):t.jsx("div",{className:l,onClick:d,style:c,tabIndex:i,role:u,"aria-label":f,children:p})}const we=_.memo(ce);function le(e){switch(e){case"primary":return"bg-gradient-gold text-dnd-ink shadow-engrave";case"secondary":return"bg-dnd-surface-raised text-dnd-text border border-dnd-gold-dim/30 hover:border-dnd-gold/70";case"danger":return"bg-dnd-crimson/15 text-dnd-crimson-bright border border-dnd-crimson/40 hover:bg-dnd-crimson/25 hover:border-dnd-crimson/60";case"arcane":return"bg-gradient-to-r from-dnd-arcane-deep to-dnd-arcane text-dnd-parchment border border-dnd-arcane-bright/40 shadow-halo-arcane";case"ghost":return"bg-transparent text-dnd-gold hover:text-dnd-gold-bright border border-transparent"}}function he(e){switch(e){case"sm":return"min-h-11 px-3 py-2 text-xs";case"lg":return"min-h-[56px] px-5 py-3.5 text-base";case"md":default:return"min-h-[48px] px-4 py-3 text-sm"}}function me({variant:e="primary",size:r="md",loading:n=!1,disabled:s=!1,icon:a,iconPosition:o="left",fullWidth:m=!1,haptic:d="light",children:c,onClick:i,className:u="",type:f="button",title:b,"aria-label":x}){const l=s||n,[p,w]=h.useState([]),j=h.useRef(null),R=g=>{if(!l){if(F(d),e==="primary"&&j.current){const S=j.current.getBoundingClientRect(),T=g.clientX-S.left,L=g.clientY-S.top,D=Date.now()+Math.random();w(k=>[...k,{id:D,x:T,y:L}]),setTimeout(()=>w(k=>k.filter(P=>P.id!==D)),400)}i==null||i(g)}},z=`relative overflow-hidden rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors duration-150 disabled:opacity-40 disabled:pointer-events-none ${he(r)} ${le(e)} ${m?"w-full":""} ${u}`;return t.jsxs(v.button,{ref:j,type:f,onClick:R,disabled:l,className:z,title:b,"aria-label":x,whileTap:{scale:.97},transition:$.press,children:[p.map(g=>t.jsx("span",{className:"absolute rounded-full bg-dnd-parchment/30 pointer-events-none",style:{left:g.x,top:g.y,width:8,height:8,marginLeft:-4,marginTop:-4,animation:"ink-spread 320ms ease-out forwards"}},g.id)),n?t.jsxs(t.Fragment,{children:[t.jsx(O,{}),c]}):t.jsxs(t.Fragment,{children:[a&&o==="left"&&a,c,a&&o==="right"&&a]})]})}const ve=_.memo(me);function ue({open:e,onClose:r,children:n,title:s,dismissible:a=!0,centered:o=!1,className:m="",zClassName:d="z-50"}){const c=H(),i=h.useRef(null),{blurStyle:u,onEntranceComplete:f}=U(e),{t:b}=C();I(e),K(e,r,a),h.useEffect(()=>{if(!e)return;const l=document.body.style.overflow;return document.body.style.overflow="hidden",()=>{document.body.style.overflow=l}},[e]);const x=(l,p)=>{(p.offset.y>120||p.velocity.y>800)&&a&&r()};return W.createPortal(t.jsx(X,{children:e&&t.jsx(v.div,{className:`fixed inset-0 ${d} flex items-end md:items-center justify-center`,style:{background:"var(--dnd-overlay)",...u},initial:{opacity:0,pointerEvents:"none"},animate:{opacity:1,pointerEvents:"auto"},exit:{opacity:0,pointerEvents:"none"},transition:{duration:.2},onAnimationComplete:f,onClick:a?r:void 0,children:t.jsxs(v.div,{ref:i,className:`
              relative w-full bg-gradient-parchment surface-parchment
              border-t border-dnd-border-strong md:border
              rounded-t-3xl md:rounded-3xl md:max-w-md
              shadow-parchment-2xl
              max-h-[85vh] overflow-hidden
              ${o?"md:self-center":""}
              ${m}
            `,initial:o?{opacity:0,scale:.96}:{y:"100%"},animate:o?{opacity:1,scale:1}:{y:0},exit:o?{opacity:0,scale:.98}:{y:"100%"},transition:$.swipe,drag:a&&!o?"y":!1,dragConstraints:{top:0,bottom:0},dragElastic:{top:0,bottom:.4},dragControls:c,dragListener:!1,onDragEnd:x,onClick:l=>l.stopPropagation(),children:[t.jsx("div",{className:"flex justify-center py-2 cursor-grab active:cursor-grabbing md:hidden touch-none",onPointerDown:l=>c.start(l),children:t.jsx("div",{className:"w-10 h-1 rounded-full bg-dnd-gold-dim/50"})}),s?t.jsxs("div",{className:"relative px-5 pb-3 border-b border-dnd-border/50",children:[t.jsx("h2",{className:"font-display text-xl font-bold text-dnd-gold-bright text-center pr-8",children:s}),a&&t.jsx("button",{type:"button",onClick:r,"aria-label":b("common.close"),className:"absolute -top-1 right-2 w-10 h-10 flex items-center justify-center rounded-full text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface-raised transition-colors",children:t.jsx(E,{size:18})})]}):a&&t.jsx("div",{className:"flex justify-end px-2 -mt-2",children:t.jsx("button",{type:"button",onClick:r,"aria-label":b("common.close"),className:"w-10 h-10 flex items-center justify-center rounded-full text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface-raised transition-colors",children:t.jsx(E,{size:18})})}),t.jsx("div",{className:"overflow-y-auto overflow-x-hidden overscroll-contain pb-safe-lg",style:{maxHeight:"calc(85vh - 60px)"},children:n})]})},"sheet-backdrop")}),document.body)}function je({helpKey:e,title:r,className:n="w-11 h-11"}){const{t:s}=C(),[a,o]=h.useState(!1),m=s(`help.${e}`,{returnObjects:!0});if(typeof m!="object")return null;const d=a?m:null;return t.jsxs(t.Fragment,{children:[t.jsx(Z,{onClick:()=>o(!0),className:`${n} shrink-0 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30`,"aria-label":s("help.open"),whileTap:{scale:.9},whileHover:{boxShadow:"var(--halo-gold)"},children:t.jsx(te,{size:20,className:"text-dnd-gold-bright"})}),t.jsx(ue,{open:a,onClose:()=>o(!1),title:s("help.title",{page:r}),children:d&&t.jsxs("div",{className:"px-5 py-4 space-y-5 font-body text-dnd-text",children:[t.jsx("p",{className:"text-sm leading-relaxed text-dnd-text-muted",children:d.summary}),d.sections.map(c=>t.jsxs("section",{className:"space-y-2",children:[t.jsx("h3",{className:"font-display font-bold text-dnd-gold-bright",children:c.title}),t.jsx("ul",{className:"list-disc pl-5 space-y-1.5 text-sm leading-relaxed marker:text-dnd-gold-dim",children:c.items.map(i=>t.jsx("li",{children:i},i))})]},c.title))]})})]})}export{ve as B,xe as D,ye as O,je as P,ue as S,ge as T,se as W,E as X,we as a,y as c};
