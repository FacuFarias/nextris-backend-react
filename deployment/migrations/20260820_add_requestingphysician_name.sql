-- Agregar columna requestingphysician_name a nextris.tbexamination
-- para almacenar el nombre del médico solicitante (ref_doctor)
ALTER TABLE nextris.tbexamination
    ADD COLUMN IF NOT EXISTS requestingphysician_name VARCHAR(255);
