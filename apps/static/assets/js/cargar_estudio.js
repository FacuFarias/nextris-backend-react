// DICOM Uploader - JavaScript Application
// API Configuration
const API_URL = window.location.origin;

// DOM Elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const selectFileBtn = document.getElementById('selectFileBtn');
const progressContainer = document.getElementById('progressContainer');
const progressBar = document.getElementById('progressBar');
const progressText = document.getElementById('progressText');
const progressDetails = document.getElementById('progressDetails');
const queueContainer = document.getElementById('queueContainer');
const queueList = document.getElementById('queueList');
const resultContainer = document.getElementById('resultContainer');
const resultContent = document.getElementById('resultContent');
const filesList = document.getElementById('filesList');
const refreshBtn = document.getElementById('refreshBtn');

// Estado de la aplicación
let isUploading = false;
let uploadQueue = [];
let currentUploadIndex = 0;
let successCount = 0;
let errorCount = 0;

// Inicialización
document.addEventListener('DOMContentLoaded', () => {
    console.log('🏥 DICOM Uploader iniciado');
    initializeEventListeners();
    loadFiles();
});

// Event Listeners
function initializeEventListeners() {
    // Botón seleccionar archivos
    selectFileBtn.addEventListener('click', () => {
        fileInput.click();
    });

    // Cambio en input de archivo
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFiles(Array.from(e.target.files));
        }
    });

    // Drag and Drop
    dropZone.addEventListener('click', () => {
        if (!isUploading) {
            fileInput.click();
        }
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        
        if (e.dataTransfer.files.length > 0 && !isUploading) {
            handleFiles(Array.from(e.dataTransfer.files));
        }
    });

    // Botón de refresh
    refreshBtn.addEventListener('click', () => {
        loadFiles();
    });
}

// Manejar múltiples archivos
function handleFiles(files) {
    console.log(`📁 ${files.length} archivo(s) seleccionado(s)`);

    // Validar que todos sean DICOM
    const validExtensions = ['dcm', 'dicom', 'dic'];
    const validFiles = [];
    const invalidFiles = [];

    files.forEach(file => {
        const fileExtension = file.name.split('.').pop().toLowerCase();
        if (validExtensions.includes(fileExtension)) {
            validFiles.push(file);
        } else {
            invalidFiles.push(file.name);
        }
    });

    if (invalidFiles.length > 0) {
        showError(`❌ Archivos rechazados (no son DICOM):<br><br>${invalidFiles.join('<br>')}`);
    }

    if (validFiles.length === 0) {
        showError('No se seleccionaron archivos DICOM válidos');
        return;
    }

    // Iniciar subida de archivos
    uploadQueue = validFiles;
    currentUploadIndex = 0;
    successCount = 0;
    errorCount = 0;

    startBatchUpload();
}

// Iniciar subida en lote
async function startBatchUpload() {
    if (isUploading) return;
    
    isUploading = true;
    hideResult();
    showQueue();
    
    console.log(`⬆️ Iniciando subida de ${uploadQueue.length} archivo(s)...`);

    // Procesar archivos uno por uno
    for (let i = 0; i < uploadQueue.length; i++) {
        currentUploadIndex = i;
        const file = uploadQueue[i];
        
        updateProgress(i, uploadQueue.length);
        updateQueueItem(i, 'processing', '⏳ Subiendo...');
        
        try {
            await uploadFile(file);
            successCount++;
            updateQueueItem(i, 'success', '✅ Completado');
        } catch (error) {
            errorCount++;
            updateQueueItem(i, 'error', `❌ Error: ${error.message}`);
        }
    }

    // Finalizar
    isUploading = false;
    hideProgress();
    showBatchSummary();
    loadFiles();
    fileInput.value = '';
}

// Subir un archivo
async function uploadFile(file) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();

        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                console.log('✅ Upload exitoso:', file.name);
                resolve(response);
            } else {
                const error = JSON.parse(xhr.responseText);
                console.error('❌ Error en upload:', file.name, error);
                reject(new Error(error.error || 'Error desconocido'));
            }
        });

        xhr.addEventListener('error', () => {
            console.error('❌ Error de red:', file.name);
            reject(new Error('Error de conexión'));
        });

xhr.open('POST', `${API_URL}/api/dicom/upload`);
        xhr.send(formData);
    });
}

// Actualizar progreso
function updateProgress(current, total) {
    const percent = Math.round(((current + 1) / total) * 100);
    progressBar.style.width = `${percent}%`;
    progressText.textContent = `Procesando archivos... ${current + 1}/${total}`;
    progressDetails.textContent = `${successCount} exitosos, ${errorCount} errores`;
}

