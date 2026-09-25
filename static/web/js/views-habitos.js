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
  kpiTile,
} from './ui.js';

const DAY_LETTERS = ['L', 'M', 'X', 'J', 'V', 'S', 'D']; // índice = isoWeekday - 1
const WEEKDAY_LETTERS = ['D', 'L', 'M', 'X', 'J', 'V', 'S']; // índice = Date.getDay() (0 = domingo)
const HABIT_SOURCE_LABEL = { manual: 'manual', bandeja: 'bandeja', telegram: 'Telegram' };

function fmtTimeR(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function isoWeekday(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return ((d.getDay() + 6) % 7) + 1;
}

export function last7() {
  const days = [];
  for (let i = 6; i >= 0; i--) days.push(addDaysISO(todayISO(), -i));
  return days;
}

export function currentWeek() {
  const d = new Date(`${todayISO()}T12:00:00`);
  const offset = (d.getDay() + 6) % 7;
  const days = [];
  for (let i = 0; i < 7; i++) days.push(addDaysISO(todayISO(), i - offset));
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

/* Un hábito semanal se cumple con el total de la semana natural (lunes a
   domingo), no con los últimos 7 días corridos. */
function weeklyMet(habit, iso, series) {
  const days = weekDays(series);
  const scope = days.length
    ? days
    : currentWeek().filter((d) => d <= (series.today || iso));
  const total = scope
    .map((d) => quantityOn(series.completions, d))
    .reduce((a, b) => a + b, 0);
  return total >= (Number(habit.weekly_target) || 1);
}

/* La semana natural (lunes a domingo) y el cumplimiento por día los calcula
   el servidor en `series.week`; aquí solo se representa. */
function weekDays(series) {
  return ((series && series.week && series.week.days) || []).map((d) => d.date);
}

function dayState(habit, iso, series) {
  const fromServer = ((series && series.week && series.week.days) || []).find(
    (d) => d.date === iso,
  );
  if (fromServer) {
    const partial =
      fromServer.scheduled &&
      habit.goal_type === 'quantity' &&
      fromServer.quantity > 0 &&
      !fromServer.met;
    return {
      qty: fromServer.quantity,
      done: fromServer.met,
      partial,
      scheduled: fromServer.scheduled,
      due: fromServer.due,
    };
  }
  const qty = quantityOn(series.completions, iso);
  const scheduled = isScheduled(habit, iso);
  const done =
    habit.frequency === 'weekly'
      ? weeklyMet(habit, iso, series)
      : scheduled && isMet(habit, iso, series, qty);
  const partial = scheduled && habit.goal_type === 'quantity' && qty > 0 && !done;
  return { qty, done, partial, scheduled, due: scheduled };
}

function seriesForDay(habit, iso, series) {
  return dayState(habit, iso, series);
}

function dayCell(habit, iso, series) {
  const s = seriesForDay(habit, iso, series);
  const isToday = iso === (series.today || todayISO());
  const future = iso > todayISO();
  const cls = [
    'day-cell',
    isToday ? 'today' : '',
    future ? 'future' : '',
    s.done ? 'done' : '',
    s.partial ? 'partial' : '',
    s.due ? 'due' : '',
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

function weekStrip(habit, series, days) {
  const strip = days && days.length ? days : weekDays(series).length ? weekDays(series) : last7();
  return `<div class="habit-row">
    <span class="item-title">${esc(habit.name)}</span>
    ${strip.map((iso) => dayCell(habit, iso, series)).join('')}
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
    const activeRows = (habits || []).filter((h) => h.status !== 'archived');
    if (!activeRows.length) {
      el.innerHTML = `
        <div class="page-head">
          <h1>Hábitos</h1>
          <p class="page-sub">Objetivos diarios y semanales con seguimiento de racha.</p>
        </div>
        <section class="card"><div class="card-body">${emptyBlock(
          'Aún no tienes hábitos. Crea el primero.',
          '<button class="btn btn-primary btn-sm" id="hbt-new">Nuevo hábito</button>',
        )}</div></section>`;
      bind(el);
      return;
    }

    const series = await Promise.all(activeRows.map((h) => habitSeries(h.id)));
    const today = series[0]?.today || todayISO();
    const selectedId = el.dataset.selectedHabit || activeRows[0]?.id || null;

    let doneToday = 0;
    let dueToday = 0;
    let maxLongest = 0;
    const completeRows = [];
    const ranking = [];
    const weekStats = { done: 0, due: 0, habitsDue: 0, habitsDone: 0 };
    const week = weekDays(series[0]).length ? weekDays(series[0]) : currentWeek();
    const daySummary = week.map((iso) => {
      const cell = { done: 0, due: 0 };
      series.forEach((s) => {
        const d = ((s.week && s.week.days) || []).find((x) => x.date === iso);
        if (!d) return;
        if (d.met) cell.done += 1;
        if (d.due) cell.due += 1;
      });
      return cell;
    });

    activeRows.forEach((h, i) => {
      const s = series[i];
      const st = dayState(h, today, s);
      if (st.done) doneToday += 1;
      else if (st.due) dueToday += 1;
      maxLongest = Math.max(maxLongest, s.longest_streak || 0);
      ranking.push({ name: h.name, id: h.id, streak: s.current_streak || 0 });
      (s.completions || []).forEach((c) => {
        completeRows.push({ habit: h.name, src: c.source, at: c.created_at || `${c.local_date}T12:00:00`, local_date: c.local_date, qty: c.quantity });
      });
      const w = s.week;
      if (w) {
        weekStats.done += w.met_days;
        weekStats.due += w.scheduled_days;
        if (w.scheduled_days > 0) weekStats.habitsDue += 1;
        if (w.goal_met) weekStats.habitsDone += 1;
      }
    });

    const weekRate = weekStats.due ? Math.round((weekStats.done / weekStats.due) * 100) : 0;

    const kpiRow = `<div class="kpi-row three">
        ${kpiTile({
          icon: 'check',
          tone: 'accent',
          label: 'Completados hoy',
          value: `${doneToday}<span class="kpi-value-unit">/ ${doneToday + dueToday}</span>`,
          note: doneToday + dueToday === 0 ? 'Nada programado para hoy' : 'Hábitos programados para hoy',
        })}
        ${kpiTile({
          icon: 'target',
          tone: 'success',
          label: 'Resumen de la semana actual',
          value: `${weekStats.habitsDone}<span class="kpi-value-unit">/ ${weekStats.habitsDue} hábitos</span>`,
          note: `${weekRate}% de constancia`,
        })}
        ${kpiTile({
          icon: 'sparkles',
          tone: 'warm',
          label: 'Mejor racha',
          value: `${maxLongest} <span class="kpi-value-unit">${maxLongest === 1 ? 'día' : 'días'}</span>`,
          note: 'Racha más larga registrada',
        })}
      </div>`;

    const topRachas = ranking.filter((r) => r.streak > 0).sort((a, b) => b.streak - a.streak).slice(0, 3);

    const mainCard = `
      <section class="card">
        <div class="card-head"><h2>${icon('target')} Tus hábitos</h2><a class="card-action" href="#/habitos/semana">Vista semanal</a></div>
        <div class="card-body">
          ${activeRows
            .map((h, i) => {
              const s = series[i];
              return `
              <div class="habit-card${h.id === selectedId ? ' is-selected' : ''}" data-hbt-select="${esc(h.id)}">
                <div class="habit-head">
                  <div class="habit-name">${esc(h.name)}</div>
                  <div class="habit-goal">${esc(goalLabel(h))}${h.status === 'paused' ? ' · en pausa' : ''}</div>
                  <div class="item-side">${badge(h.status)}</div>
                </div>
                ${weekStrip(h, s, week)}
                <div class="habit-meta">
                  <span class="streak-badge mint">${icon('sparkles')} Racha ${esc(s.current_streak)}</span>
                  <span class="streak-badge">${Math.round((s.completion_rate_14d || 0) * 100)}% últ. 14 días</span>
                  <div class="habit-actions">
                    <a class="btn btn-soft btn-xs" href="#/habitos/${esc(h.id)}">${icon('arrow')} Detalle</a>
                    <button class="btn btn-ghost btn-xs" data-hbt-edit="${esc(h.id)}" title="Editar">${icon('edit')}</button>
                    ${h.status === 'active' ? `<button class="btn btn-ghost btn-xs" data-hbt-status="${esc(h.id)}" data-status="paused">Pausar</button>` : ''}
                    ${h.status === 'paused' ? `<button class="btn btn-soft btn-xs" data-hbt-status="${esc(h.id)}" data-status="active">Reanudar</button>` : ''}
                    <button class="btn btn-ghost btn-xs" data-hbt-delete="${esc(h.id)}" title="Archivar">${icon('trash')}</button>
                  </div>
                </div>
              </div>`;
            })
            .join('')}
        </div>
      </section>`;

    const selHabit = selectedId ? activeRows.find((h) => h.id === selectedId) : null;
    const selSeries = selHabit ? series[activeRows.findIndex((h) => h.id === selectedId)] : null;
    const selWeek = (selSeries && selSeries.week) || { met_days: 0, scheduled_days: 0 };
    const selWeekRate = selWeek.scheduled_days
      ? Math.round((selWeek.met_days / selWeek.scheduled_days) * 100)
      : 0;

    const habitDetail = selHabit && selSeries ? `
      <section class="card">
        <div class="card-head"><h2>${icon('target')} ${esc(selHabit.name)}</h2>${badge(selHabit.status)}</div>
        <div class="card-body">
          <p class="page-sub">${esc(goalLabel(selHabit))}${selHabit.description ? ` · ${esc(selHabit.description)}` : ''}</p>
          <div class="kpi-row three compact">
            ${kpiTile({ label: 'Racha actual', value: esc(selSeries.current_streak), note: 'días seguidos', noIcon: true, tight: true })}
            ${kpiTile({ label: 'Racha máxima', value: esc(selSeries.longest_streak), note: 'mejor histórico', noIcon: true, tight: true })}
            ${kpiTile({ label: 'Cumplimiento 14 días', value: `${Math.round((selSeries.completion_rate_14d || 0) * 100)}<span class="kpi-value-unit">%</span>`, note: 'días programados', noIcon: true, tight: true })}
          </div>
          <div class="bar-list">
            <div class="bar-row">
              <span class="bar-name">Semana actual</span>
              <div class="bar-track"><div class="bar-fill" style="width:${selWeekRate}%"></div></div>
              <span class="bar-amt">${esc(selWeek.met_days)}/${esc(selWeek.scheduled_days)}</span>
            </div>
          </div>
          <div class="habit-detail-actions">
            <button class="btn btn-success-soft btn-sm" data-hbt-toggle="${esc(selHabit.id)}" data-hbt-toggle-target="list">${icon('check')} ${selSeries.completed_today ? 'Quitar de hoy' : 'Marcar hoy'}</button>
            <a class="btn btn-soft btn-sm" href="#/habitos/${esc(selHabit.id)}">${icon('arrow')} Ver detalle</a>
          </div>
        </div>
      </section>` : '';

    const sideHtml = `${habitDetail}
      <section class="card">
        <div class="card-head"><h2>${icon('calendar')} Semana actual</h2></div>
        <div class="card-body">
          <div class="week-matrix">
            <div class="week-matrix-scroll">
              <div class="week-matrix-grid">
                <div class="matrix-row week-head">
                  <span class="week-label">Día</span>
                  ${week.map((iso) => `<span class="week-label week-label-center">${WEEKDAY_LETTERS[new Date(`${iso}T12:00:00`).getDay()]} ${esc(iso.slice(8))}</span>`).join('')}
                  <span class="week-label week-label-right">Total</span>
                </div>
                <div class="matrix-row">
                  <span class="week-label week-label-nowrap">Cumplidos</span>
                  ${week.map((iso, di) => {
                    const d = daySummary[di];
                    return `<span class="matrix-cell ${d.done && d.done >= d.due ? 'done' : d.done ? 'partial' : ''} ${iso === today ? 'today' : ''}" title="${esc(iso)}">${esc(d.done)}${d.due ? `/${esc(d.due)}` : ''}</span>`;
                  }).join('')}
                  <span class="week-label week-label-right">${esc(weekStats.done)}</span>
                </div>
              </div>
            </div>
          </div>
          <p class="page-sub week-matrix-note">Cumplidos de ${esc(weekStats.due)} objetivos programados en la semana.</p>
        </div>
      </section>
      ${(() => {
        const recent = completeRows
          .filter((r) => r.at)
          .sort((a, b) => String(b.at).localeCompare(String(a.at)))
          .slice(0, 6);
        if (!recent.length) return '';
        return `
      <section class="card">
        <div class="card-head"><h2>${icon('clock')} Registro reciente</h2></div>
        <div class="card-body no-pad">
          <div class="list" style="padding:0 18px">
            ${recent.map((r) => `
              <div class="item">
                <div class="item-main">
                  <div class="item-title">${esc(r.habit)}</div>
                  <div class="item-sub">${r.at ? esc(fmtTimeR(r.at)) : esc(r.local_date)} · ${esc(r.qty)} ${esc(HABIT_SOURCE_LABEL[r.src] || r.src || 'manual')}</div>
                </div>
              </div>`).join('')}
          </div>
        </div>
      </section>`;
      })()}
      ${topRachas.length ? `<section class="card">
        <div class="card-head"><h2>${icon('sparkles')} Rachas destacadas</h2><a class="card-action" href="#/habitos/semana">Semana</a></div>
        <div class="card-body"><div class="p-list">${topRachas.map((r) => `
          <a class="item" href="#/habitos/${esc(r.id)}"><div class="item-main"><div class="item-title">${esc(r.name)}</div></div><div class="item-side"><span class="streak-badge mint">${esc(r.streak)} días</span></div></a>`).join('')}</div></div>
      </section>` : ''}`;

    el.innerHTML = `
      <div class="page-head">
        <h1>Hábitos</h1>
        <p class="page-sub">Semana real del ${esc(week[0].slice(8))}/${esc(week[0].slice(5, 7))} al ${esc(week[6].slice(8))}/${esc(week[6].slice(5, 7))}.</p>
        <div class="page-head-actions">
          <button class="btn btn-primary" id="hbt-new">${icon('plus')} Nuevo hábito</button>
        </div>
      </div>
      ${kpiRow}
      <div class="split-60-40">
        <div class="split-main">${mainCard}</div>
        <div class="split-side">${sideHtml}</div>
      </div>
      <p class="page-sub" style="margin-top:12px">Haz clic en cualquier día de la franja para marcarlo o desmarcarlo.</p>`;

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

    const selBtn = event.target.closest('[data-hbt-select]');
    if (selBtn && !event.target.closest('[data-hbt-edit], [data-hbt-status], [data-hbt-delete], .habit-actions a, .day-cell')) {
      el.dataset.selectedHabit = selBtn.dataset.hbtSelect;
      setTimeout(() => renderHabitos(el), 50);
      return;
    }

    const listToggle = event.target.closest('[data-hbt-toggle][data-hbt-toggle-target="list"]');
    if (listToggle) {
      const habitId = listToggle.dataset.hbtToggle;
      try {
        const s = await habitSeries(habitId);
        if (s.completed_today) {
          await unmarkHabit(habitId, { local_date: s.today });
          toast('Desmarcado', 'success');
        } else {
          await markHabit(habitId, { local_date: s.today, quantity: s.habit.goal_type === 'quantity' ? s.habit.target_quantity : 1 });
          toast('Marcado como cumplido', 'success');
        }
      } catch (err) {
        toast(`No se pudo actualizar: ${err.message}`, 'error');
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
    const days = weekDays(series[0]).length ? weekDays(series[0]) : currentWeek();
    const start = series[0]?.week?.start || days[0];
    const end = series[0]?.week?.end || days[days.length - 1];
    const head = `
      <div class="habit-row week-head">
        <span class="week-label">Hábito</span>
        ${days.map((d) => `<span class="week-label week-label-center">${WEEKDAY_LETTERS[new Date(`${d}T12:00:00`).getDay()]} ${esc(d.slice(8))}</span>`).join('')}
        <span class="week-label week-label-right">Racha</span>
      </div>`;
    el.innerHTML = `
      <div class="page-head">
        <h1>Semana actual</h1>
        <p class="page-sub">Del ${esc(start)} al ${esc(end)}. Toca una celda para marcar o desmarcar.</p>
        <div class="page-head-actions"><a class="btn btn-ghost btn-sm" href="#/habitos">${icon('arrow')} Todos los hábitos</a></div>
      </div>
      <section class="card">
        <div class="card-body">
          <div class="table-scroll">${head}${active.map((h, i) => weekStrip(h, series[i], days)).join('')}</div>
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
      <div class="page-head-row">
        <div class="page-titleblock">
          <h1>${esc(habit.name)}</h1>
          <p class="page-sub">${esc(goalLabel(habit))}${habit.description ? ` · ${esc(habit.description)}` : ''}</p>
        </div>
        <div class="detail-actions">
          <button class="btn btn-success-soft btn-sm" data-hbt-toggle="${esc(habit.id)}">${icon('check')} ${series.completed_today ? 'Quitar de hoy' : 'Marcar hoy'}</button>
          <button class="btn btn-ghost btn-sm" data-hbt-edit="${esc(habit.id)}">${icon('edit')} Editar</button>
        </div>
      </div>
      <div class="kpi-row three">
        ${kpiTile({ icon: 'sparkles', tone: 'warm', label: 'Racha actual', value: `${esc(series.current_streak)} <span class="kpi-value-unit">${series.current_streak === 1 ? 'día' : 'días'}</span>`, note: 'días seguidos' })}
        ${kpiTile({ icon: 'target', tone: 'accent', label: 'Racha máxima', value: `${esc(series.longest_streak)} <span class="kpi-value-unit">${series.longest_streak === 1 ? 'día' : 'días'}</span>`, note: 'mejor histórico' })}
        ${kpiTile({ icon: 'check', tone: 'success', label: 'Cumplimiento 14 días', value: `${Math.round((series.completion_rate_14d || 0) * 100)}<span class="kpi-value-unit">%</span>`, note: 'días programados' })}
      </div>
      <section class="card spaced">
        <div class="card-head"><h2>${icon('calendar')} Semana actual</h2></div>
        <div class="card-body">
          <div class="table-scroll">${weekStrip(habit, series)}</div>
        </div>
      </section>
      <section class="card spaced">
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