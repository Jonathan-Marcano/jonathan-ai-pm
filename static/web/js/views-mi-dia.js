'use strict';

import { api } from './api.js';
import {
  esc,
  fmtDate,
  fmtDayMonth,
  fmtTime,
  todayISO,
  money,
  icon,
  badge,
  prio,
  toast,
  skeleton,
  emptyBlock,
  errorBlock,
} from './ui.js';

function kpi(value, label, iconName, href, tone = '') {
  return `<a class="kpi" href="#${href}">
    <span class="kpi-icon ${tone}">${icon(iconName)}</span>
    <span class="kpi-meta"><span class="kpi-value">${value}</span><br /><span class="kpi-label">${esc(label)}</span></span>
  </a>`;
}

function sectionList(items, renderItem, emptyMessage, actionHref, actionLabel) {
  if (!items.length) {
    return emptyBlock(emptyMessage, actionHref ? `<a class="btn btn-soft btn-sm" href="#${actionHref}">${esc(actionLabel || 'Ver todas')}</a>` : '');
  }
  const rows = items.map(renderItem).join('');
  return `<div class="list">${rows}</div>`;
}

function kindChip(kind) {
  const labels = {
    task: 'Tarea',
    expense: 'Gasto',
    income: 'Ingreso',
    habit: 'Hábito',
    note: 'Nota',
    reference: 'Referencia',
    unknown: 'Por clasificar',
  };
  return `<span class="kind-chip kind-${esc(kind || 'unknown')}">${esc(labels[kind] || kind || 'unknown')}</span>`;
}

