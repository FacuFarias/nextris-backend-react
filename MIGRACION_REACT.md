# Plan de Migración a React - NextRIS

## Estado Actual

**Backend:** Flask con templates Jinja2
**Frontend:** HTML + JavaScript vanilla + Bootstrap
**Autenticación:** Flask-Login con sesiones
**Base de datos:** PostgreSQL

---

## Objetivo

Migrar a una arquitectura moderna con:
- **Backend:** Flask como API REST pura
- **Frontend:** React (SPA - Single Page Application)
- **Comunicación:** API REST con JSON
- **Autenticación:** JWT tokens

---

## Arquitectura Propuesta

```
┌─────────────────────┐         ┌─────────────────────┐
│   React Frontend    │         │   Flask Backend     │
│   (Puerto 3000)     │◄───────►│   (Puerto 5000)     │
│                     │  API    │                     │
│  - Components       │  REST   │  - API Endpoints    │
│  - State Mgmt       │  JSON   │  - JWT Auth         │
│  - Routing          │         │  - Business Logic   │
└─────────────────────┘         └─────────────────────┘
                                         │
                                         ▼
                                ┌─────────────────┐
                                │   PostgreSQL    │
                                └─────────────────┘
```

---

## Dependencias Necesarias

### Backend (Flask)

**Agregar a requirements.txt:**
```
flask-cors==4.0.0
flask-jwt-extended==4.6.0
```

**Instalar:**
```bash
cd /var/www/nextris-dev
source venv/bin/activate
pip install flask-cors flask-jwt-extended
pip freeze > requirements.txt
```

### Frontend (React)

**Crear proyecto React:**
```bash
cd /var/www
npx create-react-app nextris-frontend
cd nextris-frontend
npm install axios react-router-dom @tanstack/react-query zustand
```

**Dependencias recomendadas:**
- `axios`: Cliente HTTP para llamadas API
- `react-router-dom`: Manejo de rutas
- `@tanstack/react-query`: Cache y gestión de estado servidor
- `zustand`: Gestión de estado global (alternativa ligera a Redux)
- `tailwindcss` o `@mui/material`: Librería de componentes UI

---

## Cambios Necesarios en el Backend

### 1. Configurar CORS

**Archivo:** `apps/__init__.py`

```python
from flask_cors import CORS

def create_app(config):
    app = Flask(__name__)
    app.config.from_object(config)
    
    # Configurar CORS
    CORS(app, 
         resources={r"/api/*": {"origins": ["http://localhost:3000", "http://148.230.72.8:3000"]}},
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    
    register_extensions(app)
    register_blueprints(app)
    configure_database(app)
    return app
```

### 2. Configurar JWT

**Archivo:** `apps/__init__.py`

```python
from flask_jwt_extended import JWTManager

jwt = JWTManager()

def register_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)
    jwt.init_app(app)  # NUEVO
```

**Archivo:** `apps/config.py`

```python
import os
from datetime import timedelta

class Config(object):
    # ... configuración existente ...
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'super-secret-jwt-key-change-this')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
```

### 3. Crear Blueprint de API

**Crear:** `apps/api/__init__.py`

```python
from flask import Blueprint

api_blueprint = Blueprint('api', __name__, url_prefix='/api')

from apps.api import auth, patients, studies, appointments
```

**Registrar en** `apps/__init__.py`:

```python
def register_blueprints(app):
    # Blueprints existentes
    for module_name in ('authentication', 'home'):
        module = import_module('apps.{}.routes'.format(module_name))
        app.register_blueprint(module.blueprint)
    
    # Nuevo blueprint API
    from apps.api import api_blueprint
    app.register_blueprint(api_blueprint)
```

### 4. Crear Endpoints API

**Ejemplo:** `apps/api/auth.py`

```python
from flask import jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from apps.api import api_blueprint
from apps.authentication.models import Users, PatientUser
from werkzeug.security import check_password_hash

@api_blueprint.route('/auth/login', methods=['POST'])
def api_login():
    """Login endpoint que retorna JWT token"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        user_type = data.get('user_type', 'staff')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': 'Usuario y contraseña requeridos'
            }), 400
        
        # Buscar usuario
        if user_type == 'patient':
            # Lógica para paciente
            user = PatientUser.query.filter_by(username=username).first()
        else:
            # Lógica para staff
            user = Users.query.filter_by(username=username, is_active=1).first()
        
        if not user or not check_password_hash(user.password, password):
            return jsonify({
                'success': False,
                'message': 'Credenciales inválidas'
            }), 401
        
        # Crear tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        return jsonify({
            'success': True,
            'data': {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'user_type': user_type,
                    'requires_password_change': bool(user.first_login)
                }
            },
            'message': 'Login exitoso'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error en el servidor: {str(e)}'
        }), 500

@api_blueprint.route('/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Obtener información del usuario actual"""
    user_id = get_jwt_identity()
    user = Users.query.get(user_id)
    
    if not user:
        return jsonify({
            'success': False,
            'message': 'Usuario no encontrado'
        }), 404
    
    return jsonify({
        'success': True,
        'data': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'user_type': user.user_type
        }
    }), 200

@api_blueprint.route('/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refrescar access token"""
    user_id = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    
    return jsonify({
        'success': True,
        'data': {
            'access_token': access_token
        }
    }), 200
```

