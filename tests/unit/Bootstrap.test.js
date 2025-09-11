import { describe, it, expect, beforeEach } from 'vitest';

const { getBootstrapConfig, getBootstrapValue } = await import('../../static/js/utils/Bootstrap.js');

describe('Bootstrap utility', () => {
  beforeEach(() => {
    // reset DOM and window state
    document.body.innerHTML = '';
    if (global.window) {
      delete window.testKey;
      delete window.isTestEnvironment;
    }
  });

  it('parses JSON from script tag', () => {
    const data = { roomId: 'room-123', maxResponseLength: 321 };
    const script = document.createElement('script');
    script.id = 'bootstrapData';
    script.type = 'application/json';
    script.textContent = JSON.stringify(data);
    document.body.appendChild(script);

    const cfg = getBootstrapConfig();
    expect(cfg.roomId).toBe('room-123');
    expect(cfg.maxResponseLength).toBe(321);
  });

  it('getBootstrapValue returns key from JSON when present', () => {
    const data = { someKey: 'from-json' };
    const script = document.createElement('script');
    script.id = 'bootstrapData';
    script.type = 'application/json';
    script.textContent = JSON.stringify(data);
    document.body.appendChild(script);

    expect(getBootstrapValue('someKey', 'default')).toBe('from-json');
  });

  it('getBootstrapValue falls back to window when JSON missing key', () => {
    const data = { other: 'value' };
    const script = document.createElement('script');
    script.id = 'bootstrapData';
    script.type = 'application/json';
    script.textContent = JSON.stringify(data);
    document.body.appendChild(script);

    window.testKey = 'from-window';
    expect(getBootstrapValue('testKey', 'default')).toBe('from-window');
  });

  it('returns default when neither JSON nor window have key', () => {
    const script = document.createElement('script');
    script.id = 'bootstrapData';
    script.type = 'application/json';
    script.textContent = JSON.stringify({});
    document.body.appendChild(script);

    expect(getBootstrapValue('missing', 'default')).toBe('default');
  });
});
