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
      return new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });
    } catch {
      return String(value);
    }
  }

  function formatAmount(paisa) {
    const n = Number(paisa);
    if (!Number.isFinite(n)) return String(paisa);
    return "₹" + (n / 100).toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  const nav = document.getElementById("nav");
  const pages = document.querySelectorAll(".page");
  nav.addEventListener("click", (e) => {
    const btn = e.target.closest(".nav-link");
    if (!btn) return;
    const page = btn.dataset.page;
    document.querySelectorAll(".nav-link").forEach((el) => {
      el.classList.toggle("active", el === btn);
    });
    pages.forEach((el) => el.classList.toggle("active", el.dataset.page === page));
    if (page === "home") refreshHome();
    if (page === "accounts") loadAccounts();
    if (page === "filters") loadFilters();
    if (page === "mails") loadMails();
    if (page === "sms") loadSms();
    if (page === "transactions") loadTransactions();
    if (page === "logs") loadLogs();
  });

  const apiBaseInput = document.getElementById("api-base");
  apiBaseInput.value = CONFIG.DEFAULT_API_BASE;
  apiBaseInput.addEventListener("change", () => {
    refreshHome();
  });

  document.getElementById("btn-connect-gmail").addEventListener("click", () => {
    window.location.href = `${getApiBase()}/auth/gmail/connect`;
  });

  async function refreshHome() {
    const statusEl = document.getElementById("home-status");
    const statsEl = document.getElementById("home-stats");
    statusEl.textContent = "Checking API…";
    statusEl.className = "status-card";
    try {
      const health = await api.health();
      statusEl.textContent = health.message || "API is up.";
      statusEl.classList.add("ok");
      const [accounts, filters, mails, sms, txns, logs] = await Promise.all([
        api.listAccounts().catch(() => []),
        api.listFilters().catch(() => ({ count: 0 })),
        api.listMails().catch(() => ({ total: 0 })),
        api.listSms().catch(() => ({ total: 0 })),
        api.listTransactions().catch(() => ({ total: 0 })),
        api.listLogs().catch(() => ({ total: 0 })),
      ]);
      const accountCount = Array.isArray(accounts) ? accounts.length : 0;
      statsEl.innerHTML = `
        <div class="stat"><b>${accountCount}</b> accounts</div>
        <div class="stat"><b>${filters.count || 0}</b> filters</div>
        <div class="stat"><b>${mails.total || 0}</b> mails</div>
        <div class="stat"><b>${sms.total || 0}</b> sms</div>
        <div class="stat"><b>${txns.total || 0}</b> transactions</div>
        <div class="stat"><b>${logs.total || 0}</b> log events</div>
      `;
    } catch (err) {
      statusEl.textContent = "API unreachable: " + err.message;
      statusEl.classList.add("err");
      statsEl.innerHTML = "";
    }
  }

  async function loadAccounts() {
    const el = document.getElementById("accounts-table");
    try {
      const accounts = await api.listAccounts();
      if (!accounts.length) {
        el.innerHTML = "<p class='muted'>No accounts connected.</p>";
        return;
      }
      el.innerHTML = `<table>
        <thead><tr><th>Email</th><th>Active</th><th>Last polled</th><th></th></tr></thead>
        <tbody>
          ${accounts
            .map(
              (a) => `<tr>
                <td>${a.email_address}</td>
                <td>${a.is_active ? "yes" : "no"}</td>
                <td>${formatTs(a.last_polled_at)}</td>
                <td>
                  <button data-sync="${a.id}">Sync</button>
                  <button class="danger" data-del="${a.id}">Remove</button>
                </td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
      el.querySelectorAll("[data-sync]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          try {
            const r = await api.syncOne(btn.dataset.sync);
            showToast(`Sync ${r.status}. inserted=${(r.inserted ?? 0)}`);
            loadAccounts();
          } catch (err) {
            showToast(err.message, true);
          }
        });
      });
      el.querySelectorAll("[data-del]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          if (!confirm("Remove this account?")) return;
          try {
            await api.deleteAccount(btn.dataset.del);
            showToast("Account removed");
            loadAccounts();
          } catch (err) {
            showToast(err.message, true);
          }
        });
      });
    } catch (err) {
      el.innerHTML = `<p class="err">${err.message}</p>`;
    }
  }

  document.getElementById("btn-sync-all").addEventListener("click", async () => {
    try {
      const r = await api.syncAll();
      showToast(`Synced ${r.accounts?.length || 0} account(s)`);
      loadAccounts();
    } catch (err) {
      showToast(err.message, true);
    }
  });

  document.getElementById("btn-parse").addEventListener("click", async () => {
    try {
      const r = await api.parse();
      showToast(`Parse done=${r.done} failed=${r.failed}`);
    } catch (err) {
      showToast(err.message, true);
    }
  });

  async function loadFilters() {
    const el = document.getElementById("filters-table");
    try {
      const data = await api.listFilters();
      if (!data.filters.length) {
        el.innerHTML = "<p class='muted'>No filters yet. Add a sender pattern like hdfcbank.bank.in</p>";
        return;
      }
      el.innerHTML = `<table>
        <thead><tr><th>Pattern</th><th>Active</th><th></th></tr></thead>
        <tbody>
          ${data.filters
            .map(
              (f) => `<tr>
                <td>${f.pattern}</td>
                <td>${f.is_active ? "yes" : "no"}</td>
                <td><button class="danger" data-del="${f.id}">Delete</button></td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
      el.querySelectorAll("[data-del]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          try {
            await api.deleteFilter(btn.dataset.del);
            showToast("Filter deleted");
            loadFilters();
          } catch (err) {
            showToast(err.message, true);
          }
        });
      });
    } catch (err) {
      el.innerHTML = `<p class="err">${err.message}</p>`;
    }
  }

  document.getElementById("filter-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("filter-pattern");
    try {
      await api.addFilter(input.value);
      input.value = "";
      showToast("Filter added");
      loadFilters();
    } catch (err) {
      showToast(err.message, true);
    }
  });

  async function loadMails() {
    const el = document.getElementById("mails-table");
    try {
      const data = await api.listMails();
      if (!data.mails.length) {
        el.innerHTML = "<p class='muted'>No mails ingested yet.</p>";
        return;
      }
      el.innerHTML = `<table>
        <thead><tr><th>When</th><th>From</th><th>Subject</th><th>Status</th><th>Rule</th></tr></thead>
        <tbody>
          ${data.mails
            .map(
              (m) => `<tr>
                <td>${formatTs(m.gmail_received_at)}</td>
                <td>${m.sender || "—"}</td>
                <td>${m.subject || "—"}</td>
                <td>${m.processing_status}</td>
                <td>${m.matched_filter_rule || "—"}</td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
    } catch (err) {
      el.innerHTML = `<p class="err">${err.message}</p>`;
    }
  }

  function snippet(text, max = 80) {
    const value = String(text || "");
    if (value.length <= max) return value || "—";
    return value.slice(0, max) + "…";
  }

  async function loadSms() {
    const el = document.getElementById("sms-table");
    try {
      const data = await api.listSms();
      if (!data.sms.length) {
        el.innerHTML = "<p class='muted'>No SMS ingested yet.</p>";
        return;
      }
      el.innerHTML = `<table>
        <thead><tr><th>When</th><th>From</th><th>Device</th><th>Status</th><th>Body</th></tr></thead>
        <tbody>
          ${data.sms
            .map(
              (s) => `<tr>
                <td>${formatTs(s.received_at || s.created_at)}</td>
                <td>${s.sender || "—"}</td>
                <td>${s.device_id || "—"}</td>
                <td>${s.processing_status}</td>
                <td>${snippet(s.body)}</td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
    } catch (err) {
      el.innerHTML = `<p class="err">${err.message}</p>`;
    }
  }

  async function loadLogs() {
    const el = document.getElementById("logs-table");
    try {
      const data = await api.listLogs();
      if (!data.logs.length) {
        el.innerHTML = "<p class='muted'>No event logs yet.</p>";
        return;
      }
      el.innerHTML = `<table>
        <thead><tr><th>When</th><th>Severity</th><th>Source</th><th>Event</th><th>Message</th></tr></thead>
        <tbody>
          ${data.logs
            .map(
              (row) => `<tr>
                <td>${formatTs(row.created_at)}</td>
                <td class="${row.severity === "error" ? "err" : ""}">${row.severity}</td>
                <td>${row.source}</td>
                <td>${row.event_type}</td>
                <td>${row.message}</td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
    } catch (err) {
      el.innerHTML = `<p class="err">${err.message}</p>`;
    }
  }

  async function loadTransactions() {
    const el = document.getElementById("txns-table");
    try {
      const data = await api.listTransactions();
      if (!data.transactions.length) {
        el.innerHTML = "<p class='muted'>No transactions parsed yet.</p>";
        return;
      }
      el.innerHTML = `<table>
        <thead><tr><th>When</th><th>Amount</th><th>From</th><th>Subject</th></tr></thead>
        <tbody>
          ${data.transactions
            .map(
              (t) => `<tr>
                <td>${formatTs(t.gmail_received_at || t.created_at)}</td>
                <td>${formatAmount(t.amount_paisa)}</td>
                <td>${t.sender || "—"}</td>
                <td>${t.subject || "—"}</td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
    } catch (err) {
      el.innerHTML = `<p class="err">${err.message}</p>`;
    }
  }

  const params = new URLSearchParams(location.search);
  if (params.get("connected")) {
    showToast("Connected " + params.get("connected"));
    history.replaceState({}, "", location.pathname);
  }

  refreshHome();
})();
