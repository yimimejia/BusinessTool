"""add urgent flag to jobs

Revision ID: add_urgent_flag
Revises: 
Create Date: 2025-02-25 11:55:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_urgent_flag'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Agregar columna is_urgent a la tabla jobs
    op.add_column('jobs', sa.Column('is_urgent', sa.Boolean(), nullable=True, server_default='false'))

def downgrade():
    # Eliminar columna is_urgent de la tabla jobs
    op.drop_column('jobs', 'is_urgent')
