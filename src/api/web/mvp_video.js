'use strict';
const el = id => document.getElementById(id);
const base = '/api/mvp-video';
let reviews = {};
let config, job, result, timer, uploadRequest, fileUrl, connected = false, busy = false, uploadKey, preparedJob;
let logEvents = [], sequence = 0, clearedAt = 0, polling = false;
const terminal = new Set(['COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED', 'READY']);
const statusLabels = {UPLOADING:'Đang lưu video',QUEUED:'Đang chờ lượt',RUNNING:'Đang xử lý local',COMPLETED:'Đã lưu kết quả local',FAILED:'Xử lý thất bại',CANCELLED:'Đã hủy',INTERRUPTED:'Phiên bị gián đoạn'};
function node(tag, text, cls) { const n = document.createElement(tag); if(text !== undefined) n.textContent = text; if(cls) n.className=cls; return n; }
function remember(id) { try { localStorage.setItem('roadguard-local-job', id); } catch {} }
function remembered() { try { return localStorage.getItem('roadguard-local-job'); } catch { return null; } }
async function api(path, options={}) {
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),30000);
  try {
    const response=await fetch(base+path,{...options,signal:controller.signal});
    let data; try { data=await response.json(); } catch { throw {code:'INVALID_RESPONSE',stage:'connection',message:'Máy chủ trả dữ liệu không hợp lệ.',action:'Kiểm tra dịch vụ local và thử lại.'}; }
    if(!response.ok) { const detail=data.detail; throw typeof detail==='object'&&!Array.isArray(detail)?detail:{code:'HTTP_ERROR',stage:'connection',message:typeof detail==='string'?detail:'Yêu cầu không thành công.',action:`Máy chủ trả HTTP ${response.status}. Kiểm tra nhật ký.`}; }
    return data;
  } catch(error) {
    if(error.code) throw error;
    throw {code:error.name==='AbortError'?'REQUEST_TIMEOUT':'SERVICE_UNREACHABLE',stage:'connection',
      message:error.name==='AbortError'?'Dịch vụ chưa phản hồi trong 30 giây.':'Không thể kết nối dịch vụ phân tích local.',
      action:'Kiểm tra dịch vụ trên localhost và thử lại. Chưa có bằng chứng xác định lỗi CORS.'};
  } finally {clearTimeout(timeout);}
}
function failure(error,stage) {
  const data={timestamp:new Date().toISOString(),stage:error.stage||stage||'configuration',severity:'ERROR',code:error.code||'CLIENT_ERROR',message:error.message||'Yêu cầu thất bại.',details:{action:error.action||'Kiểm tra nhật ký và thử lại.'}};
  el('error').hidden=false;el('error').textContent=`${data.message}\nCông đoạn: ${data.stage} · Mã: ${data.code}\n${data.details.action}`;
  logEvents.push({...data,client:true});renderLogs();
}
function controls() {
  const selected=Boolean(el('crack').value&&el('pothole').value&&(!el('roadMaskEnabled').checked||el('segment').value));
  const valid=Boolean(el('video').files[0]&&/\.(mp4|mov|avi|mkv)$/i.test(el('video').files[0].name));
  el('prepare').disabled=!connected||!config?.ready||!selected||!valid||busy;
  el('start').disabled=!connected||!config?.ready||!selected||!preparedJob||busy;
  el('disabledReason').textContent=!connected?'Chưa kết nối dịch vụ. Kiểm tra lại kết nối.':!selected?'Thiếu model khả dụng. Không tự chuyển sang baseline.':busy?'Phiên đang xử lý; các phần khác vẫn dùng được.':preparedJob?'Video đã xác minh; kiểm tra số frame rồi bắt đầu.':!valid?'Chọn video để kiểm tra.':'Lưu video & kiểm tra số frame trên máy chủ trước khi bắt đầu.';
}
function selectedDescription(task,id) {
  const model=config.models.find(m=>m.id===id);
  return model?`${model.name} · ${model.version} · ${Object.values(model.classes).join(', ')}${model.baseline?' · Baseline chọn thủ công':''}`:`Model ${task} mặc định chưa khả dụng.`;
}
function modelSelect(id,task,retain) {
  const select=el(id);const previous=retain?select.value:null;
  const available=config.models.filter(m=>(m.task===task||m.task==='ROAD_DAMAGE')&&m.status==='available');
  select.replaceChildren(new Option('Chọn model đã xác minh…',''),...available.map(m=>new Option(m.name+(m.baseline?' · Baseline':''),m.id)));
  select.value=retain&&previous?(available.some(m=>m.id===previous)?previous:''):config.defaults[task]||'';
  select.disabled=!available.length;el(id+'Status').textContent=selectedDescription(task,select.value);
  select.onchange=()=>{el(id+'Status').textContent=selectedDescription(task,select.value);uploadKey=null;preparedJob=null;controls();};
}
function segmentSelect(retain) {
  const select=el('segment'),previous=retain?select.value:null;
  const available=(config.segment_models||[]).filter(m=>m.task==='SEGMENT'&&m.status==='available');
  select.replaceChildren(new Option('Chọn Road Seg đã xác minh…',''),...available.map(m=>new Option(m.name,m.id)));
  select.value=previous&&available.some(m=>m.id===previous)?previous:config.segment_default||'';
  select.disabled=!available.length;
  el('segmentStatus').textContent=available.length?'SEGMENT · road · mask AI chưa được duyệt; không lọc mất detection.':'Road Seg chưa khả dụng; vẫn có thể xử lý khi tắt Road Mask.';
  select.onchange=()=>{uploadKey=null;preparedJob=null;controls();};
}
async function loadConfig(refresh=false) {
  el('retryConfig').disabled=true;el('refreshModels').disabled=true;
  el('config').textContent=refresh?'Đang kiểm tra lại checkpoint…':'Đang kết nối cấu hình local…';
  try {
    if(refresh) await api('/models?refresh=true');
    const firstLoad=!config;config=await api('/config');connected=true;el('error').hidden=true;
    if(firstLoad)el('fps').value=String(config.limits.fps);
    el('config').textContent=`${config.message}. Không giới hạn dung lượng hoặc thời lượng theo cấu hình public; máy chủ kiểm tra ổ đĩa trước inference. FPS: 1 / 2 / 5 / 10 / native.`;
    modelSelect('crack','CRACK',refresh||Boolean(el('crack').options.length));modelSelect('pothole','POTHOLE',refresh||Boolean(el('pothole').options.length));
    segmentSelect(refresh||Boolean(el('segment').options.length));
    el('modelList').replaceChildren(...config.models.map(m=>node('p',`${m.name} · ${m.task||'Task chưa xác minh'} · ${m.status==='available'?'Khả dụng':'Không khả dụng'} · ${m.version||'Chưa có phiên bản'}${m.code?' · '+m.code:''}`)));
    el('report').disabled=!job||!result||!config.report_enabled;
    el('reportHint').textContent=config.report_enabled?'Báo cáo thống kê local không cần API. LLM chỉ nhận thống kê khi bạn yêu cầu.':'Báo cáo thống kê local không cần API. Provider Qwen/DeepSeek chưa được bật hoặc chưa xác minh cấu hình; YOLO vẫn hoạt động.';
  } catch(error) {connected=false;el('config').textContent='Không đọc được cấu hình dịch vụ local.';failure(error,'configuration');}
  finally {el('retryConfig').disabled=false;el('refreshModels').disabled=false;controls();}
}
function estimate() {
  const video=el('sourcePreview');el('nativeWarning').hidden=el('fps').value!=='native';
  el('estimate').textContent=Number.isFinite(video.duration)&&video.duration>0?(el('fps').value==='native'?`Thời lượng ${video.duration.toFixed(2)} giây. Native: máy chủ sẽ xác định số frame từ metadata trước inference.`:`Ước tính ${Math.ceil(video.duration*Number(el('fps').value))} frame trong ${video.duration.toFixed(2)} giây; số thực do máy chủ xác nhận.`):'Chọn video để ước tính số frame.';
  uploadKey=null;preparedJob=null;controls();
}
function fileSelected() {
  const file=el('video').files[0];if(fileUrl)URL.revokeObjectURL(fileUrl);
  if(!file)return;preparedJob=null;el('fileInfo').textContent=`${file.name} · ${(file.size/1048576).toFixed(2)} MB`;
  if(!/\.(mp4|mov|avi|mkv)$/i.test(file.name)){failure({code:'UNSUPPORTED_FILE',message:'Định dạng không hỗ trợ. Chọn MP4, MOV, AVI hoặc MKV.'},'validation');controls();return;}
  fileUrl=URL.createObjectURL(file);el('sourcePreview').src=fileUrl;el('sourcePreview').hidden=false;uploadKey=null;controls();
}
function renderLogs() {
  const visible=logEvents.slice(Math.max(clearedAt,logEvents.length-500)).filter(e=>el('logFilter').value==='ALL'||e.severity===el('logFilter').value);
  el('issues').textContent=String(logEvents.filter(e=>['ERROR','WARNING'].includes(e.severity)).length);
  el('logs').replaceChildren(...visible.map(e=>{const n=node('div',undefined,'logEvent '+e.severity);n.append(node('small',`${new Date(e.timestamp).toLocaleTimeString('vi-VN')} · ${e.stage} · ${e.severity==='ERROR'?'Lỗi':e.severity==='WARNING'?'Cảnh báo':'Thông tin'}`),node('p',e.message));const d=node('details');d.append(node('summary','Chi tiết kỹ thuật'),node('pre',JSON.stringify({code:e.code,sequence:e.sequence,job_id:e.job_id,...e.details},null,2)));n.append(d);return n;}));
  if(el('autoScroll').checked)el('logs').scrollTop=el('logs').scrollHeight;
}
function panel(open){el('logPanel').hidden=!open;el('toggleLogs').setAttribute('aria-expanded',String(open));if(open)el('closeLogs').focus();else el('toggleLogs').focus();}
const classColors=['#00b4ff','#ffdc00','#be64ff','#ff8c1e','#6496b4','#64dc50'];
function frameView() {
  if(!result?.frames.length)return;
  const frame=result.frames[el('frames').selectedIndex];if(!frame)return;
  const path=`${base}/${job}/files/`;
  el('original').src=path+encodeURIComponent(frame.original||frame.image);
  el('showRoadMask').disabled=!frame.road_overlay;
  el('preview').src=el('showRoadMask').checked&&frame.road_overlay?path+encodeURIComponent(frame.road_overlay):el('original').src;
  el('roadMaskStatus').textContent=frame.road_mask_status==='predicted_unreviewed'?'Road Mask dự đoán · chưa duyệt, không phải Ground Truth':frame.road_mask_status==='missing_needs_review'?'Không có mask: cần kiểm tra, mọi detection vẫn được giữ.':'Job/frame chưa chạy Road Mask.';
  const rows=result.detections.map((d,index)=>({...d,index})).filter(d=>d.frame===frame.frame&&(el('category').value==='ALL'||d.category===el('category').value)&&(el('classFilter').value==='ALL'||(d.class_name||d.category)===el('classFilter').value)&&d.confidence>=Number(el('confidenceFilter').value));
  el('confidenceValue').textContent=el('confidenceFilter').value;
  const draw=()=>{const image=el('preview'),canvas=el('boxCanvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);if(!el('overlay').checked)return;for(const d of rows){const [x,y,x2,y2]=d.bbox;ctx.strokeStyle=classColors[d.local_class_id%6];ctx.lineWidth=3;ctx.strokeRect(x,y,x2-x,y2-y);ctx.fillStyle=ctx.strokeStyle;ctx.font='20px sans-serif';ctx.fillText(`${d.class_name||d.category} ${d.confidence.toFixed(2)}`,x,Math.max(22,y-6));}};
  el('preview').onload=draw;if(el('preview').complete)draw();
  el('detections').replaceChildren(...rows.map(d=>{const row=node('tr');for(const value of [d.model+' / '+(d.model_version||'Job cũ'),d.class_name||d.category,d.confidence,d.frame,d.timestamp_s])row.append(node('td',String(value)));
    const cell=node('td');const state=reviews[d.index]?.status||'ai_prediction';cell.append(node('span',state));
    if(d.road_warning&&d.road_warning!=='mask_unverified')cell.append(node('p',d.road_warning==='outside_or_partial_road_mask'?'Ngoài/giao biên Road Mask · giữ lại, cần review':'Thiếu mask · cần review'));
    const reviewLink=node('a','Mở Review Queue');reviewLink.href=`${base}/${job}/review-queue/`;cell.append(reviewLink);
    row.append(cell);row.onclick=()=>{el('boxDetail').textContent=`${d.class_name||d.category} · confidence ${d.confidence} · bbox pixel [${d.bbox.join(', ')}] · ${d.model} / ${d.model_version} · ${state}`;};return row;}));
  if(!rows.length){const row=node('tr');const cell=node('td','Không có box khớp bộ lọc trong frame này.');cell.colSpan=6;row.append(cell);el('detections').append(row);}
}
function show(data) {
  result=data;
  const classes=new Map(data.models.flatMap(m=>Object.entries(m.classes||{}).map(([id,name])=>[name,id])));el('classFilter').replaceChildren(new Option('Tất cả class','ALL'),...Array.from(classes,([name,id])=>new Option(name,name)));
  el('legend').replaceChildren(...Array.from(classes,([name,id])=>{const item=node('span',name);item.style.color=classColors[Number(id)%6];return item;}));
  el('results').hidden=false;el('frames').replaceChildren(...data.frames.map((f,i)=>new Option(`Frame ${f.frame} · ${f.timestamp_s}s`,String(i))));
  frameView();const counts=data.summary.counts;
  el('summary').textContent=`${data.summary.sampled_frames} frame đã xử lý · Nứt: ${counts.CRACK||0} box · Ổ gà: ${counts.POTHOLE||0} box · ${data.summary.runtime_seconds} giây inference/ghi ảnh. Chưa phải số lỗi duy nhất.`;
  el('limitations').textContent=data.limitations;
  el('provenance').textContent=data.models.map(m=>`${m.label} · ${m.version||m.sha256?.slice(0,12)||'Job cũ'}`).join(' | ');
  if(data.road_mask?.model)el('provenance').textContent+=` | SEGMENT ${data.road_mask.model.name} · ${data.road_mask.model.version} · mask chưa duyệt`;
  const detectedFrames=new Set(data.detections.map(d=>d.frame));const indices=new Map(data.frames.map((f,i)=>[f.frame,i]));
  const markers=data.frames.filter(f=>detectedFrames.has(f.frame));
  // A long native video may contain thousands of markers; only mount a window.
  el('markers').replaceChildren(...markers.slice(0,200).map(f=>{const b=node('button',`${f.timestamp_s}s`);b.onclick=()=>{el('frames').selectedIndex=indices.get(f.frame);frameView();};return b;}));
  if(markers.length>200)el('markers').append(node('span','Hiển thị 200 mốc đầu; mọi frame vẫn chọn được trong danh sách.'));
  el('reviewQueue').href=`${base}/${job}/review-queue/`;el('reviewQueue').hidden=false;
  el('json').href=`${base}/${job}/files/analysis.json`;
  for(const [id,name]of [['localHtml','report_local.html'],['localJson','report_local.json']]){el(id).href=`${base}/${job}/files/${name}`;el(id).hidden=false;}
  el('report').disabled=!config?.report_enabled;
}
async function poll(id) {
  if(polling){timer=setTimeout(()=>poll(id),150);return;}polling=true;
  try {
    const d=await api('/'+id);if(job!==id)return;
    el('state').textContent=`${statusLabels[d.status]||d.status} · ${d.message||''} · ID ${id}`;
    if(typeof d.progress==='number')el('progress').value=d.progress;else el('progress').removeAttribute('value');
    el('counter').textContent=Number.isFinite(d.total_frames)?`${d.processed_frames||0} / ${d.total_frames} frame`:(d.video?`${d.video.sampled_frames} frame dự kiến theo metadata máy chủ`:'Chưa có tổng frame xác minh.');
    if(Number.isFinite(d.current_frame))el('counter').textContent+=` · Frame nguồn ${d.current_frame} · ${d.timestamp_s}s · Nứt ${d.candidate_counts?.CRACK||0} / Ổ gà ${d.candidate_counts?.POTHOLE||0} box quan sát`;
    if(!result&&d.models)el('provenance').textContent=d.models.map(m=>`${m.name||m.label} · ${m.version}`).join(' | ');
    for(const n of document.querySelectorAll('#stages li'))n.classList.toggle('active',n.dataset.stage===d.stage);
    const logs=await api('/'+id+'/logs?after='+sequence);if(job!==id)return;
    for(const e of logs.events){sequence=Math.max(sequence,e.sequence);logEvents.push(e);}renderLogs();el('logConnection').textContent='Đã kết nối nhật ký phiên.';
    busy=!terminal.has(d.status);el('cancel').disabled=!busy&&d.status!=='READY';
    if(d.status==='READY'){el('roadMaskEnabled').checked=Boolean(d.segment?.enabled);if(d.segment?.model)el('segment').value=d.segment.model.id;preparedJob=id;el('estimate').textContent=`Máy chủ xác minh: ${d.video.sampled_frames} frame / ${d.video.duration_seconds.toFixed(2)} giây · ${d.sample_fps===null?'Native':d.sample_fps+' FPS'}. Chưa chạy inference.`;el('crack').value=d.selection.CRACK;el('pothole').value=d.selection.POTHOLE;el('fps').value=d.sample_fps===null?'native':String(d.sample_fps);}
    if(d.status==='COMPLETED'){reviews=d.reviews||{};show(d.result);if(d.resources)el('resources').textContent=`Tài nguyên đo trên process: RAM peak lấy mẫu ${d.resources.ram_mb} MB · VRAM ${d.resources.vram_mb} MB · ${d.resources.device}.`;}
    if(d.status==='FAILED')failure(d.error||{code:'PROCESSING_FAILED',message:'Xử lý thất bại.'});
    if(d.llm_report)el('reportText').textContent=d.llm_report.text;
    if(busy||logs.events.length===1000)timer=setTimeout(()=>poll(id),1000);else loadHistory();
  } catch(error){if(job===id){el('logConnection').textContent='Mất kết nối. Dữ liệu đã lưu vẫn được giữ.';failure(error);el('retryConfig').textContent='Kết nối lại / Đối soát phiên';}}
  finally{polling=false;controls();}
}
async function openJob(id){clearTimeout(timer);job=id;preparedJob=null;remember(id);sequence=0;logEvents=[];clearedAt=0;result=null;el('results').hidden=true;el('error').hidden=true;await poll(id);}
function upload() {
  const file=el('video').files[0];if(!file||el('prepare').disabled)return;
  busy=true;controls();el('cancel').disabled=false;el('error').hidden=true;el('state').textContent='Đang tải video vào bộ lưu trữ local…';el('progress').removeAttribute('value');
  const data=new FormData();data.append('file',file);data.append('crack_model',el('crack').value);data.append('pothole_model',el('pothole').value);data.append('sample_fps',el('fps').value);data.append('prepare_only','true');data.append('road_mask_enabled',String(el('roadMaskEnabled').checked));data.append('segment_model',el('segment').value);
  uploadKey=uploadKey||crypto.randomUUID();const xhr=new XMLHttpRequest();uploadRequest=xhr;xhr.open('POST',base+'/upload');xhr.setRequestHeader('Idempotency-Key',uploadKey);
  xhr.upload.onprogress=e=>{if(e.lengthComputable){el('progress').value=100*e.loaded/e.total;el('counter').textContent=`Upload ${Math.round(e.loaded/1048576)} / ${Math.round(e.total/1048576)} MB`;}if(e.loaded===e.total)el('state').textContent='Đã gửi byte; máy chủ đang xác minh video/model/ổ đĩa. Chưa bắt đầu inference.';};
  xhr.onload=async()=>{uploadRequest=null;let d;try{d=JSON.parse(xhr.responseText);}catch{d={detail:{code:'INVALID_RESPONSE',message:'Phản hồi upload không hợp lệ.'}};}if(xhr.status>=200&&xhr.status<300){await openJob(d.job_id);}else{busy=false;failure(d.detail||{code:'HTTP_ERROR',message:'Upload thất bại.'},'upload');controls();loadHistory();}};
  xhr.onerror=()=>{uploadRequest=null;busy=false;failure({code:'UPLOAD_UNKNOWN',message:'Mất kết nối upload; kết quả tiếp nhận chưa rõ.',action:'Mở lịch sử/đối soát trước; nếu gửi lại cùng video hãy giữ nguyên khóa yêu cầu.'},'upload');controls();};
  xhr.onabort=()=>{uploadRequest=null;busy=false;failure({code:'UPLOAD_INTERRUPTED',message:'Đã dừng truyền ở trình duyệt. Máy chủ có thể đã nhận video.',action:'Làm mới lịch sử để kiểm tra và hủy đúng phiên nếu đã được nhận.'},'upload');controls();loadHistory();};xhr.send(data);
}
async function loadHistory(){try{const d=await api('/jobs');el('history').replaceChildren(...d.jobs.map(j=>{const r=node('div',undefined,'historyRow');r.append(node('p',`${j.source_name||'Video'} · ${statusLabels[j.status]||j.status}\n${j.job_id}`));const b=node('button','Mở phiên');b.onclick=()=>openJob(j.job_id);r.append(b);return r;}));if(!d.jobs.length)el('history').textContent='Chưa có phiên lưu local.';}catch(e){failure(e,'history');}}
el('prepare').onclick=upload;el('start').onclick=async()=>{if(!preparedJob)return;const id=preparedJob;preparedJob=null;busy=true;controls();try{await api('/'+id+'/start',{method:'POST'});await poll(id);}catch(e){busy=false;failure(e,'queue');await poll(id);}};el('video').onchange=fileSelected;el('sourcePreview').onloadedmetadata=estimate;el('sourcePreview').onerror=()=>{failure({code:'VIDEO_PREVIEW_UNAVAILABLE',message:'Trình duyệt chưa hỗ trợ preview video. Vẫn có thể lưu để máy chủ kiểm tra codec và số frame.'},'decode');controls();};el('fps').onchange=estimate;
el('refreshModels').onclick=()=>loadConfig(true);el('retryConfig').onclick=async()=>{await loadConfig();if(job)await poll(job);};el('refreshHistory').onclick=loadHistory;
el('toggleLogs').onclick=()=>panel(el('logPanel').hidden);el('closeLogs').onclick=()=>panel(false);el('logFilter').onchange=renderLogs;el('clearLogs').onclick=()=>{clearedAt=logEvents.length;renderLogs();};document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!el('logPanel').hidden)panel(false);});
async function copy(text){try{await navigator.clipboard.writeText(text||'Chưa có dữ liệu.');el('logConnection').textContent='Đã sao chép.';}catch{el('logConnection').textContent='Không sao chép được. Có thể chọn nội dung chi tiết để sao chép thủ công.';}}
el('copyJob').onclick=()=>copy(job);el('copyError').onclick=()=>copy(JSON.stringify(logEvents.filter(e=>e.severity==='ERROR').slice(-1)[0]||{},null,2));
el('frames').onchange=frameView;el('category').onchange=frameView;el('previous').onclick=()=>{el('frames').selectedIndex=Math.max(0,el('frames').selectedIndex-1);frameView();};el('next').onclick=()=>{el('frames').selectedIndex=Math.min(result.frames.length-1,el('frames').selectedIndex+1);frameView();};
el('cancel').onclick=async()=>{if(uploadRequest){uploadRequest.abort();return;}if(job){try{await api('/'+job+'/cancel',{method:'POST'});el('state').textContent='Đã yêu cầu hủy; chờ frame hiện tại hoàn tất.';}catch(e){failure(e,'cancel');}}};
el('report').onclick=async()=>{if(!job)return;el('report').disabled=true;el('reportText').textContent='Đang yêu cầu provider diễn giải thống kê…';try{const r=await api('/'+job+'/report',{method:'POST'});el('reportText').textContent=r.text;}catch(e){failure(e,'report');el('reportText').textContent='Chưa có diễn giải LLM. Báo cáo thống kê local vẫn dùng được.';}finally{el('report').disabled=!config?.report_enabled;}};
for(const type of ['dragenter','dragover'])el('dropzone').addEventListener(type,e=>{e.preventDefault();el('dropzone').classList.add('drag');});el('dropzone').ondragleave=()=>el('dropzone').classList.remove('drag');el('dropzone').ondrop=e=>{e.preventDefault();el('dropzone').classList.remove('drag');if(e.dataTransfer.files.length){el('video').files=e.dataTransfer.files;fileSelected();}};
(async()=>{await loadConfig();await loadHistory();const id=new URLSearchParams(location.search).get('job')||remembered();if(id)await openJob(id);})();

