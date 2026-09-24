'use strict';

import {
  api,
  listWorkspaces,
  listClients,
  listProjects,
  listDeliverables,
  listMeetings,
  listTasks,
  nameMaps,
  invalidate,
  forgetMaps,
} from './api.js';
import {
  esc,
  fmtDate,
  fmtDayMonth,
  fmtFullDate,
  fmtTime,
  todayISO,
  addDaysISO,
  timeAgo,
  icon,
  badge,
  prio,
  progressBar,
  toast,
  skeleton,
  emptyBlock,
  errorBlock,
  setPageTitle,
  promptDate,
  promptCompletionNote,
  openForm,
  promptTriage,
  genEntityId,
  humanStatus,
} from './ui.js';

const plural = (n, singular, pluralForm) => `${n} ${n === 1 ? singular : pluralForm}`;

function taskContext(task, maps) {
  const chunks = [];
  if (task.project_id) chunks.push(maps.project[task.project_id] || task.project_id);
  if (task.deliverable_id) chunks.push(maps.deliverable[task.deliverable_id] || task.deliverable_id);
  return chunks.join(' · ');
}

function projectDescription(project, maps) {
  const client = maps.client[project.client_id];
  const ws = maps.workspace[maps.clientWorkspace[project.client_id]];
  const parts = [];
  if (client) parts.push(client);
  if (ws) parts.push(ws);
  return parts.join(' · ');
}

/* ============================================================
   INICIO — MISSION CONTROL  (FASE UI-2)
   ============================================================ */

async function homeData() {
  const [maps, brief, projects, tasksDue, captures, audit, progress] = await Promise.all([
    nameMaps(),
    api('/api/v1/briefs/morning'),
    listProjects(),
    listTasks(`due_from=${todayISO()}&due_to=${todayISO()}`),
    api('/api/v1/captures?limit=100&capture_status=inbox'),
    api('/api/v1/audit-events?limit=8'),
    api('/api/v1/reports/progress'),
  ]);
  const [unmatched, toReview] = await Promise.all([
    api('/api/v1/integrations/meetings/unmatched'),
    api('/api/v1/integrations/meetings/completed'),
  ]);
  return { maps, brief, projects, tasksDue, captures, audit, progress, unmatched, toReview };
}

function kpiCard(value, label, iconName, href, tone = '') {
  return `<a class="kpi" href="${href}">
    <span class="kpi-icon ${tone}">${icon(iconName)}</span>
    <span class="kpi-meta"><span class="kpi-value">${value}</span><br /><span class="kpi-label">${esc(label)}</span></span>
  </a>`;
}

function briefSynthesis(b, maps) {
  const counts = b.counts;
  const focus = b.focus_tasks[0];
  const hasFocus = Boolean(focus);
  const sentences = [];
  const topics = [];
  if (counts.overdue_tasks) topics.push(`${plural(counts.overdue_tasks, 'tarea vencida', 'tareas vencidas')}`);
  if (counts.meetings) topics.push(`${plural(counts.meetings, 'reunión', 'reuniones')}`);
  if (counts.due_soon_tasks) topics.push(`${plural(counts.due_soon_tasks, 'tarea por vencer', 'tareas por vencer')}`);
  if (counts.focus_tasks) topics.push(`${plural(counts.focus_tasks, 'prioridad en foco', 'prioridades en foco')}`);

  let intro;
  if (topics.length) {
    intro = `Tienes ${topics.join(', ')}.`;
  } else {
    intro = 'Por ahora no hay nada urgente en el radar.';
  }
  sentences.push(intro);

  if (hasFocus) {
    sentences.push(
      `Tu ${plural(counts.focus_tasks, 'prioridad principal es', 'prioridades principales son')} ${focus.title}.`,
    );
  }

  const primary = hasFocus
    ? `<div class="brief-primary">
        <span class="brief-primary-tag">Foco</span>
        <div class="brief-primary-body">
          <b>${esc(focus.title)}</b>
          <span>${esc(taskContext(focus, maps))}</span>
        </div>
        <a class="btn btn-soft btn-sm" href="#/mi-dia">Ver mi día ${icon('arrow')}</a>
      </div>`
    : '';

  const chips = [
    ['Foco', b.counts.focus_tasks, '#/mi-dia'],
    ['Vencidas', b.counts.overdue_tasks, '#/tareas?status=overdue'],
    ['Reuniones hoy', b.counts.meetings, '#/reuniones'],
    ['Por vencer', b.counts.due_soon_tasks, '#/tareas?status=due_soon'],
    ['Bloqueadas', b.counts.blocked_tasks, '#/tareas?status=blocked'],
  ]
    .filter(([, n]) => n > 0)
    .map(
      ([label, n, href]) =>
        `<a class="brief-chip" href="#${href}"><b>${n}</b><span>${esc(label)}</span></a>`,
    )
    .join('');

  return `
    <p class="brief-greet">Buenos días.</p>
    ${sentences.map((s) => `<p class="brief-sentence">${esc(s)}</p>`).join('')}
    ${chips ? `<div class="brief-chips">${chips}</div>` : ''}
    ${primary}`;
}

function agendaHtml(b, tasksDue, maps) {
  const rows = [];
  for (const meeting of b.meetings || []) {
    rows.push({
      time: fmtTime(meeting.starts_at),
      allDay: false,
      title: meeting.title,
      meta: maps.project[meeting.project_id] ? maps.project[meeting.project_id] : (meeting.project_id ? esc(meeting.project_id) : 'Sin proyecto'),
      href: `#/reuniones/${esc(meeting.id)}`,
      chip: meeting.project_id ? '' : badge('pending'),
    });
  }
  for (const task of tasksDue || []) {
    if (task.status === 'done' || task.status === 'cancelled') continue;
    rows.push({
      time: 'Hoy',
      allDay: true,
      title: task.title,
      meta: taskContext(task, maps),
      href: '#/mi-dia',
    });
  }
  rows.sort((a, b) => (a.allDay === b.allDay ? String(a.time).localeCompare(String(b.time)) : a.allDay ? -1 : 1));
  if (!rows.length) return emptyBlock('Sin reuniones ni tareas para hoy.');
  const items = rows
    .map(
      (row) => `
      <a class="agenda-row" href="${row.href}">
        <span class="agenda-time ${row.allDay ? 'all-day' : ''}">${esc(row.time)}</span>
        <div class="item-main"><div class="item-title">${esc(row.title)}</div>
        <div class="item-sub">${row.meta}</div></div>
        ${row.chip || ''}
      </a>`,
    )
    .join('');
  return `<div class="list">${items}</div>`;
}

function prioritiesHtml(b, maps) {
  const items = [];
  for (const t of b.overdue_tasks || []) {
    items.push({ task: t, kind: 'vencida', order: 0, extra: `Vencida · ${fmtDate(t.due_at)}` });
  }
  for (const t of b.due_soon_tasks || []) {
    if (t.due_at === todayISO()) items.push({ task: t, kind: 'hoy', order: 1, extra: 'Vence hoy' });
  }
  for (const t of b.blocked_tasks || []) {
    items.push({ task: t, kind: 'bloqueada', order: 2, extra: 'Bloqueada' });
  }
  for (const t of b.focus_tasks || []) {
    if (!items.some((i) => i.task.id === t.id)) {
      items.push({ task: t, kind: 'foco', order: 3, extra: t.due_at ? `Vence ${fmtDate(t.due_at)}` : 'En foco' });
    }
  }
  items.sort((a, b) => a.order - b.order || String(a.task.priority).localeCompare(String(b.task.priority)));
  const top = items.slice(0, 5);
  if (!top.length) return emptyBlock('Nada prioritario por ahora.');
  return `<div class="p-list">${top
    .map(
      ({ task, extra }) => `
      <li class="item item-row">
        <div class="item-main">
          <div class="item-title">${esc(task.title)}</div>
          <div class="item-sub">${esc(taskContext(task, maps))} · ${esc(extra)}</div>
        </div>
        <div class="item-side">${prio(task.priority)}${badge(task.status)}</div>
      </li>`,
    )
    .join('')}
  </div>`;
}

function insightRows(b, captures, projects, toReview) {
  const rows = [];
  if (b.counts.overdue_tasks) {
    rows.push({ icon: 'warn', label: `Hay ${plural(b.counts.overdue_tasks, 'tarea vencida', 'tareas vencidas')} que requieren tu atención.`, cta: 'Ver', href: '#/tareas?status=overdue' });
  }
  const untriaged = (captures || []).length;
  if (untriaged) {
    rows.push({ icon: 'inbox', label: `Hay ${plural(untriaged, 'elemento sin clasificar', 'elementos sin clasificar')} en Inbox.`, cta: 'Organizar', href: '#/inbox' });
  }
  if (b.counts.blocked_tasks) {
    rows.push({ icon: 'alert', label: `${plural(b.counts.blocked_tasks, 'tarea está bloqueada', 'tareas están bloqueadas')}. Revisa qué las detiene.`, cta: 'Revisar', href: '#/tareas?status=blocked' });
  }
  for (const p of (projects || [])) {
    if (p.health === 'off_track' || p.health === 'at_risk') {
      rows.push({ icon: 'flag', label: `El proyecto «${p.name}» se reporta «${humanStatus(p.health)}».`, cta: 'Ver', href: '#/proyectos' });
      break;
    }
  }
  if (b.counts.deliverable_opportunities) {
    const d = b.deliverable_opportunities[0];
    rows.push({ icon: 'doc', label: `El entregable «${d.title}» vence y aún no tiene tareas en curso.`, cta: 'Revisar', href: '#/proyectos' });
  }
  if (b.counts.meetings) {
    rows.push({ icon: 'calendar', label: `${plural(b.counts.meetings, 'reunión programada para hoy', 'reuniones programadas para hoy')}.`, cta: 'Abrir', href: '#/reuniones' });
  }
  if (toReview.length) {
    rows.push({ icon: 'flag', label: `${plural(toReview.length, 'reunión espera revisión posterior', 'reuniones esperan revisión posterior')}.`, cta: 'Revisar', href: '#/reuniones' });
  }
  if (!rows.length) {
    return emptyBlock('Faro no detecta situaciones que requieran tu atención ahora mismo.');
  }
  return `<div class="p-list">${rows
    .slice(0, 5)
    .map(
      (r) => `
      <li class="insight">
        ${icon(r.icon)}
        <div class="insight-body">${esc(r.label)}</div>
        <a class="btn btn-soft btn-xs" href="#${r.href}">${esc(r.cta)}${icon('arrow')}</a>
      </li>`,
    )
    .join('')}
  </div>`;
}

function activityHtml(audit, maps) {
  const labels = {
    workspace: 'Workspace',
    client: 'Cliente',
    project: 'Proyecto',
    deliverable: 'Entregable',
    task: 'Tarea',
    meeting: 'Reunión',
    action_item: 'Elemento de acción',
    capture: 'Captura',
  };
  const verbs = { create: 'creado', update: 'actualizado', delete: 'eliminado' };
  const items = (audit || []).map((e) => {
    const name = e.changes?.name?.new || e.changes?.title?.new || e.changes?.text?.new || e.changes?.id?.new || '';
    const kindLabel = labels[e.entity_kind] || e.entity_kind;
    const verb = verbs[e.action] || e.action;
    return { name, kindLabel, verb, at: e.occurred_at };
  });
  if (!items.length) return emptyBlock('Sin actividad registrada.');
  return `<div class="p-list">${items
    .map(
      (it) => `
      <li class="activity">
        <span class="activity-kind">${icon('clock')}</span>
        <div class="activity-body">
          <b>${esc(kindCapitalize(it.name) || '—')}</b>
          <span>${esc(it.kindLabel)} ${esc(it.verb)} · ${esc(timeAgo(it.at))}</span>
        </div>
      </li>`,
    )
    .join('')}
  </div>`;
}

function kindCapitalize(name) {
  if (!name) return '';
  return name.charAt(0).toUpperCase() + name.slice(1);
}

function workloadHtml(progress) {
  if (!progress || !progress.totals || !progress.totals.tasks.total) return '';
  let rows;
  const byWorkspace = progress.workspaces || [];
  const byClient = progress.clients || [];
  const byProject = progress.projects || [];
  if (byWorkspace.length > 1) rows = byWorkspace;
  else if (byClient.length > 1) rows = byClient;
  else rows = byProject;
  rows = rows
    .map((r) => ({ name: r.name, open: r.metrics.tasks.open || 0 }))
    .filter((r) => r.open > 0)
    .sort((a, b) => b.open - a.open)
    .slice(0, 6);
  if (!rows.length) return '';
  const max = Math.max(...rows.map((r) => r.open), 1);
  const bars = rows
    .map(
      (r) => `
      <div class="workload-bar">
        <span class="wl-name" title="${esc(r.name)}">${esc(r.name)}</span>
        <div class="wl-track"><div class="wl-fill" style="width:${Math.max(8, Math.round((r.open / max) * 100))}%"></div></div>
        <span class="wl-count">${r.open}</span>
      </div>`,
    )
    .join('');
  return `
    <div class="workload-list">${bars}</div>
    <p class="workload-note">tareas abiertas</p>`;
}

function reviewAlert(b, unmatched, toReview) {
  const total = (unmatched || []).length + (toReview || []).length;
  if (!total) return '';
  const msg =
    `${plural(total, 'reunión necesita', 'reuniones necesitan')} clasificación o revisión.`;
  return `<div class="alert alert-warn">
    ${icon('flag')}
    <span><b>Revisión pendiente.</b> ${esc(msg)}</span>
    <a class="btn btn-sm btn-safe alert-cta" href="#/reuniones">Revisar</a>
  </div>`;
}

function activeProjectsBlock(projects, maps) {
  const actives = (projects || []).filter((p) => p.status === 'active' || p.status === 'planned');
  if (!actives.length) return '';
  return `<div class="card-list">${actives
    .slice(0, 4)
    .map(
      (p) => `
      <div class="item item-row">
        <div class="item-main"><div class="item-title">${esc(p.name)}</div>
        <div class="item-sub">${esc(projectDescription(p, maps))}</div></div>
        <div class="item-side">${badge(p.status)}</div>
      </div>`,
    )
    .join('')}
  </div>`;
}

