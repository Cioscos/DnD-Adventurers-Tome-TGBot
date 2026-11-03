import{r as l,R as _,j as r,a as O}from"./react-vendor-BGC0LuHo.js";import{m as j,f as C,S as F,bU as B,ac as I,W as U,u as $,U as H,V as K,bV as V,Q,bW as X,P as Z}from"./index-CoLqm00d.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const A=(...e)=>e.filter((t,a,n)=>!!t&&t.trim()!==""&&n.indexOf(t)===a).join(" ").trim();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const G=e=>e.replace(/([a-z0-9])([A-Z])/g,"$1-$2").toLowerCase();/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Y=e=>e.replace(/^([A-Z])|[\s-_]+(\w)/g,(t,a,n)=>n?n.toUpperCase():a.toLowerCase());/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const E=e=>{const t=Y(e);return t.charAt(0).toUpperCase()+t.slice(1)};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */var N={xmlns:"http://www.w3.org/2000/svg",width:24,height:24,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:2,strokeLinecap:"round",strokeLinejoin:"round"};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const J=e=>{for(const t in e)if(t.startsWith("aria-")||t==="role"||t==="title")return!0;return!1},q=l.createContext({}),ee=()=>l.useContext(q),te=l.forwardRef(({color:e,size:t,strokeWidth:a,absoluteStrokeWidth:n,className:s="",children:o,iconNode:m,...i},c)=>{const{size:d=24,strokeWidth:u=2,absoluteStrokeWidth:b=!1,color:g="currentColor",className:x=""}=ee()??{},f=n??b?Number(a??u)*24/Number(t??d):a??u;return l.createElement("svg",{ref:c,...N,width:t??d??N.width,height:t??d??N.height,stroke:e??g,strokeWidth:f,className:A("lucide",x,s),...!o&&!J(i)&&{"aria-hidden":"true"},...i},[...m.map(([h,p])=>l.createElement(h,p)),...Array.isArray(o)?o:[o]])});/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const w=(e,t)=>{const a=l.forwardRef(({className:n,...s},o)=>l.createElement(te,{ref:o,iconNode:t,className:A(`lucide-${G(E(e))}`,`lucide-${e}`,n),...s}));return a.displayName=E(e),a};/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const re=[["circle",{cx:"12",cy:"12",r:"10",key:"1mglay"}],["path",{d:"M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3",key:"1u773s"}],["path",{d:"M12 17h.01",key:"p32p05"}]],ae=w("circle-question-mark",re);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const ne=[["rect",{width:"12",height:"12",x:"2",y:"10",rx:"2",ry:"2",key:"6agr2n"}],["path",{d:"m17.92 14 3.5-3.5a2.24 2.24 0 0 0 0-3l-5-4.92a2.24 2.24 0 0 0-3 0L10 6",key:"1o487t"}],["path",{d:"M6 18h.01",key:"uhywen"}],["path",{d:"M10 14h.01",key:"ssrbsk"}],["path",{d:"M15 6h.01",key:"cblpky"}],["path",{d:"M18 9h.01",key:"2061c0"}]],we=w("dices",ne);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const se=[["path",{d:"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3",key:"wmoenq"}],["path",{d:"M12 9v4",key:"juzpu7"}],["path",{d:"M12 17h.01",key:"p32p05"}]],je=w("triangle-alert",se);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const oe=[["path",{d:"M12 20h.01",key:"zekei9"}],["path",{d:"M8.5 16.429a5 5 0 0 1 7 0",key:"1bycff"}],["path",{d:"M5 12.859a10 10 0 0 1 5.17-2.69",key:"1dl1wf"}],["path",{d:"M19 12.859a10 10 0 0 0-2.007-1.523",key:"4k23kn"}],["path",{d:"M2 8.82a15 15 0 0 1 4.177-2.643",key:"1grhjp"}],["path",{d:"M22 8.82a15 15 0 0 0-11.288-3.764",key:"z3jwby"}],["path",{d:"m2 2 20 20",key:"1ooewy"}]],de=w("wifi-off",oe);/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const ie=[["path",{d:"M18 6 6 18",key:"1bl5f8"}],["path",{d:"m6 6 12 12",key:"d8bk6v"}]],M=w("x",ie);function ce(e){switch(e){case"primary":return"bg-gradient-gold text-dnd-ink shadow-engrave";case"secondary":return"bg-dnd-surface-raised text-dnd-text border border-dnd-gold-dim/30 hover:border-dnd-gold/70";case"danger":return"bg-dnd-crimson/15 text-dnd-crimson-bright border border-dnd-crimson/40 hover:bg-dnd-crimson/25 hover:border-dnd-crimson/60";case"arcane":return"bg-gradient-to-r from-dnd-arcane-deep to-dnd-arcane text-dnd-parchment border border-dnd-arcane-bright/40 shadow-halo-arcane";case"ghost":return"bg-transparent text-dnd-gold hover:text-dnd-gold-bright border border-transparent"}}function le(e){switch(e){case"sm":return"min-h-11 px-3 py-2 text-xs";case"lg":return"min-h-[56px] px-5 py-3.5 text-base";case"md":default:return"min-h-[48px] px-4 py-3 text-sm"}}function ue({variant:e="primary",size:t="md",loading:a=!1,disabled:n=!1,icon:s,iconPosition:o="left",fullWidth:m=!1,haptic:i="light",children:c,onClick:d,className:u="",type:b="button",title:g,"aria-label":x}){const f=n||a,[h,p]=l.useState([]),v=l.useRef(null),R=y=>{if(!f){if(B(i),e==="primary"&&v.current){const S=v.current.getBoundingClientRect(),z=y.clientX-S.left,W=y.clientY-S.top,D=Date.now()+Math.random();p(k=>[...k,{id:D,x:z,y:W}]),setTimeout(()=>p(k=>k.filter(P=>P.id!==D)),400)}d==null||d(y)}},L=`relative overflow-hidden rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors duration-150 disabled:opacity-40 disabled:pointer-events-none ${le(t)} ${ce(e)} ${m?"w-full":""} ${u}`;return r.jsxs(j.button,{ref:v,type:b,onClick:R,disabled:f,className:L,title:g,"aria-label":x,whileTap:{scale:.97},transition:C.press,children:[h.map(y=>r.jsx("span",{className:"absolute rounded-full bg-dnd-parchment/30 pointer-events-none",style:{left:y.x,top:y.y,width:8,height:8,marginLeft:-4,marginTop:-4,animation:"ink-spread 320ms ease-out forwards"}},y.id)),a?r.jsxs(r.Fragment,{children:[r.jsx(F,{}),c]}):r.jsxs(r.Fragment,{children:[s&&o==="left"&&s,c,s&&o==="right"&&s]})]})}const ke=_.memo(ue),he=l.createContext(null);function me({open:e,onClose:t,children:a,title:n,dismissible:s=!0,centered:o=!1,className:m="",zClassName:i="z-50"}){const c=I(),d=l.useRef(null),{blurStyle:u,onEntranceComplete:b,entered:g}=U(e),{t:x}=$();H(e),K(e,t,s),V(d,e),l.useEffect(()=>{if(!e)return;const h=document.body.style.overflow;return document.body.style.overflow="hidden",()=>{document.body.style.overflow=h}},[e]);const f=(h,p)=>{(p.offset.y>120||p.velocity.y>800)&&s&&t()};return O.createPortal(r.jsx(Q,{children:e&&r.jsx(j.div,{className:`fixed inset-0 ${i} flex items-end md:items-center justify-center`,style:{background:"var(--dnd-overlay)",...u},initial:{opacity:0,pointerEvents:"none"},animate:{opacity:1,pointerEvents:"auto"},exit:{opacity:0,pointerEvents:"none"},transition:{duration:.2},onAnimationComplete:b,onClick:s?t:void 0,children:r.jsxs(j.div,{ref:d,className:`
              relative w-full bg-gradient-parchment surface-parchment
              border-t border-dnd-border-strong md:border
              rounded-t-3xl md:rounded-3xl md:max-w-md
              md:shadow-parchment-2xl
              max-h-[calc(var(--tg-vh,100vh)*0.85)] overflow-hidden
              ${o?"md:self-center":""}
              ${m}
            `,initial:o?{opacity:0,scale:.96}:{y:"100%"},animate:o?{opacity:1,scale:1}:{y:0},exit:o?{opacity:0,scale:.98}:{y:"100%"},transition:C.swipe,drag:s&&!o?"y":!1,dragConstraints:{top:0,bottom:0},dragElastic:{top:0,bottom:.4},dragControls:c,dragListener:!1,onDragEnd:f,onClick:h=>h.stopPropagation(),children:[r.jsx("div",{className:"flex justify-center py-2 cursor-grab active:cursor-grabbing md:hidden touch-none",onPointerDown:h=>c.start(h),children:r.jsx("div",{className:"w-10 h-1 rounded-full bg-dnd-gold-dim/50"})}),n?r.jsxs("div",{className:"relative px-5 pb-3 border-b border-dnd-border/50",children:[r.jsx("h2",{className:"font-display text-xl font-bold text-dnd-gold-bright text-center pr-8",children:n}),s&&r.jsx("button",{type:"button",onClick:t,"aria-label":x("common.close"),className:"absolute -top-1 right-2 w-11 h-11 flex items-center justify-center rounded-full text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface-raised transition-colors",children:r.jsx(M,{size:18})})]}):s&&r.jsx("div",{className:"flex justify-end px-2 -mt-2",children:r.jsx("button",{type:"button",onClick:t,"aria-label":x("common.close"),className:"w-11 h-11 flex items-center justify-center rounded-full text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface-raised transition-colors",children:r.jsx(M,{size:18})})}),r.jsx("div",{className:"overflow-y-auto overflow-x-hidden overscroll-contain pb-safe-lg",style:{maxHeight:"calc(var(--tg-vh, 100vh) * 0.85 - 60px)"},children:r.jsx(he.Provider,{value:g,children:a})})]})},"sheet-backdrop")}),document.body)}function pe(e,t){const a=new Date(e),n=a.toDateString()===new Date().toDateString();return a.toLocaleString(t,{...n?{}:{day:"2-digit",month:"2-digit"},hour:"2-digit",minute:"2-digit",hourCycle:"h23"})}function Ne({query:e,className:t=""}){const{t:a,i18n:n}=$(),s=e.isRefetchError?e.error:e.isFetching?e.failureReason:null;if(e.data===void 0||!s)return null;const o=X(s)?"common.offline_data_from":"common.stale_data_from";return r.jsxs("p",{role:"status",className:`flex items-center gap-1.5 rounded-lg border border-dnd-amber/40 bg-dnd-amber/10 px-3 py-1.5 text-xs font-body tabular-nums text-dnd-text ${t}`,children:[r.jsx(de,{size:14,className:"shrink-0 text-dnd-amber"}),r.jsx("span",{className:"min-w-0",children:a(o,{time:pe(e.dataUpdatedAt,n.language)})})]})}function fe(e){switch(e){case"elevated":return"bg-dnd-surface-raised border border-dnd-gold-dim/50 shadow-parchment-lg";case"tome":return"bg-gradient-parchment border border-dnd-border-strong shadow-parchment-xl surface-parchment";case"parchment":return"bg-gradient-parchment border border-dnd-border shadow-parchment-md surface-parchment";case"arcane":return"bg-gradient-arcane-mist border border-dnd-arcane/40 shadow-halo-arcane";case"ember":return"bg-dnd-surface border border-dnd-crimson/50 shadow-halo-danger";case"sigil":return"bg-gradient-parchment border border-dnd-gold/40 shadow-parchment-xl surface-parchment";case"flat":default:return"bg-dnd-surface border border-transparent"}}function be({children:e,className:t="",variant:a="flat",ornamented:n=!1,interactive:s=!1,asMotion:o=!1,layoutId:m,onClick:i,style:c,tabIndex:d,role:u,"aria-label":b}){const g="relative rounded-2xl p-4 transition-shadow duration-300",x=s||i?"cursor-pointer active:scale-[0.98] will-change-transform":"",f=`${g} ${fe(a)} ${x} ${t}`,h=t.split(/\s+/).filter(v=>/^(space-[xy]-|divide-)/.test(v)).join(" "),p=n?r.jsx("div",{className:`relative z-[1] pt-3 px-2 pb-2 ${h}`,children:e}):e;return o||m?r.jsx(j.div,{layoutId:m,className:f,onClick:i,style:c,tabIndex:d,role:u,"aria-label":b,whileTap:s||i?{scale:.98}:void 0,transition:C.press,children:p}):r.jsx("div",{className:f,onClick:i,style:c,tabIndex:d,role:u,"aria-label":b,children:p})}const Ce=_.memo(be);function $e({helpKey:e,title:t,className:a="w-11 h-11"}){const{t:n}=$(),[s,o]=l.useState(!1),m=`help.${e}.summary`;if(n(m)===m)return null;const i=s?n(`help.${e}`,{returnObjects:!0}):null,c=typeof i=="object"?i:null;return r.jsxs(r.Fragment,{children:[r.jsx(Z,{onClick:()=>o(!0),className:`${a} shrink-0 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30`,"aria-label":n("help.open"),whileTap:{scale:.9},whileHover:{boxShadow:"var(--halo-gold)"},children:r.jsx(ae,{size:20,className:"text-dnd-gold-bright"})}),r.jsx(me,{open:s,onClose:()=>o(!1),title:n("help.title",{page:t}),children:c&&r.jsxs("div",{className:"px-5 py-4 space-y-5 font-body text-dnd-text",children:[r.jsx("p",{className:"text-sm leading-relaxed text-dnd-text-muted",children:c.summary}),c.sections.map(d=>r.jsxs("section",{className:"space-y-2",children:[r.jsx("h3",{className:"font-display font-bold text-dnd-gold-bright",children:d.title}),r.jsx("ul",{className:"list-disc pl-5 space-y-1.5 text-sm leading-relaxed marker:text-dnd-gold-dim",children:d.items.map(u=>r.jsx("li",{children:u},u))})]},d.title))]})})]})}const xe={it:"it-IT",en:"en-US"};function T(e){return xe[e]??e}function Se(e,t){return new Intl.NumberFormat(T(t)).format(e)}function De(e,t){const a=typeof e=="string"?new Date(e):e;return new Intl.DateTimeFormat(T(t),{hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).format(a)}export{ke as B,we as D,Ne as O,$e as P,me as S,je as T,de as W,M as X,Ce as a,De as b,w as c,he as d,Se as f,T as l};
