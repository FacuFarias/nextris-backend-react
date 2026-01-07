# Guía de Implementación: Transcripción de Audio con Whisper

## 📋 Descripción General

Esta guía describe cómo implementar la funcionalidad de transcripción de dictados médicos usando Whisper en el frontend de NextRIS React.

## 🔌 Backend API

### Endpoints Disponibles

#### 1. `POST /api/transcription/upload`
Transcribe un archivo de audio completo.

**Headers:**
```
Authorization: Bearer {token}
```

**Body (multipart/form-data):**
```
audio: [archivo de audio]
language: "es" (opcional, default: "es")
task: "transcribe" (opcional, "transcribe" o "translate")
```

**Respuesta:**
```json
{
  "success": true,
  "data": {
    "text": "Paciente de sexo masculino de 45 años de edad...",
    "language": "es",
    "duration": 12.5,
    "segments": [
      {
        "start": 0.0,
        "end": 5.2,
        "text": "Paciente de sexo masculino de 45 años de edad"
      }
    ]
  },
  "message": "Audio transcrito exitosamente"
}
```

#### 2. `POST /api/transcription/stream`
Transcripción en tiempo real (streaming).

**Headers:**
```
Authorization: Bearer {token}
Content-Type: audio/wav
X-Language: es (opcional)
```

**Body:**
Binary audio data

#### 3. `GET /api/transcription/status`
Verifica el estado del servicio Whisper.

---

## 🎨 Implementación en Frontend

### Opción 1: Componente de Grabación Simple

Crear un componente que permita grabar y transcribir audio.

**Ubicación sugerida:**
```
/var/www/nextris-dev-react/frontend/src/components/Transcription/
```

**Estructura de archivos:**
```
Transcription/
├── AudioRecorder.jsx          # Componente principal
├── RecordButton.jsx           # Botón de grabación
├── TranscriptionDisplay.jsx   # Mostrar resultado
└── useAudioRecorder.js        # Hook personalizado
```

### 📝 Código de Ejemplo

#### 1. Hook personalizado: `useAudioRecorder.js`

```javascript
import { useState, useRef, useCallback } from 'react';

export const useAudioRecorder = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const [recordingTime, setRecordingTime] = useState(0);
  
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100
        } 
      });
      
      // Usar diferentes codecs según disponibilidad
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';
      
      mediaRecorderRef.current = new MediaRecorder(stream, { mimeType });
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: mimeType });
        setAudioBlob(blob);
        
        // Detener todas las pistas de audio
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
      
      // Iniciar contador de tiempo
      setRecordingTime(0);
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
      
    } catch (error) {
      console.error('Error al acceder al micrófono:', error);
      alert('No se pudo acceder al micrófono. Verifique los permisos.');
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    }
  }, [isRecording]);

  const resetRecording = useCallback(() => {
    setAudioBlob(null);
    setRecordingTime(0);
    audioChunksRef.current = [];
  }, []);

  return {
    isRecording,
    audioBlob,
    recordingTime,
    startRecording,
    stopRecording,
    resetRecording
  };
};
```

#### 2. Servicio API: `src/services/transcriptionService.js`

```javascript
import api from './api'; // Tu instancia de axios configurada

export const transcriptionService = {
  /**
   * Transcribe un archivo de audio
   * @param {Blob} audioBlob - Blob de audio a transcribir
   * @param {Object} options - Opciones de transcripción
   * @returns {Promise} - Promesa con la transcripción
   */
  async transcribeAudio(audioBlob, options = {}) {
    const formData = new FormData();
    
    // Convertir blob a archivo
    const audioFile = new File(
      [audioBlob], 
      `recording_${Date.now()}.webm`, 
      { type: audioBlob.type }
    );
    
    formData.append('audio', audioFile);
    formData.append('language', options.language || 'es');
    formData.append('task', options.task || 'transcribe');

    try {
      const response = await api.post('/api/transcription/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        // Timeout largo para archivos grandes
        timeout: 300000 // 5 minutos
      });

      return response.data;
    } catch (error) {
      console.error('Error en transcripción:', error);
      throw error;
    }
  },

  /**
   * Verifica el estado del servicio de transcripción
   * @returns {Promise} - Estado del servicio
   */
  async checkStatus() {
    try {
      const response = await api.get('/api/transcription/status');
      return response.data;
    } catch (error) {
      console.error('Error verificando estado:', error);
      throw error;
    }
  }
};
```