export async function renderInicio(el) {
  setPageTitle('Inicio');
  el.innerHTML = `
    <div class="page-head">
      <div class="page-greeting">
        <h1>Buenos días</h1>
        <span class="date-line">· ${esc(fmtFullDate(new Date()))}</span>
      </div>
      <p class="page-sub">Aquí tienes el panorama de tu trabajo.</p>
    </div>
    ${skeleton(4, true)}`;
  try {
    const { maps, brief, projects, tasksDue, captures, audit, progress, unmatched, toReview } =
      await homeData();
    const counts = brief.counts;
    const workspaceName =
      progress && progress.workspaces && progress.workspaces[0] ? progress.workspaces[0].name : '';
    const kpis = `
      ${kpiCard(counts.focus_tasks, 'Tareas en foco', 'target', '#/mi-dia')}
      ${kpiCard(counts.overdue_tasks, 'Vencidas', 'clock', '#/tareas?status=overdue', 'kpi-icon--danger')}
      ${kpiCard(counts.meetings, 'Reuniones hoy', 'calendar', '#/reuniones')}
      ${kpiCard((projects || []).filter((p) => p.status === 'active').length, 'Proyectos activos', 'folder', '#/proyectos', 'kpi-icon--success')}
      ${counts.blocked_tasks ? kpiCard(counts.blocked_tasks, 'Bloqueadas', 'alert', '#/tareas?status=blocked', 'kpi-icon--warning') : ''}
      ${counts.due_soon_tasks ? kpiCard(counts.due_soon_tasks, 'Por vencer', 'flag', '#/tareas?status=due_soon') : ''}`;

    el.innerHTML = `
      <div class="page-head">
        <div class="page-greeting">
          <h1>Buenos días</h1>
          <span class="date-line">· ${esc(workspaceName || fmtFullDate(new Date()))}</span>
        </div>
        <p class="page-sub">Aquí tienes el panorama de tu trabajo.</p>
      </div>
      <section class="kpi-row">${kpis}</section>
      ${reviewAlert(brief, unmatched, toReview)}
      <div class="page-grid two">
        <div class="stack">
          <section class="card">
            <div class="card-head"><h2>${icon('sparkles')} Brief de la mañana</h2>
              <a class="btn btn-soft btn-sm card-action" href="#/mi-dia">Mi día</a></div>
            <div class="card-body brief-body">${briefSynthesis(brief, maps)}</div>
          </section>
          <section class="card">
            <div class="card-head"><h2>${icon('clock')} Agenda de hoy</h2>
              <a class="card-action btn btn-ghost btn-sm" href="#/calendario">Calendario</a></div>
            <div class="card-body">${agendaHtml(brief, tasksDue, maps)}</div>
          </section>
          <section class="card">
            <div class="card-head"><h2>${icon('flag')} Prioridades</h2>
              <a class="card-action btn btn-ghost btn-sm" href="#/tareas">Todas</a></div>
            <div class="card-body">${prioritiesHtml(brief, maps)}</div>
          </section>
          ${activeProjectsBlock(projects, maps) ? `<section class="card">
            <div class="card-head"><h2>${icon('folder')} Proyectos en curso</h2>
              <a class="card-action btn btn-ghost btn-sm" href="#/proyectos">Portfolio</a></div>
            <div class="card-body">${activeProjectsBlock(projects, maps)}</div>
          </section>` : ''}
        </div>
        <div class="stack">
          <section class="card">
            <div class="card-head"><h2>${icon('sparkles')} Faro Insights</h2></div>
            <div class="card-body">${insightRows(brief, captures, projects, toReview)}</div>
          </section>
          <section class="card">
            <div class="card-head"><h2>${icon('clock')} Actividad reciente</h2></div>
            <div class="card-body">${activityHtml(audit, maps)}</div>
          </section>
          ${workloadHtml(progress) ? `<section class="card">
            <div class="card-head"><h2>${icon('folder')} Carga de trabajo</h2></div>
            <div class="card-body">${workloadHtml(progress)}</div>
          </section>` : ''}
        </div>
      </div>`;
  } catch (err) {
    el.innerHTML = errorBlock(`Inicio no disponible: ${esc(err.message)}`);
  }
}

/* ============================================================
   MI DÍA  (FASE UI-3)
   ============================================================ */

export async function renderMiDia(el) {
  setPageTitle('Mi Día');
  el.innerHTML = `
    <div class="page-head"><h1>Mi Día</h1><p class="page-sub">${esc(fmtFullDate(new Date()))}</p></div>
    ${skeleton(6)}`;
  try {
    const [maps, brief, tasks, evening] = await Promise.all([
      nameMaps(),
      api('/api/v1/briefs/morning'),
      listTasks(),
      api('/api/v1/briefs/evening'),
    ]);
    const open = (tasks || []).filter((t) => !['done', 'cancelled'].includes(t.status));
    const done = (tasks || []).filter((t) => t.status === 'done').length;
    const todayCount = (evening.completed_tasks || []).length;
    const total = done + open.length;
    const pct = total ? Math.round((todayCount / total) * 100) : 0;

    const timeline = [];
    for (const t of brief.focus_tasks || []) {
      timeline.push({ slot: 'Ahora', task: t, overdue: brief.overdue_tasks.some((o) => o.id === t.id) });
    }
    for (const m of brief.meetings || []) {
      timeline.push({ slot: fmtTime(m.starts_at), meeting: m });
    }
    const dueToday = (tasks || []).filter(
      (t) => t.due_at === todayISO() && !['done', 'cancelled'].includes(t.status),
    );
    for (const t of dueToday) {
      if (!timeline.some((x) => x.task && x.task.id === t.id)) {
        timeline.push({ slot: 'Hoy', task: t });
      }
    }
    timeline.sort((a, b) => {
      const rank = { Ahora: 0, Hoy: 1 };
      const sa = rank[a.slot] ?? 2;
      const sb = rank[b.slot] ?? 2;
      return sa - sb || String(a.slot).localeCompare(String(b.slot));
    });

    const items = timeline
      .map((entry) => {
        const overdue = entry.overdue;
        if (entry.meeting) {
          const m = entry.meeting;
          return `
            <div class="tl-item">
              <div class="tl-head">
                <span class="tl-time">${esc(fmtTime(m.starts_at))}</span>
                <span class="tl-title">${esc(m.title)}</span>
                ${m.project_id ? '' : badge('pending')}
              </div>
              <div class="tl-meta">Reunión · ${esc(maps.project[m.project_id] || (m.project_id ? m.project_id : 'sin proyecto'))} · <a href="#/reuniones/${esc(m.id)}">Abrir reunión</a></div>
            </div>`;
        }
        const t = entry.task;
        const actions = `
          <div class="tl-actions">
            ${t.status !== 'in_progress' ? `<button class="btn btn-soft btn-xs" data-act="start" data-id="${esc(t.id)}">${icon('play')} Iniciar</button>` : ''}
            <button class="btn btn-success-soft btn-xs" data-act="complete" data-id="${esc(t.id)}">${icon('check')} Completar</button>
            <button class="btn btn-ghost btn-xs" data-act="resched" data-id="${esc(t.id)}" data-due="${esc(t.due_at || '')}">${icon('calendar')} Reprogramar</button>
          </div>`;
        return `
          <div class="tl-item ${overdue ? 'tl-overdue' : entry.slot === 'Ahora' ? 'tl-now' : ''}">
            <div class="tl-head">
              <span class="tl-time">${esc(entry.slot === 'Ahora' ? 'Ahora' : entry.slot)}</span>
              <span class="tl-title">${esc(t.title)}</span>
              ${prio(t.priority)}
            </div>
            <div class="tl-meta">${esc(taskContext(t, maps))}${t.due_at ? ` · vence ${esc(fmtDate(t.due_at))}` : ''}${overdue ? ' · <b class="text-danger">Vencida</b>' : ''}</div>
            ${actions}
          </div>`;
      })
      .join('');

    el.innerHTML = `
      <div class="page-head">
        <div class="page-greeting"><h1>Mi Día</h1><span class="date-line">· ${esc(fmtDayMonth(new Date()))}</span></div>
        <p class="page-sub">${plural(todayCount, 'tarea completada', 'tareas completadas')} hoy · ${plural(open.length, 'pendiente', 'pendientes')}</p>
        <div style="margin-top:12px">${progressBar(pct)}</div>
      </div>
      <section class="card">
        <div class="card-head"><h2>${icon('clock')} Línea del día</h2></div>
        <div class="card-body">
          ${items ? `<div class="timeline">${items}</div>` : emptyBlock('Todo listo por ahora.', `<a class="btn btn-soft btn-sm" href="#/capturar" data-capture-open="1">Capturar algo</a>`)}
        </div>
      </section>
      <section class="card" style="margin-top:16px">
        <div class="card-head"><h2>${icon('flag')} Cierre del día</h2></div>
        <div class="card-body">
          ${eveningBlock(evening)}
        </div>
      </section>`;

    if (!el.dataset.viewBound) {
      el.dataset.viewBound = '1';
      el.addEventListener('click', async (event) => {
        const btn = event.target.closest('[data-act]');
        if (!btn) return;
        const id = btn.dataset.id;
        try {
          if (btn.dataset.act === 'start') {
            await api(`/api/v1/tasks/${encodeURIComponent(id)}/start`, { method: 'POST' });
            toast('Tarea iniciada', 'success');
          } else if (btn.dataset.act === 'complete') {
            const note = await promptCompletionNote();
            if (note === null) return;
            await api(`/api/v1/tasks/${encodeURIComponent(id)}/complete`, {
              method: 'POST',
              body: JSON.stringify(note ? { completion_note: note } : {}),
            });
            toast('Tarea completada', 'success');
          } else if (btn.dataset.act === 'resched') {
            const due = await promptDate('Reprogramar tarea', btn.dataset.due || todayISO());
            if (!due) return;
            await api(`/api/v1/tasks/${encodeURIComponent(id)}`, {
              method: 'PATCH',
              body: JSON.stringify({ due_at: due }),
            });
            toast('Fecha actualizada', 'success');
          }
        } catch (err) {
          toast(`No se pudo completar: ${err.message}`, 'error');
        }
        invalidate('tasks');
        renderMiDia(el);
      });
    }
  } catch (err) {
    el.innerHTML = errorBlock(`Mi Día no disponible: ${esc(err.message)}`);
  }
}

function eveningBlock(evening) {
  const c = evening.counts;
  const chips = [];
  if (c.completed_tasks) chips.push(`${c.completed_tasks} completadas`);
  if (c.unfinished_tasks) chips.push(`${c.unfinished_tasks} pendientes`);
  if (c.open_action_items) chips.push(`${c.open_action_items} elementos de acción abiertos`);
  if (c.untriaged_captures) chips.push(`${c.untriaged_captures} sin clasificar en Inbox`);
  if (!chips.length) return emptyBlock('Aún no hay actividad registrada para hoy.');
  return `<div class="p-list">${chips.map((c2) => `<li class="activity"><span class="activity-kind">${icon('check')}</span><div class="activity-body"><span>${esc(c2)}</span></div></li>`).join('')}</div>`;
}

/* ============================================================
   INBOX  (FASE UI-4)
   ============================================================ */

export async function renderInbox(el) {
  setPageTitle('Inbox');
  el.innerHTML = `
    <div class="page-head"><h1>Inbox</h1><p class="page-sub">Lo capturado, todavía sin organizar.</p></div>
    ${skeleton(4)}`;
  try {
    const [items, projects, meetings, maps] = await Promise.all([
      api('/api/v1/captures?limit=200&capture_status=inbox'),
      listProjects(),
      listMeetings(),
      nameMaps(),
    ]);
    const body = items && items.length
      ? `<div class="list">${items
          .map((c) => inboxItem(c, maps))
          .join('')}</div>`
      : emptyBlock('Inbox vacío. Todo lo capturado está organizado.', `<button class="btn btn-soft btn-sm" data-capture-open="1">Capturar algo</button>`);

    el.innerHTML = `
      <div class="page-head">
        <div class="page-greeting"><h1>Inbox</h1><span class="date-line">· ${plural((items || []).length, 'elemento', 'elementos')}</span></div>
        <p class="page-sub">Faro propone · tú confirmas. También puedes clasificar manualmente.</p>
      </div>
      <section class="card no-pad"><div class="card-body">${body}</div></section>`;

    if (!el.dataset.viewBound) {
      el.dataset.viewBound = '1';
      el.addEventListener('click', async (event) => {
        const btn = event.target.closest('[data-cap]');
        if (!btn || btn.disabled) return;
        const id = btn.dataset.id;
        btn.disabled = true;
        try {
          if (btn.dataset.cap === 'suggest') {
            await api(`/api/v1/captures/${encodeURIComponent(id)}/suggest`, { method: 'POST' });
            toast('Propuesta generada', 'success');
          } else if (btn.dataset.cap === 'triage') {
            const triage = await promptTriage({ projects, meetings });
            if (triage === null) { btn.disabled = false; return; }
            await api(`/api/v1/captures/${encodeURIComponent(id)}/triage`, {
              method: 'POST',
              body: JSON.stringify(triage),
            });
            toast('Captura clasificada', 'success');
          } else if (btn.dataset.cap === 'apply') {
            await api(`/api/v1/captures/${encodeURIComponent(id)}/apply`, { method: 'POST', body: '{}' });
            toast('Clasificación confirmada', 'success');
          } else if (btn.dataset.cap === 'discard') {
            const note = window.prompt('Motivo para descartar:');
            if (!note) { btn.disabled = false; return; }
            await api(`/api/v1/captures/${encodeURIComponent(id)}/triage`, {
              method: 'POST',
              body: JSON.stringify({ disposition: 'dismissed', note }),
            });
            toast('Captura descartada', 'success');
          }
        } catch (err2) {
          if (btn.dataset.cap === 'suggest' && err2.status === 503) {
            toast('Clasificación IA no configurada. Usa «Clasificar» para organizarla manualmente.', 'info');
          } else {
            toast(err2.message, 'error');
          }
          btn.disabled = false;
        }
        renderInbox(el);
      });
    }
  } catch (err) {
    el.innerHTML = errorBlock(`Inbox no disponible: ${esc(err.message)}`);
  }
}

