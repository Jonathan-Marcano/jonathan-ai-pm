'use strict';

import {
  listBandeja,
  receiveBandeja,
  refineBandeja,
  discardBandeja,
  applyBandeja,
  listProjects,
  listAccounts,
  listCategoriesByHousehold,
  listHouseholds,
  listHabits,
} from './api.js';
import {
  esc,
  fmtDate,
  fmtTime,
  todayISO,
  icon,
  badge,
  toast,
  skeleton,
  emptyBlock,
  errorBlock,
} from './ui.js';
import { suggestCapture } from './capture-triage.js';

const KIND_LABELS = {
  unknown: 'Por clasificar',
  task: 'Tarea',
  expense: 'Gasto',
  income: 'Ingreso',
  habit: 'Hábito',
  note: 'Nota / referencia',
};

const PENDING_STATUSES = ['received', 'reviewing', 'confirmed'];

let bjQuery = '';
let bjKind = '';

function statusBadge(status) {
  return badge(status);
}

export async function renderBandeja(el) {
  el.innerHTML = `
    <div class="page-head">
      <h1>Bandeja</h1>
      <p class="page-sub">Capturas manuales y de Telegram. Clasifica una a una con tu criterio.</p>
      <div class="page-head-actions">
        <button class="btn btn-primary" data-capture-open type="button">${icon('plus')} Capturar</button>
      </div>
    </div>
    ${skeleton(5)}`;
  try {
    const [items, projects, habits, households, accounts] = await Promise.all([
      listBandeja({ limit: 500 }),
      listProjects(),
      listHabits(),
      listHouseholds().catch(() => []),
      listAccounts().catch(() => []),
    ]);
    const pending = (items || []).filter((i) => PENDING_STATUSES.includes(i.status));
    const applied = (items || []).filter((i) => i.status === 'applied');
    const discarded = (items || []).filter((i) => i.status === 'discarded');
    const errors = (items || []).filter((i) => i.status === 'error');

    const query = new URLSearchParams(window.location.hash.split('?')[1] || '');
    const tab = query.get('status') || 'pending';
    const selectedId = query.get('item') || '';
    const itemsById = new Map((items || []).map((i) => [i.id, i]));
    const selected = selectedId ? itemsById.get(selectedId) : undefined;
    const selectedIsPending = !!selected && PENDING_STATUSES.includes(selected.status);

    const syncHtml = `
      <section class="sync-strip">
        <div class="sync-icon">${icon('send')}</div>
        <div class="sync-info">
          <b>${esc(pending.length)} ${pending.length === 1 ? 'captura pendiente' : 'capturas pendientes'}</b>
          <span>Faro sugiere; tú decides el destino de cada una.</span>
        </div>
        <div class="sync-actions">
          <button class="btn btn-ghost btn-sm" id="bj-refresh" type="button">${icon('clock')} Refrescar</button>
        </div>
      </section>`;

    const tabsHtml = `
      <div class="tabs" role="tablist" aria-label="Estado de la bandeja">
        <button class="tab ${tab === 'pending' ? 'active' : ''}" data-tab="pending">Pendientes (${pending.length})</button>
        <button class="tab ${tab === 'applied' ? 'active' : ''}" data-tab="applied">Aplicadas (${applied.length})</button>
        <button class="tab ${tab === 'discarded' ? 'active' : ''}" data-tab="discarded">Descartadas (${discarded.length})</button>
        <button class="tab ${tab === 'error' ? 'active' : ''}" data-tab="error">Errores (${errors.length})</button>
      </div>`;

    el.innerHTML = `
      <div class="page-head">
        <h1>Bandeja</h1>
        <p class="page-sub">${esc(pending.length)} ${pending.length === 1 ? 'captura pendiente' : 'capturas pendientes'} por clasificar.</p>
        <div class="page-head-actions">
          <button class="btn btn-primary" data-capture-open type="button">${icon('plus')} Capturar</button>
        </div>
      </div>
      ${syncHtml}
      <div class="split-bandeja">
        <aside class="bandeja-list-host ${selected ? 'is-hidden' : ''}" id="bj-list-host">
          ${tabsHtml}
          <div class="flujo-toolbar" style="padding:0 18px 8px">
            <label class="flujo-toolbar-grow"><span class="js-search" aria-hidden="true">${icon('search')}</span>
              <input type="search" class="form-control flujo-search" id="bj-q" placeholder="Buscar captura…" value="${esc(bjQuery)}" autocomplete="off" aria-label="Buscar captura" />
            </label>
            <select class="form-control flujo-search" id="bj-kind" aria-label="Filtrar por tipo">
              <option value="">Todos los tipos</option>
              ${Object.entries(KIND_LABELS).map(([k, label]) => `<option value="${k}" ${bjKind === k ? 'selected' : ''}>${esc(label)}</option>`).join('')}
            </select>
          </div>
          <section class="card">
            <div class="card-body no-pad">
              ${renderList(tab, pending, applied, discarded, errors, selectedId)}
            </div>
          </section>
        </aside>
        <section class="bandeja-detail-host ${selected ? '' : 'is-hidden'}" id="bj-detail-host" aria-live="polite">
          <section class="card">
            <div class="card-body">
              ${renderDetail(selected, { selectedIsPending })}
            </div>
          </section>
        </section>
      </div>`;

    bindTabs(el);
    bindItems(el, { projects, habits, households, accounts, itemsById });
    bindFilters(el, { pending, applied, discarded, errors, selectedId });
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Bandeja</h1></div>${errorBlock(`No disponible: ${esc(err.message)}`)}`;
  }
}

const KIND_ICONS = {
  task: 'check',
  expense: 'coin',
  income: 'arrow',
  habit: 'target',
  note: 'doc',
  reference: 'send',
  unknown: 'info',
};

function renderList(tab, pending, applied, discarded, errors, selectedId) {
  const map = { pending, applied, discarded, error: errors };
  const full = map[tab] || [];
  const q = bjQuery.trim().toLowerCase();
  const list = full.filter(
    (item) =>
      (!bjKind || item.kind === bjKind) &&
      (!q || (item.original_text || '').toLowerCase().includes(q) || (item.decision_note || '').toLowerCase().includes(q)),
  );
  if (!list.length) {
    return `<div class="card-body">${emptyBlock(
      full.length
        ? 'Ninguna captura coincide con la búsqueda o el filtro.'
        : tab === 'pending'
          ? 'Bandeja al día: nada pendiente por clasificar.'
          : 'No hay elementos en este estado.',
    )}</div>`;
  }
  return `<div class="bandeja-list">
    ${list
      .map(
        (item) => {
          const isPending = PENDING_STATUSES.includes(item.status);
          const active = item.id === selectedId;
          const kindIcon = KIND_ICONS[item.kind] || 'info';
          return `
        <div class="bandeja-item ${active ? 'active' : ''}">
          <button class="bandeja-row" data-bj-select="${esc(item.id)}" type="button">
            <span class="bandeja-icon">${icon(kindIcon)}</span>
            <span class="bandeja-content">
              <span class="bandeja-title">${esc(item.original_text)}</span>
              <span class="bandeja-meta">
                ${statusBadge(item.status)}
                <span class="kind-chip kind-${esc(item.kind || 'unknown')}">${esc(KIND_LABELS[item.kind] || item.kind)}</span>
                ${item.amount ? `<b>$${esc(Number(item.amount).toLocaleString('es-CL'))}</b>` : ''}
                <span>${esc(fmtDate(item.original_at))} ${esc(fmtTime(item.original_at))}</span>
                ${item.author ? `· ${esc(item.author)}` : ''}
              </span>
              ${item.status === 'applied' || item.status === 'discarded' ? `
                <span class="bandeja-meta">${icon('check')} Resuelto ${esc(fmtDate(item.resolved_at))} ${esc(fmtTime(item.resolved_at))}</span>` : ''}
            </span>
          </button>
        </div>`;
        },
      )
      .join('')}
  </div>`;
}

function renderDetail(item, { selectedIsPending }) {
  if (!item) {
    return `${emptyBlock('Selecciona una captura de la lista para revisarla aquí.')}`;
  }
  const suggestion = suggestCapture(item.original_text || '');
  const resolved = item.status === 'applied' || item.status === 'discarded';
  return `
    <div class="detail-back">
      <button class="btn btn-ghost btn-sm bandeja-back" data-bj-back type="button">${icon('arrow')} Volver a la lista</button>
    </div>
    <div class="detail-head">
      <div class="detail-title">«${esc(item.original_text)}»</div>
      <div class="bandeja-meta">
        ${statusBadge(item.status)}
        <span class="kind-chip kind-${esc(item.kind || 'unknown')}">${esc(KIND_LABELS[item.kind] || item.kind)}</span>
        ${item.amount ? `<b class="detail-amount">$${esc(Number(item.amount).toLocaleString('es-CL'))}</b>` : ''}
        ${item.channel ? `· ${esc(item.channel)}` : ''}
        ${item.author ? `· ${esc(item.author)}` : ''}
      </div>
    </div>
    ${selectedIsPending && suggestion && suggestion.kind !== 'unknown' ? `
      <div class="capture-suggest-chip">
        <span class="item-sub">Faro sugiere:</span>
        <span class="kind-chip kind-${esc(suggestion.kind)}">${esc(KIND_LABELS[suggestion.kind] || suggestion.kind)}</span>
        <span class="capture-suggest-conf">${Math.round(suggestion.confidence * 100)}%</span>
        ${suggestion.amount ? `<b>$${esc(Number(suggestion.amount).toLocaleString('es-CL'))}</b>` : ''}
        ${(suggestion.reasons || []).length ? `<span class="capture-suggest-reasons">${esc(suggestion.reasons.join(' '))}</span>` : ''}
      </div>` : ''}
    ${resolved ? `
      <div class="detail-resolved">
        ${icon('check')} Resuelto ${esc(fmtDate(item.resolved_at))} ${esc(fmtTime(item.resolved_at))}
        ${item.destination_module ? `→ <b>${esc(item.destination_module)}</b>` : ''}
        ${item.destination_ref ? `· ${esc(item.destination_ref)}` : ''}
        ${item.decision_note ? `<div class="decision-note">«${esc(item.decision_note)}»</div>` : ''}
      </div>` : ''}
    ${item.error ? `<div class="bandeja-meta text-danger">${esc(item.error)}</div>` : ''}
    <div class="detail-actions">
      ${item.status === 'error' ? `<button class="btn btn-ghost" data-bj-retry="${esc(item.id)}">Reintentar</button>` : ''}
      ${selectedIsPending ? `
        <button class="btn btn-primary" data-bj-apply="${esc(item.id)}">${icon('check')} Clasificar</button>
        <button class="btn btn-ghost" data-bj-refine="${esc(item.id)}">${icon('edit')} Editar</button>
        <button class="btn btn-danger-soft" data-bj-discard="${esc(item.id)}">${icon('trash')} Descartar</button>` : ''}
    </div>`;
}

function bindFilters(el, { pending, applied, discarded, errors, selectedId }) {
  const q = el.querySelector('#bj-q');
  const kind = el.querySelector('#bj-kind');
  const rerender = () => {
    const tab = el.querySelector('.tab.active')?.dataset.tab || 'pending';
    const host = el.querySelector('#bj-list-host .card-body');
    if (host) host.innerHTML = renderList(tab, pending, applied, discarded, errors, selectedId);
  };
  if (q) {
    q.addEventListener('input', () => {
      bjQuery = q.value;
      rerender();
    });
  }
  if (kind) {
    kind.addEventListener('change', () => {
      bjKind = kind.value;
      rerender();
    });
  }
}

function bindTabs(el) {
  const refresh = el.querySelector('#bj-refresh');
  if (refresh) {
    refresh.addEventListener('click', () => {
      window.dispatchEvent(new CustomEvent('ff:bandeja-changed'));
      renderBandeja(el);
    });
  }
  el.querySelectorAll('[data-tab]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const status = btn.dataset.tab === 'pending' ? '' : btn.dataset.tab;
      window.location.hash = `#/bandeja${status ? `?status=${status}` : ''}`;
      setTimeout(() => renderBandeja(el), 240);
    });
  });
}

