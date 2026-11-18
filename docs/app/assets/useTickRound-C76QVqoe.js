import{c as r,u as i,a as u,b as d,h as t,d as l,e as k}from"./index-BrS5yqpt.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const m=[["circle",{cx:"12",cy:"12",r:"10",key:"1mglay"}],["path",{d:"M12 6v6l4 2",key:"mmk7yg"}]],y=r("clock",m);function f(c){const{t:o}=i(),a=u(),n=k();return d({mutationFn:()=>l.characters.tickRound(c),onSuccess:e=>{a.setQueryData(["character",c],e);const s=e.expired_effects??[];s.length>0&&n.info(o("character.conditions.duration.expired",{names:s.join(", ")})),t.success()},onError:()=>t.error()})}export{y as C,f as u};
