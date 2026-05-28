(function () {
  const toastEl = document.getElementById("toast");
  let toastTimer = null;

  function showToast(message, isError = false) {
    toastEl.textContent = message;
    toastEl.hidden = false;
    toastEl.classList.toggle("err", isError);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastEl.hidden = true;
    }, 4000);
  }

  function formatTs(value) {
    if (!value) return "—";
    try {
      return new Date(value).toLocaleString();
    } catch {
      return String(value);
    }
  }

  function formatAmount(amountPaisa) {
    const n = Number(amountPaisa);
    if (!Number.isFinite(n)) return `₹${amountPaisa}`;
    const rupees = n / 100;
    const formatted = rupees.toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return `₹${formatted}`;
  }

  // --- Navigation ---
  const nav = document.getElementById("nav");
  const pages = document.querySelectorAll(".page");

  nav.addEventListener("click", (e) => {
    const btn = e.target.closest(".nav-link");
    if (!btn) return;
    const page = btn.dataset.page;
    document.querySelectorAll(".nav-link").forEach((el) => {
      el.classList.toggle("active", el === btn);
    });
    pages.forEach((el) => {
      el.classList.toggle("active", el.dataset.page === page);
    });
    if (page === "accounts") loadAccounts();
    if (page === "keywords") loadKeywords();
    if (page === "transactions") loadTransactions();
  });

  // --- API base URL ---
  const apiBaseInput = document.getElementById("api-base");
  const savedBase = localStorage.getItem(CONFIG.API_BASE_KEY);
  if (savedBase) {
    apiBaseInput.value = savedBase;
  }
  apiBaseInput.addEventListener("change", () => {
    saveApiBase(apiBaseInput.value);
    refreshHome();
  });

  document.getElementById("btn-connect-gmail").href = `${getApiBase()}/auth/gmail/connect`;

  // --- Home ---
  async function refreshHome() {
    const statusEl = document.getElementById("home-status");
    const statsEl = document.getElementById("home-stats");
    statusEl.textContent = "Checking API…";
    statusEl.className = "status-card";

    try {
      const health = await api.health();
      statusEl.textContent = health.message || "API is up.";
      statusEl.classList.add("ok");

      const [accounts, keywords, transactions] = await Promise.all([
        api.listAccounts().catch(() => []),
        api.getKeywords().catch(() => ({ count: 0 })),
        api.getTransactions(1).catch(() => ({ total: 0 })),
      ]);

      const accountCount = Array.isArray(accounts) ? accounts.length : 0;
      statsEl.innerHTML = `
        <div class="stat"><div class="stat-value">${accountCount}</div><div class="stat-label">Gmail accounts</div></div>
        <div class="stat"><div class="stat-value">${keywords.count ?? 0}</div><div class="stat-label">Keywords</div></div>
        <div class="stat"><div class="stat-value">${transactions.total ?? 0}</div><div class="stat-label">Transactions</div></div>
      `;
    } catch (err) {
      statusEl.textContent = `API unreachable: ${err.message}`;
      statusEl.classList.add("err");
      statsEl.innerHTML = "";
    }
  }

  document.getElementById("btn-refresh-home").addEventListener("click", refreshHome);

  // --- Accounts ---
  async function loadAccounts() {
    const listEl = document.getElementById("accounts-list");
    listEl.innerHTML = '<p class="empty">Loading…</p>';
    document.getElementById("btn-connect-gmail").href = `${getApiBase()}/auth/gmail/connect`;

    try {
      const accounts = await api.listAccounts();
      if (!accounts.length) {
        listEl.innerHTML =
          '<p class="empty">No accounts connected. Click Connect Gmail to add one.</p>';
        return;
      }

      listEl.innerHTML = "";
      for (const acc of accounts) {
        const card = document.createElement("article");
        card.className = "account-card";
        const active = acc.is_active;
        card.innerHTML = `
          <header>
            <span class="account-email">${escapeHtml(acc.email_address)}</span>
            <span class="badge ${active ? "" : "inactive"}">${active ? "Active" : "Inactive"}</span>
          </header>
          <div class="account-meta">
            ID ${acc.id} · Poll every ${acc.polling_interval_min} min
            · Last polled ${formatTs(acc.last_polled_at)}
          </div>
          <div class="account-actions">
            <label>Poll (min): <input type="number" min="5" value="${acc.polling_interval_min}" data-poll-input /></label>
            <button type="button" class="btn" data-save-poll>Save interval</button>
            <button type="button" class="btn" data-toggle-active>${active ? "Deactivate" : "Activate"}</button>
            <button type="button" class="btn btn-danger" data-remove>Remove</button>
          </div>
        `;

        card.querySelector("[data-save-poll]").addEventListener("click", async () => {
          const input = card.querySelector("[data-poll-input]");
          try {
            await api.updatePolling(acc.id, Number(input.value));
            showToast("Polling interval updated.");
            loadAccounts();
          } catch (err) {
            showToast(err.message, true);
          }
        });

        card.querySelector("[data-toggle-active]").addEventListener("click", async () => {
          try {
            await api.updateActive(acc.id, !active);
            showToast(active ? "Account deactivated." : "Account activated.");
            loadAccounts();
          } catch (err) {
            showToast(err.message, true);
          }
        });

        card.querySelector("[data-remove]").addEventListener("click", async () => {
          if (!confirm(`Disconnect ${acc.email_address}?`)) return;
          try {
            await api.removeAccount(acc.id);
            showToast("Account removed.");
            loadAccounts();
            refreshHome();
          } catch (err) {
            showToast(err.message, true);
          }
        });

        listEl.appendChild(card);
      }
    } catch (err) {
      listEl.innerHTML = `<p class="empty">Error: ${escapeHtml(err.message)}</p>`;
    }
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // --- Pipeline ---
  const pipelineLog = document.getElementById("pipeline-log");

  function logPipeline(label, data) {
    const block = `--- ${label} @ ${new Date().toLocaleTimeString()} ---\n${JSON.stringify(data, null, 2)}\n\n`;
    pipelineLog.textContent = block + pipelineLog.textContent.replace(/^No pipeline runs yet\.\n?/, "");
  }

  async function runStep(label, fn) {
    try {
      const data = await fn();
      logPipeline(label, data);
      showToast(`${label} finished.`);
      refreshHome();
      return data;
    } catch (err) {
      logPipeline(`${label} (failed)`, { error: err.message });
      showToast(err.message, true);
      throw err;
    }
  }

  document.getElementById("btn-sync-mail").addEventListener("click", () => {
    runStep("Sync filtered mail", () => api.syncMail());
  });

  document.getElementById("btn-stage1-stage2").addEventListener("click", () => {
    runStep("Stage 1 → Stage 2", () => api.runStage1ToStage2());
  });

  document.getElementById("btn-load-transactions").addEventListener("click", () => {
    runStep("Load transactions", () => api.loadTransactions());
  });

  // --- Keywords ---
  async function loadKeywords() {
    const listEl = document.getElementById("keyword-list");
    listEl.innerHTML = "<li>Loading…</li>";
    try {
      const data = await api.getKeywords();
      const keywords = data.keywords || [];
      if (!keywords.length) {
        listEl.innerHTML = '<li class="empty">No keywords yet.</li>';
        return;
      }
      listEl.innerHTML = keywords.map((k) => `<li>${escapeHtml(k)}</li>`).join("");
    } catch (err) {
      listEl.innerHTML = `<li class="empty">Error: ${escapeHtml(err.message)}</li>`;
    }
  }

  document.getElementById("btn-refresh-keywords").addEventListener("click", loadKeywords);

  document.getElementById("form-add-keyword").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("keyword-input");
    const keyword = input.value.trim();
    if (!keyword) return;
    try {
      await api.addKeyword(keyword);
      input.value = "";
      showToast("Keyword added.");
      loadKeywords();
      refreshHome();
    } catch (err) {
      showToast(err.message, true);
    }
  });

  // --- Transactions ---
  async function loadTransactions() {
    const tbody = document.getElementById("transactions-body");
    const summary = document.getElementById("transactions-summary");
    tbody.innerHTML = '<tr><td colspan="4" class="empty">Loading…</td></tr>';

    try {
      const data = await api.getTransactions(100);
      summary.textContent = `Showing ${data.count} of ${data.total} transaction(s).`;

      const rows = data.transactions || [];
      if (!rows.length) {
        tbody.innerHTML =
          '<tr><td colspan="4" class="empty">No transactions yet. Run the pipeline first.</td></tr>';
        return;
      }

      tbody.innerHTML = rows
        .map((tx) => {
          const typeClass =
            String(tx.transaction_type).toLowerCase() === "credit"
              ? "type-credit"
              : "type-debit";
          return `<tr>
            <td>${tx.id}</td>
            <td class="${typeClass}">${escapeHtml(tx.transaction_type)}</td>
            <td>${formatAmount(tx.amount)}</td>
            <td>${formatTs(tx.transaction_ts || tx.etl_insert_ts)}</td>
          </tr>`;
        })
        .join("");
    } catch (err) {
      summary.textContent = "";
      tbody.innerHTML = `<tr><td colspan="4" class="empty">Error: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  document.getElementById("btn-refresh-transactions").addEventListener("click", loadTransactions);

  // --- Init ---
  refreshHome();
})();
