'use strict';

export async function api(path, options) {
  const response = await fetch(path, {
    headers: {
      Accept: 'application/json',
      ...(options && options.body ? { 'Content-Type': 'application/json' } : {}),
    },
    ...options,
  });
  if (response.status === 204) return null;
  if (!response.ok) {
    let detail = `${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
      if (Array.isArray(detail)) detail = detail.map((d) => d.msg || String(d)).join('; ');
    } catch (_) {
      /* not json */
    }
    const err = new Error(detail);
    err.status = response.status;
    throw err;
  }
  return response.json();
}

const cache = new Map();

async function cached(key, loader) {
  if (!cache.has(key)) cache.set(key, loader());
  try {
    return await cache.get(key);
  } catch (err) {
    cache.delete(key);
    throw err;
  }
}

export function invalidate(prefix) {
  for (const key of [...cache.keys()]) {
    if (key.startsWith(prefix)) cache.delete(key);
  }
}

export function listWorkspaces() {
  return cached('workspaces', () => api('/api/v1/workspaces'));
}
export function listClients() {
  return cached('clients', () => api('/api/v1/clients'));
}
export function listProjects() {
  return cached('projects', () => api('/api/v1/projects'));
}
export function listDeliverables() {
  return cached('deliverables', () => api('/api/v1/deliverables'));
}
export function listMeetings() {
  return cached('meetings', () => api('/api/v1/meetings'));
}
export function listTasks(params) {
  const q = params ? `?${params}` : '';
  return cached(`tasks${q}`, () => api(`/api/v1/tasks${q}`));
}

let mapsPromise = null;

export function nameMaps() {
  if (!mapsPromise) {
    mapsPromise = Promise.all([
      listWorkspaces(),
      listClients(),
      listProjects(),
      listDeliverables(),
    ]).then(([workspaces, clients, projects, deliverables]) => ({
      workspace: Object.fromEntries((workspaces || []).map((w) => [w.id, w.name])),
      client: Object.fromEntries((clients || []).map((c) => [c.id, c.name])),
      clientWorkspace: Object.fromEntries((clients || []).map((c) => [c.id, c.workspace_id])),
      project: Object.fromEntries((projects || []).map((p) => [p.id, p.name])),
      projectClient: Object.fromEntries((projects || []).map((p) => [p.id, p.client_id])),
      deliverable: Object.fromEntries((deliverables || []).map((d) => [d.id, d.title])),
    }));
  }
  return mapsPromise;
}

export function forgetMaps() {
  mapsPromise = null;
}