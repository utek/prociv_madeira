// Tests for the bundled Lovelace card.
// Run with: node --test "tests/card/*.test.mjs"
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const CARD_SOURCE = readFileSync(
  new URL(
    '../../custom_components/prociv_madeira/www/prociv-madeira-weather-card.js',
    import.meta.url,
  ),
  'utf8',
);
const CARD_NAME = 'prociv-madeira-weather-card';
const EDITOR_NAME = `${CARD_NAME}-editor`;
const INJECTION = `"><img src=x onerror=alert(1)>'`;
const EN_LABELS = {
  green: 'Normal',
  yellow: 'Moderate',
  orange: 'High',
  red: 'Extreme',
  unavailable: 'Unavailable',
};
const PT_LABELS = {
  green: 'Normal',
  yellow: 'Moderado',
  orange: 'Elevado',
  red: 'Extremo',
  unavailable: 'Indisponível',
};
const REGIONS = [
  { code: 'CN', key: 'north_coast', name: 'North Coast' },
  { code: 'CS', key: 'south_coast', name: 'South Coast' },
  { code: 'PS', key: 'porto_santo', name: 'Porto Santo' },
  { code: 'RM', key: 'mountainous_regions', name: 'Mountainous Regions' },
];
const SOUTH_COAST = 'sensor.prociv_madeira_weather_alerts_south_coast';
const LAST_FETCH = 'sensor.prociv_madeira_weather_alerts_last_fetch';

// Objects created inside the card's context have foreign prototypes, so
// compare plain JSON copies.
const plain = (value) => JSON.parse(JSON.stringify(value));

function fakeElement(tagName) {
  return {
    tagName,
    style: {},
    children: [],
    listeners: {},
    innerHTML: '',
    appendChild(child) {
      this.children.push(child);
    },
    addEventListener(type, listener) {
      this.listeners[type] = listener;
    },
  };
}

