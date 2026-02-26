/**
 * ProCiv Madeira — Lovelace Cards
 *
 * Served and injected automatically by the integration. No manual resource
 * registration needed.
 *
 * Two card types are provided:
 *
 *   type: custom:prociv-madeira-card          ← compact, expandable rows
 *   type: custom:prociv-madeira-detail-card   ← always-expanded detail list
 *
 * Both accept:
 *   entities:
 *     - sensor.costa_norte
 *     - sensor.costa_sul
 *     - sensor.porto_santo
 *     - sensor.regioes_montanhosas
 *   title: "ProCiv Madeira"   # optional
 */

// ── Shared colour palette ──────────────────────────────────────────────────────

const ALERT_COLORS = {
  GREEN: {
    badge: '#00a846',
    text: '#ffffff',
    bg: 'rgba(0,168,70,0.10)',
    border: '#00b050',
  },
  YELLOW: {
    badge: '#c49b00',
    text: '#ffffff',
    bg: 'rgba(196,155,0,0.12)',
    border: '#ffd712',
  },
  ORANGE: {
    badge: '#d06000',
    text: '#ffffff',
    bg: 'rgba(208,96,0,0.12)',
    border: '#ffa500',
  },
  RED: {
    badge: '#b00000',
    text: '#ffffff',
    bg: 'rgba(176,0,0,0.12)',
    border: '#c00000',
  },
};

const ALERT_ICONS = {
  GREEN: 'mdi:check-circle',
  YELLOW: 'mdi:alert-circle',
  ORANGE: 'mdi:alert',
  RED: 'mdi:alert-octagon',
};

const ALERT_LABELS = {
  GREEN: 'Normal',
  YELLOW: 'Moderate',
  ORANGE: 'High',
  RED: 'Extreme',
};

const SEVERITY_RANK = { GREEN: 0, YELLOW: 1, ORANGE: 2, RED: 3 };

// ── Demo data for the card-picker preview ──────────────────────────────────────

const DEMO_STATES = {
  'sensor.costa_norte': {
    state: 'GREEN',
    attributes: {
      region: 'Costa Norte',
      problem_type: null,
      description: null,
      start_date: null,
      end_date: null,
    },
  },
  'sensor.costa_sul': {
    state: 'YELLOW',
    attributes: {
      region: 'Costa Sul',
      problem_type: 'Agitação Marítima',
      description: 'Ondulação de Noroeste com 2 a 3 metros de altura.',
      start_date: '2024-01-15T10:00:00',
      end_date: '2024-01-16T08:00:00',
    },
  },
  'sensor.porto_santo': {
    state: 'GREEN',
    attributes: {
      region: 'Porto Santo',
      problem_type: null,
      description: null,
      start_date: null,
      end_date: null,
    },
  },
  'sensor.regioes_montanhosas': {
    state: 'ORANGE',
    attributes: {
      region: 'Regiões Montanhosas',
      problem_type: 'Precipitação',
      description:
        'Chuva por vezes forte, podendo ser acompanhada de trovoada.',
      start_date: '2024-01-15T06:00:00',
      end_date: '2024-01-15T18:00:00',
    },
  },
};

