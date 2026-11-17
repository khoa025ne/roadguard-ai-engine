const $ = id => document.getElementById(id);
const canvas = $('canvas'), ctx = canvas.getContext('2d');
let items = [], taxonomy = {}, selected = null, image = new Image();
let boxes = [], drag = null, editingId = null, naturalWidth = 1920, naturalHeight = 1080;
let boxDirty = false, advancedDirty = false, saveInFlight = false, editCounter = 0, hasSavedRevision = false;
const annotatorKey = 'roadguard_dji_pilot_annotator';
const order = ['provisional_keep', 'uncertain', 'provisional_reject'];
const groupNames = {provisional_keep:'6 ảnh xem tiếp', uncertain:'7 ảnh chưa chắc chắn', provisional_reject:'7 ảnh xiên — giữ riêng'};

function notice(message, error=false) { $('notice').textContent = message; $('notice').className = error ? 'danger' : 'good'; }
function saveState() {
  $('save-state').textContent = !selected ? 'Chọn ảnh để bắt đầu' : saveInFlight ? 'Đang lưu…' :
    boxDirty || advancedDirty || !hasSavedRevision ? 'Chưa lưu' : 'Đã lưu';
  $('save').disabled = saveInFlight || !selected;
  $('save-review').disabled = saveInFlight || !selected;
}
function changed(advanced=false) {
  if (advanced) advancedDirty=true; else boxDirty=true;
  editCounter++;saveState();
}
function rememberedAnnotator() {
  try { return localStorage.getItem(annotatorKey) || ''; } catch { return ''; }
}
function rememberAnnotator(name) {
  try { localStorage.setItem(annotatorKey,name); } catch { /* Browser storage may be disabled. */ }
}
function getAnnotator() {
  const remembered=rememberedAnnotator();
  if (remembered) return remembered;
  const name=prompt('Tên người gán nhãn (chỉ hỏi lần đầu trên trình duyệt này):', $('annotator').value || '');
  if (name===null) return null;
  const trimmed=name.trim();
  if (!trimmed) {notice('Vui lòng nhập tên người gán nhãn trước khi lưu.',true);return null;}
  rememberAnnotator(trimmed);$('annotator').value=trimmed;return trimmed;
}
function colorFor(box) {
  if (box.label === 'crack') return '#ffd000';
  if (box.label === 'needs_review' || box.review_status === 'needs_review') return '#ff5fa2';
  return '#23d7ee';
}
function draw() {
  if (!selected || !image.complete || !image.naturalWidth) return;
  const zoom = Number($('zoom').value) / 100;
  canvas.width = Math.round(naturalWidth * zoom); canvas.height = Math.round(naturalHeight * zoom);
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
  for (const box of boxes) {
    const [x1,y1,x2,y2] = box.xyxy_px;
    ctx.strokeStyle = colorFor(box); ctx.lineWidth = 3;
    ctx.strokeRect(x1*zoom,y1*zoom,(x2-x1)*zoom,(y2-y1)*zoom);
    ctx.fillStyle = colorFor(box); ctx.font = 'bold 14px sans-serif';
    ctx.fillText(taxonomy[box.label] || box.label, x1*zoom+3, Math.max(16,y1*zoom-4));
  }
  if (drag) {
    ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2;
    ctx.strokeRect(drag.x*zoom,drag.y*zoom,(drag.toX-drag.x)*zoom,(drag.toY-drag.y)*zoom);
  }
  $('zoom-value').textContent = $('zoom').value + '%';
}
function point(event) {
  const rect=canvas.getBoundingClientRect(), zoom=Number($('zoom').value)/100;
  return {x:Math.max(0,Math.min(naturalWidth,(event.clientX-rect.left)/zoom)),
          y:Math.max(0,Math.min(naturalHeight,(event.clientY-rect.top)/zoom))};
}
function isLocked(box) { return box.label === 'crack' && box.review_status === 'approved'; }
function markPending() { if($('status').value==='approved') $('status').value='pending_review'; changed(); }
function renderBoxes() {
  const host=$('boxes'); host.replaceChildren();
  if (!boxes.length) { host.textContent='Chưa có box. Không mặc định ảnh này là âm tính.'; return; }
  for (const box of boxes) {
    const row=document.createElement('div');row.className='box-row';
    const label=document.createElement('select');label.setAttribute('aria-label','Loại box');
    for (const [code,name] of Object.entries(taxonomy)) {
      const option=document.createElement('option');option.value=code;option.textContent=name;label.append(option);
    }
    label.value=box.label;
    label.onchange=()=>{
      const old=box.label;box.label=label.value;
      if (box.label==='needs_review') box.review_status='needs_review';
      else if (old!==box.label) box.review_status=isLocked({label:old,review_status:box.review_status})?'needs_review':'draft';
      markPending();
      renderBoxes();draw();
    };
    const status=document.createElement('select');status.setAttribute('aria-label','Trạng thái box');
    for (const [value,text] of [['draft','Nháp'],['pending_review','Chờ duyệt'],['needs_review','needs_review'],['approved','Đã duyệt'],['rejected','Bỏ qua']]) {
      const option=document.createElement('option');option.value=value;option.textContent=text;
      if(value==='approved' && box.review_status!=='approved' && !$('advanced').open) option.disabled=true;
      status.append(option);
    }
    status.value=box.review_status;
    status.onchange=()=>{box.review_status=box.label==='needs_review'?'needs_review':status.value;markPending();renderBoxes();draw();};
    const edit=document.createElement('button');edit.type='button';edit.textContent='Sửa tọa độ';
    edit.disabled=isLocked(box);edit.onclick=()=>{editingId=box.id;notice('Kéo một box mới trên ảnh để thay tọa độ box đã chọn.');};
    const remove=document.createElement('button');remove.type='button';remove.textContent='Xóa';
    remove.disabled=isLocked(box);remove.onclick=()=>{boxes=boxes.filter(item=>item.id!==box.id);markPending();renderBoxes();draw();};
    const coords=document.createElement('div');coords.className='coords';
    coords.textContent=`${box.id} · [${box.xyxy_px.map(Math.round).join(', ')}] px`;
    row.append(label,status,edit,remove,coords);host.append(row);
  }
}
canvas.addEventListener('pointerdown',e=>{
  if (!selected)return;const p=point(e);drag={...p,toX:p.x,toY:p.y};canvas.setPointerCapture(e.pointerId);draw();
});
canvas.addEventListener('pointermove',e=>{if(!drag)return;const p=point(e);drag.toX=p.x;drag.toY=p.y;draw();});
canvas.addEventListener('pointerup',e=>{
  if(!drag)return;const p=point(e);
  const coords=[Math.min(drag.x,p.x),Math.min(drag.y,p.y),Math.max(drag.x,p.x),Math.max(drag.y,p.y)]
    .map(value=>Math.round(value*100)/100);
  if(coords[2]-coords[0]>2 && coords[3]-coords[1]>2) {
    if(editingId) {const box=boxes.find(item=>item.id===editingId);if(box&&!isLocked(box)){box.xyxy_px=coords;box.review_status='draft';markPending();}}
    else {const label=$('new-label').value;boxes.push({id:'box-'+crypto.randomUUID(),label,xyxy_px:coords,
      review_status:label==='needs_review'?'needs_review':$('new-box-status').value});markPending();}
  }
  drag=null;editingId=null;renderBoxes();draw();
});
$('zoom').addEventListener('input',draw);
$('new-label').addEventListener('change',()=>{if($('new-label').value==='needs_review')$('new-box-status').value='needs_review';});
$('undo').onclick=()=>{const index=boxes.findLastIndex(box=>!isLocked(box));if(index>=0){boxes.splice(index,1);markPending();}renderBoxes();draw();};

