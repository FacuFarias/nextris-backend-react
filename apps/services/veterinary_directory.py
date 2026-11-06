"""Paginated veterinary directories; filter and sort across all matching records."""
from apps.services import veterinary as vet


def directory(cursor, source, params, *, columns, search_columns, exact, default_sort='name'):
    try:
        page = max(1, int(params.get('page', 1)))
        per_page = min(100, max(1, int(params.get('per_page', 10))))
    except (ValueError, TypeError):
        raise vet.VeterinaryError('Paginación inválida')
    conditions, values = [], []
    search = params.get('search', '').strip()
    if search:
        conditions.append('(' + ' OR '.join(column + ' ILIKE %s' for column in search_columns) + ')')
        values.extend(['%' + search + '%'] * len(search_columns))
    for name, column in columns.items():
        value = params.get('filter_' + name, '').strip()
        if value:
            conditions.append('CAST(' + column + ' AS text) ILIKE %s')
            values.append('%' + value + '%')
    for name, column in exact.items():
        value = params.get(name, '').strip()
        if value:
            conditions.append('CAST(' + column + ' AS text) = %s')
            values.append(value)
    if 'responsible_names' in columns and params.get('responsible_status') in ('linked', 'pending'):
        conditions.append("responsible_names " + ("<> ''" if params['responsible_status']=='linked' else "= ''"))
    where = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
    prefix = 'WITH directory AS (' + source + ') '
    cursor.execute(prefix + 'SELECT count(*) AS total FROM directory' + where, values)
    total = cursor.fetchone()['total']
    order = columns.get(params.get('sort_column'), columns[default_sort])
    direction = 'DESC' if params.get('sort_direction')=='desc' else 'ASC'
    cursor.execute(prefix + 'SELECT * FROM directory' + where + ' ORDER BY ' + order + ' ' + direction +
                   ' NULLS LAST, id LIMIT %s OFFSET %s', values + [per_page, (page-1)*per_page])
    return {'data': cursor.fetchall(), 'page': page, 'per_page': per_page, 'total': total}


def animal_directory(cursor, params):
    source = """SELECT p.guid AS id, p.patientid, p.name, p.sexcode AS gender,
        p.species_id, p.breed_id, coalesce(s.name,'') AS species_name, coalesce(b.name,'') AS breed_name,
        coalesce((SELECT string_agg(r.name, ', ' ORDER BY r.name) FROM nextris.patient_responsibility pr
            JOIN nextris.responsible_party r ON r.id=pr.responsible_id WHERE pr.patient_id=p.guid
            AND pr.valid_from<=now() AND (pr.valid_to IS NULL OR pr.valid_to>now())), '') AS responsible_names,
        coalesce((SELECT string_agg(r.document, ' ') FROM nextris.patient_responsibility pr
            JOIN nextris.responsible_party r ON r.id=pr.responsible_id WHERE pr.patient_id=p.guid
            AND pr.valid_from<=now() AND (pr.valid_to IS NULL OR pr.valid_to>now())), '') AS responsible_documents,
        (SELECT weight_kg FROM nextris.patient_clinical_entry ce WHERE ce.patient_id=p.guid
            AND ce.weight_kg IS NOT NULL ORDER BY ce.recorded_at DESC,ce.created_at DESC,ce.id DESC LIMIT 1) AS weight_kg,
        (SELECT count(*) FROM nextris.tbexamination e WHERE e.idpatient=p.guid) AS study_count
        FROM nextris.datapatient p LEFT JOIN nextris.veterinary_species s ON s.id=p.species_id
        LEFT JOIN nextris.veterinary_breed b ON b.id=p.breed_id WHERE p.patient_kind='animal'"""
    names = ['patientid','name','gender','species_name','breed_name','responsible_names','weight_kg','study_count']
    result = directory(cursor, source, params, columns={key:key for key in names},
        search_columns=['name','patientid','responsible_names','responsible_documents'],
        exact={key:key for key in ['species_id','breed_id','gender']})
    result['data'] = [vet.animal_dict(cursor, row['id']) for row in result['data']]
    return result


def responsible_directory(cursor, params):
    names = ['name','document','email','phone','kind_label','status_label']
    source = """SELECT r.*, CASE WHEN kind='person' THEN 'Persona' ELSE 'Organización' END AS kind_label,
        CASE WHEN is_active THEN 'Activo' ELSE 'Inactivo' END AS status_label
        FROM nextris.responsible_party r"""
    return directory(cursor, source, params, columns={key:key for key in names},
        search_columns=['name','document','email','phone'],exact={'kind':'kind','is_active':'is_active'})
