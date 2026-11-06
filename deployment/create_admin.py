"""Create an initial administrator with a prompted password; never reset an existing user."""
import argparse
from getpass import getpass
from pathlib import Path
import sys
import uuid
import psycopg2
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username', required=True)
    parser.add_argument('--email', default='')
    args = parser.parse_args()
    if not args.username.strip():
        parser.error('El usuario no puede estar vacío')
    password = getpass('Contraseña inicial: ')
    if not password or password != getpass('Repetir contraseña: '):
        parser.error('Las contraseñas deben coincidir y no estar vacías')
    load_dotenv(ROOT / '.env')
    from apps.home.services.config_service import ConfigService
    with psycopg2.connect(**ConfigService.get_db_config()) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1 FROM nextris.tbuser WHERE username=%s',(args.username.strip(),))
            if cursor.fetchone():
                parser.error('El usuario ya existe; no se modificó su contraseña')
            cursor.execute("SELECT guid FROM nextris.isrole WHERE lower(description)='sysadmin' LIMIT 1")
            role = cursor.fetchone()
            if not role:
                parser.error('Ejecute primero las migraciones de instalación')
            cursor.execute('''INSERT INTO nextris.tbuser(guid,username,password,mail,idrole,isactive,first_login)
                VALUES(%s,%s,%s,%s,%s,1,1)''',
                (str(uuid.uuid4()),args.username.strip(),generate_password_hash(password),args.email,role[0]))
    print('Administrador creado. Deberá cambiar su contraseña en el primer acceso.')


if __name__ == '__main__':
    main()