/* ---------- Modales de clasificación / edición ---------- */

function classifyModal({ item, projects, habits, households, accounts, categories }) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    let projOpts = '<option value="">Sin proyecto</option>';
    for (const p of projects || []) projOpts += `<option value="${esc(p.id)}">${esc(p.name)}</option>`;
    let habitOpts = '<option value="">Elige hábito…</option>';
    for (const h of habits || []) if (h.status !== 'archived') habitOpts += `<option value="${esc(h.id)}">${esc(h.name)}</option>`;
    let accountOpts = '<option value="">Elige cuenta…</option>';
    for (const a of accounts || []) if (a.status === 'active') accountOpts += `<option value="${esc(a.id)}">${esc(a.name)}</option>`;
    let categoryOpts = '<option value="">Sin categoría</option>';
    for (const c of categories || []) categoryOpts += `<option value="${esc(c.id)}">${esc(c.name)}</option>`;

    overlay.innerHTML = `
      <div class="modal modal-md" role="dialog" aria-modal="true" aria-labelledby="cl-title">
        <header class="modal-head"><h3 id="cl-title">Clasificar captura</h3>
          <button class="icon-btn" type="button" data-cl="cancel" aria-label="Cerrar">${icon('x')}</button></header>
        <div class="modal-body">
          <p class="modal-hint">«${esc(item.original_text)}»</p>
          <label class="modal-label" for="cl-kind">Destino</label>
          <select id="cl-kind" class="form-control">
            <option value="task">Tarea (Trabajo)</option>
            <option value="expense">Gasto (Finanzas)</option>
            <option value="income">Ingreso (Finanzas)</option>
            <option value="habit">Hábito</option>
            <option value="note">Nota / referencia</option>
          </select>
          <div data-cl-group="task">
            <label class="modal-label" for="cl-project">Proyecto</label>
            <select id="cl-project" class="form-control">${projOpts}</select>
            <div class="field-group">
              <div><label class="modal-label" for="cl-prio">Prioridad</label>
              <select id="cl-prio" class="form-control">
                <option value="low">Baja</option><option value="medium" selected>Media</option>
                <option value="high">Alta</option><option value="critical">Crítica</option>
              </select></div>
              <div><label class="modal-label" for="cl-due">Vence</label>
              <input id="cl-due" type="date" class="form-control" value="" /></div>
            </div>
          </div>
          <div data-cl-group="expense income">
            <div class="field-group">
              <div><label class="modal-label" for="cl-amount">Monto (en pesos)</label>
              <input id="cl-amount" type="number" min="1" class="form-control" value="${esc(item.amount || '')}" /></div>
              <div><label class="modal-label" for="cl-account">Cuenta</label>
              <select id="cl-account" class="form-control">${accountOpts}</select></div>
            </div>
            <label class="modal-label" for="cl-category">Categoría</label>
            <select id="cl-category" class="form-control">${categoryOpts}</select>
            <label class="modal-label" for="cl-date">Fecha</label>
            <input id="cl-date" type="date" class="form-control" value="${esc(todayISO())}" />
          </div>
          <div data-cl-group="habit">
            <label class="modal-label" for="cl-habit">Hábito</label>
            <select id="cl-habit" class="form-control">${habitOpts}</select>
          </div>
          <div class="modal-actions">
            <button class="btn btn-ghost" type="button" data-cl="cancel">Cancelar</button>
            <button class="btn btn-primary" type="button" data-cl="ok">Aplicar</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const kind = overlay.querySelector('#cl-kind');
    const suggestion = suggestCapture(item.original_text);
    if (suggestion && suggestion.kind !== 'unknown') {
      kind.value = suggestion.kind;
      if (suggestion.amount) {
        const amountField = overlay.querySelector('#cl-amount');
        if (amountField && !item.amount) amountField.value = suggestion.amount;
      }
      const hint = document.createElement('div');
      hint.className = 'capture-suggest-chip';
      hint.innerHTML = `<span class="item-sub">Faro sugiere:</span>
        <span class="kind-chip kind-${esc(suggestion.kind)}">${esc(KIND_LABELS[suggestion.kind] || suggestion.kind)}</span>
        <span class="capture-suggest-conf">${Math.round(suggestion.confidence * 100)}%</span>
        ${suggestion.amount ? `<b>$${esc(Number(suggestion.amount).toLocaleString('es-CL'))}</b>` : ''}
        ${(suggestion.reasons || []).length ? `<span class="capture-suggest-reasons">${esc(suggestion.reasons.join(' '))}</span>` : ''}`;
      overlay.querySelector('.modal-hint').after(hint);
    }
    const syncKind = () => {
      const k = kind.value;
      overlay.querySelectorAll('[data-cl-group]').forEach((g) => {
        g.hidden = !(g.dataset.clGroup || '').split(' ').includes(k);
      });
    };
    kind.addEventListener('change', syncKind);
    syncKind();

    const finish = (v) => {
      overlay.remove();
      resolve(v);
    };
    overlay.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-cl]');
      if (btn) {
        if (btn.dataset.cl === 'cancel') return finish(null);
        const k = kind.value;
        const payload = { decision: k };
        const val = (id) => overlay.querySelector(`#${id}`).value.trim();
        if (k === 'task') {
          payload.project_id = val('cl-project') || undefined;
          payload.priority = val('cl-prio');
          const due = val('cl-due');
          if (due) payload.due_at = due;
        } else if (k === 'expense' || k === 'income') {
          const amount = Number(val('cl-amount'));
          const account = val('cl-account');
          if (!amount || amount <= 0) {
            toast('Indica un monto válido', 'error');
            return;
          }
          if (!account) {
            toast('Elige una cuenta (configúrala en Finanzas si no hay ninguna)', 'error');
            return;
          }
          payload.amount = amount;
          payload.account_id = account;
          const cat = val('cl-category');
          if (cat) payload.category_id = cat;
          const d = val('cl-date');
          if (d) payload.recorded_on = d;
        } else if (k === 'habit') {
          const h = val('cl-habit');
          if (!h) {
            toast('Elige un hábito', 'error');
            return;
          }
          payload.habit_id = h;
        }
        finish(payload);
      }
      if (event.target === overlay) finish(null);
    });
    overlay.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') finish(null);
    });
    kind.focus();
  });
}

