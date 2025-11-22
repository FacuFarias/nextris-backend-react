from flask import render_template, redirect, request, url_for, session, jsonify
from flask_login import (
    current_user,
    login_user,
    logout_user
)


from apps import db, login_manager
import psycopg2
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'home')))
try:
    from apps.home.routes import config
except ImportError:
    # Si no se puede importar, define config aquí o lanza error
    config = None
from apps.authentication import blueprint
from apps.authentication.forms import LoginForm, CreateAccountForm
from apps.authentication.models import Users, PatientUser
from werkzeug.security import generate_password_hash, check_password_hash
from apps.authentication.util import verify_pass



@blueprint.route('/')
def route_default():
    return redirect(url_for('authentication_blueprint.login'))

# Login & Registration


@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm(request.form)
    if 'login' in request.form:

        # read form data
        username = request.form['username']
        password = request.form['password']
        user_type = request.form.get('user_type')  # 'patient' si es paciente, None si es personal
       
        print(f"[LOGIN] Username: '{username}', User type: '{user_type}'")
        
        if user_type == 'patient':
            # Login como paciente - consultar tbuser_patient
            return login_patient(username, password, login_form)
        else:
            # Login como personal - consultar tbuser (comportamiento original)
            return login_staff(username, password, login_form)

    if not current_user.is_authenticated:
        return render_template('accounts/login.html',
                               form=login_form)
    return redirect(url_for('home_blueprint.index'))


def login_staff(username, password, login_form):
    """Login para personal médico usando tbuser"""
    # Locate user - Solo usuarios activos
    user = Users.query.filter_by(username=username, is_active=1).first()

    # Buscar el guid de tbuser según el username usando psycopg2 y config
    user_guid = None
    print(f"[LOGIN STAFF] Username recibido: '{username}'")
    try:
        if config is None:
            raise Exception("No se pudo importar config para la conexión a PostgreSQL")
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        # Buscar el guid sin restricciones primero para debug
        cursor.execute("SELECT guid, isactive, password FROM nextris.tbuser WHERE username = %s", (username,))
        debug_row = cursor.fetchone()
        print(f"[LOGIN STAFF DEBUG] Usuario en nextris.tbuser: {debug_row}")
        
        # Ahora buscar con las restricciones normales (isactive puede ser boolean o bit)
        cursor.execute("SELECT guid FROM nextris.tbuser WHERE username = %s AND isactive = true", (username,))
        row = cursor.fetchone()
        print(f"[LOGIN STAFF] Resultado de la query guid con isactive=true: {row}")
        if row:
            user_guid = row[0]
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"[LOGIN STAFF ERROR] Error buscando guid de tbuser: {e}")
        import traceback
        traceback.print_exc()
        user_guid = None

    # Debug: mostrar password recibido y hash guardado
    if user:
        print(f"[LOGIN STAFF DEBUG] Password recibido: '{password}'")
        print(f"[LOGIN STAFF DEBUG] Hash guardado: '{user.password}'")
        print(f"[LOGIN STAFF DEBUG] Usuario activo: {user.is_active}")
        
        # Verificar que el usuario esté activo y tenga contraseña
        if user.is_active == 1 and user.password:
            resultado_verificacion = verify_pass(password, user.password)
            print(f"[LOGIN STAFF DEBUG] Resultado verify_pass: {resultado_verificacion}")
        else:
            resultado_verificacion = False
            print(f"[LOGIN STAFF DEBUG] Usuario inactivo o sin contraseña")
    else:
        print("[LOGIN STAFF DEBUG] Usuario no encontrado")
        resultado_verificacion = False

    # Check the password - Solo si el usuario existe, está activo y tiene contraseña
    if user and user.is_active == 1 and user.password and verify_pass(password, user.password):
        login_user(user)
        # Guardar el guid de tbuser en la sesión para exponerlo al frontend
        session['user_guid'] = user_guid
        session['user_type'] = user.user_type
        session['username'] = username
        session['is_patient'] = False
        
        # Verificar si es la primera vez que inicia sesión
        session['requires_password_change'] = bool(user.first_login == 1)
        
        print("[LOGIN STAFF] tipo de usuario:",session['user_type'])
        print("[LOGIN STAFF] guid de tbuser:", session['user_guid'])
        print("[LOGIN STAFF] requiere cambio de contraseña:", session['requires_password_change'])
        
        return redirect(url_for('home_blueprint.index'))

    # Something (user or pass) is not ok
    return render_template('accounts/login.html',
                           msg='Usuario o contraseña incorrectos',
                           form=login_form)


