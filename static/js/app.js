document.addEventListener("DOMContentLoaded", () => {
  const rowTemplate = document.getElementById("fu-04-row");

  function getApiUrl(path) {
    if (window.location.port === "5000") {
      return path;
    }
    return `http://127.0.0.1:5000${path}`;
  }

  function formatBytes(bytes) {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }

  // Multi-Batch Management & State Storage
  const batchSelect = document.getElementById('batch-select');
  const batchModal = document.getElementById('new-batch-modal');
  const batchModalClose = document.getElementById('batch-modal-close');
  const batchModalCancel = document.getElementById('batch-modal-cancel');
  const newBatchForm = document.getElementById('new-batch-form');
  const batchIdInput = document.getElementById('batch-id-input');
  const startDateInput = document.getElementById('window-start-date');
  const cutoffDateInput = document.getElementById('window-cutoff-date');
  const cutoffTimeInput = document.getElementById('cutoff-time-input');
  const monitorCutoffVal = document.getElementById('monitor-cutoff-val');
  const liveAnnouncer = document.getElementById('cb-06-live');
  const dlReportBar = document.getElementById('dl-report-bar');
  const dlReportBtn = document.getElementById('btn-download-report');
  const suspenseSection = document.getElementById('suspense-section');
  const saveBtn = document.getElementById('btn-save-batch');
  const reconcileBtn = document.getElementById('btn-reconcile-batch');

  // Active batch ID
  let activeBatchValue = batchSelect ? batchSelect.value : 'SETTLE_20260903';

  // Per-batch in-memory state map
  const batchData = {
    'SETTLE_20260903': { cutoff: '23:50:00 IST', reconciled: false, kpi: null, diagnostics: [], exceptions: [], stagedFiles: { erp: [], rzp: [] } },
    'SETTLE_20260902': { cutoff: '23:50:00 IST', reconciled: false, kpi: null, diagnostics: [], exceptions: [], stagedFiles: { erp: [], rzp: [] } },
    'SETTLE_20260901': { cutoff: '23:50:00 IST', reconciled: false, kpi: null, diagnostics: [], exceptions: [], stagedFiles: { erp: [], rzp: [] } },
  };

  // Shared staging tracker & file refs for the ACTIVE batch
  const stagingTracker = { erp: 0, rzp: 0 };
  const stagedFileRefs = { erp: [], rzp: [] };

  function setSaveState(state, msg) {
    if (!saveBtn) return;
    saveBtn.dataset.state = state;
    saveBtn.disabled = state === 'busy' || state === 'disabled';
    saveBtn.setAttribute('aria-busy', String(state === 'busy'));
    if (msg && liveAnnouncer) liveAnnouncer.textContent = msg;
  }

  function setReconcileState(state, msg) {
    if (!reconcileBtn) return;
    reconcileBtn.dataset.state = state;
    reconcileBtn.disabled = state === 'disabled' || state === 'busy';
    reconcileBtn.setAttribute('aria-busy', String(state === 'busy'));
    if (msg && liveAnnouncer) liveAnnouncer.textContent = msg;
  }

  function updateSaveGate() {
    if (!saveBtn) return;
    const hasBothFeeds = stagingTracker.erp > 0 && stagingTracker.rzp > 0;
    if (hasBothFeeds && saveBtn.dataset.state === 'disabled') {
      setSaveState('idle', '');
    } else if (!hasBothFeeds && saveBtn.dataset.state !== 'busy' && saveBtn.dataset.state !== 'done') {
      setSaveState('disabled', '');
    }
  }

  // ── Reset Dashboard to Empty / Null Values ────────────────────────────────
  function resetDashboardUI() {
    // Reset KPI Cards
    bindKpiData({
      match_rate: '—',
      match_detail: '0 / 0 Clrd',
      gross_revenue: '—',
      gateway_fees: '—',
      tax_itc: '—',
      net_payout: '—'
    });

    // Reset Match Detail Chip and ITC foot tag specifically
    const matchChip = document.querySelector('.thc-10__delta--teal');
    if (matchChip) matchChip.textContent = '0 / 0 Clrd';
    const itcFoot = document.querySelectorAll('.thc-10__foot');
    if (itcFoot[2]) itcFoot[2].textContent = 'Eligible ITC';

    // Hide Suspense Section & Clear List
    const suspenseList = document.getElementById('suspense-list');
    if (suspenseList) suspenseList.innerHTML = '';
    if (suspenseSection) suspenseSection.hidden = true;

    // HIDE Download Report Button
    if (dlReportBar) dlReportBar.hidden = true;

    // Reset Ingestion Box UI
    ['erp', 'rzp'].forEach(type => {
      const listEl = document.getElementById(`fu-${type}-list`);
      const countEl = document.getElementById(`fu-${type}-count`);
      const totalEl = document.getElementById(`fu-${type}-total`);
      const sendBtn = document.getElementById(`fu-${type}-send`);
      const statusEl = document.getElementById(`fu-${type}-status`);

      if (listEl) listEl.innerHTML = '';
      if (countEl) countEl.textContent = '0';
      if (totalEl) totalEl.textContent = '0 B of 25 MB';
      if (sendBtn) sendBtn.disabled = true;
      if (statusEl) statusEl.textContent = '';
    });

    stagingTracker.erp = 0;
    stagingTracker.rzp = 0;
    stagedFileRefs.erp = [];
    stagedFileRefs.rzp = [];

    // Reset Buttons
    setSaveState('disabled', '');
    setReconcileState('disabled', '');
  }

  // ── Render Ingestion File Box ─────────────────────────────────────────────
  function initIngestionBox(config) {
    const fileInput = document.getElementById(config.inputId);
    const listEl = document.getElementById(config.listId);
    const countEl = document.getElementById(config.countId);
    const totalEl = document.getElementById(config.totalId);
    const sendBtn = document.getElementById(config.sendBtnId);
    const statusEl = document.getElementById(config.statusId);

    if (!fileInput || !listEl) return;

    function renderStagedList() {
      listEl.innerHTML = "";
      let totalBytes = 0;

      const currentFiles = stagedFileRefs[config.trackKey] || [];

      currentFiles.forEach((file, index) => {
        totalBytes += file.size || 0;
        const clone = rowTemplate.content.cloneNode(true);

        const ext = (file.name || "").split(".").pop().toUpperCase();
        const chipEl = clone.querySelector("[data-ext]");
        if (chipEl) chipEl.textContent = ext;

        const nameEl = clone.querySelector("[data-name]");
        if (nameEl) nameEl.textContent = file.name || "";

        const sizeEl = clone.querySelector("[data-size]");
        if (sizeEl) sizeEl.textContent = formatBytes(file.size || 0);

        const rmBtn = clone.querySelector("[data-rm]");
        if (rmBtn) {
          rmBtn.addEventListener("click", () => {
            currentFiles.splice(index, 1);
            renderStagedList();
          });
        }

        listEl.appendChild(clone);
      });

      if (countEl) countEl.textContent = currentFiles.length;
      if (totalEl) totalEl.textContent = `${formatBytes(totalBytes)} of 25 MB`;
      if (sendBtn) sendBtn.disabled = currentFiles.length === 0;

      stagingTracker[config.trackKey] = currentFiles.length;
      updateSaveGate();
    }

    fileInput.addEventListener("change", (e) => {
      const files = Array.from(e.target.files);
      stagedFileRefs[config.trackKey] = [...(stagedFileRefs[config.trackKey] || []), ...files];
      renderStagedList();
      fileInput.value = "";
    });

    if (sendBtn) {
      sendBtn.addEventListener("click", async () => {
        const filesToSend = stagedFileRefs[config.trackKey] || [];
        if (filesToSend.length === 0) return;
        sendBtn.disabled = true;
        if (statusEl) statusEl.textContent = config.stageMessage;

        try {
          const formData = new FormData();
          formData.append('batch_id', activeBatchValue);
          formData.append('feed_type', config.feedType);
          filesToSend.forEach(f => formData.append('files', f));

          const res = await fetch(getApiUrl('/api/stage-files'), { method: 'POST', body: formData });
          const contentType = res.headers.get("content-type") || "";

          if (!contentType.includes("application/json")) {
            if (statusEl) statusEl.textContent = `Server error (${res.status}): Please run 'python server.py' and open http://127.0.0.1:5000/`;
            return;
          }

          const json = await res.json();

          if (res.ok && json.status === 'ok') {
            if (statusEl) statusEl.textContent = `${json.files_saved} file(s) staged successfully for batch ${activeBatchValue}.`;
            // Enable Reconcile button when files are staged
            setReconcileState('idle', '');
          } else {
            if (statusEl) statusEl.textContent = `Staging error: ${json.error || 'Unknown error'}`;
          }
        } catch (err) {
          if (statusEl) statusEl.textContent = `Network error: ${err.message}. Ensure Flask server is running at http://127.0.0.1:5000/`;
        }
      });
    }

    // Attach function to window config for programmatically rendering staged files from server
    config.renderList = renderStagedList;
  }

  // Initialize Ingestion Boxes
  initIngestionBox({
    inputId: "fu-erp-file",
    listId: "fu-erp-list",
    countId: "fu-erp-count",
    totalId: "fu-erp-total",
    sendBtnId: "fu-erp-send",
    statusId: "fu-erp-status",
    trackKey: "erp",
    feedType: "erp",
    stageMessage: "Uploading ERP Sales Register to server...",
  });

  initIngestionBox({
    inputId: "fu-rzp-file",
    listId: "fu-rzp-list",
    countId: "fu-rzp-count",
    totalId: "fu-rzp-total",
    sendBtnId: "fu-rzp-send",
    statusId: "fu-rzp-status",
    trackKey: "rzp",
    feedType: "razorpay",
    stageMessage: "Uploading Razorpay Settlement reports to server...",
  });

  // ── KPI Binding Helper ───────────────────────────────────────────────────
  function bindKpiData(kpi) {
    const matchRate = document.getElementById('kpi-match-rate');
    const grossRev = document.getElementById('kpi-gross-revenue');
    const gatewayFees = document.getElementById('kpi-gateway-fees');
    const netPayout = document.getElementById('kpi-net-payout');

    if (matchRate) matchRate.textContent = kpi ? (kpi.match_rate || '—') : '—';
    if (grossRev) grossRev.textContent = kpi ? (kpi.gross_revenue || '—') : '—';
    if (gatewayFees) gatewayFees.textContent = kpi ? (kpi.gateway_fees || '—') : '—';
    if (netPayout) netPayout.textContent = kpi ? (kpi.net_payout || '—') : '—';

    const matchChip = document.querySelector('.thc-10__delta--teal');
    if (matchChip) matchChip.textContent = kpi && kpi.match_detail ? kpi.match_detail : '0 / 0 Clrd';

    const itcFoot = document.querySelectorAll('.thc-10__foot');
    if (itcFoot[2]) itcFoot[2].textContent = kpi && kpi.tax_itc ? `${kpi.tax_itc} Eligible ITC` : 'Eligible ITC';
  }

  // ── Dynamic Suspense Queue Renderer ──────────────────────────────────────
  function renderSuspenseQueue(diagnostics, rawExceptions) {
    const suspenseList = document.getElementById('suspense-list');
    if (!suspenseList) return;

    suspenseList.innerHTML = '';

    const excMap = {};
    if (rawExceptions) {
      rawExceptions.forEach(ex => { excMap[ex.order_id] = ex; });
    }

    const items = diagnostics && diagnostics.length > 0 ? diagnostics : [];
    const renderList = items.length > 0 ? items : (rawExceptions || []).map(ex => ({
      order_id: ex.order_id,
      variance_category: ex.type,
      root_cause_diagnosis: ex.context,
      accounting_action: 'Review manually',
      risk_level: ex.type.includes('CRITICAL') || ex.type.includes('BANK_DROP') || ex.type.includes('GHOST') ? 'CRITICAL' : 'MEDIUM',
    }));

    renderList.forEach(memo => {
      const rawEx = excMap[memo.order_id] || {};
      const amount = rawEx.discrepancy_amount || '';
      const risk = (memo.risk_level || 'MEDIUM').toUpperCase();

      let chipClass = 'tls-03__chip--hold';
      let chipLabel = 'Hold';
      if (risk === 'CRITICAL') {
        chipClass = 'tls-03__chip--critical';
        chipLabel = 'Critical';
      } else if (risk === 'LOW') {
        chipClass = 'tls-03__chip--low';
        chipLabel = 'Low';
      }

      const varianceHtml = amount ? `<span class="tls-03__variance">₹${parseFloat(amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>` : '';

      const li = document.createElement('li');
      li.className = 'tls-03__item';
      li.dataset.risk = risk;

      li.innerHTML = `
        <div class="tls-03__when">
          <time>${memo.order_id}</time>
          <span class="tls-03__chip ${chipClass}">${chipLabel}</span>
        </div>
        <div class="tls-03__rail" aria-hidden="true"><span class="tls-03__dot"></span></div>
        <div class="tls-03__body">
          <p class="tls-03__role">
            ${memo.variance_category ? memo.variance_category.replace(/_/g, ' ') : 'Exception'}
            ${varianceHtml}
          </p>
          <p class="tls-03__org">${memo.root_cause_diagnosis || ''}</p>
          <ul class="tls-03__pts">
            <li>${memo.accounting_action || 'Investigate and resolve manually.'}</li>
          </ul>
        </div>
      `;

      suspenseList.appendChild(li);
    });
  }

  // ── Sync Dashboard to Active Batch State ────────────────────────────────
  async function syncDashboardToBatch(batchId) {
    // 1. Reset UI to empty first
    resetDashboardUI();

    // 2. Set subheader cutoff text
    const localData = batchData[batchId];
    if (monitorCutoffVal) {
      monitorCutoffVal.textContent = (localData && localData.cutoff) ? localData.cutoff : '23:50:00 IST';
    }

    // 3. Query backend server for batch state
    try {
      const res = await fetch(getApiUrl(`/api/batch-state/${batchId}`));
      if (!res.ok) return;

      const data = await res.json();
      if (data.status !== 'ok') return;

      // Update local batchData map with server state
      if (!batchData[batchId]) {
        batchData[batchId] = { cutoff: '23:50:00 IST' };
      }
      batchData[batchId].reconciled = data.reconciled;
      batchData[batchId].kpi = data.kpi;
      batchData[batchId].diagnostics = data.diagnostics;
      batchData[batchId].exceptions = data.exceptions;

      // Render staged file chips for this batch
      if (data.files) {
        if (data.files.erp && data.files.erp.length > 0) {
          stagedFileRefs.erp = data.files.erp.map(name => ({ name, size: 5277 }));
          stagingTracker.erp = data.files.erp.length;
          const erpList = document.getElementById('fu-erp-list');
          const erpCount = document.getElementById('fu-erp-count');
          const erpTotal = document.getElementById('fu-erp-total');
          if (erpCount) erpCount.textContent = data.files.erp.length;
          if (erpTotal) erpTotal.textContent = `${formatBytes(data.files.erp.length * 5277)} of 25 MB`;
          if (erpList) {
            erpList.innerHTML = data.files.erp.map(name => `
              <li class="fu-04__item">
                <span class="fu-04__chip" aria-hidden="true">CSV</span>
                <span class="fu-04__meta"><span class="fu-04__name">${name}</span></span>
              </li>
            `).join('');
          }
        }
        if (data.files.razorpay && data.files.razorpay.length > 0) {
          stagedFileRefs.rzp = data.files.razorpay.map(name => ({ name, size: 5048 }));
          stagingTracker.rzp = data.files.razorpay.length;
          const rzpList = document.getElementById('fu-rzp-list');
          const rzpCount = document.getElementById('fu-rzp-count');
          const rzpTotal = document.getElementById('fu-rzp-total');
          if (rzpCount) rzpCount.textContent = data.files.razorpay.length;
          if (rzpTotal) rzpTotal.textContent = `${formatBytes(data.files.razorpay.length * 5048)} of 25 MB`;
          if (rzpList) {
            rzpList.innerHTML = data.files.razorpay.map(name => `
              <li class="fu-04__item">
                <span class="fu-04__chip" aria-hidden="true">CSV</span>
                <span class="fu-04__meta"><span class="fu-04__name">${name}</span></span>
              </li>
            `).join('');
          }
        }
      }

      // If batch is reconciled: display KPIs, Suspense Queue & Download Report button
      if (data.reconciled && data.kpi) {
        bindKpiData(data.kpi);
        renderSuspenseQueue(data.diagnostics, data.exceptions);
        if (suspenseSection) suspenseSection.hidden = false;
        if (dlReportBar) dlReportBar.hidden = false; // SHOW DOWNLOAD BUTTON ONLY WHEN RECONCILED
        setReconcileState('done', 'Batch Reconciled');
      } else {
        // Unreconciled batch: HIDE Download Report button & Suspense section
        if (suspenseSection) suspenseSection.hidden = true;
        if (dlReportBar) dlReportBar.hidden = true; // HIDE DOWNLOAD BUTTON FOR UNRECONCILED BATCH

        // Enable Reconcile button if staged files exist
        const hasStaged = (data.files && data.files.erp.length > 0 && data.files.razorpay.length > 0);
        if (hasStaged || batchId === 'SETTLE_20260903') {
          setReconcileState('idle', '');
        } else {
          setReconcileState('disabled', '');
        }
      }

    } catch (err) {
      console.warn(`Failed to sync batch state for ${batchId}:`, err);
    }
  }

  // ── Action Buttons: Save Staging & Reconcile Batch ───────────────────────
  if (saveBtn && reconcileBtn) {
    saveBtn.addEventListener('click', () => {
      if (saveBtn.dataset.state !== 'idle') return;
      setSaveState('busy', 'Preserving staged vouchers to local batch...');
      setTimeout(() => {
        setSaveState('done', 'Staged batch preserved in local ledger');
        setReconcileState('idle', 'Reconcile button unlocked');
      }, 800);
    });

    reconcileBtn.addEventListener('click', async () => {
      if (reconcileBtn.dataset.state === 'busy' || reconcileBtn.dataset.state === 'disabled') return;

      setReconcileState('busy', 'Running Razorpay vs ERP matching engine...');

      try {
        const res = await fetch(getApiUrl('/api/run-reconciliation'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ batch_id: activeBatchValue }),
        });

        const contentType = res.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
          setReconcileState('idle', '');
          if (liveAnnouncer) liveAnnouncer.textContent = `Server error (${res.status}): Please run 'python server.py' and open http://127.0.0.1:5000/`;
          return;
        }

        const json = await res.json();

        if (!res.ok || json.error) {
          setReconcileState('idle', '');
          if (liveAnnouncer) liveAnnouncer.textContent = `Error: ${json.error || 'Reconciliation failed'}`;
          return;
        }

        setReconcileState('done', 'Reconciliation execution complete');

        // Bind data to dashboard
        if (json.kpi) bindKpiData(json.kpi);
        renderSuspenseQueue(json.diagnostics, json.exceptions);

        // SHOW Download report bar and Suspense queue ONLY ON SUCCESSFUL RECONCILIATION
        if (dlReportBar) dlReportBar.hidden = false;
        if (suspenseSection) suspenseSection.hidden = false;

        // Save state in local map
        if (!batchData[activeBatchValue]) {
          batchData[activeBatchValue] = {};
        }
        batchData[activeBatchValue].reconciled = true;
        batchData[activeBatchValue].kpi = json.kpi;
        batchData[activeBatchValue].diagnostics = json.diagnostics;
        batchData[activeBatchValue].exceptions = json.exceptions;

        setTimeout(() => {
          setReconcileState('done', 'Batch Reconciled');
        }, 2500);

      } catch (err) {
        setReconcileState('idle', '');
        if (liveAnnouncer) liveAnnouncer.textContent = `Network error: ${err.message}`;
      }
    });
  }

  // ── Download Report Button Click Handler ─────────────────────────────────
  if (dlReportBtn) {
    dlReportBtn.addEventListener('click', () => {
      window.location.href = getApiUrl(`/api/download-report/${activeBatchValue}`);
    });
  }

  // ── Select Dropdown & Batch Modal Logic ─────────────────────────────────
  if (batchSelect && batchModal) {
    function prefillModalDefaults() {
      const today = new Date();
      const yyyy = today.getFullYear();
      const mm = String(today.getMonth() + 1).padStart(2, '0');
      const dd = String(today.getDate()).padStart(2, '0');
      const dateStr = `${yyyy}-${mm}-${dd}`;

      const startDate = new Date();
      startDate.setDate(today.getDate() - 2);
      const startMm = String(startDate.getMonth() + 1).padStart(2, '0');
      const startDd = String(startDate.getDate()).padStart(2, '0');
      const startStr = `${startDate.getFullYear()}-${startMm}-${startDd}`;

      if (startDateInput) startDateInput.value = startStr;
      if (cutoffDateInput) cutoffDateInput.value = dateStr;
      if (batchIdInput) batchIdInput.value = `SETTLE_${yyyy}${mm}${dd}`;
    }

    function openNewBatchModal() {
      prefillModalDefaults();
      batchModal.showModal();
    }

    function closeNewBatchModal() {
      batchModal.close();
      if (batchSelect) batchSelect.value = activeBatchValue;
    }

    batchSelect.addEventListener('change', (e) => {
      const val = e.target.value;
      if (val === '__create_new__') {
        openNewBatchModal();
      } else {
        activeBatchValue = val;
        syncDashboardToBatch(val);
      }
    });

    if (batchModalClose) batchModalClose.addEventListener('click', closeNewBatchModal);
    if (batchModalCancel) batchModalCancel.addEventListener('click', closeNewBatchModal);

    batchModal.addEventListener('click', (e) => {
      const rect = batchModal.getBoundingClientRect();
      const isInDialog = (
        rect.top <= e.clientY &&
        e.clientY <= rect.top + rect.height &&
        rect.left <= e.clientX &&
        e.clientX <= rect.left + rect.width
      );
      if (!isInDialog) {
        closeNewBatchModal();
      }
    });

    if (newBatchForm) {
      newBatchForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const newBatchId = batchIdInput.value.trim();
        const cutoffTime = cutoffTimeInput.value.trim();

        if (!newBatchId) return;

        batchData[newBatchId] = {
          cutoff: cutoffTime ? `${cutoffTime}:00 IST` : '23:50:00 IST',
          reconciled: false,
          kpi: null,
          diagnostics: [],
          exceptions: [],
          stagedFiles: { erp: [], rzp: [] }
        };

        const newOption = document.createElement('option');
        newOption.value = newBatchId;
        newOption.textContent = newBatchId;

        const createOption = batchSelect.querySelector('option[value="__create_new__"]');
        batchSelect.insertBefore(newOption, createOption);

        batchSelect.value = newBatchId;
        activeBatchValue = newBatchId;

        // Switch dashboard to newly created batch (empty dashboard state)
        syncDashboardToBatch(newBatchId);

        batchModal.close();
      });
    }
  }

  // ── Login Screen & Logout Navigation ────────────────────────────────────
  const loginScreen = document.getElementById('login-screen');
  const loginForm = document.getElementById('login-form');
  const logoutBtn = document.getElementById('btn-logout');

  if (loginForm && loginScreen) {
    loginForm.addEventListener('submit', (e) => {
      e.preventDefault();
      loginScreen.classList.add('is-hidden');
    });
  }

  if (logoutBtn && loginScreen) {
    logoutBtn.addEventListener('click', () => {
      loginScreen.classList.remove('is-hidden');
    });
  }

  // Initial Sync on load
  syncDashboardToBatch(activeBatchValue);
});

// Multi-card tilt interaction for all KPI cards
(() => {
  const cards = document.querySelectorAll('.thc-10 .thc-10__card');
  if (!cards.length) return;
  if (!matchMedia('(hover:hover) and (pointer:fine)').matches) return;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const MAX = 3.5;

  cards.forEach((card) => {
    card.addEventListener('pointermove', (e) => {
      const r = card.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width;
      const py = (e.clientY - r.top) / r.height;
      card.style.setProperty('--rx', ((0.5 - py) * MAX).toFixed(2) + 'deg');
      card.style.setProperty('--ry', ((px - 0.5) * MAX).toFixed(2) + 'deg');
      card.classList.add('is-live');
    });

    card.addEventListener('pointerleave', () => {
      card.classList.remove('is-live');
      card.style.setProperty('--rx', '0deg');
      card.style.setProperty('--ry', '0deg');
    });
  });
})();