const elCategories = new Map();

function refineModal(item, projects, habits, accounts, categories) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    let projOpts = '<option value="">Sin proyecto</option>';
    for (const p of projects || []) projOpts += `<option value="${esc(p.id)}">${esc(p.name)}</option>`;
    let accountOpts = '<option value="">Sin cuenta</option>';
    for (const a of accounts || []) accountOpts += `<option value="${esc(a.id)}">${esc(a.name)}</option>`;
    let categoryOpts = '<option value="">Sin categoría</option>';
    for (const c of categories || []) categoryOpts += `<option value="${esc(c.id)}">${esc(c.name)}</option>`;
    let habitOpts = '<option value="">Sin hábito</option>';
    for (const h of habits || []) habitOpts += `<option value="${esc(h.id)}">${esc(h.name)}</option>`;

    overlay.innerHTML = `
      <div class="modal modal-md" role="dialog" aria-modal="true" aria-labelledby="rf-title">
        <header class="modal-head"><h3 id="rf-title">Editar captura</h3>
          <button class="icon-btn" type="button" data-rf="cancel" aria-label="Cerrar">${icon('x')}</button></header>
        <div class="modal-body">
          <label class="modal-label" for="rf-kind">Tipo</label>
          <select id="rf-kind" class="form-control">
            ${Object.entries(KIND_LABELS).map(([k, label]) => `<option value="${k}" ${item.kind === k ? 'selected' : ''}>${esc(label)}</option>`).join('')}
          </select>
          <div class="field-group">
            <div><label class="modal-label" for="rf-amount">Monto</label>
            <input id="rf-amount" type="number" min="1" class="form-control" value="${esc(item.amount || '')}" /></div>
            <div><label class="modal-label" for="rf-account">Cuenta</label>
            <select id="rf-account" class="form-control">${accountOpts}</select></div>
          </div>
          <label class="modal-label" for="rf-category">Categoría</label>
          <select id="rf-category" class="form-control">${categoryOpts}</select>
          <div class="field-group">
            <div><label class="modal-label" for="rf-project">Proyecto</label>
            <select id="rf-project" class="form-control">${projOpts}</select></div>
            <div><label class="modal-label" for="rf-habit">Hábito</label>
            <select id="rf-habit" class="form-control">${habitOpts}</select></div>
          </div>
          <label class="modal-label" for="rf-note">Nota de decisión</label>
          <textarea id="rf-note" class="capture-textarea" rows="2" maxlength="500" placeholder="Opcional">${esc(item.decision_note || '')}</textarea>
          <div class="modal-actions">
            <button class="btn btn-ghost" type="button" data-rf="cancel">Cancelar</button>
            <button class="btn btn-primary" type="button" data-rf="ok">Guardar</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const finish = (v) => {
      overlay.remove();
      resolve(v);
    };
    overlay.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-rf]');
      if (btn) {
        if (btn.dataset.rf === 'cancel') return finish(null);
        const val = (id) => overlay.querySelector(`#${id}`).value.trim();
        const payload = { kind: val('rf-kind') };
        const amount = Number(val('rf-amount'));
        if (amount > 0) payload.amount = amount;
        const acc = val('rf-account');
        if (acc) payload.account_id = acc;
        const cat = val('rf-category');
        if (cat) payload.category_id = cat;
        const proj = val('rf-project');
        if (proj) payload.project_id = proj;
        const habit = val('rf-habit');
        if (habit) payload.habit_id = habit;
        const note = val('rf-note');
        if (note) payload.decision_note = note;
        finish(payload);
      }
      if (event.target === overlay) finish(null);
    });
    overlay.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') finish(null);
    });
  });
}

