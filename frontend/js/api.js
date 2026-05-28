async function apiRequest(path, options = {}) {
  const base = getApiBase();
  const url = `${base}${path}`;
  const res = await fetch(url, {
    headers: { Accept: "application/json", ...options.headers },
    ...options,
  });

  const contentType = res.headers.get("content-type") || "";
  let body = null;
  if (contentType.includes("application/json")) {
    body = await res.json();
  } else {
    body = await res.text();
  }

  if (!res.ok) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? JSON.stringify(body.detail)
        : String(body);
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }

  return body;
}

const api = {
  health: () => apiRequest("/"),
  listAccounts: () => apiRequest("/auth/gmail/accounts"),
  syncMail: () => apiRequest("/ingestion/accounts/messages/filtered/latest"),
  runStage1ToStage2: (limit = 200) =>
    apiRequest(`/pipeline/stage1-to-stage2/run?limit=${limit}`, { method: "POST" }),
  loadTransactions: () =>
    apiRequest("/pipeline/transactions/load-from-staging", { method: "POST" }),
  getKeywords: () => apiRequest("/pipeline/keywords"),
  addKeyword: (keyword) =>
    apiRequest("/pipeline/keywords", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword }),
    }),
  getTransactions: (limit = 50) =>
    apiRequest(`/pipeline/transactions?limit=${limit}`),
  updatePolling: (accountId, intervalMin) =>
    apiRequest(
      `/auth/gmail/accounts/${accountId}/polling?interval_min=${intervalMin}`,
      { method: "PATCH" }
    ),
  updateActive: (accountId, isActive) =>
    apiRequest(
      `/auth/gmail/accounts/${accountId}/active?is_active=${isActive}`,
      { method: "PATCH" }
    ),
  removeAccount: (accountId) =>
    apiRequest(`/auth/gmail/accounts/${accountId}`, { method: "DELETE" }),
};
