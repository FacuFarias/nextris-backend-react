
from flask_login import UserMixin

from apps import db, login_manager

from apps.authentication.util import hash_pass


# Clase para pacientes que no usa SQLAlchemy
class PatientUser:
    """
    Clase simple para pacientes que implementa la interfaz de Flask-Login
    sin usar SQLAlchemy
    """
    def __init__(self, patient_guid, username, name, surname, email, is_active_flag, first_login_flag):
        self.id = patient_guid
        self.username = username
        self.name = name
        self.surname = surname
        self.email = email
        self.is_active = 1 if is_active_flag else 0
        self.first_login = first_login_flag if isinstance(first_login_flag, int) else (1 if first_login_flag else 0)
        self.role_id = None
    
    def get_id(self):
        return str(self.id)
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
    
    @property
    def is_active_user(self):
        return self.is_active == 1


class Users(db.Model, UserMixin):
    """
    Modelo de usuario que mapea a las tablas PostgreSQL existentes.
    Usa tbuser como tabla principal y isrole para obtener el nombre del rol.
    """
    __tablename__ = 'tbuser'
    __table_args__ = {'schema': 'nextris'}
    
    # Mapeo de campos de la tabla tbuser
    id = db.Column('guid', db.String, primary_key=True)  # guid es el ID en PostgreSQL
    username = db.Column(db.String(64), unique=True)
    email = db.Column('mail', db.String(64))  # mail es el campo en PostgreSQL
    password = db.Column(db.String(255))  # Campo para autenticación
    name = db.Column(db.String(100))
    surname = db.Column(db.String(100))
    national_number = db.Column('nationalnumber', db.String(20))  # nationalnumber en PostgreSQL
    role_id = db.Column('idrole', db.String)  # GUID del rol
    is_active = db.Column('isactive', db.SmallInteger, default=1)  # SmallInteger para PostgreSQL
    first_login = db.Column('first_login', db.SmallInteger, default=1)  # Marca si es primera vez
    
    def __init__(self, **kwargs):
        for property, value in kwargs.items():
            if hasattr(value, '__iter__') and not isinstance(value, str):
                value = value[0]
            if property == 'password':
                value = hash_pass(value)
            elif property == 'is_active' and isinstance(value, bool):
                # Convertir booleano a entero para PostgreSQL
                value = 1 if value else 0
            setattr(self, property, value)
    
    @property
    def user_type(self):
        """
        Obtiene el nombre del rol desde la tabla isrole basado en role_id.
        Esto reemplaza el campo user_type que teníamos antes.
        """
        if self.role_id:
            try:
                # Hacer consulta para obtener el nombre del rol
                result = db.session.execute(
                    db.text("SELECT description FROM nextris.isrole WHERE guid = :role_id"),
                    {"role_id": self.role_id}
                ).fetchone()
                
                if result:
                    return result[0]
            except Exception as e:
                print(f"[ERROR] Error getting user role: {e}")
        
        return "Usuario"  # Fallback por defecto

    def __repr__(self):
        return f'<User {self.username}, Type: {self.user_type}>'


@login_manager.user_loader
def user_loader(id):
    """
    Carga el usuario desde la sesión.
    Primero intenta cargar desde tbuser (personal),
    si no encuentra, intenta cargar desde tbuser_patient (pacientes)
    """
    from flask import session
    import psycopg2
    
    # Si es un paciente (identificado por session['is_patient'])
    if session.get('is_patient'):
        try:
            # Importar config para conectarse a PostgreSQL
            import sys
            import os
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'home')))
            from apps.home.routes import config
            
            if config is None:
                return None
            
            connection = psycopg2.connect(**config)
            cursor = connection.cursor()
            
            # Buscar paciente en tbuser_patient
            cursor.execute("""
                SELECT up.guid, up.username, dp.name, dp.surname, dp.email, up.status, up.firstlogin
                FROM nextris.tbuser_patient up
                LEFT JOIN nextris.datapatient dp ON up.datapatient_id = dp.guid
                WHERE up.guid = %s
            """, (id,))
            
            patient_row = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if patient_row:
                patient_guid, username, name, surname, email, status, firstlogin = patient_row
                
                # Verificar que el paciente esté activo
                is_active = False
                if isinstance(status, (int, bool)):
                    is_active = bool(status)
                elif isinstance(status, str):
                    is_active = status.lower() in ['active', '1', 'true', 'activo']
                
                if not is_active:
                    return None
                
                # Usar la clase PatientUser definida arriba
                return PatientUser(
                    patient_guid=patient_guid,
                    username=username,
                    name=name or username,
                    surname=surname or "",
                    email=email or "",
                    is_active_flag=is_active,
                    first_login_flag=firstlogin
                )
        except Exception as e:
            print(f"[USER_LOADER] Error cargando paciente: {str(e)}")
            return None
    
    # Si no es paciente, buscar en Users (personal)
    return Users.query.filter_by(id=id).first()


@login_manager.request_loader
def request_loader(request):
    username = request.form.get('username')
    user = Users.query.filter_by(username=username).first()
    return user if user else None
