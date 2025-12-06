# Guía Rápida: Crear Frontend React

## Opción 1: Vite (Recomendado - Más Rápido)

```bash
cd /var/www
npm create vite@latest nextris-frontend -- --template react
cd nextris-frontend
npm install

# Instalar dependencias
npm install axios react-router-dom @tanstack/react-query zustand
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

## Opción 2: Create React App (Tradicional)

```bash
cd /var/www
npx create-react-app nextris-frontend
cd nextris-frontend

# Instalar dependencias
npm install axios react-router-dom @tanstack/react-query zustand
```

---

## Configurar Variables de Entorno

Crear archivo `.env` en la raíz del proyecto React:

```env
VITE_API_URL=http://148.230.72.8:5001/api
# O para Create React App:
REACT_APP_API_URL=http://148.230.72.8:5001/api
```

---

## Estructura Recomendada

```
nextris-frontend/
├── src/
│   ├── services/
│   │   └── api.js              # Cliente Axios + servicios API
│   ├── contexts/
│   │   └── AuthContext.jsx     # Context de autenticación
│   ├── hooks/
│   │   ├── useAuth.js          # Hook de autenticación
│   │   └── usePatients.js      # Hook para pacientes
│   ├── pages/
│   │   ├── Login.jsx           # Página de login
│   │   ├── Dashboard.jsx       # Dashboard principal
│   │   ├── Patients/
│   │   │   ├── PatientList.jsx
│   │   │   └── PatientDetail.jsx
│   │   └── Studies/
│   │       ├── StudyList.jsx
│   │       └── StudyViewer.jsx
│   ├── components/
│   │   ├── Layout.jsx          # Layout principal
│   │   ├── Navbar.jsx          # Barra de navegación
│   │   └── PrivateRoute.jsx    # Ruta protegida
│   ├── App.jsx
│   └── main.jsx
└── .env
```

---

## Código Base Esencial

### 1. Cliente API (`src/services/api.js`)

```javascript
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001/api';

const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Interceptor para agregar token
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

// Interceptor para refresh token
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
                localStorage.clear();
                window.location.href = '/login';
                return Promise.reject(refreshError);
            }
        }
        
        return Promise.reject(error);
    }
);

export default api;

// Servicios
export const authService = {
    login: (username, password, userType) => 
        api.post('/auth/login', { username, password, user_type: userType }),
    getCurrentUser: () => api.get('/auth/me'),
    logout: () => api.post('/auth/logout'),
};

export const patientService = {
    getPatients: (params) => api.get('/patients', { params }),
    getPatient: (guid) => api.get(`/patients/${guid}`),
};

export const studyService = {
    getStudies: (params) => api.get('/studies', { params }),
    getStudy: (guid) => api.get(`/studies/${guid}`),
    getPatientStudies: (patientId) => api.get(`/studies/patient/${patientId}`),
};
```

### 2. Context de Autenticación (`src/contexts/AuthContext.jsx`)

```jsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { authService } from '../services/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
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

    const logout = async () => {
        try {
            await authService.logout();
        } finally {
            localStorage.clear();
            setUser(null);
        }
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
```

### 3. Página de Login (`src/pages/Login.jsx`)

```jsx
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
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-500 to-purple-600">
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
                            className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                            className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                            required
                        />
                    </div>
                    
                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-gradient-to-r from-blue-500 to-purple-600 text-white py-2 rounded-lg font-semibold hover:opacity-90 disabled:opacity-50"
                    >
                        {loading ? 'Iniciando sesión...' : 'Iniciar Sesión'}
                    </button>
                </form>
            </div>
        </div>
    );
}
```

### 4. App Principal (`src/App.jsx`)

```jsx
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';

function PrivateRoute({ children }) {
    const { user, loading } = useAuth();
    
    if (loading) {
        return <div>Cargando...</div>;
    }
    
    return user ? children : <Navigate to="/login" />;
}

function App() {
    return (
        <BrowserRouter>
            <AuthProvider>
                <Routes>
                    <Route path="/login" element={<Login />} />
                    <Route
                        path="/dashboard"
                        element={
                            <PrivateRoute>
                                <Dashboard />
                            </PrivateRoute>
                        }
                    />
                    <Route path="/" element={<Navigate to="/dashboard" />} />
                </Routes>
            </AuthProvider>
        </BrowserRouter>
    );
}

export default App;
```

---

## Iniciar el Desarrollo

```bash
# En el directorio del proyecto React
npm run dev

# Acceder a:
# http://localhost:5173 (Vite)
# http://localhost:3000 (Create React App)
```

---

## Configurar TailwindCSS (Opcional pero Recomendado)

Si instalaste Tailwind, edita `tailwind.config.js`:

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

Y en `src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

---

## Próximos Pasos

1. ✅ Crear el proyecto React
2. ✅ Configurar el cliente API
3. ✅ Implementar autenticación
4. 🚀 Crear componentes para:
   - Lista de pacientes
   - Detalle de paciente
   - Lista de estudios
   - Visualizador DICOM
   - Agenda de citas
   - Editor de informes

---

## Recursos Útiles

- [React Router](https://reactrouter.com/)
- [TanStack Query](https://tanstack.com/query/latest)
- [Axios](https://axios-http.com/)
- [Tailwind CSS](https://tailwindcss.com/)

---

**¿Listo para empezar?** Ejecuta:

```bash
cd /var/www
npm create vite@latest nextris-frontend -- --template react
cd nextris-frontend
npm install
npm install axios react-router-dom @tanstack/react-query zustand
npm run dev
```