#### 3. Componente Principal: `AudioRecorder.jsx`

```jsx
import React, { useState } from 'react';
import { useAudioRecorder } from './useAudioRecorder';
import { transcriptionService } from '../../services/transcriptionService';
import { 
  FaMicrophone, 
  FaStop, 
  FaPaperPlane, 
  FaTrash,
  FaSpinner 
} from 'react-icons/fa';

const AudioRecorder = ({ onTranscriptionComplete }) => {
  const {
    isRecording,
    audioBlob,
    recordingTime,
    startRecording,
    stopRecording,
    resetRecording
  } = useAudioRecorder();

  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcription, setTranscription] = useState(null);
  const [error, setError] = useState(null);

  const handleTranscribe = async () => {
    if (!audioBlob) return;

    setIsTranscribing(true);
    setError(null);

    try {
      const result = await transcriptionService.transcribeAudio(audioBlob, {
        language: 'es',
        task: 'transcribe'
      });

      if (result.success) {
        setTranscription(result.data);
        
        // Callback opcional para el componente padre
        if (onTranscriptionComplete) {
          onTranscriptionComplete(result.data);
        }
      } else {
        setError(result.message || 'Error en la transcripción');
      }
    } catch (err) {
      setError(
        err.response?.data?.message || 
        'Error al transcribir el audio. Verifique que el servicio esté disponible.'
      );
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleReset = () => {
    resetRecording();
    setTranscription(null);
    setError(null);
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="audio-recorder-container">
      <div className="recorder-controls">
        {/* Botón de Grabar/Detener */}
        {!audioBlob && (
          <button
            onClick={isRecording ? stopRecording : startRecording}
            className={`btn-record ${isRecording ? 'recording' : ''}`}
            disabled={isTranscribing}
          >
            {isRecording ? (
              <>
                <FaStop /> Detener
              </>
            ) : (
              <>
                <FaMicrophone /> Grabar Dictado
              </>
            )}
          </button>
        )}

        {/* Contador de tiempo */}
        {isRecording && (
          <div className="recording-timer">
            <span className="recording-dot"></span>
            {formatTime(recordingTime)}
          </div>
        )}

        {/* Controles para audio grabado */}
        {audioBlob && !transcription && (
          <div className="audio-controls">
            <audio 
              controls 
              src={URL.createObjectURL(audioBlob)}
              className="audio-player"
            />
            
            <div className="action-buttons">
              <button
                onClick={handleTranscribe}
                disabled={isTranscribing}
                className="btn-transcribe"
              >
                {isTranscribing ? (
                  <>
                    <FaSpinner className="spinner" /> Transcribiendo...
                  </>
                ) : (
                  <>
                    <FaPaperPlane /> Transcribir
                  </>
                )}
              </button>

              <button
                onClick={handleReset}
                disabled={isTranscribing}
                className="btn-reset"
              >
                <FaTrash /> Eliminar
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Mostrar errores */}
      {error && (
        <div className="error-message">
          <p>⚠️ {error}</p>
        </div>
      )}

      {/* Mostrar transcripción */}
      {transcription && (
        <div className="transcription-result">
          <div className="transcription-header">
            <h4>Transcripción:</h4>
            <button onClick={handleReset} className="btn-new">
              Nueva Grabación
            </button>
          </div>
          
          <div className="transcription-text">
            {transcription.text}
          </div>

          {/* Información adicional */}
          <div className="transcription-info">
            <span>Duración: {transcription.duration?.toFixed(1)}s</span>
            <span>Idioma: {transcription.language}</span>
          </div>

          {/* Segmentos (opcional) */}
          {transcription.segments && transcription.segments.length > 0 && (
            <details className="transcription-segments">
              <summary>Ver segmentos ({transcription.segments.length})</summary>
              <div className="segments-list">
                {transcription.segments.map((segment, index) => (
                  <div key={index} className="segment-item">
                    <span className="segment-time">
                      {segment.start.toFixed(1)}s - {segment.end.toFixed(1)}s
                    </span>
                    <span className="segment-text">{segment.text}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
};

export default AudioRecorder;
```

