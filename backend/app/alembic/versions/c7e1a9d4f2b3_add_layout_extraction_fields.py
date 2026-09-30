"""Add layout-extraction content fields to questions

Revision ID: c7e1a9d4f2b3
Revises: b2c24d78ba8a
Create Date: 2026-09-30 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "c7e1a9d4f2b3"
down_revision = "b2c24d78ba8a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("questions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("content", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("solution_content", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("display_order", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "needs_review", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(sa.Column("review_reasons", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "answer_source", sqlmodel.sql.sqltypes.AutoString(), nullable=True
            )
        )
        batch_op.create_index(
            "ix_questions_display_order", ["display_order"], unique=False
        )


def downgrade():
    with op.batch_alter_table("questions", schema=None) as batch_op:
        batch_op.drop_index("ix_questions_display_order")
        batch_op.drop_column("answer_source")
        batch_op.drop_column("review_reasons")
        batch_op.drop_column("needs_review")
        batch_op.drop_column("display_order")
        batch_op.drop_column("solution_content")
        batch_op.drop_column("content")
