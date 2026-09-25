'use strict';

import {
  api,
  nameMaps,
  listDeliverables,
  listBandeja,
  dashboard,
  upcomingPayments,
} from './api.js';
import {
  esc,
  fmtDate,
  fmtDayMonth,
  fmtTime,
  todayISO,
  money,
  icon,
  badge,
  toast,
  skeleton,
  emptyBlock,
  errorBlock,
  lighthouseArt,
  progressBar,
  promptCompletionNote,
  kpiTile,
} from './ui.js';

const WEEKDAYS_ES = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
const MONTHS_ES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
];

function esDate(d) {
  return `${WEEKDAYS_ES[d.getDay()]}, ${d.getDate()} de ${MONTHS_ES[d.getMonth()]}`;
}

function greetShort() {
  const first = greetName();
  const h = new Date().getHours();
  const period = h < 6 || h >= 20 ? 'Buenas noches' : h < 12 ? 'Buenos días' : 'Buenas tardes';
  return first ? `${period}, ${first}` : period;
}

function greetName() {
  try {
    const raw = localStorage.getItem('ff.user');
    return raw && raw.trim() ? raw.trim().split(/\s+/)[0] : null;
  } catch (_) {
    return null;
  }
}

function kindChip(kind, amount = null) {
  const labels = {
    task: 'Tarea',
    expense: 'Gasto',
    income: 'Ingreso',
    habit: 'Hábito',
    note: 'Nota',
    reference: 'Referencia',
    unknown: 'Por clasificar',
  };
  const label = labels[kind] || kind || 'unknown';
  const amountHtml = amount ? ` ${money(amount, 'CLP')}` : '';
  return `<span class="kind-chip kind-${esc(kind || 'unknown')}">${esc(label)}${amountHtml}</span>`;
}

function cardHead(iconName, title, badgeText, actionHref, actionLabel) {
  return `
    <div class="card-head">
      <h2>${icon(iconName)} ${esc(title)}</h2>
      ${badgeText ? `<span class="card-meta"><span class="card-badge">${esc(badgeText)}</span></span>` : ''}
      ${actionHref ? `<a class="card-action" href="${actionHref}">${esc(actionLabel || 'Ver todo')}</a>` : ''}
    </div>`;
}

function listOrEmpty(items, renderItem, emptyMessage, actionHref, actionLabel) {
  if (!items.length) {
    return emptyBlock(emptyMessage, actionHref ? `<a class="btn btn-soft btn-sm" href="${actionHref}">${esc(actionLabel || 'Ver todo')}</a>` : '');
  }
  return `<div class="list">${items.map(renderItem).join('')}</div>`;
}