function discardModal(item) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    overlay.innerHTML = `
      <div class="modal modal-sm" role="dialog" aria-modal="true" aria-labelledby="dc-title">
        <header class="modal-head"><h3 id="dc-title">Descartar captura</h3>
          <button class="icon-btn" type="button" data-dc="cancel" aria-label="Cerrar">${icon('x')}</button></header>
        <div class="modal-body">
          <p class="modal-hint">«${esc(item.original_text)}»</p>
          <label class="modal-label" for="dc-note">Motivo</label>
          <textarea id="dc-note" class="capture-textarea" rows="2" maxlength="500" placeholder="Opcional"></textarea>
          <div class="modal-actions">
            <button class="btn btn-ghost" type="button" data-dc="cancel">Cancelar</button>
            <button class="btn btn-danger-soft" type="button" data-dc="ok">Descartar</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const finish = (v) => {
      overlay.remove();
      resolve(v);
    };
    overlay.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-dc]');
      if (btn) {
        if (btn.dataset.dc === 'cancel') return finish(undefined);
        return finish(overlay.querySelector('#dc-note').value.trim() || '');
      }
      if (event.target === overlay) finish(undefined);
    });
    overlay.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') finish(undefined);
    });
  });
}

async function ensureCategories(households) {
  const first = households && households[0];
  if (!first) return [];
  if (!elCategories.has(first.id)) {
    elCategories.set(first.id, await listCategoriesByHousehold(first.id));
  }
  return elCategories.get(first.id) || [];
}

/* ---------- Captura por chat (simulación de canal de mensajería, P4-02) ---------- */

export async function renderChat(el) {
  el.innerHTML = `
    <div class="page-head">
      <h1>Capturar por chat</h1>
      <p class="page-sub">Simula un canal de mensajería (P4-02): cada mensaje entra como captura pendiente a la bandeja, deduplicada y sin aplicar nada solo. La sugerencia de Faro es solo propuesta.</p>
    </div>
    ${skeleton(5)}`;
  try {
    const [items, projects, habits, households, accounts] = await Promise.all([
      listBandeja({ channel: 'telegram', limit: 300 }),
      listProjects(),
      listHabits(),
      listHouseholds().catch(() => []),
      listAccounts().catch(() => []),
    ]);
    const thread = (items || []).filter((i) => i.channel === 'telegram');

    el.innerHTML = `
      <div class="page-head">
        <h1>Capturar por chat</h1>
        <p class="page-sub">Simula un canal de mensajería (P4-02): cada mensaje entra como captura pendiente a la bandeja, deduplicada y sin aplicar nada solo. La sugerencia de Faro es solo propuesta.</p>
      </div>
      <section class="card">
        <div class="card-head"><h2>${icon('send')} Conversación</h2></div>
        <div class="card-body">
          <div class="chat-thread" id="chat-thread"></div>
          <div class="chat-compose">
            <textarea id="chat-input" class="capture-textarea" rows="2" maxlength="4000" placeholder="Escribe el mensaje como llegaría por Telegram/WhatsApp…"></textarea>
            <div class="modal-actions">
              <button class="btn btn-ghost" id="chat-clear" type="button">Limpiar</button>
              <button class="btn btn-primary" id="chat-send" type="button">${icon('send')} Simular envío</button>
            </div>
          </div>
        </div>
      </section>`;

    renderChatThread(el.querySelector('#chat-thread'), thread);
    bindChat(el, thread, { projects, habits, households, accounts });
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Capturar por chat</h1></div>${errorBlock(`No disponible: ${esc(err.message)}`)}`;
  }
}

