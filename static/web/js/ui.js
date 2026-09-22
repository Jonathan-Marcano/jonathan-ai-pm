'use strict';

export function esc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function fmtDate(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function fmtDayMonth(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('es-CL', { weekday: 'long', day: 'numeric', month: 'long' });
}

export function fmtFullDate(value) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('es-CL', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

export function fmtTime(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
}

export function todayISO() {
  const d = new Date();
  const tz = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - tz).toISOString().slice(0, 10);
}

export function addDaysISO(iso, days) {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + days);
  const tz = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - tz).toISOString().slice(0, 10);
}

export function timeAgo(value) {
  if (!value) return '';
  const then = new Date(value);
  const seconds = Math.max(0, Math.floor((Date.now() - then.getTime()) / 1000));
  if (seconds < 60) return 'ahora mismo';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'ayer';
  if (days < 31) return `hace ${days} días`;
  return fmtDate(value);
}

const ICONS = {
  alert: '<path d="M10 3.5 17 16.5H3L10 3.5Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" fill="none"/><path d="M10 8.5v3.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" fill="none"/><circle cx="10" cy="14.2" r="0.9" fill="currentColor"/>',
  check: '<path d="m4.5 10.5 3.4 3.4 7.6-7.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>',
  clock: '<circle cx="10" cy="10" r="6.5" stroke="currentColor" stroke-width="1.6" fill="none"/><path d="M10 6.8V10l2.2 1.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" fill="none"/>',
  play: '<path d="M7 4.8v10.4l8-5.2-8-5.2Z" fill="currentColor" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>',
  doc: '<path d="M6 3.5h5l3.5 3.5v9.5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-12a1 1 0 0 1 1-1Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" fill="none"/><path d="M11 3.5V7h3.5" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" fill="none"/>',
  drive: '<path d="M3 8 8.5 3l3.2 3 5.3 2-4.6 5.2-2.4-1.6L3 8.5Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" fill="none"/><path d="M3 8l6 1.6 2.8.4 2.2-1.5M8.6 3.2 6.8 8.8 6 9.8" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" fill="none"/>',
  flag: '<path d="M5.5 17V4l9 2.5-9 2.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>',
  link: '<path d="M9 13.5l2.5-2.5M7 11l-2.5 2.5a3 3 0 0 0 4.2 4.2L11.2 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/><path d="M13 6.5 15.5 4a3 3 0 0 1 4.2 4.2L16.5 10.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>',
  refresh: '<path d="M6.2 5A6 6 0 0 1 16 8M4 3.5V8h4.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/><path d="M13.8 15A6 6 0 0 1 4 12M16 12.5V17h-4.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>',
  arrow: '<path d="M4 10h11M10.5 5.5 15 10l-4.5 4.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>',
  folder: '<path d="M3 5.5h5l1.5 2H17v8.5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5.5Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" fill="none"/>',
  edit: '<path d="m13.5 4.5 2 2L7 15l-3 1 1-3 8.5-8.5Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" fill="none"/>',
  calendar: '<rect x="3" y="4.5" width="14" height="12" rx="1.5" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M3 8.5h14M7 3v3M13 3v3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/>',
  sparkles: '<path d="M10 3l1.5 3.6 3.6 1.5-3.6 1.5L10 13.2 8.5 9.6 4.9 8.1l3.6-1.5L10 3Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" fill="none"/><path d="M14.5 13.5l.8 1.7 1.7.8-1.7.8-.8 1.7-.8-1.7-1.7-.8 1.7-.8.8-1.7Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" fill="none"/>',
  target: '<circle cx="10" cy="10" r="6.5" stroke="currentColor" stroke-width="1.6" fill="none"/><circle cx="10" cy="10" r="2.5" stroke="currentColor" stroke-width="1.6" fill="none"/>',
  send: '<path d="m4 10 13-6-4 13-2-5-7-2Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" fill="none"/><path d="m11 12 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/>',
  trash: '<path d="M5 6.5h10M8 6.5V4.8a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1.7M6.5 6.5 7 15.5a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1l.5-9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>',
  info: '<circle cx="10" cy="10" r="6.5" stroke="currentColor" stroke-width="1.6" fill="none"/><path d="M10 8.8v4M10 6.6v.1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" fill="none"/>',
  plus: '<path d="M10 4v12M4 10h12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" fill="none"/>',
  search: '<circle cx="9" cy="9" r="5" stroke="currentColor" stroke-width="1.6" fill="none"/><path d="m13 13 4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" fill="none"/>',
  warn: '<path d="M10 3.5 17 16.5H3L10 3.5Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" fill="none"/><path d="M10 8.5v3.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" fill="none"/><circle cx="10" cy="14.2" r="0.9" fill="currentColor"/>',
  x: '<path d="M5 5l10 10M15 5 5 15" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" fill="none"/>',
};

