from pathlib import Path
import json,sys,uuid
import os
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_veterinary_api import VeterinaryApiTests as T
T.setUpClass()
case=T();a=case.new_animal(name='Synthetic Browser Animal',veterinary={'species_id':T.dog,'weight_kg':8.1})
party=T.call('POST','/veterinary/responsibles',{'name':'Synthetic Browser Responsible','kind':'person','email':'browser@example.invalid'}).json()['data']
r=T.call('POST','/veterinary/patients/'+a['guid']+'/responsibles',{'responsible_id':party['id'],'role':'owner','is_primary':True,'portal_authorized':True});assert r.status_code==201,r.text
username='browser-responsible-'+uuid.uuid4().hex[:10]
owner=T.call('POST','/veterinary/responsibles/'+party['id']+'/account',{'username':username}).json()['data']
r=T.call('POST','/veterinary/patients/'+a['guid']+'/orders',{'study_type_id':T.study_type});assert r.status_code==201,r.text
exam=r.json()['data']['guid']
r=T.call('PUT','/examinations/'+exam+'/report',{'study_reason':'Synthetic browser reason','content':'Synthetic browser veterinary findings','conclusion':'Synthetic browser conclusion'});assert r.status_code==200,r.text
r=T.call('POST','/reports/'+exam+'/sign',{});assert r.status_code==200,r.text
p=Path(os.environ['VETERINARY_BROWSER_FIXTURES']);p.write_text(json.dumps({'staff':{'username':T.username,'password':T.password},'responsible':{'username':owner['username'],'password':owner['initial_password']},'animal':a,'study_type':T.study_type,'exam':exam}));p.chmod(0o600)
T.tearDownClass()
print('Synthetic browser fixtures prepared in the disposable database.')
