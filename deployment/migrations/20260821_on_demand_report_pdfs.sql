-- Report PDFs are rendered from tbreport at request time.
-- Existing filesystem cleanup is performed by the deployment procedure after
-- validating that signed reports can be rendered from the database.
ALTER TABLE nextris.tbreport
    DROP COLUMN IF EXISTS pdfpath;
