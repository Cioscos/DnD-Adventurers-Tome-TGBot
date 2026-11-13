import{c as r}from"./index-BI36UzP7.js";/**
 * @license lucide-react v1.11.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const m=[["path",{d:"M12 7v14",key:"1akyts"}],["path",{d:"M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z",key:"ruj8y"}]],w=r("book-open",m);async function g(o,i=4096){const e=await createImageBitmap(o),n=Math.min(1,i/Math.max(e.width,e.height));if(n===1&&o.size<=10*1024*1024)return e.close(),o;const a=document.createElement("canvas");a.width=Math.round(e.width*n),a.height=Math.round(e.height*n),a.getContext("2d").drawImage(e,0,0,a.width,a.height),e.close();const c=p=>new Promise(s=>a.toBlob(s,p,.9));let t=await c("image/webp");if((!t||t.type!=="image/webp")&&(t=await c("image/jpeg")),!t)return o;const h=t.type==="image/webp"?"webp":"jpg";return new File([t],o.name.replace(/\.[^.]+$/,"")+"."+h,{type:t.type})}export{w as B,g as d};
