"use strict";

const state = {
  households: [],
  householdId: localStorage.getItem("cf.householdId") || null,
  members: [],
  accounts: [],
  institutions: [],
  categories: [],
  reviews: [],
  incomeSources: [],
  lastConfirm: null,
  importSeparator: "",
  dashboardYear: null,
  dashMonth: null,
  txnYear: null,
  txnMonth: null,
  egresosTab: "movimientos",
  egresosCat: "",
  egresosAccount: "",
  txnSearch: "",
  txnSearchTimer: null,
  selectedAccountId: null,
  accTab: "movimientos",
  rollCache: {},
  householdTxns: null,
  reportTab: "resumen",
  reportRange: "12m",
  reportYear: null,
  reportFrom: "",
  reportTo: "",
};

/* Navegación objetivo: Inicio · Ingresos · Egresos · Cuentas · Tarjetas · Deudas ·
   Presupuesto · Metas · Reportes · Asistente · Importar · Configuración.
   Items "hidden": rutas legadas que se conservan para compatibilidad/tests. */
const NAV = [
  { hash: "#/dashboard", label: "Inicio", icon: "M3 12l9-9 9 9M5 10v10h5v-6h4v6h5V10", group: "Principal" },
  { hash: "#/income", label: "Ingresos", icon: "M12 3v18M17 7l-5-4-5 4M5 17h14M8 21h8", group: "Principal" },
  { hash: "#/egresos", label: "Egresos", icon: "M12 3v18M17 17l-5 4-5-4M5 7h14M8 3h8", group: "Principal" },
  { hash: "#/accounts", label: "Cuentas", icon: "M4 6h16v12H4zM4 10h16M8 3h8M4 14h4M12 14h8", group: "Principal" },
  { hash: "#/credit-cards", label: "Tarjetas de crédito", icon: "M2 10h20M2 14h20M6 6h12a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2z", group: "Principal" },
  { hash: "#/debts", label: "Deudas y préstamos", icon: "M3 10h18M8 21V10M16 21V10M5 21h14M5 7l2-3h10l2 3z", group: "Principal" },
  { hash: "#/budget", label: "Presupuesto", icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2", group: "Principal" },
  { hash: "#/goals", label: "Metas", icon: "M12 21v-6M12 8V6M9 3h6m-1 8a3 3 0 11-4 0 3 3 0 014 0zm-4 6a7 7 0 11-2-13.6", group: "Principal" },
  { hash: "#/reports", label: "Reportes", icon: "M4 19V8M10 19V4M16 19v-7M22 19H3", group: "Principal" },
  { hash: "#/ai", label: "Asistente IA", icon: "M11 5a6 6 0 00-4.2 10.2L8 13l2.8-.1A6 6 0 0011 5zm1 0a6 6 0 014.2 10.2L16 13l-2.8-.1A6 6 0 0112 5zm-1 14h2v2h-2z", group: "Principal" },
  { hash: "#/imports", label: "Importar", icon: "M12 3v12m0 0l-4-4m4 4l4-4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2", group: "Herramientas" },
  { hash: "#/config", label: "Configuración", icon: "M4 6h16M4 12h16M4 18h16", group: "Herramientas" },
  { hash: "#/payments", label: "Pagos y resumen", icon: "M12 6v6l4 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z", group: "Legacy", hidden: true },
  { hash: "#/projections", label: "Proyecciones", icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6M9 19h10m-2-2v-4a2 2 0 00-2-2h-2m-4 8v-8", group: "Legacy", hidden: true },
  { hash: "#/notifications", label: "Avisos", icon: "M12 22a2 2 0 001.6-.8M6.3 20a15 15 0 01-1.8-2c-1.4-2.2-1.5-5-.3-7.6.8-1.6 1.2-3.1 1.2-4.4 0-3.3 2.7-6 6-6s6 2.7 6 6c0 1.3.4 2.8 1.2 4.4 1.2 2.6 1.1 5.4-.3 7.6a15 15 0 01-1.8 2", group: "Legacy", hidden: true },
];

const CHART_COLORS = [
  "#19b5a5", "#f4b942", "#e15554", "#38bdf8", "#8b5cf6", "#fb923c",
  "#2dd4bf", "#6366f1", "#a3e635", "#ec4899", "#22d3ee", "#94a3b8",
  "#0e8779", "#b8860b", "#0ea5e9", "#7c3aed", "#f97316", "#14b8a6",
];

function colorForId(id) {
  let hash = 0;
  const s = String(id || "");
  if (s === "") return CHART_COLORS[0];
  for (let i = 0; i < s.length; i++) hash = (hash * 31 + s.charCodeAt(i)) >>> 0;
  return CHART_COLORS[hash % CHART_COLORS.length];
}

const KIND_LABEL = {
  expense: "Gasto",
  income: "Ingreso",
  transfer: "Transferencia",
  payment: "Pago",
  adjustment: "Ajuste",
};

const ACCOUNT_TYPE_LABEL = {
  checking: "Corriente",
  savings: "Ahorro",
  credit_card: "Tarjeta de crédito",
  cash: "Efectivo",
  investment: "Inversión",
  wallet: "Billetera",
  loan_line: "Línea de crédito",
  other: "Otras",
};

const DEBT_TYPE_LABEL = {
  credit_card: "Tarjeta de crédito",
  loan: "Préstamo",
  auto: "Auto",
  mortgage: "Hipoteca",
  line: "Línea de crédito",
  personal: "Préstamo personal",
  family: "Préstamo familiar",
  other: "Otro",
};

const root = document.getElementById("app");

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[c]);
}

function money(value) {
  const n = Number(value || 0);
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(n);
}

