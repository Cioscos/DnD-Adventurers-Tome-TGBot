import{c as o}from"./index-DB8zdybw.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const e=[["path",{d:"M20 6 9 17l-5-5",key:"1gmf2c"}]],i=o("check",e);function r(a){const t=a==null?void 0:a.turn;if(!t)return{attacksLeft:0,actionUnused:!1};const c=t.action_attacks>0?Math.max(0,(a.attacks_allowed??1)-t.action_attacks):0,n=!t.action_used&&t.action_attacks===0||(t.extra_actions??0)>0;return{attacksLeft:c,actionUnused:n}}export{i as C,r as t};
