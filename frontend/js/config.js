const CONFIG = {
  API_BASE_KEY: "trackmyspend_api_base",
  DEFAULT_API_BASE: "http://localhost:8000",
};

function getApiBase() {
  const input = document.getElementById("api-base");
  const fromInput = input?.value?.trim();
  if (fromInput) {
    return fromInput.replace(/\/$/, "");
  }
  return localStorage.getItem(CONFIG.API_BASE_KEY) || CONFIG.DEFAULT_API_BASE;
}

function saveApiBase(value) {
  const normalized = value.replace(/\/$/, "");
  localStorage.setItem(CONFIG.API_BASE_KEY, normalized);
  const input = document.getElementById("api-base");
  if (input) {
    input.value = normalized;
  }
}