function inboxItem(c, maps) {
  const kindLabel = {
    task: 'Tarea',
    action: 'Elemento de acción',
    reference: 'Referencia',
    meeting: 'Reunión',
    note: 'Nota',
    reminder: 'Recordatorio',
  };
  const kind = kindLabel[c.proposal_kind] || 'Información';
  const proposal = c.proposal_kind
    ? `
      <div class="proposal">
        <span class="proposal-tag">Faro propone</span>
        <span>${esc(kind.toLowerCase())} · ${c.proposal_project_id ? esc(maps.project[c.proposal_project_id] || c.proposal_project_id) : 'sin proyecto'}${c.proposal_due_at ? ` · vence ${esc(fmtDate(c.proposal_due_at))}` : ''}</span>
      </div>`
    : '';
  const actions = `
    <div class="item-actions">
      <button class="btn btn-primary btn-xs" data-cap="triage" data-id="${esc(c.id)}">Clasificar</button>
      ${!c.proposal_kind ? `<button class="btn btn-ghost btn-xs" data-cap="suggest" data-id="${esc(c.id)}">Sugerir IA</button>` : ''}
      ${c.proposal_kind ? `<button class="btn btn-soft btn-xs" data-cap="apply" data-id="${esc(c.id)}">Confirmar</button>` : ''}
      <button class="btn btn-danger-soft btn-xs" data-cap="discard" data-id="${esc(c.id)}">Descartar</button>
    </div>`;
  return `
    <div class="item inbox-item">
      <div class="item-main">
        <div class="item-title"><span class="item-kind">${esc(kind)}</span> ${esc(c.text.length > 90 ? `${c.text.slice(0, 90)}…` : c.text)}</div>
        <div class="item-sub">${esc(fmtDate(c.captured_at))} · captura local</div>
        ${proposal}
      </div>
      ${actions}
    </div>`;
}

/* ============================================================
   PROYECTOS — PORTFOLIO
   ============================================================ */

export async function renderProyectos(el) {
  setPageTitle('Proyectos');
  el.innerHTML = `
    <div class="page-head"><h1>Pulso de Proyectos</h1><p class="page-sub">Portafolio de trabajo, clientes y estados.</p></div>
    ${skeleton(4)}`;
  try {
    const [workspaces, projects, clients, deliverables, tasks, maps] = await Promise.all([
      listWorkspaces(),
      listProjects(),
      listClients(),
      listDeliverables(),
      listTasks(),
      nameMaps(),
    ]);
    const projStats = {};
    for (const t of tasks || []) {
      if (t.status === 'done' || t.status === 'cancelled') continue;
      const s = (projStats[t.project_id] = projStats[t.project_id] || { open: 0, blocked: 0, overdue: 0 });
      s.open += 1;
      if (t.status === 'blocked') s.blocked += 1;
      if (t.due_at && t.due_at < todayISO()) s.overdue += 1;
    }
    const dueSoon = {};
    for (const d of deliverables || []) {
      if (d.status === 'accepted' || d.status === 'cancelled') continue;
      if (d.due_at >= todayISO() && d.due_at <= addDaysISO(todayISO(), 7)) {
        dueSoon[d.project_id] = (dueSoon[d.project_id] || 0) + 1;
      }
    }
    const counts = {
      active: (projects || []).filter((p) => p.status === 'active').length,
      paused: (projects || []).filter((p) => p.status === 'paused').length,
      blocked: (projects || []).filter((p) => p.health === 'off_track').length,
      due_soon: Object.values(dueSoon).reduce((a, b) => a + b, 0),
      completed: (projects || []).filter((p) => p.status === 'completed').length,
    };

    const wsFilter = (p) => !state.filterWs || maps.clientWorkspace[p.client_id] === state.filterWs;
    const clientFilter = (p) => !state.filterClient || p.client_id === state.filterClient;
    const statusFilter = (p) => !state.filterStatus || p.status === state.filterStatus;
    const filterPending = () => Boolean(state.filterWs || state.filterClient || state.filterStatus);

    const projectCard = (p) => {
      const s = projStats[p.id] || { open: 0, blocked: 0, overdue: 0 };
      const chips = [];
      if (s.overdue) chips.push(`<span class="proj-chip proj-chip--danger">${s.overdue} vencidas</span>`);
      if (s.blocked) chips.push(`<span class="proj-chip proj-chip--warn">${s.blocked} bloqueadas</span>`);
      if (dueSoon[p.id]) chips.push(`<span class="proj-chip proj-chip--primary">${dueSoon[p.id]} vencen pronto</span>`);
      return `
        <a class="card project-card" href="#/proyectos/${esc(p.id)}">
          <div class="project-card-head">
            <div class="project-title">${esc(p.name)}</div>
            <div class="item-side gap-1">${badge(p.status)}${p.health && p.health !== 'unknown' ? badge(p.health) : ''}</div>
          </div>
          <div class="project-desc">${esc(projectDescription(p, maps))}</div>
          ${chips.length ? `<div class="project-chips">${chips.join('')}</div>` : ''}
          <div class="project-metrics">
            <span>${plural(s.open, 'tarea abierta', 'tareas abiertas')}</span>
            <span class="project-pid">${esc(p.id)}</span>
          </div>
        </a>`;
    };
    const projectRow = (p) => {
      const s = projStats[p.id] || { open: 0, blocked: 0, overdue: 0 };
      return `
        <a class="item item-row" href="#/proyectos/${esc(p.id)}">
          <div class="item-main">
            <div class="item-title">${esc(p.name)}</div>
            <div class="item-sub">${esc(projectDescription(p, maps))} · ${plural(s.open, 'tarea abierta', 'tareas abiertas')}${s.overdue ? ` · <span class="text-danger">${s.overdue} vencidas</span>` : ''}</div>
          </div>
          <div class="item-side">${badge(p.status)}${p.health && p.health !== 'unknown' ? badge(p.health) : ''}</div>
        </a>`;
    };

    const state = { view: 'cards', filterWs: '', filterClient: '', filterStatus: '' };

    const renderGrid = () => {
      const list = (projects || []).filter(wsFilter).filter(clientFilter).filter(statusFilter);
      const host = el.querySelector('#projects-grid');
      if (!list.length) {
        host.innerHTML = emptyBlock(filterPending() ? 'Sin proyectos con esos filtros.' : 'Sin proyectos registrados.', `<button class="btn btn-soft btn-sm" data-capture-open="1">Capturar</button>`);
        return;
      }
      host.innerHTML = state.view === 'cards'
        ? `<div class="project-grid">${list.map(projectCard).join('')}</div>`
        : `<div class="list">${list.map(projectRow).join('')}</div>`;
    };

    const wsOpts = (workspaces || [])
      .map((w) => `<option value="${esc(w.id)}">${esc(w.name)}</option>`)
      .join('');
    const clientsOpts = (clients || [])
      .map((c) => `<option value="${esc(c.id)}">${esc(c.name)}</option>`)
      .join('');
    const statusOpts = ['planned', 'active', 'paused', 'completed', 'cancelled']
      .map((s) => `<option value="${s}">${esc(humanStatus(s))}</option>`)
      .join('');

    el.innerHTML = `
      <div class="page-head"><h1>Pulso de Proyectos</h1><p class="page-sub">Portafolio de trabajo.</p>
        <div class="page-head-actions">
          <button class="btn btn-primary btn-sm" data-create="project">${icon('plus')} Nuevo proyecto</button>
        </div>
      </div>
      <section class="kpi-row">
        ${kpiCard(counts.active, 'Activos', 'folder', '#/proyectos', 'kpi-icon--success')}
        ${kpiCard(counts.blocked, 'Con riesgo', 'alert', '#/proyectos', 'kpi-icon--warning')}
        ${kpiCard(counts.paused, 'En espera', 'folder', '#/proyectos')}
        ${kpiCard(counts.completed, 'Completados', 'check', '#/proyectos')}
      </section>
      <div class="filterbar">
        <select data-pf="ws" aria-label="Filtrar por workspace"><option value="">Todos los workspaces</option>${wsOpts}</select>
        <select data-pf="client" aria-label="Filtrar por cliente"><option value="">Todos los clientes</option>${clientsOpts}</select>
        <select data-pf="status" aria-label="Filtrar por estado"><option value="">Todos los estados</option>${statusOpts}</select>
        <span class="view-toggle" role="group" aria-label="Vista">
          <button type="button" class="icon-btn btn-ghost-view active" data-pf-view="cards" title="Tarjetas" aria-label="Vista de tarjetas">${icon('folder')}</button>
          <button type="button" class="icon-btn btn-ghost-view" data-pf-view="list" title="Lista" aria-label="Vista de lista">${icon('doc')}</button>
        </span>
      </div>
      <div id="projects-grid"></div>`;

    if (!el.dataset.viewBound) {
      el.dataset.viewBound = '1';
      el.addEventListener('change', (event) => {
        const sel = event.target.closest('[data-pf]');
        if (!sel) return;
        state[sel.dataset.pf] = sel.value;
        renderGrid();
      });
      el.addEventListener('click', async (event) => {
        const viewBtn = event.target.closest('[data-pf-view]');
        if (viewBtn) {
          state.view = viewBtn.dataset.pfView;
          el.querySelectorAll('[data-pf-view]').forEach((b) => b.classList.toggle('active', b === viewBtn));
          renderGrid();
          return;
        }
        const createBtn = event.target.closest('[data-create="project"]');
        if (createBtn) {
          const form = await openForm({
            title: 'Nuevo proyecto',
            submitLabel: 'Crear proyecto',
            fields: [
              { name: 'name', label: 'Nombre', required: true, placeholder: 'Ej. Migración de red' },
              {
                name: 'client',
                label: 'Cliente',
                type: 'select',
                required: true,
                options: (clients || []).map((c) => ({ value: c.id, label: c.name })),
              },
              {
                name: 'status',
                label: 'Estado',
                type: 'select',
                value: 'active',
                options: ['planned', 'active', 'paused'].map((s) => ({ value: s, label: humanStatus(s) })),
              },
            ],
          });
          if (!form) return;
          try {
            await api('/api/v1/projects', {
              method: 'POST',
              body: JSON.stringify({
                id: genEntityId('prj', form.name),
                name: form.name,
                client_id: form.client,
                status: form.status || 'planned',
                health: 'unknown',
              }),
            });
            toast('Proyecto creado', 'success');
          } catch (err) {
            toast(`No se pudo crear el proyecto: ${err.message}`, 'error');
          }
          invalidate('projects');
          renderProyectos(el);
          return;
        }
      });
    }
    renderGrid();
  } catch (err) {
    el.innerHTML = errorBlock(`No se pudieron cargar los proyectos: ${esc(err.message)}`);
  }
}

/* ============================================================
   PROYECTO — DETALLE  (FASE UI-5)
   ============================================================ */

function formatMinutes(total) {
  const m = Math.max(0, Math.round(total || 0));
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest ? `${h} h ${rest} min` : `${h} h`;
}

