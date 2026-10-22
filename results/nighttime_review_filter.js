/* Explicit counterpart of notebooks/nighttime_review_filter.py. No CSS filters. */
(function(root) {
 'use strict';
 const order=['gamma','exposure','brightness','shadows','sharpness'];
 const conditions=['weekday','weekend'].flatMap(d=>['pagi','siang','sore','malam'].map(p=>d+'_'+p));
 const raw={gamma:1,exposure:0,sharpness:0,brightness:0,shadows:0};
 const ranges={gamma:[.2,3],exposure:[-3,3],sharpness:[0,2],brightness:[-100,100],shadows:[-100,100]};
 function validate(s) {
  if(!s || Object.keys(s).sort().join()!==Object.keys(raw).sort().join())throw Error('Lima parameter wajib lengkap');
  for(const [key,[lo,hi]] of Object.entries(ranges))if(typeof s[key]!=='number'||!Number.isFinite(s[key])||s[key]<lo||s[key]>hi)throw Error('Nilai tidak valid: '+key);
  return {...s};
 }
 function apply(rgb,width,height,settings) {
  const s=validate(settings);
  if(!Number.isInteger(width)||!Number.isInteger(height)||width<1||height<1||rgb.length!==width*height*3)throw Error('Dimensi RGB tidak valid');
  const q=x=>Math.floor(Math.max(0,Math.min(255,x))+.5);
  let out=Uint8Array.from(rgb);
  const stages=[s.gamma!==1?x=>255*Math.pow(x/255,s.gamma):null,s.exposure?x=>x*Math.pow(2,s.exposure):null,
   s.brightness?x=>x+s.brightness:null,s.shadows?x=>x+.64*s.shadows*Math.pow(1-x/255,2):null];
  for(const fn of stages)if(fn)out=out.map(x=>q(fn(x)));
  if(s.sharpness) {
   const prior=out;out=new Uint8Array(prior.length);const weights=[1,2,1];
   for(let y=0;y<height;y++)for(let x=0;x<width;x++)for(let c=0;c<3;c++) {
    let smooth=0;
    for(let j=-1;j<=1;j++)for(let i=-1;i<=1;i++) {
     const xx=Math.max(0,Math.min(width-1,x+i)),yy=Math.max(0,Math.min(height-1,y+j));
     smooth+=prior[(yy*width+xx)*3+c]*weights[j+1]*weights[i+1]/16;
    }
    const k=(y*width+x)*3+c;out[k]=q(prior[k]+s.sharpness*(prior[k]-smooth));
   }
  }
  return out;
 }
 const api={schema:'night_review_filter_v1',order,conditions,raw,ranges,validate,apply};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.NightFilter=api;
})(typeof globalThis!=='undefined'?globalThis:this);