def login_patient(username, password, login_form):
    """Login para pacientes usando tbuser_patient"""
    print("\n" + "="*60)
    print("[LOGIN PATIENT] INICIO DE LOGIN DE PACIENTE")
    print("="*60)
    print(f"[LOGIN PATIENT] Username paciente recibido: '{username}'")
    print(f"[LOGIN PATIENT] Tabla a consultar: nextris.tbuser_patient")
    
    try:
        if config is None:
            raise Exception("No se pudo importar config para la conexión a PostgreSQL")
        
        print(f"[LOGIN PATIENT] Conectando a PostgreSQL...")
        print(f"[LOGIN PATIENT] Config: {config}")
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        print(f"[LOGIN PATIENT] ✓ Conexión establecida exitosamente")
        
        # Buscar paciente en tbuser_patient
        # Nota: status parece ser texto ('Active', etc.) no numérico
        query = """
            SELECT guid, username, password, status, firstlogin, datapatient_id
            FROM nextris.tbuser_patient 
            WHERE username = %s
        """
        print(f"[LOGIN PATIENT] Ejecutando query:")
        print(f"[LOGIN PATIENT] {query}")
        print(f"[LOGIN PATIENT] Parámetros: username='{username}'")
        
        cursor.execute(query, (username,))
        
        patient_row = cursor.fetchone()
        print(f"[LOGIN PATIENT] Resultado de la query: {patient_row}")
        
        if patient_row:
            patient_guid, db_username, db_password, status, firstlogin, datapatient_id = patient_row
            
            print(f"[LOGIN PATIENT] ✓ Paciente encontrado:")
            print(f"[LOGIN PATIENT]   - GUID: {patient_guid}")
            print(f"[LOGIN PATIENT]   - Username: {db_username}")
            print(f"[LOGIN PATIENT]   - Status: {status} (tipo: {type(status).__name__})")
            print(f"[LOGIN PATIENT]   - FirstLogin: {firstlogin}")
            print(f"[LOGIN PATIENT]   - DataPatient ID: {datapatient_id}")
            print(f"[LOGIN PATIENT]   - Hash guardado: {db_password[:50]}..." if db_password else "None")
            
            # Verificar que el paciente esté activo
            # El status puede ser: 1 (activo), 'Active', True, etc. dependiendo del esquema
            is_active = False
            if isinstance(status, (int, bool)):
                is_active = bool(status)
            elif isinstance(status, str):
                is_active = status.lower() in ['active', '1', 'true', 'activo']
            
            print(f"[LOGIN PATIENT]   - Paciente activo: {is_active}")
            
            if not is_active:
                print(f"[LOGIN PATIENT] ✗ Paciente inactivo (status={status})")
                cursor.close()
                connection.close()
                print("="*60)
                print("[LOGIN PATIENT] LOGIN RECHAZADO - USUARIO INACTIVO")
                print("="*60 + "\n")
                return render_template('accounts/login.html',
                                     msg='Usuario inactivo',
                                     form=login_form)
            
            # Verificar contraseña
            print(f"[LOGIN PATIENT] Verificando contraseña...")
            if check_password_hash(db_password, password):
                print(f"[LOGIN PATIENT] ✓ Contraseña correcta")
                
                # Buscar datos adicionales del paciente en datapatient
                print(f"[LOGIN PATIENT] Buscando datos adicionales en nextris.datapatient...")
                cursor.execute("""
                    SELECT name, surname, email 
                    FROM nextris.datapatient 
                    WHERE guid = %s
                """, (datapatient_id,))
                
                patient_data = cursor.fetchone()
                print(f"[LOGIN PATIENT] Datos de datapatient: {patient_data}")
                
                patient_name = patient_data[0] if patient_data else username
                patient_surname = patient_data[1] if patient_data else ""
                patient_email = patient_data[2] if patient_data else ""
                
                print(f"[LOGIN PATIENT] Datos del paciente:")
                print(f"[LOGIN PATIENT]   - Nombre: {patient_name}")
                print(f"[LOGIN PATIENT]   - Apellido: {patient_surname}")
                print(f"[LOGIN PATIENT]   - Email: {patient_email}")
                
                # Crear objeto usuario para flask-login usando la clase importada
                print(f"[LOGIN PATIENT] Creando objeto usuario para flask-login...")
                
                patient_user = PatientUser(
                    patient_guid=patient_guid,
                    username=db_username,
                    name=patient_name,
                    surname=patient_surname,
                    email=patient_email,
                    is_active_flag=is_active,
                    first_login_flag=firstlogin
                )
                
                # Login usando flask-login
                print(f"[LOGIN PATIENT] Ejecutando login_user()...")
                login_user(patient_user, remember=True)
                print(f"[LOGIN PATIENT] ✓ login_user() ejecutado exitosamente")
                print(f"[LOGIN PATIENT] current_user.is_authenticated: {current_user.is_authenticated}")
                
                # Configurar sesión para pacientes
                print(f"[LOGIN PATIENT] Configurando sesión...")
                session['user_guid'] = patient_guid
                session['user_type'] = 'Paciente'
                session['username'] = db_username
                session['is_patient'] = True
                session['datapatient_id'] = datapatient_id
                session['requires_password_change'] = bool(firstlogin == 1)
                
                print(f"[LOGIN PATIENT] ✓ Sesión configurada:")
                print(f"[LOGIN PATIENT]   - user_guid: {session['user_guid']}")
                print(f"[LOGIN PATIENT]   - user_type: {session['user_type']}")
                print(f"[LOGIN PATIENT]   - username: {session['username']}")
                print(f"[LOGIN PATIENT]   - is_patient: {session['is_patient']}")
                print(f"[LOGIN PATIENT]   - datapatient_id: {session['datapatient_id']}")
                print(f"[LOGIN PATIENT]   - requires_password_change: {session['requires_password_change']}")
                
                cursor.close()
                connection.close()
                
                print(f"[LOGIN PATIENT] Redirigiendo a: home_blueprint.mis_estudios")
                print("="*60)
                print("[LOGIN PATIENT] LOGIN EXITOSO")
                print("="*60 + "\n")
                
                return redirect(url_for('home_blueprint.mis_estudios'))
            else:
                print(f"[LOGIN PATIENT] ✗ Contraseña incorrecta")
                print(f"[LOGIN PATIENT] Comparación de hash falló")
        else:
            print("[LOGIN PATIENT] ✗ Paciente no encontrado o inactivo en la base de datos")
            print("[LOGIN PATIENT] Posibles causas:")
            print("[LOGIN PATIENT]   1. Username incorrecto")
            print("[LOGIN PATIENT]   2. Paciente con status = 0 (inactivo)")
            print("[LOGIN PATIENT]   3. No existe en la tabla tbuser_patient")
        
        cursor.close()
        connection.close()
        print("="*60)
        print("[LOGIN PATIENT] LOGIN FALLIDO")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"[LOGIN PATIENT] ✗✗✗ ERROR CRÍTICO ✗✗✗")
        print(f"[LOGIN PATIENT] Tipo de error: {type(e).__name__}")
        print(f"[LOGIN PATIENT] Mensaje: {str(e)}")
        import traceback
        print(f"[LOGIN PATIENT] Traceback completo:")
        traceback.print_exc()
        print("="*60 + "\n")

    # Login fallido
    print(f"[LOGIN PATIENT] Renderizando página de login con mensaje de error")
    return render_template('accounts/login.html',
                           msg='Usuario o contraseña incorrectos',
                           form=login_form)