export async function renderProyectoDetalle(el, projectId) {
  setPageTitle('Proyecto');
  el.innerHTML = skeleton(6);
  try {
    const [project, deliverables, tasks, meetings, driveLinks, audit, maps, allActionItems] =
      await Promise.all([
        api(`/api/v1/projects/${encodeURIComponent(projectId)}`),
        api(`/api/v1/deliverables?project_id=${encodeURIComponent(projectId)}`),
        api(`/api/v1/tasks?project_id=${encodeURIComponent(projectId)}`),
        api(`/api/v1/meetings?project_id=${encodeURIComponent(projectId)}`),
        api('/api/v1/integrations/drive-links').catch(() => []),
        api(`/api/v1/audit-events?entity_id=${encodeURIComponent(projectId)}&limit=20`).catch(() => []),
        nameMaps(),
        api('/api/v1/action-items').catch(() => []),
      ]);
    const clientId = project.client_id;
    const client = clientId ? maps.client[clientId] : '';
    const workspace = clientId ? maps.workspace[maps.clientWorkspace[clientId]] : '';

    const openTasks = (tasks || []).filter((t) => !['done', 'cancelled'].includes(t.status));
    const doneCount = (tasks || []).filter((t) => t.status === 'done').length;
    const blocked = openTasks.filter((t) => t.status === 'blocked').length;
    const acceptedDeliverables = (deliverables || []).filter((d) => d.status === 'accepted').length;
    const openDeliverables = (deliverables || []).filter((d) => d.status !== 'accepted' && d.status !== 'cancelled');
    const upcomingMeetings = (meetings || [])
      .filter((m) => m.status === 'scheduled')
      .sort((a, b) => String(a.starts_at).localeCompare(String(b.starts_at)));
    const pastMeetings = (meetings || [])
      .filter((m) => m.status !== 'scheduled')
      .sort((a, b) => String(b.starts_at).localeCompare(String(a.starts_at)));
    const nextMeeting = upcomingMeetings[0];

    const meetingIds = new Set((meetings || []).map((m) => m.id));
    const commitments = (allActionItems || []).filter(
      (ai) => meetingIds.has(ai.meeting_id) && ai.status !== 'completed',
    );

    const logsBundle = await Promise.all(
      openTasks.map((t) =>
        api(`/api/v1/tasks/${encodeURIComponent(t.id)}/work-logs`)
          .catch(() => [])
          .then((logs) => ({ taskId: t.id, logs: logs || [] })),
      ),
    );
    const logsByTask = Object.fromEntries(logsBundle.map((b) => [b.taskId, b.logs]));
    const todayIso = todayISO();
    let totalMinutes = 0;
    let todayMinutes = 0;
    for (const b of logsBundle) {
      for (const log of b.logs) {
        totalMinutes += log.minutes || 0;
        if (String(log.started_at || '').slice(0, 10) === todayIso) todayMinutes += log.minutes || 0;
      }
    }

    const deliverableIds = new Set((deliverables || []).map((d) => d.id));
    const links = (driveLinks || []).filter((l) => deliverableIds.has(l.deliverable_id));

    const tasksHtml = `<div class="tab-head">
      <button class="btn btn-soft btn-sm" data-create="project-task">${icon('plus')} Nueva tarea</button>
    </div>${openTasks.length
      ? `<div class="check-list">${openTasks.map((t) => `
        <div class="check-item">
          <button class="check-box" data-tact="complete" data-id="${esc(t.id)}" aria-label="Completar ${esc(t.title)}">${icon('check')}</button>
          <div class="item-main">
            <div class="item-title">${esc(t.title)}</div>
            <div class="item-sub">${t.due_at ? `Vence ${esc(fmtDate(t.due_at))}` : 'Sin fecha'} · ${esc(humanStatus(t.status))}</div>
          </div>
          <div class="item-side">
            ${prio(t.priority)}
            ${t.status !== 'in_progress' ? `<button class="btn btn-ghost btn-xs" data-tact="start" data-id="${esc(t.id)}" title="Iniciar">${icon('play')}</button>` : ''}
          </div>
        </div>`).join('')}</div>`
      : emptyBlock('Sin tareas abiertas. Todo listo por ahora.')}`;

    function deliverableCell(d, selected) {
      const criteria = (d.acceptance_criteria || '').trim();
      const desc = criteria || d.title;
      return `
        <div class="deliverable-card ${selected ? 'selected' : ''}" data-deliverable-select="${esc(d.id)}">
          <div class="item-main">
            <div class="item-title">${esc(d.title)}</div>
            <div class="item-sub">${esc(desc.slice(0, 120))}${desc.length > 120 ? '…' : ''}</div>
          </div>
          <div class="item-side">
            <span class="badge badge-${esc(d.status)}"><span class="badge-dot"></span>${esc(humanStatus(d.status))}</span>
            ${d.evidence_url ? `<a class="btn btn-ghost btn-xs" href="${esc(d.evidence_url)}" target="_blank" rel="noopener">${icon('doc')} Evidencia</a>` : ''}
          </div>
        </div>`;
    }

    function deliverablesHtml(selectedId) {
      const selected = (deliverables || []).find((d) => d.id === selectedId) || (deliverables || [])[0];
      const rows = (deliverables || []).length
        ? `<div class="list">${(deliverables || []).map((d) => deliverableCell(d, d.id === (selected && selected.id))).join('')}</div>`
        : emptyBlock('Sin entregables registrados.');
      const checklist = selected ? (checklistCache.get(selected.id) || []) : [];
      const criteriaPkg = checklist.length
        ? checklist.map((c) => `
            <label class="check-item check-criterion ${c.done ? 'done' : ''}">
              <button class="check-box" data-check-toggle="${esc(c.id)}" aria-label="${c.done ? 'Quitar marca de cumplido' : 'Marcar como cumplido'}" type="button">${icon('check')}</button>
              <div class="item-main">
                <div class="item-title">${esc(c.text)}</div>
                <button class="btn btn-ghost btn-xs" data-check-remove="${esc(c.id)}" title="Eliminar criterio" type="button">${icon('trash')}</button>
              </div>
            </label>`).join('')
        : (selected && selected.acceptance_criteria
          ? `<p>${esc(selected.acceptance_criteria)}</p>`
          : '');
      const detail = selected
        ? `<div class="deliverable-detail card" data-deliverable-detail="1">
            <div class="detail-actions">
              <button class="btn btn-ghost btn-sm" data-check-add="${esc(selected.id)}" type="button">${icon('plus')} Añadir criterio</button>
              <button class="btn btn-primary btn-sm" data-deliverable-advance="${esc(selected.id)}" data-status="${esc(selected.status)}">
                ${icon('arrow')} ${selected.status === 'planned' ? 'Registrar avance' : selected.status === 'in_progress' ? 'Enviar a revisión' : 'Registrar avance'}
              </button>
            </div>
            <div class="item-title">${esc(selected.title)}</div>
            <div class="item-sub">Vence ${esc(fmtDate(selected.due_at))} · ${badge(selected.status)}</div>
            <div class="dv-criteria">
              <b>Criterios de aceptación</b>
              ${criteriaPkg || '<p>Sin criterios definidos todavía.</p>'}
            </div>
            ${selected.drive_url ? `<p class="dv-link">${icon('drive')} <a href="${esc(selected.drive_url)}" target="_blank" rel="noopener">Abrir documento en Drive</a></p>` : ''}
            ${selected.evidence_url ? `<p class="dv-link">${icon('doc')} <a href="${esc(selected.evidence_url)}" target="_blank" rel="noopener">Ver evidencia</a></p>` : ''}
          </div>`
        : emptyBlock('Selecciona un entregable para ver su detalle.');
      return `<div class="tab-head">
        <button class="btn btn-soft btn-sm" data-create="project-deliverable">${icon('plus')} Nuevo entregable</button>
      </div>
      ${rows}
      ${detail}`;
    }

    const meetingsHtml = (upcomingMeetings.length || pastMeetings.length)
      ? `<div class="list">${upcomingMeetings.concat(pastMeetings).slice(0, 12).map((m) => `
        <a class="item item-row" href="#/reuniones/${esc(m.id)}">
          <div class="item-main">
            <div class="item-title">${esc(m.title)}</div>
            <div class="item-sub">${esc(fmtDate(m.starts_at))} · ${esc(fmtTime(m.starts_at))}</div>
          </div>
          <div class="item-side">${badge(m.status)}</div>
        </a>`).join('')}</div>`
      : emptyBlock('Sin reuniones asociadas.');

    const filesHtml = links.length
      ? `<div class="list">${links.map((l) => `
        <div class="item">
          <div class="item-main">
            <div class="item-title">${esc(l.external_name || l.deliverable_title)}</div>
            <div class="item-sub">${esc(l.deliverable_title)} · ${esc(l.mime_type || 'documento')}${l.external_modified_at ? ` · mod. ${esc(fmtDate(l.external_modified_at))}` : ''}</div>
          </div>
          ${l.web_url ? `<a class="btn btn-ghost btn-xs" href="${esc(l.web_url)}" target="_blank" rel="noopener">Abrir</a>` : ''}
        </div>`).join('')}</div>`
      : emptyBlock('Sin documentos vinculados en Drive.', `<a class="btn btn-soft btn-sm" href="#/integraciones">Integraciones</a>`);

    const activityItems = (audit || []).map((e) => {
      const verbs = { create: 'creado', update: 'actualizado', delete: 'eliminado' };
      return { kind: e.entity_kind, verb: verbs[e.action] || e.action, at: e.occurred_at };
    });
    const activityHtml = activityItems.length
      ? `<div class="p-list">${activityItems.map((it) => `
        <li class="activity">
          <span class="activity-kind">${icon('clock')}</span>
          <div class="activity-body"><b>${esc(it.kind)}</b><span>${esc(it.verb)} · ${esc(timeAgo(it.at))}</span></div>
        </li>`).join('')}</div>`
      : emptyBlock('Sin actividad registrada.');

    const nextDue = [...openDeliverables].sort((a, b) => String(a.due_at).localeCompare(String(b.due_at)))[0]?.due_at;
    const soonDeliverables = openDeliverables.filter(
      (d) => d.due_at >= todayISO() && d.due_at <= addDaysISO(todayISO(), 7),
    );

    const resumenHtml = `
      <section class="card">
        <div class="card-head"><h2>${icon('folder')} Panorama del proyecto</h2></div>
        <div class="card-body">
          <div class="p-list">
            <div class="item"><div class="item-main"><span class="item-sub">Cliente</span></div><div class="item-side"><b>${esc(client || '—')}</b></div></div>
            ${workspace ? `<div class="item"><div class="item-main"><span class="item-sub">Espacio de trabajo</span></div><div class="item-side">${esc(workspace)}</div></div>` : ''}
            <div class="item"><div class="item-main"><span class="item-sub">Estado</span></div><div class="item-side">${badge(project.status)}${project.health && project.health !== 'unknown' ? badge(project.health) : ''}</div></div>
            <div class="item"><div class="item-main"><span class="item-sub">Siguiente vencimiento</span></div><div class="item-side">${nextDue ? esc(fmtDate(nextDue)) : '<span class="text-muted">sin fechas</span>'}</div></div>
            <div class="item"><div class="item-main"><span class="item-sub">Creado</span></div><div class="item-side"><span class="text-muted">${esc(fmtDate(project.created_at))}</span></div></div>
            <div class="item"><div class="item-main"><span class="item-sub">Tiempo registrado</span></div><div class="item-side"><b>${esc(formatMinutes(totalMinutes))}</b></div></div>
          </div>
        </div>
      </section>
      ${nextMeeting ? `<section class="card" style="margin-top:16px">
        <div class="card-head"><h2>${icon('calendar')} Próxima reunión</h2><a class="card-action" href="#/reuniones/${esc(nextMeeting.id)}">Abrir</a></div>
        <div class="card-body">
          <div class="item">
            <div class="item-main"><div class="item-title">${esc(nextMeeting.title)}</div>
            <div class="item-sub">${esc(fmtFullDate(nextMeeting.starts_at))} · ${esc(fmtTime(nextMeeting.starts_at))}</div></div>
          </div>
        </div>
      </section>` : ''}
      ${soonDeliverables.length ? `<section class="card" style="margin-top:16px"><div class="card-head"><h2>${icon('flag')} Vencimientos próximos</h2></div>
        <div class="card-body"><div class="list">${soonDeliverables.map((d) => `
          <div class="item"><div class="item-main"><div class="item-title">${esc(d.title)}</div>
          <div class="item-sub">Vence ${esc(fmtDate(d.due_at))}</div></div>${badge(d.status)}</div>`).join('')}</div></div></section>` : ''}
      ${!nextMeeting && !soonDeliverables.length ? emptyBlock('Sin movimientos próximos. Proyecto estable.') : ''}`;

    const tabs = [
      ['resumen', 'Resumen'],
      ['entregables', `Entregables${(deliverables || []).length ? ` (${(deliverables || []).length})` : ''}`],
      ['tareas', `Tareas${openTasks.length ? ` (${openTasks.length})` : ''}`],
      ['reuniones', 'Reuniones'],
      ['archivos', 'Archivos'],
      ['actividad', 'Actividad'],
    ];
    const current = new URLSearchParams(window.location.hash.split('?')[1] || '').get('tab') || 'resumen';
    let selectedDeliverable = (deliverables || [])[0] ? (deliverables || [])[0].id : null;
    const checklistCache = new Map();
    const loadChecklist = async (deliverableId) => {
      if (checklistCache.has(deliverableId)) return checklistCache.get(deliverableId);
      const items = await api(`/api/v1/deliverables/${encodeURIComponent(deliverableId)}/checklist`).catch(() => []);
      checklistCache.set(deliverableId, items || []);
      return checklistCache.get(deliverableId);
    };
    loadChecklist(selectedDeliverable).catch(() => {});

    const renderTabBody = (key) => {
      const body = el.querySelector('#project-tab-body');
      if (!body) return;
      if (key === 'resumen') body.innerHTML = resumenHtml;
      else if (key === 'entregables') body.innerHTML = deliverablesHtml(selectedDeliverable);
      else if (key === 'tareas') body.innerHTML = tasksHtml;
      else if (key === 'reuniones') body.innerHTML = meetingsHtml;
      else if (key === 'archivos') body.innerHTML = filesHtml;
      else if (key === 'actividad') body.innerHTML = activityHtml;
    };

    const sideHtml = `
      <section class="card side-card">
        <div class="card-head"><h2>${icon('calendar')} Próxima reunión</h2></div>
        <div class="card-body">
          ${nextMeeting
            ? `<div class="item">
                <div class="item-main">
                  <div class="item-title">${esc(nextMeeting.title)}</div>
                  <div class="item-sub">${esc(fmtDate(nextMeeting.starts_at))} · ${esc(fmtTime(nextMeeting.starts_at))}</div>
                </div>
              </div>
              <div class="side-actions">
                <button class="btn btn-primary btn-sm" data-meeting-prepare="${esc(nextMeeting.id)}">${icon('sparkles')} Preparar reunión</button>
              </div>`
            : emptyBlock('Sin reuniones programadas para este proyecto.')}
        </div>
      </section>
      <section class="card side-card">
        <div class="card-head"><h2>${icon('list')} Compromisos pendientes</h2>${commitments.length ? `<span class="card-badge">${commitments.length}</span>` : ''}</div>
        <div class="card-body">
          ${commitments.length
            ? `<div class="p-list">${commitments.slice(0, 4).map((ai) => `
                <div class="item item-row">
                  <div class="item-main">
                    <div class="item-title">${esc(ai.title)}</div>
                    <div class="item-sub">de ${esc(ai.owner || 'la reunión')}</div>
                  </div>
                  <div class="item-side">
                    <button class="btn btn-soft btn-xs" data-action-convert="${esc(ai.id)}" title="Convertir en tarea">${icon('check')} Tarea</button>
                  </div>
                </div>`).join('')}</div>`
            : emptyBlock('Sin compromisos abiertos.')}
        </div>
      </section>
      <section class="card side-card">
        <div class="card-head"><h2>${icon('clock')} Tiempo registrado hoy</h2></div>
        <div class="card-body">
          <div class="kpi-value">${esc(formatMinutes(todayMinutes))}</div>
          <span class="kpi-label">${formatMinutes(totalMinutes)} en total</span>
          <div class="side-actions">
            <button class="btn btn-primary btn-sm" data-worklog-create="1">${icon('plus')} Registrar tiempo</button>
          </div>
        </div>
      </section>`;

    el.innerHTML = `
      <nav class="crumbs" aria-label="Ubicación">
        <a href="#/mi-dia">Inicio</a><span class="crumb-sep">/</span>
        <a href="#/proyectos">Proyectos</a><span class="crumb-sep">/</span>
        <span>${esc(project.name)}</span>
      </nav>
      <div class="detail-head">
        <div class="page-greeting">
          <h1>${esc(project.name)}</h1>
          <div class="detail-meta">
            ${client ? `<span class="detail-meta-item">${icon('folder')} ${esc(client)}</span>` : ''}
            ${workspace ? `<span class="detail-meta-item">${icon('link')} ${esc(workspace)}</span>` : ''}
            <span class="item-side">${badge(project.status)}${project.health && project.health !== 'unknown' ? badge(project.health) : ''}</span>
          </div>
        </div>
        <div class="detail-actions">
          <button class="btn btn-soft" data-create="project-task">${icon('plus')} Tarea</button>
          <button class="btn btn-primary" data-create="project-deliverable">${icon('plus')} Entregable</button>
        </div>
      </div>
      <section class="kpi-row">
        ${kpiCard(acceptedDeliverables, 'Entregables aceptados', 'doc', `#/proyectos/${esc(project.id)}?tab=entregables`)}
        ${kpiCard(doneCount, 'Tareas completadas', 'check', `#/proyectos/${esc(project.id)}?tab=tareas`, 'kpi-icon--success')}
        ${kpiCard(formatMinutes(totalMinutes), 'Tiempo registrado', 'clock', `#/proyectos/${esc(project.id)}`)}
        ${kpiCard(blocked, 'Bloqueos', 'alert', `#/proyectos/${esc(project.id)}?tab=tareas`, blocked ? 'kpi-icon--danger' : '')}
      </section>
      <div class="split-70-30">
        <div class="split-main">
          <div class="tabs" role="tablist" aria-label="Secciones del proyecto">
            ${tabs.map(([key, label]) => `<button class="tab ${key === current ? 'active' : ''}" data-tab="${key}" role="tab" aria-selected="${key === current ? 'true' : 'false'}">${esc(label)}</button>`).join('')}
          </div>
          <div id="project-tab-body"></div>
        </div>
        <div class="split-side">${sideHtml}</div>
      </div>`;
    renderTabBody(current);

    if (!el.dataset.viewBound) {
      el.dataset.viewBound = '1';
      el.addEventListener('click', async (event) => {
        const tabBtn = event.target.closest('[data-tab]');
        if (tabBtn) {
          const key = tabBtn.dataset.tab;
          el.querySelectorAll('.tab').forEach((t) => {
            t.classList.toggle('active', t === tabBtn);
            t.setAttribute('aria-selected', t === tabBtn ? 'true' : 'false');
          });
          const nextHash = `#/proyectos/${encodeURIComponent(projectId)}?tab=${encodeURIComponent(key)}`;
          if (window.location.hash !== nextHash) history.replaceState(null, '', nextHash);
          renderTabBody(key);
          return;
        }
        const delSel = event.target.closest('[data-deliverable-select]');
        if (delSel) {
          selectedDeliverable = delSel.dataset.deliverableSelect;
          el.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === 'entregables'));
          await loadChecklist(selectedDeliverable);
          renderTabBody('entregables');
          return;
        }
        const checkToggle = event.target.closest('[data-check-toggle]');
        if (checkToggle) {
          const item = checklistCache.get(selectedDeliverable)?.find((c) => c.id === checkToggle.dataset.checkToggle);
          if (!item) return;
          try {
            await api(`/api/v1/deliverables/checklist/${encodeURIComponent(item.id)}`, {
              method: 'PATCH',
              body: JSON.stringify({ done: !item.done }),
            });
            item.done = !item.done;
            toast(item.done ? 'Criterio cumplido' : 'Criterio marcado como pendiente', 'success');
            renderTabBody('entregables');
          } catch (err) {
            toast(`No se pudo actualizar: ${err.message}`, 'error');
          }
          return;
        }
        const checkAdd = event.target.closest('[data-check-add]');
        if (checkAdd) {
          const deliverableId = checkAdd.dataset.checkAdd;
          const form = await openForm({
            title: 'Añadir criterio de aceptación',
            submitLabel: 'Añadir',
            fields: [
              { name: 'text', label: 'Criterio', required: true, placeholder: 'Ej. Los datos migrados coinciden con la fuente' },
            ],
          });
          if (!form) return;
          try {
            const created = await api(`/api/v1/deliverables/${encodeURIComponent(deliverableId)}/checklist`, {
              method: 'POST',
              body: JSON.stringify({
                id: genEntityId('dcl', form.text),
                deliverable_id: deliverableId,
                text: form.text,
                done: false,
                position: 0,
              }),
            });
            const items = checklistCache.get(deliverableId) || [];
            items.push(created);
            checklistCache.set(deliverableId, items);
            toast('Criterio añadido', 'success');
            renderTabBody('entregables');
          } catch (err) {
            toast(`No se pudo añadir: ${err.message}`, 'error');
          }
          return;
        }
        const checkRemove = event.target.closest('[data-check-remove]');
        if (checkRemove) {
          const itemId = checkRemove.dataset.checkRemove;
          try {
            await api(`/api/v1/deliverables/checklist/${encodeURIComponent(itemId)}`, { method: 'DELETE' });
            checklistCache.set(
              selectedDeliverable,
              (checklistCache.get(selectedDeliverable) || []).filter((c) => c.id !== itemId),
            );
            toast('Criterio eliminado', 'success');
            renderTabBody('entregables');
          } catch (err) {
            toast(`No se pudo eliminar: ${err.message}`, 'error');
          }
          return;
        }
        const advance = event.target.closest('[data-deliverable-advance]');
        if (advance) {
          const id = advance.dataset.deliverableAdvance;
          const status = advance.dataset.status;
          advance.disabled = true;
          try {
            if (status === 'planned') {
              await api(`/api/v1/deliverables/${encodeURIComponent(id)}`, {
                method: 'PATCH',
                body: JSON.stringify({ status: 'in_progress' }),
              });
              toast('Avance registrado', 'success');
            } else if (status === 'in_progress') {
              await api(`/api/v1/deliverables/${encodeURIComponent(id)}/review`, { method: 'POST' });
              toast('Entregable enviado a revisión', 'success');
            } else {
              await api(`/api/v1/deliverables/${encodeURIComponent(id)}/review`, { method: 'POST' });
              toast('Entregable enviado a revisión', 'success');
            }
          } catch (err) {
            toast(`No se pudo actualizar: ${err.message}`, 'error');
          }
          invalidate('deliverables');
          renderProyectoDetalle(el, projectId);
          return;
        }
        const createTask = event.target.closest('[data-create="project-task"]');
        if (createTask) {
          const form = await openForm({
            title: 'Nueva tarea',
            submitLabel: 'Crear tarea',
            fields: [
              { name: 'title', label: 'Título', required: true, placeholder: 'Ej. Preparar demo' },
              {
                name: 'priority',
                label: 'Prioridad',
                type: 'select',
                value: 'medium',
                options: ['critical', 'high', 'medium', 'low'].map((s) => ({ value: s, label: humanStatus(s) })),
              },
              { name: 'due', label: 'Vence', type: 'date' },
            ],
          });
          if (!form) return;
          try {
            await api('/api/v1/tasks', {
              method: 'POST',
              body: JSON.stringify({
                id: genEntityId('tsk', form.title),
                project_id: projectId,
                title: form.title,
                status: 'ready',
                priority: form.priority || 'medium',
                ...(form.due ? { due_at: form.due } : {}),
              }),
            });
            toast('Tarea creada', 'success');
          } catch (err) {
            toast(`No se pudo crear la tarea: ${err.message}`, 'error');
          }
          invalidate('tasks');
          renderProyectoDetalle(el, projectId);
          return;
        }
        const createDeliverable = event.target.closest('[data-create="project-deliverable"]');
        if (createDeliverable) {
          const form = await openForm({
            title: 'Nuevo entregable',
            submitLabel: 'Crear entregable',
            fields: [
              { name: 'title', label: 'Título', required: true, placeholder: 'Ej. Documento de arquitectura' },
              { name: 'due', label: 'Vence', type: 'date', required: true },
              { name: 'drive', label: 'URL en Drive (opcional)', placeholder: 'https://drive.google.com/…' },
            ],
          });
          if (!form) return;
          try {
            await api('/api/v1/deliverables', {
              method: 'POST',
              body: JSON.stringify({
                id: genEntityId('del', form.title),
                project_id: projectId,
                title: form.title,
                status: 'planned',
                due_at: form.due,
                ...(form.drive ? { drive_url: form.drive } : {}),
              }),
            });
            toast('Entregable creado', 'success');
          } catch (err) {
            toast(`No se pudo crear el entregable: ${err.message}`, 'error');
          }
          invalidate('deliverables');
          renderProyectoDetalle(el, projectId);
          return;
        }
        const prepare = event.target.closest('[data-meeting-prepare]');
        if (prepare) {
          const meetingId = prepare.dataset.meetingPrepare;
          prepare.disabled = true;
          try {
            const prep = await api(`/api/v1/meetings/${encodeURIComponent(meetingId)}/preparation`);
            const points = [
              ...(prep.open_action_items || []).map((ai) => ai.title),
              ...(prep.task_deadlines || []).map((t) => `Vence: ${t.title}`),
              ...(prep.deliverable_deadlines || []).map((d) => `Entregable: ${d.title}`),
            ];
            const list = points.length
              ? `<div class="p-list">${points.slice(0, 6).map((p) => `<li class="activity"><span class="activity-kind">${icon('check')}</span><div class="activity-body"><span>${esc(p)}</span></div></li>`).join('')}</div>`
              : emptyBlock('Sin puntos preparados para esta reunión.');
            const overlay = document.createElement('div');
            overlay.className = 'overlay';
            overlay.innerHTML = `
              <div class="modal modal-sm" role="dialog" aria-modal="true" aria-labelledby="mp-title">
                <header class="modal-head"><h3 id="mp-title">Preparación de reunión</h3>
                  <button class="icon-btn" type="button" data-mp="cancel" aria-label="Cerrar">${icon('x')}</button></header>
                <div class="modal-body">
                  <div class="item-title">${esc(prep.meeting?.title || 'Reunión')}</div>
                  <div class="item-sub">generada ${esc(fmtDate(prep.prepared_at))}</div>
                  ${list}
                  <div class="modal-actions"><button class="btn btn-primary" type="button" data-mp="ok">Entendido</button></div>
                </div>
              </div>`;
            document.body.appendChild(overlay);
            overlay.addEventListener('click', (e) => {
              if (e.target.closest('[data-mp]') || e.target === overlay) overlay.remove();
            });
          } catch (err) {
            toast(`No se pudo preparar la reunión: ${err.message}`, 'error');
          }
          prepare.disabled = false;
          return;
        }
        const convert = event.target.closest('[data-action-convert]');
        if (convert) {
          const ai = commitments.find((c) => c.id === convert.dataset.actionConvert);
          const form = await openForm({
            title: 'Convertir en tarea',
            submitLabel: 'Crear tarea',
            fields: [
              { name: 'title', label: 'Título', required: true, value: (ai && ai.title) || '', placeholder: 'Título de la tarea' },
              {
                name: 'priority',
                label: 'Prioridad',
                type: 'select',
                value: 'medium',
                options: ['critical', 'high', 'medium', 'low'].map((s) => ({ value: s, label: humanStatus(s) })),
              },
              { name: 'due', label: 'Vence', type: 'date' },
            ],
          });
          if (!form || !ai) return;
          try {
            await api(`/api/v1/action-items/${encodeURIComponent(ai.id)}/task`, {
              method: 'POST',
              body: JSON.stringify({
                task_id: genEntityId('tsk', form.title),
                priority: form.priority || 'medium',
                ...(form.due ? { due_at: form.due } : {}),
              }),
            });
            toast('Compromiso convertido en tarea', 'success');
          } catch (err) {
            toast(`No se pudo convertir: ${err.message}`, 'error');
          }
          invalidate('tasks');
          renderProyectoDetalle(el, projectId);
          return;
        }
        const worklogBtn = event.target.closest('[data-worklog-create]');
        if (worklogBtn) {
          const form = await openForm({
            title: 'Registrar tiempo',
            submitLabel: 'Guardar',
            fields: [
              {
                name: 'task_id',
                label: 'Tarea',
                type: 'select',
                required: true,
                options: openTasks.map((t) => ({ value: t.id, label: t.title })),
              },
              { name: 'minutes', label: 'Minutos', required: true, placeholder: '45', maxlength: '8' },
              { name: 'summary', label: 'Resumen', required: true, placeholder: 'Qué avanzaste…', maxlength: '5000' },
            ],
          });
          if (!form) return;
          const minutes = parseInt(form.minutes, 10);
          if (!minutes || minutes < 1) {
            toast('Indica un número de minutos válido', 'error');
            return;
          }
          try {
            await api(`/api/v1/tasks/${encodeURIComponent(form.task_id)}/work-logs`, {
              method: 'POST',
              body: JSON.stringify({ minutes, summary: form.summary }),
            });
            toast('Tiempo registrado', 'success');
          } catch (err) {
            toast(`No se pudo registrar: ${err.message}`, 'error');
          }
          renderProyectoDetalle(el, projectId);
          return;
        }
        const taskBtn = event.target.closest('[data-tact]');
        if (!taskBtn) return;
        taskBtn.disabled = true;
        const taskId = taskBtn.dataset.id;
        try {
          if (taskBtn.dataset.tact === 'complete') {
            const note = await promptCompletionNote();
            if (note === null) { taskBtn.disabled = false; return; }
            await api(`/api/v1/tasks/${encodeURIComponent(taskId)}/complete`, {
              method: 'POST',
              body: JSON.stringify(note ? { completion_note: note } : {}),
            });
            toast('Tarea completada', 'success');
          } else if (taskBtn.dataset.tact === 'start') {
            await api(`/api/v1/tasks/${encodeURIComponent(taskId)}/start`, { method: 'POST' });
            toast('Tarea iniciada', 'success');
          }
        } catch (err) {
          toast(err.message, 'error');
        }
        invalidate('tasks');
        renderProyectoDetalle(el, projectId);
      });
    }
  } catch (err) {
    el.innerHTML = errorBlock(`Proyecto no disponible: ${esc(err.message)}`);
  }
}