function todayISO() {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function formatDate(value) {
  if (!value) return "—";
  const valid = /^\d{4}-\d{2}-\d{2}/.test(String(value)) ? String(value).slice(0, 10) : String(value);
  const [y, m, d] = valid.split("-").map(Number);
  if (!y || !m || !d) return String(value);
  const names = "Enero Febrero Marzo Abril Mayo Junio Julio Agosto Septiembre Octubre Noviembre Diciembre".split(" ");
  return `${d} ${names[m - 1]}`.replace(/\b0(\d)/g, "$1");
}

/* ---------- Componentes de UI / visualización ---------- */

function pctDelta(current, previous) {
  if (previous == null) return null;
  if (previous === 0) return current === 0 ? 0 : null;
  return ((current - previous) / previous) * 100;
}

function deltaBadge(delta, { invert = false, suffix = "% vs mes anterior" } = {}) {
  if (delta == null || !isFinite(delta)) {
    return `<span class="kpi-delta flat">sin comparación</span>`;
  }
  const safe = (delta > 0 && invert) || (delta < 0 && invert) ? -delta : delta;
  const arrow = safe > 0.05 ? "↑" : safe < -0.05 ? "↓" : "→";
  const cls = safe > 0.05 ? "up" : safe < -0.05 ? "down" : "flat";
  const abs = Math.abs(safe);
  const txt = `${arrow} ${abs.toFixed(1).replace(".", ",")}% ${suffix}`;
  return `<span class="kpi-delta ${cls}">${txt}</span>`;
}

function svgIcon(path, size = 18) {
  return `<svg class="shrink-0" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${path}"/></svg>`;
}

function kpiCard({ label, value, delta = null, invert = false, icon, color = "#19b5a5", spark = null, footer = "", href = null }) {
  return `
  <div class="cf-card kpi-card cf-fade">
    <div class="flex items-start justify-between">
      <div>
        <div class="kpi-label">${esc(label)}</div>
        <div class="kpi-value mt-1">${value}</div>
      </div>
      <div class="kpi-icon" style="background:${color}">${svgIcon(icon)}</div>
    </div>
    <div class="flex items-end justify-between gap-2 mt-2">
      <div class="min-w-0">
        ${deltaBadge(delta, { invert })}
        ${footer ? `<div class="text-xs text-slate-500 mt-0.5">${footer}</div>` : ""}
      </div>
      ${spark ? spark : ""}
    </div>
    ${href ? `<a href="${esc(href)}" class="absolute inset-0" aria-label="${esc(label)}" style="opacity:0"></a>` : ""}
  </div>`;
}

function sparkline(values, { color = "#19b5a5", w = 96, h = 32 } = {}) {
  const nums = (Array.isArray(values) ? values : []).map(Number);
  if (nums.length < 2) return "";
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const span = max - min || 1;
  const stepX = w / (nums.length - 1);
  const pts = nums.map((v, i) => `${(i * stepX).toFixed(1)},${(h - 3 - ((v - min) / span) * (h - 6) - 1.5).toFixed(1)}`);
  const path = pts.map((p, i) => (i === 0 ? `M${p}` : `L${p}`)).join(" ");
  return `<svg class="shrink-0" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">
    <path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round"/>
    <path d="${path} L${w},${h} L0,${h} Z" fill="${color}" opacity="0.12"/>
  </svg>`;
}

function donutSvg(segments, { size = 200, thickness = 30, centerLabel = "", centerValue = "" } = {}) {
  const total = segments.reduce((a, s) => a + Math.max(0, s.value), 0) || 1;
  const c = size / 2;
  const r = (size - thickness) / 2;
  const circ = 2 * Math.PI * r;
  let offset = 0;
  let segs = "";
  const title = centerLabel ? `<title>${esc(centerLabel)}</title>` : "";
  for (const s of segments) {
    const len = (Math.max(0, s.value) / total) * circ;
    segs += `<circle class="donut-segment" data-name="${esc(s.name)}" data-amount="${Number(s.value) || 0}" cx="${c}" cy="${c}" r="${r}"
      fill="none" stroke="${s.color}" stroke-width="${thickness}"
      stroke-dasharray="${len.toFixed(2)} ${(circ - len).toFixed(2)}"
      stroke-dashoffset="${(-offset).toFixed(2)}"
      stroke-linecap="${Number(s.value) >= total ? "round" : "butt"}">${title}</circle>`;
    offset += len;
  }
  return `<svg class="donut-svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(centerLabel || "distribución")}">
    ${segs}
    <text x="${c}" y="${c - 6}" text-anchor="middle" class="fill-slate-800" style="font-size:20px;font-weight:800">${esc(centerValue)}</text>
    <text x="${c}" y="${c + 14}" text-anchor="middle" class="fill-slate-500" style="font-size:11px;font-weight:600;text-transform:uppercase">${esc(centerLabel)}</text>
  </svg>`;
}

function monthLabelShort(month) {
  return "E F M A M J J A S O N D".split(" ")[month - 1] || String(month);
}

function areaChart(values, { labels = [], w = 280, h = 140, color = "#123b4a", yFmt = null } = {}) {
  const nums = (values || []).map(Number);
  if (nums.length < 2) return "";
  const min = Math.min(0, ...nums);
  const max = Math.max(...nums, 1);
  const span = max - min || 1;
  const pad = 6;
  const stepX = (w - pad * 2) / (nums.length - 1);
  const pts = nums.map((v, i) => `${(pad + i * stepX).toFixed(1)},${(h - pad - ((v - min) / span) * (h - pad * 2)).toFixed(1)}`);
  const line = pts.map((p, i) => (i === 0 ? `M${p}` : `L${p}`)).join(" ");
  const fill = `${line} L${pad + (nums.length - 1) * stepX.toFixed(1)},${h - pad} L${pad},${h - pad} Z`;
  const dotLabels = labels.length === nums.length
    ? labels.map((lb, i) => `<circle cx="${pts[i].split(",")[0]}" cy="${pts[i].split(",")[1]}" r="3" fill="${color}"><title>${esc(lb)}: ${yFmt ? yFmt(nums[i]) : nums[i]}</title></circle>`).join("")
    : "";
  return `<svg class="cf-chart-area" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="tendencia">
    <defs><linearGradient id="cf-grad-${color.replace("#", "")}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${color}" stop-opacity="0.28"/><stop offset="100%" stop-color="${color}" stop-opacity="0.02"/>
    </linearGradient></defs>
    <path d="${fill}" fill="url(#cf-grad-${color.replace("#", "")})"/>
    <path d="${line}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round"/>
    ${dotLabels}
  </svg>`;
}

function lineChart(series, { labels = [], w = 560, h = 200, yFmt = null } = {}) {
  const sets = (series || []).filter((s) => (s.values || []).length >= 2);
  if (!sets.length) return "";
  const n = Math.max(...sets.map((s) => s.values.length));
  const all = sets.flatMap((s) => s.values.map(Number));
  const min = Math.min(0, ...all);
  const max = Math.max(...all, 1);
  const span = max - min || 1;
  const pad = 10;
  const stepX = (w - pad * 2) / (n - 1);
  const x = (i) => pad + i * stepX;
  const y = (v) => h - pad - ((v - min) / span) * (h - pad * 2);
  const grid = [0.25, 0.5, 0.75].map((f) => {
    const yy = y(min + span * f);
    return `<line x1="${pad}" y1="${yy.toFixed(1)}" x2="${(w - pad).toFixed(1)}" y2="${yy.toFixed(1)}" stroke="#eef2f7" stroke-dasharray="3 3"/>`;
  }).join("");
  const paths = sets.map((s) => {
    const pts = (s.values || []).map((v, i) => `${x(i).toFixed(1)},${y(Number(v)).toFixed(1)}`);
    return `<path d="${pts.map((p, i) => (i === 0 ? `M${p}` : `L${p}`)).join(" ")}" fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linecap="round"/>`;
  }).join("");
  const tickEvery = n > 12 ? Math.ceil(n / 12) : 1;
  const labelTicks = labels.length === n
    ? labels.map((lb, i) => (i % tickEvery !== 0 && i !== n - 1 ? "" : `<text x="${x(i).toFixed(1)}" y="${h - 2}" text-anchor="middle" font-size="9" fill="#94a3b8">${esc(lb)}</text>`)).join("")
    : "";
  const legend = sets.map((s) => `<span class="inline-flex items-center gap-1 text-xs font-medium text-slate-500"><span class="w-2.5 h-2.5 rounded-full" style="background:${s.color}"></span>${esc(s.name)}</span>`).join("");
  return `<div><div class="flex flex-wrap gap-3 mb-2">${legend}</div><svg class="cf-chart-area w-full" viewBox="0 0 ${w} ${h}" role="img" aria-label="comparación de estrategias" style="min-height:${h}px">${grid}${paths}${labelTicks}</svg></div>`;
}

function barComparison(values, labels = []) {
  const max = Math.max(1, ...values.map(Math.abs));
  return values
    .map((v, i) => {
      const hite = Math.round((Math.abs(v) / max) * 100);
      const positive = v >= 0;
      return `<div class="flex-1 min-w-5 flex flex-col items-center gap-1" title="${esc(labels[i] || "")}: ${money(v)}">
        <div class="flex items-end justify-center gap-0.5 h-24 w-full">
          <div class="w-2.5 rounded-t transition-all" style="height:${hite}%;background:${positive ? "#19b5a5" : "#e15554"}"></div>
        </div>
        <div class="text-[10px] text-slate-400">${esc(labels[i] || "")}</div>
      </div>`;
    })
    .join("");
}

function progressPct(current, planned) {
  if (!planned) return 0;
  return Math.min(999, Math.round((current / planned) * 100));
}

function progressBar(current, planned, { label = false } = {}) {
  const pct = progressPct(current, planned);
  const state = pct > 100 ? "is-over" : pct >= 80 ? "is-warn" : "is-ok";
  return `
  <div class="flex items-center gap-2">
    <div class="progress-track flex-1"><div class="progress-fill ${state}" style="width:${Math.min(100, pct)}%"></div></div>
    <span class="text-xs font-semibold ${state === "is-over" ? "text-rose-600" : state === "is-warn" ? "text-amber-700" : "text-brand-turquoise-dark"}">${pct}%</span>
  </div>${label ? `<div class="text-xs text-slate-500 mt-1">${money(current)} de ${money(planned)}</div>` : ""}`;
}

/* ---------- UI-3: series mensuales rodantes (12 meses) y por cuenta ---------- */

async function dashboardSeriesFor(year) {
  if (state.rollCache[year] !== undefined) return state.rollCache[year];
  let data = [];
  try {
    const d = await api(`/api/v1/households/${state.householdId}/dashboard?year=${year}&month=1`);
    data = (d.series || []).map((s) => ({ ...s, year: s.year ?? year }));
  } catch {
    data = [];
  }
  state.rollCache[year] = data;
  return data;
}

async function rollSeriesData(year, month, windowSize = 12) {
  const map = {};
  for (const y of [year, year - 1]) {
    for (const s of (await dashboardSeriesFor(y)) || []) {
      if (s && s.month) map[`${s.year}-${s.month}`] = s;
    }
  }
  const out = [];
  for (let i = windowSize - 1; i >= 0; i--) {
    const d = new Date(year, month - 1 - i, 1);
    const base = map[`${d.getFullYear()}-${d.getMonth() + 1}`] || null;
    out.push({
      year: d.getFullYear(),
      month: d.getMonth() + 1,
      income: base?.income ?? 0,
      expenses: base?.expenses ?? 0,
      balance: base?.balance ?? 0,
      expected_income: base?.expected_income ?? 0,
    });
  }
  return out;
}

function rollMonthLabel(month) {
  return "E F M A M J J A S O N D".split(" ")[month - 1] || String(month);
}

function rollMonthFull(year, month) {
  const names = "Ene Feb Mar Abr May Jun Jul Ago Sep Oct Nov Dic".split(" ");
  return `${names[month - 1]} ${year}`;
}

async function loadHouseholdTxns() {
  if (state.householdTxns) return state.householdTxns;
  try {
    state.householdTxns = await api(`/api/v1/transactions?household_id=${state.householdId}`);
  } catch {
    state.householdTxns = [];
  }
  return state.householdTxns;
}

function groupTxnsByAccount(txns) {
  const map = {};
  for (const t of txns || []) {
    for (const id of [t.account_id, t.to_account_id]) {
      if (!id) continue;
      (map[id] = map[id] || []).push(t);
    }
  }
  for (const id of Object.keys(map)) {
    map[id].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }
  return map;
}

function accountLastTxn(txns) {
  const t = (txns || [])
    .filter((x) => x.status !== "voided")
    .sort((a, b) => String(b.date).localeCompare(String(a.date)))[0];
  if (!t) return null;
  return { date: t.date, description: t.description || KIND_LABEL[t.type] || t.type, amount: Number(t.amount || 0), type: t.type };
}

function accountSpark(account, txns) {
  const amounts = (txns || [])
    .filter((t) => t.status !== "voided")
    .map((t) => Number(t.amount) || 0);
  if (amounts.length < 2) return "";
  let running = Number(account.balance_calculated || 0) - amounts.reduce((a, b) => a + b, 0);
  const series = [running];
  for (const a of amounts) {
    running += a;
    series.push(running);
  }
  return sparkline(series, { color: account.type === "credit_card" ? "#b8860b" : "#19b5a5", w: 110, h: 34 });
}

function emptyState(message, action = "") {
  return `<div class="empty-state cf-fade">
    ${svgIcon("M4 7h16M4 7a2 2 0 012-2h12a2 2 0 012 2M4 7v9a2 2 0 002 2h12a2 2 0 002-2V7M9 12h6", 40)}
    <div class="text-sm font-medium">${esc(message)}</div>
    ${action}
  </div>`;
}

function pageHeader(title, subtitle, metaHtml = "") {
  return `<div class="mb-6 flex flex-wrap items-start justify-between gap-3 cf-fade">
    <div>
      <h1 class="text-2xl font-extrabold tracking-tight">${title}</h1>
      <p class="text-sm text-slate-500 mt-0.5">${subtitle}</p>
    </div>
    ${metaHtml ? `<div class="flex flex-wrap items-center gap-2">${metaHtml}</div>` : ""}
  </div>`;
}

function catByColor(categoryId) {
  return colorForId(categoryId);
}

function toast(message, ok = true) {
  const box = document.getElementById("toasts");
  const item = document.createElement("div");
  item.className =
    "px-4 py-3 rounded-lg shadow-lg text-sm font-medium text-white " +
    (ok ? "bg-brand-turquoise" : "bg-rose-600");
  item.textContent = message;
  box.appendChild(item);
  setTimeout(() => item.remove(), 3500);
}

async function api(path, options = {}) {
  const isForm = options.formData instanceof FormData;
  const headers = isForm ? { ...(options.headers || {}) } : { "Content-Type": "application/json", ...(options.headers || {}) };
  let response;
  try {
    response = await fetch(path, {
      method: options.method || "GET",
      headers,
      body: isForm ? options.formData : options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch (error) {
    toast("Sin conexión con el servidor", false);
    throw error;
  }
  let data = null;
  try {
    data = await response.json();
  } catch {
    /* sin cuerpo JSON */
  }
  if (!response.ok) {
    const detail = data && data.detail ? data.detail : `Error ${response.status}`;
    toast(String(detail).slice(0, 200), false);
    throw new Error(detail);
  }
  return data;
}

function field(label, id, type = "text", value = "", extra = {}) {
  const attrs = Object.entries(extra)
    .map(([k, v]) => `${k}="${esc(v)}"`)
    .join(" ");
  return `<div class="${type === "hidden" ? "hidden" : ""}">
    <label class="block text-xs font-semibold text-slate-500 mb-1" for="${id}">${esc(label)}</label>
    <input id="${id}" name="${id}" type="${type}" value="${esc(value)}" ${attrs}
      class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-amber" />
  </div>`;
}

function select(label, id, options, value = "") {
  const opts = options
    .map((o) => {
      const [val, text] = Array.isArray(o) ? o : [o, o];
      return `<option value="${esc(val)}" ${val === value ? "selected" : ""}>${esc(text)}</option>`;
    })
    .join("");
  return `<div>
    <label class="block text-xs font-semibold text-slate-500 mb-1" for="${id}">${esc(label)}</label>
    <select id="${id}" name="${id}" class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-amber">${opts}</select>
  </div>`;
}

function monthOptions() {
  return Array.from({ length: 12 }, (_, i) => [String(i + 1), "Enero Febrero Marzo Abril Mayo Junio Julio Agosto Septiembre Octubre Noviembre Diciembre".split(" ")[i]]);
}

function yearOptions() {
  const now = new Date().getFullYear();
  return Array.from({ length: 5 }, (_, i) => String(now - 2 + i));
}

function modal(id, title, formId, onSubmit, body) {
  const handlerAttr = onSubmit ? `onsubmit="submitForm(event, ${onSubmit})"` : "";
  return `<div id="${id}" class="fixed inset-0 z-40 hidden items-center justify-center bg-brand-navy-dark/50 p-4">
    <div class="w-full max-w-md rounded-xl bg-white shadow-xl p-5">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-bold">${esc(title)}</h3>
        <button type="button" onclick="closeModal('${id}')" class="text-slate-400 hover:text-slate-600 text-xl leading-none">&times;</button>
      </div>
      <form id="${formId}" ${handlerAttr}>${body}
        <div class="mt-5 flex justify-end gap-2">
          <button type="button" onclick="closeModal('${id}')" class="px-4 py-2 rounded-md border border-slate-300 text-sm">Cancelar</button>
          <button type="submit" class="px-4 py-2 rounded-md bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Guardar</button>
        </div>
      </form>
    </div>
  </div>`;
}

function closeModal(id) {
  document.getElementById(id)?.classList.add("hidden");
}

function openModal(id) {
  document.getElementById(id)?.classList.remove("hidden");
}

async function submitForm(event, handler) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  for (const key of Object.keys(data)) {
    if (data[key] === "undefined") delete data[key];
  }
  await handler(data, form);
}

async function withHousehold() {
  if (!state.households.length) return null;
  if (state.householdId && state.households.some((h) => h.id === state.householdId)) {
    return state.households.find((h) => h.id === state.householdId);
  }
  const active = state.households.find((h) => h.status === "active") || state.households[0];
  state.householdId = active.id;
  localStorage.setItem("cf.householdId", active.id);
  return active;
}

async function refreshCatalog(householdId) {
  const [members, accounts, institutions, categories, incomeSources] = await Promise.all([
    api(`/api/v1/households/${householdId}/members`),
    api(`/api/v1/accounts?household_id=${householdId}`),
    api(`/api/v1/financial-institutions`),
    api(`/api/v1/households/${householdId}/categories`),
    api(`/api/v1/households/${householdId}/income-sources`),
  ]);
  state.members = members;
  state.accounts = accounts;
  state.institutions = institutions;
  state.categories = categories;
  state.incomeSources = incomeSources;
}

async function loadState() {
  try {
    state.households = await api("/api/v1/households");
  } catch {
    state.households = [];
  }
}

function renderShell() {
  const activeHash = location.hash || "#/dashboard";
  const visible = NAV.filter((item) => !item.hidden);
  const groups = [];
  for (const item of visible) {
    const g = groups.find((x) => x.name === item.group);
    if (g) g.items.push(item);
    else groups.push({ name: item.group, items: [item] });
  }
  const navHtml = groups
    .map(
      (g) => `
      <div class="mb-1">
        ${g.name && g.name !== "Principal" ? `<div class="side-nav-group-title">${esc(g.name)}</div>` : ""}
        ${g.items
          .map(
            (item) => `<a href="${item.hash}" data-nav="${item.hash}" class="side-link ${activeHash === item.hash || (item.hash === "#/dashboard" && activeHash === "#/") ? "is-active" : ""}">
              <svg class="side-icon" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="${item.icon}"/></svg>
              <span>${esc(item.label)}</span>
            </a>`
          )
          .join("")}
      </div>`
    )
    .join("");
  const options = state.households
    .map(
      (h) =>
        `<option value="${esc(h.id)}" ${h.id === state.householdId ? "selected" : ""}>${esc(h.name)}</option>`
    )
    .join("");
  const mobileLinks = visible
    .filter((i) => ["#/dashboard", "#/income", "#/egresos", "#/imports"].includes(i.hash))
    .map(
      (item) => `<a href="${item.hash}" data-nav="${item.hash}" class="flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium ${
        activeHash === item.hash ? "bg-brand-navy text-white" : "text-slate-600"
      }">${svgIcon(item.icon, 16)}<span>${esc(item.label)}</span></a>`
    )
    .join("");
  root.innerHTML = `
  <div class="app-shell flex min-h-screen">
    <aside id="sidebar" class="sidebar hidden lg:flex flex-col w-64 p-4">
      <div class="flex items-center gap-2 px-2 py-3">
        <img src="/static/brand/CuentaFaro_Isotipo.png" alt="Isotipo CuentaFaro" class="w-10 h-10 object-contain" />
        <div>
          <div class="font-extrabold leading-tight text-brand-navy text-lg">CuentaFaro</div>
          <div class="text-[11px] text-brand-turquoise-dark">Tus finanzas en claro</div>
        </div>
      </div>
      <label for="household-switcher" class="sr-only">Hogar activo</label>
      <select id="household-switcher" class="mt-3 rounded-md border border-slate-300 px-3 py-2 text-xs w-full bg-white focus:outline-none focus:ring-2 focus:ring-brand-amber">
        ${options}
      </select>
      <nav class="mt-4 flex-1 space-y-2" aria-label="Navegación principal">${navHtml}</nav>
      <div class="text-[11px] text-slate-400 px-2 pb-1">CLP · America/Santiago</div>
    </aside>
    <div class="flex-1 flex flex-col min-w-0">
      <header class="lg:hidden bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-3">
        <button onclick="toggleSidebar()" class="text-slate-600" aria-label="Abrir menú">
          ${svgIcon("M4 6h16M4 12h16M4 18h16", 22)}
        </button>
        <span class="flex items-center gap-2 font-extrabold text-brand-navy"><img src="/static/brand/CuentaFaro_Isotipo.png" alt="" class="w-7 h-7 object-contain" />CuentaFaro</span>
        <span class="ml-auto text-xs text-slate-400">${esc((state.households.find((h) => h.id === state.householdId) || {}).name || "")}</span>
      </header>
      <div id="mobile-nav" class="hidden lg:hidden bg-white border-b border-slate-200 px-3 py-2 grid grid-cols-2 gap-1">
        ${mobileLinks}
        <a href="#/config" class="flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium ${activeHash === "#/config" ? "bg-brand-navy text-white" : "text-slate-600"}">${svgIcon("M4 6h16M4 12h16M4 18h16", 16)}<span>Configuración</span></a>
      </div>
      <main id="main" class="flex-1 p-4 lg:p-8 pb-24 lg:pb-8"></main>
      <nav class="mobile-bottom-nav lg:hidden grid grid-cols-4" aria-label="Navegación móvil">
        ${NAV.filter((i) => ["#/dashboard", "#/income", "#/egresos", "#/credit-cards"].includes(i.hash))
          .map(
            (item) => `<a href="${item.hash}" data-nav="${item.hash}" class="flex flex-col items-center gap-0.5 py-2.5 text-[10px] font-semibold ${activeHash === item.hash ? "text-brand-amber-dark" : "text-slate-500"}">
              ${svgIcon(item.icon, 20)}<span>${esc(item.label)}</span></a>`
          )
          .join("")}
      </nav>
      ${fabHtml()}
    </div>
  </div>`;
  const switcher = document.getElementById("household-switcher");
  if (switcher) {
    switcher.addEventListener("change", (e) => {
      state.householdId = e.target.value;
      localStorage.setItem("cf.householdId", state.householdId);
      refreshCatalog(state.householdId).then(route);
    });
  }
}

function fabHtml() {
  const quick = [
    { label: "Registrar gasto", hash: "#/egresos?nuevo=expense", icon: "M12 3v18M17 17l-5 4-5-4M5 7h14M8 3h8" },
    { label: "Registrar ingreso", hash: "#/income?nuevo=income", icon: "M12 3v18M17 7l-5-4-5 4M5 17h14M8 21h8" },
    { label: "Transferencia", hash: "#/egresos?nuevo=transfer", icon: "M8 9h8m-3-3l3 3-3 3M16 15H8m3 3l-3-3 3-3" },
  ];
  return `
  <div class="fab-wrap lg:hidden">
    <div id="fab-menu" class="fab-menu hidden">
      ${quick.map((q) => `<a href="${q.hash}" class="fab-action">${svgIcon(q.icon, 14)}${esc(q.label)}</a>`).join("")}
    </div>
    <button class="fab-main" id="fab-toggle" aria-label="Registro rápido" aria-expanded="false">
      ${svgIcon("M12 5v14M5 12h14", 26)}
    </button>
  </div>`;
}

function toggleSidebar() {
  document.getElementById("mobile-nav").classList.toggle("hidden");
  const expanded = !document.getElementById("mobile-nav").classList.contains("hidden");
  document.querySelectorAll("button[aria-label='Abrir menú']").forEach((b) => (b.setAttribute("aria-expanded", String(expanded))));
}

function wireFab() {
  const fab = document.getElementById("fab-toggle");
  if (!fab) return;
  fab.addEventListener("click", () => {
    const menu = document.getElementById("fab-menu");
    const open = menu.classList.toggle("hidden");
    fab.classList.toggle("open", !open);
    fab.setAttribute("aria-expanded", String(!open));
  });
}

async function ensureReady() {
  await loadState();
  const household = await withHousehold();
  renderShell();
  wireFab();
  if (!household) {
    document.getElementById("main").innerHTML = onboardingHtml();
    document.getElementById("onboarding-form").addEventListener("submit", onboardingSubmit);
    return;
  }
  try {
    await refreshCatalog(household.id);
  } catch {
    /* catálogo opcional */
  }
}

async function route() {
  await loadState();
  const household = await withHousehold();
  renderShell();
  if (!household) {
    document.getElementById("main").innerHTML = onboardingHtml();
    document.getElementById("onboarding-form").addEventListener("submit", onboardingSubmit);
    return;
  }
  try {
    await refreshCatalog(household.id);
  } catch {
    /* catálogo opcional */
  }
  const mainEl = document.getElementById("main");
  const query = location.hash.split("?")[1] || "";
  const params = new URLSearchParams(query);
  const hash = location.hash.split("?")[0] || "#/dashboard";
  document.querySelectorAll("[data-nav]").forEach((a) => {
    const active = a.dataset.nav === hash;
    a.classList.toggle("bg-brand-navy", active);
    a.classList.toggle("text-white", active);
    a.classList.toggle("text-slate-600", !active);
  });
  if (hash.startsWith("#/transactions") || hash.startsWith("#/captures")) {
    location.hash = "#/egresos";
    return;
  }
  if (hash.startsWith("#/payments")) {
    location.hash = "#/debts";
    return;
  }
  if (hash.startsWith("#/income")) {
    if (params.get("nuevo")) state.quickNew = params.get("nuevo");
    return renderIncome(mainEl);
  }
  if (hash.startsWith("#/egresos")) {
    if (params.get("nuevo")) state.quickNew = params.get("nuevo");
    return renderEgresos(mainEl);
  }
  if (hash.startsWith("#/accounts")) return renderAccounts(mainEl);
  if (hash.startsWith("#/credit-cards")) return renderCreditCards(mainEl);
  if (hash.startsWith("#/imports")) return renderImports(mainEl);
  if (hash.startsWith("#/debts")) return renderDebts(mainEl);
  if (hash.startsWith("#/budget")) return renderBudget(mainEl);
  if (hash.startsWith("#/goals")) return renderGoals(mainEl);
  if (hash.startsWith("#/reports")) return renderReports(mainEl);
  if (hash.startsWith("#/notifications")) return renderNotifications(mainEl);
  if (hash.startsWith("#/projections")) return renderProjections(mainEl);
  if (hash.startsWith("#/ai")) return renderAi(mainEl);
  if (hash.startsWith("#/config")) return renderConfig(mainEl);
  return renderDashboard(mainEl);
}

function onboardingHtml() {
  return `
  <div class="max-w-md mx-auto mt-16 bg-white rounded-2xl shadow p-8 text-center">
    <img src="/static/brand/CuentaFaro_Logo_Horizontal.png" alt="CuentaFaro" class="h-16 w-auto mx-auto mb-4 object-contain" />
    <h1 class="text-2xl font-extrabold mb-1">Bienvenido a CuentaFaro</h1>
    <p class="text-sm text-slate-500 mb-6">Crea tu hogar para empezar a registrar ingresos, gastos y deudas.</p>
    <form id="onboarding-form" class="space-y-4 text-left">
      ${field("Nombre del hogar", "name", "text", "", { required: "" })}
      ${field("Zona horaria", "timezone", "text", "America/Santiago")}
      <button type="submit" class="w-full py-3 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white font-bold">Crear hogar</button>
    </form>
  </div>`;
}

async function onboardingSubmit(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    const created = await api("/api/v1/households", { method: "POST", body: data });
    state.householdId = created.id;
    localStorage.setItem("cf.householdId", created.id);
    toast("Hogar creado");
    location.hash = "#/dashboard";
  } catch {
    /* toast ya notificó */
  }
}

/* ---------- Inicio · Financial Command Center (UI-2) ---------- */

async function renderDashboard(mainEl) {
  const now = new Date();
  const year = state.dashboardYear || now.getFullYear();
  const month = state.dashMonth || now.getMonth() + 1;
  const household = state.households.find((h) => h.id === state.householdId) || {};
  mainEl.innerHTML = `<div class="space-y-4"><div class="skeleton h-10"></div><div class="grid grid-cols-2 xl:grid-cols-4 gap-4">${"<div class='skeleton h-32'></div>".repeat(4)}</div></div>`;
  let data, upcoming, debtEvo;
  try {
    data = await api(`/api/v1/households/${state.householdId}/dashboard?year=${year}&month=${month}`);
  } catch {
    return;
  }
  try {
    upcoming = await api(`/api/v1/households/${state.householdId}/upcoming-payments?days=30`);
  } catch {
    upcoming = { pending_installments: [], recurring_minimums: [] };
  }
  try {
    debtEvo = await loadDebtEvolution();
  } catch {
    debtEvo = null;
  }
  let prevDash = null;
  if (month > 1) {
    try {
      prevDash = await api(`/api/v1/households/${state.householdId}/dashboard?year=${year}&month=${month - 1}`);
    } catch {
      prevDash = null;
    }
  }

  const monthNames = "Enero Febrero Marzo Abril Mayo Junio Julio Agosto Septiembre Octubre Noviembre Diciembre".split(" ");
  const series = data.series || [];
  const yearOptions = Array.from({ length: 5 }, (_, i) => String(now.getFullYear() - 2 + i));

  const calcSavings = (income, expenses) => (income > 0 ? (income - expenses) / income : 0);

  /* Salud financiera (fórmula documentada abajo en saludFinanciera()):
     − ahorro (35): 35 · clamp(flujo/ingreso, 0, 1)  → 0 si gastas más de lo que entra
     − deuda  (35): ratio = deuda_actual / máx(1, 12·ingreso_del_mes); 35 · máx(0, 1 − ratio/4)
     − presupuesto (30): adherencia media de categorías con monto asignado. */
  const { health, healthLabel, healthColor, healthParts } = saludFinanciera({ data, month });

  const prevIncome = prevDash ? prevDash.income : null;
  const prevExpenses = prevDash ? prevDash.expenses : null;
  const incomeDelta = prevIncome != null && (prevIncome > 0 || data.income > 0) ? pctDelta(data.income, prevIncome) : null;
  const expensesDelta = prevExpenses != null && (prevExpenses > 0 || data.expenses > 0) ? pctDelta(data.expenses, prevExpenses) : null;

  /* Patrimonio por mes: se camina hacia atrás desde el patrimonio actual restando el flujo de cada mes. */
  const nwSeries = netWorthSeriesData(series, month, data.net_worth);
  const nwPrev = nwSeries[month - 2];
  const nwDelta = nwPrev ? pctDelta(data.net_worth, nwPrev.nw) : null;

  const runningDebt = debtEvo && debtEvo.byMonth.length >= month ? debtEvo.byMonth : null;
  const debtPrev = runningDebt ? runningDebt[month - 2] : null;
  const debtDelta = debtPrev != null && debtPrev != null ? pctDelta(data.total_debt, debtPrev.balance) : null;

  const incomeSpark = series.filter((s) => s.month <= month).map((s) => s.income);
  const expenseSpark = series.filter((s) => s.month <= month).map((s) => s.expenses);
  const nwSpark = nwSeries.map((s) => s.nw);
  const debtSpark = (runningDebt || []).slice(0, month).map((s) => s.balance);

  /* Donut de gastos por categoría con detalle interactivo. */
  const catTot = (data.expense_categories || []).reduce((a, c) => a + c.amount, 0) || 1;
  const donutSegments = (data.expense_categories || []).slice(0, 8).map((c) => ({
    name: c.name,
    value: c.amount,
    color: colorForId(c.name),
  }));
  const catMeta = {};
  for (const c of data.expense_categories || []) {
    const prev = prevDash ? (prevDash.expense_categories || []).find((x) => x.name === c.name) : null;
    const budgetRow = (data.budget || []).find((b) => b.category_name === c.name);
    catMeta[c.name] = {
      amount: c.amount,
      pct: (c.amount / (catTot || 1)) * 100,
      prev: prev ? prev.amount : null,
      budget: budgetRow || null,
      color: colorForId(c.name),
    };
  }
  const legend = (data.expense_categories || [])
    .slice(0, 8)
    .map(
      (c) => `<button type="button" class="flex items-center justify-between gap-2 text-sm w-full text-left px-2 py-1 rounded-md hover:bg-brand-light/60" data-donut-name="${esc(c.name)}">
        <span class="flex items-center gap-2 min-w-0"><span class="inline-block w-2.5 h-2.5 rounded-full shrink-0" style="background:${colorForId(c.name)}"></span><span class="truncate">${esc(c.name)}</span></span>
        <span class="font-semibold whitespace-nowrap">${money(c.amount)} <span class="text-slate-400 text-xs font-medium">${Math.round((c.amount / catTot) * 100)}%</span></span>
      </button>`
    )
    .join("");

  const pendingPays = [
    ...(upcoming.pending_installments || []).map((p) => ({
      id: p.id,
      kind: "inst",
      name: "Cuota de deuda",
      due_date: p.due_date,
      amount: p.total_amount,
      days_left: p.days_left,
    })),
    ...(upcoming.recurring_minimums || []).map((p) => ({
      id: p.debt_id,
      kind: "rec",
      name: `Pago mínimo · ${p.debt_name}`,
      due_date: p.due_date,
      amount: p.minimum_payment,
      days_left: null,
    })),
  ]
    .sort((a, b) => (a.due_date < b.due_date ? -1 : 1))
    .slice(0, 5);

  const insights = buildInsights({ data, month, savingsRate: calcSavings(data.income, data.expenses), health, pendingPays, prevDash });

  const alerts = [];
  if ((data.income === 0 || data.expenses === 0) && month === now.getMonth() + 1 && year === now.getFullYear()) {
    alerts.push(`Este mes no registra ${data.income === 0 && data.expenses === 0 ? "ingresos ni gastos" : data.income === 0 ? "ingresos todavía" : "gastos todavía"}. Define tus <a href="#/income" class="font-medium underline">ingresos fijos</a> y anota movimientos desde <a href="#/egresos" class="font-medium underline">Egresos</a>.`);
  }
  if (data.total_debt > 0 && pendingPays.length > 0) {
    const sumPays = pendingPays.reduce((a, p) => a + p.amount, 0);
    const first = pendingPays[0];
    alerts.push(`Hay ${pendingPays.length === 1 ? "un pago" : `${pendingPays.length} pagos`} próximos de deuda por ${money(sumPays)}; el más cercano vence el ${esc(formatDate(first.due_date))}. <a href="#/debts" class="font-medium underline">Ver en Deudas →</a>`);
  }
  const overBudget = (data.budget || []).filter((r) => r.planned > 0 && r.actual > r.planned);
  if (overBudget.length) {
    alerts.push(`${overBudget.length} categoría(s) superaron su presupuesto del periodo, entre ellas «${esc(overBudget[0].category_name || "sin categoría")}». <a href="#/budget" class="font-medium underline">Revisar presupuesto →</a>`);
  }

  const greeting = (() => {
    const h = now.getHours();
    return h < 12 ? "Buenos días" : h < 19 ? "Buenas tardes" : "Buenas noches";
  })();

  const nwCurrent = nwSeries[month - 1] || { nw: data.net_worth };
  const nwStart = nwSeries[0] || { nw: data.net_worth };
  const patrimonialChangeYear = nwCurrent.nw - nwStart.nw;

  const evoRange = state.patrimonyRange || 12;
  const nwSlice = (() => {
    const slice = [];
    for (let i = month - 1; i >= Math.max(0, month - evoRange); i--) slice.unshift(nwSeries[i]);
    return slice;
  })();

  const evoLabels = {
    6: `Últimos 6 meses`,
    12: `Últimos 12 meses`,
    24: `Historial disponible`,
  };

  mainEl.innerHTML = `
  <div class="mb-5 cf-fade">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <div class="greeting-title">${greeting}, ${esc(household.name || "hogar")}</div>
        <p class="greeting-sub">Aquí tienes el panorama de tus finanzas. · ${esc(data.period)}</p>
      </div>
      <div class="page-toolbar">
        <select id="dash-month" class="rounded-md border border-slate-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-amber" aria-label="Mes">
          ${monthNames.map((n, i) => `<option value="${i + 1}" ${i + 1 === month ? "selected" : ""}>${n}</option>`).join("")}
        </select>
        <select id="dash-year" class="rounded-md border border-slate-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-amber" aria-label="Año">
          ${yearOptions.map((y) => `<option value="${y}" ${y === String(year) ? "selected" : ""}>${y}</option>`).join("")}
        </select>
      </div>
    </div>
  </div>
  ${alerts.length
    ? `<div class="mb-5 space-y-2">${alerts
        .map(
          (a) => `<div role="alert" class="rounded-lg bg-brand-amber/15 border border-brand-amber/40 px-4 py-3 text-sm text-amber-900">${a}</div>`
        )
        .join("")}</div>`
    : ""}
  <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
    ${kpiCard({ label: "Patrimonio neto", value: money(data.net_worth), delta: nwDelta, icon: "M12 5l9 12-9-5-9 5z", color: "#123b4a", spark: sparkline(nwSpark, { color: "#123b4a" }), footer: `${patrimonialChangeYear >= 0 ? "+" : "−"}${money(Math.abs(patrimonialChangeYear))} en lo que va del año`, href: "#/accounts" })}
    ${kpiCard({ label: "Ingresos del mes", value: money(data.income), delta: incomeDelta, icon: "M12 3v18M17 7l-5-4-5 4M5 17h14M8 21h8", color: "#19b5a5", spark: sparkline(incomeSpark, { color: "#19b5a5" }), footer: `esperado ${money(data.expected_income)}/mes · <a href="#/income" class="underline">ver en Ingresos</a>`, href: "#/income" })}
    ${kpiCard({ label: "Gastos del mes", value: money(data.expenses), delta: expensesDelta != null ? -expensesDelta : null, invert: true, icon: "M12 3v18M17 17l-5 4-5-4M5 7h14M8 3h8", color: "#e15554", spark: sparkline(expenseSpark, { color: "#e15554" }), footer: `<a href="#/egresos" class="underline">ver en Egresos</a>`, href: "#/egresos" })}
    ${kpiCard({ label: "Deuda total", value: money(data.total_debt), delta: debtDelta, icon: "M3 10h18M8 21V10M16 21V10M5 21h14M5 7l2-3h10l2 3z", color: "#b8860b", spark: debtSpark.length > 1 ? sparkline(debtSpark, { color: "#b8860b" }) : "", footer: pendingPays.length ? `próximos: ${money(pendingPays.reduce((a, p) => a + p.amount, 0))}` : "sin pagos próximos", href: "#/debts" })}
  </div>

  <div class="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
    <div class="cf-card xl:col-span-2">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-bold">Flujo de dinero · ${esc(data.period)}</h2>
        <span class="text-xs text-slate-400">¿dónde terminó el dinero del mes?</span>
      </div>
      ${data.income > 0 || data.expenses > 0
        ? moneyFlowSankey({ income: data.income, expenses: data.expenses, cats: (data.expense_categories || []).slice(0, 8), totalLabel: money(data.income) })
        : emptyCompact("Todavía no hay flujo para este periodo. Registra ingresos y gastos para ver a dónde va tu dinero.", `<a href="#/egresos" class="mt-3 inline-flex px-4 py-2 rounded-lg bg-brand-navy text-white text-sm font-semibold no-underline">Nuevo gasto</a>`)}
    </div>
    <div class="cf-card">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-bold">Gastos por categoría</h2>
        <a href="#/egresos" class="text-xs font-semibold text-brand-amber-dark hover:underline">detalle →</a>
      </div>
      ${(data.expense_categories || []).length
        ? `<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div class="donut-wrap">${donutSvg(donutSegments, { size: 178, thickness: 24, centerLabel: "gastos", centerValue: moneyCompact(data.expenses) })}</div>
            <div class="space-y-1 self-center">
              ${legend}
              <div id="donut-detail" class="mt-2 rounded-lg bg-brand-light/60 border border-brand-turquoise/20 p-3 text-xs text-slate-600">
                Pasa el cursor por el donut o la lista para ver el detalle por categoría.
              </div>
            </div>
          </div>`
        : emptyCompact("Sin gastos este periodo.")}
    </div>
  </div>

  <div class="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
    <div class="cf-card">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-bold">Salud financiera</h2>
        <span tabindex="0" class="text-xs font-semibold text-slate-400 tooltip-hover" data-tip="Ahorro (35) + Deuda controlada (35) + Adherencia al presupuesto (30). Fórmula completa en docs/architecture.md">fórmula ⓘ</span>
      </div>
      ${health == null
        ? emptyCompact("Necesitamos más historial para calcular tu salud financiera. Con 2 o más meses de movimientos la tendremos.")
        : `<div class="donut-wrap">
            <div style="width:180px;height:180px;margin:0 auto">${gaugeSvg(health, healthColor)}</div>
            <div class="donut-center">
              <div class="text-[11px] uppercase tracking-wide text-slate-400">Puntaje</div>
              <div class="text-4xl font-extrabold" style="color:${healthColor}">${health}</div>
              <div class="text-sm font-semibold text-slate-600 mt-1">${healthLabel}</div>
            </div>
          </div>
          <div class="mt-3 space-y-2 text-xs text-slate-500">
            ${healthParts.map((p) => `<div class="flex justify-between"><span>${esc(p.label)}</span><span class="font-semibold">${p.value} / ${p.max}</span></div>`).join("")}
          </div>`}
    </div>
    <div class="cf-card xl:col-span-2">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-bold">Evolución del patrimonio neto</h2>
        <div class="flex gap-1">
          ${[6, 12, 24].map((r) => `<button onclick="setPatrimonyRange(${r})" class="tab-pill ${evoRange === r ? "is-active" : ""}">${r}m</button>`).join("")}
        </div>
      </div>
      ${nwSlice.length >= 2
        ? `<div class="table-scroll">${areaChart(nwSlice.map((s) => s.nw), { labels: nwSlice.map((s) => monthLabelShort(s.month)), w: 520, h: 160, color: "#123b4a", yFmt: moneyCompact })}</div>
           <div class="mt-2 flex items-center justify-between text-xs text-slate-500">
             <span>${evoLabels[evoRange]}</span>
             <span>Patrimonio hoy: <b class="text-slate-700">${money(data.net_worth)}</b></span>
           </div>`
        : emptyCompact("Aún no hay suficiente historial para graficar la evolución del patrimonio.")}
    </div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
    <div class="cf-card">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-bold">Próximos pagos</h2>
        <a href="#/debts" class="text-xs font-semibold text-brand-amber-dark hover:underline">todos →</a>
      </div>
      ${pendingPays.length
        ? `<div class="space-y-2">${pendingPays.map((p) => `<div class="flex items-center justify-between gap-3 py-2 border-b last:border-0">
            <div class="min-w-0">
              <div class="text-sm font-medium truncate">${esc(p.name)}</div>
              <div class="text-xs text-slate-400">vence ${esc(formatDate(p.due_date))}</div>
            </div>
            <div class="text-right flex items-center gap-3">
              <div class="font-bold">${money(p.amount)}</div>
              <span class="state-badge ${p.days_left != null && p.days_left <= 3 ? "excedido" : p.days_left != null && p.days_left <= 7 ? "atencion" : "bien"}">${p.days_left != null ? `en ${p.days_left} día${p.days_left === 1 ? "" : "s"}` : "mínimo"}</span>
            </div>
          </div>`).join("")}</div>`
        : emptyCompact("No hay pagos próximos en los próximos 30 días.")}
    </div>
    <div class="cf-card">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-bold">Insights de CuentaFaro</h2>
        <span class="text-xs text-slate-400">basados en tus datos</span>
      </div>
      ${insights.length
        ? `<div class="insight-list">${insights.map((i) => `<div class="insight-item">
            <span class="insight-icon" style="background:${i.color || "rgba(230,244,241,1)"};color:${i.fg || "var(--cf-navy)"}">${esc(i.icon)}</span>
            <div class="min-w-0">${i.text}${i.href ? ` <a href="${esc(i.href)}" class="font-semibold text-brand-amber-dark underline">ver →</a>` : ""}</div>
          </div>`).join("")}</div>`
        : emptyCompact("Aún no hay observaciones con los datos actuales.")}
    </div>
  </div>

  ${(data.budget || []).length
    ? `<div class="cf-card mb-6">
        <div class="flex items-center justify-between mb-3">
          <h2 class="font-bold">Presupuesto vs real · ${esc(data.period)}</h2>
          <a href="#/budget" class="text-sm font-semibold text-brand-amber-dark hover:underline">Administrar presupuesto →</a>
        </div>
        <div class="table-scroll"><table class="cf-table">
          <thead><tr><th>Categoría</th><th class="text-right">Presupuesto</th><th class="text-right">Real</th><th class="text-right">Diferencia</th><th class="w-2/5 hidden md:table-cell">Uso</th></tr></thead>
          <tbody>${(data.budget || [])
            .map(
              (row) => `<tr>
                <td>${esc(row.category_name || "Sin categoría")}</td>
                <td class="text-right">${money(row.planned)}</td>
                <td class="text-right">${money(row.actual)}</td>
                <td class="text-right font-semibold ${row.planned > 0 && row.actual > row.planned ? "text-rose-600" : "text-brand-turquoise-dark"}">${money(row.actual - row.planned)}</td>
                <td class="hidden md:table-cell">${row.planned > 0 ? progressBar(row.actual, row.planned) : `<span class="text-xs text-slate-400">sin asignación</span>`}</td>
              </tr>`
            )
            .join("")}</tbody>
        </table></div>
      </div>` : ""}
  `;
  wireDonut(mainEl, catMeta, catTot);
  const yearSel = document.getElementById("dash-year");
  const monthSel = document.getElementById("dash-month");
  if (yearSel) {
    yearSel.addEventListener("change", () => {
      state.dashboardYear = Number(yearSel.value) || null;
      route();
    });
  }
  if (monthSel) {
    monthSel.addEventListener("change", () => {
      state.dashMonth = Number(monthSel.value) || null;
      route();
    });
  }
}

function setPatrimonyRange(range) {
  state.patrimonyRange = range;
  route();
}

function netWorthSeriesData(series, month, current) {
  const out = [];
  let acc = current;
  for (let m = month; m >= 1; m--) {
    const s = series.find((x) => x.month === m);
    out[m - 1] = { month: m, nw: acc };
    acc -= s ? s.balance : 0;
  }
  return out;
}

function saludFinanciera({ data, month }) {
  const series = data.series || [];
  const monthsWithData = series.filter((s) => s.income > 0 || s.expenses > 0).length;
  const healthBar = budgetHealthBar(data.budget);
  const savingsRate = data.income > 0 ? (data.income - data.expenses) / data.income : 0;
  const debtRatio = data.total_debt > 0 ? data.total_debt / Math.max(1, 12 * Math.max(data.income, 1)) : 0;
  const parts = [
    { label: "Ahorro del periodo", value: Math.round(35 * Math.max(0, Math.min(1, savingsRate))), max: 35 },
    { label: "Deuda controlada", value: Math.round(35 * Math.max(0, 1 - debtRatio / 4)), max: 35 },
    { label: "Adherencia al presupuesto", value: Math.round(30 * Math.max(0, Math.min(1, healthBar))), max: 30 },
  ];
  const health =
    monthsWithData >= 2
      ? Math.round(Math.max(0, Math.min(100, parts.reduce((a, p) => a + p.value, 0))))
      : null;
  const label =
    health == null ? "Necesitamos 2+ meses de historial" : health >= 80 ? "Sólida" : health >= 60 ? "En camino" : health >= 40 ? "Atención" : "Riesgo";
  const color = health == null ? "#94a3b8" : health >= 60 ? "#19b5a5" : health >= 40 ? "#f4b942" : "#e15554";
  return { health, healthLabel: label, healthColor: color, healthParts: parts, savingsRate };
}

/* Flujo de dinero estilo Sankey ligero (SVG + columnas proporcionadas). */
function moneyFlowSankey({ income, expenses, cats, totalLabel }) {
  const saved = income - expenses;
  const segs = [];
  for (const c of cats) segs.push({ name: c.name, amount: Math.max(0, c.amount || 0), color: colorForId(c.name) });
  if (saved > 0) segs.push({ name: "Ahorro / diferencia", amount: saved, color: "#19b5a5" });
  else if (saved < 0) segs.push({ name: "Déficit del mes", amount: -saved, color: "#e15554" });
  if (segs.length === 0) return emptyCompact("Sin flujo para este periodo.");

  const H = 168;
  const inTop = 26;
  const bandX = 116;
  const bandW = 46;
  const outX = bandX + bandW;
  const outW = 172;
  const scale = Math.max(income, expenses, 1);
  const hOf = (v, over) => Math.max(0, Math.round((v / scale) * (H - inTop)));
  const incomeH = hOf(income);

  let y = inTop;
  const bands = segs.map((s) => {
    const hh = hOf(s.amount);
    const b = { s, y, hh, top: y, bottom: y + hh };
    y += hh;
    return b;
  });

  const svgBands = bands
    .map((b) => `<path class="sankey-ribbon" data-ribbon="${esc(b.s.name)}" d="M${bandX},${b.top} C${bandX + bandW * 0.6},${b.top} ${outX - bandW * 0.4},${b.top + b.hh * 0.12} ${outX},${b.top + b.hh * 0.12} L${outX},${b.top + b.hh * 0.88} C${outX - bandW * 0.4},${b.top + b.hh * 0.88} ${bandX + bandW * 0.6},${b.bottom} ${bandX},${b.bottom} Z" fill="${b.s.color}" fill-opacity="0.92"><title>${esc(b.s.name)}: ${money(b.s.amount)}</title></path>`)
    .join("");

  const outRows = bands
    .map((b) => {
      const pct = Math.round((Math.abs(b.s.amount) / scale) * 100);
      return `<div data-ribbon-target="${esc(b.s.name)}">
        <div class="flex items-center justify-between text-xs mb-1">
          <span class="flex items-center gap-1.5 min-w-0"><span class="w-2 h-2 rounded-full shrink-0" style="background:${b.s.color}"></span><span class="truncate font-medium">${esc(b.s.name)}</span></span>
          <span class="flex items-center gap-2 shrink-0 ml-2"><span class="font-bold">${money(b.s.amount)}</span><span class="text-slate-400 w-8 text-right">${pct}%</span></span>
        </div>
        <div class="h-3.5 rounded bg-slate-100 overflow-hidden"><div class="h-full rounded" style="width:${Math.max(2, pct)}%;background:${b.s.color}"></div></div>
      </div>`;
    })
    .join("");

  return `<div class="sankey cf-fade">
    <div class="sankey-node sankey-in">
      <div class="sn-head">Ingresos</div>
      <div class="sankey-bars" style="height:${H}px">
        <div class="sankey-bar" style="height:${Math.max(2, incomeH)}px;background:linear-gradient(180deg,#19b5a5,#0e8779)">${moneyCompact(income)}</div>
      </div>
    </div>
    <svg class="sankey-ribbons shrink-0" width="${bandW}" height="${H}" viewBox="0 0 ${bandW} ${H}" style="margin-top:${inTop}px" role="img" aria-label="¿A dónde fue el dinero del mes?">
      ${svgBands}
    </svg>
    <div class="sankey-node sankey-out">
      <div class="sn-head">A dónde fue (${moneyCompact(expenses)} gastados)</div>
      <div class="flex flex-col justify-start gap-2.5" style="height:${H}px">
        ${outRows}
      </div>
    </div>
  </div>`;
}

function emptyCompact(message, action = "") {
  return `<div class="empty-compact cf-fade">
    ${svgIcon("M9.2 4.8A2.9 2.9 0 0114.2 6l.1.9M9.5 7H5.6A1.8 1.8 0 004 9v9a1.8 1.8 0 001.8 1.8h12A1.8 1.8 0 0019.6 18v-5.4M14 14l8-8M16 5.5l1.5 1.5L21 3.5", 22)}
    <div class="flex-1 min-w-0"><span class="text-sm font-medium text-slate-600">${esc(message)}</span>${action}</div>
  </div>`;
}

/* Evolución de la deuda por mes, desde los pagos reales registrados. */
async function loadDebtEvolution() {
  const debts = await api(`/api/v1/households/${state.householdId}/debts`);
  const withPayments = await Promise.all(
    debts.map(async (d) => {
      let payments = [];
      try {
        payments = await api(`/api/v1/debts/${d.id}/payments`);
      } catch {
        payments = [];
      }
      return { ...d, payments };
    })
  );
  const now = new Date();
  const year = state.dashboardYear || now.getFullYear();
  const month = state.dashMonth || now.getMonth() + 1;
  const current = withPayments.reduce((a, d) => a + (d.current_balance || 0), 0);
  const byMonth = [];
  let future = 0;
  const paidDates = [];
  for (const d of withPayments) for (const p of d.payments || []) paidDates.push(String(p.payment_date).slice(0, 10));
  paidDates.sort();
  for (let m = month; m >= 1; m--) {
    while (paidDates.length && paidDates[paidDates.length - 1] > `${year}-${String(m).padStart(2, "0")}-31`) {
      future += 1;
      paidDates.pop();
    }
    byMonth[m - 1] = { month: m, balance: current + future * 1_000_000 };
  }
  return { current, byMonth };
}

function wireDonut(container, catMeta, total) {
  const detailEl = container.querySelector("#donut-detail");
  if (!detailEl) return;
  const show = (name) => {
    const m = catMeta[name];
    if (!m) return;
    const budget = m.budget;
    const rows = [];
    rows.push(`<div class="flex items-center justify-between gap-2"><span class="font-semibold text-slate-700">${esc(name)}</span><span class="font-bold">${money(m.amount)}</span></div>`);
    rows.push(`<div class="text-slate-500">${m.pct.toFixed(1).replace(".", ",")}% del total del mes</div>`);
    if (m.prev != null) {
      const d = pctDelta(m.amount, m.prev);
      rows.push(`<div class="${d > 0 ? "text-rose-600" : d < 0 ? "text-brand-turquoise-dark" : "text-slate-500"}">${d > 0 ? "↑" : d < 0 ? "↓" : "→"} ${Math.abs(d).toFixed(1).replace(".", ",")}% vs mes anterior</div>`);
    }
    if (budget && budget.planned > 0) {
      const used = budget.actual > budget.planned ? "is-over" : budget.actual >= budget.planned * 0.8 ? "is-warn" : "is-ok";
      rows.push(`<div>Presupuesto: ${money(budget.planned)} · <b>${Math.round((budget.actual / budget.planned) * 100)}% usado</b></div>`);
    }
    detailEl.innerHTML = rows.join("");
  };
  container.querySelectorAll(".donut-segment").forEach((el) => {
    el.addEventListener("mouseenter", () => show(el.dataset.name));
    el.addEventListener("focus", () => show(el.dataset.name));
    el.tabIndex = 0;
    el.setAttribute("role", "button");
  });
  container.querySelectorAll("[data-donut-name]").forEach((el) => {
    el.addEventListener("mouseenter", () => show(el.dataset.donutName));
    el.addEventListener("focus", () => show(el.dataset.donutName));
  });
}

function moneyCompact(n) {
  const abs = Math.abs(Number(n) || 0);
  if (abs >= 1_000_000) return `$${(Number(n) / 1_000_000).toFixed(1).replace(".", ",")}M`;
  if (abs >= 1_000) return `$${Math.round(Number(n) / 1_000)}K`;
  return money(n);
}

function budgetHealthBar(budgetRows) {
  const rows = (budgetRows || []).filter((r) => r.planned > 0);
  if (rows.length === 0) return 1;
  const adherence = rows.map((r) => Math.max(0, Math.min(1.5, 1 - (r.actual - r.planned) / r.planned)));
  return adherence.reduce((a, v) => a + v, 0) / rows.length;
}

function gaugeSvg(value, color) {
  const r = 80;
  const circ = 2 * Math.PI * r;
  const filled = (Math.max(0, Math.min(100, value)) / 100) * circ;
  return `<svg width="180" height="180" viewBox="0 0 180 180" class="-scale-x-100" role="img" aria-label="Salud ${value} de 100">
    <circle cx="90" cy="90" r="${r}" fill="none" stroke="#e2e8f0" stroke-width="16"/>
    <circle cx="90" cy="90" r="${r}" fill="none" stroke="${color}" stroke-width="16" stroke-linecap="round"
      stroke-dasharray="${filled.toFixed(2)} ${circ.toFixed(2)}" stroke-dashoffset="0"/>
  </svg>`;
}

function buildInsights({ data, month, savingsRate, health }) {
  const out = [];
  if (data.income > 0 && savingsRate < -0.02) {
    out.push({ icon: "!", text: `Este mes se gastó más de lo que ingresó (déficit de ${money(Math.abs(data.balance))}). Revisa tus gastos para no recortar tu patrimonio.`, href: "#/egresos" });
  } else if (data.income > 0 && savingsRate >= 0.1) {
    out.push({ icon: "✓", text: `Lograste ahorrar ${Math.round(savingsRate * 100)}% de tus ingresos del mes (${money(Math.abs(data.balance))}).`, href: "#/dashboard" });
  }
  const overs = (data.budget || []).filter((r) => r.planned > 0 && r.actual > r.planned);
  if (overs.length) {
    const top = overs[0];
    out.push({ icon: "!", text: `La categoría «${esc(top.category_name || "sin categoría")}» superó su presupuesto (${money(top.actual)} contra ${money(top.planned)}).`, href: "#/budget" });
  }
  if (data.total_debt > 0 && data.income > 0) {
    const monthsToClear = data.total_debt / Math.max(1, data.income);
    out.push({
      icon: "≈",
      text: monthsToClear <= 3
        ? `Tu deuda equivale a ${monthsToClear.toFixed(1).replace(".", ",")} meses de ingresos: está en un rango manejable.`
        : `Tu deuda equivale a ${monthsToClear.toFixed(0)} meses de ingresos. Reducirla acelera tu patrimonio.`,
      href: "#/debts",
    });
  }
  const cats = data.expense_categories || [];
  if (cats.length >= 2) {
    const topCat = cats[0];
    out.push({ icon: "%", text: `«${esc(topCat.name)}» concentra el ${Math.round((topCat.amount / Math.max(1, cats.reduce((a, c) => a + c.amount, 0))) * 100)}% de tus gastos del mes.`, href: "#/reports" });
  }
  if (health != null && health < 40) {
    out.push({ icon: "!", text: "Tu puntaje de salud financiera está en zona de riesgo. Prioriza reducir deuda y ajustar el presupuesto.", href: "#/budget" });
  }
  return out.slice(0, 5);
}

/* ---------- Cuentas e instituciones (CF1-24) ---------- */

function accountsModalHtml() {
  return modal("acc-modal", "Nueva cuenta", "acc-form", "createAccount",
    `${field("Nombre", "name", "text", "", { required: "" })}
     ${select("Tipo", "type", [["checking", "Corriente"], ["savings", "Ahorro"], ["credit_card", "Tarjeta de crédito"], ["cash", "Efectivo"], ["investment", "Inversión"], ["wallet", "Billetera"], ["loan_line", "Línea de crédito"], ["other", "Otras"]], "checking")}
     ${field("Cupo / límite de crédito (CLP)", "credit_limit", "number", "", { step: "1", placeholder: "Solo tarjetas de crédito" })}
     ${field("Día de cierre — corte (solo tarjetas)", "statement_day", "number", "", { min: "1", max: "31", placeholder: "Ej: 5" })}
     ${field("Día de vencimiento — pago (solo tarjetas)", "due_day", "number", "", { min: "1", max: "31", placeholder: "Ej: 20" })}
     ${field("Saldo informado (CLP)", "balance_reported", "number", "0", { step: "1" })}
     <p class="text-xs text-slate-500 -mt-1">El cupo se usa para calcular la utilización de tarjetas (saldo ÷ cupo). Las tarjetas de crédito como cuenta se suman a tu patrimonio; la cuota pendiente vive en Deudas.</p>`);
}

function accountsPanelHtml() {
  const accRows =
    state.accounts && state.accounts.length
      ? state.accounts
          .map(
            (a) => `<tr>
              <td class="px-3 py-2"><div class="font-medium">${esc(a.name)}</div><div class="text-xs text-slate-400">${esc(ACCOUNT_TYPE_LABEL[a.type] || a.type)}</div></td>
              <td class="px-3 py-2 text-right">${money(a.balance_calculated)}</td>
              <td class="px-3 py-2 text-right text-slate-400 hidden md:table-cell">${money(a.balance_reported)}</td>
              <td class="px-3 py-2"><span class="px-2 py-0.5 rounded-full text-xs ${a.status === "active" ? "bg-brand-turquoise/20 text-brand-turquoise-dark" : "bg-slate-200 text-slate-500"}">${esc(a.status)}</span></td>
            </tr>`
          )
          .join("")
      : `<tr><td class="px-3 py-6 text-center text-slate-400" colspan="4">Aún no hay cuentas</td></tr>`;
  return `
    <div class="cf-card">
      <h2 class="font-bold mb-3">Cuentas
        <button onclick="openModal('acc-modal')" class="ml-2 px-3 py-1 rounded-md bg-brand-navy hover:bg-brand-navy-dark text-white text-xs font-semibold">Nueva cuenta</button>
      </h2>
      <div class="overflow-x-auto"><table class="cf-table w-full">
        <thead><tr><th>Cuenta</th><th class="text-right">Calculado</th><th class="text-right hidden md:table-cell">Informado</th><th>Estado</th></tr></thead>
        <tbody>${accRows}</tbody>
      </table></div>
    </div>
    ${accountsModalHtml()}
  `;
}

function acctTxnRow(t, account) {
  const resolved = t.scheduled_id ? { date: t.date, description: t.description || "Movimiento programado", amount: t.amount, type: t.type } : t;
  const sign = resolved.type === "expense" ? "-" : resolved.type === "transfer_out" ? "-" : "+";
  return `<tr>
    <td class="px-3 py-1.5 text-xs text-slate-500">${esc(resolved.date)}</td>
    <td class="px-3 py-1.5">${esc(resolved.description)}</td>
    <td class="px-3 py-1.5 text-right font-semibold ${sign === "-" ? "text-rose-600" : "text-brand-turquoise-dark"}">${sign}${money(resolved.amount)}</td>
  </tr>`;
}

function acctTxnRows(txns, account) {
  return `
  <thead><tr><th>Fecha</th><th>Concepto</th><th class="text-right">Monto</th></tr></thead>
  <tbody>${(txns || []).length ? txns.map((t) => acctTxnRow(t, account)).join("") : `<tr><td colspan="3" class="text-center text-slate-400 py-4">Sin movimientos</td></tr>`}</tbody>`;
}

function accBalanceSeries(account, txns) {
  const base = (txns || []).filter((t) => t.status !== "voided").slice().reverse();
  let running = Number(account.balance_calculated || 0);
  return base.map((t) => {
    const amount = Number(t.amount) || 0;
    const reduced = t.type === "expense" || t.type === "payment" || t.type === "transfer";
    running += reduced ? amount : -amount;
    return { date: t.date, label: t.description || KIND_LABEL[t.type] || t.type, amount, balance: running };
  });
}

function toggleAccTab(accountId, tab) {
  state.accTab = tab;
  renderAccDetail(accountId);
}

function toggleAccDetail(accountId) {
  if (state.selectedAccountId === accountId) {
    state.selectedAccountId = null;
    route();
  } else {
    state.selectedAccountId = accountId;
    renderAccDetail(accountId);
  }
}

async function renderAccDetail(accountId) {
  const account = (state.accounts || []).find((a) => String(a.id) === String(accountId));
  const panelEl = document.getElementById("acc-detail");
  if (!account || !panelEl) return;
  let card = null;
  if (account.type === "credit_card") {
    try {
      card = await cardDetailData(account);
    } catch {
      card = { debts: [], installments: [], payments: [] };
    }
    if (document.getElementById("acc-detail") !== panelEl) return;
  }
  panelEl.innerHTML = accDetailPanel(account, card);
}

async function cardDetailData(account) {
  let debts = state.debts || [];
  if (!debts.length) {
    try {
      debts = await api(`/api/v1/households/${state.householdId}/debts`);
    } catch {
      debts = [];
    }
  }
  const linked = (debts || []).filter((d) => String(d.account_id || "") === String(account.id));
  const installments = [];
  const payments = [];
  for (const d of linked) {
    try {
      const dbInstallments = await api(`/api/v1/debts/${d.id}/installments`);
      (dbInstallments || []).forEach((i) => installments.push({ ...i, debt_name: d.name }));
    } catch {
      /* sin cuotas */
    }
    try {
      const dbPayments = await api(`/api/v1/debts/${d.id}/payments`);
      (dbPayments || []).forEach((p) => payments.push({ ...p, debt_name: d.name }));
    } catch {
      /* sin pagos */
    }
  }
  return { debts: linked, installments, payments };
}

function accTabsHtml(accountId, isCard) {
  const tabs = isCard
    ? ["resumen", "movimientos", "estado-cuenta", "cuotas", "pagos"]
    : ["resumen", "movimientos", "ingresos", "egresos", "historial"];
  const labels = {
    resumen: "Resumen",
    movimientos: "Movimientos",
    "estado-cuenta": "Estado de cuenta",
    cuotas: "Cuotas",
    pagos: "Pagos",
    ingresos: "Ingresos",
    egresos: "Egresos",
    historial: "Historial",
  };
  const active = tabs.includes(state.accTab) ? state.accTab : "resumen";
  return `
  <div class="flex flex-wrap gap-1 mb-3 border-b border-slate-100 pb-2">
    ${tabs
      .map(
        (key) => `<button onclick="toggleAccTab('${accountId}', '${key}')" class="px-2.5 py-1 rounded-md text-sm font-semibold transition ${active === key ? "bg-brand-turquoise/20 text-brand-turquoise-dark" : "text-slate-500 hover:bg-slate-100"}">${labels[key]}</button>`
      )
      .join("")}
  </div>`;
}

function cardAlertLevel(usagePct) {
  if (usagePct == null) return null;
  if (usagePct < 70) return { label: "Saludable", cls: "bien" };
  if (usagePct < 90) return { label: "Atención", cls: "atencion" };
  return { label: "Crítico", cls: "excedido" };
}

function cardStatementWindow(account) {
  const cutoff = Math.min(31, Math.max(1, Number(account.statement_day) || 5));
  const now = new Date();
  const cy = now.getFullYear();
  const cm = now.getMonth() + 1;
  const from = now.getDate() >= cutoff ? new Date(cy, cm - 1, cutoff) : new Date(cy, cm - 2, cutoff);
  const to = now.getDate() >= cutoff ? new Date(cy, cm, cutoff) : new Date(cy, cm - 1, cutoff);
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const fromIso = iso(from);
  const toIso = iso(to);
  const inWin = (t) => {
    const s = String(t.date || t.payment_date || "");
    return s >= fromIso && s < toIso;
  };
  return { fromIso, toIso, inWin };
}

function cardUsage(account) {
  const cupo = Math.max(0, Number(account.credit_limit) || 0);
  const reported = Math.max(0, Number(account.balance_reported) || 0);
  const calc = Math.max(0, Number(account.balance_calculated) || 0);
  const usage = cupo > 0 ? Math.round((calc / cupo) * 100) : reported > 0 ? Math.round((calc / reported) * 100) : null;
  return { cupo, reported, calc, usage, alerta: cardAlertLevel(usage) };
}

function accDetailPanel(account, card) {
  const txnMap = groupTxnsByAccount(state.householdTxns);
  const txns = txnMap[account.id] || [];
  const base = txns.filter((t) => t.status !== "voided");
  const isCard = account.type === "credit_card";
  const incomes = base.filter((t) => t.type === "income");
  const expenses = base.filter((t) => t.type === "expense");
  const last = accountLastTxn(txns);
  const avg = base.length ? Math.round(base.reduce((a, c) => a + (Number(c.amount) || 0), 0) / base.length) : 0;
  const running = accBalanceSeries(account, base);
  const untilNext = `${esc(account.name)} · saldo calculado ${money(account.balance_calculated || 0)}`;
  let body;
  if (state.accTab === "movimientos") {
    body = `<div class="max-h-72 overflow-auto"><table class="cf-table w-full">${acctTxnRows(base)}</table></div>`;
  } else if (isCard && state.accTab === "estado-cuenta") {
    body = estadoCuentaBody(account, card);
  } else if (isCard && state.accTab === "cuotas") {
    body = cuotasBody(card);
  } else if (isCard && state.accTab === "pagos") {
    body = pagosBody(account, card);
  } else if (!isCard && state.accTab === "ingresos") {
    body = incomes.length ? `<div class="max-h-72 overflow-auto"><table class="cf-table w-full">${acctTxnRows(incomes)}</table></div>` : emptyState("Sin movimientos de ingreso en esta cuenta.");
  } else if (!isCard && state.accTab === "egresos") {
    body = expenses.length ? `<div class="max-h-72 overflow-auto"><table class="cf-table w-full">${acctTxnRows(expenses)}</table></div>` : emptyState("Sin movimientos de egreso en esta cuenta.");
  } else if (!isCard && state.accTab === "historial") {
    body = `<div class="max-h-72 overflow-auto"><table class="cf-table w-full">
        <thead><tr><th>Fecha</th><th>Concepto</th><th class="text-right">Monto</th><th class="text-right">Saldo</th></tr></thead>
        <tbody>${running
          .slice()
          .reverse()
          .map((r) => `<tr><td class="text-slate-500">${esc(r.date)}</td><td>${esc(r.label)}</td><td class="text-right">${money(r.amount)}</td><td class="text-right font-semibold ${r.balance < 0 ? "text-rose-600" : "text-brand-navy"}">${money(r.balance)}</td></tr>`)
          .join("")}</tbody>
      </table></div>`;
  } else if (isCard && state.accTab === "resumen" || isCard && !["movimientos", "estado-cuenta", "cuotas", "pagos", "ingresos", "egresos", "historial"].includes(state.accTab)) {
    const { cupo, usage, alerta } = cardUsage(account);
    body = `
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        ${kpiCard({ label: "Saldo deudor", value: money(account.balance_calculated || 0), icon: "M12 3v18M5 7h14M8 3h8M5 17h14", color: (account.balance_calculated || 0) < 0 ? "#e15554" : "#123b4a" })}
        ${kpiCard({ label: "Cupo", value: money(cupo), icon: "M2 10h20M2 14h20M6 6h12a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2z", color: "#b8860b" })}
        ${kpiCard({ label: "Utilización", value: usage != null ? `${usage}%` : "—", icon: "M3 17l5-5 4 4 8-8M14 8h6v6", color: "#19b5a5", footer: alerta ? `<span class="state-badge ${alerta.cls}">${alerta.label}</span>` : "sin cupo de referencia" })}
      </div>
      <div class="mt-3 space-y-2">
        ${last ? `<div class="flex justify-between text-sm"><span class="text-slate-500">Último movimiento</span><span class="font-semibold">${esc(last.description)} · ${money(last.amount)}</span></div>` : ""}
        <div class="flex justify-between text-sm"><span class="text-slate-500">Cierre de cuenta</span><span class="font-semibold">${account.statement_day ? `día ${account.statement_day} de cada mes` : "sin definir"}</span></div>
        <div class="flex justify-between text-sm"><span class="text-slate-500">Vencimiento</span><span class="font-semibold">${account.due_day ? `día ${account.due_day} de cada mes` : "sin definir"}</span></div>
        <div class="flex justify-between text-sm"><span class="text-slate-500">Saldo informado</span><span class="font-semibold">${money(account.balance_reported || 0)}</span></div>
        <div class="flex justify-between text-sm"><span class="text-slate-500">Diferencia</span><span class="font-semibold ${(account.balance_calculated || 0) - (account.balance_reported || 0) !== 0 ? "text-brand-amber-dark" : "text-brand-turquoise-dark"}">${money((account.balance_calculated || 0) - (account.balance_reported || 0))}</span></div>
        <button onclick="openAccEdit('${account.id}')" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Editar tarjeta</button>
      </div>`;
  } else {
    body = `<div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        ${kpiCard({ label: "Saldo calculado", value: money(account.balance_calculated || 0), icon: "M12 3v18M5 7h14M8 3h8M5 17h14", color: "#123b4a" })}
        ${kpiCard({ label: "Movimientos", value: String(base.length), icon: "M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1", color: "#19b5a5" })}
        ${kpiCard({ label: "Promedio por movimiento", value: money(avg), icon: "M4 12h4l2-5 3 10 2-5h5", color: "#b8860b" })}
      </div>
      <div class="mt-3 space-y-2">
        ${last ? `<div class="flex justify-between text-sm"><span class="text-slate-500">Último movimiento</span><span class="font-semibold">${esc(last.description)} · ${money(last.amount)}</span></div>` : ""}
        <div class="text-sm flex items-center justify-between"><span class="text-slate-500">Saldo informado</span><span class="font-semibold">${money(account.balance_reported || 0)}</span></div>
        <div class="text-sm flex items-center justify-between"><span class="text-slate-500">Diferencia</span><span class="font-semibold ${(account.balance_calculated || 0) - (account.balance_reported || 0) !== 0 ? "text-brand-amber-dark" : "text-brand-turquoise-dark"}">${money((account.balance_calculated || 0) - (account.balance_reported || 0))}</span></div>
      </div>`;
  }
  return `
  <div class="cf-card cf-fade">
    ${accTabsHtml(account.id, isCard)}
    ${body}
    <div class="mt-3 text-xs text-slate-400">${untilNext}</div>
  </div>`;
}

function estadoCuentaBody(account, card) {
  const txnMap = groupTxnsByAccount(state.householdTxns);
  const base = (txnMap[account.id] || []).filter((t) => t.status !== "voided");
  const win = cardStatementWindow(account);
  const winTxns = base.filter(win.inWin);
  const compras = winTxns.filter((t) => t.type === "expense").reduce((a, t) => a + (Number(t.amount) || 0), 0);
  const pagosTxn = winTxns.filter((t) => t.type === "payment" || t.to_account_id === account.id).reduce((a, t) => a + (Number(t.amount) || 0), 0);
  const pagosDebt = (card.payments || []).filter((p) => win.inWin(p)).reduce((a, p) => a + (Number(p.amount) || 0), 0);
  const { cupo, calc, usage, alerta } = cardUsage(account);
  const disponible = cupo > 0 ? Math.max(0, cupo - calc) : null;
  const labelPeriodo = `${win.fromIso.split("-").slice(1).join("/")} — ${win.toIso.split("-").slice(1).join("/")}`;
  return `
    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
      ${kpiCard({ label: "Período del corte", value: labelPeriodo, icon: "M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 012 2v14H3V6a2 2 0 012-2z", color: "#123b4a", footer: `cierre: ${account.statement_day ? `día ${account.statement_day}` : "sin definir"}` })}
      ${kpiCard({ label: "Compras del período", value: money(compras), icon: "M3 3h18l-2 7H5L3 3zm12 0l2 14H7l2-14", color: "#b8860b" })}
      ${kpiCard({ label: "Pagos del período", value: money(pagosTxn + pagosDebt), icon: "M9 12l2 2 4-4M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "#19b5a5" })}
      ${kpiCard({ label: "Cupo disponible", value: disponible != null ? money(disponible) : "—", icon: "M2 10h20M2 14h20M6 6h12a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2z", color: "#38bdf8" })}
    </div>
    <div class="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="cf-card"><h2 class="font-bold mb-3">Resumen</h2>
        <div class="space-y-2 text-sm">
          <div class="flex justify-between"><span class="text-slate-500">Saldo deudor actual</span><span class="font-semibold">${money(calc)}</span></div>
          <div class="flex justify-between"><span class="text-slate-500">Cupo de la tarjeta</span><span class="font-semibold">${money(cupo)}</span></div>
          <div class="flex justify-between"><span class="text-slate-500">Utilización</span><span class="font-semibold">${usage != null ? `${usage}%` : "—"}${alerta ? ` <span class="state-badge ${alerta.cls}">${alerta.label}</span>` : ""}</span></div>
          <div class="flex justify-between"><span class="text-slate-500">Vencimiento</span><span class="font-semibold">${account.due_day ? `día ${account.due_day} de cada mes` : "sin definir"}</span></div>
          <div class="flex justify-between"><span class="text-slate-500">Cuotas asociadas</span><span class="font-semibold">${(card.installments || []).length}</span></div>
          <div class="flex justify-between"><span class="text-slate-500">Pagos registrados</span><span class="font-semibold">${(card.payments || []).length}</span></div>
        </div>
      </div>
      <div class="cf-card"><h2 class="font-bold mb-3">Movimientos del período</h2>
        ${winTxns.length ? `<div class="max-h-64 overflow-auto"><table class="cf-table w-full">${acctTxnRows(winTxns)}</table></div>` : emptyState("Sin movimientos en este período de corte.")}
      </div>
    </div>`;
}

function cuotasBody(card) {
  const rows = (card.installments || []).slice().sort((a, b) => String(a.due_date).localeCompare(String(b.due_date)));
  const pending = rows.filter((i) => i.status === "pending");
  const next = pending[0];
  const pendingTotal = pending.reduce((a, i) => a + (Number(i.total_amount) || 0), 0);
  return `
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
      ${kpiCard({ label: "Cuotas pendientes", value: String(pending.length), icon: "M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1", color: "#123b4a" })}
      ${kpiCard({ label: "Total por pagar", value: money(pendingTotal), icon: "M4 12h4l2-5 3 10 2-5h5", color: "#e15554" })}
      ${kpiCard({ label: "Próxima cuota", value: next ? String(next.due_date) : "—", icon: "M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 012 2v14H3V6a2 2 0 012-2z", color: "#19b5a5", footer: next ? money(next.total_amount || 0) : "sin cuotas pendientes" })}
    </div>
    ${rows.length ? `<div class="mt-4 max-h-72 overflow-auto"><table class="cf-table w-full">
      <thead><tr><th>Vence</th><th>Deuda</th><th class="text-right hidden md:table-cell">Principal</th><th class="text-right hidden md:table-cell">Interés</th><th class="text-right">Total</th><th>Estado</th></tr></thead>
      <tbody>${rows.map((i) => `<tr><td class="text-slate-500">${esc(i.due_date)}</td><td>${esc(i.debt_name || "")}</td><td class="text-right hidden md:table-cell">${money(i.principal_amount)}</td><td class="text-right hidden md:table-cell">${money(i.interest_amount)}</td><td class="text-right font-semibold">${money(i.total_amount)}</td><td><span class="state-badge ${i.status === "pending" ? "atencion" : i.status === "overdue" ? "excedido" : "bien"}">${esc(i.status)}</span></td></tr>`).join("")}</tbody>
    </table></div>` : emptyState("Sin cuotas asociadas a esta tarjeta (asocia una deuda a la cuenta para verlas aquí).")}`;
}

function pagosBody(account, card) {
  const win = cardStatementWindow(account);
  const pagos = (card.payments || []).slice().sort((a, b) => String(b.payment_date).localeCompare(String(a.payment_date)));
  const total = pagos.reduce((a, p) => a + (Number(p.amount) || 0), 0);
  const enPeriodo = (card.payments || []).filter((p) => win.inWin(p)).reduce((a, p) => a + (Number(p.amount) || 0), 0);
  const txnMap = groupTxnsByAccount(state.householdTxns);
  const txnsPagos = (txnMap[account.id] || []).filter((t) => (t.type === "payment" || t.to_account_id === account.id) && t.status !== "voided");
  return `
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
      ${kpiCard({ label: "Pagos a deudas", value: String(pagos.length), icon: "M9 12l2 2 4-4M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "#19b5a5" })}
      ${kpiCard({ label: "Total pagado", value: money(total), icon: "M12 6v6l4 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "#123b4a" })}
      ${kpiCard({ label: "En este corte", value: money(enPeriodo), icon: "M8 2v4M16 2v4M3 10h18M8 21V10M16 21V10", color: "#b8860b", footer: `${win.fromIso} — ${win.toIso}` })}
    </div>
    ${pagos.length ? `<div class="mt-4 max-h-72 overflow-auto"><table class="cf-table w-full">
      <thead><tr><th>Fecha</th><th>Deuda</th><th>Tipo</th><th class="text-right">Monto</th></tr></thead>
      <tbody>${pagos.map((p) => `<tr><td class="text-slate-500">${esc(p.payment_date)}</td><td>${esc(p.debt_name || "")}</td><td>${esc(p.type)}</td><td class="text-right font-semibold">${money(p.amount)}</td></tr>`).join("")}</tbody>
    </table></div>` : emptyState("Sin pagos de deuda registrados desde esta tarjeta.")}
    ${txnsPagos.length ? `<div class="mt-4"><h3 class="text-xs font-bold text-slate-400 uppercase mb-2">Pagos como movimientos</h3><div class="max-h-56 overflow-auto"><table class="cf-table w-full">${acctTxnRows(txnsPagos)}</table></div></div>` : ""}`;
}

async function renderAccounts(mainEl) {
  const accounts = state.accounts || [];
  const liquid = accounts.filter((a) => a.type !== "credit_card" && a.status === "active");
  const cards = accounts.filter((a) => a.type === "credit_card" && a.status === "active");
  const liquidTotal = liquid.reduce((a, c) => a + (c.balance_calculated || 0), 0);
  const cardsTotal = cards.reduce((a, c) => a + (c.balance_calculated || 0), 0);
  const donutSegments = accounts.map((a) => ({
    name: a.name,
    value: a.balance_calculated || 0,
    color: colorForId(a.id),
  }));
  const accTxnMap = groupTxnsByAccount(state.householdTxns);
  const cardsHtml = accounts.length
    ? accounts
        .map(
          (a) => {
            const reported = Math.max(0, Number(a.balance_reported) || 0);
            const calc = Math.max(0, Number(a.balance_calculated) || 0);
            const isCard = a.type === "credit_card";
            const cupo = Math.max(0, Number(a.credit_limit) || 0);
            const alignPct = cupo > 0 ? Math.round((calc / cupo) * 100) : reported > 0 ? Math.round((calc / reported) * 100) : null;
            const last = accountLastTxn(accTxnMap[a.id] || []);
            const spark = accountSpark(a, accTxnMap[a.id] || []);
            const selected = state.selectedAccountId === a.id;
            return `
            <div class="cf-card cf-fade cursor-pointer" onclick="toggleAccDetail(${a.id})">
              <div class="flex items-start justify-between">
                <div class="min-w-0">
                  <div class="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">${esc(ACCOUNT_TYPE_LABEL[a.type] || a.type)}</div>
                  <div class="font-bold truncate mt-0.5">${esc(a.name)}</div>
                  <div class="text-lg font-extrabold mt-1 ${calc < 0 ? "text-rose-600" : "text-brand-navy"}">${money(calc)}</div>
                </div>
                <span class="px-2 py-0.5 rounded-full text-xs font-semibold ${a.status === "active" ? "bg-brand-turquoise/20 text-brand-turquoise-dark" : "bg-slate-200 text-slate-500"}">${esc(a.status)}</span>
              </div>
              ${isCard ? `
                <div class="mt-3 text-xs text-slate-500">${alignPct != null ? `Utilización · ${alignPct}% del ${cupo > 0 ? "cupo" : "informado"}` : "Sin cupo ni saldo informado"}</div>
                ${alignPct != null ? progressBar(calc, cupo > 0 ? cupo : reported) : ""}` : `
                <div class="mt-3 flex justify-between text-xs text-slate-500">
                  <span>Informado: <span class="font-semibold">${money(a.balance_reported || 0)}</span></span>
                  <span>Diferencia: <span class="font-semibold ${(a.balance_calculated || 0) - (a.balance_reported || 0) !== 0 ? "text-brand-amber-dark" : "text-brand-turquoise-dark"}">${money((a.balance_calculated || 0) - (a.balance_reported || 0))}</span></span>
                </div>`}
              <div class="mt-3 flex items-end justify-between gap-2 border-t border-slate-100 pt-2">
                <div class="min-w-0">
                  ${spark}
                  ${last ? `<div class="mt-1 text-xs text-slate-500 truncate">Último: <span class="font-semibold">${esc(last.description)} · ${money(last.amount)}</span></div>` : `<div class="mt-1 text-xs text-slate-400">Sin movimientos</div>`}
                </div>
                <span class="shrink-0 text-xs font-semibold ${selected ? "text-slate-500" : "text-brand-turquoise-dark"}">${selected ? "Ocultar" : "Ver detalle"} →</span>
              </div>
            </div>`;
          }
        )
        .join("")
    : emptyState("Aún no hay cuentas. Crea tu primera cuenta para empezar a registrar.", `<button onclick="openModal('acc-modal')" class="mt-3 px-4 py-2 rounded-lg bg-brand-navy text-white text-sm font-semibold">Nueva cuenta</button>`);
  mainEl.innerHTML = `
  ${pageHeader("Cuentas", "Saldos de tus cuentas e instituciones conectadas", `<button onclick="openModal('acc-modal')" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Nueva cuenta</button>`)}
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
    ${kpiCard({ label: "Disponible (líquido)", value: money(liquidTotal), icon: "M4 6h16v12H4zM4 10h16M8 3h8", color: "#19b5a5" })}
    ${kpiCard({ label: "Saldos en tarjetas", value: money(cardsTotal), icon: "M2 10h20M2 14h20M6 6h12a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2z", color: "#b8860b" })}
    ${kpiCard({ label: "Cuentas activas", value: String(accounts.filter((a) => a.status === "active").length), icon: "M2 12h20M8 8v8M16 8v8M4 19V5", color: "#123b4a" })}
  </div>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
    <div class="cf-card lg:col-span-2">
      <h2 class="font-bold mb-4">Tus cuentas</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">${cardsHtml}</div>
    </div>
    <div class="cf-card">
      <h2 class="font-bold mb-3">Distribución por cuenta</h2>
      ${accounts.length ? `<div class="donut-wrap">${donutSvg(donutSegments, { size: 190, thickness: 26, centerLabel: "saldos", centerValue: moneyCompact(accounts.reduce((a, c) => a + (c.balance_calculated || 0), 0)) })}</div>
      <div class="mt-3 space-y-1.5">${accounts.map((a) => `<div class="flex items-center justify-between text-sm"><span class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full" style="background:${colorForId(a.id)}"></span><span class="truncate">${esc(a.name)}</span></span><span class="font-semibold">${money(a.balance_calculated || 0)}</span></div>`).join("")}</div>`
      : emptyState("Crea cuentas para ver la distribución.")}
    </div>
  </div>
  <div class="cf-card">
    <div class="flex items-center justify-between mb-3">
      <h2 class="font-bold">Detalle de cuentas</h2>
      <a href="#/income" class="text-sm text-brand-amber-dark font-semibold hover:underline">Registrar ingreso →</a>
    </div>
    <div class="overflow-x-auto"><table class="cf-table w-full">
      <thead><tr><th>Cuenta</th><th>Tipo</th><th class="text-right">Calculado</th><th class="text-right hidden md:table-cell">Informado</th><th class="text-right hidden md:table-cell">Diferencia</th><th>Estado</th></tr></thead>
      <tbody>${state.accounts
        .map(
          (a) => `<tr>
            <td class="font-medium">${esc(a.name)}</td>
            <td>${esc(ACCOUNT_TYPE_LABEL[a.type] || a.type)}</td>
            <td class="text-right font-semibold">${money(a.balance_calculated)}</td>
            <td class="text-right text-slate-500 hidden md:table-cell">${money(a.balance_reported)}</td>
            <td class="text-right hidden md:table-cell ${(a.balance_calculated || 0) - (a.balance_reported || 0) !== 0 ? "text-brand-amber-dark" : "text-slate-400"}">${money((a.balance_calculated || 0) - (a.balance_reported || 0))}</td>
            <td><span class="px-2 py-0.5 rounded-full text-xs ${a.status === "active" ? "bg-brand-turquoise/20 text-brand-turquoise-dark" : "bg-slate-200 text-slate-500"}">${esc(a.status)}</span></td>
          </tr>`
        )
        .join("") || `<tr><td colspan="6" class="text-center text-slate-400 py-6">Aún no hay cuentas</td></tr>`}
    </tbody></table></div>
  </div>
  <div class="cf-card">
    <div class="flex items-center justify-between mb-3">
      <h2 class="font-bold">Detalle por cuenta</h2>
      <span class="text-xs text-slate-400">Haz clic en una cuenta para ver movimientos, ingresos, egresos e historial</span>
    </div>
    <div id="acc-detail">${state.selectedAccountId ? "" : emptyState("Selecciona una cuenta para inspeccionar su detalle.")}</div>
  </div>
  ${accountsModalHtml()}
  <div id="acc-edit-modal"></div>
  `;
  if (state.selectedAccountId) renderAccDetail(state.selectedAccountId);
}

async function createAccount(data) {
  data.household_id = state.householdId;
  if (!data.institution_id) data.institution_id = null;
  data.balance_reported = Number(data.balance_reported || 0);
  data.balance_calculated = data.balance_reported;
  data.credit_limit = data.credit_limit !== "" && data.credit_limit != null ? Number(data.credit_limit) : null;
  data.statement_day = data.statement_day ? Number(data.statement_day) : null;
  data.due_day = data.due_day ? Number(data.due_day) : null;
  await api("/api/v1/accounts", { method: "POST", body: data });
  toast("Cuenta creada");
  closeModal("acc-modal");
  await refreshCatalog(state.householdId);
  route();
}

function openAccEdit(accountId) {
  const a = (state.accounts || []).find((x) => String(x.id) === String(accountId));
  if (!a) return;
  state.accEditId = accountId;
  const holder = document.getElementById("acc-edit-modal");
  if (!holder) return;
  holder.innerHTML = modal("acc-edit-modal", "Editar tarjeta", "acc-edit-form", "onAccEdit",
    `${field("Nombre", "edit-name", "text", a.name, { required: "" })}
     ${field("Cupo / límite de crédito (CLP)", "edit-credit_limit", "number", a.credit_limit ?? "", { step: "1" })}
     ${field("Saldo informado (CLP)", "edit-balance_reported", "number", a.balance_reported ?? 0, { step: "1" })}
     ${field("Día de cierre — corte", "edit-statement_day", "number", a.statement_day ?? "", { min: "1", max: "31" })}
     ${field("Día de vencimiento — pago", "edit-due_day", "number", a.due_day ?? "", { min: "1", max: "31" })}
     ${select("Estado", "edit-status", [["active", "Activa"], ["paused", "Pausada"], ["closed", "Cerrada"]], a.status)}`);
  openModal("acc-edit-modal");
}

async function onAccEdit(data) {
  const body = {
    name: data["edit-name"],
    balance_reported: Number(data["edit-balance_reported"] || 0),
    credit_limit: data["edit-credit_limit"] !== "" && data["edit-credit_limit"] != null ? Number(data["edit-credit_limit"]) : null,
    statement_day: data["edit-statement_day"] ? Number(data["edit-statement_day"]) : null,
    due_day: data["edit-due_day"] ? Number(data["edit-due_day"]) : null,
    status: data["edit-status"],
  };
  try {
    await api(`/api/v1/accounts/${state.accEditId}`, { method: "PATCH", body });
    closeModal("acc-edit-modal");
    toast("Tarjeta actualizada");
    await refreshCatalog(state.householdId);
    route();
  } catch {
    /* toast ya notificó */
  }
}

/* ---------- Transacciones (CF1-25) ---------- */

function getTxnPeriod() {
  const now = new Date();
  const year = state.txnYear || now.getFullYear();
  const month = state.txnMonth || now.getMonth() + 1;
  return { year, month };
}

function setTxnPeriod(year, month) {
  state.txnYear = year;
  state.txnMonth = month;
}

function shiftTxnPeriod(delta) {
  const p = getTxnPeriod();
  const d = new Date(p.year, p.month - 1 + delta, 1);
  setTxnPeriod(d.getFullYear(), d.getMonth() + 1);
  route();
}

function resetTxnPeriod() {
  state.txnYear = null;
  state.txnMonth = null;
  route();
}

function setTxnMonthFromSelect() {
  const el = document.getElementById("txn-month");
  if (!el) return;
  const [y, m] = el.value.split("-").map(Number);
  if (yearIsValid(y) && m >= 1 && m <= 12) {
    setTxnPeriod(y, m);
    route();
  }
}

function yearIsValid(y) {
  return Number.isInteger(y) && y >= 2000 && y <= 2100;
}

function onTxnSearch() {
  const el = document.getElementById("txn-search");
  const value = ((el && el.value) || "").trim();
  clearTimeout(state.txnSearchTimer);
  state.txnSearchTimer = setTimeout(() => {
    if ((state.txnSearch || "").trim() !== value) {
      state.txnSearch = value;
      route();
    }
  }, 300);
}

function clearTxnSearch() {
  state.txnSearch = "";
  route();
}

function importedPeriodFrom(values) {
  for (const raw of values) {
    const match = String(raw || "").trim().match(/^(\d{1,4})[\/.-](\d{1,2})[\/.-](\d{1,4})$/);
    if (!match) continue;
    let year, month, day;
    if (match[1].length === 4) {
      year = Number(match[1]); month = Number(match[2]); day = Number(match[3]);
    } else if (match[3].length === 4) {
      day = Number(match[1]); month = Number(match[2]); year = Number(match[3]);
    } else {
      day = Number(match[1]); month = Number(match[2]); year = 2000 + Number(match[3]);
    }
    if (year >= 2000 && year <= 2100 && month >= 1 && month <= 12 && day >= 1 && day <= 31) {
      return { year, month };
    }
  }
  return null;
}

/* ---------- Egresos: movimientos + capturas (combinados) ---------- */

async function renderEgresos(mainEl) {
  state.egresosTab = state.egresosTab === "capturas" ? "capturas" : "movimientos";
  const p = getTxnPeriod();
  mainEl.innerHTML = `
  ${pageHeader("Egresos", "Lo que sale de tu bolsillo: movimientos, capturas y análisis del periodo.", "")}
  <div id="egresos-summary" class="mb-5"><div class="grid grid-cols-2 sm:grid-cols-4 gap-4">${[1, 2, 3, 4].map(() => '<div class="skeleton h-24"></div>').join("")}</div></div>
  <div id="egresos-chart" class="mb-5"><div class="skeleton h-32"></div></div>
  <div class="mb-4 flex flex-wrap items-center gap-2">
    <button onclick="setEgresosTab('movimientos')" class="tab-pill ${state.egresosTab === "movimientos" ? "is-active" : ""}">Movimientos</button>
    <button onclick="setEgresosTab('capturas')" class="tab-pill ${state.egresosTab === "capturas" ? "is-active" : ""}">Capturas</button>
  </div>
  <div id="egresos-panel"><div class="text-slate-400">Cargando…</div></div>
  `;
  const panel = document.getElementById("egresos-panel");
  if (state.egresosTab === "capturas") renderCaptures(panel);
  else renderTransactions(panel);
  const rollData = await rollSeriesData(p.year, p.month);
  const prev = rollData.length > 1 ? rollData[rollData.length - 2] : null;
  const rollExp = rollData.map((r) => r.expenses);
  const rollExpSum = rollExp.reduce((a, b) => a + b, 0);
  const rollExpAvg = rollData.length ? Math.round(rollExpSum / rollData.length) : 0;
  const rollWorst = rollData.reduce((a, r) => (r.expenses >= a.expenses ? r : a), rollData[0] || { expenses: 0, month: p.month, year: p.year });
  const rollFull = rollData.map((r) => rollMonthFull(r.year, r.month));
  const expDelta = prev ? pctDelta(rollExp[rollExp.length - 1], prev.expenses) : null;
  const incDelta = prev ? pctDelta(rollData[rollData.length - 1].income, prev.income) : null;
  try {
    const d = await api(`/api/v1/households/${state.householdId}/dashboard?year=${p.year}&month=${p.month}`);
    const sum = document.getElementById("egresos-summary");
    const chart = document.getElementById("egresos-chart");
    const top = (d.expense_categories || [])[0] || null;
    const avgPerDay = d.expenses > 0 ? Math.round(d.expenses / new Date(p.year, p.month, 0).getDate()) : 0;
    if (sum) {
      sum.innerHTML = `<div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
        ${kpiCard({ label: "Gastos del periodo", value: money(d.expenses), delta: expDelta, icon: "M12 3v18M17 17l-5 4-5-4M5 7h14M8 3h8", color: "#e15554", href: "#/egresos" })}
        ${kpiCard({ label: "Ingresos del periodo", value: money(d.income), delta: incDelta, icon: "M12 3v18M17 7l-5-4-5 4M5 17h14M8 21h8", color: "#19b5a5", href: "#/egresos" })}
        ${kpiCard({ label: "Balance del periodo", value: money(d.balance), icon: "M4 15l4-4 4 4 4-4M4 19h16M4 9V5h16v4", color: d.balance >= 0 ? "#19b5a5" : "#e15554", href: "#/egresos" })}
        ${kpiCard({ label: "Gasto promedio por día", value: money(avgPerDay), icon: "M12 6v6l4 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "#38bdf8", footer: top ? `top: ${esc(top.name)}` : "sin gastos este mes", href: "#/egresos" })}
      </div>`;
    }
    if (chart) {
      chart.innerHTML = `<div class="cf-card cf-fade">
        <div class="flex items-start justify-between mb-2">
          <h2 class="font-bold">Últimos 12 meses de gasto</h2>
          ${expDelta != null ? deltaBadge(expDelta, { invert: true }) : '<span class="text-xs text-slate-400">sin comparación</span>'}
        </div>
        ${rollExp.some((v) => v > 0) ? areaChart(rollExp, { labels: rollFull, w: 1000, h: 160, color: "#e15554", yFmt: moneyCompact }) : emptyState("Sin gastos registrados en los últimos 12 meses.")}
        <div class="mt-4 grid grid-cols-3 gap-2">
          <div class="rounded-lg bg-slate-50 py-2.5 text-center"><div class="text-lg font-extrabold text-rose-600">${moneyCompact(rollExpSum)}</div><div class="text-[11px] text-slate-400">Total 12 meses</div></div>
          <div class="rounded-lg bg-slate-50 py-2.5 text-center"><div class="text-lg font-extrabold">${moneyCompact(rollExpAvg)}</div><div class="text-[11px] text-slate-400">Promedio / mes</div></div>
          <div class="rounded-lg bg-slate-50 py-2.5 text-center"><div class="text-lg font-extrabold">${moneyCompact(rollWorst.expenses)}</div><div class="text-[11px] text-slate-400">Peor mes · ${esc(rollFull[rollData.indexOf(rollWorst)] || "")}</div></div>
        </div>
      </div>`;
    }
  } catch {
    const sum = document.getElementById("egresos-summary");
    if (sum) sum.innerHTML = "";
  }
}

function setEgresosTab(tab) {
  state.egresosTab = tab;
  route();
}

function setEgresosFilter(kind, value) {
  if (kind === "cat") state.egresosCat = value || "";
  else if (kind === "acc") state.egresosAccount = value || "";
  route();
}

async function renderTransactions(container) {
  const p = getTxnPeriod();
  const year = p.year;
  const month = p.month;
  const query = (state.txnSearch || "").trim();
  container.innerHTML = `<div class="text-slate-400">Cargando movimientos…</div>`;
  let rows = [];
  try {
    const url = query
      ? `/api/v1/transactions?household_id=${state.householdId}&q=${encodeURIComponent(query)}`
      : `/api/v1/transactions?household_id=${state.householdId}&year=${year}&month=${month}`;
    rows = await api(url);
  } catch {
    return;
  }
  const accountName = (id) => (state.accounts.find((a) => a.id === id) || {}).name || id;
  const typeColors = { expense: "text-rose-600", income: "text-brand-turquoise-dark", transfer: "text-sky-600", payment: "text-violet-600", adjustment: "text-slate-500" };
  const tRows = rows
    .map(
      (t) => `<tr class="border-t">
        <td class="px-3 py-2">${esc(t.date)}</td>
        <td class="px-3 py-2">${esc(t.description || KIND_LABEL[t.type] || t.type)}</td>
        <td class="px-3 py-2 hidden md:table-cell">${esc(accountName(t.account_id))}${t.to_account_id ? ` → ${esc(accountName(t.to_account_id))}` : ""}</td>
        <td class="px-3 py-2"><span class="px-2 py-0.5 rounded-full text-xs bg-slate-100 ${typeColors[t.type] || ""} font-semibold">${esc(KIND_LABEL[t.type] || t.type)}</span></td>
        <td class="px-3 py-2 text-right font-semibold">${t.amount < 0 ? `-${money(Math.abs(t.amount))}` : money(t.amount)}</td>
        <td class="px-3 py-2 text-right whitespace-nowrap">${t.status === "posted" ? `<button onclick="openTxnEdit('${t.id}')" class="text-xs text-brand-navy hover:underline mr-2">Editar</button><button onclick="voidTxn('${t.id}')" class="text-xs text-rose-600 hover:underline">Anular</button>` : `<span class="text-xs text-slate-400">${esc(t.status)}</span>`}</td>
      </tr>`
    )
    .join("");
  const accOptions = state.accounts
    .filter((a) => a.status === "active")
    .map((a) => [a.id, `${a.name} (${a.type})`]);
  const expCat = state.categories.filter((c) => c.kind === "expense" && c.status === "active").map((c) => [c.id, c.name]);
  const incCat = state.categories.filter((c) => c.kind === "income" && c.status === "active").map((c) => [c.id, c.name]);
  const tfrCat = state.categories.filter((c) => c.kind === "transfer" && c.status === "active").map((c) => [c.id, c.name]);

  const monthNames = "Enero Febrero Marzo Abril Mayo Junio Julio Agosto Septiembre Octubre Noviembre Diciembre".split(" ");
  const monthSel = yearOptions()
    .map((y) =>
      monthNames
        .map((n, i) => {
          const value = `${y}-${String(i + 1).padStart(2, "0")}`;
          return `<option value="${value}" ${Number(y) === year && i + 1 === month ? "selected" : ""}>${n} ${y}</option>`;
        })
        .join("")
    )
    .join("");
  const emptyMsg = query
    ? "Sin resultados para la búsqueda."
    : "Sin movimientos este mes";

  container.innerHTML = `
  <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 class="text-2xl font-extrabold">Movimientos</h1>
      <div class="flex flex-wrap items-center gap-1.5 text-sm text-slate-500 mt-1">
        <span class="font-semibold px-1">${query ? `Resultados para «${esc(query)}»` : `${year}-${String(month).padStart(2, "0")}`}</span>
        <select id="txn-month" class="rounded-md border border-slate-300 px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-amber" title="Ir al mes">
          ${monthSel}
        </select>
        <button onclick="resetTxnPeriod()" class="px-2 py-1.5 rounded-md border border-slate-200 hover:bg-slate-50 text-xs">Hoy</button>
        <div class="relative">
          <svg class="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"></circle><path d="M21 21l-4.35-4.35"></path></svg>
          <input id="txn-search" type="search" value="${esc(state.txnSearch || "")}" placeholder="Buscar por detalle…" class="rounded-md border border-slate-300 pl-8 pr-2 py-1.5 text-sm w-52 bg-white focus:outline-none focus:ring-2 focus:ring-brand-amber">
          ${query ? `<button onclick="clearTxnSearch()" class="ml-1 px-2 py-1 rounded-md border border-rose-200 hover:bg-rose-50 text-xs text-rose-600">Limpiar</button>` : ""}
        </div>
      </div>
    </div>
    <button onclick="openTxnNew()" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Nuevo movimiento</button>
  </div>
  <div class="bg-white rounded-xl shadow overflow-x-auto p-2">
    <table class="w-full text-sm">
      <thead><tr class="text-left text-xs text-slate-400 uppercase"><th class="px-3 py-2">Fecha</th><th class="px-3 py-2">Detalle</th><th class="px-3 py-2 hidden md:table-cell">Cuenta</th><th class="px-3 py-2">Tipo</th><th class="px-3 py-2 text-right">Monto</th><th class="px-3 py-2 text-right"></th></tr></thead>
      <tbody>${tRows || `<tr><td class="px-3 py-8 text-center text-slate-400" colspan="6">${emptyMsg}</td></tr>`}</tbody>
    </table>
  </div>
  ${modal("txn-modal", "Nuevo movimiento", "txn-form", "saveTxn",
    `${select("Tipo", "type", [["expense", "Gasto"], ["income", "Ingreso"], ["transfer", "Transferencia"]], "expense")}
     ${field("Monto (CLP)", "amount", "number", "", { required: "", min: "1", step: "1" })}
     ${field("Fecha", "date", "date", todayISO(), { required: "" })}
     ${field("Descripción", "description", "text", "")}
     <input type="hidden" id="txn-target" name="txn_id" value="">
     <button type="button" onclick="suggestTxnCategory()" class="mt-1 text-xs font-semibold text-brand-amber-dark hover:underline">Sugerir categoría con el asistente</button>
     <div id="acc-fields">
       ${select("Desde la cuenta", "account_id", accOptions)}
       <div id="to-account-wrap" class="hidden mt-3">${select("Hacia la cuenta", "to_account_id", accOptions)}</div>
     </div>
     <div id="cat-fields" class="mt-3"></div>`)}
  `;
  const monthSelEl = document.getElementById("txn-month");
  if (monthSelEl) monthSelEl.addEventListener("change", setTxnMonthFromSelect);
  const searchEl = document.getElementById("txn-search");
  if (searchEl) searchEl.addEventListener("input", onTxnSearch);
  const typeSel = document.getElementById("txn-form").querySelector("#type");
  const catWrap = document.getElementById("cat-fields");
  const toWrap = document.getElementById("to-account-wrap");
  function syncType() {
    const kind = typeSel.value;
    toWrap.classList.toggle("hidden", kind !== "transfer");
    const cats = kind === "income" ? incCat : kind === "transfer" ? tfrCat : expCat;
    const lastCatId = dataCatCache[kind] || "";
    catWrap.innerHTML =
      cats.length >= 1
        ? select("Categoría", "category_id", cats, lastCatId)
        : `<p class="text-xs text-brand-amber-dark">No hay categorías ${kind === "income" ? "de ingreso" : kind === "transfer" ? "de transferencia" : "de gasto"} activas.</p>`;
    catWrap.querySelectorAll("select").forEach((s) =>
      s.addEventListener("change", () => (dataCatCache[kind] = s.value))
    );
  }
  typeSel.addEventListener("change", syncType);
  syncType();
}

const dataCatCache = {};

function openTxnNew() {
  const modalEl = document.getElementById("txn-modal");
  const titleEl = modalEl?.querySelector("h3");
  if (titleEl) titleEl.textContent = "Nuevo movimiento";
  const form = document.getElementById("txn-form");
  if (form) {
    form.reset();
    const typeSel = form.querySelector("#type");
    if (typeSel) {
      typeSel.value = "expense";
      typeSel.dispatchEvent(new Event("change"));
    }
    form.elements.date.value = todayISO();
    form.elements.txn_id.value = "";
    if (form.elements.account_id) form.elements.account_id.value = form.elements.account_id.options[0]?.value || "";
  }
  openModal("txn-modal");
}

async function openTxnEdit(id) {
  let t;
  try {
    t = await api(`/api/v1/transactions/${id}`);
  } catch {
    return;
  }
  const form = document.getElementById("txn-form");
  if (!form) return;
  form.reset();
  form.elements.txn_id.value = id;
  form.elements.type.value = t.type;
  form.elements.type.dispatchEvent(new Event("change"));
  form.elements.amount.value = t.amount;
  form.elements.date.value = t.date;
  form.elements.description.value = t.description || "";
  const acctEl = form.elements.account_id;
  if (acctEl && t.account_id) acctEl.value = t.account_id;
  if (t.type === "transfer" && t.to_account_id) {
    document.getElementById("to-account-wrap")?.classList.remove("hidden");
    form.elements.to_account_id.value = t.to_account_id;
  }
  if (t.category_id) {
    const catEl = form.querySelector("#category_id");
    if (catEl) catEl.value = t.category_id;
  }
  const titleEl = document.getElementById("txn-modal")?.querySelector("h3");
  if (titleEl) titleEl.textContent = "Editar movimiento";
  openModal("txn-modal");
}

async function saveTxn(data) {
  const txnId = data.txn_id;
  delete data.txn_id;
  data.amount = Number(data.amount || 0);
  if (data.to_account_id === "" || data.to_account_id === undefined) delete data.to_account_id;
  if (data.category_id === "" || data.category_id === undefined) delete data.category_id;
  if (data.description === "" || data.description === undefined) delete data.description;
  try {
    if (txnId) {
      await api(`/api/v1/transactions/${txnId}`, { method: "PATCH", body: data });
      toast("Movimiento actualizado");
    } else {
      await api("/api/v1/transactions", { method: "POST", body: data });
      toast("Movimiento registrado");
    }
    closeModal("txn-modal");
    route();
  } catch {
    /* api() ya notifica el error */
  }
}

async function voidTxn(id) {
  if (!confirm("¿Anular este movimiento? La operación se revierte.")) return;
  await api(`/api/v1/transactions/${id}/void`, { method: "POST" });
  toast("Movimiento anulado");
  route();
}

/* ---------- Importación de estados de cuenta (Franja D CF2-13..CF2-15) ---------- */

const IMPORT_FIELDS_UI = [
  { key: "date", label: "Fecha" },
  { key: "description", label: "Descripción" },
  { key: "amount", label: "Monto (CLP)" },
  { key: "balance", label: "Saldo (CLP)" },
  { key: "external_id", label: "ID externo" },
  { key: "cargos", label: "Cargos (CLP)" },
  { key: "abonos", label: "Abonos (CLP)" },
];

const IMPORT_FIELD_ALIASES = {
  date: ["fecha", "date", "fechaoperacion", "fecha operacion", "fechamovimiento", "fecha movimiento"],
  description: ["descripcion", "detalle", "glosa", "concepto", "comercio", "movimiento", "description"],
  amount: ["monto", "amount", "valor", "importe", "monto clp"],
  balance: ["saldo", "balance", "saldo clp", "saldo acumulado"],
  external_id: ["codigo", "referencia", "folio", "id", "nro operacion", "external id"],
  cargos: ["cargo", "cargos", "debito", "debitos", "retiros"],
  abonos: ["abono", "abonos", "credito", "creditos", "depositos"],
};

function normLookup(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function guessSeparator(text) {
  const line = (text.split("\n").find((l) => l.trim()) || "").trim();
  const counts = [",", ";", "\t"].map((s) => [s, line.split(s).length]);
  counts.sort((a, b) => b[1] - a[1]);
  return counts[0][1] > 1 ? counts[0][0] : ",";
}

function detectMapping(headers) {
  const map = {};
  for (const f of IMPORT_FIELDS_UI) {
    const aliases = (IMPORT_FIELD_ALIASES[f.key] || []).map(normLookup);
    const hit = headers.find((h) => {
      const n = normLookup(h);
      return aliases.some((a) => (a === n && n.length > 3) || (n !== "" && n.includes(a)));
    });
    if (hit) map[f.key] = hit;
  }
  return map;
}

async function fileMappingFor(file) {
  const isCsv = /\.csv$/i.test(file.name);
  if (isCsv) {
    const text = await file.text();
    const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    const separator = guessSeparator(text);
    const headerLine = lines[0] || "";
    const headers = headerLine.split(separator).map((h) => h.trim().replace(/^"+|"+$/g, "")).filter(Boolean);
    return { headers, separator, headerRow: 1, isCsv: true };
  }
  return { headers: [], separator: ";", headerRow: 1, isCsv: false };
}

function importMappingFields(batch) {
  const { headers, isCsv, mapping } = batch;
  const detect = isCsv ? detectMapping(headers) : {};
  return `<div class="text-xs text-slate-500">Deja los campos vacíos para usar la detección automática.</div>` +
    IMPORT_FIELDS_UI.map((f) => {
    const value = mapping[f.key] || detect[f.key] || "";
    const options = isCsv
      ? headers.map((h) => `<option value="${esc(h)}" ${h === value ? "selected" : ""}>${esc(h)}</option>`).join("")
      : "";
    return `<label class="block text-xs font-medium text-slate-600 mb-1">${esc(f.label)}</label>
      ${isCsv
        ? `<select id="map_${f.key}" class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
             <option value="">— no usar —</option>${options}
           </select>`
        : `<input id="map_${f.key}" type="text" value="${esc(value)}" class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="${esc(f.label)} (nombre exacto de la columna)">`}`;
  }).join("");
}

function importStepper(active) {
  const steps = [
    ["1", "Subir"],
    ["2", "Detectar"],
    ["3", "Revisar"],
    ["4", "Confirmar"],
  ];
  return `<div class="mb-6 bg-white rounded-xl shadow p-3 flex items-center gap-2 flex-wrap">${steps
    .map(
      ([num, label], i) => {
        const idx = i + 1;
        const done = idx < active ? "bg-brand-turquoise text-white" : "";
        const current = idx === active ? "bg-brand-navy text-white ring-2 ring-brand-amber" : "";
        const connector = i > 0 ? `<div class="w-6 h-0.5 ${idx <= active ? "bg-brand-turquoise" : "bg-slate-200"}"></div>` : "";
        return `${connector}<div class="flex items-center gap-2">
        <span class="w-7 h-7 rounded-full text-xs font-bold grid place-items-center ${done || current || "bg-slate-100 text-slate-500"}">${num}</span>
        <span class="text-sm ${idx === active ? "font-bold text-brand-navy" : "text-slate-500"}">${label}</span>
      </div>`;
      }
    )
    .join("")}</div>`;
}

function cardStatementMetaBlock(batch, preview) {
  const meta = (batch.statement_meta && Object.keys(batch.statement_meta || {}).length) ? batch.statement_meta
    : (preview && preview.statement_meta && Object.keys(preview.statement_meta || {}).length) ? preview.statement_meta
    : null;
  if (!meta || preview.account_type !== "credit_card") return "";
  const cards = [];
  if (meta.total_to_pay != null) cards.push({ label: "Total a pagar", value: money(meta.total_to_pay), color: "#123b4a", icon: "M4 12h4l2-5 3 10 2-5h5" });
  if (meta.minimum_payment != null) cards.push({ label: "Pago mínimo", value: money(meta.minimum_payment), color: "#b8860b", icon: "M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1" });
  if (meta.total_debt != null) cards.push({ label: "Deuda total", value: money(meta.total_debt), color: "#e15554", icon: "M12 3v18M5 7h14M8 3h8M5 17h14" });
  if (meta.due_date) cards.push({ label: "Vence", value: esc(meta.due_date), color: "#38bdf8", icon: "M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 012 2v14H3V6a2 2 0 012-2z" });
  if (meta.credit_limit != null) cards.push({ label: "Cupo", value: money(meta.credit_limit), color: "#38bdf8", icon: "M2 10h20M2 14h20M6 6h12a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2z" });
  if (meta.statement_period) cards.push({ label: "Período", value: esc(meta.statement_period), color: "#64748b", icon: "M4 6h16v12H4zM4 10h16M8 3h8" });
  return `
  <div class="bg-white rounded-xl shadow p-5 mb-6">
    <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
      <h2 class="font-bold">Estado de cuenta de tarjeta detectado</h2>
      <span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-brand-amber/30 text-brand-amber-dark">Se aplica al confirmar</span>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
      ${cards.map((c) => kpiCard(c)).join("")}
    </div>
    <p class="text-xs text-slate-400 mt-3">Al confirmar, CuentaFaro actualiza el saldo informado, el cupo y el vencimiento de la tarjeta, y sincroniza la deuda vinculada (o la crea si aún no existe).</p>
  </div>`;
}

function importStatusBadge(status) {
  const map = { pending: "bg-slate-200 text-slate-600", parsed: "bg-sky-100 text-sky-700", confirmed: "bg-brand-turquoise/20 text-brand-turquoise-dark" };
  const label = { pending: "Pendiente", parsed: "Parseado", confirmed: "Confirmado" }[status] || status;
  return `<span class="px-2 py-0.5 rounded-full text-xs ${map[status] || "bg-slate-200 text-slate-600"}">${esc(label)}</span>`;
}

function kindBadge(kind, valid) {
  const map = { income: "bg-brand-turquoise/20 text-brand-turquoise-dark", expense: "bg-rose-100 text-rose-700", transfer: "bg-sky-100 text-sky-700" };
  const label = { income: "Ingreso", expense: "Gasto", transfer: "Transferencia" }[kind] || kind;
  return `<span class="px-2 py-0.5 rounded-full text-xs ${map[kind] || "bg-slate-200 text-slate-600"}">${valid ? esc(label) : "Inválida"}</span>`;
}

function renderImports(mainEl) {
  const hash = location.hash;
  if (hash.startsWith("#/imports/b/")) return renderBatchPreview(mainEl, decodeURIComponent(hash.split("/")[3]));
  if (hash.startsWith("#/imports/review")) return renderReviewQueue(mainEl);
  renderImportList(mainEl);
}

async function renderImportList(mainEl) {
  mainEl.innerHTML = `<div class="text-slate-400">Cargando importaciones…</div>`;
  let batches = [];
  try {
    batches = await api(`/api/v1/households/${state.householdId}/import-batches`);
  } catch {
    return;
  }
  const accOptions = state.accounts
    .filter((a) => a.status === "active")
    .map((a) => [a.id, `${a.name} (${a.type})`]);
  const bRows = batches
    .map(
      (b) => `<tr class="border-t">
        <td class="px-3 py-2">${esc(b.source_filename)}</td>
        <td class="px-3 py-2">${importStatusBadge(b.status)}</td>
        <td class="px-3 py-2 text-right">${b.total_rows ?? "—"}</td>
        <td class="px-3 py-2"><button onclick="openBatch('${b.id}')" class="text-xs text-brand-amber-dark hover:underline">Ver preview</button></td>
      </tr>`
    )
    .join("");
  mainEl.innerHTML = `
  <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
    <div><h1 class="text-2xl font-extrabold">Importar estados de cuenta</h1><p class="text-sm text-slate-500">${esc((state.households.find((h) => h.id === state.householdId) || {}).name || "")}</p></div>
    <button onclick="goReview()" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Cola de revisión</button>
  </div>
  ${importStepper(1)}
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <div class="bg-white rounded-xl shadow p-5">
      <h2 class="font-bold mb-3">Subir archivo</h2>
      ${accOptions.length
        ? `<form id="import-form">
             ${select("Cuenta", "account_id", accOptions)}
             <div id="import-card-hint" class="hidden rounded-md bg-brand-navy/5 border border-brand-navy/20 p-3 text-xs text-brand-navy mt-3">
               <b>Tarjeta de crédito:</b> los movimientos se asociarán a esta tarjeta (gastos del mes) y, si el archivo trae el resumen —Total a pagar, Pago mínimo o vencimiento—, CuentaFaro actualizará la deuda de la tarjeta al confirmar.
             </div>
             <label class="block text-xs font-medium text-slate-600 mb-1 mt-3">Archivo (CSV, Excel o PDF)</label>
             <label id="import-dropzone" class="block w-full rounded-xl border-2 border-dashed border-slate-300 p-6 text-center text-sm text-slate-500 cursor-pointer hover:border-brand-amber transition-colors">
               Arrastra aquí tu estado de cuenta o haz clic para elegir
               <input id="import-file" type="file" accept=".csv,.xlsx,.xls,.xlsm,.pdf" class="sr-only">
             </label>
             <div id="mapping-panel" class="mt-3 space-y-3"></div>
             <div class="rounded-md bg-brand-amber/15 border border-brand-amber/40 p-3 text-xs text-brand-amber-dark mt-3">
               <b>Todo automático:</b> deja las columnas vacías y CuentaFaro detecta fecha, descripción, monto, saldo e ID externo. Solo ajústalas si algo no se detectó solo.
             </div>
             <label class="block text-xs font-medium text-slate-600 mb-1 mt-3">Fila de encabezados</label>
             <input id="import-header-row" type="number" min="1" value="1" class="w-24 rounded-md border border-slate-300 px-3 py-2 text-sm">
             <div class="mt-5"><button type="submit" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Subir archivo</button></div>
           </form>`
        : `<p class="text-sm text-slate-400">Primero crea una cuenta activa para importar sus movimientos.</p>`}
    </div>
    <div class="bg-white rounded-xl shadow p-5">
      <h2 class="font-bold mb-3">Lotes importados</h2>
      <div class="overflow-x-auto"><table class="w-full text-sm">
        <thead><tr class="text-left text-xs text-slate-400 uppercase"><th class="px-3 py-2">Archivo</th><th class="px-3 py-2">Estado</th><th class="px-3 py-2 text-right">Filas</th><th class="px-3 py-2"></th></tr></thead>
        <tbody>${bRows || '<tr><td class="px-3 py-6 text-center text-slate-400" colspan="4">Aún no hay lotes</td></tr>'}</tbody>
      </table></div>
    </div>
  </div>`;
  document.getElementById("import-file").addEventListener("change", () => {
    const panel = document.getElementById("mapping-panel");
    const file = document.getElementById("import-file").files[0];
    if (!file) return (panel.innerHTML = "");
    panel.innerHTML = `<div class="text-xs bg-brand-amber/15 text-brand-amber-dark rounded-md p-2">Leyendo ${esc(file.name)}…</div>`;
    fileMappingFor(file).then(({ headers, separator, isCsv }) => {
      const mapping = isCsv ? detectMapping(headers) : {};
      state.importSeparator = isCsv ? separator : "";
      document.getElementById("import-header-row").value = "1";
      document.getElementById("mapping-panel").innerHTML = importMappingFields({ headers, isCsv, mapping });
    });
  });
  document.getElementById("import-form").addEventListener("submit", onImportSubmit);
  const accSelect = document.getElementById("account_id");
  if (accSelect) {
    const toggleCardHint = () => {
      const hint = document.getElementById("import-card-hint");
      if (!hint) return;
      const acc = state.accounts.find((a) => String(a.id) === String(accSelect.value));
      hint.classList.toggle("hidden", acc?.type !== "credit_card");
    };
    accSelect.addEventListener("change", toggleCardHint);
    toggleCardHint();
  }
  const dropzone = document.getElementById("import-dropzone");
  if (dropzone) {
    ["dragenter", "dragover"].forEach((ev) =>
      dropzone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropzone.classList.add("dropzone");
      })
    );
    dropzone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dropzone");
    });
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dropzone");
      const file = e.dataTransfer.files[0];
      if (!file) return;
      const input = document.getElementById("import-file");
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      input.dispatchEvent(new Event("change"));
    });
  }
}

