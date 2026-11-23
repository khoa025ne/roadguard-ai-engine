'use strict';
(() => {
  const el = id => document.getElementById('wf-' + id);
  let context, facts, defect, task, submission, evidence;
  let busy = false, candidateReady = false;
  const root = () => `/api/v1/projects/${context.projectId}`;
  const text = (id, value) => { el(id).textContent = value; };
  const json = value => JSON.stringify(value, null, 2);
  const value = id => el(id).value.trim();
  const nullableNumber = id => value(id) === '' ? null : Number(value(id));
  const quoted = version => version.startsWith('"') ? version : `"${version}"`;
  async function call(role, method, path, body, version) {
    const response = await fetch('/studio/workflow/be', {method:'POST', headers:{'Content-Type':'application/json','X-Studio-Request':'1'},
      body:JSON.stringify({role,method,path,body,etag:version ? quoted(version) : undefined,idempotencyKey:crypto.randomUUID()})});
    const result = await response.json();
    text('api', json(result));
    if (!response.ok || result.status >= 400) throw new Error(json(result.body || result));
    return result.body;
  }
  async function run(action) {
    if (busy) return;
    busy = true;
    const controls = [...document.querySelectorAll('#workflow-panel button, #workflow-panel select')];
    controls.forEach(b => { b.disabled = true; });
    text('message', 'Đang gọi BE thật…');
    try { await action(); text('message', 'Đã lưu/đọc lại từ BE.'); }
    catch(error) { text('message', 'Chưa hoàn tất: ' + error.message); }
    finally {
      busy = false;
      document.querySelectorAll('#workflow-panel select').forEach(s => { s.disabled = false; });
      render();
    }
  }
  function render() {
    el('refresh').disabled = !context;
    const repair = context?.classMap?.repair;
    el('keep').disabled = !candidateReady || !facts || !!defect || facts.typeCode === repair || facts.typeCode?.toLowerCase() === 'repair';
    el('assign').disabled = !defect;
    const state = String(task?.status || '').replaceAll('_','').toUpperCase();
    el('accept').disabled = !['ASSIGNED','NEWASSIGNED'].includes(state);
    el('start').disabled = state !== 'ACCEPTED';
    const measuring = ['INPROGRESS','SUPPLEMENTREQUIRED'].includes(state);
    el('upload').disabled = !measuring;
    el('submit').disabled = !measuring;
    el('review').disabled = state !== 'SUBMITTED' || !submission;
    const area = Number(task?.requiredMeasurementType || value('measure-type')) === 4 || task?.requiredMeasurementType === 'Area';
    text('unit', 'Đơn vị: ' + (area ? 'm²' : Number(task?.requiredMeasurementType || value('measure-type')) === 1 ? 'mm' : 'm'));
  }
  async function candidate() {
    facts = null; defect = null; candidateReady = false;
    const id = value('candidate');
    if (!id) return;
    facts = await call('PM','GET',root()+'/ai-candidates/'+id);
    const sourceLabel = Object.entries(context.classMap || {}).find(([,code]) => code === facts.typeCode)?.[0] || facts.typeCode;
    text('facts', `${sourceLabel} (${facts.typeCode}) · ${(facts.confidence*100).toFixed(1)}% · ${(facts.timestampMs/1000).toFixed(2)} giây · ${facts.mode}`);
    const telemetry = await call('PM','GET',root()+`/ai-videos/${context.workId}/telemetry`);
    const interval = telemetry.intervals.find(p => p.startMs <= facts.timestampMs && facts.timestampMs < p.endMs);
    text('drone', interval ? `Drone tham chiếu: ${interval.latitude}, ${interval.longitude} · ${telemetry.status}. Đây không phải vị trí hư hỏng mặt đất.` : `Không có GPS khớp thời điểm ${facts.timestampMs} ms · ${telemetry.status}.`);
    el('frame').src = '/studio/workflow/frames/'+id;
    el('frame').hidden = false;
    if (facts.disposition?.decisionId) {
      const decision = await call('PM','GET',root()+'/candidate-decisions/'+facts.disposition.decisionId);
      if (decision.defectId) defect = await call('PM','GET',root()+'/defects/'+decision.defectId);
    }
    text('defect', defect ? 'Defect đã lưu: '+defect.id : 'Chưa tạo Defect; PM phải đối chiếu ảnh và quyết định.');
    candidateReady = true;
  }
  async function readTask() {
    const id = value('tasks');
    const previous = task?.id;
    task = null; submission = null;
    if (previous !== id) {
      evidence = null;
      text('upload-state','Chưa tải ảnh cho nhiệm vụ.');
    }
    text('task','Chưa chọn hoặc chưa đọc được nhiệm vụ.');
    text('readiness','Chưa có bài đo.');
    text('submission','Crew chưa gửi số đo.');
    if (!id) return;
    const loadedTask = await call('PM','GET',root()+'/field-inspection-tasks/'+id);
    const loadedSubmission = loadedTask.latestSubmissionId ? await call('PM','GET',root()+`/field-inspection-tasks/${id}/submissions/${loadedTask.latestSubmissionId}`) : null;
    task = loadedTask; submission = loadedSubmission;
    text('task', `${task.id} · ${task.status} · phiên bản ${task.version}`);
    text('readiness', submission ? `${submission.readiness} · ${json(submission.missingReasons || [])}` : 'Chưa có bài đo.');
    text('submission', submission ? json(submission) : 'Crew chưa gửi số đo.');
  }
  async function tasks(selectId) {
    const result = await call('PM','GET',root()+'/field-inspection-tasks');
    const rows = Array.isArray(result) ? result : result.items || [];
    const selected = selectId || value('tasks');
    el('tasks').replaceChildren(new Option('Chọn nhiệm vụ', ''), ...rows.map(t => new Option(`${t.status} · ${t.id}`,t.id)));
    if (rows.some(t => t.id === selected)) el('tasks').value = selected;
    await readTask();
  }
  el('refresh').onclick = () => run(async () => { await candidate(); await tasks(); });
  el('candidate').onchange = () => run(candidate);
  el('tasks').onchange = () => run(readTask);
  el('measure-type').onchange = render;
  el('frame').onerror = () => { el('frame').hidden = true; };
  el('frame').onload = () => {
    const image = el('frame'), canvas = el('box'), box = facts?.boundingBox;
    canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
    const ctx = canvas.getContext('2d'); ctx.clearRect(0,0,canvas.width,canvas.height);
    if (box) {ctx.lineWidth=5;ctx.strokeStyle='#f02f46';ctx.strokeRect(box.x*canvas.width,box.y*canvas.height,box.width*canvas.width,box.height*canvas.height);}
  };
  el('keep').onclick = () => run(async () => {
    if (!value('decision-reason')) throw new Error('Nhập lý do PM.');
    const decision = await call('PM','POST',root()+'/candidate-decisions',{
      sourceKind:'AI_DETECTION',sourceId:facts.detectionId,sourceVersion:facts.sourceVersion,geometryVersion:facts.geometryVersion,
      decision:'KEEP_NEW',targetDefectId:null,targetVersion:null,
      classification:{defectTypeCode:facts.typeCode,causeCategoryCode:context.causeCategoryCode || null,severity:value('severity'),
        roadSectionVersionId:facts.routeVersionId,segmentId:context.segmentId},reason:value('decision-reason')});
    defect = await call('PM','GET',root()+'/defects/'+decision.defectId);
    await candidate();
  });
  el('assign').onclick = () => run(async () => {
    if (!value('due') || !value('instructions')) throw new Error('Nhập hạn và chỉ dẫn.');
    defect = await call('PM','GET',root()+'/defects/'+defect.id);
    const created = await call('PM','POST',root()+'/field-inspection-tasks',{
      defectId:defect.id,defectVersion:defect.version,surveyId:context.surveyId,sourceKind:'SURVEY',
      routeVersionId:context.routeVersionId,segmentSetId:context.segmentSetId,layoutRevisionId:null,slabId:null,
      purpose:'PRE_MEASUREMENT',requiredMeasurementType:Number(value('measure-type')),measurementScope:'{}',
      instructions:value('instructions'),assignedToUserId:context.crewUserId,dueAt:new Date(value('due')).toISOString(),
      mapPublicationId:context.geometryEvidence?.mapPublicationId || null,crsProfileRevisionId:context.geometryEvidence?.crsProfileRevisionId || null});
    await tasks(created.id);
  });
  el('accept').onclick = () => run(async () => {
    await call('CREW','POST',root()+`/field-inspection-tasks/${task.id}/accept`,{reason:'Crew nhận nhiệm vụ test.'},task.version); await readTask();
  });
  el('start').onclick = () => run(async () => {
    await call('CREW','POST',root()+`/field-inspection-tasks/${task.id}/start`,{originId:crypto.randomUUID(),claimedAt:new Date().toISOString()},task.version); await readTask();
  });
  el('upload').onclick = () => run(async () => {
    const file = el('photo').files[0];
    if (!file || !['image/jpeg','image/png'].includes(file.type) || file.size > 20*1024*1024) throw new Error('Chọn ảnh JPEG/PNG tối đa 20 MiB.');
    const response = await fetch(`/studio/workflow/tasks/${task.id}/photo`,{method:'POST',headers:{'Content-Type':file.type,'X-Studio-Request':'1'},body:file});
    const result = await response.json(); text('api',json(result));
    if (!response.ok) throw new Error(json(result));
    evidence = result; text('upload-state','MinIO đã xác minh ảnh: '+result.fileId);
  });
  el('submit').onclick = () => run(async () => {
    if (value('value') === '' || Number(value('value')) < 0) throw new Error('Nhập số đo không âm.');
    if (!el('markings').checked || value('chainage') === '') throw new Error('Nhập lý trình và xác nhận đối chiếu mốc.');
    const latitude = nullableNumber('lat'), longitude = nullableNumber('lon');
    if ((latitude === null) !== (longitude === null)) throw new Error('Nhập cả vĩ độ và kinh độ.');
    if (latitude === null && !value('location-reason')) throw new Error('Nhập lý do chưa biết tọa độ mặt đất.');
    if (!evidence) throw new Error('Tải ảnh bằng Crew trước khi gửi bài đo.');
    const start = await call('CREW','GET',root()+`/field-inspection-tasks/${task.id}/start-origin`);
    const types = {1:['DepressionDepth','LENGTH','mm'],4:['Area','AREA','m²'],5:['DepressionLength','LENGTH','m'],6:['DepressionWidth','LENGTH','m']};
    const type = types[Number(task.requiredMeasurementType)] || Object.values(types).find(t => t[0] === task.requiredMeasurementType);
    if (!type) throw new Error('Loại đo chưa được UI hỗ trợ.');
    await call('CREW','POST',root()+`/field-inspection-tasks/${task.id}/submissions`,{
      originId:crypto.randomUUID(),startOriginId:start.id,parentSubmissionId:task.latestSubmissionId || null,
      measurements:[{sampleId:'sample-'+crypto.randomUUID(),type:type[0],value:Number(value('value')),state:'KNOWN',unknownReason:null,
        dimension:type[1],unit:type[2],longitude,latitude,locationReason:latitude === null ? value('location-reason') : null,
        instrument:value('instrument'),method:value('method'),notes:'Local test; không phải đo thực địa.'}],
      evidence:[{captureOriginId:crypto.randomUUID(),fileId:evidence.fileId,purpose:'MEASUREMENT',checksumSha256:evidence.checksumSha256,
        mediaType:evidence.mediaType,capturedAt:new Date().toISOString(),attemptChecklist:null}],
      locationProof:{kind:'POSITION_CHECKLIST',checklist:'SEGMENT_MARKINGS_CONFIRMED',longitude:null,latitude:null,
        observedSegmentId:context.segmentId,observedRouteVersionId:context.routeVersionId,observedChainageMeters:Number(value('chainage'))},
      captureType:'MEASUREMENT',repaired:null,unrepairedReason:null},task.version);
    await readTask();
  });
  el('review').onclick = () => run(async () => {
    const result = await call('PM','POST',root()+`/field-inspection-tasks/${task.id}/reviews`,{
      submissionId:submission.id,decision:value('review-kind'),reason:value('review-reason')},task.version);
    text('review-result',json(result)); await tasks(task.id);
  });
  run(async () => {
    const response = await fetch('/studio/workflow/context');
    if (!response.ok) throw new Error('Chưa bật fixture BE local cho màn hình này.');
    context = await response.json();
    text('context',(context.projectName || 'Dự án AI–Crew local')+' · AI REAL đã lưu vào BE · dữ liệu local riêng.');
    text('assignee','Crew được phân công trong dự án: '+context.crewUserId);
    if (context.chainageRange) {
      el('chainage').min = context.chainageRange.min;
      el('chainage').max = context.chainageRange.max;
      el('chainage').placeholder = `Đoạn test: ${context.chainageRange.min}–${context.chainageRange.max} m`;
    }
    el('candidate').replaceChildren(...context.detectionIds.map((id,i) => new Option(`Đề xuất ${i+1} · ${id.slice(0,8)}`,id)));
    const tomorrow = new Date(Date.now()+86400000); tomorrow.setMinutes(tomorrow.getMinutes()-tomorrow.getTimezoneOffset());
    el('due').value = tomorrow.toISOString().slice(0,16);
    await candidate(); await tasks();
  });
})();
