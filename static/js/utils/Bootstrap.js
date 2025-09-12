// Bootstrap.js - Safe access to bootstrapped JSON config

export function getBootstrapConfig(scriptId = 'bootstrapData') {
  try {
    const el = document.getElementById(scriptId);
    if (!el) return {};
    const text = el.textContent || el.innerText || '';
    if (!text) return {};
    const data = JSON.parse(text);
    return data && typeof data === 'object' ? data : {};
  } catch (e) {
    console.error('Failed to parse bootstrap config:', e);
    return {};
  }
}

export function getBootstrapValue(key, defaultValue = undefined) {
  const cfg = getBootstrapConfig();
  if (Object.prototype.hasOwnProperty.call(cfg, key)) {
    return cfg[key];
  }
  // Fallback for tests/legacy where window globals may be set
  if (typeof window !== 'undefined' && Object.prototype.hasOwnProperty.call(window, key)) {
    return window[key];
  }
  return defaultValue;
}
