import{c as f}from"./index-B8mGBPL4.js";import{r as e,j as n}from"./react-vendor-BGC0LuHo.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const m=[["path",{d:"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3",key:"wmoenq"}],["path",{d:"M12 9v4",key:"juzpu7"}],["path",{d:"M12 17h.01",key:"p32p05"}]],v=f("triangle-alert",m);function y(t){const a=e.useRef(!1),r=!a.current;return e.useEffect(()=>{t!=null&&(a.current=!0)},[t]),r}function x({children:t,className:a=""}){const r=e.useRef(null),[p,d]=e.useState(!1),[s]=e.useState(()=>!localStorage.getItem("scroll-hint-seen"));return e.useEffect(()=>{const o=r.current;if(!o)return;const i=new IntersectionObserver(([c])=>{d(c.isIntersecting),c.isIntersecting&&s&&localStorage.setItem("scroll-hint-seen","1")},{threshold:.1});return i.observe(o),()=>i.disconnect()},[s]),n.jsxs("div",{className:`relative ${a}`,children:[t,n.jsx("div",{ref:r,className:"h-1"}),!p&&n.jsx("div",{className:"pointer-events-none absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-dnd-bg to-transparent flex items-end justify-center pb-2",children:s&&n.jsx("span",{className:"text-xs text-dnd-gold-dim opacity-70",children:"↓ scorri"})})]})}const l={source:"https://www.dnd5eapi.co (D&D 5e SRD 2014)",license:"CC-BY-4.0",generated_at:"2026-10-31"},u=[{index:"grappler",name:{en:"Grappler",it:"Lottatore"},desc:{en:`You’ve developed the Skills necessary to hold your own in close--quarters Grappling. You gain the following benefits:

- You have advantage on Attack Rolls against a creature you are Grappling.

- You can use your action to try to pin a creature Grappled by you. To do so, make another grapple check. If you succeed, you and the creature are both Restrained until the grapple ends.`,it:`Hai sviluppato le abilità necessarie per cavartela nella lotta corpo a corpo ravvicinata. Ottieni i seguenti benefici:

- Hai vantaggio ai tiri per colpire contro una creatura che stai afferrando.

- Puoi usare la tua azione per tentare di immobilizzare una creatura afferrata da te. Per farlo, effettua un'altra prova di lotta. Se hai successo, tu e la creatura siete entrambi trattenuti finché la presa non termina.`},prerequisites:[{ability:"str",minimum:13}]}],h={_meta:l,items:u},S=Object.freeze(Object.defineProperty({__proto__:null,_meta:l,default:h,items:u},Symbol.toStringTag,{value:"Module"}));export{x as S,v as T,S as f,y as u};