/* ============================================================
   TAREAS
   ============================================================ */

export async function renderTareas(el) {
  setPageTitle('Tareas');
  const params = new URLSearchParams(window.location.hash.split('?')[1] || '');
  el.innerHTML = `
    <div class="page-head"><h1>Tareas</h1><p class="page-sub">Todas las tareas de tu trabajo.</p></div>
    ${skeleton(6)}`;
  try {
    const [tasks, projects, maps] = await Promise.all([listTasks(), listProjects(), nameMaps()]);
    let filtered = tasks || [];
    const statusFilter = params.get('status');
    if (statusFilter === 'overdue') {
      const today = todayISO();
      filtered = filtered.filter(
        (t) => t.due_at && t.due_at < today && !['done', 'cancelled'].includes(t.status),
      );
    } else if (statusFilter === 'due_soon') {
      filtered = filtered.filter((t) => t.due_at === todayISO() && !['done', 'cancelled'].includes(t.status));
    } else if (statusFilter === 'blocked') {
      filtered = filtered.filter((t) => t.status === 'blocked');
    }
    const statuses = ['inbox', 'ready', 'in_progress', 'blocked', 'done', 'cancelled'];
    const statusOpts = `<option value="">Todos los estados</option>${statuses
      .map((s) => `<option value="${s}">${esc(humanStatus(s))}</option>`)
      .join('')}`;
    const prios = ['critical', 'high', 'medium', 'low'];
    const prioOpts = `<option value="">Toda prioridad</option>${prios
      .map((s) => `<option value="${s}">${esc(s)}</option>`)
      .join('')}`;

    const rows = filtered.length
      ? filtered
          .map(
            (t) => `
          <div class="item item-row">
            <div class="item-main">
              <div class="item-title">${t.project_id ? `<a href="#/proyectos/${esc(t.project_id)}?tab=tareas">${esc(t.title)}</a>` : esc(t.title)}</div>
              <div class="item-sub">${esc(taskContext(t, maps))}${t.due_at ? ` · vence ${esc(fmtDate(t.due_at))}` : ''}</div>
            </div>
            <div class="item-side">${prio(t.priority)}${badge(t.status)}</div>
            <div class="item-actions">
              ${t.status !== 'done' ? `<button class="btn btn-success-soft btn-xs" data-act="complete" data-id="${esc(t.id)}">Completar</button>` : ''}
            </div>
          </div>`,
          )
          .join('')
      : emptyBlock('Sin tareas que mostrar aquí.');
    el.innerHTML = `
      <div class="page-head"><h1>Tareas</h1><p class="page-sub">${plural(filtered.length, 'tarea', 'tareas')} en la vista actual.</p>
        <div class="page-head-actions">
          <button class="btn btn-primary btn-sm" data-create="task">${icon('plus')} Nueva tarea</button>
        </div>
      </div>
      <div class="filterbar">
        <select class="f-filter f-status">${statusOpts}</select>
        <select class="f-filter f-prio">${prioOpts}</select>
        <a class="btn btn-ghost btn-sm" href="#/tareas">Limpiar</a>
      </div>
      <section class="card no-pad"><div class="card-body"><div class="task-list">${rows}</div></div></section>`;

    const applyFilters = () => {
      const status = el.querySelector('.f-status').value;
      const prioVal = el.querySelector('.f-prio').value;
      let out = (tasks || []).slice();
      if (status) out = out.filter((t) => t.status === status);
      if (prioVal) out = out.filter((t) => t.priority === prioVal);
      const list = out.length
        ? out
            .map(
              (t) => `
            <div class="item item-row">
              <div class="item-main">
                <div class="item-title">${t.project_id ? `<a href="#/proyectos/${esc(t.project_id)}?tab=tareas">${esc(t.title)}</a>` : esc(t.title)}</div>
                <div class="item-sub">${esc(taskContext(t, maps))}${t.due_at ? ` · vence ${esc(fmtDate(t.due_at))}` : ''}</div>
              </div>
              <div class="item-side">${prio(t.priority)}${badge(t.status)}</div>
              <div class="item-actions">
                ${t.status !== 'done' ? `<button class="btn btn-success-soft btn-xs" data-act="complete" data-id="${esc(t.id)}">Completar</button>` : ''}
              </div>
            </div>`,
            )
            .join('')
        : emptyBlock('Sin tareas que mostrar aquí.');
      const listNode = el.querySelector('.task-list');
      if (listNode) listNode.innerHTML = list;
    };
    if (!el.dataset.viewBound) {
      el.dataset.viewBound = '1';
      el.addEventListener('change', (event) => {
        if (event.target.classList.contains('f-filter')) applyFilters();
      });
      el.addEventListener('click', async (event) => {
        const createBtn = event.target.closest('[data-create="task"]');
        if (createBtn) {
          const form = await openForm({
            title: 'Nueva tarea',
            submitLabel: 'Crear tarea',
            fields: [
              { name: 'title', label: 'Título', required: true, placeholder: 'Ej. Preparar demo para el cliente' },
              {
                name: 'project',
                label: 'Proyecto',
                type: 'select',
                required: true,
                options: (projects || []).map((p) => ({ value: p.id, label: p.name })),
              },
              {
                name: 'priority',
                label: 'Prioridad',
                type: 'select',
                value: 'medium',
                options: ['critical', 'high', 'medium', 'low'].map((s) => ({ value: s, label: humanStatus(s) })),
              },
              { name: 'due', label: 'Vence', type: 'date' },
            ],
          });
          if (!form) return;
          try {
            await api('/api/v1/tasks', {
              method: 'POST',
              body: JSON.stringify({
                id: genEntityId('tsk', form.title),
                project_id: form.project,
                title: form.title,
                status: 'ready',
                priority: form.priority || 'medium',
                ...(form.due ? { due_at: form.due } : {}),
              }),
            });
            toast('Tarea creada', 'success');
          } catch (err) {
            toast(`No se pudo crear la tarea: ${err.message}`, 'error');
          }
          invalidate('tasks');
          invalidate('projects');
          renderTareas(el);
          return;
        }
        const btn = event.target.closest('[data-act="complete"]');
        if (!btn) return;
        const note = await promptCompletionNote();
        if (note === null) return;
        btn.disabled = true;
        try {
          await api(`/api/v1/tasks/${encodeURIComponent(btn.dataset.id)}/complete`, {
            method: 'POST',
            body: JSON.stringify(note ? { completion_note: note } : {}),
          });
          toast('Tarea completada', 'success');
        } catch (err) {
          toast(err.message, 'error');
        }
        invalidate('tasks');
        renderTareas(el);
      });
    }
  } catch (err) {
    el.innerHTML = errorBlock(`No se pudieron cargar las tareas: ${esc(err.message)}`);
  }
}

