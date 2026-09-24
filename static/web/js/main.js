'use strict';

import {
  api,
  invalidate,
  listProjects,
  listTasks,
  listMeetings,
  listWorkspaces,
  nameMaps,
} from './api.js';
import { esc, icon, toast } from './ui.js';
import {
  renderProyectos,
  renderProyectoDetalle,
  renderTareas,
  renderCalendario,
  renderReuniones,
  renderReunionDetalle,
  renderAsistente,
  renderIntegraciones,
} from './views.js';
import { renderMiDia, renderPreparar, renderCierre } from './views-mi-dia.js';
import { renderFinanzas } from './views-finanzas.js';
import { renderHabitos, renderHabitoDetalle, renderSemana } from './views-habitos.js';
import { renderBandeja, renderChat } from './views-bandeja.js';
import { renderConfiguracion } from './views-configuracion.js';
import { suggestCapture, KIND_LABELS } from './capture-triage.js';

const ROUTES = {
  '/mi-dia': { title: 'Mi Día', area: 'mi-dia', render: renderMiDia },
  '/mi-dia/preparar': { title: 'Preparar mi día', area: 'mi-dia', render: renderPreparar },
  '/mi-dia/cierre': { title: 'Cierre del día', area: 'mi-dia', render: renderCierre },
  '/proyectos': { title: 'Proyectos', area: 'trabajo', render: renderProyectos, detail: renderProyectoDetalle },
  '/tareas': { title: 'Tareas', area: 'trabajo', render: renderTareas },
  '/calendario': { title: 'Calendario', area: 'trabajo', render: renderCalendario },
  '/reuniones': { title: 'Reuniones', area: 'trabajo', render: renderReuniones, detail: renderReunionDetalle },
  '/asistente': { title: 'Asistente', area: 'trabajo', render: renderAsistente },
  '/integraciones': { title: 'Integraciones', area: 'trabajo', render: renderIntegraciones },
  '/finanzas': { title: 'Finanzas', area: 'finanzas', render: renderFinanzas },
  '/habitos': { title: 'Hábitos', area: 'habitos', render: renderHabitos },
  '/bandeja': { title: 'Bandeja', area: 'bandeja', render: renderBandeja },
  '/chat': { title: 'Chat Bandeja', area: 'bandeja', render: renderChat },
  '/configuracion': { title: 'Configuración', area: 'configuracion', render: renderConfiguracion },
};

const ALIASES = {
  '/': '/mi-dia',
  '/inicio': '/mi-dia',
  '/inbox': '/bandeja',
  '/config': '/configuracion',
};

const WORK_ROUTES = [
  '/proyectos',
  '/tareas',
  '/calendario',
  '/reuniones',
  '/asistente',
  '/integraciones',
];

// Menú lateral contextual por área.
const AREA_NAV = {
  'mi-dia': [
    {
      group: 'Hoy',
      items: [
        { label: 'Resumen del día', icon: 'check', href: '#/mi-dia' },
        { label: 'Preparar mi día', icon: 'sparkles', href: '#/mi-dia/preparar' },
        { label: 'Cierre del día', icon: 'moon', href: '#/mi-dia/cierre' },
      ],
    },
    {
      group: 'Atajos',
      items: [
        { label: 'Hábitos de hoy', icon: 'target', href: '#/habitos' },
        { label: 'Bandeja pendiente', icon: 'send', href: '#/bandeja' },
      ],
    },
  ],
  trabajo: [
    {
      group: 'Trabajo',
      items: [
        { label: 'Proyectos', icon: 'folder', href: '#/proyectos' },
        { label: 'Tareas', icon: 'check', href: '#/tareas' },
        { label: 'Calendario', icon: 'calendar', href: '#/calendario' },
        { label: 'Reuniones', icon: 'clock', href: '#/reuniones' },
        { label: 'Asistente', icon: 'sparkles', href: '#/asistente' },
        { label: 'Integraciones', icon: 'link', href: '#/integraciones' },
      ],
    },
  ],
  finanzas: [
    {
      group: 'Finanzas',
      items: [
        { label: 'Resumen', icon: 'sparkles', href: '#/finanzas' },
        { label: 'Ingresos', icon: 'arrow', href: '#/finanzas/ingresos' },
        { label: 'Egresos', icon: 'flag', href: '#/finanzas/egresos' },
        { label: 'Cuentas', icon: 'folder', href: '#/finanzas/cuentas' },
        { label: 'Tarjetas y deudas', icon: 'alert', href: '#/finanzas/deudas' },
        { label: 'Presupuesto', icon: 'target', href: '#/finanzas/presupuesto' },
        { label: 'Metas de ahorro', icon: 'check', href: '#/finanzas/metas' },
      ],
    },
  ],
  habitos: [
    {
      group: 'Hábitos',
      items: [
        { label: 'Todos los hábitos', icon: 'target', href: '#/habitos' },
        { label: 'Vista semanal', icon: 'calendar', href: '#/habitos/semana' },
      ],
    },
  ],
  bandeja: [
    {
      group: 'Bandeja',
      items: [
        { label: 'Pendientes', icon: 'send', href: '#/bandeja', exact: true },
        { label: 'En revisión', icon: 'clock', href: '#/bandeja?status=reviewing', match: ['received', 'reviewing'] },
        { label: 'Aplicadas', icon: 'check', href: '#/bandeja?status=applied', exact: true },
        { label: 'Descartadas', icon: 'trash', href: '#/bandeja?status=discarded', exact: true },
        { label: 'Capturar por chat', icon: 'sparkles', href: '#/chat' },
      ],
    },
  ],
};

