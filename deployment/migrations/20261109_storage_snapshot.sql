-- Hourly disk snapshots for Gestión → Almacenamiento; the PACS catalog cannot rebuild free-space history.
CREATE TABLE IF NOT EXISTS nextris.tb_storage_snapshot (
    id bigserial PRIMARY KEY,
    taken_at timestamptz NOT NULL DEFAULT now(),
    disk_total bigint NOT NULL,
    disk_free bigint NOT NULL,
    local_bytes bigint NOT NULL,
    b2_bytes bigint NOT NULL,
    b2_objects bigint NOT NULL,
    pending_b2_objects bigint NOT NULL,
    pending_b2_bytes bigint NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_storage_snapshot_taken_at ON nextris.tb_storage_snapshot (taken_at);
