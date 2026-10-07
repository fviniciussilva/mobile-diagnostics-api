"""init

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create devices table
    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("serial", sa.String(length=255), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("android", "ios", "unknown", name="deviceplatform"),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
        sa.Column("android_version", sa.String(length=50), nullable=True),
        sa.Column("ios_version", sa.String(length=50), nullable=True),
        sa.Column("sdk_version", sa.String(length=50), nullable=True),
        sa.Column("imei", sa.String(length=50), nullable=True),
        sa.Column("imei2", sa.String(length=50), nullable=True),
        sa.Column("serial_number", sa.String(length=255), nullable=True),
        sa.Column("battery_level", sa.Integer(), nullable=True),
        sa.Column("battery_health", sa.String(length=50), nullable=True),
        sa.Column("storage_total", sa.Integer(), nullable=True),
        sa.Column("storage_free", sa.Integer(), nullable=True),
        sa.Column("is_rooted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_encrypted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "status",
            sa.Enum(
                "connected",
                "disconnected",
                "error",
                "unauthorized",
                name="devicestatus",
            ),
            nullable=False,
            server_default="disconnected",
        ),
        sa.Column(
            "last_seen", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("serial"),
    )
    op.create_index("ix_devices_platform_status", "devices", ["platform", "status"])
    op.create_index("ix_devices_last_seen", "devices", ["last_seen"])
    op.create_index(op.f("ix_devices_imei"), "devices", ["imei"], unique=False)

    # Create diagnostics table
    op.create_table(
        "diagnostics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "basic_info",
                "battery",
                "storage",
                "network",
                "security",
                "hardware",
                "software",
                "full",
                "backup",
                "imei_check",
                name="diagnostictype",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "failed",
                "timeout",
                name="diagnosticstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_diagnostics_device_type", "diagnostics", ["device_id", "type"]
    )
    op.create_index(
        "ix_diagnostics_status_created", "diagnostics", ["status", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_diagnostics_status_created", table_name="diagnostics")
    op.drop_index("ix_diagnostics_device_type", table_name="diagnostics")
    op.drop_table("diagnostics")
    op.drop_index(op.f("ix_devices_imei"), table_name="devices")
    op.drop_index("ix_devices_last_seen", table_name="devices")
    op.drop_index("ix_devices_platform_status", table_name="devices")
    op.drop_table("devices")
    op.execute("DROP TYPE deviceplatform")
    op.execute("DROP TYPE devicestatus")
    op.execute("DROP TYPE diagnostictype")
    op.execute("DROP TYPE diagnosticstatus")
