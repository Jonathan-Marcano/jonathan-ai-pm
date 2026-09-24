"""Allow multiple habit completions per day (one row per external reference).

Revision ID: 20260923_0012
Revises: 20260922_0011
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260923_0012"
down_revision: str | None = "20260922_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TMP = "habit_completions_checklist_tmp"
_COLS = (
    "id",
    "habit_id",
    "local_date",
    "quantity",
    "note",
    "source",
    "external_ref",
    "created_at",
    "updated_at",
)


def _copy(conn, src: str, dst: str) -> None:
    cols = ", ".join(_COLS)
    conn.execute(
        sa.text(
            f"INSERT INTO {dst} ({cols}) SELECT {cols} FROM {src}"
        )
    )


def upgrade() -> None:
    # SQLite: una restricción UNIQUE de tabla se guarda como autoíndice y no
    # puede eliminarse con DROP INDEX. Se reconstruye la tabla sin el UNIQUE
    # para permitir múltiples completaciones por día (una por external_ref).
    conn = op.get_bind()
    op.create_table(
        _TMP,
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("habit_id", sa.String(80), index=True),
        sa.Column("local_date", sa.Date(), index=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("note", sa.String(500)),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("external_ref", sa.String(240)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("quantity >= 1"),
        sa.CheckConstraint("source IN ('manual','bandeja','telegram')"),
    )
    op.create_index("ix_habit_completion_day", _TMP, ["habit_id", "local_date"])
    _copy(conn, "habit_completions", _TMP)
    op.drop_table("habit_completions")
    op.rename_table(_TMP, "habit_completions")


def downgrade() -> None:
    # Reconstruye con la restricción UNIQUE(habit_id, local_date) original.
    conn = op.get_bind()
    op.create_table(
        _TMP,
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("habit_id", sa.String(80)),
        sa.Column("local_date", sa.Date()),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("note", sa.String(500)),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("external_ref", sa.String(240)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("quantity >= 1"),
        sa.CheckConstraint("source IN ('manual','bandeja','telegram')"),
        sa.UniqueConstraint("habit_id", "local_date", name="uq_habit_completion_day"),
        sa.Index("ix_habit_completions_habit_id", "habit_id"),
        sa.Index("ix_habit_completions_local_date", "local_date"),
    )
    _copy(conn, "habit_completions", _TMP)
    op.drop_table("habit_completions")
    op.rename_table(_TMP, "habit_completions")