for(const id of ['classFilter','confidenceFilter','overlay','showRoadMask'])el(id).oninput=frameView;
async function dashboard(){try{const d=await api('/jobs');el('dashboardStats').textContent=`${d.jobs.length} phiên đã lưu · ${d.jobs.filter(j=>j.status==='COMPLETED').length} hoàn tất · ${d.jobs.filter(j=>j.status==='FAILED').length} lỗi`; }catch(e){el('dashboardStats').textContent='Chưa đọc được lịch sử local.';}}
dashboard();

el('rollbackModels').onclick=()=>{const names={crack:'roadguard_crack_yolo11n_v1.pt',pothole:'best (1).pt'};for(const [id,name]of Object.entries(names)){const model=config?.models.find(m=>m.name===name&&m.status==='available');if(!model){failure({code:'MODEL_UNAVAILABLE',message:'Thiếu model rollback '+name},'model_loading');return;}}for(const [id,name]of Object.entries(names)){el(id).value=config.models.find(m=>m.name===name).id;el(id).dispatchEvent(new Event('change'));}};

el('roadMaskEnabled').onchange=()=>{uploadKey=null;preparedJob=null;controls();};

async function ckeyModels(){try{const c=await api('/ckey/models');el('visionModel').replaceChildren(new Option(c.vision_model,c.vision_model));el('reportModel').replaceChildren(new Option(c.report_model,c.report_model));el('ckeyStatus').textContent=c.contract_verified?'Vision đã được xác minh image input; Report chưa xác minh riêng. Mỗi lần chạy cần đồng ý chi phí.':'Chưa xác minh contract/provider image input; chạy API đang bị chặn.';}catch(e){failure(e,'ckey');}}
el('ckeyPreview').onclick=async()=>{if(!job)return;try{el('ckeyOutput').textContent=JSON.stringify(await api('/'+job+'/ckey/preview'),null,2);}catch(e){failure(e,'ckey');}};
async function runCkey(kind){if(!job||!el('ckeyConsent').checked)return failure({message:'Chọn job và xác nhận gửi dữ liệu trả phí.'},'ckey');if(kind==='vision'&&el('ckeyMode').value==='FT95')return;try{el('ckeyOutput').textContent='Đang gửi yêu cầu…';const r=await api('/'+job+'/ckey/'+kind,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm_paid:true,mode:el('ckeyMode').value})});el('ckeyOutput').textContent=JSON.stringify(r,null,2);}catch(e){failure(e,'ckey');}}
el('ckeyVision').onclick=()=>runCkey('vision');el('ckeyReport').onclick=()=>runCkey('report');ckeyModels();
