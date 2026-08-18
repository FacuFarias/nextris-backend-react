-- Marca si un estudio tiene una orden recibida por la API.
-- Las imágenes creadas automáticamente por PACS quedan en 0 hasta que
-- llegue la orden correspondiente.
ALTER TABLE nextris.tbexamination
    ADD COLUMN IF NOT EXISTS "w-order" INTEGER NOT NULL DEFAULT 0;

UPDATE nextris.tbexamination
SET "w-order" = 0
WHERE "w-order" IS NULL;

COMMENT ON COLUMN nextris.tbexamination."w-order"
    IS '1 = orden recibida por API; 0 = sin orden API';
