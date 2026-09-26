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
  deleteGoal,
  updateTransaction,
  updateGoal,
  updateDebt,
  updateBudget,
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
  availableBalance,
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
  progressBar,
  kpiTile,
  disponibleCard,
  explainError,
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
    if (sub === 'egresos') return renderEgresos(el, household);
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
    const [dash, up, available] = await Promise.all([
      dashboard(household.id, year, month),
      upcomingPayments(household.id, 30),
      availableBalance(household.id).catch(() => null),
    ]);
    const pct = dash.expected_income ? Math.round((dash.income / dash.expected_income) * 100) : 0;

    el.innerHTML = `
      <div class="page-head">
        <h1>Finanzas · Resumen</h1>
        <p class="page-sub">${esc(household.name)} — ${esc(MONTHS[month - 1])} ${esc(String(year))}</p>
        <div class="page-head-actions">${monthPicker()}</div>
      </div>
      ${disponibleCard({ available })}
      <div class="kpi-row">
        <div class="kpi"><span class="kpi-icon tone-success">${icon('arrow')}</span><div class="kpi-body"><span class="kpi-label">Ingresos del mes</span><span class="kpi-value">${money(dash.income)}</span><span class="kpi-note">${pct}% del esperado (${money(dash.expected_income)})</span></div></div>
        <div class="kpi"><span class="kpi-icon tone-danger">${icon('flag')}</span><div class="kpi-body"><span class="kpi-label">Gastos del mes</span><span class="kpi-value">${money(dash.expenses)}</span><span class="kpi-note">${dash.expenses ? Math.round((dash.expenses / (dash.income || 1)) * 100) : 0}% del ingreso</span></div></div>
        <div class="kpi ${dash.balance >= 0 ? '' : 'tone-danger'}"><span class="kpi-icon ${dash.balance >= 0 ? 'tone-accent' : 'tone-danger'}">${icon('target')}</span><div class="kpi-body"><span class="kpi-label">Resultado del mes</span><span class="kpi-value">${money(dash.balance)}</span><span class="kpi-note">${dash.balance >= 0 ? 'superávit' : 'déficit'}</span></div></div>
        <div class="kpi"><span class="kpi-icon tone-primary">${icon('sparkles')}</span><div class="kpi-body"><span class="kpi-label">Patrimonio</span><span class="kpi-value">${money(dash.net_worth)}</span><span class="kpi-note">deuda total: ${money(dash.total_debt)}</span></div></div>
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
  const ingresosView = type === 'income' ? 'Ingresos' : 'Egresos';
  el.innerHTML = `
    <div class="page-head">
      <h1>${ingresosView}</h1>
      <p class="page-sub">Movimientos de ${ingresosView.toLowerCase()} registrados en el período.</p>
      <div class="page-head-actions">
        ${monthPicker('mr-8')}
        <button class="btn btn-primary" id="fin-new">${icon('plus')} Registrar</button>
      </div>
    </div>
    ${skeleton(6)}`;
  const { year, month } = monthParts();
  try {
    const [accounts, categories, members, txns, up, goals, dash] = await Promise.all([
      listAccounts(),
      listCategoriesByHousehold(household.id),
      api(`/api/v1/finance/households/${encodeURIComponent(household.id)}/members`),
      listTransactions({
        household_id: household.id,
        year,
        month,
        type,
      }),
      upcomingPayments(household.id, 30),
      listGoalsByHousehold(household.id),
      dashboard(household.id, year, month),
    ]);
    const catById = new Map((categories || []).map((c) => [c.id, c]));
    const catsOfType = (categories || []).filter((c) => c.kind === type);
    const total = (txns || []).reduce((sum, t) => sum + t.amount, 0);
    const upcomingCount = (up?.pending_installments?.length || 0) + (up?.recurring_minimums?.length || 0);
    const planned = (dash.budget || []).reduce((a, b) => a + (b.planned || 0), 0);
    const used = (dash.budget || []).reduce((a, b) => a + (b.actual || 0), 0);
    const budgetPct = planned ? Math.round((used / planned) * 100) : 0;

    const monthLabel = `${MONTHS[month - 1]} ${esc(String(year))}`;

    const metas = (goals || []).filter((g) => g.status === 'active').slice(0, 3);
    const metasHtml = `
      <section class="card">
        <div class="card-head"><h2>${icon('target')} Metas de ahorro</h2><a class="card-action" href="#/finanzas/metas">Ver todas</a></div>
        <div class="card-body">
          ${metas.length
            ? `<div class="p-list">${metas.map((g) => {
                const p = g.target_amount ? Math.round((g.current_amount / g.target_amount) * 100) : 0;
                return `<li class="item">
                  <div class="item-main"><div class="item-title">${esc(g.name)}</div>
                  <div class="item-sub">${money(g.current_amount)} de ${money(g.target_amount)} · ${p}%</div></div>
                  <div class="item-side">${progressBar(p)}</div>
                </li>`;
              }).join('')}</div>`
            : emptyBlock('Sin metas de ahorro activas.', '<a class="btn btn-soft btn-sm" href="#/finanzas/metas">Crear meta</a>')}
        </div>
      </section>`;

    const upcomingHtml = `
      <section class="card">
        <div class="card-head"><h2>${icon('clock')} Pagos próximos (30 días)</h2><a class="card-action" href="#/finanzas/deudas">Deudas</a></div>
        <div class="card-body no-pad">${renderUpcoming(up)}</div>
      </section>`;

    const budgetHtml = `
      <section class="card">
        <div class="card-head"><h2>${icon('sparkles')} Presupuesto del período</h2><a class="card-action" href="#/finanzas/presupuesto">Editar</a></div>
        <div class="card-body no-pad">
          ${(dash.budget || []).length ? `<div class="bar-list" style="padding:14px 18px">
            ${dash.budget.map((b) => {
              const u = b.planned ? Math.round((b.actual / b.planned) * 100) : 0;
              return `<div class="bar-row"><span class="bar-name">${esc(b.category_name || 'Categoría')}</span>
                <div class="bar-track"><div class="bar-fill ${u > 100 ? 'over' : ''}" style="width:${Math.min(100, u)}%"></div></div>
                <span class="bar-amt">${money(b.actual)} / ${money(b.planned)}</span></div>`;
            }).join('')}
          </div>` : `<div class="card-body">${emptyBlock('Sin presupuesto definido.', '<a class="btn btn-soft btn-sm" href="#/finanzas/presupuesto">Crear</a>')}</div>`}
        </div>
      </section>`;

    const kpiCards = `
      <div class="kpi-row">
        <div class="kpi"><span class="kpi-icon ${ingresosView === 'Ingresos' ? 'tone-success' : 'tone-danger'}">${icon(ingresosView === 'Ingresos' ? 'arrow' : 'flag')}</span><div class="kpi-body"><span class="kpi-label">${ingresosView} del período</span><span class="kpi-value">${money(total)}</span><span class="kpi-note">${esc(monthLabel)}</span></div></div>
        <div class="kpi"><span class="kpi-icon ${dash.balance >= 0 ? 'tone-accent' : 'tone-danger'}">${icon('target')}</span><div class="kpi-body"><span class="kpi-label">Resultado del mes</span><span class="kpi-value">${money(dash.balance)}</span><span class="kpi-note">${dash.balance >= 0 ? 'superávit' : 'déficit'}</span></div></div>
        <div class="kpi"><span class="kpi-icon tone-primary">${icon('sparkles')}</span><div class="kpi-body"><span class="kpi-label">Presupuesto usado</span><span class="kpi-value">${money(used)}</span><span class="kpi-note">de ${money(planned)} (${budgetPct}%)</span></div></div>
      </div>`;

    const chips = `<div class="filterbar chips" id="flujo-chips">
      <button class="chip active" data-fin-cat="" type="button">Todos</button>
      ${catsOfType.map((c) => `<button class="chip" data-fin-cat="${esc(c.id)}" type="button">${esc(c.name)}</button>`).join('')}
    </div>`;

    const table = `
      <section class="card">
        <div class="card-body no-pad">
          <div style="padding:16px 18px 0"><div class="flujo-toolbar">
            <span class="flujo-total"><b>${esc(monthLabel)}</b> · <span id="flujo-count">${esc(txns.length)} movimientos</span> · total <b>${money(total)}</b></span>
          </div></div>
          ${chips}
          ${txns.length ? `<div class="table-wrap" style="padding:0 0 6px"><table class="table">
            <thead><tr><th>Fecha</th><th>Descripción</th><th>Categoría</th><th>Cuenta</th><th class="num">Monto</th><th></th></tr></thead>
            <tbody id="flujo-tbody">
              ${txns.map((t) => `
                <tr data-fin-row="${esc(t.category_id || '')}">
                  <td>${esc(fmtDate(t.date))}</td>
                  <td>${esc(t.description || '—')}</td>
                  <td>${esc((catById.get(t.category_id) || {}).name || t.category_id || '—')}</td>
                  <td>${esc(t.account_id.slice(0, 8))}</td>
                  <td class="num ${ingresosView === 'Ingresos' ? 'text-success' : 'text-danger'}">${ingresosView === 'Ingresos' ? '+' : '−'}${money(t.amount)}</td>
                  <td>${t.status === 'voided' ? badge('voided') : `<div class="item-actions"><button class="btn btn-ghost btn-xs" data-fin-tx-edit="${esc(t.id)}" title="Editar movimiento" aria-label="Editar movimiento">${icon('edit')}</button><button class="btn btn-ghost btn-xs btn-danger-soft" data-fin-void="${esc(t.id)}" title="Anular movimiento" aria-label="Anular movimiento">${icon('trash')}</button></div>`}</td>
                </tr>`).join('')}
            </tbody>
          </table></div>` : `<div class="card-body">${emptyBlock(
            `Sin ${ingresosView.toLowerCase()} en este período.`,
            '<button class="btn btn-soft btn-sm" id="fin-new2">Registrar movimiento</button>',
          )}</div>`}
        </div>
      </section>`;

    el.innerHTML = `
      <div class="page-head">
        <h1>${ingresosView}</h1>
        <p class="page-sub">${esc(monthLabel)} · ${esc(txns.length)} movimientos.</p>
        <div class="page-head-actions">
          ${monthPicker('mr-8')}
          <button class="btn btn-primary" id="fin-new">${icon('plus')} Registrar</button>
        </div>
      </div>
      ${kpiCards}
      <div class="split-60-40">
        <div class="split-main">${table}</div>
        <div class="split-side">
          ${metasHtml}
          ${upcomingHtml}
          ${budgetHtml}
        </div>
      </div>`;

    bindMonth(el, () => renderFlujo(el, household, type));
    bindNew(el, { household, accounts, categories, members, type, again: () => renderFlujo(el, household, type) });
    bindVoid(el, () => renderFlujo(el, household, type), { household, accounts, categories });

    const chipWrap = el.querySelector('#flujo-chips');
    if (chipWrap) {
      chipWrap.addEventListener('click', (e) => {
        const chip = e.target.closest('.chip[data-fin-cat]');
        if (!chip) return;
        chipWrap.querySelectorAll('.chip').forEach((c) => c.classList.toggle('active', c === chip));
        const cat = chip.dataset.finCat;
        const rows = el.querySelectorAll('#flujo-tbody tr');
        let shown = 0;
        rows.forEach((row) => {
          const visible = !cat || row.dataset.finRow === cat;
          row.hidden = !visible;
          if (visible) shown += 1;
        });
        const countEl = el.querySelector('#flujo-count');
        if (countEl) countEl.textContent = `${shown} movimientos`;
      });
    }
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Finanzas · ${ingresosView}</h1></div>${errorBlock(`No disponible: ${err.message}`)}`;
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

