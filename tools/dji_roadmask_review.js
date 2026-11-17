const $ = id => document.getElementById(id);
const canvas = $('canvas'), ctx = canvas.getContext('2d');
const tint = document.createElement('canvas'), tintCtx = tint.getContext('2d');
let items = [], selected = null, image = null, maskImage = null, detections = [];
let issues = [], drag = null, dirty = false, saving = false, hasReview = false, loadToken = 0;
const nameKey = 'roadguard_roadmask_preliminary_checker';

function notify(message, error=false) { $('notice').textContent=message; $('notice').className=error?'warn':'good'; }
function saveState() {
  $('save-state').textContent = !selected ? 'Chọn ảnh để bắt đầu' : saving ? 'Đang lưu…' :
    dirty || !hasReview ? 'Chưa lưu / chưa kiểm tra' : 'Đã lưu kiểm tra sơ bộ';
  $('save').disabled = !selected || saving;
}
function changed() { dirty=true;saveState(); }
function rememberedName() { try{return localStorage.getItem(nameKey)||'';}catch{return '';} }
function rememberName(value) { try{localStorage.setItem(nameKey,value);}catch{/* Storage can be disabled. */} }
function point(event) {
  const rect=canvas.getBoundingClientRect(), scale=Number($('zoom').value)/100;
  return {x:Math.max(0,Math.min(image.naturalWidth,(event.clientX-rect.left)/scale)),
          y:Math.max(0,Math.min(image.naturalHeight,(event.clientY-rect.top)/scale))};
}
function draw() {
  if(!selected || !image?.complete || !image.naturalWidth)return;
  const scale=Number($('zoom').value)/100;
  canvas.width=Math.round(image.naturalWidth*scale);canvas.height=Math.round(image.naturalHeight*scale);
  ctx.drawImage(image,0,0,canvas.width,canvas.height);
  if($('show-mask').checked && maskImage?.complete && maskImage.naturalWidth) {
    ctx.globalAlpha=Number($('opacity').value)/100;
    ctx.drawImage(tint,0,0,canvas.width,canvas.height);ctx.globalAlpha=1;
  }
  if($('show-detections').checked) {
    ctx.lineWidth=2;ctx.font='bold 13px sans-serif';
    for(const det of detections) {
      const [x1,y1,x2,y2]=det.box;
      ctx.strokeStyle=det.class_name==='crack'?'#f9d61c':'#f95757';
      ctx.strokeRect(x1*scale,y1*scale,(x2-x1)*scale,(y2-y1)*scale);
      ctx.fillStyle=ctx.strokeStyle;ctx.fillText(`${det.id} ${det.class_name} ${det.confidence}`,
        x1*scale+3,Math.max(14,y1*scale-4));
    }
  }
  ctx.lineWidth=3;ctx.strokeStyle='#ff781f';
  for(const issue of issues) {
    const [x1,y1,x2,y2]=issue.box;
    ctx.strokeRect(x1*scale,y1*scale,(x2-x1)*scale,(y2-y1)*scale);
  }
  if(drag) {
    ctx.strokeStyle='#ffffff';ctx.strokeRect(drag.x*scale,drag.y*scale,
      (drag.toX-drag.x)*scale,(drag.toY-drag.y)*scale);
  }
  $('zoom-value').textContent=$('zoom').value+'%';
  $('opacity-value').textContent=$('opacity').value+'%';
}
function renderIssues() {
  const host=$('issues');host.replaceChildren();
  if(!issues.length){host.textContent='Chưa đánh dấu vùng sai.';return;}
  for(const [index,issue] of issues.entries()) {
    const row=document.createElement('div');row.className='issue';
    const text=document.createElement('span');text.textContent=`${issue.kind} · [${issue.box.join(', ')}]`;
    const remove=document.createElement('button');remove.type='button';remove.textContent='Xóa';
    remove.onclick=()=>{issues.splice(index,1);changed();renderIssues();draw();};
    row.append(text,remove);host.append(row);
  }
}
function buildTint() {
  if(!maskImage?.naturalWidth)return;
  tint.width=maskImage.naturalWidth;tint.height=maskImage.naturalHeight;
  tintCtx.clearRect(0,0,tint.width,tint.height);tintCtx.drawImage(maskImage,0,0);
  const pixels=tintCtx.getImageData(0,0,tint.width,tint.height);
  for(let i=0;i<pixels.data.length;i+=4){
    const active=pixels.data[i];
    pixels.data[i]=7;pixels.data[i+1]=138;pixels.data[i+2]=229;pixels.data[i+3]=active;
  }
  tintCtx.putImageData(pixels,0,0);
}
function renderList() {
  const host=$('items');host.replaceChildren();
  for(const group of ['provisional_keep','uncertain','provisional_reject']) {
    const heading=document.createElement('h2');heading.textContent={provisional_keep:'Ưu tiên xem tiếp',
      uncertain:'Ảnh chưa chắc',provisional_reject:'Ảnh xiên — phân tích riêng'}[group];host.append(heading);
    for(const item of items.filter(row=>row.triage===group)) {
      const button=document.createElement('button');button.type='button';
      button.className='item'+(selected?.image===item.image?' active':'');
      button.textContent=`${item.image} · ${item.prediction_status==='prediction_missing'?'mask thiếu':item.preliminary_review}`;
      button.onclick=()=>select(item.image).catch(error=>notify('Không mở được ảnh: '+error.message,true));
      host.append(button);
    }
  }
}
async function select(name) {
  if(saving || selected?.image===name)return;
  if(dirty && !confirm('Kiểm tra chưa lưu. Chuyển ảnh sẽ bỏ thay đổi này. Tiếp tục?'))return;
  const token=++loadToken;
  const response=await fetch('/api/roadmask/record/'+encodeURIComponent(name));
  const data=await response.json();if(!response.ok)throw new Error(data.error||'Không tải được bản ghi');
  if(token!==loadToken)return;
  selected=data.frame;detections=data.detections;issues=(data.review?.issues||[]).map(issue=>({...issue,box:[...issue.box]}));
  hasReview=Boolean(data.review);dirty=false;
  $('current').textContent=name;
  $('provenance').textContent=`${selected.source_video} · frame ${selected.frame_index_zero_based} · t≈${(selected.timestamp_ms_from_fps_nominal/1000).toFixed(3)}s (danh nghĩa, chưa xác thực PTS) · ${selected.triage} · quality: ${selected.quality_decision_at_prepare} · route: chưa xác minh`;
  $('mask-status').textContent=selected.predicted_mask?'Mask dự đoán: có, chưa được kỹ sư duyệt':'Không có mask dự đoán — cần kiểm tra, không dùng fallback';
  $('mask-status').className=selected.predicted_mask?'small':'warn';
  $('check').value=data.review?.preliminary_check||'uncertain';
  $('checked-by').value=rememberedName()||data.review?.checked_by||'';
  $('minutes').value=data.review?.minutes_actual??'';$('notes').value=data.review?.notes||'';
  $('summary').textContent=`Detector gốc: ${detections.length} box (lưu từ một lần chạy). Kiểm tra sơ bộ: ${data.review?.preliminary_check||'chưa thực hiện'}. Kỹ sư: chưa duyệt.`;
  image=new Image();image.onload=()=>{if(token===loadToken)draw();};image.src='/images/'+encodeURIComponent(name);
  maskImage=null;tint.width=0;tint.height=0;
  if(selected.predicted_mask) {
    const predicted=new Image();predicted.onload=()=>{if(token===loadToken){maskImage=predicted;buildTint();draw();}};
    predicted.onerror=()=>{if(token===loadToken){$('mask-status').textContent='Không tải được PNG mask — cần kiểm tra';maskImage=null;draw();}};
    predicted.src='/api/roadmask/predicted/'+encodeURIComponent(name);
  }
  renderIssues();renderList();saveState();notify('Chọn kết quả kiểm tra, đánh dấu vùng sai nếu cần, rồi lưu. Không tự duyệt kỹ sư.');
}
canvas.addEventListener('pointerdown',event=>{
  if(!selected||!image?.naturalWidth)return;
  const p=point(event);drag={...p,toX:p.x,toY:p.y};canvas.setPointerCapture(event.pointerId);draw();
});
canvas.addEventListener('pointermove',event=>{if(!drag)return;const p=point(event);drag.toX=p.x;drag.toY=p.y;draw();});
canvas.addEventListener('pointerup',event=>{
  if(!drag)return;const p=point(event);
  const box=[Math.floor(Math.min(drag.x,p.x)),Math.floor(Math.min(drag.y,p.y)),
             Math.ceil(Math.max(drag.x,p.x)),Math.ceil(Math.max(drag.y,p.y))];
  if(box[2]-box[0]>2 && box[3]-box[1]>2){issues.push({kind:$('issue-kind').value,box});changed();}
  drag=null;renderIssues();draw();
});
$('remove-last').onclick=()=>{if(issues.length){issues.pop();changed();renderIssues();draw();}};
for(const id of ['show-mask','show-detections','opacity','zoom'])$(id).addEventListener('input',draw);
for(const id of ['check','checked-by','minutes','notes'])$(id).addEventListener('change',changed);
$('save').onclick=async()=>{
  if(!selected||saving)return;
  const name=$('checked-by').value.trim();if(!name)return notify('Nhập tên người kiểm tra sơ bộ.',true);
  const minutes=$('minutes').value.trim();
  const payload={checked_by:name,preliminary_check:$('check').value,notes:$('notes').value,
    issues,minutes_actual:minutes===''?null:Number(minutes)};
  if(payload.preliminary_check==='looks_correct' && issues.length)
    return notify('Đã đánh dấu vùng sai; chọn “Có vùng sai / cần sửa” hoặc xóa vùng đánh dấu.',true);
  saving=true;saveState();
  try {
    const response=await fetch('/api/roadmask/review/'+encodeURIComponent(selected.image),
      {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Máy chủ từ chối lưu');
    if(result.review_status!=='pending_review')throw new Error('Trạng thái phản hồi không mong đợi');
    rememberName(name);dirty=false;hasReview=true;
    const item=items.find(row=>row.image===selected.image);if(item)item.preliminary_review=result.preliminary_check;
    $('summary').textContent=`Detector gốc: ${detections.length} box. Kiểm tra sơ bộ: ${result.preliminary_check}. Kỹ sư: chưa duyệt.`;
    notify('Đã lưu revision '+result.saved+' · Chờ duyệt chuyên môn');renderList();
  }catch(error){dirty=true;notify('Chưa xác nhận lưu được: '+error.message+'; vùng đánh dấu vẫn còn.',true);}
  finally{saving=false;saveState();}
};
window.addEventListener('beforeunload',event=>{if(dirty||saving){event.preventDefault();event.returnValue='';}});
async function start(){
  const response=await fetch('/api/roadmask/items');items=await response.json();
  if(!response.ok||items.length!==20)throw new Error('Chưa có run 20 ảnh; hãy chuẩn bị pilot trước.');
  renderList();saveState();
}
start().catch(error=>notify(error.message,true));