function renderChatThread(host, thread) {
  if (!thread.length) {
    host.innerHTML = `<div class="card-body">${emptyBlock(
      'Aún no hay mensajes de chat. Envía uno abajo para simularlo.',
    )}</div>`;
    return;
  }
  host.innerHTML = `<div class="list" style="padding:0 18px">
    ${thread
      .map((item) => {
        const suggestion = suggestCapture(item.original_text);
        const resolved = item.status === 'applied' || item.status === 'discarded';
        return `
        <div class="chat-row" id="chat-item-${esc(item.id)}">
          <div class="chat-bubble chat-in">
            <div class="item-title">${esc(item.original_text)}</div>
            <div class="item-sub">
              ${statusBadge(item.status)}
              <span class="kind-chip kind-${esc(item.kind || 'unknown')}">${esc(KIND_LABELS[item.kind] || item.kind)}</span>
              <span>· ${esc(fmtTime(item.original_at))}</span>
              ${item.amount ? ` · <b>$${esc(Number(item.amount).toLocaleString('es-CL'))}</b>` : ''}
            </div>
          </div>
          <div class="chat-bubble chat-out ${resolved ? 'chat-out-resolved' : ''}">
            ${resolved ? `
              <div class="item-sub decision-trail">
                ${icon('check')} ${item.status === 'applied' ? `Aplicada${item.destination_module ? ` → ${esc(item.destination_module)}` : ''}` : 'Descartada'}
                ${item.decision_note ? ` · <span class="decision-note">«${esc(item.decision_note)}»</span>` : ''}
                ${item.resolved_at ? ` · ${esc(fmtDate(item.resolved_at))} ${esc(fmtTime(item.resolved_at))}` : ''}
              </div>` : `
              <div class="item-sub">${suggestion && suggestion.kind !== 'unknown'
                ? `Faro sugiere: <span class="kind-chip kind-${esc(suggestion.kind)}">${esc(KIND_LABELS[suggestion.kind] || suggestion.kind)}</span> · ${Math.round(suggestion.confidence * 100)}% de confianza.`
                : 'Faro aún no tiene una propuesta para esta captura.'}</div>
              <div class="item-actions" style="margin-top:6px">
                <button class="btn btn-primary btn-xs" data-chat-classify="${esc(item.id)}">${icon('check')} Clasificar</button>
                <button class="btn btn-danger-soft btn-xs" data-chat-discard="${esc(item.id)}">${icon('trash')} Descartar</button>
              </div>`}
          </div>
        </div>`;
      })
      .join('')}
  </div>`;
}