async function refreshItems() {
  const response=await fetch('/api/items');items=await response.json();
  const host=$('items');host.replaceChildren();
  for(const group of order) {
    const heading=document.createElement('div');heading.className='group';heading.textContent=groupNames[group];host.append(heading);
    for(const item of items.filter(row=>row.triage.visual_triage===group)) {
      const button=document.createElement('button');button.type='button';
      button.className='item'+(selected?.id===item.id?' active':'');
      button.textContent=`${item.id} · ${item.status}`;button.onclick=()=>select(item.id).catch(error=>notice('Không mở được ảnh: '+error.message,true));host.append(button);
    }
  }
}
async function refreshHistory() {
  if(!selected)return;
  const response=await fetch('/api/history/'+encodeURIComponent(selected.id));
  const revisions=await response.json();const host=$('history');host.replaceChildren();
  host.textContent=`Lịch sử: ${revisions.length} phiên bản. `;
  for(const revision of revisions) {
    const link=document.createElement('a');link.href='/api/revision/'+encodeURIComponent(selected.id)+'/'+encodeURIComponent(revision.revision);
    link.download=revision.revision;link.textContent=revision.revision+' · ';host.append(link);
  }
}
async function select(id) {
  if (selected?.id===id || saveInFlight) return;
  if ((boxDirty || advancedDirty) && !confirm('Có thay đổi chưa lưu. Chuyển ảnh sẽ bỏ những thay đổi này. Tiếp tục?')) return;
  const next=items.find(item=>item.id===id);if(!next)return;
  const response=await fetch('/api/annotation/'+encodeURIComponent(id));const saved=await response.json();
  if(!response.ok)throw new Error(saved.error||'Không tải được nhãn');
  selected=next;
  hasSavedRevision=Boolean(saved.status);
  boxes=Array.isArray(saved.boxes)?saved.boxes.map(box=>({...box,xyxy_px:[...box.xyxy_px]})):
    (saved.boxes_xyxy_px||[]).map((coords,index)=>({id:'legacy-'+(index+1),label:'crack',xyxy_px:[...coords],
      review_status:saved.status==='approved'?'approved':'draft'}));
  editingId=null;drag=null;
  $('quality').value=saved.quality_decision||'uncertain';$('status').value=saved.status||'draft';
  $('annotator').value=rememberedAnnotator()||saved.annotator||'';$('reviewer').value='';$('notes').value=saved.notes||'';
  $('minutes').value=saved.annotation_minutes_actual??'';$('negative').checked=saved.negative_reviewed||false;
  $('confirm').checked=false;$('reclass-confirmed').checked=false;
  $('current').textContent=id;
  $('review-state').textContent='Trạng thái duyệt: '+(saved.status||'chưa có nhãn');
  $('provenance').textContent=`${selected.source_video} · frame ${selected.frame_index} · t≈${(selected.timestamp_ms/1000).toFixed(3)}s · triage: ${selected.triage.visual_triage}. ${selected.triage.review_note}`;
  image=new Image();image.onload=()=>{naturalWidth=image.naturalWidth;naturalHeight=image.naturalHeight;draw();};
  image.src='/images/'+encodeURIComponent(id);
  boxDirty=false;advancedDirty=false;saveState();
  renderBoxes();await refreshHistory();await refreshItems();
  notice('Box crack đã duyệt được giữ tọa độ. Nhãn ngoại vi chỉ để loại trừ/kiểm tra.');
}
$('save').onclick=async()=>{
  if(!selected||saveInFlight)return notice('Hãy chọn ảnh hoặc đợi lượt lưu hiện tại.',true);
  const annotator=getAnnotator();if(annotator===null)return;
  const imageId=selected.id, version=editCounter;
  saveInFlight=true;saveState();
  try {
    const response=await fetch('/api/save-labels/'+encodeURIComponent(imageId),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({annotator,boxes})});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Máy chủ từ chối lưu');
    if(result.status!=='pending_review')throw new Error('Máy chủ trả về trạng thái lưu không mong đợi; kiểm tra lịch sử trước khi thử lại.');
    if(editCounter===version)boxDirty=false;
    hasSavedRevision=true;
    $('status').value='pending_review';
    $('review-state').textContent='Trạng thái duyệt: Chờ duyệt (pending_review)';
    notice(`Đã lưu ${result.saved} · Chờ duyệt`);
    try { await refreshHistory();await refreshItems(); }
    catch { notice(`Đã lưu ${result.saved}; chưa cập nhật được danh sách/lịch sử. Tải lại trang để kiểm tra.`,true); }
  } catch(error) {boxDirty=true;notice('Chưa xác nhận lưu được: '+error.message+' Giữ nguyên box để kiểm tra/thử lại.',true);}
  finally {saveInFlight=false;saveState();}
};
$('save-review').onclick=async()=>{
  if(!selected||saveInFlight)return notice('Hãy chọn ảnh hoặc đợi lượt lưu hiện tại.',true);
  const annotator=getAnnotator();if(annotator===null)return;
  const imageId=selected.id, version=editCounter;
  const minutes=$('minutes').value.trim();
  const payload={quality_decision:$('quality').value,status:$('status').value,annotator,
    reviewer:$('reviewer').value,notes:$('notes').value,boxes,negative_reviewed:$('negative').checked,
    explicit_review_confirmation:$('confirm').checked,allow_reclassify_confirmed:$('reclass-confirmed').checked,
    annotation_minutes_actual:minutes===''?null:Number(minutes)};
  if(payload.status==='approved'&&!confirm('Xác nhận bạn là kỹ sư được chỉ định và đã duyệt tất cả box trên ảnh?'))return;
  saveInFlight=true;saveState();
  try {
    const response=await fetch('/api/annotation/'+encodeURIComponent(imageId),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Không lưu được');
    if(editCounter===version){boxDirty=false;advancedDirty=false;}
    hasSavedRevision=true;
    $('review-state').textContent='Trạng thái duyệt: '+result.status;
    notice(`Đã lưu ${result.saved} · ${result.status}`);
    try {await refreshHistory();await refreshItems();}catch {notice(`Đã lưu ${result.saved}; chưa cập nhật được lịch sử.`,true);}
  } catch(error){notice('Chưa xác nhận lưu được: '+error.message+' Giữ nguyên box để kiểm tra/thử lại.',true);}
  finally {saveInFlight=false;saveState();}
};
for(const id of ['quality','status','annotator','reviewer','minutes','notes','negative','confirm','reclass-confirmed']) {
  $(id).addEventListener('change',()=>{
    if(id==='annotator' && $('annotator').value.trim()) rememberAnnotator($('annotator').value.trim());
    changed(true);
  });
}
$('advanced').addEventListener('toggle',renderBoxes);
window.addEventListener('beforeunload',event=>{
  if(boxDirty||advancedDirty||saveInFlight){event.preventDefault();event.returnValue='';}
});
async function start() {
  const response=await fetch('/api/taxonomy');taxonomy=await response.json();
  for(const [code,name] of Object.entries(taxonomy)) {
    const option=document.createElement('option');option.value=code;option.textContent=name;$('new-label').append(option);
  }
  await refreshItems();
}
start().catch(error=>notice('Không tải được batch: '+error.message,true));
saveState();
