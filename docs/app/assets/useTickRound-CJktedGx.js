import{c as r,a as i,b as u,d,h as t,e as l,f}from"./index-D8YmEVi1.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const k=[["circle",{cx:"12",cy:"12",r:"10",key:"1mglay"}],["path",{d:"M12 6v6l4 2",key:"mmk7yg"}]],p=r("clock",k);function y(c){const{t:o}=i(),a=u(),n=f();return d({mutationFn:()=>l.characters.tickRound(c),onSuccess:e=>{a.setQueryData(["character",c],e);const s=e.expired_effects??[];s.length>0&&n.info(o("character.conditions.duration.expired",{names:s.join(", ")})),t.success()},onError:()=>t.error()})}export{p as C,y as u};
