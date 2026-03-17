from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'cc475c0efd63'
down_revision = '9170f1073bb2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('route_tasks', sa.Column('locations', sa.JSON(), nullable=True))
    op.add_column('route_tasks', sa.Column('segment_modes', sa.JSON(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE route_tasks
            SET locations = CASE
                WHEN transfer_address_id IS NULL THEN json_build_array(start_address_id, destination_address_id)
                ELSE json_build_array(start_address_id, transfer_address_id, destination_address_id)
            END
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE route_tasks
            SET segment_modes = CASE
                WHEN transfer_address_id IS NULL THEN json_build_array(mode::text)
                WHEN mode::text = 'mixed' THEN CASE
                    WHEN drive_part::text = 'second' THEN json_build_array('transit', 'drive')
                    ELSE json_build_array('drive', 'transit')
                END
                ELSE json_build_array(mode::text, mode::text)
            END
            """
        )
    )

    op.alter_column('route_tasks', 'locations', existing_type=sa.JSON(), nullable=False)
    op.alter_column('route_tasks', 'segment_modes', existing_type=sa.JSON(), nullable=False)

    op.drop_constraint('route_tasks_start_address_id_fkey', 'route_tasks', type_='foreignkey')
    op.drop_constraint('route_tasks_destination_address_id_fkey', 'route_tasks', type_='foreignkey')
    op.drop_constraint('route_tasks_transfer_address_id_fkey', 'route_tasks', type_='foreignkey')
    op.drop_column('route_tasks', 'mode')
    op.drop_column('route_tasks', 'start_address_id')
    op.drop_column('route_tasks', 'transfer_address_id')
    op.drop_column('route_tasks', 'destination_address_id')
    op.drop_column('route_tasks', 'drive_part')


def downgrade():
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'taskmode') THEN
                CREATE TYPE taskmode AS ENUM ('drive', 'transit', 'mixed');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'drivepart') THEN
                CREATE TYPE drivepart AS ENUM ('first', 'second');
            END IF;
        END $$;
        """
    )

    op.add_column('route_tasks', sa.Column('drive_part', postgresql.ENUM('first', 'second', name='drivepart'), autoincrement=False, nullable=True))
    op.add_column('route_tasks', sa.Column('destination_address_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('route_tasks', sa.Column('transfer_address_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('route_tasks', sa.Column('start_address_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('route_tasks', sa.Column('mode', postgresql.ENUM('drive', 'transit', 'mixed', name='taskmode'), autoincrement=False, nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE route_tasks
            SET
                start_address_id = NULLIF(locations->>0, '')::integer,
                transfer_address_id = CASE WHEN json_array_length(locations) >= 3 THEN NULLIF(locations->>1, '')::integer ELSE NULL END,
                destination_address_id = CASE
                    WHEN json_array_length(locations) >= 2 THEN NULLIF(locations->>(json_array_length(locations) - 1), '')::integer
                    ELSE NULL
                END,
                mode = CASE
                    WHEN json_array_length(segment_modes) = 1 THEN (segment_modes->>0)::taskmode
                    WHEN json_array_length(segment_modes) = 2
                         AND segment_modes->>0 <> segment_modes->>1
                         AND ((segment_modes->>0 = 'drive' AND segment_modes->>1 = 'transit')
                              OR (segment_modes->>0 = 'transit' AND segment_modes->>1 = 'drive'))
                        THEN 'mixed'::taskmode
                    WHEN json_array_length(segment_modes) >= 1 THEN (segment_modes->>0)::taskmode
                    ELSE 'drive'::taskmode
                END,
                drive_part = CASE
                    WHEN json_array_length(segment_modes) = 2
                         AND segment_modes->>0 = 'drive'
                         AND segment_modes->>1 = 'transit'
                        THEN 'first'::drivepart
                    WHEN json_array_length(segment_modes) = 2
                         AND segment_modes->>0 = 'transit'
                         AND segment_modes->>1 = 'drive'
                        THEN 'second'::drivepart
                    ELSE NULL
                END
            """
        )
    )

    op.alter_column('route_tasks', 'start_address_id', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('route_tasks', 'destination_address_id', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('route_tasks', 'mode', existing_type=postgresql.ENUM('drive', 'transit', 'mixed', name='taskmode'), nullable=False)

    op.create_foreign_key('route_tasks_transfer_address_id_fkey', 'route_tasks', 'addresses', ['transfer_address_id'], ['id'])
    op.create_foreign_key('route_tasks_destination_address_id_fkey', 'route_tasks', 'addresses', ['destination_address_id'], ['id'])
    op.create_foreign_key('route_tasks_start_address_id_fkey', 'route_tasks', 'addresses', ['start_address_id'], ['id'])
    op.drop_column('route_tasks', 'segment_modes')
    op.drop_column('route_tasks', 'locations')
