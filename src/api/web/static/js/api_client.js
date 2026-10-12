/**
 * api_client.js — RoadGuard REST API Client (Decoupled Client Architecture)
 * Đóng gói 100% giao tiếp qua HTTP API Contracts, không gọi hàm nội bộ.
 */

class RoadGuardAPIClient {
  constructor(config = {}) {
    this.baseUrl = (config.API_BASE_URL || (window.ROADGUARD_CONFIG && window.ROADGUARD_CONFIG.API_BASE_URL) || "").replace(/\/$/, "");
    this.pollingInterval = (config.POLLING_INTERVAL_MS || (window.ROADGUARD_CONFIG && window.ROADGUARD_CONFIG.POLLING_INTERVAL_MS) || 1500);
  }

  _buildUrl(endpoint) {
    if (!endpoint.startsWith("/")) {
      endpoint = "/" + endpoint;
    }
    return `${this.baseUrl}${endpoint}`;
  }

  async _request(endpoint, options = {}) {
    const url = this._buildUrl(endpoint);
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        let errDetail = `Mã lỗi HTTP ${response.status}`;
        try {
          const errJson = await response.json();
          if (errJson.detail) errDetail = errJson.detail;
        } catch (_) {}
        throw new Error(errDetail);
      }
      return await response.json();
    } catch (err) {
      console.error(`[RoadGuardAPI] Lỗi khi gọi ${endpoint}:`, err);
      throw err;
    }
  }

  // 1. KHỞI TẠO HỆ THỐNG
  async getInitInfo() {
    return await this._request("/api/init-info");
  }

  // 2. NẠP DỮ LIỆU
  async uploadVideo(file) {
    const formData = new FormData();
    formData.append("file", file);
    return await this._request("/api/upload-video", {
      method: "POST",
      body: formData
    });
  }

  async uploadDataset(file) {
    const formData = new FormData();
    formData.append("file", file);
    return await this._request("/api/upload-dataset", {
      method: "POST",
      body: formData
    });
  }

  async uploadFolder(files) {
    const formData = new FormData();
    for (let f of files) {
      formData.append("files", f);
    }
    return await this._request("/api/upload-folder", {
      method: "POST",
      body: formData
    });
  }

  // 3. ĐIỀU KHIỂN PIPELINE
  async startAnalysis(payload) {
    return await this._request("/api/start-analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  }

  async startDatasetAnalysis(payload) {
    return await this._request("/api/start-dataset-analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  }

  async getTaskStatus(taskId) {
    return await this._request(`/api/task-status/${encodeURIComponent(taskId)}`);
  }

  async getTaskResults(taskId) {
    return await this._request(`/api/task-results/${encodeURIComponent(taskId)}`);
  }

  // 4. PHÂN HỆ THẨM ĐỊNH KTV (CURATION)
  async filterAndTag(taskId, items) {
    return await this._request("/api/curation/filter-and-tag", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId, items: items })
    });
  }

  async inspectOverviewContext(taskId, items) {
    return await this._request("/api/curation/inspect-overview-context", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId, items: items })
    });
  }

  async assessCracks(taskId, items) {
    return await this._request("/api/curation/assess-cracks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId, items: items })
    });
  }

  async updateCurationItem(taskId, itemId, updateData) {
    return await this._request("/api/curation/update-item", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_id: taskId,
        item_id: itemId,
        ...updateData
      })
    });
  }

  async saveAllCuration(taskId, curatedItems) {
    return await this._request("/api/curation/save-all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_id: taskId,
        curated_items: curatedItems
      })
    });
  }

  async getCurationResults(taskId) {
    return await this._request(`/api/curation/results/${encodeURIComponent(taskId)}`);
  }

  async exportDataset(taskId, curatedItems, exportName = "curated_yolo_dataset", exportUniqueOnly = true) {
    return await this._request("/api/curation/export-dataset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_id: taskId,
        curated_items: curatedItems,
        export_name: exportName,
        export_unique_only: exportUniqueOnly
      })
    });
  }
}

// Khởi tạo instance toàn cục sẵn sàng dùng
window.RoadGuardAPI = new RoadGuardAPIClient();