async function onImportSubmit(event) {
  event.preventDefault();
  const file = document.getElementById("import-file").files[0];
  if (!file) {
    toast("Selecciona un archivo CSV o Excel", false);
    return;
  }
  if (!state.householdId) {
    toast("Primero configura el hogar en la pestaña Hogar y categorías", false);
    return;
  }
  const column_mapping = {};
  for (const f of IMPORT_FIELDS_UI) {
    const el = document.getElementById(`map_${f.key}`);
    if (el && el.value.trim()) column_mapping[f.key] = el.value.trim();
  }
  const headerRow = Number(document.getElementById("import-header-row").value || 1);
  const body = new FormData();
  body.append("account_id", document.getElementById("import-form").querySelector("#account_id").value);
  body.append("file", file);
  body.append("column_mapping", JSON.stringify(column_mapping));
  body.append("header_row", String(headerRow));
  if (state.importSeparator) body.append("separator", state.importSeparator);
  body.append("source_kind", "");
  try {
    const batch = await api(`/api/v1/households/${state.householdId}/import-batches`, { method: "POST", formData: body });
    try {
      const preview = await api(`/api/v1/import-batches/${batch.id}/preview`);
      const clean = (preview.invalid_rows ?? 0) === 0 && (preview.duplicate_rows ?? 0) === 0;
      if (clean) {
        toast("Archivo subido: sin filas inválidas ni duplicadas, confirmando…");
        await confirmBatch(batch.id, { silent: true, dest: "#/dashboard" });
        return;
      }
      toast("Archivo subido y parseado (hay filas inválidas o duplicadas por revisar)");
    } catch {
      toast("Archivo subido y parseado");
    }
    location.hash = `#/imports/b/${batch.id}`;
  } catch {
    /* toast ya notificó */
  }
}

