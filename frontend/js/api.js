function getApiBase() {
  const input = document.getElementById("api-base");
  return (input?.value || CONFIG.DEFAULT_API_BASE).replace(/\/$/, "");
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${getApiBase()}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const msg = data && data.detail ? data.detail : res.statusText;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

const api = {
  health: () => apiFetch("/"),
  listSms: () => apiFetch("/sms"),
  listSmsTransactions: () => apiFetch("/sms/transactions"),
  listLogs: () => apiFetch("/logs"),
};