/* ============================================================
   REUNIONES
   ============================================================ */

export async function renderReuniones(el) {
  setPageTitle('Reuniones');
  el.innerHTML = `
    <div class="page-head"><h1>Reuniones</h1><p class="page-sub">Próximas, pasadas y pendientes de revisión.</p></div>
    ${skeleton(5)}`;
  try {
    const [meetings, unmatched, completedQueue, projects, maps] = await Promise.all([
      listMeetings(),
      api('/api/v1/integrations/meetings/unmatched'),
      api('/api/v1/integrations/meetings/completed'),
      listProjects(),
      nameMaps(),
    ]);
    const now = new Date().toISOString();
    const upcoming = (meetings || [])
      .filter((m) => m.status === 'scheduled')
      .sort((a, b) => String(a.starts_at).localeCompare(String(b.starts_at)));
    const past = (meetings || [])
      .filter((m) => m.status !== 'scheduled')
      .sort((a, b) => String(b.starts_at).localeCompare(String(a.starts_at)));

    const row = (m) => `
      <a class="item item-row" href="#/reuniones/${esc(m.id)}">
        <div class="item-main">
          <div class="item-title">${esc(m.title)}</div>
          <div class="item-sub">${esc(fmtDate(m.starts_at))} · ${esc(fmtTime(m.starts_at))}${m.project_id ? ` · ${esc(maps.project[m.project_id] || m.project_id)}` : ' · <b class="text-danger">sin proyecto</b>'}</div>
        </div>
        <div class="item-side">${badge(m.status)}</div>
      </a>`;

    const queue = (unmatched || []).length
      ? `<div class="list">${(unmatched || [])
          .map(
            (m) => `
          <div class="item">
            <div class="item-main">
              <div class="item-title"><a href="#/reuniones/${esc(m.id)}">${esc(m.title)}</a></div>
              <div class="item-sub">${esc(fmtDate(m.starts_at))} · importada</div>
            </div>
            <div class="item-side item-actions">
              <select class="select-small" data-mid="${esc(m.id)}" aria-label="Asignar proyecto">
                <option value="">Elige proyecto…</option>
                ${(projects || []).map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}
              </select>
              <button class="btn btn-primary btn-xs" data-act="associate" data-mid="${esc(m.id)}" disabled>Confirmar</button>
            </div>
          </div>`,
          )
          .join('')}</div>`
      : emptyBlock('Sin reuniones sin proyecto.');

    const reviewed = (completedQueue || []).length
      ? `<div class="list">${(completedQueue || [])
          .map(
            (m) => `
          <div class="item">
            <div class="item-main">
              <div class="item-title"><a href="#/reuniones/${esc(m.id)}">${esc(m.title)}</a></div>
              <div class="item-sub">${esc(fmtDate(m.starts_at))} · completada</div>
            </div>
            <button class="btn btn-primary btn-xs" data-act="review" data-mid="${esc(m.id)}">${icon('check')} Revisada</button>
          </div>`,
          )
          .join('')}</div>`
      : emptyBlock('Sin reuniones por revisar.');

    el.innerHTML = `
      <div class="page-head"><h1>Reuniones</h1><p class="page-sub">${plural(upcoming.length, 'próxima', 'próximas')} · ${plural((unmatched || []).length + (completedQueue || []).length, 'requiere revisión', 'requieren revisión')}</p>
        <div class="page-head-actions">
          <button class="btn btn-primary btn-sm" data-create="meeting">${icon('plus')} Nueva reunión</button>
        </div>
      </div>
      <section class="card">
        <div class="card-head"><h2>${icon('calendar')} Próximas</h2></div>
        <div class="card-body">${upcoming.length ? `<div class="list">${upcoming.map(row).join('')}</div>` : emptyBlock('Sin reuniones próximas.')}</div>
      </section>
      <section class="card" style="margin-top:16px">
        <div class="card-head"><h2>${icon('flag')} Requieren revisión · sin proyecto</h2></div>
        <div class="card-body">${queue}</div>
      </section>
      <section class="card" style="margin-top:16px">
        <div class="card-head"><h2>${icon('check')} Completadas por revisar</h2></div>
        <div class="card-body">${reviewed}</div>
      </section>
      <section class="card" style="margin-top:16px">
        <div class="card-head"><h2>${icon('clock')} Pasadas</h2></div>
        <div class="card-body">${past.length ? `<div class="list">${past.slice(0, 12).map(row).join('')}</div>` : emptyBlock('Sin reuniones pasadas.')}</div>
      </section>`;

    if (!el.dataset.viewBound) {
      el.dataset.viewBound = '1';
      el.addEventListener('click', async (event) => {
        const createBtn = event.target.closest('[data-create="meeting"]');
        if (createBtn) {
          const form = await openForm({
            title: 'Nueva reunión',
            submitLabel: 'Crear reunión',
            fields: [
              { name: 'title', label: 'Título', required: true, placeholder: 'Ej. Revisión de sprint' },
              {
                name: 'project',
                label: 'Proyecto',
                type: 'select',
                options: [{ value: '', label: 'Sin proyecto' }].concat((projects || []).map((p) => ({ value: p.id, label: p.name }))),
              },
              { name: 'starts', label: 'Fecha y hora', type: 'datetime-local', required: true },
            ],
          });
          if (!form) return;
          try {
            await api('/api/v1/meetings', {
              method: 'POST',
              body: JSON.stringify({
                id: genEntityId('mtg', form.title),
                title: form.title,
                starts_at: form.starts,
                status: 'scheduled',
                ...(form.project ? { project_id: form.project } : {}),
              }),
            });
            toast('Reunión creada', 'success');
          } catch (err) {
            toast(`No se pudo crear la reunión: ${err.message}`, 'error');
          }
          invalidate('meetings');
          renderReuniones(el);
          return;
        }
        const btn = event.target.closest('[data-act]');
        if (!btn) return;
        btn.disabled = true;
        const mid = btn.dataset.mid;
        try {
          if (btn.dataset.act === 'associate') {
            const select = el.querySelector(`[data-mid="${mid}"]`);
            if (!select.value) { btn.disabled = false; return; }
            await api(`/api/v1/integrations/meetings/${encodeURIComponent(mid)}/project`, {
              method: 'POST',
              body: JSON.stringify({ project_id: select.value }),
            });
            toast('Reunión asignada', 'success');
          } else if (btn.dataset.act === 'review') {
            await api(`/api/v1/meetings/${encodeURIComponent(mid)}/review`, {
              method: 'POST',
              body: JSON.stringify({ decision: 'reviewed' }),
            });
            toast('Reunión marcada como revisada', 'success');
          }
        } catch (err) {
          toast(err.message, 'error');
        }
        invalidate('meetings');
        renderReuniones(el);
      });
      el.addEventListener('change', (event) => {
        const select = event.target.closest('.select-small');
        if (!select) return;
        const btn = el.querySelector(`[data-act="associate"][data-mid="${select.dataset.mid}"]`);
        if (btn) btn.disabled = !select.value;
      });
    }
  } catch (err) {
    el.innerHTML = errorBlock(`No se pudieron cargar las reuniones: ${esc(err.message)}`);
  }
}

/* ============================================================
   REUNIÓN — DETALLE / MEETING BRIEF  (FASE UI-6)
   ============================================================ */