const $ = (id) => document.getElementById(id);

function parseRoute() {
  let raw = window.location.hash || '#/mi-dia';
  let path = raw.slice(1).split('?')[0] || '/mi-dia';
  if (ALIASES[path]) {
    const target = ALIASES[path];
    const query = window.location.hash.split('?')[1] || '';
    window.history.replaceState(null, '', `#${target}${query ? `?${query}` : ''}`);
    path = target;
  }

  let match = path.match(/^\/([a-z-]+)\/([a-z0-9_]+)$/);
  if (match) {
    const base = `/${match[1]}`;
    if (ROUTES[base] && ROUTES[base].detail) {
      return { path: base, id: match[2], area: ROUTES[base].area };
    }
    if (base === '/finanzas' && /^[a-z]+$/.test(match[2])) {
      return { path: '/finanzas', sub: match[2], area: 'finanzas' };
    }
    if (base === '/habitos' && match[2] === 'semana') {
      return { path: '/habitos', sub: 'semana', area: 'habitos' };
    }
    if (base === '/habitos') {
      return { path: '/habitos', id: match[2], area: 'habitos' };
    }
  }

  if (ROUTES[path]) return { path, area: ROUTES[path].area };
  if (WORK_ROUTES.some((r) => path.startsWith(r))) {
    const base = WORK_ROUTES.find((r) => path.startsWith(r));
    return { path: base, area: 'trabajo' };
  }
  if (path.startsWith('/finanzas')) return { path: '/finanzas', area: 'finanzas' };
  if (path.startsWith('/habitos')) return { path: '/habitos', area: 'habitos' };
  if (path.startsWith('/bandeja')) return { path: '/bandeja', area: 'bandeja' };
  return { path: '/mi-dia', area: 'mi-dia' };
}

const queryFor = () => (window.location.hash.indexOf('?') >= 0 ? window.location.hash.split('?')[1] : '');

function setAreaActive(area) {
  document.querySelectorAll('.area-link').forEach((link) => {
    link.classList.toggle('active', link.dataset.area === area);
  });
  document.querySelectorAll('.mobile-item').forEach((item) => {
    item.classList.toggle('active', item.dataset.route === area);
  });
  if (area === 'configuracion') {
    document.querySelectorAll('.nav-link-foot, [data-route="configuracion"]').forEach((l) => l.classList.add('active'));
  } else {
    document.querySelectorAll('[data-route="configuracion"]').forEach((l) => l.classList.remove('active'));
  }
}