async function bindChat(el, thread, refs) {
  const input = el.querySelector('#chat-input');
  const send = el.querySelector('#chat-send');
  const threadHost = el.querySelector('#chat-thread');
  el.querySelector('#chat-clear').addEventListener('click', () => { input.value = ''; input.focus(); });

  async function reload() {
    const items = await listBandeja({ channel: 'telegram', limit: 300 });
    renderChatThread(threadHost, (items || []).filter((i) => i.channel === 'telegram'));
  }

  send.addEventListener('click', async () => {
    const text = input.value.trim();
    if (!text) {
      toast('Escribe el mensaje a simular', 'error');
      return;
    }
    try {
      const suggestion = suggestCapture(text);
      await receiveBandeja({
        channel: 'telegram',
        author: 'yo',
        source_ref: `tg:sim:${Date.now()}`,
        original_text: text,
        kind: suggestion.kind === 'unknown' ? undefined : suggestion.kind,
        amount: suggestion.amount || undefined,
      });
      toast('Mensaje recibido como captura pendiente', 'success');
      input.value = '';
      window.dispatchEvent(new CustomEvent('ff:bandeja-changed'));
      await reload();
    } catch (err) {
      toast(`No se pudo enviar: ${err.message}`, 'error');
    }
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) send.click();
  });

  threadHost.addEventListener('click', async (event) => {
    const classify = event.target.closest('[data-chat-classify]');
    const discard = event.target.closest('[data-chat-discard]');
    if (classify) {
      const items = await listBandeja({ channel: 'telegram', limit: 300 });
      const item = items.find((i) => i.id === classify.dataset.chatClassify);
      if (!item) return;
      const categories = await ensureCategories(refs.households);
      const decision = await classifyModal({ item, ...refs, categories });
      if (!decision) return;
      try {
        await applyBandeja(item.id, decision);
        toast('Captura aplicada', 'success');
      } catch (err) {
        toast(`No se pudo aplicar: ${err.message}`, 'error');
      }
      window.dispatchEvent(new CustomEvent('ff:bandeja-changed'));
      await reload();
      return;
    }
    if (discard) {
      const items = await listBandeja({ channel: 'telegram', limit: 300 });
      const item = items.find((i) => i.id === discard.dataset.chatDiscard);
      if (!item) return;
      const note = await discardModal(item);
      if (note === undefined) return;
      try {
        await discardBandeja(item.id, note ? { note } : {});
        toast('Captura descartada', 'success');
      } catch (err) {
        toast(`No se pudo descartar: ${err.message}`, 'error');
      }
      window.dispatchEvent(new CustomEvent('ff:bandeja-changed'));
      await reload();
    }
  });
}