export async function renderReunionDetalle(el, meetingId) {
  setPageTitle('Reunión');
  el.innerHTML = skeleton(6);
  try {
    const [meeting, preparation, actionItems, maps] = await Promise.all([
      api(`/api/v1/meetings/${encodeURIComponent(meetingId)}`),
      api(`/api/v1/meetings/${encodeURIComponent(meetingId)}/preparation`),
      api(`/api/v1/action-items?meeting_id=${encodeURIComponent(meetingId)}`),
      nameMaps(),
    ]);
    const projectId = meeting.project_id;
    const project = maps.project[projectId];
    const clientId = projectId ? maps.projectClient[projectId] : null;
    const client = clientId ? maps.client[clientId] : '';
    const workspace = clientId ? maps.workspace[maps.clientWorkspace[clientId]] : '';
    const prep = preparation || {};
    const taskDeadlines = prep.task_deadlines || [];
    const deliverableDeadlines = prep.deliverable_deadlines || [];
    const openActions = prep.open_action_items || [];
    const links = prep.artifact_links || [];
    const isCompleted = meeting.status === 'completed';

    const briefBlocks = `
      ${taskDeadlines.length ? `<div class="brief-block"><h4>${icon('check')} Tareas abiertas con vencimiento</h4><div class="list">${taskDeadlines.map((t) => `
        <div class="item"><div class="item-main"><div class="item-title">${esc(t.title)}</div>
        <div class="item-sub">Vence ${esc(fmtDate(t.due_at))} · ${esc(maps.project[t.project_id] || '')}</div></div>
        ${prio(t.priority)}</div>`).join('')}</div></div>` : ''}
      ${deliverableDeadlines.length ? `<div class="brief-block"><h4>${icon('doc')} Entregables cercanos</h4><div class="list">${deliverableDeadlines.map((d) => `
        <div class="item"><div class="item-main"><div class="item-title">${esc(d.title)}</div>
        <div class="item-sub">Vence ${esc(fmtDate(d.due_at))}</div></div>${badge(d.status)}</div>`).join('')}</div></div>` : ''}
      ${openActions.length ? `<div class="brief-block"><h4>${icon('flag')} Acciones pendientes de esta reunión</h4><div class="list">${openActions.map((a) => `
        <div class="item"><div class="item-main"><div class="item-title">${esc(a.title)}</div>
        <div class="item-sub">Owner: ${esc(a.owner)}</div></div>${badge(a.status)}</div>`).join('')}</div></div>` : ''}
      ${links.length ? `<div class="brief-block"><h4>${icon('drive')} Documentos relevantes</h4><div class="list">${links.map((l) => `
        <div class="item"><div class="item-main"><div class="item-title">${esc(l.external_name || l.deliverable_title)}</div>
        <div class="item-sub">${esc(l.deliverable_title)} · ${esc(l.mime_type || 'documento')}</div></div>
        ${l.web_url ? `<a class="btn btn-ghost btn-xs" href="${esc(l.web_url)}" target="_blank" rel="noopener">Abrir</a>` : ''}</div>`).join('')}</div></div>` : ''}
    `;

    const decisionActions = (actionItems || []).length
      ? `<div class="list">${(actionItems || []).map((a) => `
        <div class="item">
          <div class="item-main"><div class="item-title">${esc(a.title)}</div>
          <div class="item-sub">Owner: ${esc(a.owner)}${a.task_id ? ` · <a href="#/proyectos">vinculada a tarea</a>` : ' · sin tarea vinculada'}</div></div>
          ${badge(a.status)}
        </div>`).join('')}</div>`
      : emptyBlock('Sin action items registrados para esta reunión.');

    const meetingActions = `
      ${!isCompleted ? `<button class="btn btn-primary" data-mact="complete">${icon('check')} Completar reunión</button>` : ''}
      ${isCompleted && !meeting.reviewed_at ? `<button class="btn btn-soft" data-mact="review">${icon('check')} Marcar revisada</button>` : ''}
      ${meeting.project_id ? `<a class="btn btn-ghost" href="#/proyectos/${esc(meeting.project_id)}">${icon('folder')} Proyecto</a>` : ''}
    `;

    el.innerHTML = `
      <div class="page-head detail-head">
        <a class="btn btn-ghost btn-xs back-link" href="#/reuniones">${icon('arrow')} Reuniones</a>
        <div class="page-greeting"><h1>${esc(meeting.title)}</h1>
          <span class="date-line">· ${esc(fmtDate(meeting.starts_at))} ${esc(fmtTime(meeting.starts_at))}</span></div>
        <div class="detail-meta">
          ${project ? `<span class="detail-meta-item">${icon('folder')} ${esc(project)}</span>` : `<span class="detail-meta-item">${icon('info')} Sin proyecto asociado</span>`}
          ${client ? `<span class="detail-meta-item">${icon('link')} ${esc(client)}</span>` : ''}
          ${workspace ? `<span class="detail-meta-item">${icon('link')} ${esc(workspace)}</span>` : ''}
          <span class="item-side">${badge(meeting.status)}${isCompleted && meeting.reviewed_at ? badge('reviewed') : ''}</span>
        </div>
        <div class="detail-actions">${meetingActions}</div>
      </div>
      ${meeting.status === 'completed' ? `
        <section class="card brief-card">
          <div class="card-head"><h2>${icon('flag')} Notas · Decisiones · Action items</h2></div>
          <div class="card-body">${decisionActions}</div>
        </section>` : meeting.status === 'cancelled' ? `
        <section class="card brief-card">
          <div class="card-body">${emptyBlock('Esta reunión fue cancelada.')}</div>
        </section>` : `
        <section class="card brief-card">
          <div class="card-head"><h2>${icon('sparkles')} Meeting brief</h2>
            <span class="brief-card-note">Preparación generada ${esc(timeAgo(prep.prepared_at || new Date()))}</span></div>
          <div class="card-body">
            <p class="brief-intro">Objetivo de la reunión y estado actual antes de entrar.</p>
            ${briefBlocks || emptyBlock('No hay datos adicionales para preparar la reunión.')}
          </div>
        </section>`}
    `;

    if (!el.dataset.viewBound) {
      el.dataset.viewBound = '1';
      el.addEventListener('click', async (event) => {
        const btn = event.target.closest('[data-mact]');
        if (!btn) return;
        btn.disabled = true;
        const id = meetingId;
        try {
          if (btn.dataset.mact === 'complete') {
            await api(`/api/v1/meetings/${encodeURIComponent(id)}/complete`, { method: 'POST', body: '{}' });
            toast('Reunión completada', 'success');
          } else if (btn.dataset.mact === 'review') {
            await api(`/api/v1/meetings/${encodeURIComponent(id)}/review`, { method: 'POST', body: '{}' });
            toast('Reunión marcada como revisada', 'success');
          }
        } catch (err) {
          toast(err.message, 'error');
        }
        invalidate('meetings');
        renderReunionDetalle(el, id);
      });
    }
  } catch (err) {
    el.innerHTML = errorBlock(`Reunión no disponible: ${esc(err.message)}`);
  }
}

/* ============================================================
   CALENDARIO  (agenda de los próximos días)
   ============================================================ */

export async function renderCalendario(el) {
  setPageTitle('Calendario');
  el.innerHTML = `
    <div class="page-head"><h1>Calendario</h1><p class="page-sub">Agenda de los próximos 14 días. Vista mes en Fase UI-7.</p></div>
    ${skeleton(5)}`;
  try {
    const [projects, meetings, deliverables, tasks, maps] = await Promise.all([
      listProjects(),
      listMeetings(),
      listDeliverables(),
      listTasks(),
      nameMaps(),
    ]);
    const today = todayISO();
    const horizon = addDaysISO(today, 14);
    const events = [];
    for (const m of meetings || []) {
      if (m.status !== 'scheduled' || m.starts_at.slice(0, 10) < today) continue;
      events.push({ date: m.starts_at.slice(0, 10), time: fmtTime(m.starts_at), title: m.title, ctx: maps.project[m.project_id] || (m.project_id ? m.project_id : 'Sin proyecto'), kind: 'meeting', href: `#/reuniones/${esc(m.id)}` });
    }
    for (const d of deliverables || []) {
      if (d.due_at < today || d.status === 'accepted' || d.status === 'cancelled') continue;
      events.push({ date: d.due_at, time: '', title: d.title, ctx: maps.project[d.project_id] || d.project_id, kind: 'deliverable', href: d.project_id ? `#/proyectos/${esc(d.project_id)}?tab=entregables` : `` });
    }
    for (const t of tasks || []) {
      if (!t.due_at || t.due_at < today || t.status === 'done' || t.status === 'cancelled') continue;
      events.push({ date: t.due_at, time: '', title: t.title, ctx: maps.project[t.project_id] || t.project_id, kind: 'task', href: t.project_id ? `#/proyectos/${esc(t.project_id)}?tab=tareas` : `` });
    }
    events.sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time));

    const grouped = {};
    for (const e of events) (grouped[e.date] = grouped[e.date] || []).push(e);

    const kindBadge = { meeting: badge('scheduled'), deliverable: badge('planned'), task: badge('ready') };
    const dates = Object.keys(grouped).filter((d) => d <= horizon);
    const html = dates.length
      ? dates
          .map(
            (d) => `
        <div class="cal-day">
          <div class="cal-day-head">${esc(fmtDayMonth(`${d}T12:00:00`))}${d === today ? '<span class="cal-today">hoy</span>' : ''}</div>
          <div class="list">
            ${grouped[d]
              .map(
                (e) => `
              ${e.href ? `<a class="item item-row" href="${e.href}">` : '<div class="item">'}
                <div class="item-main">
                  <div class="item-title">${esc(e.title)}</div>
                  <div class="item-sub">${e.time ? `${esc(e.time)} · ` : ''}${esc(e.ctx)}</div>
                </div>
                <div class="item-side">${kindBadge[e.kind]}</div>
              ${e.href ? '</a>' : '</div>'}`,
              )
              .join('')}
          </div>
        </div>`,
          )
          .join('')
      : emptyBlock('Sin actividad en los próximos 14 días.');
    el.innerHTML = `
      <div class="page-head"><h1>Calendario</h1><p class="page-sub">Reuniones, vencimientos y entregables.</p>
        <div class="page-head-actions">
          <button class="btn btn-primary btn-sm" data-create="meeting">${icon('plus')} Nueva reunión</button>
        </div>
      </div>
      <div class="cal-wrap">${html}</div>`;

    if (!el.dataset.viewBound) {
      el.dataset.viewBound = '1';
      el.addEventListener('click', async (event) => {
        const createBtn = event.target.closest('[data-create="meeting"]');
        if (!createBtn) return;
        const form = await openForm({
          title: 'Nueva reunión',
          submitLabel: 'Crear reunión',
          fields: [
            { name: 'title', label: 'Título', required: true, placeholder: 'Ej. Revisión de sprint' },
            {
              name: 'project',
              label: 'Proyecto',
              type: 'select',
              options: [{ value: '', label: 'Sin proyecto' }].concat((projects || []).map((p) => ({ value: p.id, label: p.name }))),
            },
            { name: 'starts', label: 'Fecha y hora', type: 'datetime-local', required: true },
          ],
        });
        if (!form) return;
        try {
          await api('/api/v1/meetings', {
            method: 'POST',
            body: JSON.stringify({
              id: genEntityId('mtg', form.title),
              title: form.title,
              starts_at: form.starts,
              status: 'scheduled',
              ...(form.project ? { project_id: form.project } : {}),
            }),
          });
          toast('Reunión creada', 'success');
        } catch (err) {
          toast(`No se pudo crear la reunión: ${err.message}`, 'error');
        }
        invalidate('meetings');
        renderCalendario(el);
      });
    }
  } catch (err) {
    el.innerHTML = errorBlock(`Calendario no disponible: ${esc(err.message)}`);
  }
}

/* ============================================================
   ASISTENTE IA  (respuestas determinísticas; núcleo IA en UI-9)
   ============================================================ */

const QUICK_ACTIONS = [
  ['pendientes', '¿Qué tengo pendiente?'],
  ['organizar', 'Organiza mi día'],
  ['atencion', '¿Qué proyectos requieren atención?'],
  ['vencidas', '¿Qué está vencido?'],
  ['cambios', '¿Qué cambió hoy?'],
];

export async function renderAsistente(el) {
  setPageTitle('Asistente IA');
  el.innerHTML = `
    <div class="page-head"><h1>Asistente</h1><p class="page-sub">¿Qué necesitas resolver?</p></div>
    ${skeleton(3)}`;
  try {
    const [maps, brief, projects, audit] = await Promise.all([
      nameMaps(),
      api('/api/v1/briefs/morning'),
      listProjects(),
      api('/api/v1/audit-events?limit=12'),
    ]);
    const chips = QUICK_ACTIONS.map(
      ([key, label]) => `<button class="btn btn-soft" data-ask="${key}">${esc(label)}</button>`,
    ).join('');
    el.innerHTML = `
      <div class="page-head">
        <div class="page-greeting"><h1>Asistente</h1><span class="date-line">· Faro</span></div>
        <p class="page-sub">Respuestas a partir de tus datos reales. El motor de IA completo llega en la Fase UI-9.</p>
      </div>
      <section class="card">
        <div class="card-body">
          <div class="quick-row">${chips}</div>
          <div id="assistant-answer"></div>
        </div>
      </section>`;
    const answerHost = el.querySelector('#assistant-answer');
    const answers = {
      pendientes: () => {
        const c = brief.counts;
        const list = (brief.focus_tasks || []).map((t) => `<li class="tl-item tl-now"><div class="tl-head"><span class="tl-title">${esc(t.title)}</span> ${prio(t.priority)}</div><div class="tl-meta">${esc(taskContext(t, maps))}</div></li>`).join('');
        return `<h4>${plural(c.focus_tasks, 'tarea en foco', `tareas en foco`)} · ${plural(c.overdue_tasks, 'vencida', 'vencidas')}</h4>${list ? `<ul class="assistant-list">${list}</ul>` : '<p>No tienes pendientes en foco ahora mismo.</p>'}`;
      },
      organizar: () => {
        const rows = [];
        for (const m of brief.meetings || []) rows.push([fmtTime(m.starts_at), `Reunión · ${m.title}`, `#/reuniones`]);
        for (const t of brief.focus_tasks || []) rows.push(['Ahora', `Tarea · ${t.title}`, `#/mi-dia`]);
        if (!rows.length) return '<p>No hay nada para organizar hoy.</p>';
        return `<ul class="p-list">${rows.map(([time, text, href]) => `<li class="activity"><div class="activity-body"><b>${esc(time)}</b><span>${esc(text)} · <a href="#${href}">abrir</a></span></div></li>`).join('')}</ul>`;
      },
      atencion: () => {
        const risky = (projects || []).filter((p) => p.health === 'off_track' || p.health === 'at_risk');
        if (!risky.length) return '<p>Ningún proyecto se reporta en riesgo.</p>';
        return `<ul class="p-list">${risky.map((p) => `<li class="activity"><div class="activity-body"><b>${esc(p.name)}</b><span>${esc(humanStatus(p.health))} · <a href="#/proyectos">ver</a></span></div></li>`).join('')}</ul>`;
      },
      vencidas: () => {
        const list = (brief.overdue_tasks || []).map((t) => `<li class="tl-item tl-overdue"><div class="tl-head"><span class="tl-title">${esc(t.title)}</span> ${badge(t.status)}</div><div class="tl-meta">${esc(taskContext(t, maps))} · vencía ${esc(fmtDate(t.due_at))}</div></li>`).join('');
        return `<h4>${plural((brief.overdue_tasks || []).length, 'tarea vencida', 'tareas vencidas')}</h4>${list || '<p>Nada vencido.</p>'}`;
      },
      cambios: () => {
        const today = todayISO();
        const items = (audit || []).filter((e) => String(e.occurred_at).slice(0, 10) === today);
        if (!items.length) return '<p>Sin cambios registrados hoy.</p>';
        return `<ul class="p-list">${items.map((e) => `<li class="activity"><div class="activity-body"><b>${esc(e.entity_kind)}</b><span>${esc(e.action)} · <a href="#/configuracion">ver</a></span></div></li>`).join('')}</ul>`;
      },
    };
    if (!el.dataset.viewBound) {
      el.dataset.viewBound = '1';
      el.addEventListener('click', (event) => {
        const btn = event.target.closest('[data-ask]');
        if (!btn) return;
        answerHost.innerHTML = answers[btn.dataset.ask]();
      });
    }
  } catch (err) {
    el.innerHTML = errorBlock(`Asistente no disponible: ${esc(err.message)}`);
  }
}

/* ============================================================
   INTEGRACIONES
   ============================================================ */