export async function renderMiDia(el) {
  el.innerHTML = `
    <div class="hero md-hero">
      <div class="hero-body">
        <div class="hero-date">${esc(esDate(new Date()))}</div>
        <h1>${esc(greetShort())}</h1>
        <p>${esc(dailySubtitle())}</p>
      </div>
      <div class="hero-side">
        <a class="btn btn-primary btn-lg" href="#/mi-dia/preparar">${icon('sparkles')} Preparar mi día</a>
      </div>
      <div class="hero-art">${lighthouseArt()}</div>
    </div>
    ${skeleton(9)}`;

  try {
    const [home, maps, brief, deliverables, captures] = await Promise.all([
      api('/api/v1/home'),
      nameMaps(),
      api('/api/v1/briefs/morning').catch(() => null),
      listDeliverables(),
      listBandeja({ limit: 30 }).catch(() => []),
    ]);
    const today = home.date || todayISO();
    const fin = home.finance || { available: false };
    const habits = home.habits || [];
    const projects = maps.project || {};

    /* --- Tarjetas ------------------------------------------------------------------ */

    /* 1 · Prioridades: foco real (top 3 ejecutables) — no vencidas, no patrimonio */
    const focus = (brief && brief.focus_tasks) || [];
    const prioridades = `
      <section class="card">
        ${cardHead('flag', 'Tus 3 prioridades', `${focus.length} en foco`, '#/tareas', 'Ver tareas')}
        <div class="card-body">
          ${focus.length
            ? `<div class="p-list">${focus
                .slice(0, 3)
                .map(
                  (t) => `
                  <div class="prio-row">
                    <button class="prio-check" type="button" data-prio="${esc(t.id)}" aria-label="Marcar como completada">${icon('check')}</button>
                    <div class="prio-main">
                      <div class="prio-title">${esc(t.title)}</div>
                      <span class="tag-chip">${esc(projects[t.project_id] || 'Sin proyecto')}</span>
                    </div>
                  </div>`,
                )
                .join('')}</div>`
            : emptyBlock('Sin prioridades en foco ahora mismo.', '<a class="btn btn-soft btn-sm" href="#/tareas">Ir a tareas</a>')}
        </div>
      </section>`;

    /* 2 · Agenda de hoy */
    const agenda = `
      <section class="card">
        ${cardHead('calendar', 'Agenda de hoy', `${home.meetings.count} ${home.meetings.count === 1 ? 'reunión' : 'reuniones'}`, '#/reuniones', 'Agenda')}
        <div class="card-body">
          ${listOrEmpty(
            home.meetings.items,
            (m) => `
              <a class="item" href="#/reuniones/${esc(m.id)}">
                <div class="agenda-time">${esc(fmtTime(m.starts_at))}</div>
                <div class="item-main">
                  <div class="item-title">${esc(m.title)}</div>
                  <div class="item-sub">${m.project_id ? esc(projects[m.project_id] || 'reunión') : 'reunión'}</div>
                </div>
                <div class="item-side">${icon('arrow')}</div>
              </a>`,
            'Sin reuniones programadas para hoy.',
            '#/reuniones',
            'Ver reuniones',
          )}
        </div>
      </section>`;

    /* 3 · Proyectos y entregables (progreso real) */
    const deliverablesByProject = (deliverables || []).reduce((acc, d) => {
      (acc[d.project_id] ||= { total: 0, accepted: 0 });
      acc[d.project_id].total += 1;
      if (d.status === 'accepted') acc[d.project_id].accepted += 1;
      return acc;
    }, {});
    const projectRows = Object.keys(deliverablesByProject)
      .map((pid) => ({ pid, ...deliverablesByProject[pid] }))
      .filter((p) => projects[p.pid])
      .sort((a, b) => b.total - a.total)
      .slice(0, 3);
    const proyectos = `
      <section class="card">
        ${cardHead('folder', 'Proyectos y entregables', `${projectRows.length} con avance`, '#/proyectos', 'Proyectos')}
        <div class="card-body">
          ${projectRows.length
            ? `<div class="p-list">${projectRows
                .map(
                  (p) => `
                  <a class="item" href="#/proyectos/${esc(p.pid)}">
                    <div class="item-main">
                      <div class="item-title">${esc(projects[p.pid])}</div>
                      <div class="item-sub">${esc(p.accepted)}/${esc(p.total)} entregables aceptados</div>
                    </div>
                    <div class="item-side proj-progress">${progressBar((p.accepted / p.total) * 100)}${icon('arrow')}</div>
                  </a>`,
                )
                .join('')}</div>`
            : emptyBlock('Sin entregables registrados aún.', '<a class="btn btn-soft btn-sm" href="#/proyectos">Ver proyectos</a>')}
        </div>
      </section>`;

    /* 4 · Tu mes financiero (ingresos, egresos y balance del período) */
    const finanzas = await finanzasCard(fin);

    /* 5 · Hábitos de hoy */
    const dueHabits = habits.filter((h) => h.due_today);
    const doneHabits = habits.filter((h) => h.completed_today);
    const habitsBadge = habits.length
      ? `${doneHabits.length}/${dueHabits.length || habits.length} cumplidos`
      : '';
    const habitos = `
      <section class="card">
        ${cardHead('target', 'Hábitos de hoy', habitsBadge, '#/habitos', 'Hábitos')}
        <div class="card-body">
          ${habits.length
            ? `<div class="p-list">${habits
                .map(
                  (h) => `
                  <div class="md-habit-row">
                    <button class="md-habit-check ${h.completed_today ? 'is-done' : ''}" type="button" data-habit-toggle="${esc(h.id)}" data-state="${h.completed_today ? 'done' : 'open'}" aria-label="${h.completed_today ? 'Quitar cumplimiento' : 'Marcar como cumplido'}">${icon('check')}</button>
                    <div class="md-habit-main">
                      <div class="md-habit-name">${esc(h.name)}</div>
                      <div class="md-habit-sub">${h.due_today ? 'para hoy' : 'hoy no corresponde'} · racha ${esc(h.current_streak)} días</div>
                    </div>
                    <span class="md-habit-status ${h.completed_today ? 'is-done' : h.due_today ? 'is-pending' : 'is-idle'}">${h.completed_today ? 'Cumplido' : h.due_today ? 'Pendiente' : 'Hoy no toca'}</span>
                  </div>`,
                )
                .join('')}</div>`
            : emptyBlock('Aún no tienes hábitos activos.', '<a class="btn btn-soft btn-sm" href="#/habitos">Crear hábito</a>')}
        </div>
      </section>`;

    /* 6 · Bandeja de capturas */
    const pendientes = (captures || []).filter((r) =>
      ['received', 'reviewing', 'confirmed'].includes(r.status),
    );
    const bandeja = `
      <section class="card">
        ${cardHead('send', 'Bandeja de capturas', `${home.bandeja.count} ${home.bandeja.count === 1 ? 'pendiente' : 'pendientes'}`, '#/bandeja', 'Revisar')}
        <div class="card-body">
          ${listOrEmpty(
            pendientes.slice(0, 3),
            (r) => `
              <a class="item" href="#/bandeja">
                <div class="item-main">
                  <div class="item-title">${esc(r.original_text || r.title || 'Captura')}</div>
                  <div class="item-sub">${esc(fmtDate(r.original_at))}</div>
                </div>
                <div class="item-side">${kindChip(r.kind, r.amount)}${icon('arrow')}</div>
              </a>`,
            'Bandeja al día, sin pendientes.',
            '#/bandeja',
            'Ir a la bandeja',
          )}
        </div>
      </section>`;

    /* --- Pie: captura rápida -------------------------------------------------------- */
    const quickCapture = `
      <section class="card quick-capture-card">
        <div class="quick-capture">
          <span class="quick-caption">${icon('send')} Capturar como</span>
          <div class="quick-cap-group">
            <button class="btn btn-soft" type="button" data-capture-open="1">${icon('check')} Tarea</button>
            <button class="btn btn-soft" type="button" data-capture-open="1">${icon('coin')} Gasto</button>
            <button class="btn btn-soft" type="button" data-capture-open="1">${icon('target')} Hábito</button>
            <button class="btn btn-ghost quick-capture-input" type="button" data-capture-open="1">${icon('plus')} Captura rápida…</button>
            <a class="btn btn-ghost" href="#/mi-dia/cierre">${icon('moon')} Cerrar mi día</a>
          </div>
        </div>
      </section>`;

    el.innerHTML = `
      <div class="hero md-hero">
        <div class="hero-body">
          <div class="hero-date">${esc(esDate(new Date()))}</div>
          <h1>${esc(greetShort())}</h1>
          <p>${esc(dailySubtitle())}</p>
        </div>
        <div class="hero-side">
          <a class="btn btn-primary btn-lg" href="#/mi-dia/preparar">${icon('sparkles')} Preparar mi día</a>
        </div>
        <div class="hero-art">${lighthouseArt()}</div>
      </div>
      <div class="dash-grid">
        ${prioridades}
        ${agenda}
        ${proyectos}
        ${finanzas}
        ${habitos}
        ${bandeja}
      </div>
      ${quickCapture}`;

    if (!el.dataset.bound) {
      el.dataset.bound = '1';
      el.addEventListener('click', async (event) => {
        const habitBtn = event.target.closest('[data-habit-toggle]');
        if (habitBtn) {
          const habitId = habitBtn.dataset.habitToggle;
          const done = habitBtn.dataset.state === 'done';
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
          return;
        }
        const prioBtn = event.target.closest('[data-prio]');
        if (prioBtn) {
          const taskId = prioBtn.dataset.prio;
          const note = await promptCompletionNote('Completar prioridad');
          if (note === null) return;
          try {
            await api(`/api/v1/tasks/${encodeURIComponent(taskId)}/complete`, {
              method: 'POST',
              body: JSON.stringify({ completion_note: note }),
            });
            toast('Prioridad completada', 'success');
          } catch (err) {
            toast(`No se pudo completar: ${err.message}`, 'error');
          }
          renderMiDia(el);
        }
      });
    }
  } catch (err) {
    el.innerHTML = `<div class="hero md-hero"><div class="hero-body"><h1>Mi Día</h1></div></div>${errorBlock(`Mi Día no disponible: ${esc(err.message)}`)}`;
  }
}

