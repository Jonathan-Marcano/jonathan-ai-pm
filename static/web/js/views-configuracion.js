'use strict';

import { api } from './api.js';
import {
  esc,
  timeAgo,
  icon,
  toast,
  skeleton,
  emptyBlock,
  errorBlock,
} from './ui.js';

export async function renderConfiguracion(el) {
  el.innerHTML = `
    <div class="page-head">
      <h1>Configuración</h1>
      <p class="page-sub">Estado del sistema, actividad y respaldo local.</p>
    </div>
    ${skeleton(4)}`;
  try {
    const [health, progress, audit, snapshot] = await Promise.all([
      api('/health').catch(() => null),
      api('/api/v1/reports/progress').catch(() => null),
      api('/api/v1/audit-events?limit=15').catch(() => null),
      api('/api/v1/snapshots/export').catch(() => null),
    ]);
    const t = progress ? progress.totals : null;

    el.innerHTML = `
      <div class="page-head">
        <h1>Configuración</h1>
        <p class="page-sub">Estado del sistema, actividad y respaldo local.</p>
      </div>

      <div class="page-grid three">
        <section class="card">
          <div class="card-head"><h2>${icon('info')} Sistema</h2></div>
          <div class="card-body">
            <div class="settings-row"><span class="settings-key">Estado</span>${health && health.status === 'ok' ? `<span class="badge badge-active">Operativo</span>` : `<span class="badge badge-error">No responde</span>`}</div>
            <div class="settings-row"><span class="settings-key">Versión API</span><span class="settings-val">${esc((health && health.version) || '—')}</span></div>
            <div class="settings-row"><span class="settings-key">Zona horaria</span><span class="settings-val">America/Santiago</span></div>
            <div class="settings-row"><span class="settings-key">Progreso al</span><span class="settings-val">${progress ? esc(progress.as_of) : '—'}</span></div>
          </div>
        </section>
        <section class="card">
          <div class="card-head"><h2>${icon('target')} Resumen del período</h2></div>
          <div class="card-body">
            ${t ? `
              <div class="settings-row"><span class="settings-key">Tareas</span><span class="settings-val">${t.tasks.total} (${Math.round(t.tasks.completion_percent)}% completadas)</span></div>
              <div class="settings-row"><span class="settings-key">Tareas abiertas</span><span class="settings-val">${t.tasks.open} · vencidas ${t.tasks.overdue}</span></div>
              <div class="settings-row"><span class="settings-key">Tareas en bandeja</span><span class="settings-val">${t.tasks.inbox}</span></div>
              <div class="settings-row"><span class="settings-key">Entregables</span><span class="settings-val">${t.deliverables.total} (${t.deliverables.accepted} aceptados)</span></div>
              <div class="settings-row"><span class="settings-key">Horas registradas</span><span class="settings-val">${(t.logged_minutes / 60).toFixed(1)} h</span></div>` : `<div class="item-sub">Sin datos de progreso.</div>`}
          </div>
        </section>
        <section class="card">
          <div class="card-head"><h2>${icon('folder')} Respaldo local</h2></div>
          <div class="card-body">
            <p class="integ-note">Exporta una instantánea portátil (JSON) con tu información para resguardarla. El respaldo se genera al instante.</p>
            <div class="modal-actions" style="justify-content:flex-start">
              <button class="btn btn-primary btn-sm" id="cfg-export">${icon('doc')} Descargar respaldo</button>
            </div>
            <p class="integ-note" style="margin-top:10px">${snapshot ? `Último volcado: ${esc((snapshot.generated_at || snapshot.exported_at || '').slice(0, 19).replace('T', ' '))}` : 'Sin volcado previo en esta sesión.'}</p>
          </div>
        </section>
      </div>

      <div class="page-grid two">
        <section class="card">
          <div class="card-head"><h2>${icon('link')} Integraciones</h2></div>
          <div class="card-body no-pad">
            <div class="list" style="padding:0 18px">
              <div class="item"><div class="item-main"><div class="item-title">Telegram</div><div class="item-sub">Captura de mensajes a la bandeja</div></div><span class="badge badge-atrisk">Pendiente</span></div>
              <div class="item"><div class="item-main"><div class="item-title">Google Drive</div><div class="item-sub">Vínculo de documentos y entregables</div></div><span class="badge badge-atrisk">Pendiente</span></div>
              <div class="item"><div class="item-main"><div class="item-title">Google Calendar</div><div class="item-sub">Sincronización de reuniones</div></div><span class="badge badge-atrisk">Pendiente</span></div>
              <div class="item"><div class="item-main"><div class="item-title">Procesamiento de movimientos (Finanzas)</div><div class="item-sub">Importación de estados de cuenta</div></div><span class="badge badge-atrisk">Pendiente</span></div>
            </div>
            <p class="integ-note" style="padding:0 18px 12px">La verificación de integraciones externas se completa en fases posteriores; por ahora se usan sustitutos simulados en pruebas.</p>
          </div>
        </section>
        <section class="card">
          <div class="card-head"><h2>${icon('clock')} Actividad reciente</h2></div>
          <div class="card-body no-pad">
            ${audit && audit.length ? `<div class="list" style="padding:0 18px">
              ${audit.slice(0, 12).map((e) => `
                <div class="item">
                  <div class="item-main">
                    <div class="item-title">${esc(e.entity_kind)} · ${esc(e.action)}</div>
                    <div class="item-sub"><b>${esc(e.actor)}</b> · ${esc(e.entity_id)} · ${esc(timeAgo(e.occurred_at))}</div>
                  </div>
                </div>`).join('')}
            </div>` : `<div class="card-body">${emptyBlock('Sin actividad registrada.')}</div>`}
          </div>
        </section>
      </div>

      <section class="card" style="margin-top:16px">
        <div class="card-head"><h2>${icon('info')} Acerca de FaroFlow</h2></div>
        <div class="card-body">
          <p class="integ-note">Asistente local para trabajo, finanzas, hábitos y captura diaria. Los datos viven en tu máquina; ninguna integración externa ha sido verificada todavía.</p>
        </div>
      </section>`;

    el.querySelector('#cfg-export').addEventListener('click', () => {
      if (!snapshot) {
        toast('No hay respaldo disponible', 'error');
        return;
      }
      const blob = new Blob([JSON.stringify(snapshot, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `faroflow-respaldo-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast('Respaldo descargado', 'success');
    });
  } catch (err) {
    el.innerHTML = `<div class="page-head"><h1>Configuración</h1></div>${errorBlock(`No disponible: ${err.message}`)}`;
  }
}