**Ejemplo:** `apps/api/patients.py`

```python
from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from apps.api import api_blueprint
import psycopg2
from apps.home.routes import config

@api_blueprint.route('/patients', methods=['GET'])
@jwt_required()
def get_patients():
    """Listar pacientes con paginación"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT guid, name, surname, email, phonenumber, dni
            FROM nextris.datapatient
            WHERE name ILIKE %s OR surname ILIKE %s OR dni ILIKE %s
            ORDER BY surname, name
            LIMIT %s OFFSET %s
        """
        
        search_pattern = f'%{search}%'
        offset = (page - 1) * per_page
        
        cursor.execute(query, (search_pattern, search_pattern, search_pattern, per_page, offset))
        
        patients = []
        for row in cursor.fetchall():
            patients.append({
                'guid': row[0],
                'name': row[1],
                'surname': row[2],
                'email': row[3],
                'phone': row[4],
                'dni': row[5]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'patients': patients,
                'page': page,
                'per_page': per_page
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@api_blueprint.route('/patients/<guid>', methods=['GET'])
@jwt_required()
def get_patient(guid):
    """Obtener detalles de un paciente"""
    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT guid, name, surname, email, phonenumber, dni, birthdate, gender
            FROM nextris.datapatient
            WHERE guid = %s
        """, (guid,))
        
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        patient = {
            'guid': row[0],
            'name': row[1],
            'surname': row[2],
            'email': row[3],
            'phone': row[4],
            'dni': row[5],
            'birthdate': row[6].isoformat() if row[6] else None,
            'gender': row[7]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': patient
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
```

---

## Estructura Frontend React

### 1. Servicio de API

**Archivo:** `src/services/api.js`

```javascript
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    withCredentials: true
});

// Interceptor para agregar token a cada request
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Interceptor para manejar refresh token
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;
        
        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;
            
            try {
                const refreshToken = localStorage.getItem('refresh_token');
                const response = await axios.post(`${API_URL}/auth/refresh`, {}, {
                    headers: { Authorization: `Bearer ${refreshToken}` }
                });
                
                const { access_token } = response.data.data;
                localStorage.setItem('access_token', access_token);
                
                originalRequest.headers.Authorization = `Bearer ${access_token}`;
                return api(originalRequest);
            } catch (refreshError) {
                // Refresh falló, logout
                localStorage.clear();
                window.location.href = '/login';
                return Promise.reject(refreshError);
            }
        }
        
        return Promise.reject(error);
    }
);

export default api;

// Servicios específicos
export const authService = {
    login: (username, password, userType) => 
        api.post('/auth/login', { username, password, user_type: userType }),
    
    logout: () => {
        localStorage.clear();
        return Promise.resolve();
    },
    
    getCurrentUser: () => 
        api.get('/auth/me'),
};

export const patientService = {
    getPatients: (params) => 
        api.get('/patients', { params }),
    
    getPatient: (guid) => 
        api.get(`/patients/${guid}`),
};
```

### 2. Context de Autenticación

**Archivo:** `src/contexts/AuthContext.js`

```javascript
import React, { createContext, useContext, useState, useEffect } from 'react';
import { authService } from '../services/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Verificar si hay token al cargar
        const token = localStorage.getItem('access_token');
        if (token) {
            authService.getCurrentUser()
                .then(response => setUser(response.data.data))
                .catch(() => localStorage.clear())
                .finally(() => setLoading(false));
        } else {
            setLoading(false);
        }
    }, []);

    const login = async (username, password, userType) => {
        const response = await authService.login(username, password, userType);
        const { access_token, refresh_token, user } = response.data.data;
        
        localStorage.setItem('access_token', access_token);
        localStorage.setItem('refresh_token', refresh_token);
        setUser(user);
        
        return user;
    };

    const logout = () => {
        authService.logout();
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
```

### 3. Componente de Login

**Archivo:** `src/pages/Login.jsx`

