// MedSafety frontend. Vue 3 ESM, no build step. Single-tenant: no auth.
import { createApp, defineComponent, reactive, computed, onMounted, ref } from 'https://unpkg.com/vue@3.4.27/dist/vue.esm-browser.prod.js';

// -------------------- Store --------------------
const store = reactive({
  route: window.location.hash.replace(/^#/, '') || '/today',
  medications: [],
  interactions: { counts: { contraindicated: 0, major: 0, moderate: 0, minor: 0 },
                  groups: { contraindicated: [], major: [], moderate: [], minor: [] } },
  todayDate: '',
  todayBlocks: { morning: [], midday: [], evening: [], night: [] },
  todayTotals: { taken: 0, skipped: 0, pending: 0 },
  adherence: { window_days: 28, taken: 0, skipped: 0, missed: 0, take_rate: 0, streak_days: 0 },
  drugSearchResults: [],
  drugSearchSource: 'local',
  toasts: [],
  loading: {},
  errors: {},
  drawerOpen: false,
  health: null,
  explanations: {},
});

let toastId = 1;
function pushToast(message, opts = {}) {
  const id = toastId++;
  const t = { id, message, kind: opts.kind || 'info', duration: opts.duration || 4000, action: opts.action || null };
  store.toasts.push(t);
  if (store.toasts.length > 3) store.toasts.splice(0, store.toasts.length - 3);
  setTimeout(() => { dismissToast(id); }, t.duration);
}
function dismissToast(id) {
  const ix = store.toasts.findIndex(t => t.id === id);
  if (ix >= 0) store.toasts.splice(ix, 1);
}

// -------------------- HTTP --------------------
async function api(path, opts = {}) {
  const headers = Object.assign({ 'Accept': 'application/json' }, opts.headers || {});
  if (opts.body && !(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  let resp;
  try {
    resp = await fetch(path, {
      method: opts.method || 'GET',
      headers,
      body: opts.body ? (typeof opts.body === 'string' ? opts.body : JSON.stringify(opts.body)) : undefined,
    });
  } catch (e) {
    pushToast('Network error. Please check your connection.', { kind: 'major' });
    throw e;
  }
  let data = null;
  const ct = resp.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    try { data = await resp.json(); } catch { data = null; }
  }
  if (!resp.ok) {
    const err = new Error((data && data.error) || `HTTP ${resp.status}`);
    err.code = (data && data.code) || 'HTTP';
    err.status = resp.status;
    throw err;
  }
  return data;
}

// -------------------- Icons --------------------
const ICON = {
  pill: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6.75a4.5 4.5 0 0 1 6.364 6.364l-6.364 6.364a4.5 4.5 0 1 1-6.364-6.364l6.364-6.364Z"/><path stroke-linecap="round" stroke-linejoin="round" d="m7.5 9.75 6.75 6.75"/></svg>`,
  calendar: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5A2.25 2.25 0 0 1 5.25 5.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5"/></svg>`,
  alert: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"/></svg>`,
  shield: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z"/></svg>`,
  plus: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/></svg>`,
  x: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12"/></svg>`,
  check: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5"/></svg>`,
  clock: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/></svg>`,
  search: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"/></svg>`,
  trash: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"/></svg>`,
};

const Icon = defineComponent({
  props: { name: { type: String, required: true } },
  template: `<span v-html="src" class="inline-flex items-center"></span>`,
  computed: { src() { return ICON[this.name] || ''; } },
});

// -------------------- Shared bits --------------------

const DISCLAIMER = 'MedSafety is a demonstration. Drug interaction data is a curated subset for development only and is not medical advice. Always consult a pharmacist or physician.';

const Disclaimer = defineComponent({
  template: `<div class="text-xs text-text-muted mt-8 mb-4 px-6">{{ text }}</div>`,
  computed: { text() { return DISCLAIMER; } },
});

const SeverityChip = defineComponent({
  props: { sev: String },
  template: `<span :class="cls" class="px-2 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wide">{{ sev }}</span>`,
  computed: {
    cls() {
      return {
        contraindicated: 'chip-contra',
        major: 'chip-major',
        moderate: 'chip-moderate',
        minor: 'chip-minor',
      }[this.sev] || 'chip-minor';
    },
  },
});

// -------------------- TopNav --------------------
const TopNav = defineComponent({
  template: `
    <nav class="bg-bg border-b border-border">
      <div class="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <a href="#/today" class="flex items-center gap-2 text-text">
          <span v-html="shield" class="text-primary"></span>
          <span class="font-semibold">MedSafety</span>
        </a>
        <div class="flex items-center gap-1 text-sm">
          <a v-for="t in tabs" :key="t.path" :href="'#'+t.path"
             :class="active(t.path) ? 'text-primary border-b-2 border-primary' : 'text-text-muted hover:text-text'"
             class="px-3 py-3 font-medium">{{ t.label }}</a>
        </div>
        <div class="text-xs text-text-muted">single-patient instance</div>
      </div>
    </nav>
  `,
  setup() {
    const tabs = [
      { path: '/today', label: 'Today' },
      { path: '/medications', label: 'Medications' },
      { path: '/interactions', label: 'Interactions' },
      { path: '/ask', label: 'Ask' },
    ];
    const shield = ICON.shield;
    function active(p) { return store.route === p; }
    return { tabs, shield, active };
  },
});

// -------------------- Today view --------------------
const TodayView = defineComponent({
  template: `
    <div class="max-w-4xl mx-auto px-6 py-6 space-y-4">
      <div class="card p-6">
        <div class="flex items-baseline gap-4">
          <div class="mono" style="font-size: 32px; font-weight: 700;">{{ store.adherence.streak_days }}</div>
          <div class="text-text-muted">streak day{{ store.adherence.streak_days === 1 ? '' : 's' }}</div>
        </div>
        <div class="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div><span class="mono">{{ store.adherence.take_rate }}%</span> take rate <span class="text-text-muted">({{ store.adherence.window_days }} d)</span></div>
          <div><span class="mono">{{ store.adherence.taken }}</span> taken</div>
          <div><span class="mono">{{ store.adherence.skipped }}</span> skipped</div>
          <div><span class="mono">{{ store.adherence.missed }}</span> missed</div>
        </div>
        <div class="mt-2 text-xs text-text-muted">Streak counts days where every dose was taken or explicitly skipped.</div>
      </div>

      <div v-if="hasNoDoses" class="card p-6 text-center">
        <p class="text-text-muted">No doses scheduled for today. Add a medication to get started.</p>
        <button @click="goAdd" class="mt-3 px-4 py-2 bg-primary hover:bg-primary-hover text-white rounded text-sm">Add a medication</button>
      </div>

      <div v-for="b in blockOrder" :key="b.key" v-if="!hasNoDoses">
        <div v-if="store.todayBlocks[b.key].length" class="card p-6">
          <div class="flex items-baseline justify-between mb-3">
            <div class="font-semibold">{{ b.label }}</div>
            <div class="text-xs text-text-muted">{{ b.range }}</div>
          </div>
          <div class="divide-y divide-border">
            <div v-for="r in store.todayBlocks[b.key]" :key="r.id" class="py-3 flex items-center justify-between">
              <div>
                <div class="text-sm font-medium">{{ r.drug.name }}</div>
                <div class="text-xs text-text-muted">
                  <span class="mono">{{ r.dosage_mg }} mg</span>
                  &middot;
                  <span class="mono">{{ fmtTime(r.scheduled_at) }}</span>
                </div>
              </div>
              <div class="flex gap-2 items-center">
                <template v-if="r.taken_at">
                  <span class="text-sev-minor-fg text-sm">Taken at {{ fmtTime(r.taken_at) }} <span v-html="check" class="inline-block align-text-bottom"></span></span>
                </template>
                <template v-else-if="r.skipped">
                  <span class="text-sev-major-fg text-sm">Skipped <span v-html="cross" class="inline-block align-text-bottom"></span></span>
                </template>
                <template v-else>
                  <button @click="markTaken(r.id)" class="px-3 py-1 text-xs bg-primary text-white rounded hover:bg-primary-hover">Take</button>
                  <button @click="markSkip(r.id)" class="px-3 py-1 text-xs border border-border rounded text-text-muted hover:text-text">Skip</button>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const blockOrder = [
      { key: 'morning', label: 'Morning', range: '05:00 - 10:59' },
      { key: 'midday', label: 'Midday', range: '11:00 - 14:59' },
      { key: 'evening', label: 'Evening', range: '15:00 - 20:59' },
      { key: 'night', label: 'Night', range: '21:00 - 04:59' },
    ];
    const check = ICON.check;
    const cross = ICON.x;
    const hasNoDoses = computed(() => {
      const b = store.todayBlocks;
      return (!b.morning.length && !b.midday.length && !b.evening.length && !b.night.length);
    });
    function fmtTime(iso) {
      if (!iso) return '';
      const d = new Date(iso);
      const hh = String(d.getHours()).padStart(2, '0');
      const mm = String(d.getMinutes()).padStart(2, '0');
      return `${hh}:${mm}`;
    }
    async function markTaken(id) {
      try {
        await api(`/api/me/reminders/${id}/taken`, { method: 'POST' });
        await Promise.all([loadToday(), loadAdherence()]);
      } catch (e) { /* handled in api */ }
    }
    async function markSkip(id) {
      try {
        await api(`/api/me/reminders/${id}/skip`, { method: 'POST' });
        await Promise.all([loadToday(), loadAdherence()]);
      } catch (e) {}
    }
    function goAdd() {
      location.hash = '#/medications';
      setTimeout(() => { store.drawerOpen = true; }, 50);
    }
    onMounted(() => {
      loadToday();
      loadAdherence();
    });
    return { store, blockOrder, check, cross, hasNoDoses, fmtTime, markTaken, markSkip, goAdd };
  },
});

async function loadToday() {
  try {
    const d = new Date();
    const ymd = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    const data = await api(`/api/me/reminders?date=${ymd}`);
    store.todayDate = data.date;
    store.todayBlocks = data.blocks;
    store.todayTotals = data.totals;
  } catch {}
}

async function loadAdherence() {
  try {
    const data = await api('/api/me/adherence?days=28');
    store.adherence = data;
  } catch {}
}

// -------------------- Medications view --------------------
const MedicationsView = defineComponent({
  template: `
    <div class="max-w-4xl mx-auto px-6 py-6 space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">My medications</h2>
        <button @click="openDrawer" class="flex items-center gap-1 bg-primary hover:bg-primary-hover text-white px-4 py-2 rounded text-sm">
          <span v-html="plusIcon"></span><span>Add medication</span>
        </button>
      </div>
      <div v-if="!store.medications.length" class="card p-6 text-center text-text-muted">
        You have no active prescriptions. Add one to start the safety check.
      </div>
      <div v-for="rx in store.medications" :key="rx.id" class="card p-4 flex items-start justify-between">
        <div>
          <div class="flex items-center gap-2">
            <div class="font-semibold">{{ rx.drug.name }}</div>
            <span class="px-2 py-0.5 text-xs rounded bg-surface text-text-muted border border-border">{{ rx.drug.drug_class }}</span>
          </div>
          <div class="text-sm mt-1"><span class="mono">{{ rx.dosage_mg }} mg</span> &middot; {{ rx.schedule }}</div>
          <div class="text-xs text-text-muted mt-1">Started {{ fmtDate(rx.started_at) }}</div>
          <div v-if="rx.notes" class="text-xs text-text-muted mt-1">{{ rx.notes }}</div>
        </div>
        <div class="flex items-center gap-3">
          <button @click="confirmStop(rx)" class="text-text-muted hover:text-sev-major-fg" :title="'Stop '+rx.drug.name" v-html="trashIcon"></button>
        </div>
      </div>

      <add-drawer v-if="store.drawerOpen" @close="store.drawerOpen=false" @saved="onSaved"></add-drawer>

      <div v-if="confirming" class="fixed inset-0 bg-black/30 z-40 flex items-center justify-center px-4">
        <div class="card p-6 max-w-sm w-full">
          <div class="font-semibold mb-2">Stop taking {{ confirming.drug.name }}?</div>
          <div class="text-sm text-text-muted mb-4">This marks the prescription as inactive. You can re-add it later.</div>
          <div class="flex justify-end gap-2">
            <button @click="confirming=null" class="px-3 py-1 text-sm border border-border rounded">Cancel</button>
            <button @click="doStop" class="px-3 py-1 text-sm bg-sev-major-fg text-white rounded">Stop</button>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const confirming = ref(null);
    const plusIcon = ICON.plus;
    const trashIcon = ICON.trash;
    function openDrawer() { store.drawerOpen = true; }
    function fmtDate(iso) {
      if (!iso) return '';
      const d = new Date(iso);
      return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    }
    function confirmStop(rx) { confirming.value = rx; }
    async function doStop() {
      const rx = confirming.value;
      confirming.value = null;
      try {
        await api(`/api/me/prescriptions/${rx.id}`, { method: 'DELETE' });
        await loadMedications();
        await loadInteractions();
        pushToast(`Stopped ${rx.drug.name}.`);
      } catch {}
    }
    async function onSaved(payload) {
      await loadMedications();
      const beforeMajor = store.interactions.counts.contraindicated + store.interactions.counts.major;
      await loadInteractions();
      const afterMajor = store.interactions.counts.contraindicated + store.interactions.counts.major;
      if (afterMajor > beforeMajor) {
        pushToast(`Added ${payload.drug.name}. Interaction matrix updated.`, {
          kind: 'major',
          duration: 8000,
          action: { label: 'Review', route: '/interactions' },
        });
      } else {
        pushToast(`Added ${payload.drug.name}. Interaction matrix updated.`);
      }
    }
    onMounted(() => { loadMedications(); });
    return { store, confirming, plusIcon, trashIcon, openDrawer, fmtDate, confirmStop, doStop, onSaved };
  },
});

async function loadMedications() {
  try {
    const data = await api('/api/me/prescriptions?active=true');
    store.medications = data;
  } catch {}
}

const AddDrawer = defineComponent({
  template: `
    <div class="fixed inset-0 z-40 flex justify-end">
      <div class="absolute inset-0 bg-black/30" @click="$emit('close')"></div>
      <div class="relative bg-white w-full max-w-[480px] h-full overflow-y-auto p-6 drawer">
        <div class="flex items-center justify-between mb-4">
          <div class="font-semibold">Add medication</div>
          <button @click="$emit('close')" v-html="xIcon" class="text-text-muted"></button>
        </div>
        <div v-if="!selected">
          <label class="block text-xs text-text-muted mb-1">Drug name</label>
          <div class="relative">
            <span v-html="searchIcon" class="absolute left-2 top-2 text-text-muted"></span>
            <input v-model="q" @input="onInput" placeholder="ibuprofen, lipitor, ..." class="w-full pl-8 pr-3 py-2 border border-border rounded text-sm" />
          </div>
          <div v-if="results.length" class="mt-2 max-h-64 overflow-y-auto border border-border rounded">
            <button v-for="r in results" :key="(r.id||'cui-'+r.rxnorm_cui)" @click="selectDrug(r)" class="w-full text-left px-3 py-2 hover:bg-surface border-b border-border last:border-b-0">
              <div class="text-sm font-medium">{{ r.name }}</div>
              <div class="text-xs text-text-muted">{{ r.generic_name }} &middot; {{ r.drug_class }}</div>
            </button>
          </div>
          <div v-if="source === 'local'" class="text-xs text-text-muted mt-1">Offline drug list.</div>
        </div>
        <div v-else class="space-y-3">
          <div class="flex items-center gap-2 px-2 py-1 bg-surface rounded border border-border text-sm w-fit">
            <span>{{ selected.name }} <span class="text-text-muted">({{ selected.generic_name }})</span></span>
            <button @click="selected=null" v-html="xIcon" class="text-text-muted"></button>
          </div>
          <div>
            <label class="block text-xs text-text-muted mb-1">Dosage</label>
            <div class="flex items-center gap-2">
              <input v-model.number="dosage_mg" type="number" min="0" step="any" class="w-32 px-3 py-2 border border-border rounded text-sm mono" />
              <span class="text-text-muted text-sm">mg</span>
            </div>
          </div>
          <div>
            <label class="block text-xs text-text-muted mb-1">Schedule</label>
            <input v-model="schedule" placeholder="morning, evening" class="w-full px-3 py-2 border border-border rounded text-sm" />
            <div class="text-xs text-text-muted mt-1">Valid forms: "morning", "midday", "evening", "night", any comma-combo, "every 8h", or "as needed".</div>
          </div>
          <div>
            <label class="block text-xs text-text-muted mb-1">Started</label>
            <input v-model="started_at" type="date" class="w-full px-3 py-2 border border-border rounded text-sm" />
          </div>
          <div>
            <label class="block text-xs text-text-muted mb-1">Notes (optional)</label>
            <textarea v-model="notes" rows="2" class="w-full px-3 py-2 border border-border rounded text-sm"></textarea>
          </div>
          <div class="flex justify-end gap-2 pt-2">
            <button @click="$emit('close')" class="text-text-muted text-sm">Cancel</button>
            <button @click="save" :disabled="!canSave || saving" class="bg-primary hover:bg-primary-hover disabled:opacity-50 text-white px-4 py-2 rounded text-sm">{{ saving ? 'Saving...' : 'Save' }}</button>
          </div>
        </div>
      </div>
    </div>
  `,
  emits: ['close', 'saved'],
  setup(_, { emit }) {
    const q = ref('');
    const results = ref([]);
    const source = ref('local');
    const selected = ref(null);
    const dosage_mg = ref(null);
    const schedule = ref('morning');
    const started_at = ref(new Date().toISOString().slice(0, 10));
    const notes = ref('');
    const saving = ref(false);
    const xIcon = ICON.x;
    const searchIcon = ICON.search;
    const canSave = computed(() => !!selected.value && dosage_mg.value > 0 && schedule.value.trim().length > 0);
    let debounceT = null;

    function onInput() {
      if (debounceT) clearTimeout(debounceT);
      debounceT = setTimeout(doSearch, 250);
    }
    async function doSearch() {
      if (!q.value || q.value.trim().length < 2) {
        results.value = [];
        return;
      }
      try {
        const data = await api(`/api/drugs/search?q=${encodeURIComponent(q.value.trim())}`);
        source.value = data.source;
        results.value = data.results;
      } catch (e) {
        results.value = [];
      }
    }
    function selectDrug(r) {
      selected.value = r;
      results.value = [];
      q.value = '';
    }
    async function save() {
      if (!canSave.value) return;
      saving.value = true;
      try {
        const body = {
          drug_id: selected.value.id || undefined,
          rxnorm_cui: !selected.value.id ? selected.value.rxnorm_cui : undefined,
          dosage_mg: dosage_mg.value,
          schedule: schedule.value.trim(),
          started_at: new Date(started_at.value + 'T00:00:00Z').toISOString(),
          notes: notes.value || undefined,
        };
        const data = await api('/api/me/prescriptions', { method: 'POST', body });
        emit('saved', data);
        emit('close');
      } catch (e) {
        pushToast(e.message || 'Could not save prescription.', { kind: 'major' });
      } finally {
        saving.value = false;
      }
    }
    return { q, results, source, selected, dosage_mg, schedule, started_at, notes, saving, xIcon, searchIcon, canSave, onInput, selectDrug, save };
  },
});

// -------------------- Interactions view --------------------
const InteractionsView = defineComponent({
  template: `
    <div class="max-w-4xl mx-auto px-6 py-6 space-y-4">
      <div class="disclaimer-band p-3 text-sm flex items-start gap-2">
        <span v-html="alertIcon" class="text-sev-moderate-fg shrink-0 mt-0.5"></span>
        <div>{{ disclaimer }}</div>
      </div>

      <div v-if="medsCount < 2" class="card p-6 text-center text-text-muted">
        Add at least two medications to see interaction checks.
      </div>

      <template v-else>
        <div v-if="loading" class="space-y-2">
          <div v-for="i in 4" :key="i" class="card p-4">
            <div class="shimmer h-3 w-1/3 mb-2 rounded"></div>
            <div class="shimmer h-4 w-2/3 mb-2 rounded"></div>
            <div class="shimmer h-3 w-3/4 rounded"></div>
          </div>
        </div>

        <template v-else>
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <button v-for="b in buckets" :key="b.key" @click="scrollTo(b.key)" :class="b.cls" class="rounded-lg p-4 text-left">
              <div class="mono text-2xl font-bold">{{ store.interactions.counts[b.key] }}</div>
              <div class="text-xs uppercase tracking-wide font-semibold">{{ b.label }}</div>
            </button>
          </div>

          <div v-if="totalCount === 0" class="card p-6 text-center">
            <div class="flex flex-col items-center gap-2">
              <span v-html="shieldIcon" class="text-primary"></span>
              <div class="text-sm">No interactions found across your current list.</div>
              <div class="text-xs text-text-muted">This means none of the pairs are in the curated dataset - it does not guarantee safety.</div>
            </div>
          </div>

          <div v-for="b in buckets" :key="'sec-'+b.key" :id="'sec-'+b.key" v-show="store.interactions.groups[b.key].length">
            <div class="flex items-baseline gap-2 mt-4 mb-2">
              <div class="font-semibold capitalize">{{ b.label }}</div>
              <div class="text-text-muted text-sm">({{ store.interactions.counts[b.key] }})</div>
            </div>
            <div class="space-y-2">
              <div v-for="it in store.interactions.groups[b.key]" :key="it.interaction_id" class="card p-4">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="text-sm font-medium">{{ it.drug_a.name }} x {{ it.drug_b.name }}</div>
                    <div class="text-xs text-text-muted mt-1">{{ it.mechanism }}</div>
                  </div>
                  <div class="flex items-center gap-2 shrink-0">
                    <severity-chip :sev="it.severity"></severity-chip>
                    <button @click="explain(it)" class="px-3 py-1 text-xs border border-border rounded hover:bg-surface">Explain</button>
                  </div>
                </div>
                <div v-if="store.explanations[it.interaction_id]" class="mt-3 border-t border-border pt-3">
                  <div class="text-xs text-text-muted flex items-center gap-1 mb-2">
                    <span v-html="alertIcon" class="text-sev-moderate-fg"></span>
                    <span>{{ disclaimer }}</span>
                  </div>
                  <div v-if="store.explanations[it.interaction_id].loading">
                    <div class="shimmer h-3 mb-2 rounded"></div>
                    <div class="shimmer h-3 mb-2 rounded"></div>
                    <div class="shimmer h-3 w-3/4 rounded"></div>
                  </div>
                  <div v-else>
                    <div class="text-sm whitespace-pre-line">{{ store.explanations[it.interaction_id].text }}</div>
                    <div class="mt-2 text-xs text-text-muted">
                      {{ captionFor(store.explanations[it.interaction_id].model) }}
                      <button @click="explain(it, true)" class="ml-2 text-primary hover:underline">Refresh</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </template>
    </div>
  `,
  setup() {
    const loading = ref(false);
    const alertIcon = ICON.alert;
    const shieldIcon = ICON.shield;
    const buckets = [
      { key: 'contraindicated', label: 'Contraindicated', cls: 'chip-contra' },
      { key: 'major', label: 'Major', cls: 'chip-major' },
      { key: 'moderate', label: 'Moderate', cls: 'chip-moderate' },
      { key: 'minor', label: 'Minor', cls: 'chip-minor' },
    ];
    const medsCount = computed(() => store.medications.length);
    const totalCount = computed(() => {
      const c = store.interactions.counts;
      return c.contraindicated + c.major + c.moderate + c.minor;
    });
    function scrollTo(key) {
      const el = document.getElementById('sec-' + key);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    function captionFor(model) {
      if (!model) return '';
      if (model === 'template') return 'Generated locally (no LLM key set).';
      return `Generated by ${model}`;
    }
    async function explain(it, refresh) {
      const id = it.interaction_id;
      store.explanations[id] = { loading: true, text: '', model: '' };
      try {
        const url = `/api/me/interactions/${id}/explain${refresh ? '?refresh=true' : ''}`;
        const data = await api(url, { method: 'POST' });
        store.explanations[id] = { loading: false, text: data.explanation, model: data.model };
      } catch (e) {
        store.explanations[id] = { loading: false, text: 'Could not load explanation.', model: '' };
      }
    }
    onMounted(async () => {
      loading.value = true;
      if (!store.medications.length) await loadMedications();
      await loadInteractions();
      loading.value = false;
    });
    return { store, loading, alertIcon, shieldIcon, buckets, medsCount, totalCount, scrollTo, captionFor, explain, disclaimer: DISCLAIMER };
  },
});

async function loadInteractions() {
  try {
    const data = await api('/api/me/interactions');
    store.interactions = data;
  } catch {}
}

// -------------------- Toast container --------------------
const Toasts = defineComponent({
  template: `
    <div class="fixed top-4 right-4 z-50 space-y-2 w-80">
      <div v-for="t in store.toasts" :key="t.id" :class="kindCls(t.kind)" class="rounded shadow-card border px-3 py-2 text-sm flex items-start justify-between gap-2">
        <div>{{ t.message }}</div>
        <div class="flex items-center gap-2">
          <button v-if="t.action" @click="doAction(t)" class="text-primary text-xs hover:underline">{{ t.action.label }}</button>
          <button @click="dismiss(t.id)" class="text-text-muted" v-html="xIcon"></button>
        </div>
      </div>
    </div>
  `,
  setup() {
    const xIcon = ICON.x;
    function kindCls(kind) {
      if (kind === 'major') return 'chip-major border-sev-major-fg';
      return 'bg-white border-border text-text';
    }
    function dismiss(id) { dismissToast(id); }
    function doAction(t) {
      if (t.action && t.action.route) location.hash = '#' + t.action.route;
      dismissToast(t.id);
    }
    return { store, xIcon, kindCls, dismiss, doAction };
  },
});

// -------------------- Footer --------------------
const Footer = defineComponent({
  template: `
    <footer class="border-t border-border mt-8 py-4 px-6 text-xs text-text-muted text-center">
      {{ text }}
    </footer>
  `,
  computed: { text() { return DISCLAIMER; } },
});

// -------------------- Ask view --------------------
const ASK_PRESETS = [
  'Can I drink coffee with this medicine?',
  'Should I take this in the morning or evening?',
  'Is it okay to skip a dose if I forget?',
];

const AskView = defineComponent({
  template: `
    <div class="max-w-3xl mx-auto px-6 py-6 space-y-4">
      <div class="disclaimer-band p-3 text-sm flex items-start gap-2">
        <span v-html="alertIcon" class="text-sev-moderate-fg shrink-0 mt-0.5"></span>
        <div>{{ disclaimer }}</div>
      </div>

      <div class="card p-6 space-y-4">
        <div>
          <div class="font-semibold">Ask about a medicine</div>
          <div class="text-sm text-text-muted">
            Pick a drug, ask a plain-English question. The AI answers in 2-3
            short sentences and reminds you to consult a pharmacist.
          </div>
        </div>

        <div class="space-y-1">
          <label class="text-xs text-text-muted">Drug</label>
          <div class="relative">
            <input
              v-model="q"
              @input="onInput"
              type="text"
              placeholder="Search drug name (min 2 chars)..."
              class="w-full border border-border rounded px-3 py-2 text-sm" />
            <div v-if="results.length" class="absolute top-full left-0 right-0 bg-bg border border-border rounded mt-1 shadow-card z-10 max-h-60 overflow-y-auto">
              <button v-for="r in results" :key="(r.id || 'rx-') + (r.rxnorm_cui || r.name)"
                      @click="selectDrug(r)"
                      class="w-full text-left px-3 py-2 text-sm hover:bg-surface border-b border-border last:border-b-0">
                <div class="font-medium">{{ r.name }}</div>
                <div class="text-xs text-text-muted">{{ r.drug_class || 'unknown class' }}</div>
              </button>
            </div>
          </div>
          <div v-if="selected" class="text-sm mt-1">
            Selected: <span class="font-medium">{{ selected.name }}</span>
            <span class="text-text-muted">({{ selected.drug_class || 'unknown class' }})</span>
            <button @click="clearSelected" class="ml-2 text-xs text-primary hover:underline">change</button>
          </div>
        </div>

        <div class="space-y-1">
          <label class="text-xs text-text-muted">Question</label>
          <textarea v-model="question" rows="2" maxlength="240"
                    class="w-full border border-border rounded px-3 py-2 text-sm"
                    placeholder="Type your question..."></textarea>
          <div class="flex flex-wrap gap-2">
            <button v-for="p in presets" :key="p" @click="question = p"
                    class="px-2 py-1 text-xs border border-border rounded-full text-text-muted hover:text-text hover:border-primary">{{ p }}</button>
          </div>
        </div>

        <div>
          <button @click="ask" :disabled="!canAsk || loading"
                  class="px-4 py-2 bg-primary text-white rounded text-sm hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed">
            {{ loading ? 'Thinking...' : 'Ask' }}
          </button>
        </div>

        <div v-if="answer" class="border-t border-border pt-4">
          <div class="text-xs text-text-muted mb-2">Answer about {{ answer.drug_name }}</div>
          <div class="text-sm whitespace-pre-line">{{ answer.answer }}</div>
          <div class="mt-2 text-xs text-text-muted mono">Model: {{ answer.llm_model }}</div>
        </div>

        <div v-if="errorMsg" class="text-sm text-sev-major-fg">{{ errorMsg }}</div>
      </div>
    </div>
  `,
  setup() {
    const q = ref('');
    const results = ref([]);
    const selected = ref(null);
    const question = ref('');
    const answer = ref(null);
    const loading = ref(false);
    const errorMsg = ref('');
    const alertIcon = ICON.alert;
    const disclaimer = DISCLAIMER;
    const presets = ASK_PRESETS;
    let debounceT = null;

    const canAsk = computed(
      () => !!selected.value && question.value.trim().length >= 3
    );

    function onInput() {
      if (debounceT) clearTimeout(debounceT);
      debounceT = setTimeout(doSearch, 250);
    }
    async function doSearch() {
      const term = q.value.trim();
      if (term.length < 2) {
        results.value = [];
        return;
      }
      try {
        const data = await api(`/api/drugs/search?q=${encodeURIComponent(term)}`);
        results.value = data.results || [];
      } catch {
        results.value = [];
      }
    }
    function selectDrug(r) {
      selected.value = r;
      q.value = '';
      results.value = [];
    }
    function clearSelected() {
      selected.value = null;
    }
    async function ask() {
      if (!canAsk.value) return;
      errorMsg.value = '';
      answer.value = null;
      const id = selected.value && selected.value.id;
      if (!id) {
        errorMsg.value =
          'This drug is not in the local catalog yet. Add it as a prescription first, then ask.';
        return;
      }
      loading.value = true;
      try {
        const data = await api(`/api/drugs/${id}/ask`, {
          method: 'POST',
          body: { question: question.value.trim() },
        });
        answer.value = data;
      } catch (e) {
        errorMsg.value = e.message || 'Could not get an answer.';
      } finally {
        loading.value = false;
      }
    }

    return {
      q, results, selected, question, answer, loading, errorMsg,
      alertIcon, disclaimer, presets, canAsk,
      onInput, selectDrug, clearSelected, ask,
    };
  },
});

// -------------------- Root App --------------------
const App = defineComponent({
  template: `
    <div class="min-h-screen flex flex-col">
      <top-nav></top-nav>
      <main class="flex-1">
        <today-view v-if="store.route === '/today'"></today-view>
        <medications-view v-else-if="store.route === '/medications'"></medications-view>
        <interactions-view v-else-if="store.route === '/interactions'"></interactions-view>
        <ask-view v-else-if="store.route === '/ask'"></ask-view>
        <today-view v-else></today-view>
      </main>
      <footer-bar></footer-bar>
      <toasts></toasts>
    </div>
  `,
  setup() {
    return { store };
  },
});

// -------------------- Bootstrap --------------------
window.addEventListener('hashchange', () => {
  store.route = window.location.hash.replace(/^#/, '') || '/today';
});
if (!window.location.hash) {
  window.location.hash = '#/today';
}
store.route = window.location.hash.replace(/^#/, '') || '/today';

async function bootstrap() {
  try {
    await Promise.all([loadMedications(), loadInteractions(), loadAdherence(), loadToday()]);
  } catch {}
}

const app = createApp(App);
app.component('icon-svg', Icon);
app.component('severity-chip', SeverityChip);
app.component('top-nav', TopNav);
app.component('today-view', TodayView);
app.component('medications-view', MedicationsView);
app.component('add-drawer', AddDrawer);
app.component('interactions-view', InteractionsView);
app.component('ask-view', AskView);
app.component('toasts', Toasts);
app.component('footer-bar', Footer);
app.component('disclaimer-line', Disclaimer);
app.mount('#app');
bootstrap();