// A fresh V8 context with just enough browser API to run the card script.
// The shadow root counts how often its HTML is replaced, and its query
// methods can be swapped per test.
function createContext() {
  const definitions = new Map();
  const context = {
    warnings: [],
    customElements: {
      get: (name) => definitions.get(name),
      define: (name, element) => definitions.set(name, element),
    },
    document: { createElement: fakeElement },
    setInterval: () => 0,
    clearInterval: () => {},
  };
  context.console = {
    info() {},
    warn: (...args) => context.warnings.push(args.join(' ')),
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(
    `
    globalThis.HTMLElement = class {
      attachShadow() {
        this.shadowRoot = {
          renders: 0,
          html: '',
          get innerHTML() { return this.html; },
          set innerHTML(value) { this.html = value; this.renders += 1; },
          querySelectorAll: () => [],
          querySelector: () => null,
        };
        return this.shadowRoot;
      }
      dispatchEvent(event) { (this.dispatched ??= []).push(event); }
      querySelectorAll() { return []; }
      appendChild() {}
    };
    globalThis.CustomEvent = class {
      constructor(type, init) { this.type = type; this.detail = init?.detail; }
    };
    `,
    context,
  );
  return context;
}

function loadCard(source = CARD_SOURCE, context = createContext()) {
  vm.runInContext(source, context);
  return context;
}

const hoursFromNow = (hours) =>
  new Date(Date.now() + hours * 3600e3).toISOString();

function warning(
  regionCode,
  level,
  problemType,
  startHours,
  endHours,
  description = null,
) {
  return {
    region_code: regionCode,
    alert_type: level,
    problem_type: problemType,
    description,
    start_date: hoursFromNow(startHours),
    end_date: hoursFromNow(endHours),
  };
}

// hass with the four region sensors, the last-fetch sensor and an unrelated
// entity from another integration that looks like a region sensor. Regions
// listed in `unavailable` have the state Home Assistant gives an unavailable
// sensor: no attributes of the integration.
function makeHass({
  levels = {},
  active = {},
  upcoming = {},
  unavailable = [],
  ids = {},
  labels = EN_LABELS,
  lastFetch = hoursFromNow(0),
} = {}) {
  const states = {};
  const entities = {};
  // Registry order deliberately differs from the display order.
  for (const region of [...REGIONS].reverse()) {
    const id =
      ids[region.key] ?? `sensor.prociv_madeira_weather_alerts_${region.key}`;
    states[id] = unavailable.includes(region.code)
      ? {
          entity_id: id,
          state: 'unavailable',
          attributes: {
            friendly_name: `ProCiv Madeira Weather Alerts ${region.name}`,
          },
        }
      : {
          entity_id: id,
          state: levels[region.code] ?? 'green',
          attributes: {
            region_code: region.code,
            region: region.name,
            alerts: active[region.code] ?? [],
            upcoming_alerts: upcoming[region.code] ?? [],
          },
        };
    entities[id] = {
      entity_id: id,
      platform: 'prociv_madeira',
      translation_key: region.key,
    };
  }
  const lastFetchId = ids.last_fetch ?? LAST_FETCH;
  states[lastFetchId] = {
    entity_id: lastFetchId,
    state: lastFetch,
    attributes: {},
  };
  entities[lastFetchId] = {
    entity_id: lastFetchId,
    platform: 'prociv_madeira',
    translation_key: 'last_fetch',
  };
  states['sensor.other_region'] = {
    entity_id: 'sensor.other_region',
    state: 'red',
    attributes: {
      region_code: 'XX',
      region: 'Elsewhere',
      alerts: [warning('XX', 'red', 'Wind', -1, 1)],
      upcoming_alerts: [],
    },
  };
  entities['sensor.other_region'] = {
    entity_id: 'sensor.other_region',
    platform: 'other',
    translation_key: 'north_coast',
  };
  return {
    states,
    entities,
    language: 'en',
    locale: { language: 'en' },
    formatEntityState: (stateObj, state = stateObj.state) =>
      labels[state] ?? state,
  };
}

function newCard(context, config) {
  const Card = context.customElements.get(CARD_NAME);
  const card = new Card();
  card.setConfig(config);
  return card;
}

function render(config, hass, context = loadCard()) {
  const card = newCard(context, config);
  card.hass = hass;
  return card.shadowRoot.innerHTML;
}

// A copy of hass in which one entity has a new state object.
function withState(hass, entityId, changes) {
  return {
    ...hass,
    states: {
      ...hass.states,
      [entityId]: { ...hass.states[entityId], ...changes },
    },
  };
}

const matches = (html, pattern) =>
  [...html.matchAll(pattern)].map((match) => match[1]);
const regionNames = (html) =>
  matches(html, /class="region-name"[^>]*>([^<]*)</g);
const regionBadges = (html) =>
  matches(html, /class="region-badge"[^>]*>([^<]*)</g);

const southCoastHeat = () =>
  makeHass({
    levels: { CS: 'orange' },
    active: {
      CS: [warning('CS', 'orange', 'Heat', -2, 20, `Hot ${INJECTION}`)],
    },
    upcoming: { CS: [warning('CS', 'red', 'Wind', 3, 4, 'Gusts')] },
  });

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

test('shows the level in effect with its colour and a header chip', () => {
  const html = render({}, southCoastHeat());

  assert.match(html, /class="region-badge"[^>]*>High</);
  assert.ok(html.includes('#E65100'));
  assert.ok(html.includes('class="level-chip"'));
  assert.ok(!html.includes('All Clear'));
});

test('lists upcoming warnings separately', () => {
  assert.ok(render({}, southCoastHeat()).includes('Future Alerts (1)'));
});

test('hides clear regions unless show_all is on, then sorts by severity', () => {
  assert.deepEqual(regionNames(render({}, southCoastHeat())), ['South Coast']);
  assert.deepEqual(regionNames(render({ show_all: true }, southCoastHeat())), [
    'South Coast',
    'North Coast',
    'Porto Santo',
    'Mountainous Regions',
  ]);
});

test('says all clear and when the data was fetched when no region has warnings', () => {
  const html = render({}, makeHass());

  assert.ok(html.includes('All Clear'));
  assert.ok(html.includes('No weather alerts active'));
  assert.ok(html.includes('Updated just now'));
});

test('escapes text and attribute values', () => {
  const hass = southCoastHeat();
  // A time that browsers can read (the brackets are a comment) with a quote.
  hass.states[LAST_FETCH].state = 'Sep 15 2026 10:00:00 GMT ("x)';
  const html = render({}, hass);

  assert.ok(!html.includes(INJECTION));
  assert.ok(html.includes('&quot;&gt;&lt;img'));
  assert.ok(html.includes('data-ts='));
  assert.ok(!/data-ts="[^"]*"x/.test(html));
  assert.ok(html.includes('data-alert="CS|Heat|orange|'));
});

test('escapes names, titles, hazards and entity IDs', () => {
  const hass = makeHass();
  const injectedId = `sensor.injected${INJECTION}`;
  hass.states[injectedId] = {
    entity_id: injectedId,
    state: 'red',
    attributes: {
      region_code: 'CN',
      region: INJECTION,
      alerts: [warning('CN', 'red', INJECTION, -1, 1)],
      upcoming_alerts: [warning('CN', 'red', INJECTION, 2, 3)],
    },
  };
  hass.states['sensor.gone'] = {
    entity_id: 'sensor.gone',
    state: 'unavailable',
    attributes: { friendly_name: INJECTION },
  };
  const config = {
    title: INJECTION,
    show_all: true,
    entities: [
      { entity: injectedId },
      { entity: SOUTH_COAST, name: INJECTION },
      'sensor.gone',
    ],
  };

  const html = render(config, hass);
  const clear = render({ no_alerts_message: INJECTION }, makeHass());

  assert.equal(regionNames(html).length, 3);
  for (const output of [html, clear]) {
    assert.ok(!output.includes(INJECTION));
    assert.ok(!output.includes('<img'));
  }
});

test('tolerates sensors without upcoming_alerts', () => {
  const hass = southCoastHeat();
  delete hass.states[SOUTH_COAST].attributes.upcoming_alerts;

  assert.match(render({}, hass), /class="region-badge"[^>]*>High</);
});

test('leaves out dates that cannot be read', () => {
  const hass = makeHass({
    levels: { CS: 'orange' },
    active: {
      CS: [
        {
          ...warning('CS', 'orange', 'Heat', -1, 1),
          start_date: 'soon',
          end_date: 'later',
        },
      ],
    },
    lastFetch: 'garbage',
  });
  const html = render({}, hass);

  assert.ok(html.includes('class="panel-type"'));
  assert.ok(!html.includes('Invalid Date'));
  assert.ok(!html.includes('NaN'));
  assert.ok(!html.includes('Updated'));
});

test('uses the default hazard icon for hazards named like object properties', () => {
  const hass = makeHass({
    levels: { CS: 'orange' },
    active: { CS: [warning('CS', 'orange', 'constructor', -1, 1)] },
  });

  assert.deepEqual(
    matches(render({}, hass), /icon="([^"]*)"[^>]*class="panel-icon"/g),
    ['mdi:weather-cloudy-alert'],
  );
});

