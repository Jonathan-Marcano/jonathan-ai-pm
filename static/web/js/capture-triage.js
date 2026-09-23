'use strict';

/* Sugerencia de clasificación local, determinista y sin proveedor externo.
   Solo propone: nunca aplica una captura. La decisión final siempre es humana.
   Refleja en el SPA el contrato de docs/capture-classification.md sin requerir
   una cuenta de modelo (la API responde 503 hasta que se autorice uno). */

const KIND_LABELS = {
  task: 'Tarea',
  expense: 'Gasto',
  income: 'Ingreso',
  habit: 'Hábito',
  note: 'Nota / referencia',
  unknown: 'Por clasificar',
};

const SIGNALS = {
  task: [
    'reunion',
    'reunión',
    'entrevista',
    'llamada',
    'correo',
    'mail',
    'informe',
    'propuesta',
    'presentar',
    'entregar',
    'responder',
    'agendar',
    'recordar',
    'recuérdame',
    'recordarme',
    'tarea',
    'pendiente',
    'revisar',
    'enviar',
    'organizar',
    'preparar',
  ],
  expense: [
    'pag',
    'gas',
    'compra',
    'compré',
    'comprado',
    'supermercado',
    'mercado',
    'feria',
    'despensa',
    'boleta',
    'cuenta',
    'almuerzo',
    'cena',
    'café',
    'servicio',
    'tarjeta',
    'transferir',
    'transferencia',
    "CLP",
    'pesos',
  ],
  income: [
    'sueldo',
    'salario',
    'honorario',
    'ingreso',
    'ingresó',
    'ingresaron',
    'depósito',
    'depositaron',
    'me pagaron',
    'recibí',
    'cobro',
    'cobré',
    'venta',
    'vendi',
  ],
  habit: [
    'hábito',
    'habito',
    'meditar',
    'meditación',
    'deporte',
    'ejercicio',
    'correr',
    'caminar',
    'gimnasio',
    'leer',
    'lectura',
    'dormir',
    'agua',
    'estirar',
    'diario',
    'rutina',
  ],
  note: [
    'idea',
    'referencia',
    'enlace',
    'apuntar',
    'guardar',
    'nota',
    'recordatorio',
  ],
};

const URGENCY = ['urgente', 'urgent', 'asap', 'hoy', 'pronto', 'crítico', 'critico', 'antes de'];

const DAY_ISO = { 'lunes': 1, 'lun': 1, 'martes': 2, 'miércoles': 3, 'jueves': 4, 'viernes': 5, 'sábado': 6, 'domingo': 0 };

/* Detecta el primer monto razonable: admite "8.500", "8,5", "$8.500", "8500 pesos". */
function detectAmount(text) {
  const m = text.match(/(\$|\bdep)\s?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+)/i);
  if (!m) return null;
  const raw = m[2] ? m[2] : null;
  if (raw === null) return null;
  const cleaned = raw.replace(/\./g, ',').replace(/,/g, '.');
  const value = Number(cleaned);
  if (!Number.isFinite(value) || value <= 0) return null;
  const units = /(clp|pesos|mil|k|m)\b/i.exec(text);
  if (units) {
    const u = units[1].toLowerCase();
    if (u === 'mil' || u === 'k') return Math.round(value * 1000);
    if (u === 'm') return Math.round(value * 1000000);
  }
  return Math.round(value);
}

function inText(text, word) {
  return text.includes(word);
}

function suggestCapture(text) {
  const t = (text || '').toLowerCase().trim();
  if (!t) {
    return { kind: 'unknown', confidence: 0, reasons: [], amount: null, priority: null, due: null };
  }

  let best = null;
  let bestScore = 0;
  const reasons = [];
  for (const [kind, words] of Object.entries(SIGNALS)) {
    let score = 0;
    const hits = [];
    for (const word of words) {
      if (inText(t, word)) {
        score += 1;
        hits.push(word);
      }
    }
    if (score > bestScore) {
      bestScore = score;
      best = { kind, hits };
    }
  }

  if (bestScore === 0) {
    return { kind: 'unknown', confidence: 0, reasons: [], amount: detectAmount(t), priority: null, due: null };
  }

  const verb = /(pagué|pagar|pagó|gasté|gastar|gasto|compré|comprar|compra)(?:\s|\b)/.test(t);
  const noun = /(boleta|cuenta|supermercado|mercado|feria|almuerzo|cena|café)/.test(t);
  if (best.kind === 'expense' && (verb || noun || inText(t, 'clp') || inText(t, 'pesos'))) {
    reasons.push('contiene marcadores de gasto.');
  }

  for (const word of best.hits.slice(0, 3)) reasons.push(`«${word}»`);

  const priority = URGENCY.some((w) => inText(t, w)) ? 'high' : null;
  const due = detectDue(text);

  const confidence = Math.min(1, 0.45 + bestScore * 0.18 + (best.kind === 'expense' && detectAmount(t) ? 0.15 : 0));
  return {
    kind: best.kind,
    confidence: Math.round(confidence * 100) / 100,
    reasons,
    amount: best.kind === 'expense' || best.kind === 'income' ? detectAmount(t) : null,
    priority,
    due,
  };
}

function detectDue(text) {
  if (!text) return null;
  const t = text.toLowerCase();
  if (inText(t, 'hoy') || inText(t, 'hoy mismo')) return todayOffset(0);
  if (inText(t, 'mañana') || inText(t, 'manuna')) return todayOffset(1);
  for (const [day, offset] of Object.entries(DAY_ISO)) {
    if (inText(t, day)) {
      const today = new Date();
      let delta = (offset - today.getDay() + 7) % 7;
      if (delta === 0) delta = 7;
      return todayOffset(delta);
    }
  }
  const m = t.match(/eld?\s(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?/);
  if (m) {
    const month = Number(m[2]);
    if (month >= 1 && month <= 12) {
      const year = m[3] ? Number(m[3]) : new Date().getFullYear();
      const day = Number(m[1]);
      const date = new Date(year, month - 1, day);
      if (date.getDate() === day) return date.toISOString().slice(0, 10);
    }
  }
  return null;
}

function todayOffset(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export { suggestCapture, KIND_LABELS };