@blueprint.route('/register', methods=['GET', 'POST'])
def register():
    create_account_form = CreateAccountForm(request.form)
    if 'register' in request.form:

        username = request.form['username']
        email = request.form['email']
        typeofuser=request.form['user_type']
        # Check usename exists
        user = Users.query.filter_by(username=username).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Ya existe este usuario',
                                   success=False,
                                   form=create_account_form)

        # Check email exists
        user = Users.query.filter_by(email=email).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Ya se ha ocupado este mail',
                                   success=False,
                                   form=create_account_form)

        # else we can create the user
        user = Users(**request.form)
        db.session.add(user)
        db.session.commit()

        # Delete user from session
        logout_user()

        return render_template('accounts/register.html',
                               msg='Usuario creado exitosamente',
                               success=True,
                               form=create_account_form)

    else:
        return render_template('accounts/register.html', form=create_account_form)


@blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('authentication_blueprint.login')) 


@blueprint.route('/change-password', methods=['POST'])
def change_password():
    """Ruta para cambiar la contraseña del usuario (personal o paciente)"""
    
    # Verificar autenticación o si hay username en sesión (primer login)
    username_from_session = session.get('username')
    
    if not current_user.is_authenticated and not username_from_session:
        print(f"[CHANGE PASSWORD] ✗ Usuario no autenticado y sin username en sesión")
        return jsonify({'success': False, 'message': 'Usuario no autenticado'}), 401
    
    # Usar el username del current_user si está autenticado, sino de la sesión
    username = current_user.username if current_user.is_authenticated else username_from_session
    
    print(f"[CHANGE PASSWORD] Usuario: {username}")
    print(f"[CHANGE PASSWORD] current_user.is_authenticated: {current_user.is_authenticated}")
    print(f"[CHANGE PASSWORD] username_from_session: {username_from_session}")
    
    try:
        data = request.get_json()
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        # Validaciones
        if not new_password or not confirm_password:
            return jsonify({'success': False, 'message': 'Faltan campos requeridos'}), 400
        
        if new_password != confirm_password:
            return jsonify({'success': False, 'message': 'Las contraseñas no coinciden'}), 400
        
        if len(new_password) < 4:
            return jsonify({'success': False, 'message': 'La contraseña debe tener al menos 4 caracteres'}), 400
        
        if new_password == '1234':
            return jsonify({'success': False, 'message': 'No puedes usar la contraseña temporal'}), 400
        
        # Detectar si es paciente o personal
        is_patient = session.get('is_patient', False)
        
        print(f"[CHANGE PASSWORD] Es paciente: {is_patient}")
        
        # Actualizar contraseña en la base de datos usando PostgreSQL directo
        if config is None:
            raise Exception("No se pudo importar config para la conexión a PostgreSQL")
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Hash de la nueva contraseña
        hashed_password = generate_password_hash(new_password)
        
        if is_patient:
            # Actualizar contraseña en tbuser_patient
            print(f"[CHANGE PASSWORD] Actualizando contraseña en nextris.tbuser_patient para: {username}")
            cursor.execute("""
            UPDATE nextris.tbuser_patient 
            SET password = %s, firstlogin = 0 
            WHERE username = %s
            """, (hashed_password, username))
        else:
            # Actualizar contraseña en tbuser (personal)
            print(f"[CHANGE PASSWORD] Actualizando contraseña en nextris.tbuser para: {username}")
            cursor.execute("""
            UPDATE nextris.tbuser 
            SET password = %s, first_login = 0 
            WHERE username = %s
            """, (hashed_password, username))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        # Actualizar la sesión
        session['requires_password_change'] = False
        
        print(f"[CHANGE PASSWORD] ✓ Contraseña actualizada exitosamente")
        
        return jsonify({'success': True, 'message': 'Contraseña actualizada exitosamente'})
        
    except Exception as e:
        print(f"[CHANGE PASSWORD] ✗ Error al cambiar contraseña: {e}")
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500 

# Errors

@login_manager.unauthorized_handler
def unauthorized_handler():
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(403)
def access_forbidden(error):
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('home/page-404.html'), 404


@blueprint.errorhandler(500)
def internal_error(error):
    return render_template('home/page-500.html'), 500
