'use strict';

import {
  api,
  invalidate,
  listHouseholds,
  createHousehold,
  createHouseholdMember,
  listAccounts,
  createAccount,
  patchAccount,
  listInstitutions,
  listCategoriesByHousehold,
  listTransactions,
  createTransaction,
  voidTransaction,
  dashboard,
  upcomingPayments,
  debtSummary,
  netWorth,
  listDebtsByHousehold,
  createDebt,
  listBudgetsByHousehold,
  createBudget,
  listGoalsByHousehold,
  createGoal,
  contributeGoal,
} from './api.js';
import {
  esc,
  fmtDate,
  todayISO,
  money,
  icon,
  badge,
  toast,
  skeleton,
  emptyBlock,
  errorBlock,
  openForm,
} from './ui.js';

const state = {
  month: '',
};

const MONTHS = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

function monthParts() {
  const [y, m] = (state.month || currentMonth()).split('-').map(Number);
  return { year: y, month: m };
}

/* ============================================================
   Vista principal (sub-router)
   ============================================================ */

export async function renderFinanzas(el, sub = 'resumen') {
  if (!state.month) state.month = currentMonth();
  try {
    const households = await listHouseholds();
    if (!households || !households.length) {
      return renderSetup(el, () => renderFinanzas(el, sub));
    }
    const household = households[0];
    if (sub === 'ingresos') return renderFlujo(el, household, 'income');
    if (sub === 'egresos') return renderFlujo(el, household, 'expense');
    if (sub === 'cuentas') return renderCuentas(el, household);
    if (sub === 'deudas') return renderDeudas(el, household);
    if (sub === 'presupuesto') return renderPresupuesto(el, household);
    if (sub === 'metas') return renderMetas(el, household);
    return renderResumen(el, household);
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Finanzas</h1></div>${errorBlock(`No disponible: ${err.message}`)}`;
  }
}

function monthPicker(extraClass = '') {
  return `<label class="month-picker"><span class="item-sub">${icon('calendar')}</span>
    <input type="month" class="form-control" id="fin-month" value="${esc(state.month)}" aria-label="Período" /></label>`;
}

function bindMonth(el, cb) {
  const input = el.querySelector('#fin-month');
  if (!input) return;
  input.addEventListener('change', () => {
    if (!input.value) return;
    state.month = input.value;
    cb();
  });
}

/* ---------- Configuración inicial ---------- */

function renderSetup(el, again) {
  el.innerHTML = `
    <div class="page-head">
      <h1>Finanzas</h1>
      <p class="page-sub">Primero, crea tu hogar financiero, el miembro administrador y una cuenta.</p>
    </div>
    <section class="card" style="max-width:560px">
      <div class="card-body">
        <label class="modal-label" for="st-name">Nombre del hogar</label>
        <input id="st-name" class="form-control" value="Hogar principal" maxlength="200" />
        <label class="modal-label" for="st-member">Miembro administrador (tu nombre)</label>
        <input id="st-member" class="form-control" value="" placeholder="Ejemplo: Joaquín" maxlength="200" />
        <label class="modal-label" for="st-account">Cuenta inicial</label>
        <input id="st-account" class="form-control" value="Cuenta principal" maxlength="200" />
        <label class="modal-label" for="st-balance">Saldo reportado (pesos)</label>
        <input id="st-balance" class="form-control" type="number" min="0" value="0" />
        <div class="modal-actions">
          <button class="btn btn-primary" id="st-go">${icon('plus')} Crear y empezar</button>
        </div>
      </div>
    </section>`;
  el.querySelector('#st-go').addEventListener('click', async () => {
    const name = el.querySelector('#st-name').value.trim();
    const member = el.querySelector('#st-member').value.trim();
    const account = el.querySelector('#st-account').value.trim();
    const balance = Number(el.querySelector('#st-balance').value) || 0;
    if (!name || !member) {
      toast('Nombre del hogar y miembro son obligatorios', 'error');
      return;
    }
    try {
      const household = await createHousehold({ name, timezone: 'America/Santiago', status: 'active' });
      await createHouseholdMember(household.id, { name: member, role: 'admin', status: 'active' });
      await createAccount({
        household_id: household.id,
        name: account || 'Cuenta principal',
        type: 'checking',
        currency: 'CLP',
        balance_reported: balance,
        balance_calculated: balance,
        status: 'active',
      });
      invalidate(['fin']);
      toast('Hogar financiero creado', 'success');
      again();
    } catch (err) {
      toast(`No se pudo crear: ${err.message}`, 'error');
    }
  });
}

/* ---------- Resumen ---------- */

async function renderResumen(el, household) {
  el.innerHTML = `
    <div class="page-head">
      <h1>Finanzas · Resumen</h1>
      <p class="page-sub">${esc(household.name)} — escoge un período y observa el flujo.</p>
      <div class="page-head-actions">${monthPicker()}</div>
    </div>
    ${skeleton(6)}`;
  const { year, month } = monthParts();
  try {
    const [dash, up] = await Promise.all([
      dashboard(household.id, year, month),
      upcomingPayments(household.id, 30),
    ]);
    const pct = dash.expected_income ? Math.round((dash.income / dash.expected_income) * 100) : 0;

    el.innerHTML = `
      <div class="page-head">
        <h1>Finanzas · Resumen</h1>
        <p class="page-sub">${esc(household.name)} — ${esc(MONTHS[month - 1])} ${esc(String(year))}</p>
        <div class="page-head-actions">${monthPicker()}</div>
      </div>
      <div class="kpi-row">
        <div class="kpi"><span class="kpi-icon tone-success">${icon('arrow')}</span><div class="kpi-meta"><span class="kpi-label">Ingresos del mes</span><span class="kpi-value">${money(dash.income)}</span><span class="kpi-meta">${pct}% del esperado (${money(dash.expected_income)})</span></div></div>
        <div class="kpi"><span class="kpi-icon tone-danger">${icon('flag')}</span><div class="kpi-meta"><span class="kpi-label">Gastos del mes</span><span class="kpi-value">${money(dash.expenses)}</span><span class="kpi-meta">${dash.expenses ? Math.round((dash.expenses / (dash.income || 1)) * 100) : 0}% del ingreso</span></div></div>
        <div class="kpi ${dash.balance >= 0 ? '' : 'tone-danger'}"><span class="kpi-icon ${dash.balance >= 0 ? 'tone-accent' : 'tone-danger'}">${icon('target')}</span><div class="kpi-meta"><span class="kpi-label">Resultado del mes</span><span class="kpi-value">${money(dash.balance)}</span><span class="kpi-meta">${dash.balance >= 0 ? 'superávit' : 'déficit'}</span></div></div>
        <div class="kpi"><span class="kpi-icon tone-primary">${icon('sparkles')}</span><div class="kpi-meta"><span class="kpi-label">Patrimonio</span><span class="kpi-value">${money(dash.net_worth)}</span><span class="kpi-meta">deuda total: ${money(dash.total_debt)}</span></div></div>
      </div>

      <div class="page-grid two">
        <section class="card">
          <div class="card-head"><h2>${icon('calendar')} Flujo mensual ${esc(String(year))}</h2></div>
          <div class="card-body">
            <div class="chart-bars">${dash.series.map((s) => {
              const peak = maxOf(dash.series);
              const expH = Math.round((s.expenses / peak) * 100);
              const incH = Math.round((s.income / peak) * 100);
              return `
              <div class="chart-col" title="${esc(MONTHS[s.month - 1])} · ingreso ${money(s.income)} · gasto ${money(s.expenses)}">
                ${s.expenses ? `<div class="bar bar-expense" style="height:${expH}%"></div>` : `<div class="bar bar-expense bar-empty"></div>`}
                ${s.income ? `<div class="bar bar-income" style="height:${incH}%"></div>` : `<div class="bar bar-income bar-empty"></div>`}
                <span class="chart-label">${esc(MONTHS[s.month - 1].slice(0, 3))}</span>
              </div>`;
            }).join('')}</div>
          </div>
        </section>
        <section class="card">
          <div class="card-head"><h2>${icon('folder')} Gastos por categoría</h2><a class="card-action" href="#/finanzas/egresos">Detalle</a></div>
          <div class="card-body no-pad">
            ${dash.expense_categories.length ? `<div class="bar-list" style="padding:14px 18px">
              ${dash.expense_categories.map((c) => `
                <div class="bar-row">
                  <span class="bar-name">${esc(c.name)}</span>
                  <div class="bar-track"><div class="bar-fill" style="width:${Math.round((c.amount / (dash.expenses || 1)) * 100)}%"></div></div>
                  <span class="bar-amt">${money(c.amount)}</span>
                </div>`).join('')}
            </div>` : `<div class="card-body">${emptyBlock('Sin gastos categorizados este mes.')}</div>`}
          </div>
        </section>
      </div>

      <div class="page-grid two">
        <section class="card">
          <div class="card-head"><h2>${icon('target')} Presupuesto del período</h2><a class="card-action" href="#/finanzas/presupuesto">Editar</a></div>
          <div class="card-body no-pad">
            ${dash.budget.length ? `<div class="bar-list" style="padding:14px 18px">
              ${dash.budget.map((b) => {
                const used = b.planned ? Math.round((b.actual / b.planned) * 100) : 0;
                return `<div class="bar-row"><span class="bar-name">${esc(b.category_name || 'Categoría')}</span>
                  <div class="bar-track"><div class="bar-fill ${used > 100 ? 'over' : ''}" style="width:${Math.min(100, used)}%"></div></div>
                  <span class="bar-amt">${money(b.actual)} / ${money(b.planned)}</span></div>`;
              }).join('')}
            </div>` : `<div class="card-body">${emptyBlock('Sin presupuesto para este mes.', '<a class="btn btn-soft btn-sm" href="#/finanzas/presupuesto">Crear presupuesto</a>')}</div>`}
          </div>
        </section>
        <section class="card">
          <div class="card-head"><h2>${icon('clock')} Pagos próximos (30 días)</h2></div>
          <div class="card-body no-pad">
            ${renderUpcoming(up)}
          </div>
        </section>
      </div>`;
    bindMonth(el, () => renderResumen(el, household));
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Finanzas · Resumen</h1></div>${errorBlock(`No disponible: ${err.message}`)}`;
  }
}

