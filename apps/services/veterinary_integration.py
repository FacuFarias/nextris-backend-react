"""Veterinary DICOM metadata and a disabled-by-default DCM4CHEE MWL adapter."""
import os
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from apps.services.veterinary import VeterinaryError


def read_veterinary_metadata(ds):
    fields={'species':'PatientSpeciesDescription','breed':'PatientBreedDescription','reproductive_status':'PatientSexNeutered',
            'responsible':'ResponsiblePerson','responsible_role':'ResponsiblePersonRole','responsible_organization':'ResponsibleOrganization',
            'weight_kg':'PatientWeight'}
    return {key:str(getattr(ds,tag,'')) for key,tag in fields.items() if getattr(ds,tag,None) is not None}


def prepare_manual_upload(file, patient_id, exam_id, confirmed, actor):
    """Validate explicit identity reconciliation before the existing STOW/upload pipeline runs."""
    import io
    from pathlib import Path
    from datetime import datetime, timezone
    import uuid
    import pydicom
    from psycopg2.extras import RealDictCursor
    from apps.services import veterinary as vet
    if not patient_id or not exam_id:
        raise VeterinaryError('Seleccione el animal y la orden para la carga manual')
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as cursor:
        context=vet.patient_context(cursor,patient_id)
        cursor.execute('SELECT localacc FROM nextris.tbexamination WHERE guid=%s AND idpatient=%s',(str(exam_id),str(patient_id)))
        order=cursor.fetchone()
        if not context or not order:raise VeterinaryError('Animal u orden no encontrados',404)
    try:
        raw=file.read();file.stream.seek(0)
        dataset=pydicom.dcmread(io.BytesIO(raw))
        if not getattr(dataset,'SOPInstanceUID',None) or not getattr(dataset,'StudyInstanceUID',None):
            raise ValueError()
        from pydicom.uid import UID
        if not UID(str(dataset.SOPInstanceUID)).is_valid or not UID(str(dataset.StudyInstanceUID)).is_valid:
            raise ValueError()
    except Exception:
        raise VeterinaryError('El archivo no contiene un estudio DICOM válido')
    mismatch=str(getattr(dataset,'PatientID','')).strip()!=context['patientid'] or str(getattr(dataset,'AccessionNumber','')).strip()!=order['localacc']
    for attribute,key in [('PatientName','name'),('PatientSpeciesDescription','species_name'),('PatientBreedDescription','breed_name')]:
        supplied=str(getattr(dataset,attribute,'')).strip()
        if supplied and context.get(key) and supplied.casefold()!=str(context[key]).casefold():mismatch=True
    with vet.database() as connection,connection.cursor() as cursor:
        cursor.execute('''SELECT 1 FROM nextris.tbexamination WHERE studyinstanceuid=%s AND idpatient<>%s LIMIT 1''',(str(dataset.StudyInstanceUID),str(patient_id)))
        if cursor.fetchone():raise VeterinaryError('El estudio ya está vinculado a otro animal; no se puede reasignar mediante una carga',409)
    if mismatch and not confirmed:
        raise VeterinaryError('La identidad o el acceso DICOM no coinciden. Confirme explícitamente la conciliación con el animal y la orden seleccionados.',409)
    if mismatch:
        original=Dataset()
        for key in ('PatientID','PatientName','AccessionNumber','IssuerOfPatientID','PatientSpeciesDescription','PatientBreedDescription'):
            if key in dataset:original.add(dataset.data_element(key))
        audit=Dataset();audit.SourceOfPreviousValues='Original uploaded file'
        audit.AttributeModificationDateTime=datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S.%f%z')
        audit.ModifyingSystem='CDIVET RIS';audit.ReasonForTheAttributeModification='COERCE'
        audit.ModifiedAttributesSequence=Sequence([original])
        previous=list(getattr(dataset,'OriginalAttributesSequence',[]));dataset.OriginalAttributesSequence=Sequence(previous+[audit])
    metadata=veterinary_dataset(context,accession=order['localacc'],study_uid=str(dataset.StudyInstanceUID))
    identity={'PatientID','PatientName','AccessionNumber','IssuerOfPatientID'}
    for element in metadata:
        if element.keyword in ('ScheduledProcedureStepSequence','StudyInstanceUID'):
            continue
        existing=dataset.get(element.tag)
        if element.keyword in identity or not existing or existing.is_empty or (mismatch and element.keyword in ('PatientSpeciesDescription','PatientBreedDescription')):
            dataset[element.tag]=element
    originals=Path(__file__).resolve().parents[2]/'uploads_dicom'/'originals'
    originals.mkdir(parents=True,exist_ok=True)
    original_path=originals/(uuid.uuid4().hex+'.dcm')
    original_path.write_bytes(raw);original_path.chmod(0o600)
    import json
    import hashlib
    provenance=original_path.with_suffix('.json')
    provenance.write_text(json.dumps({'actor_id':str(actor),'patient_id':str(patient_id),'exam_id':str(exam_id),
        'sha256':hashlib.sha256(raw).hexdigest(),'identity_reconciled':mismatch,'received_at':datetime.now(timezone.utc).isoformat()},indent=2)+'\n')
    provenance.chmod(0o600)
    result=io.BytesIO();dataset.save_as(result,write_like_original=False);result.seek(0);file.stream=result


