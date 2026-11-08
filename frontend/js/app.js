function escapeHtml(text) {
  return String(text).replace(/[&<>"]/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
  })[ch]);
}

function formatLogContext(context) {
  if (!context || typeof context !== "object" || Array.isArray(context)) return "";
  return Object.entries(context)
    .map(([key, value]) => {
      const rendered = value !== null && typeof value === "object" ? JSON.stringify(value) : (value ?? "");
      return `${escapeHtml(key)}=${escapeHtml(rendered)}`;
    })
    .join("<br>");
}

if (typeof document === "undefined") {
  const assert = require("node:assert");
  assert.strictEqual(formatLogContext(null), "");
  assert.strictEqual(formatLogContext({}), "");
  assert.strictEqual(formatLogContext([]), "");
  assert.strictEqual(
    formatLogContext({ seen: 10, inserted: 2, skipped: 7, failed: 1 }),
    "seen=10<br>inserted=2<br>skipped=7<br>failed=1",
  );
  assert.strictEqual(formatLogContext({ note: "<b>" }), "note=&lt;b&gt;");
  assert.strictEqual(formatLogContext({ ok: false, n: 0 }), "ok=false<br>n=0");
  console.log("formatLogContext ok");
  process.exit(0);
}

(function () {
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
    if (page === "sms") loadSms();
    if (page === "logs") loadLogs();
  });

  const apiBaseInput = document.getElementById("api-base");
  apiBaseInput.value = CONFIG.DEFAULT_API_BASE;
  apiBaseInput.addEventListener("change", () => {
    refreshHome();
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
      const [sms, ledger, logs] = await Promise.all([
        api.listSms().catch(() => ({ total: 0 })),
        api.listSmsTransactions().catch(() => ({ total: 0 })),
        api.listLogs().catch(() => ({ total: 0 })),
      ]);
      statsEl.innerHTML = `
        <div class="stat"><b>${sms.total || 0}</b> sms</div>
        <div class="stat"><b>${ledger.total || 0}</b> ledger rows</div>
        <div class="stat"><b>${logs.total || 0}</b> log events</div>
      `;
    } catch (err) {
      statusEl.textContent = "API unreachable: " + err.message;
      statusEl.classList.add("err");
      statsEl.innerHTML = "";
    }
  }


  function snippet(text, max = 80) {
    const value = String(text || "");
    if (value.length <= max) return value || "—";
    return value.slice(0, max) + "…";
  }

  async function loadSms() {
    const el = document.getElementById("sms-table");
    const ledgerEl = document.getElementById("sms-ledger-table");
    try {
      const data = await api.listSms();
      if (!data.sms.length) {
        el.innerHTML = "<p class='muted'>No SMS ingested yet.</p>";
      } else {
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
      }
    } catch (err) {
      el.innerHTML = `<p class="err">${err.message}</p>`;
    }
    try {
      const data = await api.listSmsTransactions();
      if (!data.transactions.length) {
        ledgerEl.innerHTML = "<p class='muted'>No SMS ledger rows yet.</p>";
        return;
      }
      ledgerEl.innerHTML = `<table>
        <thead><tr><th>When</th><th>Kind</th><th>Amount</th><th>Instrument</th><th>Account</th><th>Counterparty</th><th>Reference</th><th>Template</th></tr></thead>
        <tbody>
          ${data.transactions
            .map(
              (t) => `<tr>
                <td>${formatTs(t.sms_received_at)}</td>
                <td>${t.kind || "—"}</td>
                <td>${t.amount_paisa == null ? "—" : formatAmount(t.amount_paisa)}</td>
                <td>${t.instrument || "—"}</td>
                <td>${t.account_mask || "—"}</td>
                <td>${t.counterparty || "—"}</td>
                <td>${t.reference || "—"}</td>
                <td>${t.template_name || "—"}</td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
    } catch (err) {
      ledgerEl.innerHTML = `<p class="err">${err.message}</p>`;
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
        <thead><tr><th>When</th><th>Severity</th><th>Source</th><th>Event</th><th>Message</th><th>Context</th></tr></thead>
        <tbody>
          ${data.logs
            .map(
              (row) => `<tr>
                <td>${formatTs(row.created_at)}</td>
                <td class="${row.severity === "error" ? "err" : ""}">${row.severity}</td>
                <td>${row.source}</td>
                <td>${row.event_type}</td>
                <td>${row.message}</td>
                <td>${formatLogContext(row.context)}</td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
    } catch (err) {
      el.innerHTML = `<p class="err">${err.message}</p>`;
    }
  }


  refreshHome();
})();
