# Modelo de datos

Documento de referencia: CF0-07.

## Relaciones

```text
Household 1 ── * HouseholdMember
Household 1 ── * FinancialAccount
Household 1 ── * Category
Household 1 ── * IncomeSource
Household 1 ── * Budget 1 ── * BudgetCategory
Household 1 ── * Debt
Debt 1 ── * Installment
Debt 1 ── * DebtPayment
Household 1 ── * FinancialGoal
Household 1 ── * PaymentPlan 1 ── * ProjectionScenario
Household 1 ── * DocumentReference
Household 1 ── * ImportBatch
FinancialAccount 1 ── * Transaction
Category 1 ── * Transaction
HouseholdMember 1 ── * Transaction (optional, author)
```

## Entidades

| Entidad | Propósito | Campos clave requeridos |
|---|---|---|
| Household | Hogar o unidad financiera | `id`, `name`, `status`, `timezone` |
| HouseholdMember | Integrante del hogar | `id`, `household_id`, `name`, `role`, `status` |
| FinancialInstitution | Banco u otra entidad | `id`, `name`, `type` |
| FinancialAccount | Cuenta corriente, tarjeta, crédito, efectivo | `id`, `household_id`, `institution_id?`, `name`, `type`, `currency`, `balance_reported`, `balance_calculated`, `original_amount?`, `status` |
| Transaction | Ingreso, gasto, transferencia, pago o ajuste | `id`, `account_id`, `amount`, `type`, `date`, `status` |
| Category | Clasificación de ingresos y gastos | `id`, `household_id`, `name`, `kind`, `status` |
| IncomeSource | Salario, trabajo adicional, bono u otro | `id`, `household_id`, `member_id?`, `name`, `type`, `expected_amount`, `frequency`, `status` |
| Budget | Presupuesto de un periodo | `id`, `household_id`, `year_month`, `status` |
| BudgetCategory | Monto planificado por categoría | `id`, `budget_id`, `category_id`, `planned_amount`, `actual_amount` |
| Debt | Tarjeta, crédito, auto, préstamo o línea | `id`, `household_id`, `account_id?`, `name`, `type`, `original_amount`, `current_balance`, `interest_rate`, `minimum_payment`, `due_day`, `status` |
| DebtPayment | Pago ordinario o extraordinario | `id`, `debt_id`, `amount`, `type`, `payment_date`, `recorded_by` |
| Installment | Cuota programada (capital, interés, cargos) | `id`, `debt_id`, `due_date`, `principal_amount`, `interest_amount`, `fee_amount`, `total_amount`, `status` |
| FinancialGoal | Eliminar deuda, ahorrar o crear fondo | `id`, `household_id`, `name`, `type`, `target_amount`, `current_amount`, `deadline?`, `priority`, `status` |
| PaymentPlan | Estrategia de pago seleccionada | `id`, `household_id`, `strategy`, `name`, `status` |
| ProjectionScenario | Simulación con pagos y bonos | `id`, `plan_id`, `name`, `monthly_payment`, `extra_income`, `assumptions`, `result_summary` |
| DocumentReference | Enlace a comprobante o estado de cuenta | `id`, `household_id`, `entity_kind`, `entity_id`, `url`, `description` |
| ImportBatch | Registro auditable de una importación | `id`, `household_id`, `source_file`, `format`, `status`, `record_count`, `imported_by` |
| AuditEvent | Historial inmutable de cambios | `id`, `entity_kind`, `entity_id`, `action`, `actor`, `occurred_at`, `changes` |

## Vocabularios de estado

| Entidad | Estados permitidos |
|---|---|
| Household | `active`, `paused`, `archived` |
| HouseholdMember | `active`, `inactive` |
| FinancialAccount | `active`, `paused`, `closed` |
| FinancialInstitution | `active`, `inactive` |
| Transaction | `posted`, `voided` |
| Category | `active`, `inactive` |
| IncomeSource | `active`, `inactive` |
| Budget | `draft`, `active`, `closed` |
| Debt | `active`, `paid_off`, `closed` |
| Installment | `pending`, `paid`, `overdue` |
| PaymentPlan | `selected`, `draft`, `archived` |
| FinancialGoal | `active`, `achieved`, `abandoned` |
| ImportBatch | `pending`, `completed`, `failed` |

## Reglas de precisión monetaria

- Todo monto es un entero en unidades menores (centavos de CLP); nunca `float`.
- Se distinguen claramente: saldo informado por la institución, saldo calculado,
  monto originalmente financiado, capital pendiente, intereses, cargos, pago mínimo,
  cuota pactada y pago extraordinario.
- Un pago no puede modificar silenciosamente el saldo original.
- Las transferencias internas no se contabilizan como ingreso o gasto.
- Intereses y prórratas se redondean en el paso y su regla se documenta.

Ver [ADR 0002](decisions/0002-money-and-precision.md).

## Identificadores y tiempo

- IDs con prefijos legibles: `hh_`, `mem_`, `fin_`, `fac_`, `txn_`, `cat_`,
  `inc_`, `bud_`, `bcc_`, `deb_`, `dpy_`, `ins_`, `gol_`, `ppl_`, `psc_`,
  `doc_`, `imp_`, `aud_`.
- Fechas y timestamps en ISO 8601.
- Timestamps almacenados en UTC; presentación con `APP_TIMEZONE`.
- Registros incluyen `created_at` y `updated_at` al persistir.

## Alcance por fase

- **MVP (Fase 1)**: Household, HouseholdMember, FinancialInstitution,
  FinancialAccount, Transaction, Category, IncomeSource, Budget, BudgetCategory,
  Debt, DebtPayment, Installment, FinancialGoal, PaymentPlan, ProjectionScenario,
  DocumentReference, AuditEvent.
- **Fase 2**: ImportBatch, identidades externas estables, deduplicación y cola de revisión.
- **Fases 3-4**: registros de propuestas de IA y capturas WhatsApp (gate de decisión previo).

El contrato legible por máquina es [schemas/domain-model.schema.json](../schemas/domain-model.schema.json).