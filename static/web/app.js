'use strict';

const $ = (id) => document.getElementById(id);

function badge(status) {
  const s = String(status || 'unknown').toLowerCase();
  const label = String(status || '—');
  return `<span class="badge badge-${s.replace(/[^a-z0-9]/g, '')}">${escapeHtml(label)}</span>`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function api(path, options) {
  const response = await fetch(path, {
    headers: { 'Accept': 'application/json', ...(options && options.body ? { 'Content-Type': 'application/json' } : {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = `${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* not json */ }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

function setList(id, html) {
  const node = $(id);
  if (node) node.innerHTML = html;
}

function emptyBlock(message) {
  return `<div class="empty">${escapeHtml(message)}</div>`;
}

function fmtDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

async function loadBrief() {
  try {
    const brief = await api('/api/v1/briefs/morning');
    const meetings = brief.meetings || [];
    const overdue = brief.overdue_tasks || [];
    const dueSoon = brief.due_soon_tasks || [];
    const focus = brief.focus_tasks || [];

    $('page-title').textContent = `Resumen de ${fmtDate(brief.date)}`;
    $('hero-date').textContent = fmtDate(brief.date);

    setList('brief-summary', `
      <div class="stat"><b>${meetings.length}</b><span>REUNIONES HOY</span></div>
      <div class="stat"><b>${focus.length}</b><span>EN FOCO</span></div>
      <div class="stat"><b>${overdue.length}</b><span>VENCIDAS</span></div>
      <div class="stat"><b>${dueSoon.length}</b><span>POR VENCER</span></div>
    `);

    const focusHtml = focus.length
      ? focus.map((t) => itemRow(`${escapeHtml(t.title)} · ${escapeHtml(t.project_name || t.project_id || '')}`, badge(t.status))).join('')
      : emptyBlock('Sin tareas en foco hoy.');
    setList('brief-focus', focusHtml);
    return brief;
  } catch (err) {
    setList('brief-summary', `<div class="error">Brief no disponible: ${escapeHtml(err.message)}</div>`);
    return null;
  }
}

function itemRow(main, extra, sub) {
  return `<div class="item"><div class="item-main"><span class="item-title">${main}</span>${sub ? `<div class="item-sub">${sub}</div>` : ''}</div>${extra || ''}</div>`;
}

async function loadMeetings() {
  try {
    const meetings = await api('/api/v1/meetings');
    const sorted = [...(meetings || [])]
      .filter((m) => m.status !== 'cancelled')
      .sort((a, b) => String(a.starts_at || '').localeCompare(String(b.starts_at || '')))
      .slice(0, 8);
    setList('meetings-list', sorted.length
      ? sorted.map((m) => itemRow(
          escapeHtml(m.title),
          badge(m.project_id ? 'assigned' : 'unassigned'),
          m.project_id
            ? `${escapeHtml(fmtDate(m.starts_at))} · proyecto ${escapeHtml(m.project_id)}`
            : `${escapeHtml(fmtDate(m.starts_at))} · sin proyecto`,
        )).join('')
      : emptyBlock('Sin reuniones registradas.'));
  } catch (err) {
    setList('meetings-list', `<div class="error">${escapeHtml(err.message)}</div>`);
  }
}

async function loadReview() {
  try {
    const [unmatched, projects] = await Promise.all([
      api('/api/v1/integrations/meetings/unmatched'),
      api('/api/v1/projects'),
    ]);
    const options = (projects || [])
      .map((p) => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)}</option>`)
      .join('');

    setList('review-list', (unmatched && unmatched.length)
      ? unmatched.map((m) => `
          <div class="item">
            <div class="item-main">
              <span class="item-title">${escapeHtml(m.title)}</span>
              <div class="item-sub">${escapeHtml(fmtDate(m.starts_at))} · ${escapeHtml(m.source_system || 'importada')}</div>
            </div>
            <form class="review-form" data-meeting="${escapeHtml(m.id)}">
              <select class="project-pick" required>${projects && projects.length ? options : '<option value="">Sin proyectos</option>'}</select>
              <button class="confirm" type="submit" ${projects && projects.length ? '' : 'disabled'}>Confirmar</button>
            </form>
          </div>`).join('')
      : emptyBlock('No hay reuniones sin proyecto.'));
  } catch (err) {
    setList('review-list', `<div class="error">${escapeHtml(err.message)}</div>`);
  }
}

async function confirmMeeting(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const meetingId = form.dataset.meeting;
  const projectId = form.querySelector('select').value;
  if (!projectId) return;
  const button = form.querySelector('button');
  button.disabled = true;
  try {
    await api(`/api/v1/integrations/meetings/${encodeURIComponent(meetingId)}/project`, {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId }),
    });
    await Promise.all([loadReview(), loadMeetings(), loadBrief()]);
  } catch (err) {
    button.disabled = false;
    alert(`No se pudo confirmar: ${err.message}`);
  }
}

async function loadProjects() {
  try {
    const projects = await api('/api/v1/projects');
    setList('projects-list', (projects && projects.length)
      ? projects.map((p) => itemRow(
          escapeHtml(p.name),
          badge(p.status),
          `cliente ${escapeHtml(p.client_name || p.client_id || '')}`,
        )).join('')
      : emptyBlock('Sin proyectos registrados.'));
  } catch (err) {
    setList('projects-list', `<div class="error">${escapeHtml(err.message)}</div>`);
  }
}

async function loadFocusTasks() {
  try {
    const tasks = await api('/api/v1/tasks?limit=30');
    const open = (tasks || [])
      .filter((t) => !['completed', 'cancelled'].includes(t.status))
      .slice(0, 8);
    setList('focus-tasks', open.length
      ? open.map((t) => itemRow(
          escapeHtml(t.title),
          badge(t.status),
          t.due_date ? `vence ${escapeHtml(fmtDate(t.due_date))}` : '',
        )).join('')
      : emptyBlock('Sin tareas abiertas.'));
  } catch (err) {
    setList('focus-tasks', `<div class="error">${escapeHtml(err.message)}</div>`);
  }
}

async function loadDriveLinks() {
  try {
    const links = await api('/api/v1/integrations/drive-links');
    setList('drive-links', (links && links.length)
      ? links.map((link) => itemRow(
          escapeHtml(link.external_name || link.deliverable_title || link.external_id),
          badge('muted'),
          `${escapeHtml(link.mime_type || 'documento')} · v${escapeHtml(link.external_version || '?')} · ${escapeHtml(link.deliverable_title)}`,
        )).join('')
      : emptyBlock('Sin documentos Drive vinculados.'));
  } catch (err) {
    setList('drive-links', `<div class="error">${escapeHtml(err.message)}</div>`);
  }
  const status = $('drive-refresh-status');
  if (status) status.textContent = '';
}

async function refreshDriveMetadata() {
  const button = $('drive-refresh');
  const status = $('drive-refresh-status');
  if (!button || !status) return;
  button.disabled = true;
  status.textContent = 'Refrescando…';
  try {
    const run = await api('/api/v1/integrations/drive/refresh', { method: 'POST' });
    status.textContent =
      `Sincronización ${run.status}: ${run.updated_count} actualizadas, ${run.unchanged_count} sin cambios, ${run.skipped_count} omitidas.`;
    await loadDriveLinks();
  } catch (err) {
    status.textContent = /not configured|no configurado/i.test(err.message) ? 'Drive no configurado aún.' : err.message;
  } finally {
    button.disabled = false;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.addEventListener('submit', (event) => {
    if (event.target.classList.contains('review-form')) confirmMeeting(event);
  });
  $('drive-refresh').addEventListener('click', refreshDriveMetadata);
  Promise.all([loadBrief(), loadMeetings(), loadReview(), loadProjects(), loadDriveLinks(), loadFocusTasks()]);
});