"""add_visual_detection_fields_to_question

Revision ID: 388905b5f056
Revises: a8d7ce5d3758
Create Date: 2026-02-22 14:38:00.179386

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '388905b5f056'
down_revision = 'a8d7ce5d3758'
branch_labels = None
depends_on = None


def upgrade():
    # Split into two batches to avoid circular dependency in some SQLite versions
    # op.add_column('questions', sa.Column('has_visual', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    # op.add_column('questions', sa.Column('visual_tag', sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column('marks',
               existing_type=sa.INTEGER(),
               type_=sa.Float(),
               existing_nullable=False)


def downgrade():
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column('marks',
               existing_type=sa.Float(),
               type_=sa.INTEGER(),
               existing_nullable=False)
        batch_op.drop_column('visual_tag')
        batch_op.drop_column('has_visual')
