import{c as r}from"./format-Dy9ltPj6.js";import{u as i,a as u,b as m,h as s,c as d,d as l}from"./index-C17HiLRh.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const p=[["circle",{cx:"12",cy:"12",r:"10",key:"1mglay"}],["path",{d:"M12 6v6l4 2",key:"mmk7yg"}]],y=r("clock",p);function h(c){const{t}=i(),a=u(),n=l();return m({mutationFn:()=>d.characters.tickRound(c),onSuccess:e=>{a.setQueryData(["character",c],e);const o=e.expired_effects??[];o.length>0&&n.info(t("character.conditions.duration.expired",{names:o.join(", ")})),s.success()},onError:()=>s.error()})}export{y as C,h as u};
