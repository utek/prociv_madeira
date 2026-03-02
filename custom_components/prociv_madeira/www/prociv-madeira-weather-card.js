/**
 * Prociv Madeira Weather Alerts Card
 * Lovelace custom card for displaying Prociv Madeira weather alerts.
 * Inspired by lovelace-mushroom (https://github.com/piitaya/lovelace-mushroom)
 *
 * Installation: Copy this file to <config>/www/ and add as a Lovelace resource.
 * Usage: Add card type "prociv-madeira-weather-card" in your dashboard.
 *
 * @version 1.6.0
 * @license MIT
 */
(function () {
  'use strict';

  const CARD_VERSION = '1.6.0';
  const CARD_NAME = 'prociv-madeira-weather-card';
  const EDITOR_NAME = 'prociv-madeira-weather-card-editor';

  console.info(
    `%c PROCIV-MADEIRA-WEATHER-CARD %c v${CARD_VERSION} `,
    'color: white; background: #1565C0; font-weight: 700; padding: 2px 6px; border-radius: 3px 0 0 3px;',
    'color: #1565C0; background: white; font-weight: 700; padding: 2px 6px; border-radius: 0 3px 3px 0; border: 1px solid #1565C0;',
  );

  // ---------------------------------------------------------------------------
  // Alert level definitions
  // ---------------------------------------------------------------------------

  const ALERT_LEVELS = {
    green: {
      color: '#1B5E20',
      chipBg: 'rgba(27,94,32,0.10)',
      chipBorder: 'rgba(27,94,32,0.25)',
      icon: 'mdi:check-circle',
      label: 'Normal',
      order: 0,
    },
    yellow: {
      color: '#C8A000',
      chipBg: 'rgba(200,160,0,0.10)',
      chipBorder: 'rgba(200,160,0,0.28)',
      icon: 'mdi:alert',
      label: 'Moderate',
      order: 1,
    },
    orange: {
      color: '#BF360C',
      chipBg: 'rgba(191,54,12,0.10)',
      chipBorder: 'rgba(191,54,12,0.28)',
      icon: 'mdi:alert-circle',
      label: 'High',
      order: 2,
    },
    red: {
      color: '#B71C1C',
      chipBg: 'rgba(183,28,28,0.12)',
      chipBorder: 'rgba(183,28,28,0.30)',
      icon: 'mdi:alert-octagon',
      label: 'Extreme',
      order: 3,
    },
  };

  // ---------------------------------------------------------------------------
  // Problem type → MDI icon  (matches sensor.py PROBLEM_TYPE_TRANSLATIONS keys)
  // ---------------------------------------------------------------------------

  const PROBLEM_TYPE_ICONS = {
    Rain: 'mdi:weather-pouring',
    Precipitation: 'mdi:weather-rainy',
    Wind: 'mdi:weather-windy',
    'Rough Seas': 'mdi:waves',
    Storm: 'mdi:weather-lightning-rainy',
    Thunderstorm: 'mdi:weather-lightning',
    Snow: 'mdi:weather-snowy',
    Ice: 'mdi:snowflake',
    Cold: 'mdi:thermometer-low',
    Heat: 'mdi:thermometer-high',
    Fog: 'mdi:weather-fog',
    Hail: 'mdi:weather-hail',
  };

  function getProblemIcon(problemType) {
    return PROBLEM_TYPE_ICONS[problemType] ?? 'mdi:weather-cloudy-alert';
  }

  function getAlertLevel(state) {
    return ALERT_LEVELS[(state ?? '').toUpperCase()] ?? null;
  }

  function isActiveAlert(state) {
    const s = (state ?? '').toUpperCase();
    return s !== 'green' && s !== 'UNAVAILABLE' && s !== 'UNKNOWN' && s !== '';
  }

  // Check if an alert is currently active (now is between start and end times, or no end time)
  function isCurrentAlert(alert) {
    const now = Date.now();
    const start = alert.start_date
      ? new Date(alert.start_date).getTime()
      : null;
    const end = alert.end_date ? new Date(alert.end_date).getTime() : null;

    // If no start date, assume it's current
    if (!start) return true;
    // If now is before start, it's a future alert
    if (now < start) return false;
    // If there's an end date and now is after it, it's expired
    if (end && now > end) return false;
    // Otherwise it's current
    return true;
  }

  // Get the highest severity level from current alerts
  function getHighestCurrentAlertLevel(alerts) {
    let highest = null;
    for (const alert of alerts) {
      if (!isCurrentAlert(alert)) continue;
      const level = getAlertLevel(alert.alert_type);
      if (level && (!highest || level.order > highest.order)) {
        highest = level;
      }
    }
    return highest;
  }

  // ---------------------------------------------------------------------------
  // Date helpers
  // ---------------------------------------------------------------------------

  function formatDate(isoStr) {
    if (!isoStr) return null;
    try {
      return new Date(isoStr).toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
    } catch {
      return null;
    }
  }

  function formatDateRange(startStr, endStr) {
    const start = formatDate(startStr);
    const end = formatDate(endStr);
    if (start && end) return `${start} – ${end}`;
    if (end) return `Until ${end}`;
    if (start) return `From ${start}`;
    return null;
  }

  function relativeTime(dateStr) {
    if (!dateStr) return null;
    const delta = Math.round((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (delta < 60) return 'just now';
    if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
    if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
    return `${Math.floor(delta / 86400)}d ago`;
  }

  // Accepts both legacy string[] and new {entity, name?}[] formats.
  function normalizeEntities(entities) {
    if (!entities || !entities.length) return [];
    return entities.map((e) => (typeof e === 'string' ? { entity: e } : e));
  }

  // Sanitize strings before interpolating into HTML to prevent XSS.
  const _escapeEl = document.createElement('div');
  function escapeHtml(str) {
    _escapeEl.textContent = str ?? '';
    return _escapeEl.innerHTML;
  }

  // ---------------------------------------------------------------------------
  // Default config
  // ---------------------------------------------------------------------------

  const DEFAULT_CONFIG = {
    title: 'Madeira Weather Alerts',
    entity_prefix: 'sensor.prociv_madeira_alert_',
    entities: [],
    columns: 2,
    show_all: false,
    show_icon: true,
    severity_order: true,
    show_header: true,
    show_last_updated: true,
    no_alerts_message: 'No weather alerts active',
    // Per-alert field visibility
    show_problem_type: true,
    show_dates: true,
  };

  // ---------------------------------------------------------------------------
  // Card Editor
  // ---------------------------------------------------------------------------

  // Injected into the editor element (no shadow DOM).
  const EDITOR_CSS = `
    .entity-section { padding: 4px 0 0; }

    .section-title {
      font-size: 11px;
      font-weight: 700;
      color: var(--secondary-text-color);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      padding: 12px 16px 4px;
    }

    .section-hint {
      font-size: 11px;
      color: var(--secondary-text-color);
      padding: 0 16px 8px;
      line-height: 1.5;
    }

    .entity-row {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 16px;
    }

    .entity-row ha-entity-picker { flex: 1; }

    .name-input {
      width: 140px;
      height: 40px;
      padding: 0 10px;
      border: 1px solid var(--divider-color, #ccc);
      border-radius: 4px;
      background: var(--input-fill-color, var(--secondary-background-color, #f5f5f5));
      color: var(--primary-text-color);
      font-size: 13px;
      box-sizing: border-box;
    }

    .name-input:focus {
      outline: none;
      border-color: var(--primary-color);
    }

    .delete-btn {
      flex-shrink: 0;
      background: none;
      border: none;
      cursor: pointer;
      color: var(--secondary-text-color);
      padding: 6px;
      border-radius: 50%;
      line-height: 1;
      font-size: 14px;
    }

    .delete-btn:hover { color: var(--error-color, #b71c1c); }

    .add-btn {
      display: block;
      margin: 6px 16px 12px;
      padding: 7px 14px;
      width: calc(100% - 32px);
      border: 1px dashed var(--divider-color);
      border-radius: 6px;
      background: none;
      cursor: pointer;
      font-size: 12px;
      font-weight: 600;
      color: var(--primary-color);
      text-align: center;
      box-sizing: border-box;
    }

    .add-btn:hover { background: rgba(var(--rgb-primary-color, 33,150,243), 0.05); }
  `;

  const EDITOR_SCHEMA = [
    // ── General ───────────────────────────────────────────────────────────────
    {
      name: 'title',
      label: 'Card Title',
      selector: { text: {} },
    },
    {
      name: 'entity_prefix',
      label: 'Entity Prefix (e.g. sensor.prociv_madeira_weather_)',
      selector: { text: {} },
    },
    // ── Layout ────────────────────────────────────────────────────────────────
    {
      type: 'grid',
      name: '',
      schema: [
        {
          name: 'columns',
          label: 'Grid Columns',
          selector: { number: { min: 1, max: 4, mode: 'box', step: 1 } },
        },
        {
          name: 'show_all',
          label: 'Show green (clear) regions',
          selector: { boolean: {} },
        },
      ],
    },
    // ── Card chrome ───────────────────────────────────────────────────────────
    {
      type: 'grid',
      name: '',
      schema: [
        {
          name: 'show_header',
          label: 'Show Card Header',
          selector: { boolean: {} },
        },
        {
          name: 'show_last_updated',
          label: 'Show Last Updated',
          selector: { boolean: {} },
        },
      ],
    },
    // ── Sensor fields ─────────────────────────────────────────────────────────
    {
      type: 'grid',
      name: '',
      schema: [
        {
          name: 'show_icon',
          label: 'Show Alert Icon',
          selector: { boolean: {} },
        },
        {
          name: 'severity_order',
          label: 'Sort by Severity',
          selector: { boolean: {} },
        },
      ],
    },
    {
      type: 'grid',
      name: '',
      schema: [
        {
          name: 'show_problem_type',
          label: 'Show Alert Type',
          selector: { boolean: {} },
        },
      ],
    },
    {
      type: 'grid',
      name: '',
      schema: [
        {
          name: 'show_dates',
          label: 'Show Active Dates',
          selector: { boolean: {} },
        },
      ],
    },
    // ── Messages ──────────────────────────────────────────────────────────────
    {
      name: 'no_alerts_message',
      label: 'Message when no alerts',
      selector: { text: {} },
    },
  ];

  class ProcivMadeiraWeatherCardEditor extends HTMLElement {
    constructor() {
      super();
      this._config = {};
      this._hass = null;
      this._form = null;
      this._entitySection = null;
    }

    setConfig(config) {
      this._config = {
        ...DEFAULT_CONFIG,
        ...config,
        entities: normalizeEntities(config.entities),
      };
      this._syncForm();
      this._rebuildEntityList();
    }

    set hass(hass) {
      this._hass = hass;
      if (this._form) this._form.hass = hass;
      // Propagate hass and refresh the allowed-entity list on every live picker
      const regionIds = this._regionEntityIds();
      this.querySelectorAll('ha-entity-picker').forEach((p) => {
        p.hass = hass;
        p.includeEntities = regionIds;
      });
    }

    connectedCallback() {
      if (!this._form) this._buildLayout();
      this._syncForm();
      this._rebuildEntityList();
    }

    // ── Layout ──────────────────────────────────────────────────────────────

    _buildLayout() {
      this.innerHTML = '';

      // General settings via ha-form
      const form = document.createElement('ha-form');
      form.schema = EDITOR_SCHEMA;
      form.computeLabel = (s) => s.label ?? s.name;
      form.addEventListener('value-changed', (e) => {
        this._config = { ...this._config, ...e.detail.value };
        this._fire();
      });
      if (this._hass) form.hass = this._hass;
      this._form = form;
      this.appendChild(form);

      // Custom entity list (entity + optional name per row)
      const section = document.createElement('div');
      section.className = 'entity-section';
      this._entitySection = section;
      this.appendChild(section);

      // Scoped styles
      const style = document.createElement('style');
      style.textContent = EDITOR_CSS;
      this.appendChild(style);
    }

    // ── Entity list ──────────────────────────────────────────────────────────

    _rebuildEntityList() {
      if (!this._entitySection) return;
      const entities = this._config.entities ?? [];

      this._entitySection.innerHTML = `
        <div class="section-title">Entities</div>
        <div class="section-hint">
          When left empty the prefix above is used to auto-discover sensors.<br>
          <strong>Name</strong> overrides the region label from the sensor attribute.
        </div>
      `;

      entities.forEach((item, idx) => {
        this._entitySection.appendChild(this._buildRow(item, idx));
      });

      const addBtn = document.createElement('button');
      addBtn.className = 'add-btn';
      addBtn.textContent = '+ Add Entity';
      addBtn.addEventListener('click', () => {
        this._config.entities.push({ entity: '' });
        this._rebuildEntityList();
        this._fire();
      });
      this._entitySection.appendChild(addBtn);
    }

    _buildRow(item, idx) {
      const row = document.createElement('div');
      row.className = 'entity-row';

      // Entity picker — limited to region sensors only (those with region_code).
      // This keeps worst_alert, last_fetch, and binary sensors out of the list.
      const picker = document.createElement('ha-entity-picker');
      if (this._hass) {
        picker.hass = this._hass;
        picker.includeEntities = this._regionEntityIds();
      }
      picker.value = item.entity ?? '';
      picker.allowCustomEntity = false;
      picker.addEventListener('value-changed', (e) => {
        this._config.entities[idx] = {
          ...this._config.entities[idx],
          entity: e.detail.value,
        };
        this._fire();
      });

      // Name override input
      const nameInput = document.createElement('input');
      nameInput.type = 'text';
      nameInput.className = 'name-input';
      nameInput.placeholder = 'Name (optional)';
      nameInput.value = item.name ?? '';
      nameInput.addEventListener('change', (e) => {
        const val = e.target.value.trim();
        this._config.entities[idx] = {
          ...this._config.entities[idx],
          ...(val ? { name: val } : {}),
        };
        if (!val) delete this._config.entities[idx].name;
        this._fire();
      });

      // Delete button
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'delete-btn';
      deleteBtn.title = 'Remove';
      deleteBtn.textContent = '✕';
      deleteBtn.addEventListener('click', () => {
        this._config.entities.splice(idx, 1);
        this._rebuildEntityList();
        this._fire();
      });

      row.appendChild(picker);
      row.appendChild(nameInput);
      row.appendChild(deleteBtn);
      return row;
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    // Returns entity IDs of all region sensors (have region_code attribute).
    _regionEntityIds() {
      if (!this._hass) return [];
      return Object.entries(this._hass.states)
        .filter(([, s]) => s.attributes?.region_code != null)
        .map(([id]) => id);
    }

    _syncForm() {
      if (!this._form) return;
      this._form.data = this._config;
    }

    _fire() {
      this.dispatchEvent(
        new CustomEvent('config-changed', { detail: { config: this._config } }),
      );
    }
  }

  // ---------------------------------------------------------------------------
  // Main Card
  // ---------------------------------------------------------------------------

  class ProcivMadeiraWeatherCard extends HTMLElement {
    constructor() {
      super();
      this._config = null;
      this._hass = null;
      this._cardExpanded = false;
      this._collapsedRegions = new Set();
      this._expandedAlerts = new Set();
      this._tickTimer = null;
      this.attachShadow({ mode: 'open' });
    }

    connectedCallback() {
      this._startTick();
    }

    disconnectedCallback() {
      if (this._tickTimer) {
        clearInterval(this._tickTimer);
        this._tickTimer = null;
      }
    }

    // ── HA Card API ────────────────────────────────────────────────────────────

    static getStubConfig() {
      return { ...DEFAULT_CONFIG };
    }

    static getConfigElement() {
      return document.createElement(EDITOR_NAME);
    }

    setConfig(config) {
      const hasEntities = config.entities && config.entities.length > 0;
      const hasPrefix = !!config.entity_prefix;
      if (!hasEntities && !hasPrefix) {
        throw new Error(
          'Prociv Madeira Weather Card: provide "entity_prefix" or "entities".',
        );
      }
      this._config = { ...DEFAULT_CONFIG, ...config };
      if (this._hass) this._render();
    }

    set hass(hass) {
      const prev = this._hass;
      this._hass = hass;
      if (this._statesChanged(prev, hass)) this._render();
    }

    // Only re-render when relevant entity states have actually changed.
    _statesChanged(prev, next) {
      if (!prev || !this._config) return true;
      const { entities, entity_prefix } = this._config;
      const ids =
        entities && entities.length > 0
          ? normalizeEntities(entities)
              .filter((e) => e.entity)
              .map((e) => e.entity)
          : Object.keys(next.states).filter((id) =>
              id.startsWith(entity_prefix),
            );
      for (const id of ids) {
        if (prev.states[id] !== next.states[id]) return true;
      }
      // Also check the last_fetch sensor
      const base = (entity_prefix ?? '').replace(/alert_$/, '');
      const fetchId = `${base}last_fetch`;
      if (prev.states[fetchId] !== next.states[fetchId]) return true;
      return false;
    }

    getCardSize() {
      return 3;
    }

    // ── Entity resolution ──────────────────────────────────────────────────────

    _resolveEntities() {
      if (!this._hass) return [];
      const { entities, entity_prefix } = this._config;

      if (entities && entities.length > 0) {
        // Explicit list (supports both legacy strings and {entity, name} objects).
        // Only region sensors (those carrying region_code) are included.
        return normalizeEntities(entities)
          .filter((item) => item.entity)
          .map((item) => ({
            id: item.entity,
            stateObj: this._hass.states[item.entity],
            customName: item.name ?? null,
          }))
          .filter((e) => e.stateObj?.attributes?.region_code != null);
      }

      // Prefix scan — exclude worst_alert, last_fetch, binary sensors, etc.
      return Object.entries(this._hass.states)
        .filter(
          ([id, stateObj]) =>
            id.startsWith(entity_prefix) &&
            stateObj.attributes?.region_code != null,
        )
        .map(([id, stateObj]) => ({ id, stateObj, customName: null }));
    }

    // ── Render ─────────────────────────────────────────────────────────────────

    _render() {
      if (!this._config || !this._hass) return;

      // Snapshot which regions/alerts the user has collapsed before wiping the DOM.
      this.shadowRoot.querySelectorAll('details[data-region]').forEach((d) => {
        if (d.open) this._collapsedRegions.delete(d.dataset.region);
        else this._collapsedRegions.add(d.dataset.region);
      });
      this.shadowRoot.querySelectorAll('details[data-alert]').forEach((d) => {
        if (d.open) this._expandedAlerts.add(d.dataset.alert);
        else this._expandedAlerts.delete(d.dataset.alert);
      });

      const cfg = this._config;
      let entities = this._resolveEntities();

      // Filter out green unless show_all is on
      // Also filter out regions where all alerts start in the future (no current alerts)
      if (!cfg.show_all) {
        entities = entities.filter((e) => {
          const alerts = e.stateObj.attributes?.alerts ?? [];
          // Keep if there are current alerts OR if there are any alerts (show future too)
          // If there are no current alerts but there are future alerts, we still show them
          // The coloring will be handled in _regionSectionHtml
          return alerts.length > 0;
        });
      }

      // Sort worst-first when requested
      if (cfg.severity_order) {
        entities.sort((a, b) => {
          const la = getAlertLevel(a.stateObj.state);
          const lb = getAlertLevel(b.stateObj.state);
          return (lb?.order ?? -1) - (la?.order ?? -1);
        });
      }

      // Count every individual alert by severity level across all regions.
      const alertsByLevel = { red: 0, orange: 0, yellow: 0 };
      for (const { stateObj } of entities) {
        for (const a of stateObj.attributes?.alerts ?? []) {
          const t = (a.alert_type ?? '').toUpperCase();
          if (t in alertsByLevel) alertsByLevel[t]++;
        }
      }

      const hasVisible = entities.length > 0;
      const cols = Math.max(1, Math.min(4, cfg.columns ?? 2));

      // Card body is hidden until the user expands it (unless there is no header to click).
      const showContent = this._cardExpanded || cfg.show_header === false;

      this.shadowRoot.innerHTML = `
        <style>${this._styles(cols)}</style>
        <ha-card>
          ${cfg.show_header !== false ? this._headerHtml(cfg, alertsByLevel) : ''}
          ${
            showContent
              ? `
          <div class="card-content">
            ${hasVisible ? this._alertsHtml(entities, cfg) : this._noAlertsHtml(cfg)}
          </div>`
              : ''
          }
        </ha-card>
      `;

      // Toggle card expand/collapse when the header is clicked.
      if (cfg.show_header !== false) {
        this.shadowRoot
          .querySelector('.card-header')
          ?.addEventListener('click', () => {
            this._cardExpanded = !this._cardExpanded;
            this._render();
          });
      }
    }

    // ── Header ─────────────────────────────────────────────────────────────────

    _headerHtml(cfg, alertsByLevel) {
      const totalActive =
        alertsByLevel.red + alertsByLevel.orange + alertsByLevel.yellow;
      const hasAlerts = totalActive > 0;

      const statusHtml = hasAlerts
        ? [
            { key: 'red', level: ALERT_LEVELS.red },
            { key: 'orange', level: ALERT_LEVELS.orange },
            { key: 'yellow', level: ALERT_LEVELS.yellow },
          ]
            .filter(({ key }) => alertsByLevel[key] > 0)
            .map(
              ({ key, level }) => `
              <div class="level-chip" style="background:${level.chipBg};border-color:${level.chipBorder};color:${level.color};">
                <ha-icon icon="${level.icon}" style="--mdc-icon-size:12px;"></ha-icon>
                <span>${alertsByLevel[key]}</span>
              </div>`,
            )
            .join('')
        : `<div class="badge badge--clear">
             <ha-icon icon="mdi:check-circle"></ha-icon>
             <span>All Clear</span>
           </div>`;

      const chevronCls = this._cardExpanded
        ? 'card-chevron card-chevron--open'
        : 'card-chevron';

      return `
        <div class="card-header">
          <div class="header-icon">
            <ha-icon icon="mdi:weather-cloudy-alert"></ha-icon>
          </div>
          <span class="header-title">${escapeHtml(cfg.title || DEFAULT_CONFIG.title)}</span>
          <div class="header-status">${statusHtml}</div>
          <ha-icon icon="mdi:chevron-down" class="${chevronCls}"></ha-icon>
        </div>
        ${this._cardExpanded ? '<div class="divider"></div>' : ''}
      `;
    }

    // ── No-alerts state ────────────────────────────────────────────────────────

    _noAlertsHtml(cfg) {
      return `
        <div class="no-alerts">
          <ha-icon icon="mdi:check-circle-outline" class="no-alerts-icon"></ha-icon>
          <span class="no-alerts-text">${escapeHtml(cfg.no_alerts_message || DEFAULT_CONFIG.no_alerts_message)}</span>
        </div>
      `;
    }

    // ── Regions list ───────────────────────────────────────────────────────────

    _alertsHtml(entities, cfg) {
      const sections = entities
        .map((e) => this._regionSectionHtml(e, cfg))
        .join('');
      const updatedAt = cfg.show_last_updated ? this._updatedAtHtml() : '';
      return `<div class="regions-list">${sections}</div>${updatedAt}`;
    }

    _regionSectionHtml({ id, stateObj, customName }, cfg) {
      const attrs = stateObj.attributes ?? {};
      const alerts = attrs.alerts ?? [];

      // customName (set in the editor) > sensor region attribute > entity id
      const regionName = customName ?? attrs.region ?? id;

      // Split alerts into current and future
      const currentAlerts = alerts.filter((a) => isCurrentAlert(a));
      const futureAlerts = alerts.filter((a) => !isCurrentAlert(a));

      // Determine region color/status based on highest current alert level
      // If there are no current alerts, show green/Normal
      const highestCurrentLevel = getHighestCurrentAlertLevel(alerts);
      const hasCurrentAlerts = currentAlerts.length > 0;
      const level = hasCurrentAlerts ? highestCurrentLevel : ALERT_LEVELS.green;
      const color = level?.color ?? 'var(--secondary-text-color)';
      const status = hasCurrentAlerts
        ? (level?.label ?? stateObj.state)
        : 'Normal';
      const headerIcon =
        cfg.show_icon !== false
          ? (level?.icon ?? 'mdi:weather-cloudy-alert')
          : null;

      const iconHtml = headerIcon
        ? `<ha-icon icon="${headerIcon}" style="color:${color};--mdc-icon-size:16px;" class="region-icon"></ha-icon>`
        : '';

      // Sort current and future alerts by start date
      const sortByDate = (a, b) => {
        if (!a.start_date) return 1;
        if (!b.start_date) return -1;
        return a.start_date < b.start_date
          ? -1
          : a.start_date > b.start_date
            ? 1
            : 0;
      };
      currentAlerts.sort(sortByDate);
      futureAlerts.sort(sortByDate);

      // Render current alerts directly under region name (always visible)
      const currentAlertsHtml =
        currentAlerts.length > 0
          ? currentAlerts
              .map((a) => this._currentAlertHtml(a, cfg, color))
              .join('')
          : '';

      // Render future alerts in collapsible section
      const futurePanelsHtml =
        futureAlerts.length > 0
          ? futureAlerts.map((a) => this._alertPanelHtml(a, cfg)).join('')
          : '';

      const isOpen = !this._collapsedRegions.has(id);
      const hasFutureAlerts = futureAlerts.length > 0;

      return `
        <details class="region-section" data-region="${id}"${isOpen ? ' open' : ''}>
          <summary class="region-header">
            ${iconHtml}
            <span class="region-name" style="color:${color};">${escapeHtml(regionName)}</span>
            <span class="region-badge" style="color:${color};">${status}</span>
            <ha-icon icon="mdi:chevron-down" class="chevron-icon" style="color:${color};--mdc-icon-size:14px;"></ha-icon>
          </summary>
          ${currentAlertsHtml ? `<div class="current-alerts">${currentAlertsHtml}</div>` : ''}
          ${
            hasFutureAlerts
              ? `
          <details class="future-alerts-section">
            <summary class="future-alerts-header">
              <span>Future Alerts (${futureAlerts.length})</span>
              <ha-icon icon="mdi:chevron-down" class="future-alerts-chevron" style="--mdc-icon-size:12px;"></ha-icon>
            </summary>
            <div class="alert-panels">
              ${futurePanelsHtml}
            </div>
          </details>`
              : ''
          }
        </details>
      `;
    }

    // Render a current alert using the same panel layout as future alerts.
    _currentAlertHtml(alert, cfg, regionColor) {
      const level = getAlertLevel(alert.alert_type);
      const color =
        level?.color ?? regionColor ?? 'var(--secondary-text-color)';
      const bg = level?.chipBg ?? 'rgba(0,0,0,0.05)';
      const border = level?.chipBorder ?? 'rgba(0,0,0,0.10)';
      const icon = alert.problem_type
        ? getProblemIcon(alert.problem_type)
        : (level?.icon ?? 'mdi:weather-cloudy-alert');

      const typeHtml =
        cfg.show_problem_type !== false && alert.problem_type
          ? `<span class="panel-type" style="color:${color};">${escapeHtml(alert.problem_type)}</span>`
          : '';

      const levelBadge = `<span class="panel-level-badge" style="color:${color};">${escapeHtml(level?.label ?? alert.alert_type)}</span>`;

      const dateRange =
        cfg.show_dates !== false
          ? formatDateRange(alert.start_date, alert.end_date)
          : null;
      const dateHtml = dateRange
        ? `<div class="panel-dates" style="color:${color};">${escapeHtml(dateRange)}</div>`
        : '';

      const descHtml = alert.description
        ? `<div class="panel-description" style="color:${color};">${escapeHtml(alert.description)}</div>`
        : '';

      const iconHtml = `<ha-icon icon="${escapeHtml(icon)}" style="color:${color};--mdc-icon-size:18px;" class="panel-icon"></ha-icon>`;
      const bodyHtml = `
        <div class="panel-body">
          <div class="panel-top">${typeHtml}${typeHtml ? '<span class="panel-sep"> · </span>' : ''}${levelBadge}</div>
          ${dateHtml}
        </div>`;

      // No description — static panel.
      if (!descHtml) {
        return `
          <div class="alert-panel" style="background:${bg};border-color:${border};">
            ${iconHtml}
            ${bodyHtml}
          </div>
        `;
      }

      // Has description — collapsible panel.
      const alertKey = `current_${alert.region_code}__${alert.start_date || alert.problem_type || ''}`;
      const isOpen = this._expandedAlerts.has(alertKey);
      return `
        <details class="alert-panel" data-alert="${escapeHtml(alertKey)}"${isOpen ? ' open' : ''} style="background:${bg};border-color:${border};">
          <summary class="panel-summary">
            ${iconHtml}
            ${bodyHtml}
            <ha-icon icon="mdi:chevron-down" class="alert-chevron" style="color:${color};--mdc-icon-size:12px;"></ha-icon>
          </summary>
          <div class="panel-details">
            ${descHtml}
          </div>
        </details>
      `;
    }

    _alertPanelHtml(alert, cfg) {
      const level = getAlertLevel(alert.alert_type);
      const color = level?.color ?? 'var(--secondary-text-color)';
      const bg = level?.chipBg ?? 'rgba(0,0,0,0.05)';
      const border = level?.chipBorder ?? 'rgba(0,0,0,0.10)';
      const icon = alert.problem_type
        ? getProblemIcon(alert.problem_type)
        : (level?.icon ?? 'mdi:weather-cloudy-alert');

      const typeHtml =
        cfg.show_problem_type !== false && alert.problem_type
          ? `<span class="panel-type" style="color:${color};">${escapeHtml(alert.problem_type)}</span>`
          : '';

      const levelBadge = `<span class="panel-level-badge" style="color:${color};">${escapeHtml(level?.label ?? alert.alert_type)}</span>`;

      const dateRange =
        cfg.show_dates !== false
          ? formatDateRange(alert.start_date, alert.end_date)
          : null;
      const dateHtml = dateRange
        ? `<div class="panel-dates" style="color:${color};">${escapeHtml(dateRange)}</div>`
        : '';

      const descHtml = alert.description
        ? `<div class="panel-description" style="color:${color};">${escapeHtml(alert.description)}</div>`
        : '';

      // Dates are always visible; only the description is toggled.
      const iconHtml = `<ha-icon icon="${escapeHtml(icon)}" style="color:${color};--mdc-icon-size:18px;" class="panel-icon"></ha-icon>`;
      const bodyHtml = `
        <div class="panel-body">
          <div class="panel-top">${typeHtml}${typeHtml ? '<span class="panel-sep"> · </span>' : ''}${levelBadge}</div>
          ${dateHtml}
        </div>`;

      // No description to toggle — render a plain static panel.
      if (!descHtml) {
        return `
          <div class="alert-panel" style="background:${bg};border-color:${border};">
            ${iconHtml}
            ${bodyHtml}
          </div>
        `;
      }

      // Has description — render a collapsible <details> panel.
      const alertKey = `${alert.region_code}__${alert.start_date || alert.problem_type || ''}`;
      const isOpen = this._expandedAlerts.has(alertKey);
      return `
        <details class="alert-panel" data-alert="${escapeHtml(alertKey)}"${isOpen ? ' open' : ''} style="background:${bg};border-color:${border};">
          <summary class="panel-summary">
            ${iconHtml}
            ${bodyHtml}
            <ha-icon icon="mdi:chevron-down" class="alert-chevron" style="color:${color};--mdc-icon-size:12px;"></ha-icon>
          </summary>
          <div class="panel-details">
            ${descHtml}
          </div>
        </details>
      `;
    }

    // ── Last updated ───────────────────────────────────────────────────────────

    _updatedAtHtml() {
      // Derive the last-fetch sensor ID from entity_prefix:
      // "sensor.prociv_madeira_alert_" → "sensor.prociv_madeira_last_fetch"
      const prefix = this._config?.entity_prefix ?? '';
      const base = prefix.replace(/alert_$/, '');
      const sensor = this._hass?.states[`${base}last_fetch`];
      const ts = sensor?.state;
      if (!ts || ts === 'unavailable' || ts === 'unknown') return '';
      const rel = relativeTime(ts);
      return rel
        ? `<div class="updated-at" data-ts="${ts}">Updated ${rel}</div>`
        : '';
    }

    // Starts the 30-second relative-time ticker (idempotent — safe to call repeatedly).
    _startTick() {
      if (this._tickTimer) return;
      this._tickTimer = setInterval(() => this._tickUpdatedAt(), 30000);
    }

    // Updates only the "Updated X ago" text without a full re-render.
    _tickUpdatedAt() {
      const el = this.shadowRoot?.querySelector('.updated-at[data-ts]');
      if (!el) return;
      const rel = relativeTime(el.dataset.ts);
      if (rel) el.textContent = `Updated ${rel}`;
    }

    // ── Styles ─────────────────────────────────────────────────────────────────

    _styles(cols) {
      return `
        :host { display: block; }

        ha-card { overflow: hidden; height: 100%; }

        /* ── Header ─────────────────────────────── */
        .card-header {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 14px 16px 10px;
          cursor: pointer;
          user-select: none;
        }

        .card-chevron {
          flex-shrink: 0;
          color: var(--secondary-text-color);
          --mdc-icon-size: 18px;
          transition: transform 0.2s ease;
        }

        .card-chevron--open { transform: rotate(180deg); }

        .header-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 38px;
          height: 38px;
          border-radius: 50%;
          background: rgba(21,101,192,0.12);
          flex-shrink: 0;
        }

        .header-icon ha-icon {
          --mdc-icon-size: 20px;
          color: #1565C0;
        }

        .header-title {
          flex: 1;
          font-size: 14px;
          font-weight: 600;
          color: var(--primary-text-color);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          letter-spacing: 0.01em;
        }

        /* ── Header status area ─────────────────── */
        .header-status {
          display: flex;
          align-items: center;
          gap: 4px;
          flex-shrink: 0;
        }

        /* All-clear single badge */
        .badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 3px 10px 3px 6px;
          border-radius: 12px;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.04em;
          white-space: nowrap;
        }

        .badge ha-icon { --mdc-icon-size: 13px; }

        .badge--clear { background: rgba(27,94,32,0.12); color: #1B5E20; }

        /* Per-level alert count chips */
        .level-chip {
          display: inline-flex;
          align-items: center;
          gap: 3px;
          padding: 3px 8px 3px 5px;
          border-radius: 12px;
          border: 1px solid transparent;
          font-size: 11px;
          font-weight: 700;
          white-space: nowrap;
        }

        /* ── Divider ────────────────────────────── */
        .divider {
          height: 1px;
          background: var(--divider-color, rgba(0,0,0,0.08));
        }

        /* ── Card content ───────────────────────── */
        .card-content { padding: 12px 14px 14px; }

        /* ── No alerts state ────────────────────── */
        .no-alerts {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 28px 16px;
          gap: 8px;
        }

        .no-alerts-icon {
          --mdc-icon-size: 40px;
          color: #2E7D32;
          opacity: 0.85;
        }

        .no-alerts-text {
          font-size: 13px;
          font-weight: 500;
          color: #2E7D32;
          text-align: center;
        }

        /* ── Regions list (grid via columns config) */
        .regions-list {
          display: grid;
          grid-template-columns: repeat(${cols}, 1fr);
          gap: 14px;
        }

        /* ── Region section ─────────────────────── */
        .region-section {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .region-header {
          display: flex;
          align-items: center;
          gap: 7px;
          padding: 0 2px;
          cursor: pointer;
          user-select: none;
          list-style: none;
        }

        .region-header::-webkit-details-marker { display: none; }

        .region-icon { flex-shrink: 0; }

        .chevron-icon {
          flex-shrink: 0;
          margin-left: auto;
          transition: transform 0.2s ease;
        }

        .region-section[open] .chevron-icon {
          transform: rotate(180deg);
        }

        .region-name {
          flex: 1;
          font-size: 13px;
          font-weight: 700;
          letter-spacing: 0.01em;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .region-badge {
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          opacity: 0.80;
          flex-shrink: 0;
        }

        /* ── Alert panels ───────────────────────── */
        .alert-panels {
          display: flex;
          flex-direction: column;
          gap: 5px;
          padding-top: 4px;
        }

        .alert-panel {
          border-radius: 8px;
          border: 1px solid transparent;
          border-left-width: 3px;
        }

        /* Static panel (no collapsible details) */
        .alert-panel:not(details) {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 9px 12px;
        }

        /* Collapsible panel summary row */
        .panel-summary {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 9px 12px;
          list-style: none;
          cursor: pointer;
          user-select: none;
        }

        .panel-summary::-webkit-details-marker { display: none; }

        .alert-chevron {
          flex-shrink: 0;
          margin-left: auto;
          transition: transform 0.2s ease;
        }

        .alert-panel[open] .alert-chevron { transform: rotate(180deg); }

        /* Collapsible content */
        .panel-details {
          padding: 0 12px 9px calc(12px + 18px + 10px);
          display: flex;
          flex-direction: column;
          gap: 3px;
        }

        .panel-icon { flex-shrink: 0; }

        .panel-body {
          flex: 1;
          min-width: 0;
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .panel-top {
          display: flex;
          flex-wrap: wrap;
          align-items: baseline;
          gap: 2px;
          line-height: 1.4;
        }

        .panel-type {
          font-size: 12px;
          font-weight: 600;
        }

        .panel-sep {
          font-size: 10px;
          opacity: 0.45;
        }

        .panel-level-badge {
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.05em;
          text-transform: uppercase;
          opacity: 0.75;
        }

        .panel-dates {
          font-size: 10px;
          opacity: 0.75;
          line-height: 1.3;
        }

        .panel-description {
          font-size: 10px;
          opacity: 0.80;
          line-height: 1.4;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }

        .no-region-alerts {
          font-size: 11px;
          color: var(--secondary-text-color);
          opacity: 0.55;
          padding: 3px 0;
        }

        /* ── Current alerts (always visible) ─────── */
        .current-alerts {
          display: flex;
          flex-direction: column;
          gap: 5px;
          padding: 6px 0 6px 6px;
        }

        /* ── Future alerts collapsible ──────────────── */
        .future-alerts-section {
          margin-top: 4px;
          padding-left: 6px;
        }

        .future-alerts-header {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 10px;
          font-weight: 700;
          color: var(--secondary-text-color);
          text-transform: uppercase;
          letter-spacing: 0.08em;
          padding: 6px 0 4px;
          opacity: 0.6;
          cursor: pointer;
          user-select: none;
          list-style: none;
        }

        .future-alerts-header::-webkit-details-marker { display: none; }

        .future-alerts-chevron {
          color: var(--secondary-text-color);
          opacity: 0.6;
          transition: transform 0.2s ease;
        }

        .future-alerts-section[open] .future-alerts-chevron {
          transform: rotate(180deg);
        }

        /* ── Last updated ───────────────────────── */
        .updated-at {
          margin-top: 10px;
          text-align: right;
          font-size: 10px;
          color: var(--secondary-text-color);
          opacity: 0.65;
        }
      `;
    }
  }

  // ---------------------------------------------------------------------------
  // Registration
  // ---------------------------------------------------------------------------

  if (!customElements.get(EDITOR_NAME)) {
    customElements.define(EDITOR_NAME, ProcivMadeiraWeatherCardEditor);
  }

  if (!customElements.get(CARD_NAME)) {
    customElements.define(CARD_NAME, ProcivMadeiraWeatherCard);
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.find((c) => c.type === CARD_NAME)) {
    window.customCards.push({
      type: CARD_NAME,
      name: 'Prociv Madeira Weather Card',
      description:
        'Displays Prociv Madeira regional weather alerts. Highlights active warnings and shows a clear status when all regions are safe.',
      preview: true,
    });
  }
})();
