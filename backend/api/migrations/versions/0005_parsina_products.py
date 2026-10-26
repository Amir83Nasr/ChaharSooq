"""Parsina product mirror: product columns + sync state table."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_parsina_products"
down_revision: str | None = "0004_session_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("products_sku_key", "products", type_="unique")
    op.alter_column(
        "products",
        "price",
        existing_type=sa.Integer(),
        type_=sa.Numeric(18, 2),
        existing_nullable=False,
        postgresql_using="price::numeric(18,2)",
    )
    op.alter_column(
        "products",
        "stock",
        existing_type=sa.Integer(),
        type_=sa.Numeric(18, 3),
        existing_nullable=False,
        postgresql_using="stock::numeric(18,3)",
    )
    op.add_column("products", sa.Column("external_id", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("main_group_id", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("sub_group_id", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("main_group_name", sa.String(200), nullable=True))
    op.add_column("products", sa.Column("sub_group_name", sa.String(200), nullable=True))
    op.add_column("products", sa.Column("unit_id", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("unit_name", sa.String(120), nullable=True))
    op.add_column("products", sa.Column("weight", sa.Numeric(18, 3), nullable=True))
    op.add_column(
        "products",
        sa.Column("is_special", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "products",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("products", sa.Column("buy_price", sa.Numeric(18, 2), nullable=True))
    op.add_column("products", sa.Column("sale_pack_price", sa.Numeric(18, 2), nullable=True))
    op.add_column("products", sa.Column("sale_box_price", sa.Numeric(18, 2), nullable=True))
    op.add_column("products", sa.Column("use_price", sa.Numeric(18, 2), nullable=True))
    op.add_column("products", sa.Column("discount", sa.Numeric(9, 4), nullable=True))
    op.add_column("products", sa.Column("extra", sa.Numeric(9, 4), nullable=True))
    op.add_column("products", sa.Column("number_in_box", sa.Numeric(18, 3), nullable=True))
    op.add_column("products", sa.Column("number_in_pack", sa.Numeric(18, 3), nullable=True))
    op.add_column("products", sa.Column("ware_remain", sa.Numeric(18, 3), nullable=True))
    op.add_column("products", sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_products_external_id", "products", ["external_id"])
    op.create_index("ix_products_sku", "products", ["sku"])
    op.create_index("ix_products_main_group_name", "products", ["main_group_name"])

    op.create_table(
        "parsina_sync_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lock_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("running_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("last_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_deactivated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_skipped", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("parsina_sync_state")
    op.drop_index("ix_products_main_group_name", table_name="products")
    op.drop_index("ix_products_sku", table_name="products")
    op.drop_constraint("uq_products_external_id", "products", type_="unique")
    for column in [
        "synced_at",
        "ware_remain",
        "number_in_pack",
        "number_in_box",
        "extra",
        "discount",
        "use_price",
        "sale_box_price",
        "sale_pack_price",
        "buy_price",
        "is_active",
        "is_special",
        "weight",
        "unit_name",
        "unit_id",
        "sub_group_name",
        "main_group_name",
        "sub_group_id",
        "main_group_id",
        "external_id",
    ]:
        op.drop_column("products", column)
    op.alter_column(
        "products",
        "stock",
        existing_type=sa.Numeric(18, 3),
        type_=sa.Integer(),
        postgresql_using="stock::integer",
    )
    op.alter_column(
        "products",
        "price",
        existing_type=sa.Numeric(18, 2),
        type_=sa.Integer(),
        postgresql_using="price::integer",
    )
    op.create_unique_constraint("products_sku_key", "products", ["sku"])