function maxOf(series) {
  return Math.max(1, ...series.map((s) => Math.max(s.income, s.expenses)));
}

function renderUpcoming(up) {
  const rows = [];
  for (const i of up.pending_installments || []) {
    rows.push({ due: i.due_date, name: `Cuota de deuda (${i.debt_id.slice(0, 6)})`, amount: i.total_amount, days: i.days_left });
  }
  for (const r of up.recurring_minimums || []) {
    rows.push({ due: r.due_date, name: `${r.debt_name} — pago mínimo`, amount: r.minimum_payment, days: null });
  }
  rows.sort((a, b) => (a.due < b.due ? -1 : 1));
  if (!rows.length) return `<div class="card-body">${emptyBlock('Nada pendiente en los próximos 30 días.')}</div>`;
  return `<div class="list" style="padding:0 18px">
    ${rows.slice(0, 8).map((r) => `
      <div class="item">
        <div class="item-main"><div class="item-title">${esc(r.name)}</div>
        <div class="item-sub">vence ${esc(fmtDate(r.due))}${r.days !== null ? ` · en ${esc(r.days)} días` : ''}</div></div>
        <div class="item-side">${money(r.amount)}</div>
      </div>`).join('')}
  </div>`;
}

/* ---------- Ingresos / Egresos ---------- */

