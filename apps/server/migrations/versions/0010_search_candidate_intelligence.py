"""Versioned AI opportunity cards, distinct from verified JD records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint('uq_search_candidates_owner_id_id', 'search_candidates', ['owner_id', 'id'])
    op.create_table('search_candidate_analyses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('candidate_id', sa.UUID(), nullable=False),
        sa.Column('analysis_run_id', sa.UUID(), nullable=False),
        sa.Column('data', postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_search_candidate_analyses')),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_search_candidate_analyses_owner_id_users'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_id','candidate_id'], ['search_candidates.owner_id','search_candidates.id'], name=op.f('fk_search_candidate_analyses_owner_id_candidate_id_search_candidates')),
        sa.ForeignKeyConstraint(['owner_id','analysis_run_id'], ['agent_runs.owner_id','agent_runs.id'], name=op.f('fk_search_candidate_analyses_owner_id_analysis_run_id_agent_runs')),
        sa.UniqueConstraint('owner_id','candidate_id','analysis_run_id', name=op.f('uq_search_candidate_analyses_owner_id_candidate_id_analysis_run_id')))
    op.create_index('ix_search_candidate_analyses_candidate_id', 'search_candidate_analyses', ['candidate_id'])
    op.create_index('ix_search_candidate_analyses_owner_id', 'search_candidate_analyses', ['owner_id'])


def downgrade():
    op.drop_table('search_candidate_analyses')
    op.drop_constraint('uq_search_candidates_owner_id_id', 'search_candidates', type_='unique')
