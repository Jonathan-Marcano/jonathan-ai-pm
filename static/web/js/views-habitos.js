'use strict';

import {
  listHabits,
  createHabit,
  updateHabit,
  deleteHabit,
  habitSeries,
  markHabit,
  unmarkHabit,
} from './api.js';
import {
  esc,
  todayISO,
  addDaysISO,
  icon,
  badge,
  toast,
  skeleton,
  emptyBlock,
  errorBlock,
  genEntityId,
} from './ui.js';

const DAY_LETTERS = ['L', 'M', 'X', 'J', 'V', 'S', 'D']; // índice = isoWeekday - 1
const WEEKDAY_LETTERS = ['D', 'L', 'M', 'X', 'J', 'V', 'S']; // índice = Date.getDay() (0 = domingo)

export function isoWeekday(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return ((d.getDay() + 6) % 7) + 1;
}

export function last7() {
  const days = [];
  for (let i = 6; i >= 0; i--) days.push(addDaysISO(todayISO(), -i));
  return days;
}

function isScheduled(habit, iso) {
  const frequency = habit.frequency || 'daily';
  if (frequency === 'daily') return true;
  if (frequency === 'weekdays') return isoWeekday(iso) <= 5;
  if (frequency === 'specific_days') {
    return (habit.specific_days || []).includes(isoWeekday(iso));
  }
  return true; // weekly: puede marcarse cualquier día de la semana
}

function quantityOn(completions, iso) {
  return (completions || [])
    .filter((c) => c.local_date === iso)
    .reduce((sum, c) => sum + (Number(c.quantity) || 0), 0);
}

function isMet(habit, iso, completions, qtyOverride) {
  const qty = qtyOverride !== undefined ? qtyOverride : quantityOn(completions, iso);
  const target = Number(habit.target_quantity) || 1;
  return qty >= target;
}

function weeklyMet(habit, iso, series) {
  const days = last7();
  const total = days
    .map((d) => quantityOn(series.completions, d))
    .reduce((a, b) => a + b, 0);
  return total >= (Number(habit.weekly_target) || 1);
}

function seriesForDay(habit, iso, series) {
  const qty = quantityOn(series.completions, iso);
  const scheduled = isScheduled(habit, iso);
  let done;
  if (habit.frequency === 'weekly') {
    done = weeklyMet(habit, iso, series);
  } else {
    done = scheduled && isMet(habit, iso, series, qty);
  }
  const partial = scheduled && habit.goal_type === 'quantity' && qty > 0 && !done;
  return { qty, done, partial, scheduled };
}

function dayCell(habit, iso, series) {
  const s = seriesForDay(habit, iso, series);
  const isToday = iso === (series.today || todayISO());
  const cls = [
    'day-cell',
    isToday ? 'today' : '',
    s.done ? 'done' : '',
    s.partial ? 'partial' : '',
    s.scheduled ? 'due' : '',
  ]
    .filter(Boolean)
    .join(' ');
  const content = s.done
    ? icon('check')
    : s.partial
      ? `<span style="font-size:10px">${esc(s.qty)}</span>`
      : WEEKDAY_LETTERS[new Date(`${iso}T12:00:00`).getDay()];
  return `<button class="${cls}" data-day="${esc(iso)}" data-habit="${esc(habit.id)}" title="${esc(iso)}${s.scheduled ? '' : ' (no corresponde)'}">${content}</button>`;
}

function weekStrip(habit, series) {
  return `<div class="habit-row">
    <span class="item-title">${esc(habit.name)}</span>
    ${last7().map((iso) => dayCell(habit, iso, series)).join('')}
    <span class="streak-badge">${icon('sparkles')} ${esc(series.current_streak)}</span>
  </div>`;
}

function goalLabel(habit) {
  const g = habit.goal_type || 'binary';
  const f = habit.frequency || 'daily';
  const parts = [g === 'binary' ? 'Binario' : `Cantidad (${habit.target_quantity ?? 1} ${habit.unit || ''})`.trim()];
  parts.push(
    f === 'daily' ? 'diario'
      : f === 'weekdays' ? 'días de semana'
        : f === 'weekly' ? `semanal x${habit.weekly_target ?? 1}`
          : 'días específicos',
  );
  return parts.join(' · ');
}

/* ---------- Modal de hábito ---------- */