// Mostrar progreso
function showProgress() {
    progressContainer.style.display = 'block';
    progressBar.style.width = '0%';
    progressText.textContent = 'Iniciando...';
    progressDetails.textContent = '';
}

// Ocultar progreso
function hideProgress() {
    setTimeout(() => {
        progressContainer.style.display = 'none';
    }, 1000);
}

// Mostrar cola
function showQueue() {
    queueContainer.style.display = 'block';
    queueList.innerHTML = uploadQueue.map((file, index) => `
        <div class="queue-item" id="queue-item-${index}">
            <span class="queue-item-name">📄 ${file.name}</span>
            <span class="queue-item-status">⏳ En espera</span>
        </div>
    `).join('');
    showProgress();
}

// Actualizar item de cola
function updateQueueItem(index, status, message) {
    const item = document.getElementById(`queue-item-${index}`);
    if (item) {
        item.className = `queue-item ${status}`;
        item.querySelector('.queue-item-status').textContent = message;
    }
}

// Mostrar resumen del lote
function showBatchSummary() {
    const total = uploadQueue.length;
    const isSuccess = errorCount === 0;
    
    resultContent.innerHTML = `
        <div class="result-${isSuccess ? 'success' : 'error'}">
            <div class="result-title">
                <span>${isSuccess ? '✅' : '⚠️'}</span>
                <span>Proceso completado</span>
            </div>
            
            <div class="result-info">
                <div class="result-info-item">
                    <span class="result-info-label">Total de archivos:</span>
                    <span class="result-info-value">${total}</span>
                </div>
                <div class="result-info-item">
                    <span class="result-info-label">Subidos exitosamente:</span>
                    <span class="result-info-value" style="color: var(--success-color);">${successCount}</span>
                </div>
                <div class="result-info-item">
                    <span class="result-info-label">Enviados al PACS:</span>
                    <span class="result-info-value" style="color: var(--success-color);">${successCount}</span>
                </div>
                ${errorCount > 0 ? `
                <div class="result-info-item">
                    <span class="result-info-label">Con errores:</span>
                    <span class="result-info-value" style="color: var(--error-color);">${errorCount}</span>
                </div>
                ` : ''}
            </div>

            <p style="margin-top: 20px; color: var(--${isSuccess ? 'success' : 'warning'}-color); font-weight: 600;">
                ${isSuccess ? '🎉 Todos los archivos fueron enviados al PACS exitosamente' : '⚠️ Algunos archivos tuvieron errores'}
            </p>
        </div>
    `;
    
    resultContainer.style.display = 'block';
}

// Mostrar error
function showError(message) {
    resultContent.innerHTML = `
        <div class="result-error">
            <div class="result-title">
                <span>❌</span>
                <span>Error</span>
            </div>
            <p style="margin-top: 15px; color: var(--error-color); line-height: 1.6;">${message}</p>
        </div>
    `;
    
    resultContainer.style.display = 'block';
}

// Ocultar resultado
function hideResult() {
    resultContainer.style.display = 'none';
    queueContainer.style.display = 'none';
}

// Cargar lista de archivos
async function loadFiles() {
    console.log('📂 Cargando lista de archivos...');
    
    filesList.innerHTML = '<p class="loading">Cargando archivos...</p>';
    
    try {
        const response = await fetch(`${API_URL}/api/dicom/files`);
        const data = await response.json();
        
        if (data.success && data.data.files.length > 0) {
            displayFiles(data.data.files);
        } else {
            filesList.innerHTML = `
                <div class="empty-state">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    </svg>
                    <p>No hay archivos subidos todavía</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('❌ Error cargando archivos:', error);
        filesList.innerHTML = `
            <p class="loading" style="color: var(--error-color);">
                Error al cargar archivos. Verifica que el servidor esté funcionando.
            </p>
        `;
    }
}

// Mostrar archivos
function displayFiles(files) {
    filesList.innerHTML = files.map(file => `
        <div class="file-item">
            <div class="file-header">
                <span class="file-icon">📄</span>
                <span class="file-name">${file.filename}</span>
            </div>
            <div class="file-meta">
                <span>📦 ${file.size_mb} MB</span>
                <span>🕒 ${formatDate(file.upload_time)}</span>
            </div>
        </div>
    `).join('');
}

// Formatear fecha
function formatDate(isoDate) {
    const date = new Date(isoDate);
    return date.toLocaleString('es-ES', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}