async function renderBatchPreview(mainEl, batchId) {
  mainEl.innerHTML = `<div class="text-slate-400">Cargando preview…</div>`;
  let batch = null;
  let preview = null;
  try {
    const [b, p] = await Promise.all([
      api(`/api/v1/import-batches/${batchId}`),
      api(`/api/v1/import-batches/${batchId}/preview`),
    ]);
    batch = b;
    preview = p;
  } catch {
    mainEl.innerHTML = `<p class="text-slate-500">No se pudo cargar el lote.</p>`;
    return;
  }
  const accountName = (id) => (state.accounts.find((a) => a.id === id) || {}).name || id;
  const catName = (id) => (state.categories.find((c) => c.id === id) || {}).name || "";
  const rows = (preview.rows || [])
    .map(
      (r) => `<tr class="border-t">
        <td class="px-3 py-2">${esc(r.date) || "—"}</td>
        <td class="px-3 py-2">${esc(r.description) || "—"}</td>
        <td class="px-3 py-2 text-right font-semibold ${r.amount < 0 ? "text-rose-600" : "text-brand-turquoise-dark"}">${money(r.amount)}</td>
        <td class="px-3 py-2">${kindBadge(r.kind, r.valid)}</td>
        <td class="px-3 py-2 text-right text-slate-500 hidden md:table-cell">${r.balance !== null && r.balance !== undefined ? money(r.balance) : "—"}</td>
        <td class="px-3 py-2">
          ${r.duplicate ? `<span class="px-2 py-0.5 rounded-full text-xs bg-brand-amber/30 text-brand-amber-dark">Duplicado</span>` : ""}
          ${!r.valid ? `<span class="text-xs text-rose-600">${esc((r.errors || []).join(" · "))}</span>` : ""}
          ${r.valid && !r.duplicate && r.balance_ok === false ? `<span class="text-xs text-amber-600">Saldo fuera de rango</span>` : ""}
        </td>
        <td class="px-3 py-2">${r.suggested_category_id ? `<span class="px-2 py-0.5 rounded-full text-xs bg-violet-100 text-violet-700">${esc(catName(r.suggested_category_id))}</span>` : ""}</td>
      </tr>`
    )
    .join("");
  const confirmedNote = batch.status === "confirmed" ? `<div class="rounded-lg bg-brand-turquoise/10 border border-brand-turquoise/30 p-3 text-sm mb-4">
    Lote confirmado: ocurrieron <b>${state.lastConfirm ? state.lastConfirm.created : "—"}</b> creaciones y <b>${state.lastConfirm ? state.lastConfirm.queued_for_review : "—"}</b> envíos a revisión.
  </div>` : "";
  mainEl.innerHTML = `
  <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
    <div>
      <a href="#/imports" class="text-xs text-brand-amber-dark hover:underline">← Importaciones</a>
      <h1 class="text-2xl font-extrabold mt-1">${esc(batch.source_filename)}</h1>
      <p class="text-sm text-slate-500">${esc(accountName(batch.account_id))} · ${importStatusBadge(batch.status)}</p>
    </div>
    ${batch.status === "parsed" ? `<button onclick="confirmBatch('${batch.id}')" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Confirmar lote</button>` : ""}
  </div>
  ${importStepper(batch.status === "confirmed" ? 4 : batch.status === "parsed" ? 3 : 2)}
  ${confirmedNote}
  ${cardStatementMetaBlock(batch, preview)}
  <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
    <div class="bg-white rounded-xl shadow p-4"><div class="text-xs text-slate-400">Total filas</div><div class="text-xl font-bold">${preview.total_rows ?? "—"}</div></div>
    <div class="bg-white rounded-xl shadow p-4"><div class="text-xs text-slate-400">Válidas</div><div class="text-xl font-bold text-brand-turquoise-dark">${preview.valid_rows ?? "—"}</div></div>
    <div class="bg-white rounded-xl shadow p-4"><div class="text-xs text-slate-400">Inválidas</div><div class="text-xl font-bold text-rose-600">${preview.invalid_rows ?? "—"}</div></div>
    <div class="bg-white rounded-xl shadow p-4"><div class="text-xs text-slate-400">Duplicados</div><div class="text-xl font-bold text-amber-600">${preview.duplicate_rows ?? "—"}</div></div>
    <div class="bg-white rounded-xl shadow p-4"><div class="text-xs text-slate-400">Saldos</div><div class="text-xl font-bold text-sky-600">${preview.reconciliation_mismatches ?? "—"}</div></div>
  </div>
  <div class="bg-white rounded-xl shadow overflow-x-auto p-2">
    <table class="w-full text-sm">
      <thead><tr class="text-left text-xs text-slate-400 uppercase"><th class="px-3 py-2">Fecha</th><th class="px-3 py-2">Detalle</th><th class="px-3 py-2 text-right">Monto</th><th class="px-3 py-2">Tipo</th><th class="px-3 py-2 text-right hidden md:table-cell">Saldo</th><th class="px-3 py-2">Estado</th><th class="px-3 py-2">Categoría</th></tr></thead>
      <tbody>${rows || '<tr><td class="px-3 py-8 text-center text-slate-400" colspan="7">Sin movimientos</td></tr>'}</tbody>
    </table>
  </div>
  `;
}

async function confirmBatch(batchId, opts = {}) {
  const { silent = false, dest = "#/egresos" } = opts;
  if (!silent && !confirm("¿Confirmar este lote? Las filas válidas pasarán a la cola de revisión según corresponda.")) return;
  try {
    state.lastConfirm = await api(`/api/v1/import-batches/${batchId}/confirm`, { method: "POST", body: {} });
    toast(`Lote confirmado: ${state.lastConfirm.created} creadas, ${state.lastConfirm.queued_for_review} en revisión`);
    try {
      const detail = await api(`/api/v1/import-batches/${batchId}`);
      const period = importedPeriodFrom((detail.rows || []).map((r) => (r.values || {}).date));
      if (period) {
        setTxnPeriod(period.year, period.month);
        state.dashboardYear = period.year;
        state.dashMonth = period.month;
      }
    } catch {
      /* el periodo queda como estaba */
    }
    location.hash = dest;
  } catch {
    /* toast ya notificó */
  }
}