function buildSidebar(area) {
  const nav = $('areaside-nav');
  const groups = (AREA_NAV[area] || AREA_NAV['mi-dia']);
  const path = window.location.hash.split('?')[0] || '#/mi-dia';
  const query = queryFor();

  const itemActive = (item) => {
    if (item.exact) {
      return `${item.href}${item.match ? '' : ''}` === `${path}${query ? `?${query}` : ''}`;
    }
    if (item.match) {
      const status = params(query).status;
      return status ? item.match.includes(status) : path === item.href;
    }
    const base = item.href.split('?')[0];
    return path === base || path.startsWith(`${base}/`) || (item.href.includes('?') && path === item.href.split('?')[0] && item.href.split('?')[1] === query);
  };

  nav.innerHTML = groups
    .map(
      (group) => `
      <span class="nav-group-label">${esc(group.group)}</span>
      ${group.items
        .map(
          (item) => `
          <a class="nav-link ${itemActive(item) ? 'active' : ''}" href="${item.href}">
            ${icon(item.icon)}
            <span>${esc(item.label)}</span>
          </a>`,
        )
        .join('')}`,
    )
    .join('');
}

function params(qs) {
  return Object.fromEntries(new URLSearchParams(qs));
}

async function route() {
  const { path, id, sub } = parseRoute();
  const routeDef = ROUTES[path];
  const area = routeDef ? routeDef.area : 'mi-dia';
  setAreaActive(area);
  buildSidebar(area);

  const view = $('view');
  if (!view) return;
  window.scrollTo({ top: 0 });
  const fresh = document.createElement('div');
  fresh.id = 'view';
  fresh.className = 'view';
  fresh.tabIndex = -1;
  view.parentNode.replaceChild(fresh, view);

  const title = routeDef ? routeDef.title : 'Mi Día';
  document.title = `${title} · FaroFlow`;

  try {
    if (path === '/finanzas') {
      await renderFinanzas(fresh, sub || 'resumen');
    } else if (path === '/habitos' && sub === 'semana') {
      await renderSemana(fresh);
    } else if (path === '/habitos' && id) {
      await renderHabitoDetalle(fresh, id);
    } else if (id && routeDef && routeDef.detail) {
      await routeDef.detail(fresh, id);
    } else if (routeDef) {
      await routeDef.render(fresh);
    } else {
      await renderMiDia(fresh);
    }
  } catch (err) {
    fresh.innerHTML = `<div class="view"><div class="error">No se pudo cargar: ${esc(err.message)}</div></div>`;
  }
  closeSidebar();
}

function closeOverlay(id) {
  const overlay = $(id);
  if (overlay) overlay.hidden = true;
}

/* ---------- Captura global ---------- */
let captureKind = null;
let captureAmount = null;

function suggestRow(suggestion) {
  const host = $('capture-suggest');
  if (!host) return;
  if (!suggestion || suggestion.kind === 'unknown' && !suggestion.amount) {
    host.hidden = true;
    return;
  }
  const label = KIND_LABELS[suggestion.kind] || 'Por clasificar';
  const reasons = (suggestion.reasons || []).join(' ');
  const confidence = Math.round(suggestion.confidence * 100);
  host.hidden = false;
  host.innerHTML = `
    <div class="capture-suggest-chip">
      <span class="item-sub">Faro sugiere:</span>
      <span class="kind-chip kind-${esc(suggestion.kind)}">${esc(label)}</span>
      <span class="capture-suggest-conf">${confidence}%</span>
      ${suggestion.amount ? `<b>$${esc(Number(suggestion.amount).toLocaleString('es-CL'))}</b>` : ''}
      ${suggestion.due ? `<span class="item-sub">· vence ${esc(suggestion.due)}</span>` : ''}
      ${reasons ? `<span class="capture-suggest-reasons">${esc(reasons)}</span>` : ''}
      <button class="btn btn-soft btn-xs" id="capture-use-suggest" type="button">Usar</button>
    </div>`;
}

function renderCaptureSuggest() {
  const input = $('capture-text');
  const suggestion = suggestCapture(input.value);
  captureKind = null;
  captureAmount = null;
  suggestRow(suggestion);
  const use = $('capture-use-suggest');
  if (use) {
    use.addEventListener('click', () => {
      captureKind = suggestion.kind;
      captureAmount = suggestion.amount;
      use.disabled = true;
      use.textContent = 'Se usará';
    });
  }
}

function openCapture() {
  const overlay = $('capture-overlay');
  overlay.hidden = false;
  const input = $('capture-text');
  input.value = '';
  $('capture-char-hint').textContent = '0 / 5000';
  captureKind = null;
  captureAmount = null;
  renderCaptureSuggest();
  input.focus();
}