function bindVoid(el, again, ctx = {}) {
  el.addEventListener('click', async (e) => {
    const editBtn = e.target.closest('[data-fin-tx-edit]');
    if (editBtn) {
      const { household, accounts, categories } = ctx;
      const all = await listTransactions({ household_id: household.id, limit: 500 });
      const t = all.find((x) => x.id === editBtn.dataset.finTxEdit);
      if (!t) return;
      const form = await openForm({
        title: 'Editar movimiento',
        submitLabel: 'Guardar',
        fields: [
          { name: 'description', label: 'Descripción', value: t.description || '' },
          { name: 'amount', label: 'Monto', required: true, value: String(t.amount) },
          { name: 'date', label: 'Fecha', type: 'date', value: String(t.date || '').slice(0, 10) },
          {
            name: 'category_id',
            label: 'Categoría',
            type: 'select',
            value: t.category_id,
            options: [{ value: '', label: 'Sin categoría' }, ...(categories || []).map((c) => ({ value: c.id, label: c.name }))],
          },
          {
            name: 'account_id',
            label: 'Cuenta',
            type: 'select',
            value: t.account_id,
            options: (accounts || []).map((a) => ({ value: a.id, label: a.name })),
          },
        ],
      });
      if (!form) return;
      try {
        await updateTransaction(t.id, {
          description: form.description,
          amount: Number(form.amount) || 0,
          date: form.date || null,
          category_id: form.category_id || null,
          account_id: form.account_id || null,
        });
        invalidate(['fin']);
        toast('Movimiento actualizado', 'success');
        again();
      } catch (err) {
        toast(explainError(err), 'error');
      }
      return;
    }

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
                <div class="kpi no-icon"><div class="kpi-body"><span class="kpi-label">Calculado</span><span class="kpi-value">${money(a.balance_calculated)}</span></div></div>
                <div class="kpi no-icon"><div class="kpi-body"><span class="kpi-label">Reportado</span><span class="kpi-value">${money(a.balance_reported)}</span></div></div>
              </div>
              ${a.type === 'credit' ? `<div class="habit-goal">Límite: ${money(a.credit_limit)} · vence día ${a.due_day ?? '—'}</div>` : ''}
              <div class="habit-actions">
                <button class="btn btn-ghost btn-xs" data-fin-acc-toggle="${esc(a.id)}" data-status="${a.status === 'active' ? 'inactive' : 'active'}">${a.status === 'active' ? 'Desactivar' : 'Reactivar'}</button>
                <button class="btn btn-ghost btn-xs" data-fin-acc-balance="${esc(a.id)}" title="Ajustar el saldo que reporta el banco">${icon('edit')} Ajustar saldo</button>
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
    const v = await openForm({
      title: 'Ajustar saldo reportado',
      submitLabel: 'Guardar',
      hint: 'Es el saldo que dice el banco, no el que calcula FaroFlow con los movimientos.',
      fields: [{ name: 'balance_reported', label: 'Nuevo saldo', required: true }],
    });
    if (!v) return;
    try {
      // El campo se llama balance_reported: enviar balance_calculated lo hacia
      // descartar en silencio y el saldo nunca cambiaba.
      await patchAccount(btn.dataset.finAccBalance, { balance_reported: Number(v.balance_reported) || 0 });
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
        <div class="kpi"><span class="kpi-icon tone-danger">${icon('alert')}</span><div class="kpi-body"><span class="kpi-label">Saldo total</span><span class="kpi-value">${money(summary.total_current_balance)}</span><span class="kpi-note">original: ${money(summary.total_original_amount)}</span></div></div>
        <div class="kpi"><span class="kpi-icon tone-primary">${icon('folder')}</span><div class="kpi-body"><span class="kpi-label">Activas</span><span class="kpi-value">${esc((byStatus.active || {}).count || 0)}</span><span class="kpi-note">${money((byStatus.active || {}).current_balance || 0)}</span></div></div>
        <div class="kpi"><span class="kpi-icon tone-success">${icon('check')}</span><div class="kpi-body"><span class="kpi-label">Pagadas</span><span class="kpi-value">${esc((byStatus.paid_off || {}).count || 0)}</span></div></div>
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
                  <td><div class="item-actions">
                    <button class="btn btn-ghost btn-xs" data-fin-debt-edit="${esc(d.id)}" title="Editar deuda" aria-label="Editar ${esc(d.name)}">${icon('edit')}</button>
                  </div></td>
                </tr>`).join('')}
            </tbody>
          </table></div>` : `<div class="card-body">${emptyBlock('Sin deudas registradas.', '<button class="btn btn-soft btn-sm" id="fin-debt-new2">Registrar deuda</button>')}</div>`}
        </div>
      </section>`;
    bind(el, '#fin-debt-new, #fin-debt-new2', () => debtModal(el, household, accounts));
    bindDebts(el, household, accounts, () => renderDeudas(el, household));
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
        <div class="page-head-actions">${monthPicker()}${
          budget
            ? `<button class="btn btn-ghost btn-sm" data-fin-budget-status="${esc(budget.id)}" data-status="${budget.status === 'closed' ? 'active' : 'closed'}">${
                budget.status === 'closed' ? 'Reabrir presupuesto' : 'Cerrar presupuesto'
              }</button>`
            : ''
        }</div>
      </div>
      ${budget ? `
        <div class="kpi-row">
          <div class="kpi"><span class="kpi-icon tone-accent">${icon('target')}</span><div class="kpi-body"><span class="kpi-label">Planeado</span><span class="kpi-value">${money(totalPlanned)}</span></div></div>
          <div class="kpi"><span class="kpi-icon tone-danger">${icon('flag')}</span><div class="kpi-body"><span class="kpi-label">Real</span><span class="kpi-value">${money(totalActual)}</span></div></div>
          <div class="kpi"><span class="kpi-icon tone-primary">${icon('sparkles')}</span><div class="kpi-body"><span class="kpi-label">Avance</span><span class="kpi-value">${totalPlanned ? Math.round((totalActual / totalPlanned) * 100) : 0}%</span></div></div>
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
    if (budget) {
      el.addEventListener('click', async (e) => {
        const btn = e.target.closest('[data-fin-budget-status]');
        if (!btn) return;
        const next = btn.dataset.status;
        if (next === 'closed' && !window.confirm('Cerrar el presupuesto del mes?\n\nDeja de admitir nuevos montos planificados, pero conserva lo ya gastado.')) return;
        try {
          await updateBudget(btn.dataset.finBudgetStatus, { status: next });
          invalidate(['fin', 'budgets']);
          toast(next === 'closed' ? 'Presupuesto cerrado' : 'Presupuesto reabierto', 'success');
          renderPresupuesto(el, household);
        } catch (err) {
          toast(explainError(err), 'error');
        }
      });
    }
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
                <div class="kpi no-icon"><div class="kpi-body"><span class="kpi-label">Progreso</span><span class="kpi-value">${money(g.current_amount)}</span></div></div>
                <div class="kpi no-icon"><div class="kpi-body"><span class="kpi-label">Meta</span><span class="kpi-value">${money(g.target_amount)}</span></div></div>
              </div>
              <div class="bar-track" style="margin:6px 0"><div class="bar-fill ${pct >= 100 ? 'over' : ''}" style="width:${Math.min(100, pct)}%"></div></div>
              <div class="habit-goal">${pct}% alcanzado · aporte mensual ${money(g.monthly_contribution)}</div>
              <div class="modal-actions" style="margin-top:10px;justify-content:flex-start">
                ${g.status === 'active' ? `<button class="btn btn-primary btn-xs" data-fin-goal-contribute="${esc(g.id)}">${icon('plus')} Aportar</button>` : ''}
                <button class="btn btn-ghost btn-xs" data-fin-goal-edit="${esc(g.id)}" title="Editar meta" aria-label="Editar ${esc(g.name)}">${icon('edit')} Editar</button>
                <button class="btn btn-ghost btn-xs btn-danger-soft" data-fin-goal-delete="${esc(g.id)}" title="Eliminar meta" aria-label="Eliminar ${esc(g.name)}">${icon('trash')} Eliminar</button>
              </div>
            </div>
          </section>`;
        }).join('')}
      </div>` : `<section class="card"><div class="card-body">${emptyBlock('Sin metas de ahorro.', '<button class="btn btn-soft btn-sm" id="fin-goal-new2">Crear meta</button>')}</div></section>`}`;
    bind(el, '#fin-goal-new, #fin-goal-new2', () => goalModal(el, household, accounts));
    bindContribute(el, accounts, () => renderMetas(el, household));
    bindGoals(el, household, accounts, () => renderMetas(el, household));
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

/* ---------- Egresos ---------- */

const DONUT_COLORS = [
  '#00AAA5', '#007F83', '#3BC0BA', '#71C9C4', '#A8DCD8',
  '#F2A65A', '#F7C88F', '#E2F8F5', '#82C95B', '#5A8BB9',
];

export function donutChart(parts) {
  const total = parts.reduce((s, p) => s + (p.amount || 0), 0);
  if (!total || !parts.length) {
    return `<div class="donut empty">—</div><div class="item-sub">${esc('Sin datos para este período.')}</div>`;
  }
  let acc = 0;
  const stops = parts.map((p, i) => {
    const from = (acc / total) * 360;
    acc += p.amount || 0;
    const to = (acc / total) * 360;
    const color = p.color || DONUT_COLORS[i % DONUT_COLORS.length];
    return `${color} ${from.toFixed(1)}deg ${to.toFixed(1)}deg`;
  });
  const legend = parts.map((p, i) => {
    const color = p.color || DONUT_COLORS[i % DONUT_COLORS.length];
    const pct = Math.round(((p.amount || 0) / total) * 100);
    return `<div class="donut-row">
      <span class="swatch" style="background:${color}"></span>
      <span class="donut-name">${esc(p.label)}</span>
      <span class="donut-pct">${pct}%</span>
      <span class="donut-amt">${money(p.amount)}</span>
    </div>`;
  });
  return `<div class="donut-wrap">
    <div class="donut" style="background:conic-gradient(${stops.join(', ')})"><div class="donut-center"><b>${money(total)}</b></div></div>
    <div class="donut-legend">${legend.join('')}</div>
  </div>`;
}

async function renderEgresos(el, household) {
  if (!state.month) state.month = currentMonth();
  const { year, month } = monthParts();
  const monthLabel = `${MONTHS[month - 1]} ${String(year)}`;
  el.innerHTML = `
    <nav class="crumbs" aria-label="Ubicación">
      <a href="#/finanzas">Finanzas</a><span class="crumb-sep">/</span><span>Egresos</span>
    </nav>
    <h1>Egresos</h1>
    <div class="page-sub">${esc(monthLabel)}</div>
    <div class="page-head-actions">
      ${monthPicker('mr-8')}
      <button class="btn btn-primary" id="fin-new">${icon('plus')} Registrar</button>
    </div>
    ${skeleton(6)}`;
  try {
    const [accounts, categories, members, txns, up, dash, debts, available] = await Promise.all([
      listAccounts(),
      listCategoriesByHousehold(household.id),
      api(`/api/v1/finance/households/${encodeURIComponent(household.id)}/members`),
      listTransactions({ household_id: household.id, year, month, type: 'expense' }),
      upcomingPayments(household.id, 30),
      dashboard(household.id, year, month),
      listDebtsByHousehold(household.id),
      availableBalance(household.id).catch(() => null),
    ]);
    let bandeja = [];
    try {
      bandeja = (await api('/api/v1/bandeja')) || [];
    } catch (_err) {
      bandeja = [];
    }

    const catById = new Map((categories || []).map((c) => [c.id, c]));
    const catsOfType = (categories || []).filter((c) => c.kind === 'expense');
    const accById = new Map((accounts || []).map((a) => [a.id, a]));
    const accName = (id) => (accById.get(id || '') || {}).name || '—';
    const total = (txns || []).reduce((sum, t) => sum + t.amount, 0);
    const planned = (dash.budget || []).reduce((a, b) => a + (b.planned || 0), 0);
    const used = (dash.budget || []).reduce((a, b) => a + (b.actual || 0), 0);
    const budgetPct = planned ? Math.round((used / planned) * 100) : 0;
    const incomePct = dash.income ? Math.round((total / dash.income) * 100) : 0;

    const pendingCaptures = bandeja.filter(
      (b) => (b.destination_module === 'finance' || ['expense', 'income'].includes(b.kind)) && ['received', 'reviewing'].includes(b.status),
    ).length;

    const upcomingRows = [];
    for (const i of up.pending_installments || []) {
      upcomingRows.push({ due: i.due_date, name: `Cuota de deuda (${String(i.debt_id || '').slice(0, 6)})`, amount: i.total_amount, days: i.days_left });
    }
    for (const r of up.recurring_minimums || []) {
      upcomingRows.push({ due: r.due_date, name: `${r.debt_name} — pago mínimo`, amount: r.minimum_payment, days: null });
    }
    upcomingRows.sort((a, b) => (a.due < b.due ? -1 : 1));

    const activeDebts = (debts || []).filter((d) => d.status === 'active').sort((a, b) => (a.due_day || 31) - (b.due_day || 31));

    const chips = `<div class="filterbar chips" id="flujo-chips">
      <button class="chip active" data-fin-cat="" type="button">Todos</button>
      ${catsOfType.map((c) => `<button class="chip" data-fin-cat="${esc(c.id)}" type="button">${esc(c.name)}</button>`).join('')}
    </div>`;

    const accountFilter = (accounts || []).length > 1 ? `<select class="form-control flujo-search" id="flujo-account" aria-label="Filtrar por cuenta">
      <option value="">Todas las cuentas</option>
      ${accounts.map((a) => `<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('')}
    </select>` : '';

    /* Filtros con backing real: mes (en la cabecera), estado y búsqueda.
       No se ofrecen «tipo» ni «método»: en Egresos todas las filas son de tipo
       expense y el modelo de transacción no tiene método de pago, así que ambos
       controles serían decorativos. */
    const statusFilter = `<select class="form-control flujo-search" id="flujo-estado" aria-label="Filtrar por estado">
      <option value="">Todos los estados</option>
      <option value="posted">Vigentes</option>
      <option value="voided">Anuladas</option>
    </select>`;

    const movimientosHtml = `
      <div style="padding:16px 18px 0"><div class="flujo-toolbar">
        <span class="flujo-total"><b id="flujo-count">${esc(txns.length)} movimientos</b> · total <b>${money(total)}</b></span>
      </div></div>
      <div class="flujo-toolbar" style="padding:2px 18px 0">
        <span class="js-search">${icon('search')}</span>
        <input type="search" class="form-control flujo-search" id="flujo-q" placeholder="Buscar por descripción…" autocomplete="off" />
        ${statusFilter}
        ${accountFilter}
      </div>
      ${chips}
      ${txns.length ? `<div class="table-wrap" style="padding:0 0 6px"><table class="table">
        <thead><tr><th>Fecha</th><th>Descripción</th><th>Categoría</th><th>Cuenta</th><th class="num">Monto</th><th></th></tr></thead>
        <tbody id="flujo-tbody">
          ${txns.map((t) => `
            <tr data-fin-row="${esc(t.category_id || '')}" data-fin-acc="${esc(t.account_id || '')}" data-fin-status="${esc(t.status || 'posted')}" data-fin-search="${esc(String(t.description || '').toLowerCase())}">
              <td>${esc(fmtDate(t.date))}</td>
              <td>${esc(t.description || '—')}</td>
              <td>${esc((catById.get(t.category_id) || {}).name || t.category_id || '—')}</td>
              <td>${accName(t.account_id)}</td>
              <td class="num text-danger">−${money(t.amount)}</td>
              <td>${t.status === 'voided' ? badge('voided') : `<div class="item-actions"><button class="btn btn-ghost btn-xs" data-fin-tx-edit="${esc(t.id)}" title="Editar movimiento" aria-label="Editar movimiento">${icon('edit')}</button><button class="btn btn-ghost btn-xs btn-danger-soft" data-fin-void="${esc(t.id)}" title="Anular movimiento" aria-label="Anular movimiento">${icon('trash')}</button></div>`}</td>
            </tr>`).join('')}
        </tbody>
      </table></div>` : `<div class="card-body">${emptyBlock(
        'Sin egresos en este período.',
        '<button class="btn btn-soft btn-sm" id="fin-new2">Registrar movimiento</button>',
      )}</div>`}`;

    const categorias = [...(dash.expense_categories || [])].sort((a, b) => b.amount - a.amount);
    const categoriasHtml = categorias.length
      ? `<div style="padding:18px">${donutChart(categorias.map((c) => ({ label: c.name, amount: c.amount })))}</div>
        <div class="bar-list" style="padding:0 18px 14px">
          ${categorias.map((c) => `
            <div class="bar-row">
              <span class="bar-name">${esc(c.name)}</span>
              <div class="bar-track"><div class="bar-fill" style="width:${Math.round((c.amount / (dash.expenses || 1)) * 100)}%"></div></div>
              <span class="bar-amt">${money(c.amount)}</span>
            </div>`).join('')}
        </div>`
      : emptyBlock('Sin egresos categorizados este mes.');

    const recurrentesHtml = `
      <div class="card-body no-pad">
        ${activeDebts.length ? `<div class="list" style="padding:0 18px">
          ${activeDebts.map((d) => `
            <div class="item">
              <div class="item-main">
                <div class="item-title">${esc(d.name)}</div>
                <div class="item-sub">${esc(d.type)} · pago mínimo ${money(d.minimum_payment)} · día ${esc(d.due_day || 1)}</div>
              </div>
              <div class="item-side">${money(d.current_balance)}</div>
            </div>`).join('')}
        </div>` : emptyBlock('Sin deudas activas recurrentes.')}
        ${upcomingRows.length ? `<div class="tab-head" style="margin:6px 18px 0">
          <button class="btn btn-ghost btn-sm" id="fin-egresos-upcoming">${icon('clock')} Próximos pagos (${esc(upcomingRows.length)})</button>
        </div>` : ''}
      </div>`;

    /* «Por categoría» ya no es una pestaña: la distribución vive arriba, en el
       bloque de la derecha, para no mostrar el mismo donut dos veces. */
    const tabs = [['movimientos', 'Movimientos'], ['recurrentes', 'Recurrentes']];
    let currentTab = 'movimientos';

    const renderTabBody = () => {
      const body = el.querySelector('#egresos-tab-body');
      if (!body) return;
      if (currentTab === 'movimientos') body.innerHTML = `<section class="card"><div class="card-body no-pad">${movimientosHtml}</div></section>`;
      else body.innerHTML = `<section class="card"><div class="card-body">${recurrentesHtml}</div></section>`;
    };

    const upcomingSide = `
      <section class="card">
        <div class="card-head"><h2>${icon('clock')} Próximos pagos</h2><a class="card-action" href="#/finanzas/deudas">Deudas</a></div>
        <div class="card-body no-pad">
          ${upcomingRows.length ? `<div class="list" style="padding:0 18px">
            ${upcomingRows.slice(0, 6).map((r) => `
              <div class="item">
                <div class="item-main"><div class="item-title">${esc(r.name)}</div>
                <div class="item-sub">vence ${esc(fmtDate(r.due))}${r.days !== null ? ` · en ${esc(r.days)} días` : ''}</div></div>
                <div class="item-side">${money(r.amount)}</div>
              </div>`).join('')}
          </div>` : `<div class="card-body">${emptyBlock('Nada pendiente en 30 días.')}</div>`}
        </div>
      </section>`;

    const capturesSide = pendingCaptures
      ? `<section class="card tone-soft"><div class="card-body">
          <div class="advice">
            ${icon('alert')}
            <div><b>Tienes ${esc(pendingCaptures)} ${pendingCaptures === 1 ? 'captura pendiente' : 'capturas pendientes'} por clasificar</b>
            <div class="item-sub">Revisa en la bandeja qué mueven tus finanzas.</div></div>
            <a class="btn btn-primary btn-sm" href="#/bandeja">Ir a la bandeja</a>
          </div>
        </div></section>`
      : '';

    /* Política de gastos = el presupuesto real del mes (planned vs. actual por
       categoría). No existe una entidad "política de gastos" en el modelo, así
       que la tarjeta muestra los datos que sí existen en vez de inventar reglas. */
    const budgetRows = (dash.budget || []).slice().sort((a, b) => (b.planned || 0) - (a.planned || 0));
    const policySide = `
      <section class="card">
        <div class="card-head">
          <h2>${icon('target')} Política de gastos</h2>
          <a class="card-action" href="#/finanzas/presupuesto">Presupuesto</a>
        </div>
        <div class="card-body no-pad">
          ${budgetRows.length ? `
            <div class="kpi-row compact" style="margin:0; padding:16px 18px 4px">
              ${kpiTile({ icon: 'target', tone: 'primary', label: 'Planificado', value: money(planned), note: `${budgetRows.length} categorías` })}
              ${kpiTile({ icon: 'flag', tone: planned && used > planned ? 'danger' : 'accent', label: 'Gastado', value: money(used), note: `${budgetPct}% de lo planificado` })}
            </div>
            <div class="list" style="padding:0 18px 6px">
              ${budgetRows.map((b) => {
                const pct = b.planned ? Math.round((b.actual / b.planned) * 100) : 0;
                const over = pct > 100;
                return `<div class="item">
                  <div class="item-main">
                    <div class="item-title">${esc(b.category_name || 'Sin categoría')}</div>
                    <div class="item-sub">${money(b.actual)} de ${money(b.planned)}</div>
                  </div>
                  <div class="item-side"><span class="${over ? 'text-danger' : ''}">${pct}%</span></div>
                </div>`;
              }).join('')}
            </div>`
          : `<div class="card-body">${emptyBlock('Sin presupuesto definido para este mes.', `<a class="btn btn-soft btn-sm" href="#/finanzas/presupuesto">Definir presupuesto</a>`)}</div>`}
        </div>
      </section>`;

    el.innerHTML = `
      <nav class="crumbs" aria-label="Ubicación">
        <a href="#/finanzas">Finanzas</a><span class="crumb-sep">/</span><span>Egresos</span>
      </nav>
      <div class="detail-head">
        <div>
          <h1>Egresos</h1>
          <div class="page-sub">${esc(monthLabel)} · ${esc(txns.length)} movimientos.</div>
        </div>
        <div class="page-head-actions">
          ${monthPicker('mr-8')}
          <button class="btn btn-primary" id="fin-new">${icon('plus')} Registrar</button>
        </div>
      </div>
      ${disponibleCard({ available })}
      <div class="split-60-40">
        <div class="split-main">
          <section class="card">
            <div class="card-head"><h2>${icon('sparkles')} Este mes</h2></div>
            <div class="card-body">
              <div class="stack">
                ${kpiTile({ icon: 'flag', tone: 'danger', label: 'Total de egresos', value: money(total), note: `${incomePct}% del ingreso del mes` })}
                ${kpiTile({ icon: 'target', tone: dash.balance >= 0 ? 'accent' : 'danger', label: 'Resultado del mes', value: money(dash.balance), note: dash.balance >= 0 ? 'superávit' : 'déficit' })}
                ${kpiTile({ icon: 'clock', tone: 'warm', label: 'Movimientos', value: esc(txns.length), note: `${money(total)} en total` })}
              </div>
            </div>
          </section>
        </div>
        <div class="split-side">
          <section class="card">
            <div class="card-head"><h2>${icon('folder')} Distribución</h2></div>
            <div class="card-body no-pad">${categoriasHtml}</div>
          </section>
        </div>
      </div>
      ${policySide}
      <div class="split-72-28">
        <div class="split-main">
          <div class="tabs" role="tablist" aria-label="Secciones de egresos">
            ${tabs.map(([key, label]) => `<button class="tab ${key === 'movimientos' ? 'active' : ''}" data-eg-tab="${key}" role="tab" aria-selected="${key === 'movimientos' ? 'true' : 'false'}">${esc(label)}</button>`).join('')}
          </div>
          <div id="egresos-tab-body"></div>
        </div>
        <div class="split-side">
          ${upcomingSide}
          ${capturesSide}
        </div>
      </div>`;
    renderTabBody();

    bindMonth(el, () => renderEgresos(el, household));
    bindNew(el, { household, accounts, categories, members, type: 'expense', again: () => renderEgresos(el, household) });
    bindVoid(el, () => renderEgresos(el, household), { household, accounts, categories });

    el.querySelector('.tabs').addEventListener('click', (e) => {
      const btn = e.target.closest('[data-eg-tab]');
      if (!btn) return;
      currentTab = btn.dataset.egTab;
      el.querySelectorAll('.tab').forEach((t) => {
        t.classList.toggle('active', t === btn);
        t.setAttribute('aria-selected', t === btn ? 'true' : 'false');
      });
      renderTabBody();
    });

    const chipWrap = el.querySelector('#flujo-chips');
    const qInput = el.querySelector('#flujo-q');
    const accSelect = el.querySelector('#flujo-account');
    const statusSelect = el.querySelector('#flujo-estado');
    const applyFilters = () => {
      const cat = (chipWrap?.querySelector('.chip.active[data-fin-cat]') || {}).dataset?.finCat || '';
      const acc = accSelect?.value || '';
      const status = statusSelect?.value || '';
      const q = (qInput?.value || '').trim().toLowerCase();
      const rows = el.querySelectorAll('#flujo-tbody tr');
      let shown = 0;
      rows.forEach((row) => {
        const visible =
          (!cat || row.dataset.finRow === cat) &&
          (!acc || row.dataset.finAcc === acc) &&
          (!status || row.dataset.finStatus === status) &&
          (!q || (row.dataset.finSearch || '').includes(q));
        row.hidden = !visible;
        if (visible) shown += 1;
      });
      const countEl = el.querySelector('#flujo-count');
      if (countEl) countEl.textContent = `${shown} movimientos`;
    };
    if (chipWrap) {
      chipWrap.addEventListener('click', (e) => {
        const chip = e.target.closest('.chip[data-fin-cat]');
        if (!chip) return;
        chipWrap.querySelectorAll('.chip').forEach((c) => c.classList.toggle('active', c === chip));
        applyFilters();
      });
    }
    if (qInput) qInput.addEventListener('input', applyFilters);
    if (accSelect) accSelect.addEventListener('change', applyFilters);
    if (statusSelect) statusSelect.addEventListener('change', applyFilters);

    const upBtn = el.querySelector('#fin-egresos-upcoming');
    if (upBtn) {
      upBtn.addEventListener('click', () => {
        const side = el.querySelector('.split-side');
        if (side) side.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  } catch (err) {
    el.innerHTML = `<nav class="crumbs" aria-label="Ubicación"><a href="#/finanzas">Finanzas</a><span class="crumb-sep">/</span><span>Egresos</span></nav><h1>Egresos</h1>${errorBlock(`No disponible: ${err.message}`)}`;
  }
}
/* ---------- Editar y eliminar metas ---------- */

function bindGoals(el, household, accounts, again) {
  el.addEventListener('click', async (e) => {
    const editBtn = e.target.closest('[data-fin-goal-edit]');
    if (editBtn) {
      const goals = await listGoalsByHousehold(household.id);
      const g = goals.find((x) => x.id === editBtn.dataset.finGoalEdit);
      if (!g) return;
      const form = await openForm({
        title: 'Editar meta',
        submitLabel: 'Guardar',
        fields: [
          { name: 'name', label: 'Nombre', required: true, value: g.name },
          {
            name: 'category',
            label: 'Categoría',
            type: 'select',
            value: g.category,
            options: [['fondo', 'Fondo de emergencia'], ['security', 'Seguridad'], ['travel', 'Viaje'], ['purchase', 'Compra'], ['debt', 'Pago de deuda'], ['other', 'Otro']].map(([v, l]) => ({ value: v, label: l })),
          },
          { name: 'target_amount', label: 'Monto meta', required: true, value: String(g.target_amount) },
          { name: 'current_amount', label: 'Ya ahorrado', value: String(g.current_amount) },
          { name: 'monthly_contribution', label: 'Aporte mensual', value: String(g.monthly_contribution || 0) },
          { name: 'target_date', label: 'Fecha meta', type: 'date', value: String(g.target_date || '').slice(0, 10) },
          {
            name: 'status',
            label: 'Estado',
            type: 'select',
            value: g.status,
            options: [['active', 'Activa'], ['achieved', 'Alcanzada'], ['archived', 'Archivada']].map(([v, l]) => ({ value: v, label: l })),
          },
        ],
      });
      if (!form) return;
      try {
        await updateGoal(g.id, {
          name: form.name,
          category: form.category,
          target_amount: Number(form.target_amount) || 0,
          current_amount: Number(form.current_amount) || 0,
          monthly_contribution: Number(form.monthly_contribution) || 0,
          target_date: form.target_date || null,
          status: form.status,
        });
        invalidate(['fin']);
        toast('Meta actualizada', 'success');
        again();
      } catch (err) {
        toast(explainError(err), 'error');
      }
      return;
    }

    const delBtn = e.target.closest('[data-fin-goal-delete]');
    if (delBtn) {
      const goals = await listGoalsByHousehold(household.id);
      const g = goals.find((x) => x.id === delBtn.dataset.finGoalDelete);
      if (!g) return;
      const saved = g.current_amount || 0;
      if (!window.confirm(`Eliminar la meta «${g.name}»?\n\nSe borra su historial de aportes: ${money(saved)} ahorrados.`)) return;
      try {
        await deleteGoal(g.id);
        invalidate(['fin']);
        toast('Meta eliminada', 'success');
        again();
      } catch (err) {
        toast(explainError(err), 'error');
      }
    }
  });
}

/* ---------- Editar deudas ---------- */

function bindDebts(el, household, accounts, again) {
  el.addEventListener('click', async (e) => {
    const editBtn = e.target.closest('[data-fin-debt-edit]');
    if (!editBtn) return;
    const debts = await listDebtsByHousehold(household.id);
    const d = debts.find((x) => x.id === editBtn.dataset.finDebtEdit);
    if (!d) return;
    const form = await openForm({
      title: 'Editar deuda',
      submitLabel: 'Guardar',
      hint: 'Una deuda no se borra: se marca como pagada o se cierra.',
      fields: [
        { name: 'name', label: 'Nombre', required: true, value: d.name },
        {
          name: 'type',
          label: 'Tipo',
          type: 'select',
          value: d.type,
          options: [['credit_card', 'Tarjeta de crédito'], ['loan', 'Préstamo'], ['auto', 'Auto'], ['mortgage', 'Hipoteca'], ['line', 'Línea de crédito'], ['other', 'Otra']].map(([v, l]) => ({ value: v, label: l })),
        },
        {
          name: 'account_id',
          label: 'Cuenta asociada',
          type: 'select',
          value: d.account_id,
          options: [{ value: '', label: 'Ninguna' }, ...(accounts || []).map((a) => ({ value: a.id, label: a.name }))],
        },
        { name: 'current_balance', label: 'Saldo actual', value: String(d.current_balance) },
        { name: 'minimum_payment', label: 'Pago mínimo', value: String(d.minimum_payment) },
        { name: 'interest_rate', label: 'Tasa % mensual', value: String(d.interest_rate) },
        { name: 'due_day', label: 'Día de pago (1-31)', value: String(d.due_day) },
        {
          name: 'status',
          label: 'Estado',
          type: 'select',
          value: d.status,
          options: [['active', 'Activa'], ['paid_off', 'Pagada'], ['closed', 'Cerrada']].map(([v, l]) => ({ value: v, label: l })),
        },
      ],
    });
    if (!form) return;
    try {
      await updateDebt(d.id, {
        name: form.name,
        type: form.type,
        account_id: form.account_id || null,
        current_balance: Number(form.current_balance) || 0,
        minimum_payment: Number(form.minimum_payment) || 0,
        interest_rate: Number(form.interest_rate) || 0,
        due_day: Number(form.due_day) || 1,
        status: form.status,
      });
      invalidate(['fin']);
      toast('Deuda actualizada', 'success');
      again();
    } catch (err) {
      toast(explainError(err), 'error');
    }
  });
}