def veterinary_dataset(context, *, accession, study_uid, modality='', scheduled_step_id=''):
    ds=Dataset();ds.SpecificCharacterSet='ISO_IR 192'
    ds.PatientID=context['patientid'];ds.PatientName=context['name']
    if os.getenv('NEXTRIS_PATIENT_ID_ISSUER'):ds.IssuerOfPatientID=os.environ['NEXTRIS_PATIENT_ID_ISSUER']
    ds.PatientBirthDate=(context.get('birthdate') or '').replace('-','')
    ds.PatientSex=context.get('gender') if context.get('gender') in ('M','F','O') else ''
    if not context.get('species_name'):
        raise VeterinaryError('Defina la especie antes de generar una orden DICOM')
    ds.PatientSpeciesDescription=context['species_name'];ds.PatientBreedDescription=context.get('breed_name') or ''
    ds.PatientBreedCodeSequence=Sequence([]);ds.BreedRegistrationSequence=Sequence([])
    for prefix,attribute in [('species','PatientSpeciesCodeSequence'),('breed','PatientBreedCodeSequence')]:
        if context.get(prefix+'_code_value') and context.get(prefix+'_coding_scheme'):
            coded=Dataset();coded.CodeValue=context[prefix+'_code_value'];coded.CodingSchemeDesignator=context[prefix+'_coding_scheme'];coded.CodeMeaning=context[prefix+'_name']
            setattr(ds,attribute,Sequence([coded]))
    ds.PatientSexNeutered={'neutered':'ALTERED','intact':'UNALTERED'}.get(context.get('reproductive_status'),'')
    if context.get('weight_kg') is not None:ds.PatientWeight=str(context['weight_kg'])
    responsible=next((r for r in context.get('responsibles',[]) if r.get('is_primary')),None)
    ds.ResponsiblePerson=responsible['name'] if responsible and responsible.get('kind')=='person' else ''
    if ds.ResponsiblePerson:ds.ResponsiblePersonRole={'owner':'OWNER','guardian':'GUARDIAN','custodian':'CUSTODIAN','veterinarian':'VETERINARIAN'}[responsible['role']]
    ds.ResponsibleOrganization=(responsible.get('organization') or (responsible['name'] if responsible.get('kind')=='organization' else '')) if responsible else ''
    ds.AccessionNumber=accession;ds.StudyInstanceUID=study_uid
    sps=Dataset();sps.Modality=modality;sps.ScheduledProcedureStepID=scheduled_step_id or accession
    ds.ScheduledProcedureStepSequence=Sequence([sps])
    return ds


def send_veterinary_worklist(dataset, *, session, base_url, aet, access_token):
    if os.getenv('NEXTRIS_MWL_ENABLED','false').lower()!='true':
        raise VeterinaryError('MWL desactivada: esta instalación utiliza carga manual',409)
    if not aet or not base_url:
        raise VeterinaryError('Configure el destino MWL antes de habilitar el envío')
    from urllib.parse import quote
    response=session.post(base_url.rstrip('/')+'/aets/'+quote(aet,safe='')+'/rs/mwlitems',
        json=dataset.to_json_dict(),headers={'Authorization':'Bearer '+access_token,'Content-Type':'application/dicom+json'},timeout=15)
    response.raise_for_status()
    return True
