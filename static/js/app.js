document.addEventListener("DOMContentLoaded", () => {
  const rowTemplate = document.getElementById("fu-04-row");

  function formatBytes(bytes) {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }

  function initIngestionBox(config) {
    const fileInput = document.getElementById(config.inputId);
    const listEl = document.getElementById(config.listId);
    const countEl = document.getElementById(config.countId);
    const totalEl = document.getElementById(config.totalId);
    const sendBtn = document.getElementById(config.sendBtnId);
    const statusEl = document.getElementById(config.statusId);

    if (!fileInput || !listEl) return;

    let stagedFiles = [];

    function renderStagedList() {
      listEl.innerHTML = "";
      let totalBytes = 0;

      stagedFiles.forEach((file, index) => {
        totalBytes += file.size;
        const clone = rowTemplate.content.cloneNode(true);

        const ext = file.name.split(".").pop().toUpperCase();
        const chipEl = clone.querySelector("[data-ext]");
        if (chipEl) chipEl.textContent = ext;

        const nameEl = clone.querySelector("[data-name]");
        if (nameEl) nameEl.textContent = file.name;

        const sizeEl = clone.querySelector("[data-size]");
        if (sizeEl) sizeEl.textContent = formatBytes(file.size);

        const rmBtn = clone.querySelector("[data-rm]");
        if (rmBtn) {
          rmBtn.addEventListener("click", () => {
            stagedFiles.splice(index, 1);
            renderStagedList();
          });
        }

        listEl.appendChild(clone);
      });

      if (countEl) countEl.textContent = stagedFiles.length;
      if (totalEl) totalEl.textContent = `${formatBytes(totalBytes)} of 25 MB`;
      if (sendBtn) sendBtn.disabled = stagedFiles.length === 0;
    }

    fileInput.addEventListener("change", (e) => {
      const files = Array.from(e.target.files);
      stagedFiles = [...stagedFiles, ...files];
      renderStagedList();
      fileInput.value = "";
    });

    if (sendBtn) {
      sendBtn.addEventListener("click", () => {
        if (statusEl) statusEl.textContent = config.stageMessage;
        setTimeout(() => {
          if (statusEl) statusEl.textContent = config.successMessage;
        }, 800);
      });
    }
  }

  // Initialize Box 1: ERP Sales Register Feed
  initIngestionBox({
    inputId: "fu-erp-file",
    listId: "fu-erp-list",
    countId: "fu-erp-count",
    totalId: "fu-erp-total",
    sendBtnId: "fu-erp-send",
    statusId: "fu-erp-status",
    stageMessage: "Staging ERP Sales Register files into memory...",
    successMessage: "ERP Sales Register staged successfully."
  });

  // Initialize Box 2: Razorpay Settlement Feed
  initIngestionBox({
    inputId: "fu-rzp-file",
    listId: "fu-rzp-list",
    countId: "fu-rzp-count",
    totalId: "fu-rzp-total",
    sendBtnId: "fu-rzp-send",
    statusId: "fu-rzp-status",
    stageMessage: "Staging Razorpay Settlement report files...",
    successMessage: "Razorpay Settlement reports staged successfully."
  });

  // Stateful Action Buttons: Save Staging & Reconcile Batch
  const saveBtn = document.getElementById('btn-save-batch');
  const reconcileBtn = document.getElementById('btn-reconcile-batch');
  const liveAnnouncer = document.getElementById('cb-06-live');

  if (saveBtn && reconcileBtn) {
    const setSaveState = (state, msg) => {
      saveBtn.dataset.state = state;
      saveBtn.disabled = state === 'busy';
      saveBtn.setAttribute('aria-busy', String(state === 'busy'));
      if (msg && liveAnnouncer) liveAnnouncer.textContent = msg;
    };

    const setReconcileState = (state, msg) => {
      reconcileBtn.dataset.state = state;
      reconcileBtn.disabled = state === 'disabled' || state === 'busy';
      reconcileBtn.setAttribute('aria-busy', String(state === 'busy'));
      if (msg && liveAnnouncer) liveAnnouncer.textContent = msg;
    };

    // Save Button Click Event
    saveBtn.addEventListener('click', () => {
      if (saveBtn.dataset.state !== 'idle') return;

      // 1. Busy State
      setSaveState('busy', 'Preserving staged vouchers to local batch...');

      // 2. Saved (Done) State
      setTimeout(() => {
        setSaveState('done', 'Staged batch preserved in local ledger');

        // UNLOCK Reconcile button when Save changes to Saved (done)
        setReconcileState('idle', 'Reconcile button unlocked');

        // 3. Reset Save button to Idle after confirmation
        setTimeout(() => {
          setSaveState('idle', '');
        }, 2000);
      }, 1200);
    });

    // Reconcile Button Click Event
    reconcileBtn.addEventListener('click', () => {
      if (reconcileBtn.dataset.state !== 'idle') return;

      // 1. Busy / Matching State
      setReconcileState('busy', 'Running Razorpay vs ERP matching engine...');

      // 2. Reconciled (Done) State
      setTimeout(() => {
        setReconcileState('done', 'Reconciliation execution complete');

        // Reset Reconcile button back to Idle
        setTimeout(() => {
          setReconcileState('idle', '');
        }, 2500);
      }, 1500);
    });
  }
});
// Multi-card tilt interaction for all KPI cards
(() => {
  const cards = document.querySelectorAll('.thc-10 .thc-10__card');
  if (!cards.length) return;
  if (!matchMedia('(hover:hover) and (pointer:fine)').matches) return;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const MAX = 3.5; // Subtle enterprise tilt

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