export async function renderIntegraciones(el) {
  setPageTitle('Integraciones');
  el.innerHTML = `
    <div class="page-head"><h1>Integraciones</h1><p class="page-sub">Servicios externos conectados a FaroFlow.</p></div>
    ${skeleton(4)}`;
  try {
    const [links, runs, maps] = await Promise.all([
      api('/api/v1/integrations/drive-links'),
      api('/api/v1/integrations/sync-runs'),
      nameMaps(),
    ]);
    const driveRuns = (runs || []).filter((r) => r.source_system === 'google-drive');
    const calRuns = (runs || []).filter((r) => r.resource_kind === 'calendar');
    const lastDrive = driveRuns[0];
    const lastCal = calRuns[0];

    el.innerHTML = `
      <div class="page-head"><h1>Integraciones</h1><p class="page-sub">Metadata de solo lectura. Los archivos externos nunca se modifican.</p></div>
      <div class="page-grid two">
        <section class="card">
          <div class="card-head"><h2>${icon('drive')} Google Drive</h2>
            <button class="btn btn-ghost btn-sm card-action" data-drive-refresh="1">${icon('refresh')} Sincronizar</button></div>
          <div class="card-body">
            <div class="integ-row"><b>Estado</b><span>${links.length ? 'Conectado' : 'Vinculado sin credenciales'}</span></div>
            <div class="integ-row"><b>Documentos vinculados</b><span>${plural(links.length, 'entregable', 'entregables')}</span></div>
            <div class="integ-row"><b>Última sincronización</b><span>${lastDrive ? formatSync(lastDrive) : '—'}</span></div>
            <p class="integ-note">Agrega las credenciales de Drive en <code>.env</code> y ejecuta la sincronización. Los vínculos son solo-metadata, nunca se modifican archivos externos.</p>
            ${links.length ? `<div class="card-list" style="margin-top:8px">${links.slice(0, 4).map((l) => `
              <div class="item">
                <div class="item-main"><div class="item-title">${esc(l.external_name || l.deliverable_title)}</div>
                <div class="item-sub">${esc(l.deliverable_title)} · ${esc(l.mime_type || 'documento')}</div></div>
                ${l.web_url ? `<a class="btn btn-ghost btn-xs" href="${esc(l.web_url)}" target="_blank" rel="noopener">Abrir</a>` : ''}
              </div>`).join('')}</div>` : ''}
          </div>
        </section>
        <section class="card">
          <div class="card-head"><h2>${icon('calendar')} Calendarios</h2></div>
          <div class="card-body">
            <div class="integ-row"><b>Última sincronización</b><span>${lastCal ? formatSync(lastCal) : '—'}</span></div>
            <p class="integ-note">Se sincronizan reuniones como solo-lectura mediante adaptadores Microsoft 365 y Google Calendar cuando se configuran credenciales locales.</p>
          </div>
        </section>
      </div>
      <section class="card" style="margin-top:16px">
        <div class="card-head"><h2>${icon('clock')} Historial de sincronización</h2></div>
        <div class="card-body">${runs && runs.length ? `<div class="list">${runs.slice(0, 8).map((r) => `
          <div class="item">
            <div class="item-main"><div class="item-title">${esc(r.source_system)} · ${esc(r.resource_kind)}</div>
            <div class="item-sub">${esc(formatSync(r))}</div></div>
            ${badge(r.status)}
          </div>`).join('')}</div>` : emptyBlock('Sin ejecuciones de sincronización registradas.')}</div>
      </section>`;

    if (!el.dataset.viewBound) {
      el.dataset.viewBound = '1';
      el.addEventListener('click', async (event) => {
        const btn = event.target.closest('[data-drive-refresh]');
        if (!btn) return;
        btn.disabled = true;
        try {
          const run = await api('/api/v1/integrations/drive/refresh', { method: 'POST' });
          toast(`Sincronización: ${run.updated_count} actualizadas, ${run.unchanged_count} sin cambios`, 'success');
        } catch (err2) {
          toast(err2.status === 503 ? 'Drive no configurado aún. Agrega credenciales en .env' : err2.message, 'error');
        }
        btn.disabled = false;
        renderIntegraciones(el);
      });
    }
  } catch (err) {
    el.innerHTML = errorBlock(`Integraciones no disponibles: ${esc(err.message)}`);
  }
}

function formatSync(run) {
  const counts = `vistos ${run.seen_count} · creados ${run.created_count} · actualizados ${run.updated_count} · sin cambios ${run.unchanged_count} · omitidos ${run.skipped_count} · errores ${run.error_count}`;
  const when = run.completed_at ? fmtDate(run.completed_at) : run.started_at ? fmtDate(run.started_at) : '';
  return `${when} — ${counts}`;
}

/* ============================================================
   CONFIGURACIÓN
   ============================================================ */

const TIMEZONES = [
  'America/Santiago',
  'America/Argentina/Buenos_Aires',
  'America/Lima',
  'America/Bogota',
  'America/Mexico_City',
  'America/New_York',
  'America/Los_Angeles',
  'Europe/Madrid',
  'UTC',
];

export async function renderConfiguracion(el, initialTab = 'cat') {
  setPageTitle('Configuración');
  el.innerHTML = `
    <div class="page-head"><h1>Configuración</h1><p class="page-sub">Tu perfil, catálogo y preferencias.</p></div>
    ${skeleton(4)}`;
  try {
    const [workspaces, clients, projects, tasks, meetings, maps] = await Promise.all([
      listWorkspaces(),
      listClients(),
      listProjects(),
      listTasks(),
      listMeetings(),
      nameMaps(),
    ]);
    const tabs = [['cat', 'Catálogo'], ['sys', 'Sistema']];
    const wsActions = (w) => `
      <div class="item-side item-actions">
        <button class="btn btn-ghost btn-xs" data-conf="ws-edit" data-id="${esc(w.id)}">${icon('edit')} Editar</button>
        <button class="btn btn-danger-soft btn-xs" data-conf="ws-delete" data-id="${esc(w.id)}">${icon('trash')} Eliminar</button>
        ${badge(w.status)}
      </div>`;
    const clientActions = (c) => `
      <div class="item-side item-actions">
        <button class="btn btn-ghost btn-xs" data-conf="client-edit" data-id="${esc(c.id)}">${icon('edit')} Editar</button>
        <button class="btn btn-danger-soft btn-xs" data-conf="client-delete" data-id="${esc(c.id)}">${icon('trash')} Eliminar</button>
        ${badge(c.status)}
      </div>`;
    const catalog = `
      <section class="card">
        <div class="card-head"><h2>${icon('folder')} Workspaces</h2>
          <button class="btn btn-soft btn-sm card-action" data-conf="ws-create">${icon('plus')} Nuevo workspace</button></div>
        <div class="card-body"><div class="list">${(workspaces || []).map((w) => `
          <div class="item">
            <div class="item-main"><div class="item-title">${esc(w.name)}</div>
            <div class="item-sub">${esc(w.id)} · ${esc(w.timezone)}</div></div>
            ${wsActions(w)}
          </div>`).join('') || emptyBlock('Sin workspaces. Crea el primero para organizar tu trabajo.')}</div></div>
      </section>
      <section class="card" style="margin-top:16px">
        <div class="card-head"><h2>${icon('folder')} Clientes</h2>
          <button class="btn btn-soft btn-sm card-action" data-conf="client-create">${icon('plus')} Nuevo cliente</button></div>
        <div class="card-body"><div class="list">${(clients || []).map((c) => `
          <div class="item"><div class="item-main"><div class="item-title">${esc(c.name)}</div>
          <div class="item-sub">${esc(maps.workspace[maps.clientWorkspace[c.id]] || c.workspace_id)}</div></div>
          ${clientActions(c)}
          </div>`).join('') || emptyBlock('Sin clientes. Crea el primero para empezar el portafolio.')}</div></div>
      </section>`;
    const counts = [
      ['Workspaces', (workspaces || []).length],
      ['Clientes', (clients || []).length],
      ['Proyectos', (projects || []).length],
      ['Tareas', (tasks || []).length],
      ['Reuniones', (meetings || []).length],
    ];
    const sys = `
      <section class="card">
        <div class="card-head"><h2>${icon('info')} Resumen del sistema</h2></div>
        <div class="card-body"><div class="list">${counts.map(([label, n]) => `<div class="integ-row"><b>${esc(label)}</b><span>${n}</span></div>`).join('')}</div>
        <p class="integ-note" style="margin-top:10px">Esta instalación opera en modo manual local (usuario único). Las secciones de perfil, notificaciones y seguridad se habilitarán junto con el sistema de autenticación.</p></div>
      </section>`;

    const reloadCatalog = async () => {
      invalidate('workspaces');
      invalidate('clients');
      invalidate('projects');
      invalidate('deliverables');
      invalidate('meetings');
      forgetMaps();
      window.dispatchEvent(new Event('ff:config-changed'));
      renderConfiguracion(el, 'cat');
    };

    const refresh = (tab) => {
      el.querySelector('#conf-content').innerHTML = tab === 'sys' ? sys : catalog;
      el.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === tab));
    };

    const timezoneField = (value = 'America/Santiago') => ({
      name: 'timezone',
      label: 'Zona horaria',
      type: 'select',
      required: true,
      value,
      options: TIMEZONES.map((tz) => ({ value: tz, label: tz })),
    });

    const wsFields = (w) => {
      const fields = [
        { name: 'name', label: 'Nombre', required: true, value: w ? w.name : '', placeholder: 'Ej. Consultora Mirada' },
        timezoneField(w ? w.timezone : 'America/Santiago'),
        {
          name: 'status',
          label: 'Estado',
          type: 'select',
          value: w ? w.status : 'active',
          options: ['active', 'paused', 'archived'].map((s) => ({ value: s, label: humanStatus(s) })),
        },
      ];
      return fields;
    };

    el.innerHTML = `
      <div class="page-head"><h1>Configuración</h1><p class="page-sub">Catálogo y estado de tu instalación.</p></div>
      <div class="tabs">
        ${tabs.map(([key, label]) => `<button class="tab ${key === initialTab ? 'active' : ''}" data-tab="${key}">${esc(label)}</button>`).join('')}
      </div>
      <div id="conf-content">${initialTab === 'sys' ? sys : catalog}</div>`;

    if (!el.dataset.viewBound) {
      el.dataset.viewBound = '1';
      el.addEventListener('click', async (event) => {
        const tab = event.target.closest('.tab');
        if (tab) {
          refresh(tab.dataset.tab);
          return;
        }
        const action = event.target.closest('[data-conf]');
        const btn = action;
        if (!btn) return;
        const kind = btn.dataset.conf;
        const id = btn.dataset.id;
        try {
          if (kind === 'ws-create') {
            const form = await openForm({
              title: 'Nuevo workspace',
              submitLabel: 'Crear workspace',
              fields: wsFields(),
              hint: 'El workspace agrupa clientes y proyectos de tu operación.',
            });
            if (!form) return;
            await api('/api/v1/workspaces', {
              method: 'POST',
              body: JSON.stringify({ id: genEntityId('wrk', form.name), name: form.name, timezone: form.timezone, status: form.status || 'active' }),
            });
            toast('Workspace creado', 'success');
            await reloadCatalog();
            return;
          }
          if (kind === 'ws-edit') {
            const ws = (workspaces || []).find((w) => w.id === id);
            const form = await openForm({
              title: 'Editar workspace',
              submitLabel: 'Guardar cambios',
              fields: wsFields(ws),
            });
            if (!form) return;
            await api(`/api/v1/workspaces/${encodeURIComponent(id)}`, {
              method: 'PATCH',
              body: JSON.stringify({ name: form.name, timezone: form.timezone, status: form.status }),
            });
            toast('Workspace actualizado', 'success');
            await reloadCatalog();
            return;
          }
          if (kind === 'ws-delete') {
            const ws = (workspaces || []).find((w) => w.id === id) || {};
            if (!window.confirm(`¿Eliminar el workspace «${ws.name}»?`)) return;
            await api(`/api/v1/workspaces/${encodeURIComponent(id)}`, { method: 'DELETE' });
            toast('Workspace eliminado', 'success');
            await reloadCatalog();
            return;
          }
          if (kind === 'client-create') {
            const current = localStorage.getItem('ff.workspace') || (workspaces && workspaces[0] ? workspaces[0].id : '');
            const form = await openForm({
              title: 'Nuevo cliente',
              submitLabel: 'Crear cliente',
              fields: [
                { name: 'name', label: 'Nombre', required: true, placeholder: 'Ej. Northwind' },
                {
                  name: 'workspace',
                  label: 'Workspace',
                  type: 'select',
                  required: true,
                  value: current,
                  options: (workspaces || []).map((w) => ({ value: w.id, label: w.name })),
                },
                {
                  name: 'status',
                  label: 'Estado',
                  type: 'select',
                  value: 'active',
                  options: ['active', 'paused', 'archived'].map((s) => ({ value: s, label: humanStatus(s) })),
                },
              ],
            });
            if (!form) return;
            await api('/api/v1/clients', {
              method: 'POST',
              body: JSON.stringify({ id: genEntityId('cli', form.name), workspace_id: form.workspace, name: form.name, status: form.status || 'active' }),
            });
            toast('Cliente creado', 'success');
            await reloadCatalog();
            return;
          }
          if (kind === 'client-edit') {
            const client = (clients || []).find((c) => c.id === id);
            const form = await openForm({
              title: 'Editar cliente',
              submitLabel: 'Guardar cambios',
              fields: [
                { name: 'name', label: 'Nombre', required: true, value: client ? client.name : '' },
                {
                  name: 'workspace',
                  label: 'Workspace',
                  type: 'select',
                  required: true,
                  value: client ? client.workspace_id : '',
                  options: (workspaces || []).map((w) => ({ value: w.id, label: w.name })),
                },
                {
                  name: 'status',
                  label: 'Estado',
                  type: 'select',
                  value: client ? client.status : 'active',
                  options: ['active', 'paused', 'archived'].map((s) => ({ value: s, label: humanStatus(s) })),
                },
              ],
            });
            if (!form) return;
            await api(`/api/v1/clients/${encodeURIComponent(id)}`, {
              method: 'PATCH',
              body: JSON.stringify({ name: form.name, workspace_id: form.workspace, status: form.status }),
            });
            toast('Cliente actualizado', 'success');
            await reloadCatalog();
            return;
          }
          if (kind === 'client-delete') {
            const client = (clients || []).find((c) => c.id === id) || {};
            if (!window.confirm(`¿Eliminar el cliente «${client.name}»?`)) return;
            await api(`/api/v1/clients/${encodeURIComponent(id)}`, { method: 'DELETE' });
            toast('Cliente eliminado', 'success');
            await reloadCatalog();
          }
        } catch (err) {
          toast(err.message, 'error');
        }
      });
    }
  } catch (err) {
    el.innerHTML = errorBlock(`Configuración no disponible: ${esc(err.message)}`);
  }
}