async function renderFlujo(el, household, type) {
  const ingress = type === 'income';
  el.innerHTML = `
    <div class="page-head">
      <h1>Finanzas · ${ingress ? 'Ingresos' : 'Egresos'}</h1>
      <p class="page-sub">Movimientos de ${ingress ? 'ingreso' : 'egreso'} registrados.</p>
      <div class="page-head-actions">
        ${monthPicker('mr-8')}
        <button class="btn btn-primary" id="fin-new">${icon('plus')} Registrar</button>
      </div>
    </div>
    ${skeleton(5)}`;
  const { year, month } = monthParts();
  try {
    const [accounts, categories, members, txns] = await Promise.all([
      listAccounts(),
      listCategoriesByHousehold(household.id),
      api(`/api/v1/finance/households/${encodeURIComponent(household.id)}/members`),
      listTransactions({
        household_id: household.id,
        year,
        month,
        type,
      }),
    ]);
    const catById = new Map((categories || []).map((c) => [c.id, c]));
    el.innerHTML = `
      <div class="page-head">
        <h1>Finanzas · ${ingress ? 'Ingresos' : 'Egresos'}</h1>
        <p class="page-sub">${esc(MONTHS[month - 1])} ${esc(String(year))} · ${esc(txns.length)} movimientos.</p>
        <div class="page-head-actions">
          ${monthPicker('mr-8')}
          <button class="btn btn-primary" id="fin-new">${icon('plus')} Registrar</button>
        </div>
      </div>
      <section class="card">
        <div class="card-body no-pad">
          ${txns.length ? `<div class="table-wrap"><table class="table">
            <thead><tr><th>Fecha</th><th>Descripción</th><th>Categoría</th><th>Cuenta</th><th class="num">Monto</th><th></th></tr></thead>
            <tbody>
              ${txns.map((t) => `
                <tr>
                  <td>${esc(fmtDate(t.date))}</td>
                  <td>${esc(t.description || '—')}</td>
                  <td>${esc((catById.get(t.category_id) || {}).name || t.category_id || '—')}</td>
                  <td>${esc(t.account_id.slice(0, 8))}</td>
                  <td class="num ${ingress ? 'text-success' : 'text-danger'}">${ingress ? '+' : '−'}${money(t.amount)}</td>
                  <td>${t.status === 'voided' ? badge('voided') : `<button class="btn btn-ghost btn-xs" data-fin-void="${esc(t.id)}">${icon('trash')}</button>`}</td>
                </tr>`).join('')}
            </tbody>
          </table></div>` : `<div class="card-body">${emptyBlock(
            `Sin ${ingress ? 'ingresos' : 'egresos'} en este período.`,
            '<button class="btn btn-soft btn-sm" id="fin-new2">Registrar movimiento</button>',
          )}</div>`}
        </div>
      </section>`;

    bindMonth(el, () => renderFlujo(el, household, type));
    bindNew(el, { household, accounts, categories, members, type, again: () => renderFlujo(el, household, type) });
    bindVoid(el, () => renderFlujo(el, household, type));
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Finanzas · ${ingress ? 'Ingresos' : 'Egresos'}</h1></div>${errorBlock(`No disponible: ${err.message}`)}`;
  }
}

async function bindNew(el, { household, accounts, categories, members, type, again }) {
  const go = (e) => {
    const btn = e.target.closest('#fin-new, #fin-new2');
    if (!btn) return;
    openForm({
      title: type === 'income' ? 'Registrar ingreso' : 'Registrar gasto',
      submitLabel: 'Registrar',
      hint: 'Crea un ingreso o gasto simple. Los montos se anotan en pesos.',
      fields: [
        { name: 'type', label: 'Tipo', type: 'select', required: true, value: type, options: [['income', 'Ingreso'], ['expense', 'Gasto'], ['transfer', 'Transferencia']].map(([v, l]) => ({ value: v, label: l })) },
        { name: 'amount', label: 'Monto', type: 'text', required: true, placeholder: '15000' },
        { name: 'account_id', label: 'Cuenta', type: 'select', required: true, options: (accounts || []).filter((a) => a.status === 'active').map((a) => ({ value: a.id, label: `${a.name} (${a.type})` })) },
        { name: 'to_account_id', label: 'Cuenta destino (solo transferencia)', type: 'select', options: [{ value: '', label: 'Ninguna' }, ...(accounts || []).filter((a) => a.status === 'active').map((a) => ({ value: a.id, label: a.name }))] },
        { name: 'category_id', label: 'Categoría', type: 'select', options: [{ value: '', label: 'Sin categoría' }, ...(categories || []).filter((c) => c.kind === type || c.kind === 'transfer').map((c) => ({ value: c.id, label: `${c.name} (${c.kind})` }))] },
        { name: 'date', label: 'Fecha', type: 'date', value: todayISO() },
        { name: 'description', label: 'Descripción', type: 'text', maxlength: 500, placeholder: 'Supermercado' },
      ],
    }).then(async (v) => {
      if (!v) return;
      const amount = Number(v.amount);
      if (!amount || amount <= 0) return toast('Monto inválido', 'error');
      if (v.type === 'transfer' && v.to_account_id === v.account_id) return toast('Cuenta origen y destino iguales', 'error');
      const member = (members || []).find((m) => m.role === 'admin');
      try {
        await createTransaction({
          account_id: v.account_id,
          to_account_id: v.type === 'transfer' ? v.to_account_id || undefined : undefined,
          category_id: v.category_id || undefined,
          recorded_by: member ? member.id : undefined,
          type: v.type,
          amount,
          date: v.date,
          description: v.description || undefined,
        });
        invalidate(['fin', 'transactions']);
        toast('Movimiento registrado', 'success');
        again();
      } catch (err) {
        toast(`No se pudo registrar: ${err.message}`, 'error');
      }
    });
  };
  el.addEventListener('click', go);
}

function bindVoid(el, again) {
  el.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-fin-void]');
    if (!btn) return;
    if (!window.confirm('Anular este movimiento?')) return;
    try {
      await voidTransaction(btn.dataset.finVoid);
      invalidate(['transactions']);
      toast('Movimiento anulado', 'success');
      again();
    } catch (err) {
      toast(`No se pudo anular: ${err.message}`, 'error');
    }
  });
}

/* ---------- Cuentas ---------- */

async function renderCuentas(el, household) {
  el.innerHTML = `
    <div class="page-head">
      <h1>Finanzas · Cuentas</h1>
      <p class="page-sub">Saldo reportado vs. calculado a partir de transacciones.</p>
      <div class="page-head-actions"><button class="btn btn-primary" id="fin-acc-new">${icon('plus')} Nueva cuenta</button></div>
    </div>
    ${skeleton(3)}`;
  try {
    const [accounts, institutions] = await Promise.all([listAccounts(), listInstitutions()]);
    const instById = new Map((institutions || []).map((i) => [i.id, i]));
    const total = (accounts || []).reduce((s, a) => s + (a.balance_calculated || 0), 0);
    el.innerHTML = `
      <div class="page-head">
        <h1>Finanzas · Cuentas</h1>
        <p class="page-sub">Saldo total calculado: <b>${money(total)}</b></p>
        <div class="page-head-actions"><button class="btn btn-primary" id="fin-acc-new">${icon('plus')} Nueva cuenta</button></div>
      </div>
      ${!(accounts || []).length ? `<section class="card"><div class="card-body">${emptyBlock('Sin cuentas aún.', '<button class="btn btn-soft btn-sm" id="fin-acc-new2">Nueva cuenta</button>')}</div></section>` : `
      <div class="page-grid">
        ${(accounts || []).map((a) => `
          <section class="card">
            <div class="card-body">
              <div class="habit-head">
                <div><div class="habit-name">${esc(a.name)}</div>
                <div class="habit-goal">${esc(a.type)} · ${esc(a.currency)}${a.institution_name ? ` · ${esc(a.institution_name)}` : ''}${instById.get(a.institution_id)?.name ? ` · ${esc(instById.get(a.institution_id).name)}` : ''}</div></div>
                <div class="item-side">${badge(a.status)}</div>
              </div>
              <div class="kpi-row" style="margin:6px 0 0">
                <div class="kpi"><div class="kpi-meta"><span class="kpi-label">Calculado</span><span class="kpi-value">${money(a.balance_calculated)}</span></div></div>
                <div class="kpi"><div class="kpi-meta"><span class="kpi-label">Reportado</span><span class="kpi-value">${money(a.balance_reported)}</span></div></div>
              </div>
              ${a.type === 'credit' ? `<div class="habit-goal">Límite: ${money(a.credit_limit)} · vence día ${a.due_day ?? '—'}</div>` : ''}
              <div class="habit-actions">
                <button class="btn btn-ghost btn-xs" data-fin-acc-toggle="${esc(a.id)}" data-status="${a.status === 'active' ? 'inactive' : 'active'}">${a.status === 'active' ? 'Desactivar' : 'Reactivar'}</button>
                <button class="btn btn-ghost btn-xs" data-fin-acc-balance="${esc(a.id)}">${icon('edit')} Ajustar saldo</button>
              </div>
            </div>
          </section>`).join('')}
      </div>`}
      <section class="card" style="margin-top:16px">
        <div class="card-head"><h2>${icon('link')} Instituciones</h2></div>
        <div class="card-body no-pad">
          ${(institutions || []).length ? `<div class="list" style="padding:0 18px">${(institutions || []).map((i) => `<div class="item"><div class="item-main"><div class="item-title">${esc(i.name)}</div><div class="item-sub">${esc(i.type)}</div></div>${badge(i.status)}</div>`).join('')}</div>` : emptyBlock('Sin instituciones. Se crean al agregar una cuenta.')}
        </div>
      </section>`;

    bind(el, '#fin-acc-new, #fin-acc-new2', () => accountModal(el, household, institutions));
    bindToggle(el);
    bindBalance(el, () => renderCuentas(el, household));
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Finanzas · Cuentas</h1></div>${errorBlock(`No disponible: ${err.message}`)}`;
  }
}