export function icon(name) {
  const body = ICONS[name] || ICONS.info;
  return `<svg viewBox="0 0 20 20" class="ff-icon" aria-hidden="true">${body}</svg>`;
}

export function badge(status) {
  const raw = String(status || 'unknown');
  const key = raw.replace(/[^a-z0-9]/g, '');
  return `<span class="badge badge-${key}"><span class="badge-dot" aria-hidden="true"></span>${esc(humanStatus(raw))}</span>`;
}

const STATUS_LABELS = {
  active: 'Activa',
  paused: 'En espera',
  archived: 'Archivada',
  planned: 'Planificado',
  completed: 'Completado',
  cancelled: 'Cancelado',
  inbox: 'Bandeja',
  ready: 'Lista',
  in_progress: 'En curso',
  blocked: 'Bloqueada',
  done: 'Completada',
  scheduled: 'Programada',
  captured: 'Capturado',
  accepted: 'Aceptado',
  dismissed: 'Descartado',
  rejected: 'Rechazado',
  in_review: 'En revisión',
  reviewed: 'Revisada',
  triaged: 'Clasificada',
  on_track: 'Al día',
  at_risk: 'En riesgo',
  off_track: 'Fuera de curso',
};

export function humanStatus(status) {
  return STATUS_LABELS[status] || String(status);
}

export function prio(level) {
  const labels = { critical: 'Crítico', high: 'Alto', medium: 'Medio', low: 'Bajo' };
  return `<span class="prio prio-${esc(level)}">${esc(labels[level] || level)}</span>`;
}

export function progressBar(percent) {
  const p = Math.max(0, Math.min(100, Math.round(percent || 0)));
  return `<div class="progress" role="progressbar" aria-valuenow="${p}" aria-valuemin="0" aria-valuemax="100"><div class="progress-bar" style="width:${p}%"></div></div>`;
}

export function toast(message, kind = 'info') {
  const host = document.getElementById('toasts');
  if (!host) return;
  const icons = { success: 'check', error: 'warn', info: 'info' };
  const node = document.createElement('div');
  node.className = `toast toast-${kind}`;
  node.innerHTML = `${icon(icons[kind] || 'info')}<span>${esc(message)}</span>`;
  host.appendChild(node);
  window.setTimeout(() => {
    node.style.opacity = '0';
    node.style.transition = 'opacity 200ms ease';
    window.setTimeout(() => node.remove(), 220);
  }, 3600);
}

export function skeleton(rows = 3, block = false) {
  const lines = Array.from({ length: rows }, () => '<div class="skeleton skel-line"></div>').join('');
  const inner = block ? `<div class="skeleton skel-block"></div>${lines}` : lines;
  return `<div class="skeleton-panel" aria-busy="true">${inner}</div>`;
}

export function emptyBlock(message, actionHtml = '') {
  return `<div class="empty"><span class="empty-icon">${icon('check')}</span><span>${esc(message)}</span>${actionHtml ? `<div>${actionHtml}</div>` : ''}</div>`;
}

export function errorBlock(message) {
  return `<div class="error">${esc(message)}</div>`;
}

export function setPageTitle(title) {
  document.getElementById('route-title').textContent = title;
  document.title = `${title} · FaroFlow`;
}

export function nowGroup(label, extraClass = '') {
  return `<div class="tl-head"><span class="tl-time">${esc(label)}</span></div>`;
}

