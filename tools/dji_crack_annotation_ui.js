const $ = id => document.getElementById(id);
const canvas = $('canvas'), ctx = canvas.getContext('2d');
let items = [], selected = null, image = new Image(), boxes = [], drag = null;
let naturalWidth = 1920, naturalHeight = 1080;
const order = ['provisional_keep','uncertain','provisional_reject'];
const groupNames = {provisional_keep:'6 ảnh xem tiếp',uncertain:'7 ảnh chưa chắc chắn',provisional_reject:'7 ảnh xiên — giữ riêng'};

function notice(message, error=false) { $('notice').textContent = message; $('notice').className = error ? 'danger' : 'good'; }
function draw() {
  if (!selected || !image.complete) return;
  const zoom = Number($('zoom').value)/100;
  canvas.width = naturalWidth*zoom; canvas.height = naturalHeight*zoom;
  ctx.drawImage(image,0,0,canvas.width,canvas.height);
  ctx.lineWidth = 3; ctx.strokeStyle = '#ffcf00';
  for (const box of boxes) ctx.strokeRect(box[0]*zoom,box[1]*zoom,(box[2]-box[0])*zoom,(box[3]-box[1])*zoom);
  if (drag) { ctx.strokeStyle='#00f0ff'; ctx.strokeRect(drag.x*zoom,drag.y*zoom,(drag.toX-drag.x)*zoom,(drag.toY-drag.y)*zoom); }
  $('zoom-value').textContent = $('zoom').value+'%';
  $('boxes').textContent = boxes.length ? `${boxes.length} box crack nháp: ${boxes.map(b=>'['+b.map(Math.round).join(', ')+']').join(' · ')}` : 'Chưa vẽ box. Không mặc định đây là ảnh âm tính.';
}
function point(event) {
  const rect=canvas.getBoundingClientRect(), zoom=Number($('zoom').value)/100;
  return {x:Math.max(0,Math.min(naturalWidth,(event.clientX-rect.left)/zoom)), y:Math.max(0,Math.min(naturalHeight,(event.clientY-rect.top)/zoom))};
}
canvas.addEventListener('pointerdown',e=>{if(!selected)return; const p=point(e); drag={...p,toX:p.x,toY:p.y};canvas.setPointerCapture(e.pointerId);draw();});
canvas.addEventListener('pointermove',e=>{if(!drag)return;const p=point(e);drag.toX=p.x;drag.toY=p.y;draw();});
canvas.addEventListener('pointerup',e=>{if(!drag)return;const p=point(e);const b=[Math.min(drag.x,p.x),Math.min(drag.y,p.y),Math.max(drag.x,p.x),Math.max(drag.y,p.y)];if(b[2]-b[0]>2&&b[3]-b[1]>2)boxes.push(b.map(v=>Math.round(v*100)/100));drag=null;draw();});
$('zoom').addEventListener('input',draw);
$('undo').onclick=()=>{boxes.pop();draw();};
$('clear').onclick=()=>{if(confirm('Xóa các box chưa lưu trên ảnh này?')){boxes=[];draw();}};

async function refreshItems() {
  const response=await fetch('/api/items'); items=await response.json();
  const host=$('items'); host.replaceChildren();
  for (const group of order) {
    const heading=document.createElement('div');heading.className='group';heading.textContent=groupNames[group];host.append(heading);
    for (const item of items.filter(i=>i.triage.visual_triage===group)) {
      const button=document.createElement('button');button.type='button';button.className='item'+(selected?.id===item.id?' active':'');
      button.textContent=`${item.id} · ${item.status}`;button.onclick=()=>select(item.id);host.append(button);
    }
  }
}
async function select(id) {
  selected=items.find(i=>i.id===id); if(!selected)return;
  const response=await fetch('/api/annotation/'+encodeURIComponent(id));const saved=await response.json();
  boxes=Array.isArray(saved.boxes_xyxy_px)?saved.boxes_xyxy_px:[];
  $('quality').value=saved.quality_decision||'uncertain';$('status').value=saved.status||'draft';
  $('annotator').value=saved.annotator||'';$('reviewer').value='';$('notes').value=saved.notes||'';
  $('minutes').value=saved.annotation_minutes_actual??'';$('negative').checked=saved.negative_reviewed||false;$('confirm').checked=false;
  $('current').textContent=id;
  $('provenance').textContent=`${selected.source_video} · frame ${selected.frame_index} · t≈${(selected.timestamp_ms/1000).toFixed(3)}s · triage: ${selected.triage.visual_triage}. ${selected.triage.review_note}`;
  image=new Image();image.onload=()=>{naturalWidth=image.naturalWidth;naturalHeight=image.naturalHeight;draw();};image.src='/images/'+encodeURIComponent(id);
  notice('Bản sàng lọc chỉ là gợi ý. Người duyệt phải xác nhận crack-vs-khe và góc bay.');
  await refreshItems();
}
$('save').onclick=async()=>{
  if(!selected)return notice('Hãy chọn ảnh trước.',true);
  const minutes=$('minutes').value.trim();
  const payload={quality_decision:$('quality').value,status:$('status').value,annotator:$('annotator').value,reviewer:$('reviewer').value,
    notes:$('notes').value,boxes,negative_reviewed:$('negative').checked,explicit_review_confirmation:$('confirm').checked,
    annotation_minutes_actual:minutes===''?null:Number(minutes)};
  if(payload.status==='approved'&&!confirm('Xác nhận bạn là kỹ sư được chỉ định và đã duyệt ảnh/nhãn này?'))return;
  try {const response=await fetch('/api/annotation/'+encodeURIComponent(selected.id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Không lưu được');
    notice(`Đã lưu ${result.saved} · ${result.status}`);await refreshItems();
  } catch(error){notice(error.message,true);}
};
refreshItems().catch(error=>notice('Không tải được batch: '+error.message,true));