const bind = (el, selector, cb) => {
  el.addEventListener('click', (e) => {
    if (e.target.closest(selector)) cb();
  });
};

async function accountModal(el, household, institutions) {
  const v = await openForm({
    title: 'Nueva cuenta',
    submitLabel: 'Crear',
    fields: [
      { name: 'name', label: 'Nombre', type: 'text', required: true, placeholder: 'Cuenta corriente' },
      { name: 'type', label: 'Tipo', type: 'select', required: true, value: 'checking', options: [['checking', 'Cuenta corriente'], ['savings', 'Ahorro'], ['credit', 'Tarjeta de crédito'], ['cash', 'Efectivo'], ['other', 'Otra']].map(([v, l]) => ({ value: v, label: l })) },
      { name: 'institution_id', label: 'Institución', type: 'select', options: [{ value: '', label: 'Sin institución' }, ...(institutions || []).map((i) => ({ value: i.id, label: i.name }))] },
      { name: 'balance_reported', label: 'Saldo reportado', type: 'text', value: '0', placeholder: '0' },
      { name: 'credit_limit', label: 'Límite (solo crédito)', type: 'text', placeholder: '1000000' },
      { name: 'due_day', label: 'Día de vencimiento', type: 'text', placeholder: '5' },
    ],
  });
  if (!v) return;
  try {
    await createAccount({
      household_id: household.id,
      name: v.name,
      type: v.type,
      currency: 'CLP',
      balance_reported: Number(v.balance_reported) || 0,
      balance_calculated: Number(v.balance_reported) || 0,
      credit_limit: v.type === 'credit' && v.credit_limit ? Number(v.credit_limit) : undefined,
      due_day: v.type === 'credit' && v.due_day ? Number(v.due_day) : undefined,
      institution_id: v.institution_id || undefined,
      status: 'active',
    });
    invalidate(['fin']);
    toast('Cuenta creada', 'success');
    renderCuentas(el, household);
  } catch (err) {
    toast(`No se pudo crear: ${err.message}`, 'error');
  }
}