async function renderReviewQueue(mainEl) {
  mainEl.innerHTML = `<div class="text-slate-400">Cargando cola de revisión…</div>`;
  let items = [];
  try {
    items = await api(`/api/v1/import-reviews?household_id=${state.householdId}&status=pending`);
  } catch {
    return;
  }
  const kindLabel = { invalid: "Inválida", duplicate: "Duplicada" };
  const cards = items
    .map(
      (it) => {
        const values = it.values || {};
        return `<div class="bg-white rounded-xl shadow p-4">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div class="font-medium">${esc(it.source_filename || "Lote")} · fila ${esc(it.row_number)}</div>
            <div class="text-xs text-slate-400"><span class="px-2 py-0.5 rounded-full text-xs ${it.kind === "invalid" ? "bg-rose-100 text-rose-700" : "bg-brand-amber/30 text-brand-amber-dark"}">${esc(kindLabel[it.kind] || it.kind)}</span> ${esc(it.reason || "")}</div>
          </div>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm mt-2">
          <div><span class="text-xs text-slate-400">Fecha</span><div>${esc(values.date) || "—"}</div></div>
          <div class="col-span-2"><span class="text-xs text-slate-400">Descripción</span><div>${esc(values.description) || "—"}</div></div>
          <div><span class="text-xs text-slate-400">Monto</span><div class="text-right font-semibold">${money(values.amount)}</div></div>
        </div>
        <div class="flex gap-2 mt-3">
          ${it.kind === "invalid" ? `<button onclick="openReviewEdit('${it.id}')" class="px-3 py-1.5 rounded-md bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold">Corregir</button>` : `<button onclick="resolveReview('${it.id}','confirm')" class="px-3 py-1.5 rounded-md bg-brand-turquoise hover:bg-brand-turquoise-dark text-white text-xs font-semibold">Confirmar</button>`}
          <button onclick="resolveReview('${it.id}','discard')" class="px-3 py-1.5 rounded-md bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-semibold">Descartar</button>
        </div>
      </div>`;
      }
    )
    .join("");
  const catOptions = state.categories.filter((c) => c.status === "active").map((c) => [c.id, c.name]);
  state.reviews = items;
  mainEl.innerHTML = `
  <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
    <div>
      <a href="#/imports" class="text-xs text-brand-amber-dark hover:underline">← Importaciones</a>
      <h1 class="text-2xl font-extrabold mt-1">Cola de revisión</h1>
      <p class="text-sm text-slate-500">Movimientos que requieren confirmación manual</p>
    </div>
  </div>
  <div class="space-y-4">${cards || '<div class="bg-white rounded-xl shadow p-6 text-center text-slate-400">Sin pendientes — cola vacía.</div>'}</div>
  ${modal("review-modal", "Corregir movimiento", "review-form", "onReviewCorrectSubmit",
    `${field("Fecha", "date", "date", "")}
     ${field("Monto (CLP)", "amount", "number", "", { required: "", step: "1" })}
     ${field("Descripción", "description", "text", "")}
     ${select("Categoría", "category_id", [["", "Sin categoría"]].concat(catOptions))}
     <input type="hidden" id="review-target-id" name="review_target_id" value="">`)}
  `;
}

function openReviewEdit(reviewId) {
  const item = (state.reviews || []).find((r) => r.id === reviewId);
  const values = (item && item.values) || {};
  document.getElementById("review-target-id").value = reviewId;
  document.getElementById("date").value = values.date || "";
  document.getElementById("amount").value = values.amount || "";
  document.getElementById("description").value = values.description || "";
  openModal("review-modal");
}

async function resolveReview(reviewId, action) {
  try {
    await api(`/api/v1/import-reviews/${reviewId}/resolve`, { method: "POST", body: { action } });
    toast(action === "confirm" ? "Movimiento confirmado" : "Movimiento descartado");
    closeModal("review-modal");
    route();
  } catch {
    /* toast ya notificó */
  }
}

async function onReviewCorrectSubmit(data) {
  const reviewId = document.getElementById("review-target-id").value;
  const payload = {
    action: "correct",
    values: {
      date: data.date || "",
      amount: data.amount || "",
      description: data.description || "",
    },
  };
  if (data.category_id) payload.category_id = data.category_id;
  try {
    await api(`/api/v1/import-reviews/${reviewId}/resolve`, { method: "POST", body: payload });
    toast("Movimiento corregido");
    closeModal("review-modal");
    route();
  } catch {
    /* toast ya notificó */
  }
}

function openBatch(batchId) {
  location.hash = `#/imports/b/${batchId}`;
}

function goReview() {
  location.hash = "#/imports/review";
}

/* ---------- Bandeja de capturas (CF4-05/CF4-08) ---------- */

const CAPTURE_KIND_LABEL = { text: "Texto", audio: "Audio", image: "Imagen" };
const CAPTURE_STATUS_LABEL = {
  pending: "Pendiente",
  needs_input: "Requiere revisión",
  confirmed: "Confirmada",
  rejected: "Rechazada",
  discarded: "Descartada",
};

function captureProposal(item) {
  return (item && item.payload && item.payload.proposal) || {};
}

async function renderCaptures(container) {
  container.innerHTML = `<div class="text-slate-400">Cargando bandeja de capturas…</div>`;
  const h = state.householdId;
  let pending = [];
  let needsInput = [];
  let history = [];
  try {
    [pending, needsInput, history] = await Promise.all([
      api(`/api/v1/households/${h}/captures?status=pending`),
      api(`/api/v1/households/${h}/captures?status=needs_input`),
      api(`/api/v1/households/${h}/captures`),
    ]);
  } catch {
    return;
  }
  state.captures = history;
  const inbox = [...pending, ...needsInput];

  const cards = inbox
    .map((item) => {
      const proposal = captureProposal(item);
      const cat = state.categories.find((c) => c.id === proposal.category_id);
      const canConfirm = proposal.processed && proposal.amount > 0;
      return `<div class="bg-white rounded-xl shadow p-4">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded-full text-xs ${
              item.kind === "image" ? "bg-sky-100 text-sky-700" : item.kind === "audio" ? "bg-violet-100 text-violet-700" : "bg-slate-100 text-slate-700"
            }">${esc(CAPTURE_KIND_LABEL[item.kind] || item.kind)}</span>
            <span class="px-2 py-0.5 rounded-full text-xs ${
              item.status === "needs_input" ? "bg-brand-amber/30 text-brand-amber-dark" : "bg-brand-turquoise/20 text-brand-turquoise-dark"
            }">${esc(CAPTURE_STATUS_LABEL[item.status] || item.status)}</span>
            <span class="text-xs text-slate-400">${esc(item.channel || "simulado")}</span>
          </div>
          <div class="text-xs text-slate-400">${esc((item.created_at || "").slice(0, 16).replace("T", " "))}</div>
        </div>
        <div class="text-sm mt-2">"${esc(item.raw_text || "—")}"</div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm mt-2">
          <div><span class="text-xs text-slate-400">Fecha propuesta</span><div>${esc(proposal.date || "—")}</div></div>
          <div><span class="text-xs text-slate-400">Monto propuesto</span><div class="text-right font-semibold">${money(proposal.amount)}</div></div>
          <div class="col-span-2"><span class="text-xs text-slate-400">Descripción</span><div>${esc(proposal.description || "—")}${proposal.category_id ? `<span class="ml-1 text-xs text-brand-amber-dark">(${esc(cat ? cat.name : "categoría")})</span>` : ""}</div></div>
        </div>
        <div class="flex flex-wrap gap-2 mt-3">
          ${proposal.processed ? "" : `<button onclick="processCapture('${item.id}')" class="px-3 py-1.5 rounded-md bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold">Procesar</button>`}
          ${canConfirm ? `<button onclick="openCaptureConfirm('${item.id}')" class="px-3 py-1.5 rounded-md bg-brand-turquoise hover:bg-brand-turquoise-dark text-white text-xs font-semibold">Confirmar</button>` : `<button onclick="openCaptureConfirm('${item.id}')" class="px-3 py-1.5 rounded-md bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-semibold">Confirmar</button>`}
          <button onclick="openCaptureEdit('${item.id}')" class="px-3 py-1.5 rounded-md bg-brand-navy hover:bg-brand-navy-dark text-white text-xs font-semibold">Corregir</button>
          <button onclick="discardCapture('${item.id}','discard')" class="px-3 py-1.5 rounded-md bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-semibold">Descartar</button>
          <button onclick="discardCapture('${item.id}','reject')" class="px-3 py-1.5 rounded-md bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold">Rechazar</button>
        </div>
      </div>`;
    })
    .join("");

  const historyRows = history
    .map((item) => {
      const proposal = captureProposal(item);
      return `<tr>
        <td class="px-3 py-2 text-xs">${esc((item.created_at || "").slice(0, 10))}</td>
        <td class="px-3 py-2 text-xs"><span class="px-2 py-0.5 rounded-full text-xs ${
          item.status === "confirmed" ? "bg-brand-turquoise/20 text-brand-turquoise-dark" : item.status === "discarded" ? "bg-slate-100 text-slate-600" : "bg-rose-100 text-rose-700"
        }">${esc(CAPTURE_STATUS_LABEL[item.status] || item.status)}</span></td>
        <td class="px-3 py-2 text-xs">${esc(CAPTURE_KIND_LABEL[item.kind] || item.kind)}</td>
        <td class="px-3 py-2 text-xs">${esc((item.raw_text || "").slice(0, 40))}</td>
        <td class="px-3 py-2 text-xs">${esc(proposal.description || "—")}</td>
        <td class="px-3 py-2 text-xs text-right">${money(proposal.amount)}</td>
      </tr>`;
    })
    .join("");

  const catOptions = state.categories.filter((c) => c.status === "active").map((c) => [c.id, c.name]);
  const accountOptions = state.accounts.filter((a) => a.status === "active").map((a) => [a.id, a.name]);

  container.innerHTML = `
  <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 class="text-2xl font-extrabold">Bandeja de capturas</h1>
      <p class="text-sm text-slate-500">La máquina propone fecha, monto y categoría; la persona confirma, corrige o descarta.</p>
    </div>
    <button onclick="openModal('capture-new-modal')" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Nueva captura</button>
  </div>
  <div class="space-y-4">${cards || '<div class="bg-white rounded-xl shadow p-6 text-center text-slate-400">Sin capturas pendientes.</div>'}</div>
  <div class="mt-8">
    <h2 class="text-lg font-bold mb-3">Historial</h2>
    <div class="bg-white rounded-xl shadow overflow-x-auto">
      <table class="w-full text-sm">
        <thead><tr class="text-left text-xs text-slate-400 border-b">${["Fecha", "Estado", "Canal", "Texto", "Descripción", "Monto"].map((c) => `<th class="px-3 py-2 font-medium">${c}</th>`).join("")}</tr></thead>
        <tbody>${historyRows || '<tr><td colspan="6" class="px-3 py-6 text-center text-slate-400">Sin capturas registradas.</td></tr>'}</tbody>
      </table>
    </div>
  </div>
  ${modal("capture-confirm-modal", "Confirmar captura", "capture-confirm-form", "confirmCapture",
    `${select("Cuenta", "account_id", accountOptions)}
     ${field("Monto (CLP)", "amount", "number", "", { step: "1" })}
     ${field("Fecha", "date", "date", "")}
     ${field("Descripción", "description", "text", "")}
     ${select("Categoría", "category_id", [["", "Sin categoría"]].concat(catOptions))}
     <input type="hidden" id="capture-confirm-target" name="capture_id" value="">`)}
  ${modal("capture-edit-modal", "Corregir propuesta", "capture-edit-form", "onCaptureEdit",
    `${field("Fecha", "date", "date", "")}
     ${field("Monto (CLP)", "amount", "number", "", { required: "", step: "1" })}
     ${field("Descripción", "description", "text", "")}
     ${select("Categoría", "category_id", [["", "Sin categoría"]].concat(catOptions))}
     <input type="hidden" id="capture-edit-target" name="capture_id" value="">`)}
  ${modal("capture-new-modal", "Nueva captura", "capture-new-form", "createCapture",
    `${select("Tipo", "kind", [["text", "Texto"], ["image", "Imagen"], ["audio", "Audio"]], "text")}
     ${field("Texto de la captura", "raw_text", "text", "", { required: "", placeholder: "Ej: Pagué 15.000 en supermercado Líder" })}`)}
  `;
}

async function processCapture(captureId) {
  try {
    await api(`/api/v1/captures/${captureId}/process`, { method: "POST" });
    toast("Captura procesada: propuesta lista");
    route();
  } catch {
    /* toast ya notificó */
  }
}

async function createCapture(data) {
  try {
    const created = await api(`/api/v1/households/${state.householdId}/captures`, { method: "POST", body: data });
    closeModal("capture-new-modal");
    toast("Captura creada");
    await processCapture(created.id);
  } catch {
    /* toast ya notificó */
  }
}

function openCaptureConfirm(captureId) {
  const item = (state.captures || []).find((c) => c.id === captureId);
  const proposal = captureProposal(item);
  const form = document.getElementById("capture-confirm-form");
  form.elements.capture_id.value = captureId;
  form.elements.account_id.value = (state.accounts[0] || {}).id || "";
  form.elements.amount.value = proposal.amount || "";
  form.elements.date.value = proposal.date || "";
  form.elements.description.value = proposal.description || "";
  form.elements.category_id.value = proposal.category_id || "";
  openModal("capture-confirm-modal");
}

async function confirmCapture(data) {
  const captureId = data.capture_id;
  const payload = { account_id: data.account_id, amount: Number(data.amount) || undefined };
  if (data.date) payload.date = data.date;
  if (data.description) payload.description = data.description;
  if (data.category_id) payload.category_id = data.category_id;
  try {
    await api(`/api/v1/captures/${captureId}/confirm`, { method: "POST", body: payload });
    toast("Captura confirmada: movimiento registrado");
    closeModal("capture-confirm-modal");
    route();
  } catch {
    /* toast ya notificó */
  }
}

function openCaptureEdit(captureId) {
  const item = (state.captures || []).find((c) => c.id === captureId);
  const proposal = captureProposal(item);
  const form = document.getElementById("capture-edit-form");
  form.elements.capture_id.value = captureId;
  form.elements.date.value = proposal.date || "";
  form.elements.amount.value = proposal.amount || "";
  form.elements.description.value = proposal.description || "";
  form.elements.category_id.value = proposal.category_id || "";
  openModal("capture-edit-modal");
}

async function onCaptureEdit(data) {
  const captureId = data.capture_id;
  const payload = {};
  if (data.date) payload.date = data.date;
  if (data.amount) payload.amount = Number(data.amount);
  if (data.description) payload.description = data.description;
  if (data.category_id) payload.category_id = data.category_id;
  try {
    await api(`/api/v1/captures/${captureId}/proposal`, { method: "POST", body: payload });
    toast("Propuesta corregida");
    closeModal("capture-edit-modal");
    route();
  } catch {
    /* toast ya notificó */
  }
}

async function discardCapture(captureId, resolution) {
  try {
    await api(`/api/v1/captures/${captureId}/resolve`, {
      method: "POST",
      body: { resolution },
    });
    toast(resolution === "discard" ? "Captura descartada" : "Captura rechazada");
    route();
  } catch {
    /* toast ya notificó */
  }
}

/* ---------- Avisos y recordatorios (CF4-07/CF4-08) ---------- */

const NOTIFICATION_LABEL = {
  upcoming_payment: "Pago próximo por vencer",
  weekly_summary: "Resumen semanal",
  budget_deviation: "Desviación de presupuesto",
  monthly_close: "Cierre de mes",
};

async function renderNotifications(mainEl) {
  mainEl.innerHTML = `<div class="text-slate-400">Cargando avisos…</div>`;
  const h = state.householdId;
  let prefs = [];
  let sends = [];
  let pending = [];
  try {
    [prefs, sends, pending] = await Promise.all([
      api(`/api/v1/households/${h}/notification-preferences`),
      api(`/api/v1/households/${h}/notifications/sends`),
      api(`/api/v1/households/${h}/notifications?status=pending`),
    ]);
  } catch {
    return;
  }
  state.messagingPrefs = prefs;

  const toggleCards = prefs
    .map(
      (pref) => `<label class="flex items-center justify-between bg-white rounded-xl shadow p-4 cursor-pointer">
        <div>
          <div class="font-medium">${esc(NOTIFICATION_LABEL[pref.template_kind] || pref.template_kind)}</div>
        </div>
        <input type="checkbox" data-kind="${esc(pref.template_kind)}" ${pref.enabled ? "checked" : ""} onchange="toggleNotification(this)" class="w-5 h-5 accent-brand-amber">
      </label>`
    )
    .join("");

  const pendingRows = pending
    .map(
      (n) => `<tr>
        <td class="px-3 py-2 text-xs">${esc(NOTIFICATION_LABEL[n.template_kind] || n.template_kind)}</td>
        <td class="px-3 py-2 text-xs">${esc(n.due_date || "—")}</td>
        <td class="px-3 py-2 text-xs">${esc(n.title)}</td>
      </tr>`
    )
    .join("");

  const sendRows = sends
    .map(
      (s) => `<tr>
        <td class="px-3 py-2 text-xs">${esc((s.sent_at || "").slice(0, 16).replace("T", " "))}</td>
        <td class="px-3 py-2 text-xs">${esc(s.title)}</td>
        <td class="px-3 py-2 text-xs">${esc(s.provider)}</td>
        <td class="px-3 py-2 text-xs text-slate-400">${esc(s.message_id || "—")}</td>
      </tr>`
    )
    .join("");

  mainEl.innerHTML = `
  <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 class="text-2xl font-extrabold">Avisos y recordatorios</h1>
      <p class="text-sm text-slate-500">El programador arma la cola de salida por fecha y entrega cada aviso (simulado por ahora).</p>
    </div>
    <button onclick="runNotifications()" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Ejecutar programador ahora</button>
  </div>
  <div class="grid md:grid-cols-2 gap-4 mb-6">
    <div>
      <h2 class="text-lg font-bold mb-3">Preferencias</h2>
      <div class="space-y-2">${toggleCards}</div>
    </div>
    <div>
      <h2 class="text-lg font-bold mb-3">Cola pendiente</h2>
      <div class="bg-white rounded-xl shadow overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="text-left text-xs text-slate-400 border-b">${["Tipo", "Programado", "Aviso"].map((c) => `<th class="px-3 py-2 font-medium">${c}</th>`).join("")}</tr></thead>
          <tbody>${pendingRows || '<tr><td colspan="3" class="px-3 py-6 text-center text-slate-400">Sin avisos pendientes.</td></tr>'}</tbody>
        </table>
      </div>
    </div>
  </div>
  <div>
    <h2 class="text-lg font-bold mb-3">Historial de envíos</h2>
    <div class="bg-white rounded-xl shadow overflow-x-auto">
      <table class="w-full text-sm">
        <thead><tr class="text-left text-xs text-slate-400 border-b">${["Fecha", "Título", "Proveedor", "ID"].map((c) => `<th class="px-3 py-2 font-medium">${c}</th>`).join("")}</tr></thead>
        <tbody>${sendRows || '<tr><td colspan="4" class="px-3 py-6 text-center text-slate-400">Todavía no se ha entregado ningún aviso.</td></tr>'}</tbody>
      </table>
    </div>
  </div>`;
}

async function runNotifications() {
  try {
    const result = await api(`/api/v1/households/${state.householdId}/notifications/run`, {
      method: "POST",
    });
    toast(`Programador: ${result.enqueued} encolados, ${result.sent} enviados`);
    route();
  } catch {
    /* toast ya notificó */
  }
}

async function toggleNotification(checkbox) {
  try {
    await api(`/api/v1/households/${state.householdId}/notification-preferences`, {
      method: "PATCH",
      body: { template_kind: checkbox.dataset.kind, enabled: checkbox.checked },
    });
    toast("Preferencia guardada");
  } catch {
    checkbox.checked = !checkbox.checked;
  }
}

/* ---------- Deudas y pagos (CF1-26) ---------- */