export async function promptDate(caption, initial) {
  return new Promise((resolve) => {
    const value = initial || todayISO();
    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    overlay.innerHTML = `
      <div class="modal modal-sm" role="dialog" aria-modal="true" aria-labelledby="pd-title">
        <header class="modal-head"><h3 id="pd-title">${esc(caption)}</h3>
          <button class="icon-btn" type="button" data-pd="cancel" aria-label="Cerrar">${icon('x')}</button>
        </header>
        <div class="modal-body">
          <input type="date" class="capture-textarea" value="${esc(value)}" aria-label="Nueva fecha" />
          <div class="modal-actions">
            <button class="btn btn-ghost" type="button" data-pd="cancel">Cancelar</button>
            <button class="btn btn-primary" type="button" data-pd="ok">Guardar</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const input = overlay.querySelector('input');
    overlay.addEventListener('click', (event) => {
      const close = event.target.closest('[data-pd]');
      if (close) {
        const ok = close.dataset.pd === 'ok';
        overlay.remove();
        resolve(ok ? input.value : null);
      }
      if (event.target === overlay) {
        overlay.remove();
        resolve(null);
      }
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') { event.preventDefault(); overlay.remove(); resolve(input.value); }
      if (event.key === 'Escape') { overlay.remove(); resolve(null); }
    });
    input.focus();
  });
}

export function genEntityId(prefix, fromName = '') {
  const base = (fromName || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40);
  return `${prefix}_${base || 'item'}_${Math.random().toString(36).slice(2, 8)}`;
}

export function openForm({ title, fields = [], submitLabel = 'Guardar', hint = '' }) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    const rows = fields
      .map((f) => {
        const id = `ff-${f.name}`;
        let control;
        if (f.type === 'select') {
          const options = (f.options || [])
            .map((o) => {
              const value = typeof o === 'object' ? o.value : o;
              const label = typeof o === 'object' ? o.label || o.value : o;
              const selected = f.value !== undefined && String(f.value) === String(value) ? ' selected' : '';
              return `<option value="${esc(value)}"${selected}>${esc(label)}</option>`;
            })
            .join('');
          control = `<select id="${id}" class="form-control"${f.required ? ' required' : ''}>${options}</select>`;
        } else if (f.type === 'textarea') {
          control = `<textarea id="${id}" class="capture-textarea" rows="${f.rows || 2}" maxlength="${f.maxlength || 5000}"${f.required ? ' required' : ''}>${esc(f.value || '')}</textarea>`;
        } else if (f.type === 'datetime-local' || f.type === 'date') {
          control = `<input id="${id}" class="form-control" type="${esc(f.type)}" value="${esc(f.value || '')}"${f.required ? ' required' : ''} />`;
        } else {
          control = `<input id="${id}" class="form-control" type="text" value="${esc(f.value || '')}"${f.required ? ' required' : ''} placeholder="${esc(f.placeholder || '')}" maxlength="${esc(f.maxlength || 300)}" />`;
        }
        return `<label class="modal-label" for="${id}">${esc(f.label)}</label>${control}`;
      })
      .join('');
    overlay.innerHTML = `
      <div class="modal modal-sm" role="dialog" aria-modal="true" aria-labelledby="of-title">
        <header class="modal-head"><h3 id="of-title">${esc(title)}</h3>
          <button class="icon-btn" type="button" data-of="cancel" aria-label="Cerrar">${icon('x')}</button></header>
        <div class="modal-body">
          ${hint ? `<p class="modal-hint">${esc(hint)}</p>` : ''}
          ${rows}
          <div class="modal-actions">
            <button class="btn btn-ghost" type="button" data-of="cancel">Cancelar</button>
            <button class="btn btn-primary" type="button" data-of="ok">${esc(submitLabel)}</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const readValues = () => {
      const out = {};
      for (const f of fields) {
        const node = overlay.querySelector(`#ff-${f.name}`);
        if (!node) continue;
        let val = node.value;
        if (f.type === 'datetime-local') val = val ? new Date(val).toISOString() : '';
        else val = val.trim();
        if (val) out[f.name] = val;
      }
      return out;
    };
    const missing = (v) => fields.some((f) => f.required && !v[f.name]);
    const finish = (v) => {
      overlay.remove();
      resolve(v);
    };
    overlay.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-of]');
      if (btn) {
        if (btn.dataset.of === 'cancel') return finish(null);
        const v = readValues();
        if (missing(v)) {
          toast('Completa los campos obligatorios', 'error');
          return;
        }
        finish(v);
      }
      if (event.target === overlay) finish(null);
    });
    const first = overlay.querySelector('input, select, textarea');
    if (first) first.focus();
    overlay.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && event.target.tagName === 'INPUT') {
        event.preventDefault();
        const v = readValues();
        if (missing(v)) {
          toast('Completa los campos obligatorios', 'error');
          return;
        }
        finish(v);
      }
      if (event.key === 'Escape') finish(null);
    });
  });
}