function bindToggle(el) {
  el.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-fin-acc-toggle]');
    if (!btn) return;
    try {
      await patchAccount(btn.dataset.finAccToggle, { status: btn.dataset.status });
      invalidate(['fin']);
      toast('Cuenta actualizada', 'success');
      location.reload();
    } catch (err) {
      toast(`No se pudo actualizar: ${err.message}`, 'error');
    }
  });
}

async function bindBalance(el, again) {
  el.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-fin-acc-balance]');
    if (!btn) return;
    const v = await openForm({ title: 'Ajustar saldo calculado', submitLabel: 'Guardar', fields: [{ name: 'balance_calculated', label: 'Nuevo saldo', type: 'text', required: true }] });
    if (!v) return;
    try {
      await patchAccount(btn.dataset.finAccBalance, { balance_calculated: Number(v.balance_calculated) || 0 });
      invalidate(['fin']);
      toast('Saldo ajustado', 'success');
      again();
    } catch (err) {
      toast(`No se pudo ajustar: ${err.message}`, 'error');
    }
  });
}

/* ---------- Deudas ---------- */

async function renderDeudas(el, household) {
  el.innerHTML = `
    <div class="page-head">
      <h1>Finanzas · Tarjetas y deudas</h1>
      <p class="page-sub">Deudas activas y consolidado.</p>
      <div class="page-head-actions"><button class="btn btn-primary" id="fin-debt-new">${icon('plus')} Nueva deuda</button></div>
    </div>
    ${skeleton(3)}`;
  try {
    const [summary, debts, accounts] = await Promise.all([
      debtSummary(household.id),
      listDebtsByHousehold(household.id),
      listAccounts(),
    ]);
    const byStatus = summary.by_status || {};
    el.innerHTML = `
      <div class="page-head">
        <h1>Finanzas · Tarjetas y deudas</h1>
        <p class="page-sub">${esc(debts.length)} deudas registradas.</p>
        <div class="page-head-actions"><button class="btn btn-primary" id="fin-debt-new">${icon('plus')} Nueva deuda</button></div>
      </div>
      <div class="kpi-row">
        <div class="kpi"><span class="kpi-icon tone-danger">${icon('alert')}</span><div class="kpi-meta"><span class="kpi-label">Saldo total</span><span class="kpi-value">${money(summary.total_current_balance)}</span><span class="kpi-meta">original: ${money(summary.total_original_amount)}</span></div></div>
        <div class="kpi"><span class="kpi-icon tone-primary">${icon('folder')}</span><div class="kpi-meta"><span class="kpi-label">Activas</span><span class="kpi-value">${esc((byStatus.active || {}).count || 0)}</span><span class="kpi-meta">${money((byStatus.active || {}).current_balance || 0)}</span></div></div>
        <div class="kpi"><span class="kpi-icon tone-success">${icon('check')}</span><div class="kpi-meta"><span class="kpi-label">Pagadas</span><span class="kpi-value">${esc((byStatus.paid_off || {}).count || 0)}</span></div></div>
      </div>
      <section class="card">
        <div class="card-body no-pad">
          ${debts.length ? `<div class="table-wrap"><table class="table">
            <thead><tr><th>Nombre</th><th>Tipo</th><th class="num">Original</th><th class="num">Saldo actual</th><th class="num">Pago mín.</th><th>Día</th><th></th></tr></thead>
            <tbody>
              ${debts.map((d) => `
                <tr>
                  <td>${esc(d.name)}</td>
                  <td>${esc(d.type)}</td>
                  <td class="num">${money(d.original_amount)}</td>
                  <td class="num">${money(d.current_balance)}</td>
                  <td class="num">${money(d.minimum_payment)}</td>
                  <td>${esc(d.due_day)}</td>
                  <td>${badge(d.status)}</td>
                </tr>`).join('')}
            </tbody>
          </table></div>` : `<div class="card-body">${emptyBlock('Sin deudas registradas.', '<button class="btn btn-soft btn-sm" id="fin-debt-new2">Registrar deuda</button>')}</div>`}
        </div>
      </section>`;
    bind(el, '#fin-debt-new, #fin-debt-new2', () => debtModal(el, household, accounts));
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Finanzas · Deudas</h1></div>${errorBlock(`No disponible: ${err.message}`)}`;
  }
}

async function debtModal(el, household, accounts) {
  const v = await openForm({
    title: 'Nueva deuda',
    submitLabel: 'Crear',
    fields: [
      { name: 'name', label: 'Nombre', type: 'text', required: true, placeholder: 'Tarjeta Banco X' },
      { name: 'type', label: 'Tipo', type: 'select', required: true, value: 'credit_card', options: [['credit_card', 'Tarjeta de crédito'], ['loan', 'Préstamo'], ['auto', 'Auto'], ['mortgage', 'Hipoteca'], ['line', 'Línea de crédito'], ['other', 'Otra']].map(([v, l]) => ({ value: v, label: l })) },
      { name: 'account_id', label: 'Cuenta asociada', type: 'select', options: [{ value: '', label: 'Ninguna' }, ...(accounts || []).map((a) => ({ value: a.id, label: a.name }))] },
      { name: 'original_amount', label: 'Monto original', type: 'text', required: true, placeholder: '1000000' },
      { name: 'current_balance', label: 'Saldo actual', type: 'text', placeholder: 'Mismo que original' },
      { name: 'minimum_payment', label: 'Pago mínimo', type: 'text', placeholder: '25000' },
      { name: 'interest_rate', label: 'Tasa % mensual', type: 'text', placeholder: '2.0' },
      { name: 'due_day', label: 'Día de pago (1-31)', type: 'text', placeholder: '5' },
    ],
  });
  if (!v) return;
  try {
    await createDebt(household.id, {
      account_id: v.account_id || undefined,
      name: v.name,
      type: v.type,
      original_amount: Number(v.original_amount) || 0,
      minimum_payment: Number(v.minimum_payment) || 0,
      interest_rate: Number(v.interest_rate) || 0,
      due_day: Number(v.due_day) || 1,
      status: 'active',
    });
    invalidate(['fin']);
    toast('Deuda registrada', 'success');
    renderDeudas(el, household);
  } catch (err) {
    toast(`No se pudo crear: ${err.message}`, 'error');
  }
}

/* ---------- Presupuesto ---------- */

async function renderPresupuesto(el, household) {
  el.innerHTML = `
    <div class="page-head">
      <h1>Finanzas · Presupuesto</h1>
      <p class="page-sub">Planeado vs. real por categoría.</p>
      <div class="page-head-actions">${monthPicker()}</div>
    </div>
    ${skeleton(4)}`;
  const { year, month } = monthParts();
  try {
    const [dash, budgets, categories] = await Promise.all([
      dashboard(household.id, year, month),
      listBudgetsByHousehold(household.id),
      listCategoriesByHousehold(household.id),
    ]);
    const budget = (budgets || []).find((b) => b.year === year && b.month === month);
    const totalPlanned = dash.budget.reduce((s, b) => s + (b.planned || 0), 0);
    const totalActual = dash.budget.reduce((s, b) => s + (b.actual || 0), 0);
    const budgetCategories = (categories || []).filter((c) => c.kind === 'expense' || c.kind === 'transfer');

    el.innerHTML = `
      <div class="page-head">
        <h1>Finanzas · Presupuesto</h1>
        <p class="page-sub">${esc(MONTHS[month - 1])} ${esc(String(year))}${budget ? ` · estado ${esc(budget.status)}` : ' · sin presupuesto'}</p>
        <div class="page-head-actions">${monthPicker()}</div>
      </div>
      ${budget ? `
        <div class="kpi-row">
          <div class="kpi"><span class="kpi-icon tone-accent">${icon('target')}</span><div class="kpi-meta"><span class="kpi-label">Planeado</span><span class="kpi-value">${money(totalPlanned)}</span></div></div>
          <div class="kpi"><span class="kpi-icon tone-danger">${icon('flag')}</span><div class="kpi-meta"><span class="kpi-label">Real</span><span class="kpi-value">${money(totalActual)}</span></div></div>
          <div class="kpi"><span class="kpi-icon tone-primary">${icon('sparkles')}</span><div class="kpi-meta"><span class="kpi-label">Avance</span><span class="kpi-value">${totalPlanned ? Math.round((totalActual / totalPlanned) * 100) : 0}%</span></div></div>
        </div>
        <section class="card">
          <div class="card-head"><h2>${icon('folder')} Categorías del presupuesto</h2>
            <button class="btn btn-ghost btn-sm" id="fin-budget-add">${icon('plus')} Añadir categoría</button></div>
          <div class="card-body no-pad">
            ${dash.budget.length ? `<div class="bar-list" style="padding:14px 18px">
              ${dash.budget.map((b) => {
                const used = b.planned ? Math.round((b.actual / b.planned) * 100) : 0;
                return `<div class="bar-row">
                  <span class="bar-name">${esc(b.category_name || 'Categoría')}</span>
                  <div class="bar-track"><div class="bar-fill ${used > 100 ? 'over' : ''}" style="width:${Math.min(100, used)}%"></div></div>
                  <span class="bar-amt">${money(b.actual)} / ${money(b.planned)} (${used}%)</span>
                </div>`;
              }).join('')}
            </div>` : `<div class="card-body">${emptyBlock('Presupuesto sin categorías todavía.')}</div>`}
          </div>
        </section>
        <section class="card" style="margin-top:16px">
          <div class="card-head"><h2>${icon('folder')} Categorías disponibles</h2></div>
          <div class="card-body no-pad">
            <div class="list" style="padding:0 18px">
              ${budgetCategories.map((c) => `<div class="item"><div class="item-main"><div class="item-title">${esc(c.name)}</div><div class="item-sub">${esc(c.kind)}</div></div>${badge(c.status)}</div>`).join('')}
            </div>
          </div>
        </section>`
      : `<section class="card"><div class="card-body">${emptyBlock('Aún no hay presupuesto para este período.', '<button class="btn btn-primary btn-sm" id="fin-budget-create">Crear presupuesto del mes</button>')}</div></section>`}`;
    bindMonth(el, () => renderPresupuesto(el, household));
    bindBudgetCreate(el, household, year, month);
    bindBudgetAddCategory(el, household, budget, budgetCategories);
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Finanzas · Presupuesto</h1></div>${errorBlock(`No disponible: ${err.message}`)}`;
  }
}