test('is expanded by default and collapses when the header is clicked', () => {
  const card = newCard(loadCard(), {});
  const header = fakeElement('div');
  card.shadowRoot.querySelector = (selector) =>
    selector === '.card-header' ? header : null;
  card.hass = southCoastHeat();
  assert.ok(card.shadowRoot.innerHTML.includes('class="card-content"'));

  header.listeners.click();

  assert.ok(card.shadowRoot.innerHTML.includes('class="card-header"'));
  assert.ok(!card.shadowRoot.innerHTML.includes('class="card-content"'));
});

// ---------------------------------------------------------------------------
// Regions without data
// ---------------------------------------------------------------------------

test('shows unavailable regions instead of claiming all clear', () => {
  const hass = makeHass({
    unavailable: ['CS'],
    levels: { CN: 'orange' },
    active: { CN: [warning('CN', 'orange', 'Wind', -1, 5)] },
  });
  const html = render({}, hass);

  assert.deepEqual(regionNames(html), ['North Coast', 'South Coast']);
  assert.deepEqual(regionBadges(html), ['High', 'Unavailable']);
  assert.ok(html.includes('data-level="orange"'));
  assert.ok(html.includes('data-level="no-data"'));
  assert.ok(!html.includes('All Clear'));
});

test('says there is no data when every region is unavailable', () => {
  const html = render({}, makeHass({ unavailable: ['CN', 'CS', 'PS', 'RM'] }));

  assert.equal(regionNames(html).length, 4);
  assert.ok(html.includes('class="badge badge--no-data"'));
  assert.ok(!html.includes('All Clear'));
  assert.ok(!html.includes('No weather alerts active'));
  assert.ok(html.includes('Updated just now'));
});

test('labels regions without data when translations are missing', () => {
  const hass = makeHass({ unavailable: ['CS'] });
  hass.formatEntityState = (stateObj, state = stateObj.state) => state;

  assert.deepEqual(regionBadges(render({ show_all: true }, hass)), [
    'Normal',
    'Normal',
    'Normal',
    'No data',
  ]);
});