```javascript
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [userType, setUserType] = useState('staff');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    
    const { login } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            await login(username, password, userType);
            navigate('/dashboard');
        } catch (err) {
            setError(err.response?.data?.message || 'Error al iniciar sesión');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-500 to-indigo-600">
            <div className="bg-white p-8 rounded-lg shadow-xl w-full max-w-md">
                <h1 className="text-3xl font-bold text-center mb-6 text-gray-800">
                    NextRIS
                </h1>
                
                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
                        {error}
                    </div>
                )}
                
                <form onSubmit={handleSubmit}>
                    <div className="mb-4">
                        <label className="block text-sm font-medium mb-2">
                            Tipo de usuario
                        </label>
                        <div className="space-y-2">
                            <label className="flex items-center">
                                <input
                                    type="radio"
                                    value="staff"
                                    checked={userType === 'staff'}
                                    onChange={(e) => setUserType(e.target.value)}
                                    className="mr-2"
                                />
                                Personal Médico
                            </label>
                            <label className="flex items-center">
                                <input
                                    type="radio"
                                    value="patient"
                                    checked={userType === 'patient'}
                                    onChange={(e) => setUserType(e.target.value)}
                                    className="mr-2"
                                />
                                Paciente
                            </label>
                        </div>
                    </div>
                    
                    <div className="mb-4">
                        <label className="block text-sm font-medium mb-2">
                            Usuario
                        </label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                            required
                        />
                    </div>
                    
                    <div className="mb-6">
                        <label className="block text-sm font-medium mb-2">
                            Contraseña
                        </label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                            required
                        />
                    </div>
                    
                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-gradient-to-r from-purple-500 to-indigo-600 text-white py-2 rounded-lg font-semibold hover:opacity-90 disabled:opacity-50"
                    >
                        {loading ? 'Iniciando sesión...' : 'Iniciar Sesión'}
                    </button>
                </form>
            </div>
        </div>
    );
}
```

---

## Plan de Migración por Fases

### Fase 1: Preparación (1-2 semanas)
- [ ] Instalar dependencias backend (CORS, JWT)
- [ ] Crear estructura de API en Flask
- [ ] Crear proyecto React
- [ ] Configurar entornos de desarrollo

### Fase 2: Autenticación (1 semana)
- [ ] Implementar endpoints de auth con JWT
- [ ] Crear componentes de login en React
- [ ] Probar flujo completo de autenticación

### Fase 3: Migración Módulo Portal Pacientes (2-3 semanas)
- [ ] API: Endpoints de estudios del paciente
- [ ] React: Componentes de lista de estudios
- [ ] React: Visualizador de imágenes DICOM
- [ ] Probar funcionalidad completa

### Fase 4: Migración Módulo Administrativo (3-4 semanas)
- [ ] API: Endpoints de pacientes
- [ ] API: Endpoints de citas
- [ ] React: Gestión de pacientes
- [ ] React: Agenda de citas

### Fase 5: Migración Módulo Médico (3-4 semanas)
- [ ] API: Endpoints de estudios
- [ ] API: Endpoints de informes
- [ ] React: Visualizador DICOM avanzado
- [ ] React: Editor de informes

### Fase 6: Optimización y Deploy (1-2 semanas)
- [ ] Build de producción
- [ ] Configurar Nginx como proxy
- [ ] Testing completo
- [ ] Deploy a producción

---

## Consideraciones Técnicas

### Performance
- Implementar paginación en todas las listas
- Usar React Query para cache inteligente
- Lazy loading de componentes pesados
- Optimizar imágenes DICOM

### Seguridad
- HTTPS obligatorio en producción
- Tokens con tiempo de expiración corto
- Validación de inputs en backend
- Rate limiting en endpoints

### SEO y Accesibilidad
- Considerar Next.js si necesitas SEO
- ARIA labels en componentes
- Soporte para lectores de pantalla

---

## Configuración de Producción

### Nginx como Proxy Reverso

```nginx
server {
    listen 80;
    server_name nextris.example.com;

    # Frontend React (build estático)
    location / {
        root /var/www/nextris-frontend/build;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## Recursos y Referencias

### Documentación
- Flask-RESTX: https://flask-restx.readthedocs.io/
- Flask-JWT-Extended: https://flask-jwt-extended.readthedocs.io/
- React: https://react.dev/
- React Router: https://reactrouter.com/
- TanStack Query: https://tanstack.com/query/

### Alternativas a Considerar
- **Next.js** en lugar de Create React App (mejor SEO, SSR)
- **Redux Toolkit** en lugar de Zustand (para apps muy complejas)
- **Material-UI** o **Chakra UI** para componentes pre-diseñados
- **TypeScript** para mayor seguridad en tipos

---

## Preguntas Frecuentes

**¿Puedo mantener las páginas existentes mientras migro?**
Sí, puedes tener ambos sistemas funcionando en paralelo.

**¿Necesito reescribir toda la lógica de negocio?**
No, la lógica de negocio puede mantenerse igual, solo cambias cómo la expones (JSON en lugar de HTML).

**¿Cuánto tiempo toma la migración completa?**
Dependiendo del equipo, entre 2-4 meses para una migración completa y probada.

**¿Es necesario cambiar la base de datos?**
No, puedes mantener la misma estructura de PostgreSQL.

---

**Última actualización:** 4 de diciembre de 2025