export async function renderMiDia(el) {
  el.innerHTML = `<div class="page-head">
      <div class="page-greeting"><h1>Mi Día</h1><span class="date-line">· ${esc(fmtDayMonth(new Date()))}</span></div>
      <p class="page-sub">Tu día en un vistazo: trabajo, finanzas, hábitos y bandeja.</p>
    </div>
    ${skeleton(8)}`;
  try {
    const home = await api('/api/v1/home');
    const today = home.date || todayISO();
    const fin = home.finance || { available: false };

    const habitsDone = (home.habits || []).filter((h) => h.completed_today).length;
    const habitsTotal = (home.habits || []).filter((h) => h.due_today).length;

    const kpiRow = `
      <div class="kpi-row">
        ${kpi(esc(home.work.count), 'tareas vencidas', 'flag', '/tareas?status=overdue', 'tone-danger')}
        ${kpi(esc(home.meetings.count), 'reuniones hoy', 'calendar', '/reuniones', 'tone-primary')}
        ${kpi(esc(home.projects.count), 'proyectos en riesgo', 'warn', '/proyectos', 'tone-warm')}
        ${kpi(esc(home.bandeja.count), 'capturas pendientes', 'send', '/bandeja', 'tone-primary')}
        ${kpi(habitsTotal ? `${habitsDone}/${habitsTotal}` : '—', 'hábitos con objetivo hoy', 'target', '/habitos', 'tone-accent')}
        ${fin.available
          ? kpi(money(fin.total_balance, 'CLP'), 'patrimonio financiero', 'sparkles', '/finanzas', 'tone-accent')
          : kpi('—', 'finanzas sin configurar', 'info', '/finanzas', 'tone-primary')}
      </div>`;

    const quick = `
      <div class="quick-actions">
        <button class="btn btn-soft btn-sm" data-capture-open="1">${icon('plus')} Capturar</button>
        <a class="btn btn-ghost btn-sm" href="#/mi-dia/cierre">${icon('clock')} Cierre del día</a>
      </div>`;

    const workCard = `
      <section class="card">
        <div class="card-head"><h2>${icon('flag')} Trabajo</h2><a class="card-action" href="#/tareas">Ver todas</a></div>
        <div class="card-body">
          ${sectionList(
            home.work.items,
            (t) => `
              <div class="item">
                <div class="item-main">
                  <div class="item-title">${esc(t.title)}</div>
                  <div class="item-sub">${badge(t.status)} · vence ${esc(fmtDate(t.due_at))}</div>
                </div>
                <div class="item-side"><a class="btn btn-soft btn-xs" href="#/tareas?status=overdue">Revisar${icon('arrow')}</a></div>
              </div>`,
            'Sin tareas vencidas hoy.',
            '/tareas',
            'Ver tareas',
          )}
        </div>
      </section>`;

    const meetingsCard = `
      <section class="card">
        <div class="card-head"><h2>${icon('calendar')} Reuniones de hoy</h2><a class="card-action" href="#/reuniones">Agenda</a></div>
        <div class="card-body">
          ${sectionList(
            home.meetings.items,
            (m) => `
              <a class="agenda-row" href="#/reuniones/${esc(m.id)}">
                <span class="agenda-time">${esc(fmtTime(m.starts_at))}</span>
                <span class="item-title">${esc(m.title)}</span>
                <span class="item-sub">${m.project_id ? esc(m.project_id) : ''}</span>
              </a>`,
            'Sin reuniones programadas para hoy.',
            '/reuniones',
            'Ver reuniones',
          )}
        </div>
      </section>`;

    const projectsCard = `
      <section class="card">
        <div class="card-head"><h2>${icon('folder')} Proyectos en riesgo</h2><a class="card-action" href="#/proyectos">Proyectos</a></div>
        <div class="card-body">
          ${sectionList(
            home.projects.items,
            (p) => `
              <a class="item" href="#/proyectos/${esc(p.id)}">
                <div class="item-main">
                  <div class="item-title">${esc(p.title)}</div>
                  <div class="item-sub">${badge(p.health)}</div>
                </div>
                <span class="item-side arrow">${icon('arrow')}</span>
              </a>`,
            'Ningún proyecto en riesgo.',
            '/proyectos',
            'Ver proyectos',
          )}
        </div>
      </section>`;

    const bandejaCard = `
      <section class="card">
        <div class="card-head"><h2>${icon('send')} Bandeja</h2><a class="card-action" href="#/bandeja">Revisar</a></div>
        <div class="card-body">
          ${sectionList(
            home.bandeja.items,
            (r) => `
              <div class="item">
                <div class="item-main">
                  <div class="item-title">${esc(r.title)}</div>
                  <div class="item-sub">${badge(r.status)} · ${esc(fmtDate(r.original_at))}</div>
                </div>
                <div class="item-side">${kindChip(r.kind)}</div>
              </div>`,
            'Bandeja al día, sin pendientes.',
            '/bandeja',
            'Ir a la bandeja',
          )}
        </div>
      </section>`;

    const habitsCard = `
      <section class="card">
        <div class="card-head"><h2>${icon('target')} Hábitos de hoy</h2><a class="card-action" href="#/habitos">Hábitos</a></div>
        <div class="card-body">
          ${(home.habits && home.habits.length)
            ? `<div class="p-list">${home.habits
                .map(
                  (h) => `
                  <li class="item">
                    <div class="item-main">
                      <div class="item-title">${esc(h.name)}</div>
                      <div class="item-sub">${h.due_today ? '' : 'hoy no corresponde · '}racha ${esc(h.current_streak)} días${h.goal_type === 'quantity' ? ' · cantidad' : ''}</div>
                    </div>
                    <div class="item-side">
                      ${h.goal_type === 'quantity'
                        ? '<span class="btn btn-soft btn-xs">Cantidad</span>'
                        : `<button class="btn btn-xs ${h.completed_today ? 'btn-danger-soft' : 'btn-success-soft'}" data-habit-toggle="${esc(h.id)}" data-state="${h.completed_today ? 'done' : 'open'}">
                            ${icon(h.completed_today ? 'x' : 'check')} ${h.completed_today ? 'Quitar' : 'Cumplido hoy'}
                          </button>`}
                      <a class="btn btn-ghost btn-xs" href="#/habitos/${esc(h.id)}">${icon('arrow')}</a>
                    </div>
                  </li>`,
                )
                .join('')}</div>`
            : emptyBlock('Aún no tienes hábitos activos.', '<a class="btn btn-soft btn-sm" href="#/habitos">Crear hábito</a>')}
        </div>
      </section>`;

    const financeCard = `
      <section class="card">
        <div class="card-head"><h2>${icon('sparkles')} Finanzas</h2><a class="card-action" href="#/finanzas">Resumen</a></div>
        <div class="card-body">
          ${fin.available
            ? `<div class="p-list">
                <li class="item">
                  <div class="item-main"><b>Patrimonio</b></div>
                  <div class="item-side"><b class="fin-kpi-value pos">${money(fin.total_balance, 'CLP')}</b></div>
                </li>
                <li class="item">
                  <div class="item-main">Deudas activas</div>
                  <div class="item-side">${esc(fin.active_debts)}</div>
                </li>
                <li class="item">
                  <div class="item-main">Pagos próximos (30 días)</div>
                  <div class="item-side">${esc(fin.upcoming_payments)}</div>
                </li>
              </div>`
            : emptyBlock('Configura tu hogar financiero para ver el resumen.', '<a class="btn btn-soft btn-sm" href="#/finanzas">Configurar</a>')}
        </div>
      </section>`;

    el.innerHTML = `
      <div class="page-head">
        <div class="page-greeting"><h1>Mi Día</h1><span class="date-line">· ${esc(fmtDayMonth(new Date()))}</span></div>
        <p class="page-sub">Tu día en un vistazo: trabajo, finanzas, hábitos y bandeja.</p>
        ${quick}
      </div>
      ${kpiRow}
      <div class="masonry">
        <div class="stack">
          ${workCard}
        </div>
        <div class="stack">
          ${habitsCard}
          ${meetingsCard}
        </div>
        <div class="stack">
          ${bandejaCard}
          ${financeCard}
        </div>
        <div class="stack">
          ${projectsCard}
        </div>
      </div>`;

    if (!el.dataset.bound) {
      el.dataset.bound = '1';
      el.addEventListener('click', async (event) => {
        const btn = event.target.closest('[data-habit-toggle]');
        if (!btn) return;
        const habitId = btn.dataset.habitToggle;
        const done = btn.dataset.state === 'done';
        try {
          if (done) {
            await api(`/api/v1/habits/${encodeURIComponent(habitId)}/unmark`, {
              method: 'POST',
              body: JSON.stringify({ local_date: today }),
            });
            toast('Cumplimiento desmarcado', 'success');
          } else {
            await api(`/api/v1/habits/${encodeURIComponent(habitId)}/mark`, {
              method: 'POST',
              body: JSON.stringify({ local_date: today, quantity: 1 }),
            });
            toast('Hábito cumplido hoy', 'success');
          }
        } catch (err) {
          toast(`No se pudo actualizar: ${err.message}`, 'error');
        }
        renderMiDia(el);
      });
    }
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Mi Día</h1></div>${errorBlock(`Mi Día no disponible: ${esc(err.message)}`)}`;
  }
}

export async function renderCierre(el) {
  el.innerHTML = `
    <div class="page-head"><h1>Cierre del día</h1><p class="page-sub">Recuento honesto de lo completado y lo pendiente.</p></div>
    ${skeleton(4)}`;
  try {
    const close = await api('/api/v1/briefs/evening');
    const chipsHtml = close.counts
      ? `
      <div class="page-grid three">
        <div class="card"><div class="card-body"><span class="kpi-label">Completadas hoy</span><div class="kpi-value">${esc(close.counts.completed_tasks || 0)}</div></div></div>
        <div class="card"><div class="card-body"><span class="kpi-label">Pendientes</span><div class="kpi-value">${esc(close.counts.unfinished_tasks || 0)}</div></div></div>
        <div class="card"><div class="card-body"><span class="kpi-label">Sin clasificar</span><div class="kpi-value">${esc(close.counts.untriaged_captures || 0)}</div></div></div>
      </div>`
      : '';
    el.innerHTML = `
      <div class="page-head"><h1>Cierre del día</h1><p class="page-sub">${esc(fmtDayMonth(new Date()))}</p></div>
      ${chipsHtml}
      <section class="card" style="margin-top:16px">
        <div class="card-head"><h2>${icon('check')} Actividad</h2></div>
        <div class="card-body">${closeActivity(close)}</div>
      </section>`;
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Cierre del día</h1></div>${errorBlock(`No disponible: ${esc(err.message)}`)}`;
  }
}

function closeActivity(close) {
  const parts = [];
  const c = close.counts || {};
  if (c.completed_tasks) {
    parts.push({ label: `${c.completed_tasks} tareas completadas` });
  }
  if ((close.completed_tasks || []).length) {
    for (const t of close.completed_tasks.slice(0, 8)) {
      parts.push({ label: `— ${t.title}` });
    }
  }
  if (c.unfinished_tasks) parts.push({ label: `${c.unfinished_tasks} tareas sin terminar` });
  if (c.open_action_items) parts.push({ label: `${c.open_action_items} acciones abiertas` });
  if (c.untriaged_captures) parts.push({ label: `${c.untriaged_captures} capturas sin organizar` });
  if (!parts.length) return emptyBlock('Aún no hay actividad registrada para hoy.');
  return `<div class="p-list">${parts
    .map((p) => `<li class="activity"><span class="activity-kind">${icon('check')}</span><div class="activity-body">${esc(p.label)}</div></li>`)
    .join('')}</div>`;
}