test('does not claim all clear when no region sensors are found', () => {
  const hass = {
    states: {},
    entities: {},
    language: 'en',
    locale: {},
    formatEntityState: (stateObj, state) => state,
  };
  const html = render({}, hass);

  assert.ok(!html.includes('All Clear'));
  assert.ok(html.includes('No ProCiv Madeira region sensors found'));
});

// ---------------------------------------------------------------------------
// Finding entities
// ---------------------------------------------------------------------------

test('discovers region sensors from the entity registry in display order', () => {
  assert.deepEqual(regionNames(render({ show_all: true }, makeHass())), [
    'North Coast',
    'South Coast',
    'Porto Santo',
    'Mountainous Regions',
  ]);
});

test('does not discover region sensors hidden in Home Assistant', () => {
  const hass = makeHass();
  hass.entities[SOUTH_COAST].hidden = true;

  assert.deepEqual(regionNames(render({ show_all: true }, hass)), [
    'North Coast',
    'Porto Santo',
    'Mountainous Regions',
  ]);
});

test('an explicit entity list wins over discovery', () => {
  const config = {
    show_all: true,
    entities: [
      {
        entity: 'sensor.prociv_madeira_weather_alerts_porto_santo',
        name: 'Ilha',
      },
    ],
  };

  assert.deepEqual(regionNames(render(config, makeHass())), ['Ilha']);
});

test('a prefix that matches nothing falls back to discovery', () => {
  const config = {
    show_all: true,
    entity_prefix: 'sensor.prociv_madeira_alert_',
  };

  assert.equal(regionNames(render(config, makeHass())).length, 4);
});

test('a matching prefix filters the discovered sensors', () => {
  const hass = makeHass({ ids: { south_coast: 'sensor.custom_south' } });

  assert.deepEqual(
    regionNames(
      render({ show_all: true, entity_prefix: 'sensor.custom_' }, hass),
    ),
    ['South Coast'],
  );
});

test('finds the last fetch sensor by translation key', () => {
  const renamed = makeHass({
    levels: { CS: 'orange' },
    active: { CS: [warning('CS', 'orange', 'Heat', -2, 20)] },
    ids: { last_fetch: 'sensor.ultima_atualizacao' },
  });

  assert.ok(render({}, renamed).includes('Updated just now'));
});

test('scans the entity registry only when it changes', () => {
  const context = loadCard();
  const card = newCard(context, {});
  const hass = southCoastHeat();
  let scans = 0;
  const counted = (target) =>
    new Proxy(target, {
      ownKeys(object) {
        scans += 1;
        return Reflect.ownKeys(object);
      },
    });

  const entities = counted(hass.entities);
  card.hass = { ...hass, entities };
  card.hass = { ...hass, entities, states: { ...hass.states } };
  assert.equal(scans, 1);

  card.hass = { ...hass, entities: counted({ ...hass.entities }) };
  assert.equal(scans, 2);
});

// ---------------------------------------------------------------------------
// Updates
// ---------------------------------------------------------------------------

test('re-renders when a region sensor changes', () => {
  const card = newCard(loadCard(), {});
  const hass = southCoastHeat();
  card.hass = hass;
  const renders = card.shadowRoot.renders;

  card.hass = withState(hass, SOUTH_COAST, { state: 'red' });

  assert.equal(card.shadowRoot.renders, renders + 1);
  assert.match(card.shadowRoot.innerHTML, /class="region-badge"[^>]*>Extreme</);
});

test('updates the last fetch time in place instead of rebuilding the card', () => {
  const card = newCard(loadCard(), {});
  const hass = southCoastHeat();
  hass.states[LAST_FETCH].state = hoursFromNow(-2);
  card.hass = hass;
  assert.ok(card.shadowRoot.innerHTML.includes('Updated 2h ago'));
  const updatedAt = {
    dataset: { ts: hass.states[LAST_FETCH].state },
    textContent: 'Updated 2h ago',
  };
  card.shadowRoot.querySelector = (selector) =>
    selector.startsWith('.updated-at') ? updatedAt : null;
  const renders = card.shadowRoot.renders;

  const fetched = hoursFromNow(0);
  card.hass = withState(hass, LAST_FETCH, { state: fetched });

  assert.equal(card.shadowRoot.renders, renders);
  assert.equal(updatedAt.dataset.ts, fetched);
  assert.equal(updatedAt.textContent, 'Updated just now');
});