async function bindBudgetCreate(el, household, year, month) {
  const btn = el.querySelector('#fin-budget-create');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    try {
      await createBudget(household.id, { year, month, status: 'active' });
      invalidate(['fin', 'budgets']);
      toast('Presupuesto creado', 'success');
      renderPresupuesto(el, household);
    } catch (err) {
      toast(`No se pudo crear: ${err.message}`, 'error');
    }
  });
}

async function bindBudgetAddCategory(el, household, budget, categoryList) {
  const btn = el.querySelector('#fin-budget-add');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    if (!budget) return;
    const v = await openForm({
      title: 'Añadir categoría al presupuesto',
      submitLabel: 'Añadir',
      fields: [
        { name: 'category_id', label: 'Categoría', type: 'select', required: true, options: categoryList.map((c) => ({ value: c.id, label: `${c.name} (${c.kind})` })) },
        { name: 'planned_amount', label: 'Monto planeado', type: 'text', required: true, placeholder: '50000' },
      ],
    });
    if (!v) return;
    try {
      await api(`/api/v1/finance/budgets/${encodeURIComponent(budget.id)}/categories`, {
        method: 'POST',
        body: JSON.stringify({ category_id: v.category_id, planned_amount: Number(v.planned_amount) || 0 }),
      });
      invalidate(['fin', 'budgets']);
      toast('Categoría añadida', 'success');
      renderPresupuesto(el, household);
    } catch (err) {
      toast(`No se pudo añadir: ${err.message}`, 'error');
    }
  });
}

