// The timeline ruler under each app's header (Action Atlas, Move Explorer, Trends), with shared/ruler.css. A classic
// script loaded before the app's own: it defines placePlayhead, setKeys and stepKey for the app to call, and makes the
// key row scroll. The app fills the keys (button.kf with aria-pressed) and decides what selecting one does
// the playhead appears in place (no slide) on load, after a resize and after being hidden; the key row scrolls to keep it in view
let phStill=true;
function placePlayhead(){
  const ph=document.getElementById('playhead'),k=document.querySelector('#keys .kf[aria-pressed="true"]');
  if(!k){ph.hidden=true;phStill=true;return}
  const i=k.querySelector('i'),x=i.offsetLeft+i.offsetWidth/2,row=ph.parentNode;
  ph.classList.toggle('still',phStill);ph.hidden=false;phStill=false;
  ph.style.transform=`translateX(${x-1}px)`;
  if(row.scrollWidth>row.clientWidth&&(x<row.scrollLeft+40||x>row.scrollLeft+row.clientWidth-60))row.scrollTo({left:x-row.clientWidth/2,behavior:'smooth'})}
addEventListener('resize',()=>{phStill=true;placePlayhead()});
document.fonts?.ready.then(()=>{phStill=true;placePlayhead()});
// the key row scrolls sideways by dragging (a flick glides on) or by the wheel; pulled past either end it stretches with
// growing resistance and springs back. A vertical wheel moves the row only while it can, then scrolls the page
function elasticRow(row){
  const calm=matchMedia('(prefers-reduced-motion: reduce)'),max=()=>Math.max(0,row.scrollWidth-row.clientWidth);
  let p=0,v=0,glide=0,drag=null,dragged=false,wt;
  const show=()=>{const c=Math.min(max(),Math.max(0,p)),o=p-c;row.scrollLeft=c;row.style.transform=o?`translateX(${(-o*.5/(1+Math.abs(o)/160)).toFixed(1)}px)`:''};
  const settle=()=>{p=Math.min(max(),Math.max(0,p));if(!row.style.transform)return;row.classList.toggle('settle',!calm.matches);row.style.transform=''};
  const stop=()=>{cancelAnimationFrame(glide);glide=0;row.classList.remove('settle')};
  // past an end the glide brakes hard, so a flick into the end stretches the row briefly before it springs back
  const fly=()=>{v*=p<0||p>max()?.6:.95;p+=v;show();if(Math.abs(v)>.5)glide=requestAnimationFrame(fly);else{glide=0;settle()}};
  row.addEventListener('transitionend',e=>{if(e.target===row)row.classList.remove('settle')});
  row.addEventListener('pointerdown',e=>{if(e.button||e.pointerType==='touch')return;stop();p=row.scrollLeft;v=0;dragged=false;drag={id:e.pointerId,x:e.clientX,p,t:e.timeStamp}});
  row.addEventListener('pointermove',e=>{if(!drag||e.pointerId!==drag.id)return;const dx=e.clientX-drag.x;
    if(!dragged){if(Math.abs(dx)<4)return;dragged=true;row.setPointerCapture(e.pointerId);row.classList.add('dragging')}
    const np=drag.p-dx;v=(np-p)/Math.max(1,e.timeStamp-drag.t)*16;drag.t=e.timeStamp;p=np;show()});
  const end=e=>{if(!drag||e.pointerId!==drag.id)return;const still=e.timeStamp-drag.t>80;drag=null;row.classList.remove('dragging');if(!dragged)return;
    if(!calm.matches&&!still&&Math.abs(v)>1&&p>=0&&p<=max())glide=requestAnimationFrame(fly);else settle()};
  row.addEventListener('pointerup',end);row.addEventListener('pointercancel',end);
  // a drag that ends over a key doesn't select it
  row.addEventListener('click',e=>{if(dragged){dragged=false;e.stopPropagation();e.preventDefault()}},true);
  row.addEventListener('wheel',e=>{if(e.ctrlKey)return;
    const k=e.deltaMode===1?16:e.deltaMode===2?row.clientWidth:1,dx=e.deltaX*k,dy=e.deltaY*k,m=max();
    if(Math.abs(dx)<=Math.abs(dy)&&!e.shiftKey){
      if(!m||(dy<0?row.scrollLeft<=0:row.scrollLeft>=m-1))return;
      e.preventDefault();stop();row.scrollLeft+=dy;return}
    e.preventDefault();stop();if(!row.style.transform)p=row.scrollLeft;p+=Math.abs(dx)>Math.abs(dy)?dx:dy;show();
    clearTimeout(wt);wt=setTimeout(settle,120)},{passive:false})}
elasticRow(document.getElementById('keys').parentNode);
// redraws the keys; a redraw drops the focused key, so focus goes back to the ruler and Left/Right keep stepping it
function setKeys(html){
  const keys=document.getElementById('keys'),rf=keys.closest('.ruler').contains(document.activeElement);
  keys.innerHTML=html;placePlayhead();
  if(rf)keys.parentNode.focus({preventScroll:true})}
// with focus in the ruler (click a key first), Left/Right step through its keys like keyframes, stopping at the first
// and last; returns the key to select. A key that holds focus hands it to the key row, so its ring doesn't stay behind
function stepKey(e){
  if((e.key!=='ArrowLeft'&&e.key!=='ArrowRight')||e.ctrlKey||e.shiftKey||e.altKey||e.metaKey||e.defaultPrevented)return null;
  if(!e.target.closest?.('.ruler')||document.getElementById('sheet')?.hidden===false)return null;
  const ks=[...document.querySelectorAll('#keys .kf')];if(!ks.length)return null;
  const i=ks.findIndex(k=>k.getAttribute('aria-pressed')==='true'),d=e.key==='ArrowLeft'?-1:1;
  const n=i<0?(d>0?0:ks.length-1):Math.min(ks.length-1,Math.max(0,i+d));
  if(document.activeElement?.classList.contains('kf'))document.getElementById('keys').parentNode.focus({preventScroll:true});
  e.preventDefault();return n===i?null:ks[n]}