// ── Shared helpers ─────────────────────────────────────────────────────────────

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('pt-PT', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function worstState(states) {
  return states.reduce((worst, s) => {
    return (SEVERITY_RANK[s] ?? -1) > (SEVERITY_RANK[worst] ?? -1) ? s : worst;
  }, 'GREEN');
}

// ── Card 1: prociv-madeira-card (compact, expandable) ─────────────────────────

class ProcivMadeiraCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._expandedEntities = new Set();
    this._preview = false;
  }

  setConfig(config) {
    if (
      !config.entities ||
      !Array.isArray(config.entities) ||
      config.entities.length === 0
    ) {
      throw new Error('prociv-madeira-card: provide at least one entity ID.');
    }
    this._config = config;
  }

  set preview(val) {
    this._preview = val;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _stateFor(id) {
    return (
      this._hass?.states[id] ??
      (this._preview || !this._hass ? DEMO_STATES[id] : null)
    );
  }

  // ── row ───────────────────────────────────────────────────────────────────

  _rowHtml(id) {
    const state = this._stateFor(id);
    if (!state)
      return `<div class="row-error">Entity not found:<br><code>${id}</code></div>`;

    const alertType = ALERT_COLORS[state.state] ? state.state : 'GREEN';
    const c = ALERT_COLORS[alertType];
    const icon = ALERT_ICONS[alertType] ?? 'mdi:help-circle';
    const label = ALERT_LABELS[alertType] ?? alertType;
    const attrs = state.attributes ?? {};
    const region = attrs.region ?? attrs.friendly_name ?? id;
    const problem = attrs.problem_type;
    const startDate = attrs.start_date;
    const endDate = attrs.end_date;
    const desc = attrs.description;

    const hasDetails =
      alertType !== 'GREEN' && (problem || startDate || endDate || desc);
    const expanded = this._expandedEntities.has(id);

    return `
      <div class="region-row"
           data-entity="${id}"
           data-expandable="${hasDetails}"
           style="--ac:${c.badge};--ac-bg:${c.bg};--ac-border:${c.border};--ac-text:${c.text};">
        <div class="row-main">
          <div class="icon-circle"><ha-icon icon="${icon}"></ha-icon></div>
          <div class="region-info">
            <span class="region-name">${region}</span>
            ${problem ? `<span class="problem-label">${problem}</span>` : ''}
          </div>
          <span class="alert-badge">${label}</span>
          ${
            hasDetails
              ? `<ha-icon class="chevron" icon="${expanded ? 'mdi:chevron-up' : 'mdi:chevron-down'}"></ha-icon>`
              : `<span class="chevron-placeholder"></span>`
          }
        </div>
        ${
          hasDetails && expanded
            ? `
        <div class="row-details">
          ${desc ? `<p class="detail-desc">${desc}</p>` : ''}
          ${
            startDate || endDate
              ? `
          <div class="detail-dates">
            <ha-icon icon="mdi:calendar-range"></ha-icon>
            <span>${fmtDate(startDate)} → ${fmtDate(endDate)}</span>
          </div>`
              : ''
          }
        </div>`
            : ''
        }
      </div>`;
  }

  // ── render ────────────────────────────────────────────────────────────────

  _render() {
    if (!this._config) return;
    if (!this._hass && !this._preview) return;

    const ids = this._config.entities;
    const states = ids.map((id) => this._stateFor(id)?.state ?? 'GREEN');
    const worst = worstState(states);
    const wc = ALERT_COLORS[worst];
    const title = this._config.title ?? 'Madeira - Weather Alerts';
    const hdrIcon = worst === 'GREEN' ? 'mdi:shield-check' : 'mdi:shield-alert';

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .card {
          background: var(--ha-card-background, var(--card-background-color, #fff));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 10px rgba(0,0,0,.12));
          overflow: hidden;
          font-family: var(--primary-font-family, Roboto, sans-serif);
        }
        .accent-bar { height: 4px; background: linear-gradient(90deg, ${wc.badge}, ${wc.border}cc); }
        .card-header {
          display: flex; align-items: center; gap: 10px;
          padding: 14px 16px 12px;
          border-bottom: 1px solid var(--divider-color, rgba(0,0,0,.08));
        }
        .header-icon { --mdc-icon-size: 26px; color: ${wc.badge}; filter: drop-shadow(0 0 6px ${wc.badge}88); flex-shrink: 0; }
        .header-title { flex: 1; font-size: .97rem; font-weight: 600; color: var(--primary-text-color); letter-spacing: .25px; }
        .header-badge { font-size: .68rem; font-weight: 700; letter-spacing: .7px; text-transform: uppercase; padding: 4px 10px; border-radius: 20px; background: ${wc.badge}; color: ${wc.text}; }
        .regions-list { padding: 6px 12px; }
        .region-row { border-left: 3px solid var(--ac-border); background: var(--ac-bg); border-radius: 0 8px 8px 0; margin: 4px 0; cursor: pointer; transition: filter .15s; }
        .region-row:hover { filter: brightness(.96); }
        .row-main { display: flex; align-items: center; gap: 10px; padding: 10px 6px; }
        .icon-circle { width: 36px; height: 36px; border-radius: 50%; background: var(--ac); display: flex; align-items: center; justify-content: center; flex-shrink: 0; box-shadow: 0 2px 8px var(--ac)66; }
        .icon-circle ha-icon { --mdc-icon-size: 20px; color: #fff; }
        .region-info { flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
        .region-name { font-size: .875rem; font-weight: 600; color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .problem-label { font-size: .72rem; color: var(--ac); font-weight: 500; }
        .alert-badge { font-size: .66rem; font-weight: 700; letter-spacing: .7px; text-transform: uppercase; padding: 3px 9px; border-radius: 20px; background: var(--ac); color: var(--ac-text); flex-shrink: 0; }
        .chevron { --mdc-icon-size: 18px; color: var(--secondary-text-color); flex-shrink: 0; }
        .chevron-placeholder { width: 18px; flex-shrink: 0; }
        .row-details { padding: 0 6px 10px 52px; display: flex; flex-direction: column; gap: 5px; }
        .detail-desc { margin: 0; font-size: .76rem; color: var(--secondary-text-color); line-height: 1.4; }
        .detail-dates { display: flex; align-items: center; gap: 6px; font-size: .74rem; color: var(--secondary-text-color); }
        .detail-dates ha-icon { --mdc-icon-size: 14px; color: var(--ac); }
        .row-error { padding: 8px 16px; color: var(--error-color, #b00); font-size: .78rem; }
      </style>

      <div class="card">
        <div class="accent-bar"></div>
        <div class="card-header">
          <ha-icon class="header-icon" icon="${hdrIcon}"></ha-icon>
          <span class="header-title">${title}</span>
          <span class="header-badge">${ALERT_LABELS[worst] ?? worst}</span>
        </div>
        <div class="regions-list">
          ${ids.map((id) => this._rowHtml(id)).join('')}
        </div>
      </div>`;

    this.shadowRoot.querySelectorAll('.region-row').forEach((row) => {
      row.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = row.dataset.entity;
        const expandable = row.dataset.expandable === 'true';
        if (expandable) {
          this._expandedEntities.has(id)
            ? this._expandedEntities.delete(id)
            : this._expandedEntities.add(id);
          this._render();
        } else {
          this.dispatchEvent(
            new CustomEvent('hass-more-info', {
              bubbles: true,
              composed: true,
              detail: { entityId: id },
            }),
          );
        }
      });
    });
  }

  getCardSize() {
    return Math.ceil((this._config?.entities?.length ?? 4) * 0.85) + 2;
  }

  static getStubConfig() {
    return {
      entities: [
        'sensor.costa_norte',
        'sensor.costa_sul',
        'sensor.porto_santo',
        'sensor.regioes_montanhosas',
      ],
    };
  }
}

customElements.define('prociv-madeira-card', ProcivMadeiraCard);

// ── Card 2: prociv-madeira-detail-card (always-expanded detail list) ──────────

class ProcivMadeiraDetailCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._preview = false;
  }

  setConfig(config) {
    if (
      !config.entities ||
      !Array.isArray(config.entities) ||
      config.entities.length === 0
    ) {
      throw new Error(
        'prociv-madeira-detail-card: provide at least one entity ID.',
      );
    }
    this._config = config;
  }

  set preview(val) {
    this._preview = val;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _stateFor(id) {
    return (
      this._hass?.states[id] ??
      (this._preview || !this._hass ? DEMO_STATES[id] : null)
    );
  }

  // ── row ───────────────────────────────────────────────────────────────────

  _rowHtml(id) {
    const state = this._stateFor(id);
    if (!state)
      return `<div class="row-error">Entity not found: <code>${id}</code></div>`;

    const alertType = ALERT_COLORS[state.state] ? state.state : 'GREEN';
    const c = ALERT_COLORS[alertType];
    const attrs = state.attributes ?? {};
    const region = attrs.region ?? attrs.friendly_name ?? id;
    const problem = attrs.problem_type;
    const desc = attrs.description;
    const startDate = attrs.start_date;
    const endDate = attrs.end_date;

    return `
      <div class="region-row" style="border-left-color:${c.border};background:${c.bg};">
        <div class="row-header">
          <span class="region-name">${region}</span>
          <span class="alert-badge" style="background:${c.badge};color:${c.text};">${ALERT_LABELS[alertType]}</span>
        </div>
        ${problem ? `<div class="problem-label">⚠ ${problem}</div>` : ''}
        ${desc ? `<div class="detail-desc">${desc}</div>` : ''}
        ${
          startDate || endDate
            ? `
        <div class="detail-dates">
          📅 <span>${fmtDate(startDate)}</span><span class="arrow">→</span><span>${fmtDate(endDate)}</span>
        </div>`
            : ''
        }
      </div>`;
  }

  // ── render ────────────────────────────────────────────────────────────────

  _render() {
    if (!this._config) return;
    if (!this._hass && !this._preview) return;

    const ids = this._config.entities;
    const title = this._config.title ?? 'ProCiv Madeira';
    const worst = worstState(
      ids.map((id) => this._stateFor(id)?.state ?? 'GREEN'),
    );
    const wc = ALERT_COLORS[worst];
    const wIcon = ALERT_ICONS[worst];

    const firstState = this._stateFor(ids[0]);
    const lastUpdated = firstState?.last_updated
      ? fmtDate(firstState.last_updated)
      : this._preview
        ? '15 Jan, 14:30'
        : '—';

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .card {
          background: var(--ha-card-background, var(--card-background-color, #fff));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 10px rgba(0,0,0,.12));
          overflow: hidden;
          font-family: var(--primary-font-family, Roboto, sans-serif);
        }
        .accent-bar { height: 4px; background: linear-gradient(90deg, ${wc.badge}, ${wc.border}cc); }
        .summary-row {
          display: flex; align-items: center; gap: 10px;
          margin: 10px 12px 0; padding: 10px 12px;
          background: ${wc.bg}; border-left: 4px solid ${wc.border}; border-radius: 0 8px 8px 0;
        }
        .summary-icon { --mdc-icon-size: 20px; color: ${wc.badge}; flex-shrink: 0; }
        .summary-text { flex: 1; font-weight: 600; font-size: .88rem; color: var(--primary-text-color); }
        .summary-badge { background: ${wc.badge}; color: ${wc.text}; font-size: .6rem; font-weight: 700; letter-spacing: .7px; text-transform: uppercase; padding: 3px 10px; border-radius: 20px; white-space: nowrap; }
        .regions-list { padding: 8px 12px; display: flex; flex-direction: column; gap: 7px; }
        .region-row { border-left: 4px solid; border-radius: 0 8px 8px 0; padding: 9px 12px 9px 14px; }
        .row-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
        .region-name { font-weight: 600; font-size: .88rem; flex: 1; color: var(--primary-text-color); }
        .alert-badge { font-size: .6rem; font-weight: 700; letter-spacing: .7px; text-transform: uppercase; padding: 3px 9px; border-radius: 20px; white-space: nowrap; }
        .problem-label { font-size: .77rem; font-weight: 500; margin-top: 5px; color: var(--primary-text-color); }
        .detail-desc { font-size: .74rem; margin-top: 5px; color: var(--secondary-text-color); line-height: 1.45; border-top: 1px solid var(--divider-color, rgba(0,0,0,.08)); padding-top: 6px; }
        .detail-dates { display: flex; align-items: center; gap: 5px; font-size: .71rem; margin-top: 5px; color: var(--secondary-text-color); opacity: .85; }
        .arrow { opacity: .5; }
        .card-footer { display: flex; align-items: center; gap: 6px; padding: 8px 16px; font-size: .68rem; color: var(--secondary-text-color); border-top: 1px solid var(--divider-color, rgba(0,0,0,.08)); margin-top: 2px; }
        .row-error { padding: 8px 16px; color: var(--error-color, #b00); font-size: .78rem; }
      </style>

      <div class="card">
        <div class="accent-bar"></div>
        <div class="summary-row">
          <ha-icon class="summary-icon" icon="${wIcon}"></ha-icon>
          <span class="summary-text">${worst === 'GREEN' ? 'All regions normal' : 'Active alerts'}</span>
          <span class="summary-badge">${ALERT_LABELS[worst]}</span>
        </div>
        <div class="regions-list">
          ${ids.map((id) => this._rowHtml(id)).join('')}
        </div>
        <div class="card-footer">🕐 Updated ${lastUpdated}</div>
      </div>`;
  }

  getCardSize() {
    return Math.ceil((this._config?.entities?.length ?? 4) * 1.3) + 2;
  }

  static getStubConfig() {
    return {
      entities: [
        'sensor.costa_norte',
        'sensor.costa_sul',
        'sensor.porto_santo',
        'sensor.regioes_montanhosas',
      ],
    };
  }
}

customElements.define('prociv-madeira-detail-card', ProcivMadeiraDetailCard);

// ── Card picker registration ───────────────────────────────────────────────────

window.customCards = window.customCards || [];
window.customCards.push(
  {
    type: 'prociv-madeira-card',
    name: 'ProCiv Madeira',
    description:
      'Compact alert overview with expandable rows for active alerts.',
    preview: true,
  },
  {
    type: 'prociv-madeira-detail-card',
    name: 'ProCiv Madeira — Detail',
    description:
      'Full detail list with descriptions, problem types, and active date ranges.',
    preview: true,
  },
);