async function submitCapture() {
  const input = $('capture-text');
  const text = input.value.trim();
  if (!text) return;
  const submit = $('capture-submit');
  submit.disabled = true;
  const body = {
    channel: 'manual',
    author: 'yo',
    source_ref: `manual_${Date.now()}`,
    original_text: text,
  };
  if (captureKind && captureKind !== 'unknown') body.kind = captureKind;
  if (captureAmount && captureAmount > 0) body.amount = captureAmount;
  try {
    await api('/api/v1/bandeja', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    toast('Capturado. Está en la Bandeja para revisarlo.', 'success');
    closeOverlay('capture-overlay');
    refreshBandejaCount();
  } catch (err) {
    toast(`No se pudo capturar: ${err.message}`, 'error');
  } finally {
    submit.disabled = false;
  }
}

async function refreshBandejaCount() {
  try {
    const items = await api('/api/v1/bandeja?status=received');
    const badgeEl = $('bandeja-count');
    if (!badgeEl) return;
    const count = (items || []).length;
    if (count > 0) {
      badgeEl.hidden = false;
      badgeEl.textContent = count > 99 ? '99+' : count;
    } else {
      badgeEl.hidden = true;
    }
  } catch (_) {
    /* silencioso */
  }
}

/* ---------- Sidebar móvil ---------- */
function openSidebar() {
  $('areaside').classList.add('open');
  $('scrim').hidden = false;
  $('menu-btn').setAttribute('aria-expanded', 'true');
}

function closeSidebar() {
  $('areaside').classList.remove('open');
  $('scrim').hidden = true;
  $('menu-btn').setAttribute('aria-expanded', 'false');
}

/* ---------- Command palette (⌘K) ---------- */
let paletteIndex = 0;

function paletteRender(results) {
  const host = $('palette-results');
  if (!results.length) {
    host.innerHTML = '<div class="palette-empty">Sin resultados.</div>';
    paletteIndex = 0;
    return;
  }
  paletteIndex = 0;
  host.innerHTML = results
    .map(
      (item, i) => `
        <button class="palette-item ${i === 0 ? 'selected' : ''}" data-href="${esc(item.href)}" tabindex="-1">
          ${icon(item.icon)}
          <span><b>${esc(item.label)}</b></span>
          <span class="palette-kind">${esc(item.kind)}</span>
        </button>`,
    )
    .join('');
}

function paletteMove(delta) {
  const items = Array.from($('palette-results').querySelectorAll('.palette-item'));
  if (!items.length) return;
  paletteIndex = (paletteIndex + delta + items.length) % items.length;
  items.forEach((item, i) => item.classList.toggle('selected', i === paletteIndex));
  items[paletteIndex].scrollIntoView({ block: 'nearest' });
}

function paletteGo() {
  const items = Array.from($('palette-results').querySelectorAll('.palette-item'));
  const item = items[paletteIndex];
  if (!item) return;
  window.location.hash = item.dataset.href;
  closeOverlay('palette-overlay');
}

async function paletteSearch(query) {
  const host = $('palette-results');
  const q = query.trim().toLowerCase();
  if (!q) {
    host.innerHTML =
      '<div class="palette-empty">Busca proyectos, tareas o reuniones. Arrow ↑↓ para navegar, Enter para abrir.</div>';
    paletteIndex = 0;
    return;
  }
  try {
    const [projects, tasks, meetings] = await Promise.all([
      listProjects(),
      listTasks(),
      listMeetings(),
    ]);
    const results = [];
    for (const p of projects || []) {
      if (p.name.toLowerCase().includes(q)) {
        results.push({ kind: 'Proyecto', icon: 'folder', label: p.name, href: `#/proyectos/${p.id}` });
      }
    }
    for (const t of tasks || []) {
      if (!['done', 'cancelled'].includes(t.status) && t.title.toLowerCase().includes(q)) {
        results.push({ kind: 'Tarea', icon: 'check', label: t.title, href: t.project_id ? `#/proyectos/${t.project_id}?tab=tareas` : '#/tareas' });
      }
    }
    for (const m of meetings || []) {
      if (m.status === 'scheduled' && m.title.toLowerCase().includes(q)) {
        results.push({ kind: 'Reunión', icon: 'calendar', label: m.title, href: `#/reuniones/${m.id}` });
      }
    }
    results.sort((a, b) => a.kind.localeCompare(b.kind));
    paletteRender(results.slice(0, 8));
  } catch (_) {
    host.innerHTML = '<div class="palette-empty">No se pudo buscar.</div>';
    paletteIndex = 0;
  }
}

function openPalette() {
  paletteIndex = 0;
  $('palette-overlay').hidden = false;
  $('palette-input').value = '';
  $('palette-results').innerHTML =
    '<div class="palette-empty">Busca proyectos, tareas o reuniones. Arrow ↑↓ para navegar, Enter para abrir.</div>';
  window.setTimeout(() => $('palette-input').focus(), 30);
}

/* ---------- Workspace selector (no requerido en el nuevo shell, se mantiene API) ---------- */
async function setupWorkspaces() {
  try {
    await listWorkspaces();
  } catch (_) {
    /* silencioso */
  }
}

/* ---------- Boot ---------- */
function bind() {
  window.addEventListener('hashchange', () => {
    route();
    refreshBandejaCount();
  });

  $('capture-cta').addEventListener('click', (e) => { e.preventDefault(); openCapture(); });
  $('fab').addEventListener('click', (e) => { e.preventDefault(); openCapture(); });
  $('capture-cancel').addEventListener('click', () => closeOverlay('capture-overlay'));
  $('capture-close').addEventListener('click', () => closeOverlay('capture-overlay'));
  $('capture-submit').addEventListener('click', submitCapture);

  const captureInput = $('capture-text');
  captureInput.addEventListener('input', () => {
    $('capture-char-hint').textContent = `${captureInput.value.length} / 5000`;
    renderCaptureSuggest();
  });
  captureInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) submitCapture();
    if (event.key === 'Escape') closeOverlay('capture-overlay');
  });

  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-capture-open]')) {
      event.preventDefault();
      openCapture();
      return;
    }
    if (event.target.closest('.nav-link')) closeSidebar();
  });

  ['capture-overlay', 'palette-overlay'].forEach((id) => {
    $(id).addEventListener('click', (event) => {
      if (event.target === $(id)) closeOverlay(id);
    });
  });

  const searchTrigger = $('search-trigger');
  searchTrigger.addEventListener('click', (e) => {
    e.preventDefault();
    openPalette();
  });
  searchTrigger.addEventListener('focus', (e) => {
    e.preventDefault();
    openPalette();
  });
  searchTrigger.addEventListener('input', () => {
    const value = searchTrigger.value.trim();
    if (value) {
      openPalette();
      const paletteInput = $('palette-input');
      if (paletteInput) {
        paletteInput.value = value;
        paletteSearch(value);
      }
    }
  });

  const paletteInput = $('palette-input');
  paletteInput.addEventListener('input', () => paletteSearch(paletteInput.value));
  paletteInput.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown') { event.preventDefault(); paletteMove(1); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); paletteMove(-1); }
    else if (event.key === 'Enter') { event.preventDefault(); paletteGo(); }
    else if (event.key === 'Escape') closeOverlay('palette-overlay');
  });

  $('palette-results').addEventListener('click', (event) => {
    const item = event.target.closest('.palette-item');
    if (item) {
      window.location.hash = item.dataset.href;
      closeOverlay('palette-overlay');
    }
  });

  document.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      openPalette();
    }
    if (event.key === 'Escape') {
      closeOverlay('capture-overlay');
      closeOverlay('palette-overlay');
    }
  });

  $('menu-btn').addEventListener('click', () => {
    if ($('areaside').classList.contains('open')) closeSidebar();
    else openSidebar();
  });
  $('scrim').addEventListener('click', closeSidebar);

  window.addEventListener('ff:config-changed', setupWorkspaces);
  window.addEventListener('ff:bandeja-changed', refreshBandejaCount);

  const initial = localStorage.getItem('ff.user');
  if (initial) {
    $('user-name').textContent = initial;
    $('user-avatar').textContent = initial.charAt(0).toUpperCase();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  bind();
  setupWorkspaces();
  route();
  refreshBandejaCount();
});

export { invalidate, toast };