#### 4. Estilos CSS: `AudioRecorder.css`

```css
.audio-recorder-container {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.recorder-controls {
  display: flex;
  flex-direction: column;
  gap: 15px;
  align-items: center;
}

.btn-record {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 15px 30px;
  font-size: 16px;
  font-weight: 600;
  border: none;
  border-radius: 50px;
  cursor: pointer;
  transition: all 0.3s ease;
  background: #007bff;
  color: white;
}

.btn-record:hover {
  background: #0056b3;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
}

.btn-record.recording {
  background: #dc3545;
  animation: pulse 1.5s infinite;
}

.btn-record.recording:hover {
  background: #c82333;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}

.recording-timer {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 24px;
  font-weight: bold;
  color: #dc3545;
}

.recording-dot {
  width: 12px;
  height: 12px;
  background: #dc3545;
  border-radius: 50%;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.audio-controls {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.audio-player {
  width: 100%;
  max-width: 400px;
}

.action-buttons {
  display: flex;
  gap: 10px;
  justify-content: center;
}

.btn-transcribe,
.btn-reset,
.btn-new {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.btn-transcribe {
  background: #28a745;
  color: white;
}

.btn-transcribe:hover:not(:disabled) {
  background: #218838;
}

.btn-transcribe:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-reset,
.btn-new {
  background: #6c757d;
  color: white;
}

.btn-reset:hover:not(:disabled),
.btn-new:hover {
  background: #5a6268;
}

.spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.error-message {
  background: #f8d7da;
  border: 1px solid #f5c6cb;
  border-radius: 6px;
  padding: 12px;
  color: #721c24;
  margin-top: 15px;
}

.transcription-result {
  margin-top: 20px;
  background: white;
  border-radius: 8px;
  padding: 20px;
  border: 1px solid #dee2e6;
}

.transcription-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  border-bottom: 2px solid #007bff;
  padding-bottom: 10px;
}

.transcription-header h4 {
  margin: 0;
  color: #007bff;
}

.transcription-text {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 6px;
  line-height: 1.6;
  font-size: 15px;
  color: #333;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.transcription-info {
  display: flex;
  gap: 20px;
  margin-top: 15px;
  font-size: 13px;
  color: #6c757d;
}

.transcription-segments {
  margin-top: 15px;
  border-top: 1px solid #dee2e6;
  padding-top: 15px;
}

.transcription-segments summary {
  cursor: pointer;
  font-weight: 600;
  color: #007bff;
  user-select: none;
}

.segments-list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.segment-item {
  display: flex;
  gap: 15px;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 4px;
  font-size: 14px;
}

.segment-time {
  color: #6c757d;
  font-weight: 600;
  min-width: 100px;
}

.segment-text {
  flex: 1;
  color: #333;
}
```

---

## 🚀 Uso del Componente

### Ejemplo 1: En una página de informes médicos

```jsx
import AudioRecorder from './components/Transcription/AudioRecorder';

function MedicalReportPage() {
  const [reportText, setReportText] = useState('');

  const handleTranscriptionComplete = (transcriptionData) => {
    // Agregar la transcripción al reporte
    setReportText(prev => prev + '\n' + transcriptionData.text);
  };

  return (
    <div>
      <h2>Informe Médico</h2>
      
      {/* Componente de transcripción */}
      <AudioRecorder onTranscriptionComplete={handleTranscriptionComplete} />
      
      {/* Editor de texto */}
      <textarea 
        value={reportText}
        onChange={(e) => setReportText(e.target.value)}
        rows={10}
      />
    </div>
  );
}
```

