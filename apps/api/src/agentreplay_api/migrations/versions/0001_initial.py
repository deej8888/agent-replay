"""Initial trace storage.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("model", sa.String(200)),
        sa.Column("source_run_id", sa.String(36)),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    for field in ("name", "status", "started_at", "model"):
        op.create_index(f"ix_runs_{field}", "runs", [field])
    op.create_index("ix_runs_started_id", "runs", ["started_at", "id"])
    op.create_table(
        "spans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("parent_id", sa.String(36)),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_spans_run_id", "spans", ["run_id"])


def downgrade():
    op.drop_table("spans")
    op.drop_table("runs")