async function renderDebts(mainEl) {
  state.debtsTab = state.debtsTab || "deudas";
  mainEl.innerHTML = `<div class="text-slate-400">Cargando deudas…</div>`;
  let debts = [];
  let summary = null;
  let upcoming = null;
  try {
    [debts, summary, upcoming] = await Promise.all([
      api(`/api/v1/households/${state.householdId}/debts`),
      api(`/api/v1/households/${state.householdId}/debt-summary`),
      api(`/api/v1/households/${state.householdId}/upcoming-payments?days=60`),
    ]);
  } catch {
    return;
  }
  state.debts = debts;
  const accOptions = state.accounts.filter((a) => a.status === "active").map((a) => [a.id, a.name]);
  const upcomingList = [
    ...(upcoming.pending_installments || []).map((p) => ({ kind: "inst", ...p })),
    ...(upcoming.recurring_minimums || []).map((p) => ({ kind: "rec", ...p })),
  ].slice(0, 8);
  const paidPct = (d) => (d.original_amount > 0 ? Math.round(Math.min(100, (1 - d.current_balance / d.original_amount) * 100)) : d.current_balance > 0 ? 0 : 0);

  let debtCards = "";
  for (const debt of debts) {
    let payments = [];
    let installments = [];
    try {
      const [p, i] = await Promise.all([
        api(`/api/v1/debts/${debt.id}/payments`),
        api(`/api/v1/debts/${debt.id}/installments`),
      ]);
      payments = p;
      installments = i;
    } catch {
      /* sin detalle */
    }
    const pct = paidPct(debt);
    const stateCls = debt.status === "active" ? (pct >= 100 ? "is-ok" : pct >= 60 ? "is-warn" : "is-over") : "is-ok";
    const lastPayment = payments.length ? payments[payments.length - 1] : null;
    debtCards += `
    <div class="cf-card cf-fade">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <div class="min-w-0">
          <h3 class="font-bold truncate">${esc(debt.name)}</h3>
          <p class="text-xs text-slate-400">${esc(DEBT_TYPE_LABEL[debt.type] || debt.type)} · vence día ${debt.due_day}</p>
        </div>
        <span class="text-lg font-extrabold ${debt.status === "paid_off" ? "text-brand-turquoise-dark" : debt.status === "closed" ? "text-slate-400" : ""}">${money(debt.current_balance)}</span>
      </div>
      <div class="mt-3">${progressBar(Math.max(0, debt.original_amount - debt.current_balance), debt.original_amount, { label: false })}</div>
      <div class="mt-1 flex justify-between text-[11px] text-slate-500">
        <span>${pct}% saldado · original ${money(debt.original_amount)}</span>
        <span>mínimo ${money(debt.minimum_payment)} · tasa ${esc(debt.interest_rate)}%</span>
      </div>
      <details class="mt-3 text-sm"><summary class="cursor-pointer font-semibold text-brand-amber-dark">Pagos (${payments.length})${lastPayment ? ` · último ${formatDate(lastPayment.payment_date)}` : ""}</summary>
        <table class="w-full text-xs mt-2">${payments
          .map((p) => `<tr class="border-t"><td class="px-2 py-1.5">${esc(p.payment_date)}</td><td class="px-2 py-1.5">${esc(p.type === "extraordinary" ? "Extraordinario" : "Ordinario")}</td><td class="px-2 py-1.5 text-right">${money(p.amount)}</td></tr>`)
          .join("") || '<tr><td class="px-2 py-2 text-slate-400">Sin pagos</td></tr>'}</table>
      </details>
      <details class="mt-2 text-sm"><summary class="cursor-pointer font-semibold text-brand-amber-dark">Cuotas (${installments.length})</summary>
        <table class="w-full text-xs mt-2">${installments
          .map((i) => `<tr class="border-t"><td class="px-2 py-1.5">${esc(i.due_date)}</td><td class="px-2 py-1.5 text-right">${money(i.total_amount)}</td><td class="px-2 py-1.5 text-right"><span class="state-badge ${
            i.status === "paid" ? "bien" : i.status === "overdue" ? "excedido" : "atencion"
          }">${esc(i.status)}</span></td></tr>`)
          .join("") || '<tr><td class="px-2 py-2 text-slate-400">Sin cuotas</td></tr>'}</table>
      </details>
      <div class="mt-4 flex flex-wrap gap-2">
        <button onclick="openModal('pay-${debt.id}')" ${debt.status !== "active" ? "disabled" : ""} class="px-3 py-1.5 rounded-md bg-brand-turquoise hover:bg-brand-turquoise-dark text-white text-xs font-semibold ${debt.status !== "active" ? "opacity-40 cursor-not-allowed" : ""}">Registrar pago</button>
        <button onclick="openModal('inst-${debt.id}')" class="px-3 py-1.5 rounded-md bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-semibold">Agregar cuota</button>
      </div>
    </div>
    ${modal(`pay-${debt.id}`, `Pago · ${esc(debt.name)}`, `pay-form-${debt.id}`, "",
      `${field("Monto (CLP)", "amount", "number", "", { required: "", min: "1" })}
       ${select("Tipo", "type", [["ordinary", "Ordinario"], ["extraordinary", "Extraordinario"]], "ordinary")}
       ${select("Cuenta", "account_id", accOptions.concat([["", "Sin cuenta"]]))}
       ${field("Fecha", "payment_date", "date", todayISO(), { required: "" })}`)}
    ${modal(`inst-${debt.id}`, `Cuota · ${esc(debt.name)}`, `inst-form-${debt.id}`, "",
      `${field("Vencimiento", "due_date", "date", "", { required: "" })}
       ${field("Capital (CLP)", "principal_amount", "number", "0", { min: "0" })}
       ${field("Interés (CLP)", "interest_amount", "number", "0", { min: "0" })}
       ${field("Comisión (CLP)", "fee_amount", "number", "0", { min: "0" })}`)}
  `;
  }
  const instRows = (upcoming.pending_installments || [])
    .map(
      (p) => `<div class="flex items-center justify-between py-2 border-b last:border-0 gap-3">
        <div class="min-w-0"><div class="font-medium truncate">Cuota por ${money(p.total_amount)}</div><div class="text-xs text-slate-400">${esc(formatDate(p.due_date))} · en ${p.days_left} día(s)</div></div>
        <div class="font-bold">${money(p.total_amount)}</div></div>`
    )
    .join("");
  const recRows = (upcoming.recurring_minimums || [])
    .map(
      (p) => `<div class="flex items-center justify-between py-2 border-b last:border-0 gap-3">
        <div class="min-w-0"><div class="font-medium truncate">${esc(p.debt_name)}</div><div class="text-xs text-slate-400">Pago mínimo · ${esc(formatDate(p.due_date))}</div></div>
        <div class="font-bold">${money(p.minimum_payment)}</div></div>`
    )
    .join("");
  const statusRows = Object.entries(summary.by_status || {})
    .map(
      ([status, bucket]) => `<div class="flex items-center justify-between py-1.5 text-sm"><span class="capitalize text-slate-500">${esc(status)} · ${bucket.count}</span><span class="font-semibold">${money(bucket.current_balance)}</span></div>`
    )
    .join("");

  mainEl.innerHTML = `
  ${pageHeader("Deudas y préstamos", "Saldo pendiente, próximos vencimientos y estrategias de pago.", `<button onclick="openModal('debt-modal')" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Nueva deuda</button>`)}
  <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
    ${kpiCard({ label: "Saldo total pendiente", value: money(summary.total_current_balance || 0), icon: "M3 10h18M8 21V10M16 21V10M5 21h14M5 7l2-3h10l2 3z", color: "#b8860b", footer: `${debts.filter((d) => d.status === "active").length} deuda(s) activa(s)` })}
    ${kpiCard({ label: "Total financiado", value: money(summary.total_original_amount || 0), icon: "M2 12h20M8 8v8M16 8v8M4 19V5", color: "#123b4a", footer: `${debts.length} deuda(s) registradas` })}
    ${kpiCard({ label: "Cuotas próximas (60 días)", value: String((upcoming.pending_installments || []).length), icon: "M12 6v6l4 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "#38bdf8", footer: "más mínimos recurrentes" })}
    ${kpiCard({ label: "Saldo promedio", value: debts.length ? money(Math.round((summary.total_current_balance || 0) / debts.length)) : money(0), icon: "M12 3v18M17 7l-5-4-5 4M5 17h14M8 21h8", color: "#19b5a5", footer: "de tasas y condiciones", href: "#/projections" })}
  </div>
  <div class="mb-4 flex flex-wrap gap-2">
    <button onclick="setDebtsTab('deudas')" class="tab-pill ${state.debtsTab === "deudas" ? "is-active" : ""}">Mis deudas (${debts.length})</button>
    <button onclick="setDebtsTab('vencimientos')" class="tab-pill ${state.debtsTab === "vencimientos" ? "is-active" : ""}">Próximos pagos</button>
    <button onclick="setDebtsTab('simulador')" class="tab-pill ${state.debtsTab === "simulador" ? "is-active" : ""}">Simulador de pagos</button>
  </div>
  <div id="debts-panel"></div>
  ${modal("debt-modal", "Nueva deuda", "debt-form", "createDebt",
    `${field("Nombre", "name", "text", "", { required: "" })}
     ${select("Tipo", "type", [["credit_card", "Tarjeta de crédito"], ["loan", "Préstamo"], ["auto", "Auto"], ["mortgage", "Hipoteca"], ["line", "Línea de crédito"], ["personal", "Préstamo personal"], ["family", "Préstamo familiar"], ["other", "Otro"]], "loan")}
     ${field("Monto original (CLP)", "original_amount", "number", "", { required: "", min: "0" })}
     ${field("Pago mínimo mensual (CLP)", "minimum_payment", "number", "0", { min: "0" })}
     ${field("Interés anual (%)", "interest_rate", "number", "0", { min: "0", step: "0.01" })}
     ${field("Día de vencimiento", "due_day", "number", "1", { min: "1", max: "31" })}
     ${select("Cuenta asociada", "account_id", accOptions.concat([["", "Sin cuenta"]]))}`)}
  `;
  const panel = document.getElementById("debts-panel");
  if (state.debtsTab === "vencimientos") {
    panel.innerHTML = `
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="cf-card">
          <h2 class="font-bold mb-2">Cuotas por vencer</h2>
          ${instRows || '<p class="text-sm text-slate-400">Sin cuotas próximas en 60 días.</p>'}
        </div>
        <div class="space-y-6">
          <div class="cf-card">
            <h2 class="font-bold mb-2">Mínimos recurrentes</h2>
            ${recRows || '<p class="text-sm text-slate-400">Sin mínimos recurrentes definidos.</p>'}
          </div>
          <div class="cf-card">
            <h2 class="font-bold mb-2">Resumen de deuda</h2>
            <div class="grid grid-cols-2 gap-3 mb-3">
              <div class="rounded-lg bg-slate-50 p-3"><div class="text-xs text-slate-400">Saldo total</div><div class="text-xl font-extrabold">${money(summary.total_current_balance || 0)}</div></div>
              <div class="rounded-lg bg-slate-50 p-3"><div class="text-xs text-slate-400">Original total</div><div class="text-xl font-extrabold">${money(summary.total_original_amount || 0)}</div></div>
            </div>
            ${statusRows || '<p class="text-sm text-slate-400">Sin deudas</p>'}
            <a href="#/projections" class="mt-2 inline-block text-sm text-brand-amber-dark font-semibold hover:underline">Simular estrategias de pago →</a>
          </div>
        </div>
      </div>`;
  } else if (state.debtsTab === "simulador") {
    panel.innerHTML = `<div class="text-slate-400">Cargando simulador…</div>`;
    renderProjections(panel);
  } else {
    panel.innerHTML = debts.length
      ? `<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">${debtCards}</div>`
      : emptyState("Aún no hay deudas registradas.", `<button onclick="openModal('debt-modal')" class="mt-3 px-4 py-2 rounded-lg bg-brand-navy text-white text-sm font-semibold">Nueva deuda</button>`);
  }
}

function setDebtsTab(tab) {
  state.debtsTab = tab;
  route();
}

async function createDebt(data) {
  data.original_amount = Number(data.original_amount || 0);
  data.minimum_payment = Number(data.minimum_payment || 0);
  data.interest_rate = Number(data.interest_rate || 0);
  data.due_day = Number(data.due_day || 1);
  if (!data.account_id) delete data.account_id;
  await api(`/api/v1/households/${state.householdId}/debts`, { method: "POST", body: data });
  toast("Deuda creada");
  closeModal("debt-modal");
  route();
}

async function payDebt(debtId, data) {
  data.amount = Number(data.amount || 0);
  if (!data.account_id) delete data.account_id;
  await api(`/api/v1/debts/${debtId}/payments`, { method: "POST", body: data });
  toast("Pago registrado");
  closeModal(`pay-${debtId}`);
  route();
}

async function addInstallment(debtId, data) {
  data.principal_amount = Number(data.principal_amount || 0);
  data.interest_amount = Number(data.interest_amount || 0);
  data.fee_amount = Number(data.fee_amount || 0);
  await api(`/api/v1/debts/${debtId}/installments`, { method: "POST", body: data });
  toast("Cuota agregada");
  closeModal(`inst-${debtId}`);
  route();
}

document.addEventListener("submit", (e) => {
  if (!e.target.id || !e.target.id.startsWith("pay-form-")) return;
  e.preventDefault();
  const debtId = e.target.id.replace("pay-form-", "");
  const data = Object.fromEntries(new FormData(e.target).entries());
  payDebt(debtId, data);
});
document.addEventListener("submit", (e) => {
  if (!e.target.id || !e.target.id.startsWith("inst-form-")) return;
  e.preventDefault();
  const debtId = e.target.id.replace("inst-form-", "");
  const data = Object.fromEntries(new FormData(e.target).entries());
  addInstallment(debtId, data);
});

/* ---------- Presupuesto (CF1-27) ---------- */

async function renderBudget(mainEl) {
  const now = new Date();
  const year = state.budgetYear || now.getFullYear();
  const month = state.budgetMonth || now.getMonth() + 1;
  const monthNames = "Enero Febrero Marzo Abril Mayo Junio Julio Agosto Septiembre Octubre Noviembre Diciembre".split(" ");
  const yearOptions = Array.from({ length: 5 }, (_, i) => String(now.getFullYear() - 2 + i));
  mainEl.innerHTML = `
  ${pageHeader("Presupuesto", "Plan mensual por categoría para controlar lo que se asigna y lo que se gasta.", `
    <select id="budget-month" class="rounded-md border border-slate-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-amber" aria-label="Mes presupuesto">${monthNames.map((n, i) => `<option value="${i + 1}" ${i + 1 === month ? "selected" : ""}>${n}</option>`).join("")}</select>
    <select id="budget-year" class="rounded-md border border-slate-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-amber" aria-label="Año presupuesto">${yearOptions.map((y) => `<option value="${y}" ${y === String(year) ? "selected" : ""}>${y}</option>`).join("")}</select>
    <button onclick="createBudget()" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Crear presupuesto del mes</button>
    <button onclick="openBudgetAlloc()" class="px-4 py-2 rounded-lg bg-brand-amber hover:bg-brand-amber-dark text-brand-navy text-sm font-semibold">Asignar monto</button>`)}
  ${modal("budget-alloc-modal", "Asignar monto por categoría", "budget-alloc-form", "assignBudgetRow",
    `${select("Categoría", "budget-cat", state.categories.filter((c) => c.kind === "expense" && c.status === "active").map((c) => [c.id, c.name]))}
     ${field("Monto planeado (CLP)", "budget-amount", "number", "0", { min: "0" })}`)}`;
  const yearSel = document.getElementById("budget-year");
  const monthSel = document.getElementById("budget-month");
  if (yearSel) yearSel.addEventListener("change", () => { state.budgetYear = Number(yearSel.value) || null; route(); });
  if (monthSel) monthSel.addEventListener("change", () => { state.budgetMonth = Number(monthSel.value) || null; route(); });
  await loadBudget(mainEl, year, month);
}

async function loadBudget(mainEl, year, month) {
  let budgets = [];
  try {
    budgets = await api(`/api/v1/households/${state.householdId}/budgets`);
  } catch {
    return;
  }
  const budget = budgets.find((b) => b.year === year && b.month === month);
  const container = document.createElement("div");
  container.className = "mt-6";
  mainEl.appendChild(container);
  if (!budget) {
    container.innerHTML = `<div class="empty-state">${svgIcon("M15 12h-4a2 2 0 010-4h.7l3.5-4M15 12v6h4M9 9.9V20H5a-.9.9 0 010-1.8h1", 36)}${year}/${month} no tiene presupuesto todavía. Crea el presupuesto del mes y asigna montos por categoría.</div>`;
    return;
  }
  state.budget = budget;
  let rows = [];
  try {
    rows = await api(`/api/v1/budgets/${budget.id}/categories`);
  } catch {
    return;
  }
  const catName = (id) => (state.categories.find((c) => c.id === id) || {}).name || id;
  const plannedTotal = rows.reduce((a, r) => a + (r.planned_amount || 0), 0);
  const actualTotal = rows.reduce((a, r) => a + (r.actual_amount || 0), 0);
  const overRows = rows.filter((r) => r.planned_amount > 0 && r.actual_amount > r.planned_amount);
  const globalPct = progressPct(actualTotal, plannedTotal);
  const stateBadge = (r) =>
    r.planned_amount > 0 && r.actual_amount > r.planned_amount ? "excedido" : r.planned_amount > 0 && r.actual_amount >= r.planned_amount * 0.8 ? "atencion" : "bien";
  container.innerHTML = `
    <div class="cf-card mb-6">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h2 class="font-bold">Uso del presupuesto · ${esc(`${monthNamesShort(year, month)}`)}</h2>
          <div class="text-sm text-slate-500 mt-0.5">${money(actualTotal)} de ${money(plannedTotal)} planeados</div>
        </div>
        <span class="state-badge ${globalPct > 100 ? "excedido" : globalPct >= 80 ? "atencion" : "bien"}">${globalPct}% usado</span>
      </div>
      <div class="progress-track"><div class="progress-fill ${globalPct > 100 ? "is-over" : globalPct >= 80 ? "is-warn" : "is-ok"}" style="width:${Math.min(100, globalPct)}%"></div></div>
      ${overRows.length ? `<p class="text-xs text-rose-600 mt-2">${overRows.length} categoría(s) superaron su monto asignado.</p>` : ""}
    </div>
    <div class="cf-card">
      <div class="flex items-center justify-between mb-2">
        <h2 class="font-bold">Categorías</h2>
        <span class="text-xs text-slate-400">${rows.length} asignadas</span>
      </div>
      <div class="space-y-4">
        ${rows
          .map(
            (r) => `<div>
              <div class="flex items-center justify-between text-sm mb-1">
                <span class="font-medium">${esc(catName(r.category_id))}</span>
                <span class="flex items-center gap-2">
                  <span class="text-slate-500">${money(r.actual_amount)} de ${money(r.planned_amount)}</span>
                  <span class="state-badge ${stateBadge(r)}">${r.planned_amount > 0 && r.actual_amount > r.planned_amount ? "Excedido" : r.planned_amount > 0 && r.actual_amount >= r.planned_amount * 0.8 ? "Atención" : "Bien"}</span>
                </span>
              </div>
              ${progressBar(r.actual_amount, r.planned_amount)}
              <div class="text-xs text-slate-400 mt-1">Diferencia: ${money(r.actual_amount - r.planned_amount)}</div>
            </div>`
          )
          .join("") || '<p class="text-sm text-slate-400 py-4">Asigna un monto a una categoría para comenzar.</p>'}
      </div>
    </div>`;
}

function monthNamesShort(year, month) {
  const d = new Date(year, month - 1, 1);
  return d.toLocaleString("es-CL", { month: "long", year: "numeric" });
}

async function createBudget() {
  const now = new Date();
  try {
    await api(`/api/v1/households/${state.householdId}/budgets`, {
      method: "POST",
      body: { year: now.getFullYear(), month: now.getMonth() + 1, status: "active" },
    });
    toast("Presupuesto creado");
  } catch {
    /* toast ya notificó */
  }
  route();
}

async function assignBudgetRow() {
  const categoryId = document.getElementById("budget-cat").value;
  const planned = Number(document.getElementById("budget-amount").value || 0);
  if (!state.budget) {
    toast("Crea el presupuesto del mes primero", false);
    return;
  }
  await api(`/api/v1/budgets/${state.budget.id}/categories`, {
    method: "POST",
    body: { category_id: categoryId, planned_amount: planned },
  });
  closeModal("budget-alloc-modal");
  toast("Asignación guardada");
  route();
}

function openBudgetAlloc() {
  if (!state.budget) {
    toast("Crea el presupuesto del mes primero", false);
    return;
  }
  openModal("budget-alloc-modal");
}

/* ---------- Próximos pagos y resumen de deudas (CF1-28) ---------- */

async function renderPayments(mainEl) {
  mainEl.innerHTML = `<div class="text-slate-400">Cargando…</div>`;
  let upcoming = null;
  let summary = null;
  try {
    [upcoming, summary] = await Promise.all([
      api(`/api/v1/households/${state.householdId}/upcoming-payments?days=60`),
      api(`/api/v1/households/${state.householdId}/debt-summary`),
    ]);
  } catch {
    return;
  }
  const inst = (upcoming.pending_installments || [])
    .map(
      (p) => `<div class="flex items-center justify-between py-2 border-b last:border-0">
        <div><div class="font-medium">Cuota de ${esc(p.debt_id)} · ${esc(p.due_date)}</div><div class="text-xs text-slate-400">en ${p.days_left} días</div></div>
        <div class="font-bold">${money(p.total_amount)}</div></div>`
    )
    .join("");
  const rec = (upcoming.recurring_minimums || [])
    .map(
      (p) => `<div class="flex items-center justify-between py-2 border-b last:border-0">
        <div><div class="font-medium">${esc(p.debt_name)}</div><div class="text-xs text-slate-400">Mínimo · ${esc(p.due_date)}</div></div>
        <div class="font-bold">${money(p.minimum_payment)}</div></div>`
    )
    .join("");
  const statusRows = Object.entries(summary.by_status || {})
    .map(
      ([status, bucket]) => `<div class="flex items-center justify-between py-2 border-b last:border-0">
        <div class="capitalize">${esc(status)} (${bucket.count})</div><div class="font-semibold">${money(bucket.current_balance)}</div></div>`
    )
    .join("");
  mainEl.innerHTML = `
  <div class="mb-6"><h1 class="text-2xl font-extrabold">Pagos y resumen de deudas</h1><p class="text-sm text-slate-500">Hasta ${esc(upcoming.as_of)} + 60 días</p></div>
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <div class="bg-white rounded-xl shadow p-5">
      <h2 class="font-bold mb-2">Próximos vencimientos</h2>
      ${inst || '<p class="text-sm text-slate-400">Sin cuotas próximas</p>'}
      ${rec ? `<h3 class="font-bold text-sm text-slate-500 mt-4 mb-1">Mínimos recurrentes</h3>${rec}` : ""}
    </div>
    <div class="space-y-6">
      <div class="bg-white rounded-xl shadow p-5">
        <h2 class="font-bold mb-2">Resumen de deuda</h2>
        <div class="grid grid-cols-2 gap-3 mb-3">
          <div class="rounded-lg bg-slate-50 p-3"><div class="text-xs text-slate-400">Saldo total</div><div class="text-xl font-extrabold">${money(summary.total_current_balance)}</div></div>
          <div class="rounded-lg bg-slate-50 p-3"><div class="text-xs text-slate-400">Original total</div><div class="text-xl font-extrabold">${money(summary.total_original_amount)}</div></div>
        </div>
        ${statusRows || '<p class="text-sm text-slate-400">Sin deudas</p>'}
      </div>
    </div>
  </div>`;
}

/* ---------- Proyecciones (CF1-29) ---------- */

async function renderProjections(mainEl) {
  mainEl.innerHTML = `<div class="text-slate-400">Cargando…</div>`;
  let plans = [];
  try {
    plans = await api(`/api/v1/households/${state.householdId}/plans`);
  } catch {
    return;
  }
  const planOptions = plans.map((p) => [p.id, `${p.name} (${p.strategy})`]);
  mainEl.innerHTML = `
  <div class="mb-6"><h1 class="text-2xl font-extrabold">Proyecciones</h1><p class="text-sm text-slate-500">Bola de nieve y avalancha sobre tus deudas activas</p></div>
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <div class="bg-white rounded-xl shadow p-5">
      <h2 class="font-bold mb-3">Simular estrategia</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        ${select("Estrategia", "sim-strategy", [["snowball", "Bola de nieve"], ["avalanche", "Avalancha"]], "snowball")}
        ${field("Pago mensual (CLP)", "sim-payment", "number", "", { required: "", min: "1" })}
      </div>
      <button onclick="simulate()" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Simular</button>
      <div id="sim-result" class="mt-4"></div>
    </div>
    <div class="space-y-6">
      <div class="bg-white rounded-xl shadow p-5">
        <h2 class="font-bold mb-3">Planes de pago
          <button onclick="createPlan()" class="ml-2 px-3 py-1 rounded-md bg-brand-navy hover:bg-brand-navy-dark text-white text-xs font-semibold">Nuevo plan</button>
        </h2>
        ${plans.length ? plans.map((p) => `
          <div class="flex items-center justify-between py-2 border-b last:border-0">
            <div><div class="font-medium">${esc(p.name)}</div><div class="text-xs text-slate-400">${esc(p.strategy)} · ${esc(p.status)}</div></div>
            ${p.status !== "selected" ? `<button onclick="selectPlan('${p.id}', 'selected')" class="text-xs text-brand-amber-dark hover:underline">Activar</button>` : `<span class="text-xs text-brand-turquoise-dark font-semibold">Activo</span>`}
          </div>`).join("") : '<p class="text-sm text-slate-400">Sin planes</p>'}
      </div>
      <div class="bg-white rounded-xl shadow p-5">
        <h2 class="font-bold mb-3">Escenarios</h2>
        ${select("Plan", "scenario-plan", planOptions)}
        ${field("Nombre", "scenario-name", "text", "", { placeholder: "Ej: con bono de marzo" })}
        ${field("Pago mensual (CLP)", "scenario-payment", "number", "", { min: "1" })}
        ${field("Ingresos extra (mes:monto, separados por ;)", "scenario-extra", "text", "")}
        <button onclick="runScenario()" class="mt-3 px-4 py-2 rounded-lg bg-brand-turquoise hover:bg-brand-turquoise-dark text-white text-sm font-semibold">Ejecutar escenario</button>
        <div id="scenario-result" class="mt-4"></div>
        <h3 class="text-xs font-bold text-slate-400 uppercase mt-4 mb-1">Escenarios guardados</h3>
        <div id="scenarios-list" class="text-sm"></div>
      </div>
    </div>
  </div>
  ${modal("plan-modal", "Nuevo plan de pago", "plan-form", "onCreatePlan",
    `${select("Estrategia", "strategy", [["snowball", "Bola de nieve"], ["avalanche", "Avalancha"]], "snowball")}
     ${field("Nombre", "name", "text", "", { required: "" })}`)}
  `;
  const scenarioPlanSel = document.getElementById("scenario-plan");
  if (scenarioPlanSel) {
    scenarioPlanSel.addEventListener("change", () => {
      const resultEl = document.getElementById("scenario-result");
      if (resultEl) resultEl.innerHTML = "";
      renderScenariosList();
    });
    renderScenariosList();
  }
}

function renderPayoffOrder(order) {
  const list = (order || [])
    .map(
      (d, i) =>
        `<li>${i + 1}. ${esc(d.name)} · saldo ${money(d.current_balance)}${d.interest_rate ? ` · tasa ${esc(d.interest_rate)}%` : ""}</li>`
    )
    .join("");
  return list
    ? `<div class="text-xs text-slate-500 mt-2">Deudas en orden de pago:<ul class="mt-1 space-y-0.5">${list}</ul></div>`
    : "";
}

async function simulate() {
  const strategy = document.getElementById("sim-strategy").value;
  const monthly_payment = Number(document.getElementById("sim-payment").value || 0);
  const run = (s) =>
    api(`/api/v1/households/${state.householdId}/projections/simulate`, {
      method: "POST",
      body: { strategy: s, monthly_payment },
    });
  let snow;
  let ava;
  try {
    [snow, ava] = await Promise.all([run("snowball"), run("avalanche")]);
  } catch {
    /* toast ya notificó */
    return;
  }
  const chosen = strategy === "avalanche" ? ava : snow;
  const sample = (ser) => {
    if (!Array.isArray(ser) || ser.length <= 120) return ser || [];
    const out = [ser[0]];
    const step = (ser.length - 2) / 118;
    for (let i = 1; i < 119; i++) out.push(ser[Math.round(i * step)]);
    out.push(ser[ser.length - 1]);
    return out;
  };
  const sSeries = sample(snow.months_series).map((p) => Number(p.balance));
  const aSeries = sample(ava.months_series).map((p) => Number(p.balance));
  const maxMonths = Math.max(sSeries.length, aSeries.length);
  const labels = Array.from({ length: maxMonths }, (_, i) => `m${i + 1}`);
  document.getElementById("sim-result").innerHTML = `
    <div class="rounded-lg bg-brand-turquoise/10 border border-brand-turquoise/30 p-3 text-sm">
      <div class="font-bold mb-2">${esc(chosen.strategy === "snowball" ? "Bola de nieve" : "Avalancha")} · ${money(monthly_payment)}/mes</div>
      <div class="grid grid-cols-3 gap-2 text-center">
        <div class="rounded-lg bg-white p-2"><div class="text-[11px] text-slate-400 uppercase">Meses a deuda cero</div><div class="font-extrabold text-lg">${chosen.months_to_freedom ?? "—"}</div></div>
        <div class="rounded-lg bg-white p-2"><div class="text-[11px] text-slate-400 uppercase">Interés total</div><div class="font-extrabold text-lg">${money(chosen.total_interest)}</div></div>
        <div class="rounded-lg bg-white p-2"><div class="text-[11px] text-slate-400 uppercase">Total pagado</div><div class="font-extrabold text-lg">${money(chosen.total_paid)}</div></div>
      </div>
      <div class="text-xs text-slate-500 mt-2">${chosen.converged ? "Fondos suficientes para saldar las deudas." : "El pago mensual no alcanza para converger."}</div>
      ${renderPayoffOrder(chosen.payoff_order)}
    </div>
    <div class="bg-white rounded-lg border border-slate-200 p-4 mt-4">
      <h3 class="font-bold text-sm mb-1">Bola de nieve vs Avalancha</h3>
      <p class="text-xs text-slate-400 mb-3">Saldo total de deuda mes a mes con el mismo pago mensual.</p>
      ${lineChart([{ name: "Bola de nieve", color: "#19b5a5", values: sSeries }, { name: "Avalancha", color: "#f4b942", values: aSeries }], { labels, w: 560, h: 180, yFmt: moneyCompact })}
      <table class="cf-table w-full mt-3">
        <thead><tr><th>Estrategia</th><th class="text-right">Meses a deuda cero</th><th class="text-right">Interés</th><th class="text-right">Total pagado</th></tr></thead>
        <tbody>
          <tr class="${strategy === "snowball" ? "bg-brand-turquoise/5" : ""}"><td>Bola de nieve</td><td class="text-right font-semibold">${snow.months_to_freedom ?? "no converge"}</td><td class="text-right">${money(snow.total_interest)}</td><td class="text-right">${money(snow.total_paid)}</td></tr>
          <tr class="${strategy === "avalanche" ? "bg-brand-turquoise/5" : ""}"><td>Avalancha</td><td class="text-right font-semibold">${ava.months_to_freedom ?? "no converge"}</td><td class="text-right">${money(ava.total_interest)}</td><td class="text-right">${money(ava.total_paid)}</td></tr>
        </tbody>
      </table>
      <p class="text-[11px] text-slate-400 mt-2">${esc(chosen.assumptions?.interest || "tasas mensuales = interés anual / 12, interés simple")}</p>
    </div>`;
}

function createPlan() {
  openModal("plan-modal");
}

async function onCreatePlan(data) {
  try {
    await api(`/api/v1/households/${state.householdId}/plans`, { method: "POST", body: data });
    closeModal("plan-modal");
    toast("Plan creado");
    route();
  } catch {
    /* toast ya notificó */
  }
}

async function renderScenariosList() {
  const el = document.getElementById("scenarios-list");
  const planSel = document.getElementById("scenario-plan");
  if (!el || !planSel) return;
  const planId = planSel.value;
  if (!planId) {
    el.innerHTML = "";
    return;
  }
  let scenarios;
  try {
    scenarios = await api(`/api/v1/plans/${planId}/scenarios`);
  } catch {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = scenarios.length
    ? scenarios
        .map((s) => {
          const r = s.result_summary || {};
          const months = r.months_to_freedom;
          return `<div class="flex items-center justify-between py-2 border-b last:border-0">
            <div><div class="font-medium">${esc(s.name)}</div><div class="text-xs text-slate-400">${money(s.monthly_payment)}/mes · interés ${money(r.total_interest ?? 0)} · total ${money(r.total_paid ?? 0)}</div></div>
            <div class="text-xs font-semibold ${r.converged ? "text-brand-turquoise-dark" : "text-rose-500"}">${months !== null && months !== undefined ? `${months} meses` : r.converged ? "—" : "no converge"}</div>
          </div>`;
        })
        .join("")
    : '<p class="text-sm text-slate-400">Aún no has ejecutado escenarios.</p>';
}

async function selectPlan(planId) {
  await api(`/api/v1/plans/${planId}`, { method: "PATCH", body: { status: "selected" } });
  toast("Plan activado");
  route();
}

async function runScenario() {
  const planId = document.getElementById("scenario-plan").value;
  const name = String(document.getElementById("scenario-name").value).trim();
  const monthly_payment = Number(document.getElementById("scenario-payment").value || 0);
  if (!planId || !name || !monthly_payment) {
    toast("Completa plan, nombre y pago mensual", false);
    return;
  }
  const extraRaw = String(document.getElementById("scenario-extra").value).trim();
  const extra_income = [];
  if (extraRaw) {
    for (const part of extraRaw.split(";")) {
      const [m, a] = part.split(":").map((s) => s.trim());
      const month_offset = Number(m);
      const amount = Number(a);
      if (month_offset >= 1 && amount > 0) extra_income.push({ month_offset, amount });
    }
  }
  try {
    const result = await api(`/api/v1/plans/${planId}/scenarios`, {
      method: "POST",
      body: { name, monthly_payment, extra_income },
    });
    const s = result.result_summary || {};
    document.getElementById("scenario-result").innerHTML = `
      <div class="rounded-lg bg-sky-50 border border-sky-200 p-3 text-sm">
        <div class="font-bold">${esc(result.name)}</div>
        <div>Meses: <b>${s.months_to_freedom ?? "—"}</b> · Interés: <b>${money(s.total_interest ?? 0)}</b> · Total: <b>${money(s.total_paid ?? 0)}</b></div>
        ${Array.isArray(result.extra_income) && result.extra_income.length ? `<div class="text-xs text-slate-500 mt-1">Incluye ${result.extra_income.length} ingreso(s) extra</div>` : ""}
        ${s.converged === false ? '<div class="text-xs text-rose-500 mt-1">El pago mensual no alcanza para saldar las deudas.</div>' : ""}
        ${renderPayoffOrder(s.payoff_order)}
      </div>`;
    renderScenariosList();
  } catch {
    /* toast ya notificó */
  }
}

/* ---------- Ingresos (fuentes de ingreso mensuales) ---------- */

async function renderIncome(mainEl) {
  mainEl.innerHTML = `<div class="text-slate-400">Cargando ingresos…</div>`;
  let sources;
  try {
    sources = await api(`/api/v1/households/${state.householdId}/income-sources`);
  } catch {
    return;
  }
  state.incomeSources = sources;
  const now = new Date();
  const year = state.dashboardYear || now.getFullYear();
  const month = state.dashMonth || now.getMonth() + 1;
  let monthData = null;
  try {
    monthData = await api(`/api/v1/households/${state.householdId}/dashboard?year=${year}&month=${month}`);
  } catch {
    monthData = null;
  }
  const memberName = (id) => (state.members.find((m) => m.id === id) || {}).name || "";
  const active = sources.filter((s) => s.status === "active");
  const total = active.reduce((a, s) => a + (s.expected_amount || 0), 0);
  const recorded = monthData ? monthData.income : 0;
  const saldoTotal = (state.accounts || []).reduce((a, acc) => a + (acc.balance_calculated || 0), 0);
  const monthLabel = new Date(year, month - 1, 1).toLocaleString("es-CL", { month: "long" });
  const monthNames = "Enero Febrero Marzo Abril Mayo Junio Julio Agosto Septiembre Octubre Noviembre Diciembre".split(" ");
  const yearOptions = Array.from({ length: 5 }, (_, i) => String(now.getFullYear() - 2 + i));
  const sourceKindLabel = {
    salary: "Sueldo",
    freelance: "Freelance",
    revenue: "Negocio / ventas",
    rent: "Arriendo",
    other: "Otro",
  };
  const rows = sources
    .map(
      (s) => `
    <div class="rounded-xl border border-slate-200 bg-white p-4 cf-fade">
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0">
          <div class="font-bold truncate">${esc(s.name)}</div>
          <div class="text-xs text-slate-400 mt-0.5">${esc(sourceKindLabel[s.type] || s.type)}${s.member_id ? ` · ${esc(memberName(s.member_id))}` : ""}</div>
        </div>
        <span class="px-2 py-0.5 rounded-full text-xs font-semibold shrink-0 ${s.status === "active" ? "bg-brand-turquoise/20 text-brand-turquoise-dark" : "bg-slate-200 text-slate-500"}">${s.status === "active" ? "Activa" : "Pausada"}</span>
      </div>
      <div class="text-lg font-extrabold mt-2 text-brand-navy">${money(s.expected_amount)}<span class="text-xs font-semibold text-slate-400">/mes</span></div>
      <div class="mt-3 flex flex-wrap gap-2 text-xs">
        <button onclick="recordIncome('${esc(s.id)}')" class="px-2.5 py-1 rounded-lg bg-brand-turquoise/15 text-brand-turquoise-dark font-semibold hover:bg-brand-turquoise/25" title="Crea un movimiento de ingreso por este monto">+ Registro</button>
        <button onclick="openIncomeEdit('${esc(s.id)}')" class="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-600 font-semibold hover:bg-slate-200">Editar</button>
        <button onclick="toggleIncomeSource('${esc(s.id)}')" class="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-600 font-semibold hover:bg-slate-200">${s.status === "active" ? "Pausar" : "Activar"}</button>
        <button onclick="deleteIncomeSource('${esc(s.id)}')" class="px-2.5 py-1 rounded-lg bg-rose-50 text-rose-600 font-semibold hover:bg-rose-100">Eliminar</button>
      </div>
    </div>`
    )
    .join("");
  const memberOptions = [["", "Hogar"]].concat(state.members.map((m) => [m.id, m.name]));
  const accOptions = state.accounts
    .filter((a) => a.status === "active")
    .map((a) => [a.id, `${a.name} (${a.type})`]);
  const incomeCats = state.categories
    .filter((c) => c.kind === "income" && c.status === "active")
    .map((c) => [c.id, c.name]);
  const monthFlow = monthData ? (monthData.series || []).filter((s) => s.month <= month).map((s) => s.income) : [];
  const recordedThisYear = monthData ? (monthData.series || []).reduce((a, s) => a + s.income, 0) : recorded;
  const sourceDonut = active.length
    ? active.map((s) => ({ name: s.name, value: s.expected_amount || 0, color: colorForId(s.id) }))
    : [];
  const progressExpected = total > 0 ? Math.round(Math.min(150, (recorded / total) * 100)) : recorded > 0 ? null : 0;
  const rollData = await rollSeriesData(year, month);
  const rollIncome = rollData.map((r) => r.income);
  const rollSum = rollIncome.reduce((a, b) => a + b, 0);
  const rollAvg = rollData.length ? Math.round(rollSum / rollData.length) : 0;
  const rollPeak = rollData.reduce((a, r) => (r.income >= a.income ? r : a), rollData[0] || { income: 0, month: month, year });
  const rollFull = rollData.map((r) => rollMonthFull(r.year, r.month));
  const prevIncome = rollData.length > 1 ? rollData[rollData.length - 2].income : null;
  mainEl.innerHTML = `
  <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 class="text-2xl font-extrabold">Ingresos</h1>
      <p class="text-sm text-slate-500">Tus cuentas y cuánto gana tu hogar al mes: sueldos, arriendos, negocio o trabajo freelance.</p>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <select id="income-month" class="rounded-md border border-slate-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-amber" aria-label="Mes de ingreso">
        ${monthNames.map((n, i) => `<option value="${i + 1}" ${i + 1 === month ? "selected" : ""}>${n}</option>`).join("")}
      </select>
      <select id="income-year" class="rounded-md border border-slate-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-amber" aria-label="Año de ingreso">
        ${yearOptions.map((y) => `<option value="${y}" ${y === String(year) ? "selected" : ""}>${y}</option>`).join("")}
      </select>
      <button onclick="openIncomeNew()" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Nueva fuente</button>
      <button onclick="openRecordIncome()" class="px-4 py-2 rounded-lg bg-brand-turquoise hover:bg-brand-turquoise-dark text-white text-sm font-semibold" title="Registra el ingreso del mes con monto y fecha libre">Registrar ingreso por mes</button>
    </div>
  </div>
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
    ${kpiCard({ label: "Ingreso mensual esperado", value: money(total), icon: "M12 3v18M17 7l-5-4-5 4M5 17h14M8 21h8", color: "#19b5a5", spark: sparkline(active.map((s) => s.expected_amount || 0), { color: "#19b5a5" }), footer: `suma de tus fuentes activas` })}
    ${kpiCard({ label: `Registrado · ${esc(monthLabel)}`, value: money(recorded), delta: pctDelta(recorded, prevIncome), icon: "M9 12l2 2 4-4M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "#123b4a", spark: sparkline(monthFlow, { color: "#123b4a" }), footer: total > 0 ? `<div class="mt-1">${progressBar(recorded, total)}</div>` : `sin fuentes activas` })}
    ${kpiCard({ label: "Saldo en cuentas", value: money(saldoTotal), icon: "M4 6h16v12H4zM4 10h16M8 3h8", color: "#38bdf8", footer: `${sources.filter((s) => s.status === "active").length} fuente(s) activa(s)` })}
  </div>
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
    <div class="cf-card">
      <div class="flex items-start justify-between mb-2">
        <h2 class="font-bold">Evolución últimos 12 meses</h2>
        <span class="text-xs text-slate-400">total: <b>${moneyCompact(rollSum)}</b></span>
      </div>
      ${rollIncome.some((v) => v > 0) ? areaChart(rollIncome, { labels: rollFull, w: 560, h: 150, color: "#19b5a5", yFmt: moneyCompact }) : emptyState("Aún no hay movimientos de ingreso en los últimos 12 meses.")}
      <div class="mt-4 grid grid-cols-3 gap-2">
        <div class="rounded-lg bg-slate-50 py-2.5 text-center"><div class="text-lg font-extrabold text-brand-turquoise-dark">${moneyCompact(rollSum)}</div><div class="text-[11px] text-slate-400">Total 12 meses</div></div>
        <div class="rounded-lg bg-slate-50 py-2.5 text-center"><div class="text-lg font-extrabold">${moneyCompact(rollAvg)}</div><div class="text-[11px] text-slate-400">Promedio / mes</div></div>
        <div class="rounded-lg bg-slate-50 py-2.5 text-center"><div class="text-lg font-extrabold">${moneyCompact(rollPeak.income)}</div><div class="text-[11px] text-slate-400">Mejor mes · ${esc(rollFull[rollData.indexOf(rollPeak)] || "")}</div></div>
      </div>
    </div>
    <div class="cf-card">
      <h2 class="font-bold mb-2">Composición de fuentes activas</h2>
      ${sourceDonut.length
        ? `<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div class="donut-wrap">${donutSvg(sourceDonut, { size: 170, thickness: 24, centerLabel: "fuentes", centerValue: moneyCompact(total) })}</div>
            <div class="space-y-1.5 self-center">${active.map((s) => `<div class="flex items-center justify-between text-sm gap-3"><span class="flex items-center gap-2 min-w-0"><span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:${colorForId(s.id)}"></span><span class="truncate">${esc(s.name)}</span></span><span class="font-semibold">${money(s.expected_amount)}</span></div>`).join("")}</div>
          </div>`
        : emptyState("Crea fuentes de ingreso para ver su composición.")}
    </div>
  </div>
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    ${accountsPanelHtml()}
    <div class="cf-card">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-bold">Fuentes de ingreso</h2>
        <button onclick="openIncomeNew()" class="text-xs font-semibold text-brand-amber-dark hover:underline">+ Nueva fuente</button>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">${rows || emptyState("Sin fuentes todavía. Crea una por cada trabajo o ingreso, por ejemplo «Sueldo», «Arriendo».")}</div>
      ${total > 0 ? `<div class="mt-4 rounded-lg bg-slate-50 p-3"><div class="flex items-center justify-between text-xs text-slate-500 mb-1"><span>Recibido del esperado este mes</span><span>${money(recorded)} de ${money(total)}</span></div>${progressBar(recorded, total)}</div>` : ""}
      <p class="text-xs text-slate-500 mt-3 bg-brand-amber/10 border border-brand-amber/40 rounded-lg px-3 py-2">El monto esperado es tu referencia mensual y <b>no crea movimientos</b>. Cuando el dinero llegue (por cartola o transferencia), usa «+ Registro» para anotarlo en Movimientos.</p>
    </div>
  </div>
  ${modal("income-modal", "Fuente de ingreso", "income-form", "saveIncomeSource",
    `${field("Nombre", "name", "text", "", { required: "", placeholder: "Ej: Sueldo trabajo fijo, Ferias, Arriendo Arica" })}
     ${select("Trabaja / titular", "member_id", memberOptions)}
     ${select("Tipo", "type", [["salary", "Sueldo"], ["freelance", "Freelance"], ["revenue", "Negocio / ventas"], ["rent", "Arriendo"], ["other", "Otro"]], "salary")}
     ${field("Monto mensual (CLP)", "expected_amount", "number", "0", { min: "0", step: "1000" })}
     ${select("Estado", "status", [["active", "Activa"], ["inactive", "Pausada"]], "active")}
     <input type="hidden" id="income-target" name="source_id" value="">`)}
  ${modal("income-record-modal", "Registrar ingreso del mes", "income-record-form", "saveRecordedIncome",
    `${select("Cuenta", "account_id", accOptions)}
     ${select("Categoría", "category_id", [["", "Sin categoría"]].concat(incomeCats))}
     ${field("Monto (CLP)", "amount", "number", "", { required: "", min: "1", step: "1" })}
     ${field("Fecha", "date", "date", todayISO(), { required: "" })}
     ${field("Descripción", "description", "text", "", { placeholder: "Ej: Sueldo de agosto" })}
     <input type="hidden" id="income-record-target" name="source_id" value="">
     <p class="text-xs text-slate-400">Se creará un movimiento tipo <b>Ingreso</b> en la cuenta elegida.</p>`)}
  `;
  const yearSel = document.getElementById("income-year");
  const monthSel = document.getElementById("income-month");
  if (yearSel) {
    yearSel.addEventListener("change", () => {
      state.dashboardYear = Number(yearSel.value) || null;
      route();
    });
  }
  if (monthSel) {
    monthSel.addEventListener("change", () => {
      state.dashMonth = Number(monthSel.value) || null;
      route();
    });
  }
}

function incomePeriodDate() {
  const now = new Date();
  const year = state.dashboardYear || now.getFullYear();
  const month = state.dashMonth || now.getMonth() + 1;
  if (year === now.getFullYear() && month === now.getMonth() + 1) return todayISO();
  const day = Math.min(now.getDate(), new Date(year, month, 0).getDate());
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function openIncomeNew() {
  const form = document.getElementById("income-form");
  form.reset();
  form.elements.status.value = "active";
  form.elements.source_id.value = "";
  form.elements.expected_amount.value = "0";
  openModal("income-modal");
}

function openIncomeEdit(id) {
  const s = state.incomeSources.find((x) => x.id === id);
  if (!s) return;
  const form = document.getElementById("income-form");
  form.elements.source_id.value = id;
  form.elements.name.value = s.name;
  form.elements.member_id.value = s.member_id || "";
  form.elements.type.value = s.type;
  form.elements.expected_amount.value = s.expected_amount;
  form.elements.status.value = s.status;
  openModal("income-modal");
}

async function saveIncomeSource(data) {
  const sourceId = data.source_id;
  delete data.source_id;
  data.expected_amount = Number(data.expected_amount || 0);
  if (!data.member_id) delete data.member_id;
  try {
    if (sourceId) {
      await api(`/api/v1/income-sources/${sourceId}`, { method: "PATCH", body: data });
      toast("Fuente actualizada");
    } else {
      await api(`/api/v1/households/${state.householdId}/income-sources`, { method: "POST", body: data });
      toast("Fuente de ingreso creada");
    }
    closeModal("income-modal");
    route();
  } catch {
    /* api() ya notifica el error */
  }
}

async function toggleIncomeSource(id) {
  const s = state.incomeSources.find((x) => x.id === id);
  if (!s) return;
  try {
    await api(`/api/v1/income-sources/${id}`, { method: "PATCH", body: { status: s.status === "active" ? "inactive" : "active" } });
    toast(s.status === "active" ? "Fuente pausada" : "Fuente activada");
    route();
  } catch {
    /* api() ya notifica el error */
  }
}

async function deleteIncomeSource(id) {
  if (!confirm("¿Eliminar esta fuente de ingreso? Los movimientos registrados no se borran.")) return;
  try {
    await api(`/api/v1/income-sources/${id}`, { method: "DELETE" });
    toast("Fuente eliminada");
  } catch {
    /* api() ya notifica el error */
  }
  route();
}

function recordIncome(id) {
  const s = state.incomeSources.find((x) => x.id === id);
  if (!s) return;
  const form = document.getElementById("income-record-form");
  const accountEl = form.elements.account_id;
  if (accountEl.options.length) accountEl.value = accountEl.options[0].value;
  form.elements.source_id.value = id;
  form.elements.amount.value = s.expected_amount || "";
  form.elements.date.value = incomePeriodDate();
  form.elements.description.value = s.name || "";
  form.elements.category_id.value = "";
  openModal("income-record-modal");
}

function openRecordIncome() {
  const form = document.getElementById("income-record-form");
  const accountEl = form.elements.account_id;
  if (accountEl.options.length) accountEl.value = accountEl.options[0].value;
  form.elements.source_id.value = "";
  form.elements.amount.value = "";
  form.elements.date.value = incomePeriodDate();
  form.elements.description.value = "";
  form.elements.category_id.value = "";
  openModal("income-record-modal");
}

async function saveRecordedIncome(data) {
  const s = state.incomeSources.find((x) => x.id === data.source_id);
  const payload = {
    account_id: data.account_id,
    type: "income",
    amount: Number(data.amount),
    date: data.date,
    description: data.description || (s ? s.name : "Ingreso"),
  };
  if (data.category_id) payload.category_id = data.category_id;
  try {
    await api("/api/v1/transactions", { method: "POST", body: payload });
    toast("Ingreso registrado en Movimientos");
    closeModal("income-record-modal");
    route();
  } catch {
    /* api() ya notifica el error */
  }
}

/* ---------- Configuración (hogar, miembros, fuentes, categorías, avisos) ---------- */

async function renderConfig(mainEl) {
  const household = state.households.find((h) => h.id === state.householdId) || state.households[0];
  let notifyPrefs = [];
  try {
    notifyPrefs = await api(`/api/v1/households/${state.householdId}/notification-preferences`);
  } catch {
    notifyPrefs = [];
  }
  const notifyCards = notifyPrefs
    .map(
      (pref) => `<label class="flex items-center justify-between py-1.5 border-b last:border-0 cursor-pointer gap-2">
        <div><div class="font-medium text-sm">${esc(NOTIFICATION_LABEL[pref.template_kind] || pref.template_kind)}</div></div>
        <input type="checkbox" data-kind="${esc(pref.template_kind)}" ${pref.enabled ? "checked" : ""} onchange="toggleNotification(this)" class="w-5 h-5 accent-brand-amber shrink-0">
      </label>`
    )
    .join("");
  const members = state.members
    .map(
      (m) => `<div class="flex items-center justify-between py-2 border-b last:border-0">
        <div><div class="font-medium">${esc(m.name)}</div><div class="text-xs text-slate-400">${esc(m.role)} · ${esc(m.status)}</div></div>
        <button onclick="deleteMember('${esc(m.id)}', '${esc(m.name)}')" class="text-xs text-rose-600 hover:text-rose-800 border border-rose-200 rounded-md px-2 py-1" title="Eliminar miembro">Eliminar</button>
      </div>`
    )
    .join("");
  const sources = state.incomeSources;
  const catsByKind = {};
  for (const c of state.categories) (catsByKind[c.kind] = catsByKind[c.kind] || []).push(c);
  const catRows = Object.keys(catsByKind)
    .map(
      (kind) => `
      <div class="mb-3"><h3 class="text-xs font-bold text-slate-400 uppercase mb-1">${esc(kind)}</h3>
        <div class="flex flex-wrap gap-1.5">
          ${catsByKind[kind].map((c) => `<span class="px-2 py-1 rounded-full text-xs ${c.status === "active" ? "bg-brand-amber/30 text-brand-amber-dark" : "bg-slate-100 text-slate-400"}">${esc(c.name)}</span>`).join("")}
        </div></div>`
    )
    .join("");
  mainEl.innerHTML = `
  <div class="mb-6"><h1 class="text-2xl font-extrabold">Hogar y categorías</h1><p class="text-sm text-slate-500">${esc(household?.name || "")}</p></div>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <div class="bg-white rounded-xl shadow p-5">
      <h2 class="font-bold mb-3">Miembros
        <button onclick="openModal('member-modal')" class="ml-2 px-3 py-1 rounded-md bg-brand-navy hover:bg-brand-navy-dark text-white text-xs font-semibold">Agregar</button>
      </h2>
      ${members || '<p class="text-sm text-slate-400">Sin miembros</p>'}
    </div>
    <div class="bg-white rounded-xl shadow p-5">
      <h2 class="font-bold mb-3">Categorías</h2>
      ${catRows || '<p class="text-sm text-slate-400">Sin categorías</p>'}
      <button onclick="openModal('cat-modal')" class="mt-3 px-3 py-1 rounded-md bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-semibold">Nueva categoría</button>
    </div>
    <div class="bg-white rounded-xl shadow p-5">
      <h2 class="font-bold mb-3">Fuentes de ingreso</h2>
      <div id="sources-panel">${sources && sources.length ? sources.map((s) => `<div class="py-1 text-sm">${esc(s.name)} · ${money(s.expected_amount)}</div>`).join("") : '<p class="text-sm text-slate-400">Sin fuentes</p>'}</div>
      <button onclick="openModal('source-modal')" class="mt-3 px-3 py-1 rounded-md bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-semibold">Nueva fuente</button>
    </div>
    <div class="bg-white rounded-xl shadow p-5">
      <h2 class="font-bold mb-3">Preferencias de avisos
        <a href="#/notifications" class="ml-2 text-xs font-semibold text-brand-amber-dark hover:underline">ver Avisos →</a>
      </h2>
      ${notifyCards || '<p class="text-sm text-slate-400">Sin preferencias configuradas.</p>'}
    </div>
  </div>
  <div class="mt-8 bg-white rounded-xl shadow p-5 border border-rose-100">
    <h2 class="font-bold text-rose-700 mb-1">Zona de peligro</h2>
    <p class="text-sm text-slate-500 mb-3">Elimina el hogar «${esc(household?.name || "")}» y todos sus datos (cuentas, movimientos, presupuestos, importaciones). Esta acción no se puede deshacer.</p>
    <button onclick="deleteHousehold()" class="px-3 py-2 rounded-md bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold">Eliminar hogar</button>
  </div>
  ${modal("member-modal", "Nuevo miembro", "member-form", "createMember",
    `${field("Nombre", "name", "text", "", { required: "" })}
     ${select("Rol", "role", [["member", "Miembro"], ["admin", "Admin"]], "member")}`)}
  ${modal("cat-modal", "Nueva categoría", "cat-form", "createCategory",
    `${field("Nombre", "name", "text", "", { required: "" })}
     ${select("Tipo", "kind", [["expense", "Gasto"], ["income", "Ingreso"], ["transfer", "Transferencia"]], "expense")}`)}
  ${modal("source-modal", "Nueva fuente de ingreso", "source-form", "createSource",
    `${field("Nombre", "name", "text", "", { required: "" })}
     ${select("Miembro", "member_id", state.members.map((m) => [m.id, m.name]).concat([["", "Sin miembro"]]))}
     ${field("Monto esperado mensual (CLP)", "expected_amount", "number", "0", { min: "0" })}`)}
  `;
}

async function createMember(data) {
  await api(`/api/v1/households/${state.householdId}/members`, { method: "POST", body: data });
  toast("Miembro agregado");
  closeModal("member-modal");
  route();
}

async function deleteInstitution(id, name) {
  if (!confirm(`¿Eliminar la institución «${name}»? Las cuentas que la usen quedarán sin institución.`)) return;
  try {
    await api(`/api/v1/financial-institutions/${id}`, { method: "DELETE" });
    toast("Institución eliminada");
  } catch {
    /* toast ya notificó */
  }
  await refreshCatalog(state.householdId);
  route();
}

async function deleteMember(memberId, name) {
  if (!confirm(`¿Eliminar al miembro «${name}»? Las referencias quedarán sin autor, no se borrarán movimientos.`)) return;
  try {
    await api(`/api/v1/members/${memberId}`, { method: "DELETE" });
    toast("Miembro eliminado");
  } catch {
    /* api() ya notifica el error */
  }
  route();
}

async function deleteHousehold() {
  const household = state.households.find((h) => h.id === state.householdId) || state.households[0];
  if (!household) return;
  if (!confirm(`¿Eliminar el hogar «${household.name}» y TODOS sus datos? Esta acción no se puede deshacer.`)) return;
  try {
    await api(`/api/v1/households/${household.id}`, { method: "DELETE" });
    toast("Hogar eliminado");
    localStorage.removeItem("cf.householdId");
    state.households = state.households.filter((h) => h.id !== household.id);
    if (state.households.length) {
      state.householdId = state.households[0].id;
      localStorage.setItem("cf.householdId", state.householdId);
    } else {
      state.householdId = null;
    }
  } catch {
    /* api() ya notifica el error */
  }
  route();
}

async function createCategory(data) {
  await api(`/api/v1/households/${state.householdId}/categories`, { method: "POST", body: data });
  toast("Categoría creada");
  closeModal("cat-modal");
  route();
}

async function createSource(data) {
  if (!data.member_id) delete data.member_id;
  data.expected_amount = Number(data.expected_amount || 0);
  await api(`/api/v1/households/${state.householdId}/income-sources`, { method: "POST", body: data });
  toast("Fuente creada");
  closeModal("source-modal");
  route();
}

/* ---------- Asistente con IA local (Fase 3, CF3-01..CF3-08) ---------- */

async function renderAi(mainEl) {
  const now = new Date();
  const quickActions = `
    <div class="flex flex-wrap gap-2">
      <a href="#/reportes" class="px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-sm text-slate-600 hover:border-brand-amber hover:text-brand-amber-dark">Ver Reportes</a>
      <a href="#/transactions?new=1" class="px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-sm text-slate-600 hover:border-brand-amber hover:text-brand-amber-dark">Registrar movimiento</a>
      <a href="#/simulador" class="px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-sm text-slate-600 hover:border-brand-amber hover:text-brand-amber-dark">Simular pagos</a>
      <a href="#/budgets" class="px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-sm text-slate-600 hover:border-brand-amber hover:text-brand-amber-dark">Asignar presupuesto</a>
    </div>`;
  mainEl.innerHTML = `
  <div class="mb-6"><h1 class="text-2xl font-extrabold">Asistente</h1><p class="text-sm text-slate-500">IA local que propone; la decisión final siempre es tuya.</p></div>
  <div class="mb-6">${quickActions}</div>
  <div class="bg-white rounded-xl shadow p-4 mb-6">
    <h2 class="text-sm font-bold text-slate-600 mb-3">Analizar un mes</h2>
    <div class="flex flex-wrap items-end gap-2">
      <div class="w-32">${select("Mes", "aiMonth", monthOptions(), String(now.getMonth() + 1))}</div>
      <div class="w-32">${select("Año", "aiYear", yearOptions(), String(now.getFullYear()))}</div>
      <button onclick="aiAnalyze()" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Analizar mes</button>
    </div>
  </div>
  <div id="ai-insights" class="mb-6"></div>
  <div class="bg-white rounded-xl shadow p-4 mb-6">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-sm font-bold text-slate-600">Propuestas del asistente</h2>
      <button onclick="aiReloadProposals()" class="text-xs text-brand-amber-dark hover:underline">Recargar</button>
    </div>
    <div id="ai-proposals" class="space-y-2"></div>
  </div>
  <div class="bg-white rounded-xl shadow p-4">
    <h2 class="text-sm font-bold text-slate-600 mb-3">Sugerir categoría para una descripción</h2>
    <div class="flex flex-wrap items-end gap-2">
      <div class="flex-1 min-w-56">
        <label class="block text-xs font-semibold text-slate-500 mb-1" for="aiDesc">Descripción</label>
        <input id="aiDesc" placeholder="Ej: Supermercado Santa Isabel" class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-amber"/>
      </div>
      <div class="w-32">${field("Monto (CLP)", "aiAmount", "number", "", { min: "1", step: "1" })}</div>
      <button onclick="aiSuggest()" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Sugerir</button>
    </div>
    <div id="ai-suggestions" class="mt-3 space-y-1"></div>
  </div>
  `;
  aiAnalyze();
}

async function aiAnalyze() {
  const month = document.getElementById("aiMonth")?.value;
  const year = document.getElementById("aiYear")?.value;
  const panel = document.getElementById("ai-insights");
  if (!panel) return;
  panel.innerHTML = `<div class="text-slate-400 text-sm">Analizando…</div>`;
  let data;
  try {
    data = await api(`/api/v1/households/${state.householdId}/assistant/insights?year=${year}&month=${month}`);
  } catch {
    panel.innerHTML = "";
    return;
  }
  const severityColor = { danger: "border-rose-200 bg-rose-50", warning: "border-brand-amber/40 bg-brand-amber/15", info: "border-sky-200 bg-sky-50" };
  const insights = (data.insights || [])
    .map((item) => `<div class="p-3 rounded-lg border ${severityColor[item.severity] || severityColor.info}">
      <div class="font-semibold text-sm">${esc(item.title)}</div>
      <div class="text-sm text-slate-600">${esc(item.detail)}</div>
    </div>`)
    .join("");
  const anomalies = (data.anomalies || [])
    .map((a) => `<div class="p-3 rounded-lg border border-brand-amber/40 bg-brand-amber/15">
      <div class="font-semibold text-sm">${esc(a.title)}</div>
      <div class="text-sm text-slate-600">${esc(a.detail)}</div>
      ${a.suggested_planned_amount ? `<div class="mt-1 text-xs text-brand-amber-dark">Ajuste propuesto al presupuesto: <b>${money(a.suggested_planned_amount)}</b></div>` : ""}
    </div>`)
    .join("");
  panel.innerHTML = `
    <div class="mb-2 flex items-center justify-between">
      <h2 class="text-sm font-bold text-slate-600">Resumen de ${data.period}</h2>
      <span class="text-xs text-slate-400">Proveedor: ${esc(data.provider)} · local y gratuito</span>
    </div>
    ${insights || '<p class="text-sm text-slate-400">Sin observaciones para el mes.</p>'}
    ${anomalies ? `<h3 class="text-sm font-bold text-slate-600 mt-4 mb-2">Anomalías detectadas</h3>${anomalies}` : ""}
  `;
  aiReloadProposals();
}

async function aiReloadProposals() {
  const panel = document.getElementById("ai-proposals");
  if (!panel) return;
  let proposals;
  try {
    proposals = await api(`/api/v1/households/${state.householdId}/assistant/proposals`);
  } catch {
    return;
  }
  if (!proposals.length) {
    panel.innerHTML = `<p class="text-sm text-slate-400">Sin propuestas por ahora.</p>`;
    return;
  }
  const AI_KIND_LABEL = {
    category_suggestion: "Sugerencia de categoría",
    insight: "Observación",
    anomaly: "Anomalía",
    budget_adjust: "Ajuste de presupuesto",
  };
  const AI_STATUS_LABEL = { pending: "En revisión", applied: "Aplicada", dismissed: "Descartada" };
  panel.innerHTML = proposals
    .map((p) => {
      const payload = p.payload || {};
      let body = "";
      if (p.kind === "category_suggestion") {
        const name = (payload.suggestions || []).map((s) => s.category_name).join(", ");
        body = `<div class="text-sm text-slate-600">${esc(payload.description || "")} → <b>${esc(name || "sin sugerencia")}</b></div>`;
      } else if (p.kind === "insight") {
        body = `<div class="text-sm text-slate-600">${esc(payload.title || "")}</div>
                <div class="text-sm text-slate-500">${esc(payload.detail || "")}</div>`;
      } else if (p.kind === "anomaly") {
        body = `<div class="text-sm text-slate-600">${esc(payload.title || "")}</div>`;
      } else if (p.kind === "budget_adjust") {
        body = `<div class="text-sm text-slate-600">Ajustar plan de ${esc(payload.title || "la categoría")} a <b>${money(payload.suggested_planned_amount)}</b></div>`;
      }
      const badge = p.status === "pending" ? "bg-brand-amber/30 text-brand-amber-dark" : p.status === "applied" ? "bg-brand-turquoise/20 text-brand-turquoise-dark" : "bg-slate-100 text-slate-500";
      const actions =
        p.status === "pending"
          ? `<div class="flex gap-2">
              ${p.kind === "budget_adjust" ? `<button onclick="aiResolve('${p.id}', 'applied')" class="px-3 py-1 rounded-md bg-brand-turquoise hover:bg-brand-turquoise-dark text-white text-xs font-semibold">Aplicar ajuste</button>` : ""}
              <button onclick="aiResolve('${p.id}', 'dismissed')" class="px-3 py-1 rounded-md border border-slate-300 text-xs">Descartar</button>
            </div>`
          : "";
      return `<div class="p-3 rounded-lg border border-slate-200">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-xs font-semibold uppercase tracking-wide text-slate-400">${esc(AI_KIND_LABEL[p.kind] || p.kind)}</span>
              <span class="px-2 py-0.5 rounded-full text-xs ${badge}">${esc(AI_STATUS_LABEL[p.status] || p.status)}</span>
            </div>
            ${body}
          </div>
          ${actions}
        </div>
      </div>`;
    })
    .join("");
}

async function aiResolve(proposalId, resolution) {
  if (resolution === "applied" && !confirm("¿Aplicar el ajuste propuesto? Se modifica el presupuesto.")) return;
  let proposal;
  try {
    proposal = await api(`/api/v1/assistant/proposals/${proposalId}/resolve`, { method: "POST", body: { resolution } });
  } catch {
    return;
  }
  toast(proposal.status === "applied" ? "Ajuste aplicado" : "Propuesta descartada");
  aiReloadProposals();
}

async function aiSuggest() {
  const panel = document.getElementById("ai-suggestions");
  const description = (document.getElementById("aiDesc")?.value || "").trim();
  if (!description) {
    toast("Escribe una descripción", false);
    return;
  }
  const amount = Number(document.getElementById("aiAmount")?.value || 0);
  const body = { description };
  if (amount > 0) body.amount = amount;
  let result;
  try {
    result = await api(`/api/v1/households/${state.householdId}/assistant/suggest-category`, { method: "POST", body });
  } catch {
    return;
  }
  const suggestions = result.suggestions || [];
  if (!suggestions.length) {
    panel.innerHTML = `<p class="text-sm text-slate-400">Sin sugerencias: no hay reglas ni historial para esa descripción.</p>`;
    return;
  }
  panel.innerHTML = suggestions
    .map(
      (s) => `<div class="flex flex-wrap items-center justify-between gap-2 p-2 rounded-lg border ${s.rank === 1 ? "border-brand-amber/60 bg-brand-amber/15" : "border-slate-200"}">
        <div>
          <span class="font-semibold text-sm">${esc(s.category_name)}</span>
          <span class="text-xs text-slate-500"> · ${esc(s.reason)}</span>
        </div>
        <span class="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">${Math.round(s.confidence * 100)}%</span>
      </div>`
    )
    .join("");
}

async function suggestTxnCategory() {
  const form = document.getElementById("txn-form");
  if (!form) return;
  const type = form.querySelector("#type")?.value;
  if (type !== "expense") {
    toast("La sugerencia aplica a gastos", false);
    return;
  }
  const description = (form.querySelector("#description")?.value || "").trim();
  if (!description) {
    toast("Escribe una descripción primero", false);
    return;
  }
  const amount = Number(form.querySelector("#amount")?.value || 0);
  const body = { description };
  if (amount > 0) body.amount = amount;
  let result;
  try {
    result = await api(`/api/v1/households/${state.householdId}/assistant/suggest-category`, { method: "POST", body });
  } catch {
    return;
  }
  const suggestion = result.suggestions?.[0];
  if (!suggestion) {
    toast("Sin sugerencia para esa descripción", false);
    return;
  }
  const catSelect = form.querySelector("#category_id");
  if (catSelect) {
    const option = Array.from(catSelect.options).find((o) => o.value === suggestion.category_id);
    if (option) {
      catSelect.value = suggestion.category_id;
      catSelect.dispatchEvent(new Event("change"));
    }
  }
  toast(`Asistente: ${suggestion.category_name} (${suggestion.reason})`);
}

/* ---------- Tarjetas de crédito (UI-4) ---------- */

async function renderCreditCards(mainEl) {
  mainEl.innerHTML = `<div class="text-slate-400">Cargando tarjetas…</div>`;
  let summary = null;
  let upcoming = null;
  try {
    [summary, upcoming] = await Promise.all([
      api(`/api/v1/households/${state.householdId}/debt-summary`),
      api(`/api/v1/households/${state.householdId}/upcoming-payments?days=60`),
    ]);
  } catch {
    return;
  }
  const cards = (state.accounts || []).filter((a) => a.type === "credit_card");
  const ccDebts = (state.debts || []).filter((d) => d.type === "credit_card");
  const debtByAccount = Object.fromEntries(ccDebts.map((d) => [d.account_id, d]));
  const nextMin = (upcoming.recurring_minimums || []).reduce((a, p) => a + (Number(p.minimum_payment) || 0), 0);
  const totalCalc = cards.reduce((a, c) => a + (Number(c.balance_calculated) || 0), 0);

  const cardsHtml = cards.length
    ? cards
        .map((c, idx) => {
          const reported = Math.max(0, Number(c.balance_reported) || 0);
          const calc = Math.max(0, Number(c.balance_calculated) || 0);
          const cupo = Math.max(0, Number(c.credit_limit) || 0);
          const alignPct = cupo > 0 ? Math.round((calc / cupo) * 100) : reported > 0 ? Math.round((calc / reported) * 100) : null;
          const linked = debtByAccount[c.id];
          return `
          <div class="cf-card cf-fade text-white" style="background:linear-gradient(135deg,#123b4a 0%,#0f2a33 60%,#19b5a5 160%)">
            <div class="flex items-start justify-between">
              <div class="min-w-0">
                <div class="text-[10px] font-semibold text-slate-300/80 uppercase tracking-wide">${esc(c.institution_name || ACCOUNT_TYPE_LABEL[c.type] || "Tarjeta")}</div>
                <div class="font-bold text-lg truncate mt-0.5">${esc(c.name)}</div>
                <div class="mt-4 flex items-baseline gap-2">
                  <span class="text-xl font-extrabold">${money(calc)}</span>
                  <span class="text-xs text-slate-300/80">informado ${money(reported)}</span>
                </div>
              </div>
              <svg class="shrink-0 opacity-70" width="34" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20M6 15h4"/></svg>
            </div>
            ${cupo > 0 ? `<div class="mt-3 text-xs text-slate-300/80">Cupo <span class="font-bold text-white">${money(cupo)}</span></div>` : ""}
            ${alignPct != null ? `<div class="mt-2"><div class="text-[10px] text-slate-300/80 mb-1">${alignPct}% del ${cupo > 0 ? "cupo utilizado" : "saldo informado"}</div><div class="progress-track" style="background:rgba(255,255,255,.18)"><div class="progress-fill is-ok" style="width:${Math.min(100, alignPct)}%;background:#19b5a5"></div></div></div>` : ""}
            ${linked ? `<div class="mt-3 rounded-lg bg-black/20 p-2 text-xs flex items-center justify-between">
              <span>Deuda: <span class="font-bold">${money(linked.current_balance)}</span> · mín ${money(linked.minimum_payment)}</span>
              <a href="#/debts" class="underline font-semibold text-brand-amber-dark">Ver</a>
            </div>` : ""}
          </div>`;
        })
        .join("")
    : emptyState("Aún no tienes tarjetas de crédito entre tus cuentas.", `<button onclick="openModal('acc-modal')" class="mt-3 px-4 py-2 rounded-lg bg-brand-navy text-white text-sm font-semibold">Nueva tarjeta</button>`);

  mainEl.innerHTML = `
  ${pageHeader("Tarjetas de crédito", "Saldos, deuda asociada y cuota mínima de cada plástico.", "")}
  <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
    ${kpiCard({ label: "Deuda total en tarjetas", value: money(ccDebts.reduce((a, d) => a + (d.current_balance || 0), 0)), icon: "M2 10h20M2 14h20M6 6h12a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2z", color: "#b8860b", footer: `${ccDebts.length} deuda(s) tipo tarjeta` })}
    ${kpiCard({ label: "Saldo en cuentas de tarjetas", value: money(totalCalc), icon: "M4 6h16v12H4zM4 10h16", color: "#123b4a", footer: `${cards.length} tarjeta(s) en cuentas` })}
    ${kpiCard({ label: "Cuotas mínimas (60 días)", value: money(nextMin), icon: "M12 6v6l4 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "#38bdf8", footer: "mínimos recurrentes" })}
    ${kpiCard({ label: "Deuda total del hogar", value: money(summary.total_current_balance || 0), icon: "M9 6h6a3 3 0 010 6M9 6a3 3 0 010 6M9 6V3M9 12H6M9 12v3M15 12h2l-4 7M17 4l3 6-3 2", color: "#19b5a5", href: "#/debts" })}
  </div>
  <div class="text-xs bg-brand-amber/15 border border-brand-amber/40 rounded-lg px-3 py-2 text-amber-900 mb-6">
    Cada tarjeta captura su <strong>cupo</strong> (CLP) en la cuenta; la utilización se muestra como saldo ÷ cupo. Si una tarjeta no tiene cupo definido, se usa el saldo informado como referencia. La cuota pendiente se registra como deuda.
  </div>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
    <div class="lg:col-span-2">
      <h2 class="font-bold mb-3">Tus tarjetas</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">${cardsHtml || emptyState("Aún no hay tarjetas.")}</div>
    </div>
    <div>
      <h2 class="font-bold mb-3">Deudas por tarjeta</h2>
      ${ccDebts.length ? `<div class="cf-card space-y-3">${ccDebts
        .map(
          (d) => `<div>
            <div class="flex items-center justify-between text-sm mb-1">
              <span class="font-medium truncate">${esc(d.name)}</span>
              <span class="font-bold">${money(d.current_balance)}</span>
            </div>
            ${progressBar(Math.max(0, d.original_amount - d.current_balance), d.original_amount)}
            <div class="text-xs text-slate-400 mt-1">Vence el día ${d.due_day} · mín ${money(d.minimum_payment)}</div>
          </div>`
        )
        .join("")}</div>
      <a href="#/debts" class="mt-3 inline-block text-sm text-brand-amber-dark font-semibold hover:underline">Gestionar deudas →</a>` : `<div class="cf-card text-sm text-slate-400">No hay deudas asociadas a tarjetas.</div>`}
    </div>
  </div>
  ${accountsModalHtml()}
  `;
}

/* ---------- Metas de ahorro (UI-6) ---------- */

const GOAL_CATEGORY_META = {
  fondo: { label: "Fondo de emergencia", icon: "M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z", color: "#19b5a5" },
  security: { label: "Seguridad", icon: "M12 3l7 3v5c0 4.4-2.5 8.3-7 10-4.5-1.7-7-5.6-7-10V6zM9 12l2 2 4-4", color: "#123b4a" },
  travel: { label: "Viajes", icon: "M3 18L21 6M3 18a3 3 0 105 0 3 3 0 00-5 0zM21 6a3 3 0 11-6 0 3 3 0 016 0z", color: "#38bdf8" },
  purchase: { label: "Compra grande", icon: "M12 3v12M7 6l5-3 5 3M5 15h14M7 15v4a2 2 0 002 2h6a2 2 0 002-2v-4", color: "#f4b942" },
  debt: { label: "Pago de deuda", icon: "M9 6h6v12H9zM6 6h12M6 18h12M12 6V4", color: "#e15554" },
  other: { label: "Otra meta", icon: "M12 6v12M6 12h12", color: "#7c3aed" },
};

function goalCategoryMeta(cat) {
  return GOAL_CATEGORY_META[cat] || { label: "Otra meta", icon: "M12 6v12M6 12h12", color: "#7c3aed" };
}

async function fetchGoals() {
  return api(`/api/v1/households/${state.householdId}/goals`);
}

async function renderGoals(mainEl) {
  mainEl.innerHTML = `<div class="text-slate-400">Cargando metas…</div>`;
  let goals = [];
  try {
    goals = await fetchGoals();
  } catch {
    return;
  }
  state.goals = goals;
  const active = goals.filter((g) => g.status === "active");
  const achieved = goals.filter((g) => g.status === "achieved");
  const targetTotal = active.reduce((a, g) => a + (g.target_amount || 0), 0);
  const savedTotal = active.reduce((a, g) => a + (g.current_amount || 0), 0);
  const avgPct = active.length ? Math.round(active.reduce((a, g) => a + progressPct(g.current_amount, g.target_amount), 0) / active.length) : 0;
  const nextDue = active
    .filter((g) => g.target_date)
    .sort((a, b) => a.target_date.localeCompare(b.target_date))
    .slice(0, 3);
  const accOptions = state.accounts.filter((a) => a.status === "active").map((a) => [a.id, a.name]);

  const goalCards = goals.length
    ? goals
        .map((g) => {
          const meta = goalCategoryMeta(g.category);
          const pct = progressPct(g.current_amount, g.target_amount);
          return `
          <div class="cf-card cf-fade">
            <div class="flex items-start justify-between gap-2">
              <div class="flex items-center gap-3 min-w-0">
                <div class="kpi-icon" style="background:${meta.color}">${svgIcon(meta.icon)}</div>
                <div class="min-w-0">
                  <div class="font-bold truncate">${esc(g.name)}</div>
                  <div class="text-xs text-slate-400">${esc(meta.label)}${g.target_date ? ` · hacia ${esc(formatDate(g.target_date))}` : ""}</div>
                </div>
              </div>
              <span class="state-badge ${g.status === "achieved" ? "bien" : g.status === "archived" ? "" : "atencion"} whitespace-nowrap">${esc(g.status)}</span>
            </div>
            <div class="mt-4">${progressBar(g.current_amount, g.target_amount)}</div>
            <div class="mt-2 flex flex-wrap justify-between text-xs text-slate-500">
              <span>${money(g.current_amount)} de ${money(g.target_amount)}</span>
              <span>${pct}% · aporte ${money(g.monthly_contribution)}/mes</span>
            </div>
            <div class="mt-4 flex flex-wrap gap-2">
              <button onclick="openModal('goal-contribute-${g.id}')" ${g.status !== "active" ? "disabled" : ""} class="px-3 py-1.5 rounded-md bg-brand-turquoise hover:bg-brand-turquoise-dark text-white text-xs font-semibold ${g.status !== "active" ? "opacity-40 cursor-not-allowed" : ""}">Aportar</button>
              <button onclick="openModal('goal-edit-${g.id}')" class="px-3 py-1.5 rounded-md bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-semibold">Editar</button>
              ${g.status === "active" ? `<button onclick="archiveGoal('${g.id}')" class="px-3 py-1.5 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-500 text-xs font-semibold">Archivar</button>` : ""}
            </div>
          </div>
          ${modal(`goal-contribute-${g.id}`, `Aportar · ${esc(g.name)}`, `goal-contribute-form-${g.id}`, "",
            `${field("Monto (CLP)", "amount", "number", "", { required: "", min: "1" })}
             ${select("Desde la cuenta", "account_id", accOptions.concat([["", "Sin asociar"]]))}
             ${field("Fecha", "date", "date", todayISO())}`)}
          ${modal(`goal-edit-${g.id}`, `Editar · ${esc(g.name)}`, `goal-edit-form-${g.id}`, "",
            `${field("Nombre", "name", "text", esc(g.name), { required: "" })}
             ${select("Categoría", "category", Object.entries(GOAL_CATEGORY_META).map(([k, m]) => [k, m.label]), g.category)}
             ${field("Monto objetivo (CLP)", "target_amount", "number", String(g.target_amount), { required: "", min: "1" })}
             ${field("Aporte mensual (CLP)", "monthly_contribution", "number", String(g.monthly_contribution || 0), { min: "0" })}
             ${field("Fecha objetivo", "target_date", "date", (g.target_date || "").slice(0, 10))}`)}`;
        })
        .join("")
    : "";

  mainEl.innerHTML = `
  ${pageHeader("Metas de ahorro", "Objetivos con aportes mensuales para fondear compras, viajes o protecciones.", `<button onclick="openModal('goal-modal')" class="px-4 py-2 rounded-lg bg-brand-navy hover:bg-brand-navy-dark text-white text-sm font-semibold">Nueva meta</button>`)}
  <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
    ${kpiCard({ label: "Metas activas", value: String(active.length), icon: "M12 3v12M7 6l5-3 5 3M5 15h14M7 15v4a2 2 0 002 2h6a2 2 0 002-2v-4", color: "#123b4a", footer: `${achieved.length} ya lograda(s)` })}
    ${kpiCard({ label: "Monto objetivo", value: money(targetTotal), icon: "M2 12h20M8 8v8M16 8v8M4 19V5", color: "#f4b942", footer: "metas activas" })}
    ${kpiCard({ label: "Ahorrado", value: money(savedTotal), icon: "M12 3v18M17 7l-5-4-5 4M5 17h14M8 21h8", color: "#19b5a5", footer: targetTotal ? `${Math.round((savedTotal / targetTotal) * 100)}% del objetivo` : "agrega una meta" })}
    ${kpiCard({ label: "Avance promedio", value: `${avgPct}%`, icon: "M12 6v6l4 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "#7c3aed", footer: "de las metas activas" })}
  </div>
  ${nextDue.length ? `<div class="cf-card mb-6"><h2 class="font-bold text-sm mb-2">Próximas a vencer</h2><div class="flex flex-wrap gap-2">${nextDue
    .map((g) => `<a href="#/goals" class="px-3 py-1.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 hover:bg-slate-200">${esc(g.name)} · ${esc(formatDate(g.target_date))}</a>`)
    .join("")}</div></div>` : ""}
  ${goals.length ? `<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">${goalCards}</div>` : ""}
  <div class="cf-card ${goals.length ? "text-sm text-slate-500" : ""}">
    ${goals.length ? "" : emptyState("Todavía no tienes metas. Define un objetivo, aporta mes a mes y míralo crecer.", `<button onclick="openModal('goal-modal')" class="mt-3 px-4 py-2 rounded-lg bg-brand-navy text-white text-sm font-semibold">Nueva meta</button>`)}
  </div>
  ${modal("goal-modal", "Nueva meta de ahorro", "goal-form", "createGoal",
    `${field("Nombre", "name", "text", "", { required: "", placeholder: "Ej: Viaje a la Patagonia" })}
     ${select("Categoría", "category", Object.entries(GOAL_CATEGORY_META).map(([k, m]) => [k, m.label]), "fondo")}
     <div class="grid grid-cols-2 gap-3">
       ${field("Monto objetivo (CLP)", "target_amount", "number", "", { required: "", min: "1" })}
       ${field("Aporte mensual (CLP)", "monthly_contribution", "number", "0", { min: "0" })}
     </div>
     ${field("Fecha objetivo (opcional)", "target_date", "date", "")}
     ${field("Aporte inicial (CLP)", "current_amount", "number", "0", { min: "0" })}`)}
  `;
}

async function createGoal(data) {
  data.target_amount = Number(data.target_amount || 0);
  data.monthly_contribution = Number(data.monthly_contribution || 0);
  data.current_amount = Number(data.current_amount || 0);
  if (!data.target_date) delete data.target_date;
  await api(`/api/v1/households/${state.householdId}/goals`, { method: "POST", body: data });
  toast("Meta creada");
  closeModal("goal-modal");
  route();
}

document.addEventListener("submit", (e) => {
  if (!e.target.id || !e.target.id.startsWith("goal-contribute-form-")) return;
  e.preventDefault();
  const goalId = e.target.id.replace("goal-contribute-form-", "");
  const data = Object.fromEntries(new FormData(e.target).entries());
  data.amount = Number(data.amount || 0);
  if (!data.account_id) delete data.account_id;
  if (!data.date) delete data.date;
  api(`/api/v1/goals/${goalId}/contributions`, { method: "POST", body: data })
    .then(() => {
      toast("Aporte registrado");
      closeModal(`goal-contribute-${goalId}`);
      route();
    });
});

document.addEventListener("submit", (e) => {
  if (!e.target.id || !e.target.id.startsWith("goal-edit-form-")) return;
  e.preventDefault();
  const goalId = e.target.id.replace("goal-edit-form-", "");
  const data = Object.fromEntries(new FormData(e.target).entries());
  data.target_amount = Number(data.target_amount || 0);
  data.monthly_contribution = Number(data.monthly_contribution || 0);
  if (!data.target_date) delete data.target_date;
  api(`/api/v1/goals/${goalId}`, { method: "PATCH", body: data })
    .then(() => {
      toast("Meta actualizada");
      closeModal(`goal-edit-${goalId}`);
      route();
    });
});

async function archiveGoal(goalId) {
  await api(`/api/v1/goals/${goalId}`, { method: "PATCH", body: { status: "archived" } });
  toast("Meta archivada");
  route();
}

/* ---------- Reportes (UI-7) ---------- */

function reportMonths() {
  const now = new Date();
  const cy = now.getFullYear();
  const cm = now.getMonth() + 1;
  const out = [];
  const push = (y, m) => {
    if (y >= 2000 && y <= 2100 && m >= 1 && m <= 12) out.push({ year: y, month: m });
  };
  const r = state.reportRange || "12m";
  if (r === "year") {
    for (let m = 1; m <= 12; m++) push(state.reportYear || cy, m);
  } else if (r === "custom") {
    const from = state.reportFrom ? new Date(`${state.reportFrom}T00:00:00`) : null;
    const to = state.reportTo ? new Date(`${state.reportTo}T00:00:00`) : null;
    if (from && to && from <= to) {
      let y = from.getFullYear();
      let m = from.getMonth() + 1;
      const endY = to.getFullYear();
      const endM = to.getMonth() + 1;
      for (;;) {
        push(y, m);
        if (y === endY && m === endM) break;
        m += 1;
        if (m > 12) {
          m = 1;
          y += 1;
        }
      }
    }
  } else {
    const n = Math.min(36, Number(String(r).replace("m", "")) || 6);
    for (let i = n - 1; i >= 0; i--) {
      const d = new Date(cy, cm - 1 - i, 1);
      push(d.getFullYear(), d.getMonth() + 1);
    }
  }
  return out;
}

function reportPriorMonths(months) {
  const n = months.length;
  if (!n) return [];
  const first = months[0];
  const out = [];
  for (let i = n; i > 0; i--) {
    const d = new Date(first.year, first.month - 1 - i, 1);
    out.push({ year: d.getFullYear(), month: d.getMonth() + 1 });
  }
  return out;
}

function reportMonthKey(y, m) {
  return `${y}-${String(m).padStart(2, "0")}`;
}

function reportTxnMonthKey(t) {
  return String(t.date || t.payment_date || "").slice(0, 7);
}

function reportMonthlyTotals(txns, months) {
  const idx = new Map(months.map((m, i) => [reportMonthKey(m.year, m.month), i]));
  const rows = Array.from({ length: months.length }, () => ({ income: 0, expenses: 0, transfers: 0, count: 0 }));
  for (const t of txns || []) {
    const i = idx.get(reportTxnMonthKey(t));
    if (i === undefined) continue;
    const amt = Number(t.amount) || 0;
    if (t.type === "income") rows[i].income += amt;
    else if (t.type === "expense") rows[i].expenses += amt;
    else rows[i].transfers += amt;
    rows[i].count += 1;
  }
  return rows;
}

function reportCatTotals(txns, months, kind) {
  const set = new Set(months.map((m) => reportMonthKey(m.year, m.month)));
  const cat = {};
  for (const t of txns || []) {
    if (t.type !== kind || !set.has(reportTxnMonthKey(t))) continue;
    const name = (state.categories.find((c) => c.id === t.category_id) || {}).name || "Sin categoría";
    cat[name] = (cat[name] || 0) + (Number(t.amount) || 0);
  }
  return Object.entries(cat).sort((a, b) => b[1] - a[1]);
}

function reportLabels(months) {
  const short = "Ene Feb Mar Abr May Jun Jul Ago Sep Oct Nov Dic".split(" ");
  return months.map((m) => `${short[m.month - 1]} ${String(m.year).slice(2)}`);
}

function reportWindowLabel(months) {
  if (!months.length) return "sin periodo";
  const a = months[0];
  const b = months[months.length - 1];
  const short = "Ene Feb Mar Abr May Jun Jul Ago Sep Oct Nov Dic".split(" ");
  return a.year === b.year && a.month === b.month
    ? `${short[a.month - 1]} ${a.year}`
    : `${short[a.month - 1]} ${a.year} – ${short[b.month - 1]} ${b.year}`;
}

function reportBestWorst(rows, key) {
  let best = null;
  let worst = null;
  rows.forEach((r, i) => {
    if (best == null || r[key] > best.value) best = { value: r[key], i };
    if (worst == null || r[key] < worst.value) worst = { value: r[key], i };
  });
  return { best, worst };
}

function reportMonthDiff(prevValue, currentValue) {
  const delta = pctDelta(currentValue, prevValue);
  return delta == null ? null : -delta;
}

async function reportDebtData(debts, months) {
  const payments = {};
  for (const d of debts || []) {
    try {
      payments[d.id] = (await api(`/api/v1/debts/${d.id}/payments`)) || [];
    } catch {
      payments[d.id] = [];
    }
  }
  const balances = months.map(() => 0);
  const paid = months.map(() => 0);
  for (const d of debts || []) {
    const created = d.created_at ? reportTxnMonthKey(d.created_at) : null;
    const original = Math.max(0, Number(d.original_amount) || 0);
    const ps = (payments[d.id] || []).sort((a, b) => String(a.payment_date).localeCompare(String(b.payment_date)));
    let cum = 0;
    for (let i = 0; i < months.length; i++) {
      const m = months[i];
      const key = reportMonthKey(m.year, m.month);
      if (created && key < created) continue;
      balances[i] += Math.max(0, original - cum);
      const sum = ps.filter((p) => reportTxnMonthKey(p) === key).reduce((a, p) => a + (Number(p.amount) || 0), 0);
      if (sum > 0) {
        paid[i] += sum;
        cum += sum;
      }
    }
  }
  if (months.length && debts.length) {
    balances[balances.length - 1] = debts.reduce((a, d) => a + (Number(d.current_balance) || 0), 0);
  }
  return { balances, paid };
}

async function renderReports(mainEl) {
  state.reportTab = state.reportTab || "resumen";
  const months = reportMonths();
  const prior = reportPriorMonths(months);
  const labels = reportLabels(months);
  const rangeOptions = [["3m", "3 meses"], ["6m", "6 meses"], ["12m", "12 meses"], ["year", "Año"], ["custom", "Personalizado"]];
  const tabs = [
    ["resumen", "Resumen"],
    ["ingresos", "Ingresos"],
    ["gastos", "Gastos"],
    ["patrimonio", "Patrimonio"],
    ["deudas", "Deudas"],
  ];
  const yearSelect = state.reportRange === "year"
    ? `<select id="report-year" class="rounded-md border border-slate-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-amber" aria-label="Año del reporte">${yearOptions().map((y) => `<option value="${y}" ${y === String(state.reportYear || new Date().getFullYear()) ? "selected" : ""}>${y}</option>`).join("")}</select>`
    : "";
  const customInputs = state.reportRange === "custom"
    ? `<input id="report-from" type="date" value="${esc(state.reportFrom)}" aria-label="Desde" class="rounded-md border border-slate-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-amber" /> <span class="text-xs text-slate-400">a</span> <input id="report-to" type="date" value="${esc(state.reportTo)}" aria-label="Hasta" class="rounded-md border border-slate-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-amber" />`
    : "";
  mainEl.innerHTML = `
  ${pageHeader("Reportes", `Cómo has evolucionado: ingresos, gastos, patrimonio y deuda.`, "")}
  <div class="cf-card mb-6">
    <div class="flex flex-wrap items-center gap-2">
      <span class="text-xs font-semibold text-slate-500 uppercase tracking-wide mr-1">Periodo</span>
      ${rangeOptions.map(([val, text]) => `<button data-range="${val}" class="px-3 py-1.5 rounded-full text-xs font-semibold ${state.reportRange === val ? "bg-brand-navy text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}">${text}</button>`).join("")}
      ${yearSelect}
      ${customInputs}
      <span class="text-xs text-slate-400 ml-auto">${esc(reportWindowLabel(months))}</span>
    </div>
    <div class="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
      ${tabs.map(([val, text]) => `<button data-tab="${val}" class="px-4 py-2 rounded-lg text-sm font-semibold ${state.reportTab === val ? "bg-brand-amber text-brand-navy" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}">${text}</button>`).join("")}
    </div>
  </div>
  <div id="reports-body"><div class="skeleton h-48"></div></div>`;
  mainEl.querySelectorAll("[data-range]").forEach((b) => {
    b.addEventListener("click", () => {
      state.reportRange = b.dataset.range;
      if (state.reportRange === "custom" && !state.reportFrom) {
        const now = new Date();
        const d = new Date(now.getFullYear(), now.getMonth() - 5, 1);
        state.reportFrom = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
        state.reportTo = todayISO();
      }
      if (state.reportRange !== "year") state.reportYear = null;
      renderReports(mainEl);
    });
  });
  mainEl.querySelectorAll("[data-tab]").forEach((b) => {
    b.addEventListener("click", () => {
      state.reportTab = b.dataset.tab;
      renderReports(mainEl);
    });
  });
  const yearSel = document.getElementById("report-year");
  if (yearSel) yearSel.addEventListener("change", () => { state.reportYear = Number(yearSel.value) || new Date().getFullYear(); renderReports(mainEl); });
  const fromEl = document.getElementById("report-from");
  const toEl = document.getElementById("report-to");
  if (fromEl) fromEl.addEventListener("change", () => { state.reportFrom = fromEl.value; renderReports(mainEl); });
  if (toEl) toEl.addEventListener("change", () => { state.reportTo = toEl.value; renderReports(mainEl); });
  if (!months.length) {
    document.getElementById("reports-body").innerHTML = emptyState("Selecciona un periodo válido para ver el reporte.");
    return;
  }

  let txns = [];
  try {
    txns = await loadHouseholdTxns();
  } catch {
    return;
  }
  const bodyEl = document.getElementById("reports-body");
  const rows = reportMonthlyTotals(txns, months);
  const priorRows = reportMonthlyTotals(txns, prior);
  const sum = (arr, k) => arr.reduce((a, r) => a + r[k], 0);
  const income = sum(rows, "income");
  const expenses = sum(rows, "expenses");
  const flow = rows.map((r) => r.income - r.expenses);
  let acc = 0;
  const cumulative = flow.map((v) => (acc = acc + v));
  const prevIncome = sum(priorRows, "income");
  const prevExpenses = sum(priorRows, "expenses");
  const capGasto = reportCatTotals(txns, months, "expense");
  const capIngreso = reportCatTotals(txns, months, "income");
  const gpTotal = expenses || 1;

  let debts = [];
  let debtSeries = null;
  try {
    debts = await api(`/api/v1/households/${state.householdId}/debts`);
  } catch {
    debts = [];
  }
  if (state.reportTab === "patrimonio" || state.reportTab === "deudas") {
    try {
      debtSeries = await reportDebtData(debts, months);
    } catch {
      debtSeries = null;
    }
  }
  const activeDebts = (debts || []).filter((d) => d.status === "active");
  const totalDebt = activeDebts.reduce((a, d) => a + (Number(d.current_balance) || 0), 0);
  const activeAccounts = (state.accounts || []).filter((a) => a.status === "active");
  const totalAssets = activeAccounts.reduce((a, c) => a + (Number(c.balance_calculated) || 0), 0);

  const TABS = {
    resumen: () => `
      <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        ${kpiCard({ label: "Ingresos del periodo", value: money(income), delta: pctDelta(income, prevIncome), icon: "M12 3v18M17 7l-5-4-5 4M5 17h14M8 21h8", color: "#19b5a5", spark: sparkline(rows.map((r) => r.income), { color: "#19b5a5" }), footer: esc(reportWindowLabel(months)) })}
        ${kpiCard({ label: "Gastos del periodo", value: money(expenses), delta: reportMonthDiff(prevExpenses, expenses), invert: true, icon: "M12 3v18M17 17l-5 4-5-4M5 7h14M8 3h8", color: "#e15554", spark: sparkline(rows.map((r) => r.expenses), { color: "#e15554" }), footer: esc(reportWindowLabel(months)) })}
        ${kpiCard({ label: "Flujo neto", value: money(income - expenses), icon: "M4 15l4-4 4 4 4-4M4 19h16M4 9V5h16v4", color: income - expenses >= 0 ? "#19b5a5" : "#e15554", spark: sparkline(flow, { color: income - expenses >= 0 ? "#19b5a5" : "#e15554" }), footer: "ingresos − gastos" })}
        ${kpiCard({ label: "Ahorro acumulado", value: money(cumulative[cumulative.length - 1] || 0), icon: "M12 8c-2.5 0-4 1.5-4 3.5S9.5 15 12 15s4-1.5 4-3.5S14.5 8 12 8zm0 0V5m-6 5a8 8 0 1012 0", color: "#123b4a", spark: sparkline(cumulative, { color: "#123b4a" }), footer: "flujo mes a mes acumulado" })}
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div class="cf-card"><h2 class="font-bold mb-4">Ingresos vs gastos por mes</h2><div class="flex items-end gap-2 h-40">${barComparison(flow, labels.map((l) => l.split(" ")[0]))}</div></div>
        <div class="cf-card"><h2 class="font-bold mb-4">Flujo acumulado</h2>${areaChart(cumulative, { labels: months.map((m) => reportWindowLabel([m])), w: 520, h: 160, color: "#123b4a", yFmt: moneyCompact })}</div>
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="cf-card"><h2 class="font-bold mb-4">Gastos por categoría</h2>
          ${capGasto.length ? `<div class="flex flex-col sm:flex-row items-center gap-4"><div class="donut-wrap">${donutSvg(capGasto.map(([name, amount]) => ({ name, value: amount, color: colorForId(name) })), { size: 180, thickness: 26, centerLabel: "gastos", centerValue: moneyCompact(expenses) })}</div><div class="flex-1 min-w-0 space-y-1.5 w-full">${capGasto.slice(0, 6).map(([name, amount]) => `<div class="flex justify-between text-sm gap-2"><span class="truncate font-medium">${esc(name)}</span><span class="font-semibold shrink-0">${Math.round((amount / gpTotal) * 100)}% · ${moneyCompact(amount)}</span></div>`).join("")}${capGasto.length > 6 ? `<div class="text-xs text-slate-400">+ ${capGasto.length - 6} categoría(s) · ver en Gastos</div>` : ""}</div></div>` : emptyCompact("Sin gastos en el periodo.", `<button data-tab="gastos" class="mt-3 px-4 py-2 rounded-lg bg-brand-navy text-white text-sm font-semibold">Ver Gastos</button>`)}
        </div>
        <div class="cf-card"><h2 class="font-bold mb-3">Mayor gasto por categoría</h2>
          ${capGasto.length ? `<div class="space-y-3">${capGasto.slice(0, 5).map(([name, amount], i) => `<div><div class="flex justify-between text-sm mb-1"><span class="truncate font-medium">${esc(name)}</span><span class="font-semibold">${money(amount)} · ${Math.round((amount / capGasto[0][1]) * 100)}%</span></div>${progressBar(amount, capGasto[0][1])}</div>`).join("")}</div><button data-tab="gastos" class="mt-3 text-xs font-semibold text-brand-amber-dark hover:underline">Ver detalle de gastos →</button>` : "<p class='text-sm text-slate-400'>Sin gastos registrados en el periodo.</p>"}
        </div>
      </div>`,
    ingresos: () => {
      const best = reportBestWorst(rows, "income").best;
      return `
        <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
          ${kpiCard({ label: "Ingresos del periodo", value: money(income), delta: pctDelta(income, prevIncome), icon: "M12 3v18M17 7l-5-4-5 4M5 17h14M8 21h8", color: "#19b5a5", spark: sparkline(rows.map((r) => r.income), { color: "#19b5a5" }), footer: esc(reportWindowLabel(months)) })}
          ${kpiCard({ label: "Promedio mensual", value: money(months.length ? Math.round(income / months.length) : 0), icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6M9 19h10m-2-2v-4a2 2 0 00-2-2h-2m-4 8v-8", color: "#38bdf8", footer: `${months.length} mes(es) analizados` })}
          ${kpiCard({ label: "Mejor mes", value: money(best ? best.value : 0), icon: "M12 6v6l4 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "#f4b942", footer: best ? esc(labels[best.i]) : "-" })}
          ${kpiCard({ label: "Meses con ingreso", value: `${rows.filter((r) => r.income > 0).length} de ${rows.length || 0}`, icon: "M9 12l2 2 4-4M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "#123b4a" })}
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div class="cf-card"><h2 class="font-bold mb-4">Evolución de ingresos</h2>${income > 0 ? areaChart(rows.map((r) => r.income), { labels: months.map((m) => reportWindowLabel([m])), w: 540, h: 170, color: "#19b5a5", yFmt: moneyCompact }) : emptyCompact("Aún no hay ingresos registrados en el periodo.")}</div>
          <div class="cf-card"><h2 class="font-bold mb-4">Ingresos por categoría</h2>
            ${capIngreso.length ? `<div class="flex flex-col sm:flex-row items-center gap-4"><div class="donut-wrap">${donutSvg(capIngreso.map(([name, amount]) => ({ name, value: amount, color: colorForId(name) })), { size: 180, thickness: 26, centerLabel: "ingresos", centerValue: moneyCompact(income) })}</div><div class="flex-1 min-w-0 space-y-1.5 w-full">${capIngreso.slice(0, 6).map(([name, amount]) => `<div class="flex justify-between text-sm gap-2"><span class="truncate font-medium">${esc(name)}</span><span class="font-semibold shrink-0">${Math.round((amount / (income || 1)) * 100)}% · ${moneyCompact(amount)}</span></div>`).join("")}</div></div>` : emptyCompact("Sin ingresos por categoría en el periodo.")}
          </div>
        </div>`;
    },
    gastos: () => {
      const best = reportBestWorst(rows, "expenses").best;
      const cur = months[months.length - 1];
      const prev = months[months.length - 2];
      const curKey = cur ? reportMonthKey(cur.year, cur.month) : "";
      const prevKey = prev ? reportMonthKey(prev.year, prev.month) : "";
      const catLast = capGasto.slice(0, 5);
      const maxCat = catLast.reduce((a, [, amount]) => Math.max(a, amount), 1);
      const lastVsPrev = catLast.map(([name]) => {
        let cc = 0;
        let pp = 0;
        for (const t of txns || []) {
          if (t.type !== "expense") continue;
          const cat = (state.categories.find((c) => c.id === t.category_id) || {}).name || "Sin categoría";
          if (cat !== name) continue;
          const k = reportTxnMonthKey(t);
          if (k === curKey) cc += Number(t.amount) || 0;
          if (k === prevKey) pp += Number(t.amount) || 0;
        }
        return { name, cur: cc, prev: pp };
      });
      return `
        <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
          ${kpiCard({ label: "Gastos del periodo", value: money(expenses), delta: reportMonthDiff(prevExpenses, expenses), invert: true, icon: "M12 3v18M17 17l-5 4-5-4M5 7h14M8 3h8", color: "#e15554", spark: sparkline(rows.map((r) => r.expenses), { color: "#e15554" }), footer: esc(reportWindowLabel(months)) })}
          ${kpiCard({ label: "Promedio diario", value: money(months.length ? Math.round(expenses / (months.length * 30)) : 0), icon: "M12 6v6l4 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "#38bdf8" })}
          ${kpiCard({ label: "Transacciones", value: String(rows.reduce((a, r) => a + r.count, 0)), icon: "M4 7h16M4 12h16M4 17h16", color: "#123b4a" })}
          ${kpiCard({ label: "Mayor gasto", value: money(best ? best.value : 0), icon: "M12 3v18M17 17l-5 4-5-4M5 7h14M8 3h8", color: "#e15554", footer: best ? esc(labels[best.i]) : "-" })}
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div class="cf-card"><h2 class="font-bold mb-4">Evolución del gasto</h2>${expenses > 0 ? areaChart(rows.map((r) => r.expenses), { labels: months.map((m) => reportWindowLabel([m])), w: 540, h: 170, color: "#e15554", yFmt: moneyCompact }) : emptyCompact("Aún no hay gastos registrados en el periodo.")}</div>
          <div class="cf-card"><h2 class="font-bold mb-4">Gastos por categoría</h2>
            ${capGasto.length ? `<div class="flex flex-col sm:flex-row items-center gap-4"><div class="donut-wrap">${donutSvg(capGasto.map(([name, amount]) => ({ name, value: amount, color: colorForId(name) })), { size: 180, thickness: 26, centerLabel: "gastos", centerValue: moneyCompact(expenses) })}</div><div class="flex-1 min-w-0 space-y-1.5 w-full">${capGasto.slice(0, 8).map(([name, amount]) => `<div class="flex justify-between text-sm gap-2"><span class="truncate font-medium">${esc(name)}</span><span class="font-semibold shrink-0">${Math.round((amount / gpTotal) * 100)}% · ${moneyCompact(amount)}</span></div>`).join("")}</div></div>` : emptyCompact("Sin gastos registrados en el periodo.")}
          </div>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div class="cf-card"><h2 class="font-bold mb-4">Último mes vs anterior por categoría</h2>
            ${lastVsPrev.length ? `<div class="space-y-3">${lastVsPrev.map((c) => `<div><div class="flex justify-between text-sm mb-1"><span class="truncate font-medium">${esc(c.name)}</span><span class="font-semibold">${money(c.cur)}${c.prev > c.cur ? " ↓" : c.prev < c.cur ? " ↑" : ""}</span></div>${progressBar(c.cur, Math.max(1, maxCat))}<div class="text-[11px] text-slate-400 mt-0.5">mes anterior: ${money(c.prev)}</div></div>`).join("")}</div>` : "<p class='text-sm text-slate-400'>Sin datos para comparar los últimos dos meses.</p>"}
          </div>
          <div class="cf-card"><h2 class="font-bold mb-3">Distribución por categoría</h2>
            <table class="cf-table w-full"><thead><tr><th>Categoría</th><th class="text-right">Monto</th><th class="text-right hidden md:table-cell">%</th><th class="w-2/5">Participación</th></tr></thead>
            <tbody>${capGasto.length ? capGasto.map(([name, amount]) => `<tr><td>${esc(name)}</td><td class="text-right font-semibold">${money(amount)}</td><td class="text-right text-slate-500 hidden md:table-cell">${Math.round((amount / gpTotal) * 100)}%</td><td>${progressBar(amount, gpTotal)}</td></tr>`).join("") : `<tr><td colspan="4" class="text-center text-slate-400 py-6">Sin gastos en el periodo</td></tr>`}</tbody></table>
          </div>
        </div>`;
    },
    patrimonio: () => `
      <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
        ${kpiCard({ label: "Patrimonio neto", value: money(totalAssets - totalDebt), icon: "M12 8c-2.5 0-4 1.5-4 3.5S9.5 15 12 15s4-1.5 4-3.5S14.5 8 12 8zm0 0V5m-6 5a8 8 0 1012 0", color: totalAssets - totalDebt >= 0 ? "#19b5a5" : "#e15554", footer: "activos − deuda" })}
        ${kpiCard({ label: "Activos", value: money(totalAssets), icon: "M4 6h16v12H4zM4 10h16M8 3h8", color: "#123b4a", footer: `${activeAccounts.length} cuenta(s) activa(s)` })}
        ${kpiCard({ label: "Deuda total", value: money(totalDebt), icon: "M3 10h18M8 21V10M16 21V10M5 21h14M5 7l2-3h10l2 3z", color: "#e15554", footer: `${activeDebts.length} deuda(s) activa(s)` })}
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div class="cf-card"><h2 class="font-bold mb-4">Evolución de la deuda</h2>
          ${debtSeries && debtSeries.balances.some((v) => v > 0) ? areaChart(debtSeries.balances, { labels: months.map((m) => reportWindowLabel([m])), w: 540, h: 170, color: "#e15554", yFmt: moneyCompact }) : emptyCompact("Aún no tenemos historial suficiente para mostrar la tendencia de deuda.")}
          <p class="text-xs text-slate-400 mt-2">Deuda estimada mes a mes desde el saldo original menos los pagos registrados (reconstrucción; el último punto usa el saldo actual real).</p>
        </div>
        <div class="cf-card"><h2 class="font-bold mb-4">Composición de activos</h2>
          ${activeAccounts.length ? `<div class="flex flex-col sm:flex-row items-center gap-4"><div class="donut-wrap">${donutSvg(activeAccounts.map((a) => ({ name: a.name, value: Math.max(0, Number(a.balance_calculated) || 0), color: colorForId(a.name) })), { size: 180, thickness: 26, centerLabel: "activos", centerValue: moneyCompact(totalAssets) })}</div><div class="flex-1 min-w-0 space-y-1.5 w-full">${activeAccounts.slice(0, 6).map((a) => `<div class="flex justify-between text-sm gap-2"><span class="truncate font-medium">${esc(a.name)}</span><span class="font-semibold shrink-0">${moneyCompact(Number(a.balance_calculated) || 0)}</span></div>`).join("")}</div></div>` : emptyCompact("No tienes cuentas activas registradas.")}
        </div>
      </div>
      <div class="cf-card"><h2 class="font-bold mb-3">Resumen de cuentas</h2>
        <table class="cf-table w-full"><thead><tr><th>Cuenta</th><th class="text-right">Saldo</th><th class="hidden md:table-cell">Estado</th></tr></thead>
        <tbody>${activeAccounts.length ? activeAccounts.map((a) => `<tr><td>${esc(a.name)}</td><td class="text-right font-semibold">${money(Number(a.balance_calculated) || 0)}</td><td class="hidden md:table-cell"><span class="state-badge bien">activa</span></td></tr>`).join("") : `<tr><td colspan="3" class="text-center text-slate-400 py-6">Sin cuentas</td></tr>`}</tbody></table>
      </div>`,
    deudas: () => {
      const paidTotal = debtSeries ? debtSeries.paid.reduce((a, v) => a + v, 0) : 0;
      const paidAvg = debtSeries && months.length ? Math.round(paidTotal / months.length) : 0;
      let zeroDate = null;
      let zeroMonths = null;
      if (paidAvg > 0 && totalDebt > 0) {
        zeroMonths = Math.ceil(totalDebt / paidAvg);
        const d = new Date();
        const target = new Date(d.getFullYear(), d.getMonth() + zeroMonths, 1);
        zeroDate = `${target.getFullYear()}-${String(target.getMonth() + 1).padStart(2, "0")}`;
      }
      return `
        <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
          ${kpiCard({ label: "Deuda activa", value: money(totalDebt), icon: "M3 10h18M8 21V10M16 21V10M5 21h14M5 7l2-3h10l2 3z", color: "#e15554", footer: `${activeDebts.length} deuda(s)` })}
          ${kpiCard({ label: "Pagado en el periodo", value: money(paidTotal), icon: "M9 12l2 2 4-4M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "#19b5a5", spark: debtSeries && debtSeries.paid.some((v) => v > 0) ? sparkline(debtSeries.paid, { color: "#19b5a5" }) : null, footer: esc(reportWindowLabel(months)) })}
          ${kpiCard({ label: "Promedio de pago mensual", value: money(paidAvg), icon: "M12 6v6l4 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z", color: "#38bdf8", footer: "de los pagos registrados" })}
          ${kpiCard({ label: "Deuda cero estimada", value: zeroDate ? `${months.length ? reportWindowLabel([{ year: Number(zeroDate.slice(0, 4)), month: Number(zeroDate.slice(5, 7)) }]) : zeroDate}` : "—", icon: "M22 11.1V12a10 10 0 11-5.9-9.1M22 4L12 14l-3-3", color: "#123b4a", footer: zeroMonths ? `≈ ${zeroMonths} mes(es) al ritmo actual` : "sin pagos suficientes en el periodo" })}
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div class="cf-card"><h2 class="font-bold mb-4">Evolución de la deuda</h2>${debtSeries && debtSeries.balances.some((v) => v > 0) ? areaChart(debtSeries.balances, { labels: months.map((m) => reportWindowLabel([m])), w: 540, h: 170, color: "#e15554", yFmt: moneyCompact }) : emptyCompact("Sin deudas o sin historial de pagos en el periodo.")}</div>
          <div class="cf-card"><h2 class="font-bold mb-4">Pagos de deuda por mes</h2>${debtSeries && debtSeries.paid.some((v) => v > 0) ? `<div class="flex items-end gap-2 h-40">${barComparison(debtSeries.paid, labels.map((l) => l.split(" ")[0]))}</div>` : emptyCompact("Sin pagos de deuda registrados en el periodo.")}</div>
        </div>
        <div class="cf-card"><h2 class="font-bold mb-3">Deudas</h2>
          <table class="cf-table w-full"><thead><tr><th>Deuda</th><th class="text-right">Original</th><th class="text-right">Actual</th><th class="text-right hidden md:table-cell">Pagado</th><th class="w-2/5">Avance</th></tr></thead>
          <tbody>${debts.length ? activeDebts.length ? activeDebts.map((d) => { const paid = Math.max(0, (Number(d.original_amount) || 0) - (Number(d.current_balance) || 0)); const pct = (Number(d.original_amount) || 0) > 0 ? Math.round(Math.min(100, (paid / d.original_amount) * 100)) : (Number(d.current_balance) || 0) > 0 ? 0 : 100; return `<tr><td>${esc(d.name)}</td><td class="text-right text-slate-500">${money(d.original_amount)}</td><td class="text-right font-semibold">${money(d.current_balance)}</td><td class="text-right text-slate-500 hidden md:table-cell">${money(paid)} · ${pct}%</td><td>${progressBar(paid, Math.max(1, Number(d.original_amount) || 0))}</td></tr>`; }).join("") : `<tr><td colspan="5" class="text-center text-slate-400 py-6">No hay deudas activas</td></tr>` : `<tr><td colspan="5" class="text-center text-slate-400 py-6">No tienes deudas registradas</td></tr>`}</tbody></table>
        </div>`;
    },
  };
  bodyEl.innerHTML = (TABS[state.reportTab] || TABS.resumen)();
  bodyEl.querySelectorAll("[data-tab]").forEach((b) => {
    b.addEventListener("click", () => {
      state.reportTab = b.dataset.tab;
      renderReports(mainEl);
    });
  });
}

/* ---------- Bootstrap ---------- */

window.addEventListener("hashchange", route);
window.openModal = openModal;
window.closeModal = closeModal;
window.toggleSidebar = toggleSidebar;
window.createAccount = createAccount;
window.setEgresosTab = setEgresosTab;
window.setDebtsTab = setDebtsTab;
window.createGoal = createGoal;
window.archiveGoal = archiveGoal;
window.deleteInstitution = deleteInstitution;
window.saveTxn = saveTxn;
window.openTxnNew = openTxnNew;
window.openTxnEdit = openTxnEdit;
window.voidTxn = voidTxn;
window.createDebt = createDebt;
window.createBudget = createBudget;
window.assignBudgetRow = assignBudgetRow;
window.openBudgetAlloc = openBudgetAlloc;
window.simulate = simulate;
window.createPlan = createPlan;
window.selectPlan = selectPlan;
window.runScenario = runScenario;
window.createMember = createMember;
window.createCategory = createCategory;
window.createSource = createSource;
window.openBatch = openBatch;
window.goReview = goReview;
  window.confirmBatch = confirmBatch;
  window.resolveReview = resolveReview;
  window.openReviewEdit = openReviewEdit;
  window.onReviewCorrectSubmit = onReviewCorrectSubmit;
  window.processCapture = processCapture;
  window.openCaptureConfirm = openCaptureConfirm;
  window.confirmCapture = confirmCapture;
  window.openCaptureEdit = openCaptureEdit;
  window.onCaptureEdit = onCaptureEdit;
  window.discardCapture = discardCapture;
  window.runNotifications = runNotifications;
  window.toggleNotification = toggleNotification;
window.aiAnalyze = aiAnalyze;
window.aiReloadProposals = aiReloadProposals;
window.aiResolve = aiResolve;
window.aiSuggest = aiSuggest;
window.suggestTxnCategory = suggestTxnCategory;

async function init() {
  await ensureReady();
  route();
}

init();