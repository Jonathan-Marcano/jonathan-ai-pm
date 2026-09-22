'use strict';

import { api, invalidate, listProjects, listTasks, listMeetings, listWorkspaces } from './api.js';
import { esc, icon, toast } from './ui.js';
import {
  renderInicio,
  renderMiDia,
  renderInbox,
  renderProyectos,
  renderProyectoDetalle,
  renderTareas,
  renderCalendario,
  renderReuniones,
  renderReunionDetalle,
  renderAsistente,
  renderIntegraciones,
  renderConfiguracion,
} from './views.js';

const ROUTES = {
  '/inicio': { title: 'Inicio', render: renderInicio },
  '/mi-dia': { title: 'Mi Día', render: renderMiDia },
  '/inbox': { title: 'Inbox', render: renderInbox },
  '/proyectos': { title: 'Proyectos', render: renderProyectos, detail: renderProyectoDetalle },
  '/tareas': { title: 'Tareas', render: renderTareas },
  '/calendario': { title: 'Calendario', render: renderCalendario },
  '/reuniones': { title: 'Reuniones', render: renderReuniones, detail: renderReunionDetalle },
  '/asistente': { title: 'Asistente', render: renderAsistente },
  '/integraciones': { title: 'Integraciones', render: renderIntegraciones },
  '/configuracion': { title: 'Configuración', render: renderConfiguracion },
};

const $ = (id) => document.getElementById(id);

function currentRoute() {
  const raw = window.location.hash || '#/inicio';
  const path = raw.slice(1).split('?')[0];
  if (ROUTES[path]) return { path, id: null };
  const match = path.match(/^\/([a-z-]+)\/([a-z0-9_]+)$/);
  if (match) {
    const base = `/${match[1]}`;
    if (ROUTES[base] && ROUTES[base].detail) return { path: base, id: match[2] };
  }
  return { path: '/inicio', id: null };
}

function setActive(path) {
  const key = path.slice(1);
  document.querySelectorAll('.nav-link, .mobile-item').forEach((link) => {
    link.classList.toggle('active', link.dataset.route === key);
  });
}

async function route() {
  const { path, id } = currentRoute();
  setActive(path);
  const view = $('view');
  if (view) {
    window.scrollTo({ top: 0 });
    const fresh = view.cloneNode(false);
    view.parentNode.replaceChild(fresh, view);
    const renderer = id && ROUTES[path].detail ? ROUTES[path].detail : ROUTES[path].render;
    renderer(fresh, id);
  }
  closeSidebar();
}

function closeOverlay(id) {
  const overlay = $(id);
  if (overlay) overlay.hidden = true;
}

/* ---------- Captura global ---------- */
function openCapture() {
  const overlay = $('capture-overlay');
  overlay.hidden = false;
  const input = $('capture-text');
  input.value = '';
  $('capture-char-hint').textContent = '0 / 5000';
  input.focus();
}

async function submitCapture() {
  const input = $('capture-text');
  const text = input.value.trim();
  if (!text) return;
  const submit = $('capture-submit');
  submit.disabled = true;
  try {
    await api('/api/v1/captures', { method: 'POST', body: JSON.stringify({ text }) });
    toast('Capturado. Puedes organizarlo desde Inbox.', 'success');
    closeOverlay('capture-overlay');
    refreshInboxCount();
  } catch (err) {
    toast(`No se pudo capturar: ${err.message}`, 'error');
  } finally {
    submit.disabled = false;
  }
}

async function refreshInboxCount() {
  try {
    const items = await api('/api/v1/captures?limit=100&capture_status=inbox');
    const badgeEl = $('inbox-count');
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
  $('sidebar').classList.add('open');
  $('scrim').hidden = false;
  $('menu-btn').setAttribute('aria-expanded', 'true');
}

function closeSidebar() {
  $('sidebar').classList.remove('open');
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

/* ---------- Workspace selector ---------- */
async function setupWorkspaces() {
  try {
    const workspaces = await listWorkspaces();
    const picker = $('workspace-picker');
    const select = $('workspace-select');
    if (!workspaces || !workspaces.length) return;
    if (workspaces.length === 1) {
      picker.querySelector('label').textContent = 'Workspace';
      select.innerHTML = `<option>${esc(workspaces[0].name)}</option>`;
      select.disabled = true;
      return;
    }
    const saved = localStorage.getItem('ff.workspace');
    select.innerHTML = workspaces
      .map(
        (w) =>
          `<option value="${esc(w.id)}" ${w.id === saved ? 'selected' : ''}>${esc(w.name)}</option>`,
      )
      .join('');
    select.addEventListener('change', () => {
      localStorage.setItem('ff.workspace', select.value);
      route();
    });
  } catch (_) {
    /* silencioso */
  }
}

/* ---------- Boot ---------- */
function bind() {
  window.addEventListener('hashchange', route);

  $('capture-cta').addEventListener('click', (e) => { e.preventDefault(); openCapture(); });
  $('sidebar-capture').addEventListener('click', (e) => { e.preventDefault(); openCapture(); });
  $('fab').addEventListener('click', (e) => { e.preventDefault(); openCapture(); });
  $('capture-cancel').addEventListener('click', () => closeOverlay('capture-overlay'));
  $('capture-close').addEventListener('click', () => closeOverlay('capture-overlay'));
  $('capture-submit').addEventListener('click', submitCapture);

  const captureInput = $('capture-text');
  captureInput.addEventListener('input', () => {
    $('capture-char-hint').textContent = `${captureInput.value.length} / 5000`;
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

  $('search-trigger').addEventListener('click', (e) => {
    e.preventDefault();
    openPalette();
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
    if ($('sidebar').classList.contains('open')) closeSidebar();
    else openSidebar();
  });
  $('scrim').addEventListener('click', closeSidebar);

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
  refreshInboxCount();
});