export function promptTriage({ projects, meetings }) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    const projOptions = (projects || [])
      .map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`)
      .join('');
    const meetOptions = (meetings || [])
      .filter((m) => m.status === 'scheduled')
      .map((m) => `<option value="${esc(m.id)}">${esc(m.title)}</option>`)
      .join('');
    overlay.innerHTML = `
      <div class="modal modal-sm" role="dialog" aria-modal="true" aria-labelledby="ct-title">
        <header class="modal-head"><h3 id="ct-title">Clasificar captura</h3>
          <button class="icon-btn" type="button" data-ct="cancel" aria-label="Cerrar">${icon('x')}</button></header>
        <div class="modal-body">
          <label class="modal-label" for="ct-disposition">Tipo</label>
          <select id="ct-disposition" class="form-control">
            <option value="task">Tarea</option>
            <option value="action">Elemento de acción</option>
            <option value="reference">Referencia</option>
            <option value="dismissed">Descartar</option>
          </select>
          <div data-ct-group="task reference">
            <label class="modal-label" for="ct-project">Proyecto</label>
            <select id="ct-project" class="form-control"><option value="">Sin proyecto</option>${projOptions}</select>
          </div>
          <div data-ct-group="task">
            <label class="modal-label" for="ct-priority">Prioridad</label>
            <select id="ct-priority" class="form-control">
              <option value="low">Baja</option>
              <option value="medium" selected>Media</option>
              <option value="high">Alta</option>
              <option value="critical">Crítica</option>
            </select>
            <label class="modal-label" for="ct-due">Vence</label>
            <input id="ct-due" type="date" class="form-control" />
          </div>
          <div data-ct-group="action" hidden>
            <label class="modal-label" for="ct-meeting">Reunión</label>
            <select id="ct-meeting" class="form-control"><option value="">Elige reunión…</option>${meetOptions}</select>
            <label class="modal-label" for="ct-owner">Responsable (owner)</label>
            <input id="ct-owner" type="text" class="form-control" placeholder="Quién responde" maxlength="200" />
          </div>
          <div data-ct-group="dismissed" hidden>
            <label class="modal-label" for="ct-note">Motivo</label>
            <textarea id="ct-note" class="capture-textarea" rows="2" maxlength="2000" placeholder="Por qué se descarta…"></textarea>
          </div>
          <div class="modal-actions">
            <button class="btn btn-ghost" type="button" data-ct="cancel">Cancelar</button>
            <button class="btn btn-primary" type="button" data-ct="ok">Clasificar</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const disposition = () => overlay.querySelector('#ct-disposition').value;
    const setGroups = () => {
      overlay.querySelectorAll('[data-ct-group]').forEach((g) => {
        g.hidden = !(g.dataset.ctGroup || '').split(' ').includes(disposition());
      });
    };
    const valueOf = (id) => overlay.querySelector(`#${id}`).value.trim();
    const finish = (v) => {
      overlay.remove();
      resolve(v);
    };
    overlay.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-ct]');
      if (btn) {
        if (btn.dataset.ct === 'cancel') return finish(null);
        const d = disposition();
        const payload = { disposition: d };
        if (d === 'task') {
          const projectId = valueOf('ct-project');
          if (!projectId) {
            toast('Elige un proyecto para la tarea', 'error');
            return;
          }
          payload.project_id = projectId;
          payload.task_id = genEntityId('tsk');
          payload.priority = valueOf('ct-priority');
          const due = valueOf('ct-due');
          if (due) payload.due_at = due;
        } else if (d === 'action') {
          const meetingId = valueOf('ct-meeting');
          const owner = valueOf('ct-owner');
          if (!meetingId || !owner) {
            toast('El elemento de acción requiere reunión y responsable', 'error');
            return;
          }
          payload.meeting_id = meetingId;
          payload.action_item_id = genEntityId('act');
          payload.owner = owner;
        } else if (d === 'dismissed') {
          const note = valueOf('ct-note');
          if (!note) {
            toast('Indica el motivo para descartar', 'error');
            return;
          }
          payload.note = note;
        } else {
          const projectId = valueOf('ct-project');
          if (projectId) payload.project_id = projectId;
        }
        finish(payload);
      }
      if (event.target === overlay) finish(null);
    });
    overlay.querySelector('#ct-disposition').addEventListener('change', setGroups);
    overlay.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') finish(null);
    });
    setGroups();
    overlay.querySelector('#ct-disposition').focus();
  });
}

export function promptCompletionNote(caption = 'Completar tarea') {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    overlay.innerHTML = `
      <div class="modal modal-sm" role="dialog" aria-modal="true" aria-labelledby="cn-title">
        <header class="modal-head"><h3 id="cn-title">${esc(caption)}</h3>
          <button class="icon-btn" type="button" data-cn="cancel" aria-label="Cerrar">${icon('x')}</button>
        </header>
        <div class="modal-body">
          <label class="modal-label" for="cn-input">Nota de compleción</label>
          <textarea id="cn-input" class="capture-textarea" rows="2" maxlength="2000" aria-label="Nota de compleción" placeholder="Qué se completó… (obligatoria si no hay registro de trabajo)"></textarea>
          <p class="form-hint">Faro guarda la nota como evidencia de la decisión.</p>
          <div class="modal-actions">
            <button class="btn btn-ghost" type="button" data-cn="cancel">Cancelar</button>
            <button class="btn btn-primary" type="button" data-cn="ok">Completar</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const input = overlay.querySelector('#cn-input');
    input.focus();
    const finish = (value) => {
      overlay.remove();
      resolve(value);
    };
    overlay.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-cn]');
      if (btn) finish(btn.dataset.cn === 'ok' ? input.value.trim() : null);
      if (event.target === overlay) finish(null);
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); finish(input.value.trim()); }
      if (event.key === 'Escape') finish(null);
    });
  });
}