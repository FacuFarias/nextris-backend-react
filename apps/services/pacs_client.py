"""DICOMweb client shared by manual upload and persistent veterinary uploads."""
import os
import requests


def get_pacs_token():
    response=requests.post(os.getenv('PACS_KEYCLOAK_TOKEN_URL',os.getenv('VIEWER_KEYCLOAK_TOKEN_URL','')),
        data={'grant_type':'client_credentials','client_id':os.getenv('PACS_KEYCLOAK_CLIENT_ID',''),
              'client_secret':os.getenv('PACS_KEYCLOAK_CLIENT_SECRET','')}, timeout=15,
        verify=os.getenv('PACS_VERIFY_TLS','false').lower()=='true')
    response.raise_for_status()
    return response.json()['access_token']


class MultipartDicom:
    def __init__(self, path):
        self.path=path
        self.prefix=b'--NextRISDicom\r\nContent-Type: application/dicom\r\n\r\n'
        self.suffix=b'\r\n--NextRISDicom--\r\n'

    def __len__(self):
        return len(self.prefix)+self.path.stat().st_size+len(self.suffix)

    def __iter__(self):
        yield self.prefix
        with self.path.open('rb') as stream:
            while chunk:=stream.read(1024*1024): yield chunk
        yield self.suffix


def first_multipart_part(raw, content_type):
    """Body of a single-part multipart/related response, byte for byte."""
    if 'multipart/' not in content_type:
        return raw
    boundary=next((item.split('=',1)[1].strip().strip('"') for item in content_type.split(';') if item.strip().lower().startswith('boundary=')),None)
    if not boundary:
        raise RuntimeError('Respuesta DICOMweb sin boundary')
    delimiter=b'--'+boundary.encode()
    start=raw.index(delimiter)+len(delimiter)
    start=raw.index(b'\r\n\r\n',start)+4
    return raw[start:raw.index(b'\r\n'+delimiter,start)]


class PacsClient:
    PAGE=1000

    def __init__(self):
        self.base=os.environ['PACS_STOW_URL'].rstrip('/').removesuffix('/studies')
        self.verify=os.getenv('PACS_VERIFY_TLS','false').lower()=='true'
        self.token=get_pacs_token()

    def request(self, method, path, *, headers=None, **kwargs):
        """Long transfers outlive the service-account token, so a 401 renews it once."""
        for attempt in (1,2):
            response=requests.request(method,self.base+path,headers={'Authorization':'Bearer '+self.token,**(headers or {})},
                                      verify=self.verify,**kwargs)
            if response.status_code!=401 or attempt==2:
                return response
            self.token=get_pacs_token()

    def instances(self, study_uid):
        """Every instance of a study, requesting only the fields needed, across QIDO result pages."""
        rows=[];offset=0
        while True:
            response=self.request('GET','/studies/'+study_uid+'/instances',timeout=60,headers={'Accept':'application/dicom+json'},
                params={'includefield':['00080018','00100020'],'limit':self.PAGE,'offset':offset})
            if response.status_code in (204,404):
                return rows
            response.raise_for_status()
            page=response.json();rows+=page;offset+=len(page)
            if len(page)<self.PAGE:
                return rows

    def retrieve(self, study, series, sop):
        # Per-instance retrieval detects UID/content collisions, keeping the stored transfer syntax. Never modifies PACS.
        response=self.request('GET',f'/studies/{study}/series/{series}/instances/{sop}',timeout=120,
            headers={'Accept':'multipart/related; type="application/dicom"; transfer-syntax=*'})
        response.raise_for_status()
        return first_multipart_part(response.content,response.headers.get('Content-Type',''))

    def frame_available(self, study, series, sop):
        response=self.request('GET',f'/studies/{study}/series/{series}/instances/{sop}/frames/1',timeout=60,stream=True,
            headers={'Accept':'multipart/related; type="application/octet-stream"; transfer-syntax=*'})
        try:
            if response.status_code==404:
                return False
            response.raise_for_status()
            return bool(next(response.iter_content(1024),b''))
        finally:
            response.close()

    def store(self, path):
        response=self.request('POST','/studies',data=MultipartDicom(path),timeout=120,headers={'Accept':'application/dicom+json',
            'Content-Type':'multipart/related; type="application/dicom"; boundary=NextRISDicom'})
        if response.status_code not in (200,202):
            raise RuntimeError('PACS rechazó la instancia (HTTP '+str(response.status_code)+')')
        if response.content and response.json().get('00081198',{}).get('Value'):
            raise RuntimeError('PACS informó instancias fallidas en STOW-RS')
