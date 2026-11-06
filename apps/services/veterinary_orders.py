"""Shared order creation for admission and confirmed uploads. Caller owns the transaction."""
import uuid
from datetime import datetime
from psycopg2.extras import Json
from pydicom.uid import generate_uid
from apps.services import veterinary as vet


def create_order(cursor, patient_id, data, *, key=None, accession=None, study_uid=None, context=None):
    study=data.get('study_type_id') or None
    protocol=data.get('protocol_id') or None
    context=context or vet.protocol_context(cursor, patient_id, protocol, study)
    if not study: raise vet.VeterinaryError('Seleccione el tipo de estudio')
    key=key or str(uuid.uuid4())
    accession=accession or 'VT'+uuid.uuid4().hex[:12].upper()
    study_uid=study_uid or generate_uid()
    cursor.execute('''INSERT INTO nextris.tbexamination(guid,idpatient,studytype_id,localacc,admisionnumber,studyinstanceuid,
        history,clinicalquestion,requestingphysician_name,"w-order",veterinary_protocol_id,veterinary_context)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s)''',
        (key,patient_id,study,accession,accession,study_uid,data.get('history',''),data.get('clinical_question',''),
         data.get('requesting_veterinarian',''),protocol,Json(context)))
    cursor.execute('INSERT INTO nextris.tbreport(guid,idexamination,idpatient) VALUES(%s,%s,%s)',(str(uuid.uuid4()),key,patient_id))
    if data.get('scheduled_start'):
        try:
            start=datetime.fromisoformat(data['scheduled_start']);end=datetime.fromisoformat(data['scheduled_end'])
            if end<=start: raise ValueError()
        except (ValueError,TypeError,KeyError): raise vet.VeterinaryError('Horario de turno inválido')
        cursor.execute('''INSERT INTO nextris.tbagendaevents(guid,comienzo,fin,idpatient,idexam,title,medico_solicitante,
            veterinary_protocol_id,veterinary_context) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (str(uuid.uuid4()),start,end,patient_id,key,context['name'],data.get('requesting_veterinarian',''),protocol,Json(context)))
    return {'guid':key,'accession_number':accession,'study_instance_uid':study_uid,'veterinary_context':context}