test('ignores the last fetch time when it is not shown', () => {
  const card = newCard(loadCard(), { show_last_updated: false });
  const hass = southCoastHeat();
  card.hass = hass;
  const renders = card.shadowRoot.renders;

  card.hass = withState(hass, LAST_FETCH, { state: hoursFromNow(1) });

  assert.equal(card.shadowRoot.renders, renders);
});

test('keeps future alerts open across updates', () => {
  const card = newCard(loadCard(), {});
  const hass = southCoastHeat();
  card.hass = hass;
  assert.ok(
    card.shadowRoot.innerHTML.includes(`data-future="${SOUTH_COAST}">`),
  );
  card.shadowRoot.querySelectorAll = (selector) =>
    selector === 'details[data-future]'
      ? [{ open: true, dataset: { future: SOUTH_COAST } }]
      : [];

  card.hass = withState(hass, SOUTH_COAST, { state: 'red' });

  assert.ok(
    card.shadowRoot.innerHTML.includes(`data-future="${SOUTH_COAST}" open>`),
  );
});

// ---------------------------------------------------------------------------
// Labels
// ---------------------------------------------------------------------------

test('re-renders with translated labels when the language changes', () => {
  const card = newCard(loadCard(), {});
  const hass = southCoastHeat();
  card.hass = hass;
  assert.ok(card.shadowRoot.innerHTML.includes('>High<'));

  card.hass = {
    ...hass,
    language: 'pt',
    locale: { language: 'pt' },
    formatEntityState: (stateObj, state = stateObj.state) =>
      PT_LABELS[state] ?? state,
  };
  assert.ok(card.shadowRoot.innerHTML.includes('>Elevado<'));
});

test('re-renders when translations arrive after the first render', () => {
  const card = newCard(loadCard(), {});
  // Before its translations load, Home Assistant formats states as themselves.
  const hass = {
    ...southCoastHeat(),
    language: 'pt',
    locale: { language: 'pt' },
    formatEntityState: (stateObj, state = stateObj.state) => state,
  };
  card.hass = hass;
  assert.ok(card.shadowRoot.innerHTML.includes('>High<'));

  card.hass = {
    ...hass,
    formatEntityState: (stateObj, state = stateObj.state) =>
      PT_LABELS[state] ?? state,
  };
  assert.ok(card.shadowRoot.innerHTML.includes('>Elevado<'));
});

test('falls back to English labels when translations are missing', () => {
  const untranslated = southCoastHeat();
  untranslated.formatEntityState = (stateObj, state = stateObj.state) => state;
  const withoutFormatter = southCoastHeat();
  delete withoutFormatter.formatEntityState;

  assert.match(render({}, untranslated), /class="region-badge"[^>]*>High</);
  assert.match(render({}, withoutFormatter), /class="region-badge"[^>]*>High</);
});

// ---------------------------------------------------------------------------
// Card API
// ---------------------------------------------------------------------------

test('accepts an empty config and offers an empty stub config', () => {
  const context = loadCard();
  const Card = context.customElements.get(CARD_NAME);

  assert.doesNotThrow(() => new Card().setConfig({}));
  assert.deepEqual(plain(Card.getStubConfig()), {});
});

test('provides grid options for the sections view', () => {
  const card = newCard(loadCard(), {});

  assert.deepEqual(plain(card.getGridOptions()), {
    columns: 12,
    rows: 'auto',
    min_columns: 6,
  });
});

test('warns when a different version of the card is already loaded', () => {
  const context = loadCard();
  loadCard(CARD_SOURCE, context);
  assert.deepEqual(context.warnings, []);

  const older = CARD_SOURCE.replace(
    /const CARD_VERSION = '[^']+'/,
    "const CARD_VERSION = '0.0.1'",
  );
  loadCard(older, context);
  assert.equal(context.warnings.length, 1);
  assert.ok(context.warnings[0].includes('0.0.1'));
});

test('the editor saves only options that differ from the defaults', () => {
  const context = loadCard();
  const Editor = context.customElements.get(EDITOR_NAME);
  const editor = new Editor();
  editor.setConfig({ type: `custom:${CARD_NAME}` });
  editor.hass = makeHass();
  editor.connectedCallback();

  editor._form.listeners['value-changed']({
    detail: { value: { ...editor._form.data, title: 'Madeira' } },
  });

  assert.deepEqual(plain(editor.dispatched.at(-1).detail.config), {
    type: `custom:${CARD_NAME}`,
    title: 'Madeira',
  });
});