function habitModal(existing) {
  return new Promise((resolve) => {
    const h = existing || {};
    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    const daysOptions = [1, 2, 3, 4, 5, 6, 7]
      .map(
        (d) => `<label class="day-check"><input type="checkbox" name="hbt-day" value="${d}" ${(h.specific_days || []).includes(d) ? 'checked' : ''}/>${DAY_LETTERS[d - 1]}</label>`,
      )
      .join('');
    overlay.innerHTML = `
      <div class="modal modal-md" role="dialog" aria-modal="true" aria-labelledby="hbt-title">
        <header class="modal-head"><h3 id="hbt-title">${existing ? 'Editar hábito' : 'Nuevo hábito'}</h3>
          <button class="icon-btn" type="button" data-hbt="cancel" aria-label="Cerrar">${icon('x')}</button></header>
        <div class="modal-body">
          <label class="modal-label" for="hbt-name">Nombre</label>
          <input id="hbt-name" class="form-control" required maxlength="200" value="${esc(h.name || '')}" placeholder="Ejemplo: Beber agua" />
          <label class="modal-label" for="hbt-desc">Descripción</label>
          <textarea id="hbt-desc" class="capture-textarea" rows="2" maxlength="500" placeholder="Opcional">${esc(h.description || '')}</textarea>
          <div class="field-group">
            <div>
              <label class="modal-label" for="hbt-goal">Tipo de objetivo</label>
              <select id="hbt-goal" class="form-control">
                <option value="binary" ${h.goal_type === 'quantity' ? '' : 'selected'}>Binario (cumplido / no)</option>
                <option value="quantity" ${h.goal_type === 'quantity' ? 'selected' : ''}>Cantidad</option>
              </select>
            </div>
            <div data-hbt-group="quantity" style="${h.goal_type === 'quantity' ? '' : 'display:none'}">
              <label class="modal-label" for="hbt-target">Cantidad objetivo</label>
              <input id="hbt-target" class="form-control" type="number" min="1" value="${esc(h.target_quantity || 1)}" />
            </div>
            <div data-hbt-group="quantity" style="${h.goal_type === 'quantity' ? '' : 'display:none'}">
              <label class="modal-label" for="hbt-unit">Unidad</label>
              <input id="hbt-unit" class="form-control" maxlength="40" value="${esc(h.unit || '')}" placeholder="vasos, km…" />
            </div>
          </div>
          <label class="modal-label" for="hbt-freq">Frecuencia</label>
          <select id="hbt-freq" class="form-control">
            <option value="daily" ${(h.frequency || 'daily') === 'daily' ? 'selected' : ''}>Cada día</option>
            <option value="weekdays" ${h.frequency === 'weekdays' ? 'selected' : ''}>Días de semana</option>
            <option value="weekly" ${h.frequency === 'weekly' ? 'selected' : ''}>Semanal</option>
            <option value="specific_days" ${h.frequency === 'specific_days' ? 'selected' : ''}>Días específicos</option>
          </select>
          <div data-hbt-group="weekly" style="display:none">
            <label class="modal-label" for="hbt-weekly">Objetivo semanal</label>
            <input id="hbt-weekly" class="form-control" type="number" min="1" value="${esc(h.weekly_target || 1)}" />
          </div>
          <div data-hbt-group="specific_days" style="display:none">
            <label class="modal-label">Días de la semana</label>
            <div class="day-checks">${daysOptions}</div>
          </div>
          <div class="modal-actions">
            <button class="btn btn-ghost" type="button" data-hbt="cancel">Cancelar</button>
            <button class="btn btn-primary" type="button" data-hbt="ok">${existing ? 'Guardar' : 'Crear hábito'}</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const goal = overlay.querySelector('#hbt-goal');
    const freq = overlay.querySelector('#hbt-freq');
    const sync = () => {
      const isQ = goal.value === 'quantity';
      overlay.querySelectorAll('[data-hbt-group="quantity"]').forEach((n) => { n.style.display = isQ ? '' : 'none'; });
      const isW = freq.value === 'weekly';
      const isD = freq.value === 'specific_days';
      overlay.querySelector('[data-hbt-group="weekly"]').style.display = isW ? '' : 'none';
      overlay.querySelector('[data-hbt-group="specific_days"]').style.display = isD ? '' : 'none';
    };
    goal.addEventListener('change', sync);
    freq.addEventListener('change', sync);
    const finish = (v) => {
      overlay.remove();
      resolve(v);
    };
    overlay.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-hbt]');
      if (btn) {
        if (btn.dataset.hbt === 'cancel') return finish(null);
        const name = overlay.querySelector('#hbt-name').value.trim();
        if (!name) {
          toast('El nombre es obligatorio', 'error');
          return;
        }
        const payload = {
          name,
          description: overlay.querySelector('#hbt-desc').value.trim() || undefined,
          goal_type: goal.value,
          frequency: freq.value,
          target_quantity: goal.value === 'quantity' ? Number(overlay.querySelector('#hbt-target').value) || 1 : 1,
          unit: goal.value === 'quantity' ? overlay.querySelector('#hbt-unit').value.trim() || undefined : undefined,
          weekly_target: freq.value === 'weekly' ? Number(overlay.querySelector('#hbt-weekly').value) || 1 : undefined,
          specific_days: freq.value === 'specific_days'
            ? [...overlay.querySelectorAll('input[name="hbt-day"]:checked')].map((c) => Number(c.value))
            : undefined,
        };
        if (freq.value === 'specific_days' && !payload.specific_days.length) {
          toast('Elige al menos un día', 'error');
          return;
        }
        finish(payload);
      }
      if (event.target === overlay) finish(null);
    });
    overlay.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') finish(null);
    });
    overlay.querySelector('#hbt-name').focus();
  });
}

/* ---------- Vista principal ---------- */

export async function renderHabitos(el) {
  el.innerHTML = `
    <div class="page-head">
      <h1>Hábitos</h1>
      <p class="page-sub">Objetivos diarios y semanales con seguimiento de racha.</p>
      <div class="page-head-actions">
        <button class="btn btn-primary" id="hbt-new">${icon('plus')} Nuevo hábito</button>
      </div>
    </div>
    ${skeleton(5)}`;
  try {
    const habits = await listHabits();
    if (!habits || !habits.length) {
      el.innerHTML = `
        <div class="page-head">
          <h1>Hábitos</h1>
          <p class="page-sub">Objetivos diarios y semanales con seguimiento de racha.</p>
        </div>
        <section class="card"><div class="card-body">${emptyBlock(
          'Aún no tienes hábitos. Crea el primero.',
          '<button class="btn btn-primary btn-sm" id="hbt-new">Nuevo hábito</button>',
        )}</div></section>`;
    } else {
      const series = await Promise.all(habits.map((h) => habitSeries(h.id)));
      el.innerHTML = `
        <div class="page-head">
          <h1>Hábitos</h1>
          <p class="page-sub">Objetivos diarios y semanales con seguimiento de racha.</p>
          <div class="page-head-actions">
            <button class="btn btn-primary" id="hbt-new">${icon('plus')} Nuevo hábito</button>
          </div>
        </div>
        <div class="page-grid">
          ${habits
            .map((h, i) => {
              const s = series[i];
              return `
              <section class="card">
                <div class="card-body">
                  <div class="habit-card">
                    <div class="habit-head">
                      <div>
                        <div class="habit-name">${esc(h.name)}</div>
                        <div class="habit-goal">${esc(goalLabel(h))}</div>
                      </div>
                      <div class="item-side">${badge(h.status)}</div>
                    </div>
                    ${weekStrip(h, s)}
                    <div class="habit-meta">
                      <span class="streak-badge">${icon('sparkles')} Racha: ${esc(s.current_streak)}</span>
                      <span class="streak-badge" style="background:var(--ff-accent-100);color:var(--ff-accent-700)">${Math.round((s.completion_rate_14d || 0) * 100)}% últ. 14 días</span>
                    </div>
                    <div class="habit-actions">
                      <a class="btn btn-soft btn-xs" href="#/habitos/${esc(h.id)}">${icon('arrow')} Detalle</a>
                      <button class="btn btn-ghost btn-xs" data-hbt-edit="${esc(h.id)}">${icon('edit')} Editar</button>
                      ${h.status === 'active' ? `<button class="btn btn-warm-soft btn-xs" data-hbt-status="${esc(h.id)}" data-status="paused">Pausar</button>` : ''}
                      ${h.status === 'paused' ? `<button class="btn btn-soft btn-xs" data-hbt-status="${esc(h.id)}" data-status="active">Reanudar</button>` : ''}
                      <button class="btn btn-ghost btn-xs" data-hbt-delete="${esc(h.id)}">${icon('trash')} Archivar</button>
                    </div>
                  </div>
                </div>
              </section>`;
            })
            .join('')}
        </div>
        <p class="page-sub" style="margin-top:16px">Haz clic en cualquier día de la franja para marcarlo o desmarcarlo.</p>`;
    }

    bind(el);
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Hábitos</h1></div>${errorBlock(`No disponible: ${esc(err.message)}`)}`;
  }
}

async function bind(el) {
  if (el.dataset.bound) return;
  el.dataset.bound = '1';
  el.addEventListener('click', async (event) => {
    const newBtn = event.target.closest('#hbt-new');
    if (newBtn) {
      const payload = await habitModal(null);
      if (!payload) return;
      try {
        await createHabit({ ...payload, id: genEntityId('hbt'), status: 'active', timezone: 'America/Santiago' });
        toast('Hábito creado', 'success');
      } catch (err) {
        toast(`No se pudo crear: ${err.message}`, 'error');
      }
      setTimeout(() => renderHabitos(el), 250);
      return;
    }

    const editBtn = event.target.closest('[data-hbt-edit]');
    if (editBtn) {
      try {
        const all = await listHabits();
        const habit = all.find((h) => h.id === editBtn.dataset.hbtEdit);
        if (!habit) return;
        const payload = await habitModal(habit);
        if (!payload) return;
        await updateHabit(habit.id, payload);
        toast('Hábito actualizado', 'success');
      } catch (err) {
        toast(`No se pudo actualizar: ${err.message}`, 'error');
      }
      setTimeout(() => renderHabitos(el), 250);
      return;
    }

    const statusBtn = event.target.closest('[data-hbt-status]');
    if (statusBtn) {
      try {
        await updateHabit(statusBtn.dataset.hbtStatus, { status: statusBtn.dataset.status });
        toast(statusBtn.dataset.status === 'active' ? 'Hábito reanudado' : 'Hábito en pausa', 'success');
      } catch (err) {
        toast(`No se pudo actualizar: ${err.message}`, 'error');
      }
      setTimeout(() => renderHabitos(el), 250);
      return;
    }

    const deleteBtn = event.target.closest('[data-hbt-delete]');
    if (deleteBtn) {
      if (!window.confirm('Archivar este hábito (conserva su historial)?')) return;
      try {
        await updateHabit(deleteBtn.dataset.hbtDelete, { status: 'archived' });
        toast('Hábito archivado', 'success');
      } catch (err) {
        toast(`No se pudo archivar: ${err.message}`, 'error');
      }
      setTimeout(() => renderHabitos(el), 250);
      return;
    }

    const day = event.target.closest('[data-day]');
    if (day) {
      const habitId = day.dataset.habit;
      const iso = day.dataset.day;
      if (iso > todayISO()) return;
      try {
        const series = await habitSeries(habitId);
        const habit = series.habit;
        const state = seriesForDay(habit, iso, series);
        if (state.done || (habit.frequency === 'weekly' && weeklyMet(habit, iso, series))) {
          await unmarkHabit(habitId, { local_date: iso });
          toast('Cumplimiento desmarcado', 'success');
        } else {
          await markHabit(habitId, { local_date: iso, quantity: habit.goal_type === 'quantity' ? habit.target_quantity : 1 });
          toast('Cumplimiento marcado', 'success');
        }
      } catch (err) {
        toast(`No se pudo marcar: ${err.message}`, 'error');
      }
      const path = window.location.hash.startsWith('#/habitos/semana') ? renderSemana : renderHabitos;
      setTimeout(() => path(el), 250);
      return;
    }
  });
}

/* ---------- Vista semanal ---------- */

export async function renderSemana(el) {
  el.innerHTML = `
    <div class="page-head">
      <h1>Vista semanal</h1>
      <p class="page-sub">Últimos 7 días. Toca una celda para marcar o desmarcar.</p>
    </div>
    ${skeleton(5)}`;
  try {
    const habits = await listHabits();
    const active = (habits || []).filter((h) => h.status !== 'archived');
    if (!active.length) {
      el.innerHTML = `
        <div class="page-head"><h1>Vista semanal</h1></div>
        <section class="card"><div class="card-body">${emptyBlock('Sin hábitos activos.', '<a class="btn btn-soft btn-sm" href="#/habitos">Crear hábito</a>')}</div></section>`;
      bind(el);
      return;
    }
    const series = await Promise.all(active.map((h) => habitSeries(h.id)));
    const days = last7();
    const head = `
      <div class="habit-row week-head">
        <span class="week-label">Hábito</span>
        ${days.map((d) => `<span class="week-label" style="text-align:center">${WEEKDAY_LETTERS[new Date(`${d}T12:00:00`).getDay()]} ${d.slice(8)}</span>`).join('')}
        <span class="week-label">Racha</span>
      </div>`;
    el.innerHTML = `
      <div class="page-head">
        <h1>Vista semanal</h1>
        <p class="page-sub">Últimos 7 días. Toca una celda para marcar o desmarcar.</p>
        <div class="page-head-actions"><a class="btn btn-ghost btn-sm" href="#/habitos">${icon('arrow')} Todos los hábitos</a></div>
      </div>
      <section class="card">
        <div class="card-body">
          <div style="overflow-x:auto">${head}${active.map((h, i) => weekStrip(h, series[i])).join('')}</div>
        </div>
      </section>`;
    bind(el);
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Vista semanal</h1></div>${errorBlock(`No disponible: ${esc(err.message)}`)}`;
  }
}

/* ---------- Detalle de un hábito ---------- */

export async function renderHabitoDetalle(el, habitId) {
  el.innerHTML = `<div class="page-head"><a class="back-link" href="#/habitos">${icon('arrow')} Hábitos</a></div>${skeleton(4)}`;
  try {
    const series = await habitSeries(habitId);
    const habit = series.habit;
    const completions = series.completions || [];

    el.innerHTML = `
      <a class="back-link" href="#/habitos">${icon('arrow')} Hábitos</a>
      <div class="page-head">
        <div class="page-greeting"><h1>${esc(habit.name)}</h1> ${badge(habit.status)}</div>
        <p class="page-sub">${esc(goalLabel(habit))}${habit.description ? ` · ${esc(habit.description)}` : ''}</p>
        <div class="page-head-actions">
          <button class="btn btn-success-soft btn-sm" data-hbt-toggle="${esc(habit.id)}">${icon('check')} ${series.completed_today ? 'Quitar de hoy' : 'Marcar hoy'}</button>
          <button class="btn btn-ghost btn-sm" data-hbt-edit="${esc(habit.id)}">${icon('edit')} Editar</button>
        </div>
      </div>
      <div class="page-grid three">
        <div class="card"><div class="card-body"><span class="kpi-label">Racha actual</span><div class="kpi-value">${esc(series.current_streak)} ${esc(series.current_streak === 1 ? 'día' : 'días')}</div></div></div>
        <div class="card"><div class="card-body"><span class="kpi-label">Racha máxima</span><div class="kpi-value">${esc(series.longest_streak)} ${esc(series.longest_streak === 1 ? 'día' : 'días')}</div></div></div>
        <div class="card"><div class="card-body"><span class="kpi-label">Cumplimiento 14 días</span><div class="kpi-value">${Math.round((series.completion_rate_14d || 0) * 100)}%</div></div></div>
      </div>
      <section class="card" style="margin-top:16px">
        <div class="card-head"><h2>${icon('calendar')} Últimos 7 días</h2></div>
        <div class="card-body">
          <div style="overflow-x:auto">${weekStrip(habit, series)}</div>
        </div>
      </section>
      <section class="card" style="margin-top:16px">
        <div class="card-head"><h2>${icon('clock')} Historial de cumplimientos</h2></div>
        <div class="card-body no-pad">
          ${completions.length
            ? `<div class="table-wrap"><table class="table">
                <thead><tr><th>Fecha</th><th>Cantidad</th><th>Nota</th><th>Fuente</th></tr></thead>
                <tbody>
                  ${completions
                    .slice()
                    .reverse()
                    .slice(0, 30)
                    .map(
                      (c) => `<tr>
                        <td>${esc(c.local_date)}</td>
                        <td>${esc(c.quantity)}</td>
                        <td>${esc(c.note || '')}</td>
                        <td>${esc(c.source || 'manual')}</td>
                      </tr>`,
                    )
                    .join('')}
                </tbody>
              </table></div>`
            : `<div class="card-body">${emptyBlock('Sin cumplimientos registrados todavía.')}</div>`}
        </div>
      </section>`;

    bind(el);

    const toggle = el.querySelector('[data-hbt-toggle]');
    toggle.addEventListener('click', async () => {
      try {
        if (series.completed_today) {
          await unmarkHabit(habit.id, { local_date: series.today });
          toast('Desmarcado', 'success');
        } else {
          await markHabit(habit.id, { local_date: series.today, quantity: habit.goal_type === 'quantity' ? habit.target_quantity : 1 });
          toast('Marcado como cumplido', 'success');
        }
      } catch (err) {
        toast(`No se pudo actualizar: ${err.message}`, 'error');
      }
      setTimeout(() => renderHabitoDetalle(el, habit.id), 250);
    });
  } catch (err) {
    el.innerHTML = `<a class="back-link" href="#/habitos">${icon('arrow')} Hábitos</a>${errorBlock(`No disponible: ${esc(err.message)}`)}`;
  }
}