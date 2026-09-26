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

// Acepta un prefijo o una lista de prefijos. Antes, passing un array hacia
// startsWith lo convertia a "fin,goals", que no matcheaba ninguna clave: la
// invalidacion de Finanzas no hacia nada y las vistas servian datos viejos.
export function invalidate(prefixes) {
  const list = Array.isArray(prefixes) ? prefixes : [prefixes];
  for (const key of [...cache.keys()]) {
    if (list.some((prefix) => prefix && key.startsWith(prefix))) cache.delete(key);
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

/* Saldo disponible del hogar: suma el saldo de las cuentas activas. Es un
   número global (no depende del mes), así que se cachea y todas las vistas lo
   comparten sin volver a pedirlo. Se usa `balance_calculated` y, cuando falta,
   `balance_reported` como respaldo para cuentas sin saldo calculado.
   Sin `householdId` se usa el primer hogar, igual que hace el backend. */
export async function availableBalance(householdId = '') {
  const id = householdId || (await listHouseholds())?.[0]?.id;
  if (!id) return { total: 0, currency: 'CLP', accounts: 0, credit: 0 };
  return cached(`fin:available:${id}`, async () => {
    const accounts = (await listAccounts()) || [];
    const active = accounts.filter((a) => a.status === 'active');
    const balanceOf = (a) => {
      const value = a.balance_calculated ?? a.balance_reported ?? 0;
      return Number(value) || 0;
    };
    const total = active.reduce((sum, a) => sum + balanceOf(a), 0);
    return {
      total,
      currency: active[0]?.currency || 'CLP',
      accounts: active.length,
      credit: active
        .filter((a) => (Number(a.credit_limit) || 0) > 0)
        .reduce((sum, a) => sum + (Number(a.credit_limit) || 0), 0),
    };
  });
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
  }).then((res) => {
    invalidate('habits');
    invalidate(`habit-series:${habitId}`);
    return res;
  });
}

export function unmarkHabit(habitId, payload) {
  return api(`/api/v1/habits/${encodeURIComponent(habitId)}/unmark`, {
    method: 'POST',
    body: JSON.stringify(payload),
  }).then((res) => {
    invalidate('habits');
    invalidate(`habit-series:${habitId}`);
    return res;
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
/* ---------- Editar y borrar registros ---------- */

const KIND_PATH = {
  workspace: 'workspaces',
  client: 'clients',
  project: 'projects',
  deliverable: 'deliverables',
  meeting: 'meetings',
  action_item: 'action-items',
  habit: 'habits',
  task: 'tasks',
  capture: 'captures',
  bandeja: 'bandeja',
  translation: 'translations',
};

// PATCH generico por tipo de entidad. El store ignora los campos ausentes, asi
// que solo hay que mandar lo que cambio.
export function updateRecord(kind, entityId, changes) {
  const path = KIND_PATH[kind];
  if (!path) return Promise.reject(new Error(`Tipo no editable: ${kind}`));
  return api(`/api/v1/${path}/${encodeURIComponent(entityId)}`, {
    method: 'PATCH',
    body: JSON.stringify(changes),
  }).then((res) => {
    invalidate(path);
    invalidate(`${path}-`);
    return res;
  });
}

export function deleteRecord(kind, entityId) {
  const path = KIND_PATH[kind];
  if (!path) return Promise.reject(new Error(`Tipo no eliminable: ${kind}`));
  return api(`/api/v1/${path}/${encodeURIComponent(entityId)}`, {
    method: 'DELETE',
  }).then((res) => {
    invalidate(path);
    invalidate(`${path}-`);
    forgetMaps();
    return res;
  });
}

export function deleteBandeja(itemId) {
  return api(`/api/v1/bandeja/${encodeURIComponent(itemId)}`, { method: 'DELETE' });
}

export function listCaptures(params) {
  const q = params ? `?${params}` : '';
  return cached(`captures${q}`, () => api(`/api/v1/captures${q}`));
}

export function deleteCapture(captureId) {
  return deleteRecord('capture', captureId);
}

/* ---------- Finanzas: editar y borrar ---------- */

// Toda mutacion de finanzas invalida la familia "fin" completa. Los saldos,
// budgets, deudas y metas se derivan entre si, asi que invalidar por entidad
// dejaba lecturas mezcladas: el total actualizado con una lista vieja.
const FIN_PREFIXES = ['fin', 'transactions'];

function finWrite(path, method, payload) {
  return finance(path, {
    method,
    body: payload === undefined ? undefined : JSON.stringify(payload),
  }).then((res) => {
    invalidate(FIN_PREFIXES);
    return res;
  });
}

export function updateAccount(accountId, changes) {
  return finWrite(`/accounts/${encodeURIComponent(accountId)}`, 'PATCH', changes);
}

export function updateTransaction(transactionId, changes) {
  return finWrite(`/transactions/${encodeURIComponent(transactionId)}`, 'PATCH', changes);
}

export function updateBudget(budgetId, changes) {
  return finWrite(`/budgets/${encodeURIComponent(budgetId)}`, 'PATCH', changes);
}

export function updateDebt(debtId, changes) {
  return finWrite(`/debts/${encodeURIComponent(debtId)}`, 'PATCH', changes);
}

export function updateGoal(goalId, changes) {
  return finWrite(`/goals/${encodeURIComponent(goalId)}`, 'PATCH', changes);
}

export function updateCategory(categoryId, changes) {
  return finWrite(`/categories/${encodeURIComponent(categoryId)}`, 'PATCH', changes);
}

export function updateInstitution(institutionId, changes) {
  return finWrite(`/financial-institutions/${encodeURIComponent(institutionId)}`, 'PATCH', changes);
}

export function updateIncomeSource(sourceId, changes) {
  return finWrite(`/income-sources/${encodeURIComponent(sourceId)}`, 'PATCH', changes);
}

export function updateMember(memberId, changes) {
  return finWrite(`/members/${encodeURIComponent(memberId)}`, 'PATCH', changes);
}

export function updateHousehold(householdId, changes) {
  return finWrite(`/households/${encodeURIComponent(householdId)}`, 'PATCH', changes);
}

// Solo las entidades sin historial financiero tienen DELETE. Un movimiento, un
// presupuesto o una deuda no se borran: se anulan o se cierran, para que el
// historial del hogar no cambie bajo los pies.
export function deleteGoal(goalId) {
  return finWrite(`/goals/${encodeURIComponent(goalId)}`, 'DELETE');
}

export function deleteInstitution(institutionId) {
  return finWrite(`/financial-institutions/${encodeURIComponent(institutionId)}`, 'DELETE');
}

export function deleteIncomeSource(sourceId) {
  return finWrite(`/income-sources/${encodeURIComponent(sourceId)}`, 'DELETE');
}

export function deleteMember(memberId) {
  return finWrite(`/members/${encodeURIComponent(memberId)}`, 'DELETE');
}
