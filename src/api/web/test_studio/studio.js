"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const classes = ["alligator crack", "longitudinal crack", "oblique crack", "pothole", "repair", "transverse crack"];
  const names = ["Nứt da cá sấu", "Nứt dọc", "Nứt xiên", "Ổ gà", "Vùng đã vá", "Nứt ngang"];
  const colors = ["#007f88", "#c4782f", "#7c62bb", "#c04955", "#49815e", "#3e7bb8"];
  const stateNames = {AWAITING_INPUT: "Chờ đầu vào", QUEUED: "Đang xếp hàng", RUNNING: "Đang phân tích", COMPLETED: "Hoàn tất", FAILED: "Thất bại", CANCELLED: "Đã hủy", INTERRUPTED: "Bị gián đoạn"};
  const terminal = new Set(["COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"]);
  let config = null, selectedFile = null, previewUrl = null, uploadRequest = null;
  let selectedId = null, currentJob = null, jobs = [], selectionVersion = 0, pollBusy = false;
  let renderedResult = null, bearerToken = "", beBusy = false;
  const selectedClasses = new Set(classes);
  const endpoint = id => `/studio/jobs/${encodeURIComponent(id)}`;
  const artifactUrl = (jobId, artifactId) => `${endpoint(jobId)}/artifacts/${encodeURIComponent(artifactId)}`;
  const size = n => n >= 1024 ** 3 ? `${(n / 1024 ** 3).toFixed(1)} GiB` : `${(n / 1024 ** 2).toFixed(1)} MiB`;
  const time = ms => { const s = Math.max(0, Number(ms) || 0) / 1000; return `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toFixed(3).padStart(6, "0")}`; };
  const setText = (id, value) => { $(id).textContent = value; };
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function notify(message) { setText("notice", message); $("notice").hidden = !message; }
  function messageOf(body, fallback) {
    if (typeof body === "string") return body.slice(0, 500) || fallback;
    return body?.detail || body?.message || body?.errorCode || body?.code || body?.error || fallback;
  }
  async function request(path, options = {}) {
    const headers = new Headers(options.headers);
    if (options.method && options.method !== "GET") headers.set("X-Studio-Request", "1");
    const response = await fetch(path, {...options, headers, credentials: "omit", cache: "no-store", redirect: "error"});
    const text = await response.text();
    let body;
    try { body = text ? JSON.parse(text) : null; } catch { body = text; }
    if (!response.ok) throw new Error(`${response.status} · ${messageOf(body, "Yêu cầu không thành công")}`);
    return body;
  }
  function showMode(mode) {
    for (const name of ["local", "be", "workflow"]) {
      const active = mode === name;
      $(`${name}-tab`).classList.toggle("active", active);
      $(`${name}-tab`).setAttribute("aria-selected", String(active));
      $(`${name}-panel`).hidden = !active;
    }
  }
  $("workflow-tab").addEventListener("click", () => showMode("workflow"));
  function releasePreview() { if (previewUrl) URL.revokeObjectURL(previewUrl); previewUrl = null; }
  function showVideo(url) {
    const video = $("video");
    if (video.getAttribute("src") !== url) { video.src = url; video.load(); }
    video.hidden = false; $("video-empty").hidden = true;
  }
  function resetVideo() {
    $("video").pause(); $("video").removeAttribute("src"); $("video").load();
    $("video").hidden = true; $("video-empty").hidden = false; releasePreview();
  }
  function updateUploadButton() { $("upload").disabled = !selectedFile || !config?.ready || !!uploadRequest; }
  function chooseFile(file) {
    if (!file || uploadRequest) return;
    if (file.size <= 0 || file.size > (config?.maxUploadBytes ?? 2 * 1024 ** 3)) { notify("Video rỗng hoặc vượt giới hạn dung lượng."); return; }
    selectedFile = file; selectedId = null; currentJob = null; selectionVersion++;
    renderedResult = null; releasePreview(); previewUrl = URL.createObjectURL(file);
    setText("file-label", `${file.name} · ${size(file.size)}`); setText("run-name", file.name);
    showVideo(previewUrl); setText("run-state", "Xem trước cục bộ");
    setText("run-detail", "Video chưa gửi worker. Máy chủ sẽ xác minh metadata trước khi nhận phiên.");
    notify(""); renderJobList(); renderResult(null); renderActions();
    setText("saved-annotation", "Tải video lên trước khi lưu ghi chú."); updateUploadButton();
  }
  function newRun() {
    if (uploadRequest) { notify("Hãy hoàn tất hoặc dừng lượt tải hiện tại trước khi chọn video mới."); return; }
    selectedId = null; currentJob = null; selectedFile = null; selectionVersion++; renderedResult = null;
    $("video-file").value = ""; resetVideo(); renderJobList(); renderResult(null); renderActions();
    setText("file-label", "Chọn hoặc kéo video vào đây"); setText("run-name", "Chưa có video được chọn");
    setText("run-state", "Sẵn sàng"); setText("run-detail", "Kết quả xuất hiện sau khi worker hoàn tất.");
    setText("saved-annotation", "Chưa chọn phiên phân tích."); updateUploadButton();
  }
  function renderJobList() {
    const list = $("job-list"); list.replaceChildren();
    if (!jobs.length) { list.append(element("p", "empty-note", "Chưa có phiên nào. Bắt đầu bằng một video mới.")); return; }
    for (const job of jobs) {
      const button = element("button", `job${job.id === selectedId ? " active" : ""}`);
      button.type = "button"; button.setAttribute("aria-pressed", String(job.id === selectedId));
      button.append(element("strong", "", job.name || "Video không tên"));
      const date = new Date(typeof job.createdAt === "number" ? job.createdAt * 1000 : job.createdAt);
      button.append(element("small", "", `${Number.isNaN(date.getTime()) ? "" : date.toLocaleString("vi-VN", {day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"})} · ${size(job.inputBytes || 0)}`));
      button.append(element("span", "job-state", stateNames[job.state] || job.state));
      button.addEventListener("click", () => selectJob(job.id).catch(error => notify(error.message)));
      list.append(button);
    }
  }
  async function refreshJobs() {
    const result = await request("/studio/jobs"); jobs = result.items || []; renderJobList();
  }
  async function selectJob(id) {
    if (uploadRequest) { notify("Lượt tải đang hoạt động. Đợi hoàn tất hoặc dừng tải trước khi đổi phiên."); return; }
    const version = ++selectionVersion;
    selectedId = id; currentJob = null; selectedFile = null; renderedResult = null;
    $("video-file").value = ""; setText("file-label", "Chọn hoặc kéo video vào đây"); updateUploadButton();
    releasePreview(); showVideo(`${endpoint(id)}/video`); renderJobList(); renderResult(null); renderActions();
    setText("run-name", jobs.find(job => job.id === id)?.name || "Đang đọc phiên…");
    setText("run-state", "Đang đọc…"); setText("saved-annotation", "Đang đọc ghi chú…"); notify("");
    const job = await request(endpoint(id));
    if (version !== selectionVersion) return;
    applyJob(job);
    try {
      const annotation = await request(`${endpoint(id)}/annotation`);
      if (version === selectionVersion) setText("saved-annotation", annotation && Object.keys(annotation).length ? JSON.stringify(annotation, null, 2) : "Chưa có ghi chú cục bộ.");
    } catch (error) { if (version === selectionVersion) setText("saved-annotation", `Không đọc được ghi chú: ${error.message}`); }
  }
  function applyJob(job) {
    currentJob = job; setText("run-name", job.name || "Video");
    setText("run-state", stateNames[job.state] || job.state);
    $("run-state").classList.toggle("error", ["FAILED", "INTERRUPTED"].includes(job.state));
    setText("run-detail", job.errorCode ? `Mã lỗi: ${job.errorCode}` : job.cancellationRequested && !terminal.has(job.state) ? "Đã yêu cầu hủy · đang chờ worker xác nhận." : job.state === "RUNNING" ? "Worker đang chạy FT95 thật. Có thể hủy phiên khi cần." : job.state === "QUEUED" ? "Đang chờ worker. Một phiên chạy tại một thời điểm." : job.state === "COMPLETED" ? "Kết quả AI bất biến · kiểm tra box và nhãn nguồn bên dưới." : "Trạng thái được đọc từ worker cục bộ.");
    renderActions();
    if (renderedResult !== job.result && (!renderedResult || renderedResult.resultId !== job.result?.resultId)) {
      renderedResult = job.result || null; renderResult(renderedResult);
    }
  }
  function renderActions() {
    $("cancel-job").hidden = !currentJob || terminal.has(currentJob.state);
    $("retry-job").hidden = !currentJob || !["FAILED", "INTERRUPTED", "CANCELLED"].includes(currentJob.state);
    $("save-annotation").disabled = !currentJob;
  }
  async function mutateJob(action) {
    if (!selectedId) return;
    const id = selectedId, version = selectionVersion;
    const button = $(`${action}-job`); button.disabled = true;
    try {
      const job = await request(`${endpoint(id)}/${action}`, {method: "POST"});
      await refreshJobs();
      if (version !== selectionVersion) return;
      if (action === "retry") await selectJob(job.id); else applyJob(job);
    } catch (error) { notify(error.message); } finally { button.disabled = false; }
  }
  function upload() {
    if (!selectedFile || uploadRequest || !config?.ready) return;
    const file = selectedFile, xhr = new XMLHttpRequest(); uploadRequest = xhr; updateUploadButton(); notify("");
    $("upload-progress").hidden = false; $("progress").value = 0; setText("upload-message", "Đang tải video… 0%");
    xhr.open("POST", "/studio/jobs");
    xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
    xhr.setRequestHeader("X-Video-Name", encodeURIComponent(file.name)); xhr.setRequestHeader("X-Studio-Request", "1");
    // Content-Length is a forbidden request header; the browser supplies the raw File body length.
    xhr.upload.onprogress = event => {
      if (event.lengthComputable) { const value = Math.round(event.loaded / event.total * 100); $("progress").value = value; setText("upload-message", `Đang tải video… ${value}%`); }
    };
    xhr.upload.onload = () => { $("progress").removeAttribute("value"); setText("upload-message", "Đã tải xong · đang phân tích metadata, hash và kiểm tra dung lượng…"); };
    xhr.onload = async () => {
      let body; try { body = JSON.parse(xhr.responseText); } catch { body = null; }
      uploadRequest = null; $("upload-progress").hidden = true; updateUploadButton();
      if (xhr.status < 200 || xhr.status >= 300 || !body?.id) { notify(`${xhr.status} · ${messageOf(body, "Không nhận được phiên phân tích. Kiểm tra video và trạng thái máy chủ.")}`); return; }
      try { await refreshJobs(); await selectJob(body.id); } catch (error) { notify(error.message); }
    };
    xhr.onerror = () => { finishUpload("Mất kết nối khi tải video. Lịch sử phiên sẽ cho biết máy chủ đã nhận hay chưa."); };
    xhr.onabort = () => { finishUpload("Đã dừng tải ở trình duyệt. Làm mới lịch sử để kiểm tra xem máy chủ đã nhận phiên hay chưa."); };
    xhr.send(file);
  }
  function finishUpload(message) { uploadRequest = null; $("upload-progress").hidden = true; updateUploadButton(); notify(message); refreshJobs().catch(() => {}); }
  function visibleDetections(result) {
    return (result?.detections || []).filter(d => selectedClasses.has(d.sourceClass) && Number(d.confidence) >= Number($("confidence").value) / 100);
  }
  function renderResult(result) {
    $("download-json").hidden = !result; $("download-srt").hidden = !result?.telemetry?.srtArtifact;
    if (result && selectedId) {
      $("download-json").href = `${endpoint(selectedId)}/result`;
      if (result.telemetry?.srtArtifact) $("download-srt").href = artifactUrl(selectedId, result.telemetry.srtArtifact.artifactId);
    }
    setText("detection-count", result ? (result.detections || []).length.toLocaleString("vi-VN") : "—");
    setText("frame-count", result ? (result.frameArtifacts || []).length.toLocaleString("vi-VN") : "—");
    setText("gps-state", !result ? "Chưa có dữ liệu" : result.telemetry?.outcome === "EXTRACTED_VALID" ? "Có SRT nhúng" : "Thiếu telemetry đo thực");
    $("limitations-wrap").hidden = !result;
    setText("limitations", JSON.stringify(result ? {roadMaskStatus: result.roadMaskStatus, telemetry: result.telemetry, limitations: result.limitations} : {}, null, 2));
    const frames = $("frames"); frames.replaceChildren();
    if (!result) { frames.append(element("div", "results-empty", "Các frame và bounding box chuẩn hóa sẽ xuất hiện tại đây.")); setText("result-summary", "Chưa có kết quả. Không hiển thị dữ liệu mô phỏng."); return; }
    const filtered = visibleDetections(result), grouped = new Map();
    for (const detection of filtered) {
      if (!grouped.has(detection.frameArtifactId)) grouped.set(detection.frameArtifactId, []);
      grouped.get(detection.frameArtifactId).push(detection);
    }
    const allFilters = selectedClasses.size === classes.length && Number($("confidence").value) === 0;
    const artifacts = (result.frameArtifacts || []).filter(frame => allFilters || grouped.has(frame.artifactId));
    setText("result-summary", `${filtered.length} / ${(result.detections || []).length} box · ${artifacts.length} / ${(result.frameArtifacts || []).length} frame khớp bộ lọc. ${allFilters ? "Đang hiện cả frame không có box." : "Đặt ngưỡng 0% và chọn đủ nhãn để xem cả frame không có box."}`);
    if (!artifacts.length) { frames.append(element("div", "results-empty", "Không có box khớp bộ lọc. Giảm ngưỡng hoặc chọn thêm nhãn; 0 box không chứng minh mặt đường không có hư hỏng.")); return; }
    for (const artifact of artifacts) {
      const detections = grouped.get(artifact.artifactId) || [];
      const card = element("article", "frame-card"), stage = element("div", "frame-stage");
      const image = document.createElement("img"), canvas = document.createElement("canvas");
      image.loading = "lazy"; image.width = artifact.width; image.height = artifact.height;
      image.style.aspectRatio = `${artifact.width} / ${artifact.height}`;
      image.src = artifactUrl(selectedId, artifact.artifactId);
      image.alt = `Frame nguồn với ${detections.length} đề xuất AI theo bộ lọc`;
      canvas.setAttribute("aria-hidden", "true");
      const draw = () => drawBoxes(canvas, image, detections);
      image.addEventListener("load", draw);
      image.addEventListener("error", () => { image.alt = "Không tải được ảnh artifact. Làm mới phiên để thử lại."; });
      stage.append(image, canvas); card.append(stage);
      const caption = element("div", "frame-caption");
      // Frame descriptors have no PTS; never manufacture timestamps from an ordinal / sample rate.
      const sourceDetection = (result.detections || []).find(d => d.frameArtifactId === artifact.artifactId);
      if (sourceDetection) {
        const seek = element("button", "", `${time(sourceDetection.timestampMs)} ↗`);
        seek.type = "button"; seek.title = "Chuyển video đến PTS này";
        seek.addEventListener("click", () => { $("video").currentTime = sourceDetection.timestampMs / 1000; $("video").focus(); }); caption.append(seek);
      } else caption.append(element("span", "muted", "PTS không có trong descriptor"));
      caption.append(element("span", "muted", `${detections.length} box`)); card.append(caption);
      const labels = element("div", "frame-labels");
      for (const detection of detections) {
        const label = element("span", "detection-tag", `${detection.sourceClass} · ${(detection.confidence * 100).toFixed(1)}%`);
        label.style.borderColor = colors[classes.indexOf(detection.sourceClass)] || colors[0]; labels.append(label);
      }
      if (!detections.length) labels.append(element("span", "muted small", "Không có box"));
      card.append(labels); frames.append(card);
    }
  }
  function drawBoxes(canvas, image, detections) {
    if (!image.naturalWidth || !image.clientWidth) return;
    const width = image.naturalWidth, height = image.naturalHeight;
    canvas.width = width; canvas.height = height;
    const ctx = canvas.getContext("2d"); if (!ctx) return;
    const scale = width / Math.max(image.clientWidth, 1), font = Math.max(12, 10 * scale);
    ctx.lineWidth = Math.max(2, 1.6 * scale); ctx.font = `600 ${font}px Segoe UI, sans-serif`;
    for (const detection of detections) {
      const box = detection.bbox;
      if (!Array.isArray(box) || box.length !== 4 || !box.every(Number.isFinite)) continue;
      const [x, y, w, h] = box, color = colors[classes.indexOf(detection.sourceClass)] || colors[0];
      ctx.strokeStyle = color; ctx.strokeRect(x * width, y * height, w * width, h * height);
      const text = `${detection.sourceClass} ${(detection.confidence * 100).toFixed(0)}%`;
      const textWidth = ctx.measureText(text).width + 10 * scale, labelHeight = font + 8 * scale;
      const left = Math.max(0, Math.min(x * width, width - textWidth)), top = Math.max(0, y * height - labelHeight);
      ctx.fillStyle = color; ctx.fillRect(left, top, textWidth, labelHeight);
      ctx.fillStyle = "white"; ctx.fillText(text, left + 5 * scale, top + font + scale);
    }
  }
  function initFilters() {
    classes.forEach((source, index) => {
      const label = element("label", "class-filter"), input = document.createElement("input"), dot = element("i");
      input.type = "checkbox"; input.checked = true; dot.style.background = colors[index];
      const title = source === "repair" ? "Vùng đã vá trước đó; không phải công việc sửa chữa cần thực hiện" : names[index];
      label.title = title; label.append(input, dot, document.createTextNode(source));
      input.setAttribute("aria-label", `${source}: ${title}`);
      input.addEventListener("change", () => { if (input.checked) selectedClasses.add(source); else selectedClasses.delete(source); renderResult(currentJob?.result); });
      $("class-filters").append(label);
    });
  }
  function annotationKindChanged() {
    const estimate = $("annotation-kind").value === "OPERATOR_ESTIMATE";
    $("srt-field").hidden = estimate;
    document.querySelectorAll(".estimate-field").forEach(field => { field.hidden = !estimate; });
    $("latitude").required = estimate; $("longitude").required = estimate; $("annotation-reason").required = estimate;
  }
  async function saveAnnotation(event) {
    event.preventDefault(); if (!selectedId) return;
    const id = selectedId, version = selectionVersion, kind = $("annotation-kind").value;
    const body = {kind}, reason = $("annotation-reason").value.trim();
    $("save-annotation").disabled = true;
    try {
      if (kind === "EXTERNAL_SRT") {
        const file = $("annotation-srt").files[0];
        if (!file || file.size > 1024 ** 2) throw new Error("Chọn SRT không quá 1 MiB.");
        body.srtText = await file.text(); if (!body.srtText.trim()) throw new Error("SRT không được rỗng.");
        if (reason) body.reason = reason;
      } else {
        body.latitude = Number($("latitude").value); body.longitude = Number($("longitude").value); body.reason = reason;
        if (!reason || !Number.isFinite(body.latitude) || !Number.isFinite(body.longitude) || Math.abs(body.latitude) > 90 || Math.abs(body.longitude) > 180) throw new Error("Điền tọa độ hợp lệ và lý do ước lượng.");
      }
      const saved = await request(`${endpoint(id)}/annotation`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
      if (version === selectionVersion) { setText("saved-annotation", JSON.stringify(saved, null, 2)); notify("Đã lưu ghi chú cục bộ; không ghi dữ liệu sang BE."); }
    } catch (error) { notify(error.message); } finally { $("save-annotation").disabled = !currentJob; }
  }
  // Templates mirror public controller routes and DTO field names, not a new wire contract.
  const templates = [
    ["Danh sách dự án", "GET", "/api/v1/projects"],
    ["Nhiệm vụ khảo sát của tôi", "GET", "/api/v1/me/survey-tasks"],
    ["Đọc nhiệm vụ khảo sát", "GET", "/api/v1/survey-tasks/{taskId}"],
    ["Dataset của nhiệm vụ", "GET", "/api/v1/survey-tasks/{taskId}/datasets"],
    ["Đọc dataset", "GET", "/api/v1/datasets/{datasetId}"],
    ["Tạo processing job", "POST", "/api/v1/processing-jobs", {datasetId: "{datasetId}", scope: {routeVersionId: "{routeVersionId}", segmentSetId: "{segmentSetId}", segmentIds: ["{segmentId}"], targetBand: "{targetBand}"}, modelVersionId: "{modelVersionId}", preprocessingVersion: "{preprocessingVersion}", configVersion: "{configVersion}", mode: "REAL"}],
    ["Đọc processing job", "GET", "/api/v1/processing-jobs/{jobId}"],
    ["Retry processing job", "POST", "/api/v1/processing-jobs/{jobId}/retry", {reason: "{reason}"}],
    ["Khám phá video AI", "GET", "/api/v1/projects/{projectId}/ai-videos?datasetId={datasetId}"],
    ["Đọc telemetry + ETag", "GET", "/api/v1/projects/{projectId}/ai-videos/{workId}/telemetry"],
    ["Thêm telemetry revision SRT", "POST", "/api/v1/projects/{projectId}/ai-videos/{workId}/telemetry-revisions", {kind: "EXTERNAL_SRT", srtText: "{SRT text}", offsetMs: 0, estimate: null, reason: "{reason}", correctionReason: null}],
    ["Đối sánh candidate", "GET", "/api/v1/projects/{projectId}/candidates?sourceKind={sourceKind}&sourceId={sourceId}"],
    ["Đọc quyết định candidate", "GET", "/api/v1/projects/{projectId}/candidate-decisions/{decisionId}"],
    ["Quyết định candidate (theo quyền BE)", "POST", "/api/v1/projects/{projectId}/candidate-decisions", {sourceKind: "{sourceKind}", sourceId: "{sourceId}", sourceVersion: "{sourceVersion}", geometryVersion: "{geometryVersion}", decision: "{decision}", targetDefectId: null, targetVersion: null, classification: null, reason: "{reason}"}],
    ["Tạo upload session", "POST", "/api/v1/uploads", {purpose: "{purpose}", projectId: "{projectId}", targetId: "{targetId}", fileName: "video.mp4", mediaType: "video/mp4", sizeBytes: 0, checksumSha256: "{sha256}"}],
    ["Đọc upload session", "GET", "/api/v1/uploads/{uploadId}"],
    ["Xin URL upload từng phần", "POST", "/api/v1/uploads/{uploadId}/part-urls", {partNumbers: [1]}],
    ["Hoàn tất upload session", "POST", "/api/v1/uploads/{uploadId}/complete", {parts: [{partNumber: 1, eTag: "{objectStorageETag}"}], checksumSha256: "{sha256}"}],
    ["Đọc metadata file", "GET", "/api/v1/files/{fileId}"]
  ];
  function selectTemplate() {
    const template = templates[Number($("be-template").value)];
    $("be-path").value = template[2]; $("be-body").value = template[3] ? JSON.stringify(template[3], null, 2) : "";
    $("be-body").disabled = template[1] === "GET";
    setText("send-be", `${template[1]} · Gửi tới BE cục bộ ↗`);
    $("be-idempotency").value = template[1] === "POST" ? crypto.randomUUID() : "";
    $("be-etag").value = "";
  }
  async function sendBe(event) {
    event.preventDefault(); if (!config?.beConfigured || beBusy) return;
    const template = templates[Number($("be-template").value)], path = $("be-path").value.trim();
    try {
      if (!bearerToken.trim()) throw new Error("Nhập bearer token của BE. Token không được lưu sau khi đóng hoặc tải lại trang.");
      if (!path.startsWith("/api/v1/") || path.includes("://") || path.includes("#") || /[{}]/.test(path)) throw new Error("Điền ID thật vào path /api/v1/ tương đối, không dùng URL ngoài.");
      const body = {method: template[1], path};
      if (template[1] !== "GET") {
        body.body = JSON.parse($("be-body").value || "{}");
        if (/"\{[^"}]+\}"/.test(JSON.stringify(body.body))) throw new Error("Thay mọi giá trị {placeholder} trong JSON trước khi gửi.");
      }
      if ($("be-etag").value.trim()) body.etag = $("be-etag").value.trim();
      if ($("be-idempotency").value.trim()) body.idempotencyKey = $("be-idempotency").value.trim();
      beBusy = true; $("send-be").disabled = true; setText("be-response-status", "ĐANG GỌI");
      const response = await request("/studio/be", {method: "POST", headers: {"Content-Type": "application/json", Authorization: `Bearer ${bearerToken.trim()}`}, body: JSON.stringify(body)});
      setText("be-response-status", `HTTP ${response.status}`);
      setText("be-response-etag", `ETag: ${response.etag || "—"}`);
      setText("be-response", typeof response.body === "string" ? response.body : JSON.stringify(response.body, null, 2));
      notify("");
    } catch (error) { setText("be-response-status", "KHÔNG HOÀN TẤT"); setText("be-response", error.message); }
    finally { beBusy = false; $("send-be").disabled = !config?.beConfigured; }
  }
  async function poll() {
    if (pollBusy || document.hidden || uploadRequest) return;
    pollBusy = true;
    try {
      await refreshJobs();
      const id = selectedId, version = selectionVersion;
      if (id && (!currentJob || !terminal.has(currentJob.state))) {
        const job = await request(endpoint(id)); if (version === selectionVersion) applyJob(job);
      }
      if (config) { setText("connection", config.ready ? "Worker sẵn sàng" : "Worker chưa sẵn sàng"); $("connection").classList.toggle("error", !config.ready); }
    } catch (error) { setText("connection", "Mất kết nối Studio"); $("connection").classList.add("error"); }
    finally { pollBusy = false; }
  }
  async function start() {
    initFilters();
    templates.forEach((template, index) => { const option = element("option", "", `${template[1]} · ${template[0]}`); option.value = String(index); $("be-template").append(option); });
    selectTemplate();
    $("local-tab").addEventListener("click", () => showMode("local")); $("be-tab").addEventListener("click", () => showMode("be"));
    $("video-file").addEventListener("change", event => chooseFile(event.target.files[0]));
    $("video").addEventListener("error", () => notify("Trình duyệt không phát được video này. Worker vẫn kiểm tra định dạng và metadata riêng; có thể thử MP4 H.264 để xem trước."));
    $("new-run").addEventListener("click", newRun); $("upload").addEventListener("click", upload);
    $("abort-upload").addEventListener("click", () => uploadRequest?.abort());
    $("refresh").addEventListener("click", async () => { try { await refreshJobs(); if (selectedId) await selectJob(selectedId); } catch (error) { notify(error.message); } });
    $("cancel-job").addEventListener("click", () => mutateJob("cancel")); $("retry-job").addEventListener("click", () => mutateJob("retry"));
    $("confidence").addEventListener("input", () => { setText("confidence-value", `${$("confidence").value}%`); renderResult(currentJob?.result); });
    $("annotation-kind").addEventListener("change", annotationKindChanged); $("annotation-form").addEventListener("submit", saveAnnotation);
    $("be-template").addEventListener("change", selectTemplate); $("be-form").addEventListener("submit", sendBe);
    $("be-token").addEventListener("input", event => { bearerToken = event.target.value; });
    $("clear-token").addEventListener("click", () => { bearerToken = ""; $("be-token").value = ""; });
    const drop = $("dropzone");
    ["dragenter", "dragover"].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.add("drag"); }));
    ["dragleave", "drop"].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.remove("drag"); }));
    drop.addEventListener("drop", event => chooseFile(event.dataTransfer.files[0]));
    window.addEventListener("pagehide", () => { bearerToken = ""; $("be-token").value = ""; });
    window.addEventListener("beforeunload", () => { bearerToken = ""; $("be-token").value = ""; releasePreview(); });
    window.addEventListener("resize", () => document.querySelectorAll(".frame-stage").forEach(stage => {
      const image = stage.querySelector("img"), canvas = stage.querySelector("canvas");
      const id = decodeURIComponent(new URL(image.src).pathname.split("/").pop());
      drawBoxes(canvas, image, visibleDetections(currentJob?.result).filter(d => d.frameArtifactId === id));
    }));
    try {
      config = await request("/studio/config");
      setText("connection", config.ready ? "Worker sẵn sàng" : "Worker chưa sẵn sàng");
      $("connection").classList.toggle("error", !config.ready);
      setText("upload-limits", `Tối đa ${size(config.maxUploadBytes)} · ${config.maxDurationSeconds} giây · lấy mẫu ${config.sampleFps} FPS`);
      setText("be-status", config.beConfigured ? "Đã cấu hình BE cục bộ" : "BE chưa được cấu hình");
      setText("be-config-note", config.beConfigured ? "Đích BE được đặt qua môi trường máy chủ Studio. Cần BE chạy riêng và token hợp lệ; chưa có xác minh tích hợp cho tới khi gọi thật." : "BE chưa được cấu hình. Đặt URL loopback qua biến môi trường máy chủ Studio rồi khởi động lại; không có đích production mặc định.");
      $("send-be").disabled = !config.beConfigured;
      if (!config.ready) notify("Worker chưa sẵn sàng. Kiểm tra model FT95 và cấu hình máy chủ trước khi chạy video.");
      await refreshJobs(); updateUploadButton();
    } catch (error) { setText("connection", "Không kết nối được Studio"); $("connection").classList.add("error"); setText("job-list", "Không đọc được lịch sử."); setText("be-status", "Chưa xác định cấu hình BE"); notify(error.message); }
    setInterval(poll, 3000);
  }
  start();
})();
