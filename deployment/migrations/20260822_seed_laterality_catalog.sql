-- Catálogo de lateralidad utilizado por la confirmación de estudios.
INSERT INTO nextris.islaterality (guid, description)
VALUES
    ('7b2f0a7e-4cb0-4c54-9e32-000000000001', 'IZQUIERDA'),
    ('7b2f0a7e-4cb0-4c54-9e32-000000000002', 'DERECHA'),
    ('7b2f0a7e-4cb0-4c54-9e32-000000000003', 'BILATERAL')
ON CONFLICT (guid) DO UPDATE
SET description = EXCLUDED.description;