function dailySubtitle() {
  const h = new Date().getHours();
  if (h < 6) return 'Un vistazo a lo importante antes de descansar.';
  if (h < 12) return 'Un vistazo y arranca el día con lo importante.';
  if (h < 20) return 'Mantén el foco: todo lo importante está aquí.';
  return 'Cierra el día con honestidad y descansa.';
}

async function finanzasCard(fin) {
  const head = cardHead('coin', 'Tu mes financiero', fin.available && fin.household_name ? esc(fin.household_name) : '', '#/finanzas', 'Ver finanzas');
  if (!fin.available) {
    return `
      <section class="card">
        ${head}
        <div class="card-body">${emptyBlock('Configura tu hogar financiero para ver el resumen del mes.', '<a class="btn btn-soft btn-sm" href="#/finanzas">Configurar</a>')}</div>
      </section>`;
  }
  if (!fin.household_id) {
    return `
      <section class="card">
        ${head}
        <div class="card-body">${emptyBlock('Resumen financiero no disponible todavía.')}</div>
      </section>`;
  }
  const now = new Date();
  const dash = await dashboard(fin.household_id, now.getFullYear(), now.getMonth() + 1).catch(() => null);
  if (!dash) {
    return `
      <section class="card">
        ${head}
        <div class="card-body">${emptyBlock('Resumen del mes no disponible todavía.')}</div>
      </section>`;
  }
  const upcoming = await upcomingPayments(fin.household_id, 30).catch(() => null);
  const payments = [
    ...((upcoming && upcoming.pending_installments) || []).map((p) => ({
      name: 'Cuota de deuda',
      amount: p.total_amount,
      due: p.due_date,
    })),
    ...((upcoming && upcoming.recurring_minimums) || []).map((p) => ({
      name: p.debt_name,
      amount: p.minimum_payment,
      due: p.due_date,
    })),
  ].sort((a, b) => String(a.due).localeCompare(String(b.due)));
  const next = payments[0];
  return `
    <section class="card">
      ${head}
      <div class="card-body">
        <div class="fin-month-grid">
          <div class="fin-month-cell">
            <span class="kpi-label">Ingresos</span>
            <b class="fin-month-val pos">${money(dash.income, 'CLP')}</b>
          </div>
          <div class="fin-month-cell">
            <span class="kpi-label">Egresos</span>
            <b class="fin-month-val neg">${money(dash.expenses, 'CLP')}</b>
          </div>
          <div class="fin-month-cell">
            <span class="kpi-label">Balance</span>
            <b class="fin-month-val ${dash.balance >= 0 ? 'pos' : 'neg'}">${money(dash.balance, 'CLP')}</b>
          </div>
        </div>
        <div class="item">
          <div class="item-main">
            <div class="item-title">${next ? esc(next.name) : 'Sin pagos próximos'}</div>
            <div class="item-sub">${next ? esc(fmtDate(next.due)) : 'No hay pagos en los próximos 30 días.'}</div>
          </div>
          <div class="item-side">${next ? `<b class="fin-month-val">${money(next.amount, 'CLP')}</b>` : ''}</div>
        </div>
        <div class="fin-links">
          <a href="#/finanzas/ingresos">Ingresos</a>
          <a href="#/finanzas/egresos">Egresos</a>
        </div>
      </div>
    </section>`;
}

