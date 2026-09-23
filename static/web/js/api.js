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

/* ============================================================
   Área Finanzas (CuentaFaro bajo /api/v1/finance)
   ============================================================ */

const finance = (path, options) =>
  api(`/api/v1/finance${path}`, options);

export function listHouseholds() {
  return cached('fin:households', () => finance('/households'));
}
export function createHousehold(payload) {
  return finance('/households', { method: 'POST', body: JSON.stringify(payload) });
}
export function listHouseholdMembers(householdId) {
  return cached(`fin:members:${householdId}`, () => finance(`/households/${encodeURIComponent(householdId)}/members`));
}
export function createHouseholdMember(householdId, payload) {
  return finance(`/households/${encodeURIComponent(householdId)}/members`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
export function listAccounts() {
  return cached('fin:accounts', () => finance('/accounts'));
}
export function createAccount(payload) {
  return finance('/accounts', { method: 'POST', body: JSON.stringify(payload) });
}
export function patchAccount(accountId, payload) {
  return finance(`/accounts/${encodeURIComponent(accountId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}
export function listInstitutions() {
  return cached('fin:institutions', () => finance('/financial-institutions'));
}
export function createInstitution(payload) {
  return finance('/financial-institutions', { method: 'POST', body: JSON.stringify(payload) });
}
export async function listCategoriesByHousehold(householdId) {
  return cached(`fin:categories:${householdId}`, () =>
    finance(`/households/${encodeURIComponent(householdId)}/categories`));
}

export function listTransactions(params) {
  const qs = params
    ? `?${Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== '')
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&')}`
    : '';
  return api(`/api/v1/finance/transactions${qs}`);
}
export function createTransaction(payload) {
  return finance('/transactions', { method: 'POST', body: JSON.stringify(payload) });
}
export function voidTransaction(transactionId) {
  return finance(`/transactions/${encodeURIComponent(transactionId)}/void`, { method: 'POST' });
}
export function dashboard(householdId, year, month) {
  return finance(
    `/households/${encodeURIComponent(householdId)}/dashboard?year=${year}&month=${month}`,
  );
}
export function upcomingPayments(householdId, days = 30) {
  return finance(`/households/${encodeURIComponent(householdId)}/upcoming-payments?days=${days}`);
}
export function debtSummary(householdId) {
  return finance(`/households/${encodeURIComponent(householdId)}/debt-summary`);
}
export function netWorth(householdId) {
  return finance(`/households/${encodeURIComponent(householdId)}/net-worth`);
}
export function listDebtsByHousehold(householdId) {
  return cached(`fin:debts:${householdId}`, () =>
    finance(`/households/${encodeURIComponent(householdId)}/debts`));
}
export function createDebt(householdId, payload) {
  return finance(`/households/${encodeURIComponent(householdId)}/debts`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
export async function listBudgetsByHousehold(householdId) {
  return cached(`fin:budgets:${householdId}`, () =>
    finance(`/households/${encodeURIComponent(householdId)}/budgets`));
}
export function createBudget(householdId, payload) {
  return finance(`/households/${encodeURIComponent(householdId)}/budgets`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
export async function listGoalsByHousehold(householdId) {
  return cached(`fin:goals:${householdId}`, () =>
    finance(`/households/${encodeURIComponent(householdId)}/goals`));
}
export function createGoal(householdId, payload) {
  return finance(`/households/${encodeURIComponent(householdId)}/goals`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
export function contributeGoal(goalId, payload) {
  return finance(`/goals/${encodeURIComponent(goalId)}/contributions`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/* ============================================================
   Hábitos
   ============================================================ */

export function listHabits() {
  return cached('habits', () => api('/api/v1/habits'));
}
export function createHabit(payload) {
  return api('/api/v1/habits', { method: 'POST', body: JSON.stringify(payload) });
}
export function updateHabit(habitId, payload) {
  return api(`/api/v1/habits/${encodeURIComponent(habitId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}
export function deleteHabit(habitId) {
  return api(`/api/v1/habits/${encodeURIComponent(habitId)}`, { method: 'DELETE' });
}
export function habitSeries(habitId) {
  return cached(`habit-series:${habitId}`, () =>
    api(`/api/v1/habits/${encodeURIComponent(habitId)}/series`));
}
export function markHabit(habitId, payload) {
  return api(`/api/v1/habits/${encodeURIComponent(habitId)}/mark`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
export function unmarkHabit(habitId, payload) {
  return api(`/api/v1/habits/${encodeURIComponent(habitId)}/unmark`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/* ============================================================
   Bandeja
   ============================================================ */

export function listBandeja(params) {
  const qs = params
    ? `?${Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== '')
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&')}`
    : '';
  return api(`/api/v1/bandeja${qs}`);
}
export function receiveBandeja(payload) {
  return api('/api/v1/bandeja', { method: 'POST', body: JSON.stringify(payload) });
}
export function refineBandeja(itemId, payload) {
  return api(`/api/v1/bandeja/${encodeURIComponent(itemId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}
export function discardBandeja(itemId, payload) {
  return api(`/api/v1/bandeja/${encodeURIComponent(itemId)}/discard`, {
    method: 'POST',
    body: JSON.stringify(payload || {}),
  });
}
export function applyBandeja(itemId, payload) {
  return api(`/api/v1/bandeja/${encodeURIComponent(itemId)}/apply`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}