/* ---------- Metas de ahorro ---------- */

async function renderMetas(el, household) {
  el.innerHTML = `
    <div class="page-head">
      <h1>Finanzas · Metas de ahorro</h1>
      <p class="page-sub">Objetivos de ahorro con progreso.</p>
      <div class="page-head-actions"><button class="btn btn-primary" id="fin-goal-new">${icon('plus')} Nueva meta</button></div>
    </div>
    ${skeleton(3)}`;
  try {
    const [goals, accounts] = await Promise.all([listGoalsByHousehold(household.id), listAccounts()]);
    el.innerHTML = `
      <div class="page-head">
        <h1>Finanzas · Metas de ahorro</h1>
        <p class="page-sub">${esc(goals.length)} metas registradas.</p>
        <div class="page-head-actions"><button class="btn btn-primary" id="fin-goal-new">${icon('plus')} Nueva meta</button></div>
      </div>
      ${goals.length ? `<div class="page-grid">
        ${goals.map((g) => {
          const pct = g.target_amount ? Math.round((g.current_amount / g.target_amount) * 100) : 0;
          return `<section class="card">
            <div class="card-body">
              <div class="habit-head">
                <div><div class="habit-name">${esc(g.name)}</div>
                <div class="habit-goal">${esc(g.category)}${g.target_date ? ` · meta: ${esc(g.target_date)}` : ''}</div></div>
                <div class="item-side">${badge(g.status)}</div>
              </div>
              <div class="kpi-row" style="margin:6px 0 0">
                <div class="kpi"><div class="kpi-meta"><span class="kpi-label">Progreso</span><span class="kpi-value">${money(g.current_amount)}</span></div></div>
                <div class="kpi"><div class="kpi-meta"><span class="kpi-label">Meta</span><span class="kpi-value">${money(g.target_amount)}</span></div></div>
              </div>
              <div class="bar-track" style="margin:6px 0"><div class="bar-fill ${pct >= 100 ? 'over' : ''}" style="width:${Math.min(100, pct)}%"></div></div>
              <div class="habit-goal">${pct}% alcanzado · aporte mensual ${money(g.monthly_contribution)}</div>
              ${g.status === 'active' ? `<div class="modal-actions" style="margin-top:10px;justify-content:flex-start">
                <button class="btn btn-primary btn-xs" data-fin-goal-contribute="${esc(g.id)}">${icon('plus')} Aportar</button>
              </div>` : ''}
            </div>
          </section>`;
        }).join('')}
      </div>` : `<section class="card"><div class="card-body">${emptyBlock('Sin metas de ahorro.', '<button class="btn btn-soft btn-sm" id="fin-goal-new2">Crear meta</button>')}</div></section>`}`;
    bind(el, '#fin-goal-new, #fin-goal-new2', () => goalModal(el, household, accounts));
    bindContribute(el, accounts, () => renderMetas(el, household));
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Finanzas · Metas</h1></div>${errorBlock(`No disponible: ${err.message}`)}`;
  }
}

async function goalModal(el, household, accounts) {
  const v = await openForm({
    title: 'Nueva meta de ahorro',
    submitLabel: 'Crear',
    fields: [
      { name: 'name', label: 'Nombre', type: 'text', required: true, placeholder: 'Fondo de emergencia' },
      { name: 'category', label: 'Categoría', type: 'select', required: true, value: 'fondo', options: [['fondo', 'Fondo de emergencia'], ['security', 'Seguridad'], ['travel', 'Viaje'], ['purchase', 'Compra'], ['debt', 'Pago de deuda'], ['other', 'Otro']].map(([v, l]) => ({ value: v, label: l })) },
      { name: 'target_amount', label: 'Monto meta', type: 'text', required: true, placeholder: '1000000' },
      { name: 'current_amount', label: 'Ya ahorrado', type: 'text', placeholder: '0' },
      { name: 'monthly_contribution', label: 'Aporte mensual', type: 'text', placeholder: '50000' },
      { name: 'target_date', label: 'Fecha meta', type: 'date' },
    ],
  });
  if (!v) return;
  try {
    await createGoal(household.id, {
      name: v.name,
      category: v.category,
      target_amount: Number(v.target_amount) || 0,
      current_amount: Number(v.current_amount) || 0,
      monthly_contribution: Number(v.monthly_contribution) || 0,
      target_date: v.target_date || undefined,
      status: 'active',
    });
    invalidate(['fin', 'goals']);
    toast('Meta creada', 'success');
    renderMetas(el, household);
  } catch (err) {
    toast(`No se pudo crear: ${err.message}`, 'error');
  }
}

function bindContribute(el, accounts, again) {
  el.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-fin-goal-contribute]');
    if (!btn) return;
    const v = await openForm({
      title: 'Aportar a la meta',
      submitLabel: 'Aportar',
      hint: 'Crea una transacción de ahorro con la cuenta seleccionada.',
      fields: [
        { name: 'amount', label: 'Monto', type: 'text', required: true, placeholder: '10000' },
        { name: 'account_id', label: 'Cuenta origen', type: 'select', required: true, options: (accounts || []).filter((a) => a.status === 'active').map((a) => ({ value: a.id, label: `${a.name} (${a.type})` })) },
        { name: 'date', label: 'Fecha', type: 'date', value: todayISO() },
        { name: 'description', label: 'Descripción', type: 'text', maxlength: 500, placeholder: 'Aporte a meta' },
      ],
    });
    if (!v) return;
    try {
      await contributeGoal(btn.dataset.finGoalContribute, {
        amount: Number(v.amount) || 0,
        account_id: v.account_id,
        date: v.date,
        description: v.description || undefined,
      });
      invalidate(['fin', 'goals']);
      toast('Aporte registrado', 'success');
      again();
    } catch (err) {
      toast(`No se pudo aportar: ${err.message}`, 'error');
    }
  });
}