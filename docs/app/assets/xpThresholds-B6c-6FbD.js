import{c as s}from"./index-CcQcKx6d.js";/**
 * @license lucide-react v1.8.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const i=[["path",{d:"m17 11-5-5-5 5",key:"e8nh98"}],["path",{d:"m17 18-5-5-5 5",key:"2avn1x"}]],u=s("chevrons-up",i),c=[0,300,900,2700,6500,14e3,23e3,34e3,48e3,64e3,85e3,1e5,12e4,14e4,165e3,195e3,225e3,265e3,305e3,355e3];function h(n){let t=1;for(let e=1;e<c.length&&n>=c[e];e++)t=e+1;return Math.min(t,20)}function m(n){if(n<=0)return[];const t=[.02,.07,.2,.5],e=5,r=t.map(o=>Math.max(e,Math.round(o*n/10)*10));return r.filter((o,a)=>a===0||o!==r[a-1])}export{u as C,c as X,h as l,m as q};