function bindItems(el, refs) {
  if (el.dataset.bound) return;
  el.dataset.bound = '1';
  el.addEventListener('click', async (event) => {
    const selectBtn = event.target.closest('[data-bj-select]');
    if (selectBtn) {
      const base = window.location.hash.split('?')[0] || '';
      window.location.hash = `${base}?item=${encodeURIComponent(selectBtn.dataset.bjSelect)}`;
      setTimeout(() => renderBandeja(el), 240);
      return;
    }
    const backBtn = event.target.closest('[data-bj-back]');
    if (backBtn) {
      window.location.hash = window.location.hash.split('?')[0] || '#/bandeja';
      setTimeout(() => renderBandeja(el), 240);
      return;
    }
    const applyBtn = event.target.closest('[data-bj-apply]');
    if (applyBtn) {
      try {
        const items = await listBandeja({ limit: 500 });
        const item = items.find((i) => i.id === applyBtn.dataset.bjApply);
        if (!item) return;
        const categories = await ensureCategories(refs.households);
        const decision = await classifyModal({ item, ...refs, categories });
        if (!decision) return;
        await applyBandeja(item.id, decision);
        toast('Captura aplicada', 'success');
      } catch (err) {
        toast(`No se pudo aplicar: ${err.message}`, 'error');
      }
      window.dispatchEvent(new CustomEvent('ff:bandeja-changed'));
      setTimeout(() => renderBandeja(el), 250);
      return;
    }

    const retryBtn = event.target.closest('[data-bj-retry]');
    if (retryBtn) {
      const items = await listBandeja({ limit: 500 });
      const item = items.find((i) => i.id === retryBtn.dataset.bjRetry);
      if (!item) return;
      const categories = await ensureCategories(refs.households);
      const decision = await classifyModal({ item, ...refs, categories });
      if (!decision) return;
      try {
        await applyBandeja(item.id, decision);
        toast('Reintentado con éxito', 'success');
      } catch (err) {
        toast(`Falló: ${err.message}`, 'error');
      }
      setTimeout(() => renderBandeja(el), 250);
      return;
    }

    const refineBtn = event.target.closest('[data-bj-refine]');
    if (refineBtn) {
      const items = await listBandeja({ limit: 500 });
      const item = items.find((i) => i.id === refineBtn.dataset.bjRefine);
      if (!item) return;
      const categories = await ensureCategories(refs.households);
      const payload = await refineModal(item, refs.projects, refs.habits, refs.accounts, categories);
      if (!payload) return;
      try {
        await refineBandeja(item.id, payload);
        toast('Captura actualizada', 'success');
      } catch (err) {
        toast(`No se pudo actualizar: ${err.message}`, 'error');
      }
      setTimeout(() => renderBandeja(el), 250);
      return;
    }

    const discardBtn = event.target.closest('[data-bj-discard]');
    if (discardBtn) {
      const items = await listBandeja({ limit: 500 });
      const item = items.find((i) => i.id === discardBtn.dataset.bjDiscard);
      if (!item) return;
      const note = await discardModal(item);
      if (note === undefined) return;
      try {
        await discardBandeja(item.id, note ? { note } : {});
        toast('Captura descartada', 'success');
      } catch (err) {
        toast(`No se pudo descartar: ${err.message}`, 'error');
      }
      setTimeout(() => renderBandeja(el), 250);
      return;
    }
  });
}