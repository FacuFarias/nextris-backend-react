"""Explicit RIS assignment of PACS studies to animals, preserving PACS originals."""
import uuid
from psycopg2.extras import Json, RealDictCursor
from apps.services import veterinary as vet


def reassign_study(data, actor):
    if not isinstance(data, dict):
        raise vet.VeterinaryError('Se requiere un objeto JSON')
    if data.get('new_patient') is not None:
        raise vet.VeterinaryError('Registre un animal mediante el alta veterinaria antes de seleccionarlo')
    if data.get('modify_dicom') not in (None, False):
        raise vet.VeterinaryError('La reasignación veterinaria conserva los originales DICOM')
    if data.get('confirm_identity') is not True:
        raise vet.VeterinaryError('Confirme que las imágenes corresponden al animal seleccionado',409)
    animal_id = vet.identifier(data.get('animal_guid') or data.get('patient_guid'))
    try:
        if isinstance(data.get('study_pk'), bool):
            raise ValueError()
        study_pk = int(data.get('study_pk'))
        if study_pk < 1:
            raise ValueError()
    except (TypeError, ValueError):
        raise vet.VeterinaryError('Seleccione un estudio válido')

    with vet.database() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute('''SELECT s.pk,s.study_iuid,s.accession_no FROM public.study s
            JOIN nextris.available_pacs_study a ON a.pk=s.pk WHERE s.pk=%s FOR UPDATE OF s''', (study_pk,))
        study = cursor.fetchone()
        if not study:
            raise vet.VeterinaryError('Estudio no encontrado o sin imágenes disponibles',404)
        animal = vet.animal(cursor, animal_id, lock=True)
        uid = study['study_iuid']
        cursor.execute('''SELECT e.* FROM nextris.tbexamination e WHERE EXISTS (
            SELECT 1 FROM nextris.examination_pacs_study ep
            WHERE ep.examination_guid=e.guid AND ep.study_iuid=%s) FOR UPDATE OF e''', (uid,))
        orders = cursor.fetchall()
        if len(orders) > 1:
            raise vet.VeterinaryError('El estudio está asociado a varias órdenes; revise sus vínculos antes de reasignarlo',409)
        order = orders[0] if orders else None
        if order and str(order['idpatient']) == animal_id:
            cursor.execute('UPDATE nextris.tbexamination SET isimage=1 WHERE guid=%s AND COALESCE(isimage,0)<>1',
                           (order['guid'],))
            return {'study_pk':study_pk,'animal_guid':animal_id,'animal_id':animal['patientid'],
                    'examination_guid':order['guid']}
        if order:
            cursor.execute('SELECT wassaved FROM nextris.tbreport WHERE idexamination=%s FOR UPDATE', (order['guid'],))
            if order['isreported'] or any(row['wassaved'] for row in cursor.fetchall()):
                raise vet.VeterinaryError('No se puede cambiar el animal de una orden con un informe guardado o firmado',409)
            cursor.execute('''SELECT 1 FROM nextris.examination_pacs_study ep
                JOIN nextris.available_pacs_study s ON s.study_iuid=ep.study_iuid
                WHERE ep.examination_guid=%s AND ep.study_iuid<>%s LIMIT 1''', (order['guid'],uid))
            if cursor.fetchone():
                raise vet.VeterinaryError('La orden contiene otros estudios con imágenes; revise sus vínculos antes de reasignarla',409)
            context = vet.protocol_context(cursor,animal_id,order['veterinary_protocol_id'],order['studytype_id'])
            exam_id = order['guid']
            original_uid = order['studyinstanceuid']
            cursor.execute('''UPDATE nextris.tbexamination SET idpatient=%s,studyinstanceuid=%s,
                isimage=1,veterinary_context=%s WHERE guid=%s''', (animal_id,uid,Json(context),exam_id))
            cursor.execute('UPDATE nextris.tbreport SET idpatient=%s WHERE idexamination=%s', (animal_id,exam_id))
        else:
            context = vet.protocol_context(cursor,animal_id)
            exam_id = str(uuid.uuid4())
            original_uid = uid
            accession = study['accession_no'] or 'VT'+uuid.uuid4().hex[:12].upper()
            cursor.execute('''INSERT INTO nextris.tbexamination
                (guid,idpatient,localacc,studyinstanceuid,status,isexecuted,isreported,isimage,createdon,"w-order",veterinary_context)
                VALUES(%s,%s,%s,%s,'Scheduled',0,0,1,NOW(),0,%s)''',
                (exam_id,animal_id,accession,uid,Json(context)))
            cursor.execute('INSERT INTO nextris.tbreport(guid,idexamination,idpatient,wassaved) VALUES(%s,%s,%s,false)',
                           (str(uuid.uuid4()),exam_id,animal_id))
        cursor.execute('''UPDATE nextris.tbpacs_study_link SET link_status='unlinked',unlinked_at=NOW(),
            updated_at=NOW(),unlinked_reason='Reasignación veterinaria confirmada'
            WHERE link_status='linked' AND (pacs_study_pk=%s OR pacs_study_iuid=%s OR order_guid=%s)''',
            (study_pk,uid,exam_id))
        cursor.execute('SELECT username FROM nextris.tbuser WHERE guid=%s', (str(actor),))
        user = cursor.fetchone()
        cursor.execute('''INSERT INTO nextris.tbpacs_study_link
            (pacs_study_pk,pacs_study_iuid,order_guid,order_study_uuid,source,linked_by_user_guid,linked_by_username)
            VALUES(%s,%s,%s,%s,'reconcile',%s,%s)''',
            (study_pk,uid,exam_id,original_uid,str(actor),user['username'] if user else None))
        cursor.execute('''UPDATE nextris.tbviewer_share_link SET revoked=true,revoked_at=NOW()
            WHERE study_iuid=%s AND NOT revoked''', (uid,))
        cursor.execute('''UPDATE nextris.tb_viewer_handoff SET expires_at=LEAST(expires_at,NOW())
            WHERE study_iuid=%s AND consumed_at IS NULL''', (uid,))
        return {'study_pk':study_pk,'animal_guid':animal_id,'animal_id':animal['patientid'],'examination_guid':exam_id}