export async function renderPreparar(el) {
  el.innerHTML = `<div class="page-head">
      <div class="page-greeting"><h1>Preparar mi día</h1><span class="date-line">· ${esc(fmtDate(new Date().toISOString()))}</span></div>
      <p class="page-sub">Recuento de la mañana: reuniones, prioridades y lo que necesita atención.</p>
    </div>
    ${skeleton(4)}`;
  try {
    const brief = await api('/api/v1/briefs/morning');
    const counts = brief.counts || {};
    const chips = `<div class="kpi-row four">
        ${kpiTile({ icon: 'calendar', tone: 'accent', label: 'Reuniones hoy', value: esc(counts.meetings ?? '—'), note: 'Agenda del día' })}
        ${kpiTile({ icon: 'clock', tone: 'danger', label: 'Tareas vencidas', value: esc(counts.overdue_tasks ?? '—'), note: 'Requieren atención' })}
        ${kpiTile({ icon: 'target', tone: 'primary', label: 'En foco', value: esc(counts.focus_tasks ?? '—'), note: 'Prioridades de hoy' })}
        ${kpiTile({ icon: 'alert', tone: 'warm', label: 'Proyectos en riesgo', value: esc(counts.at_risk_projects ?? '—'), note: 'Necesitan seguimiento' })}
      </div>`;

    const meetings = (brief.meetings || [])
      .map(
        (m) => `
        <li class="item">
          <div class="item-main"><div class="item-title">${esc(m.title)}</div></div>
          <div class="item-side"><span class="agenda-time">${esc(fmtTime(m.starts_at))}</span></div>
        </li>`,
      )
      .join('');

    const focus = (brief.focus_tasks || [])
      .map(
        (t) => `
        <li class="item">
          <div class="item-main"><div class="item-title">${esc(t.title)}</div></div>
          <div class="item-side"><span class="item-sub">vence ${esc(fmtDate(t.due_at))}</span></div>
        </li>`,
      )
      .join('');

    const atRisk = (brief.at_risk_projects || [])
      .map(
        (p) => `
        <li class="item">
          <a class="item-main" href="#/proyectos/${esc(p.id)}"><div class="item-title">${esc(p.name)}</div></a>
          <div class="item-side">${badge(p.health)}</div>
        </li>`,
      )
      .join('');

    el.innerHTML = `
      <div class="page-head">
        <div class="page-greeting"><h1>Preparar mi día</h1><span class="date-line">· ${esc(fmtDayMonth(new Date()))}</span></div>
        <p class="page-sub">Recuento de la mañana: reuniones, prioridades y lo que necesita atención.</p>
      </div>
      ${chips}
      <div class="split-60-40">
        <div class="split-main">
          <section class="card">
            <div class="card-head"><h2>${icon('calendar')} Reuniones de hoy</h2><a class="card-action" href="#/reuniones">Agenda</a></div>
            <div class="card-body">${meetings ? `<ul class="p-list">${meetings}</ul>` : emptyBlock('Sin reuniones programadas hoy.')}</div>
          </section>
          <section class="card">
            <div class="card-head"><h2>${icon('check')} Tareas en foco</h2><a class="card-action" href="#/tareas">Tareas</a></div>
            <div class="card-body">${focus ? `<ul class="p-list">${focus}</ul>` : emptyBlock('Nada pendiente en foco hoy.')}</div>
          </section>
        </div>
        <div class="split-side">
          <section class="card">
            <div class="card-head"><h2>${icon('warn')} Proyectos en riesgo</h2><a class="card-action" href="#/proyectos">Proyectos</a></div>
            <div class="card-body">${atRisk ? `<ul class="p-list">${atRisk}</ul>` : emptyBlock('Ningún proyecto en riesgo.')}</div>
          </section>
        </div>
      </div>`;
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Preparar mi día</h1></div>${errorBlock(`No disponible: ${esc(err.message)}`)}`;
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