### Ejemplo 2: Como modal/popup

```jsx
import { useState } from 'react';
import Modal from './components/Modal';
import AudioRecorder from './components/Transcription/AudioRecorder';

function ReportEditor() {
  const [showRecorder, setShowRecorder] = useState(false);

  const handleTranscription = (data) => {
    // Insertar transcripción en el cursor del editor
    insertTextAtCursor(data.text);
    setShowRecorder(false);
  };

  return (
    <>
      <button onClick={() => setShowRecorder(true)}>
        🎤 Dictar
      </button>

      <Modal isOpen={showRecorder} onClose={() => setShowRecorder(false)}>
        <AudioRecorder onTranscriptionComplete={handleTranscription} />
      </Modal>
    </>
  );
}
```

---

## ⚙️ Configuración Adicional

### 1. Configurar axios (si aún no lo tienes)

```javascript
// src/services/api.js
import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:5001',
  timeout: 300000, // 5 minutos para transcripciones
});

// Interceptor para agregar token JWT
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
```

### 2. Variables de entorno

```bash
# .env
REACT_APP_API_URL=http://148.230.72.8:5001
```

### 3. Verificar permisos de micrófono

Agregar en `public/index.html` o en el componente:

```javascript
// Verificar permisos antes de grabar
const checkMicrophonePermission = async () => {
  try {
    const permissionStatus = await navigator.permissions.query({ 
      name: 'microphone' 
    });
    
    if (permissionStatus.state === 'denied') {
      alert('El acceso al micrófono está bloqueado. Por favor, habilítelo en la configuración del navegador.');
      return false;
    }
    return true;
  } catch (error) {
    // En navegadores que no soportan Permissions API
    return true;
  }
};
```

---

## 🧪 Testing

### Test del endpoint

```bash
# Verificar estado del servicio
curl -X GET http://localhost:5001/api/transcription/status \
  -H "Authorization: Bearer YOUR_TOKEN"

# Transcribir un archivo
curl -X POST http://localhost:5001/api/transcription/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "audio=@test-audio.wav" \
  -F "language=es"
```

---

## 📦 Dependencias necesarias

### Backend
```bash
pip install requests
```

### Frontend
```bash
npm install axios react-icons
```

---

## 🔒 Consideraciones de Seguridad

1. **Autenticación**: Todos los endpoints requieren JWT
2. **Validación de archivos**: Solo se permiten formatos de audio específicos
3. **Límite de tamaño**: 25 MB por archivo
4. **Timeout**: 5 minutos máximo por transcripción
5. **CORS**: Configurar adecuadamente en Flask

---

## 📱 Compatibilidad de Navegadores

- **Chrome/Edge**: ✅ Soporte completo
- **Firefox**: ✅ Soporte completo
- **Safari**: ⚠️ Requiere HTTPS para micrófono
- **Mobile**: ✅ Compatible con navegadores móviles modernos

---

## 🐛 Troubleshooting

### Problema: "No se pudo acceder al micrófono"
- Verificar permisos del navegador
- Usar HTTPS en producción
- Verificar que no haya otra aplicación usando el micrófono

### Problema: "Servicio de transcripción no disponible"
- Verificar que Whisper esté corriendo en `http://localhost:9000`
- Verificar logs del servicio Whisper
- Verificar conectividad de red

### Problema: "La transcripción tarda mucho"
- Archivos muy largos pueden tardar varios minutos
- Considerar dividir audios largos en segmentos más pequeños
- Verificar recursos del servidor (CPU/RAM)

---

## 📚 Recursos Adicionales

- [Whisper OpenAI](https://github.com/openai/whisper)
- [MediaRecorder API](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder)
- [Flask File Uploads](https://flask.palletsprojects.com/en/2.3.x/patterns/fileuploads/)
