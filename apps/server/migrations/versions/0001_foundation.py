"""S0 migration foundation; later stages add their own tables."""
from alembic import op
import sqlalchemy as sa
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("deployment_metadata", sa.Column("key", sa.String(100), primary_key=True), sa.Column("value", sa.Text(), nullable=False))
    op.execute("INSERT INTO deployment_metadata (key,value) VALUES ('architecture','postgres-worker-v1')")


def downgrade():
    op.drop_table("deployment_metadata")
