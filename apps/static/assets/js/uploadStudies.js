/**
 * Upload Studies - JavaScript Application
 * Maneja la carga de archivos DICOM y su envío al PACS
 */

// Configuración API
const API_URL = window.location.origin;

// DOM Elements
const dropZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
const selectFilesBtn = document.getElementById('select-files-btn');
const progressContainer = document.getElementById('progress-container');
const progressBar = document.getElementById('progress-bar');
const progressText = document.getElementById('progress-text');
const progressDetails = document.getElementById('progress-details');
const queueContainer = document.getElementById('queue-container');
const queueList = document.getElementById('queue-list');
const resultContainer = document.getElementById('result-container');
const resultContent = document.getElementById('result-content');
const filesList = document.getElementById('files-list');
const refreshBtn = document.getElementById('refresh-btn');

// Estado de la aplicación
let isUploading = false;
let uploadQueue = [];
let currentUploadIndex = 0;
let successCount = 0;
let errorCount = 0;

/**
 * Inicialización del módulo
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('🏥 Upload Studies - Módulo iniciado');
    initializeEventListeners();
    loadUploadedFiles();
    
    // Inicializar funcionalidad de vinculación si estamos en ese tab
    const linkTab = document.getElementById('content-link');
    if (linkTab && linkTab.classList.contains('active')) {
        initLinkFunctionality();
    }
});

/**
 * Inicializar event listeners
 */
function initializeEventListeners() {
    // Botón seleccionar archivos
    if (selectFilesBtn) {
        selectFilesBtn.addEventListener('click', () => {
            fileInput.click();
        });
    }

    // Cambio en input de archivo
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFiles(Array.from(e.target.files));
            }
        });
    }

    // Drag and Drop en zona de carga
    if (dropZone) {
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
    }

    // Botón de refresh
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadUploadedFiles();
        });
    }
}

/**
 * Manejar múltiples archivos seleccionados
 */
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

    // Mostrar archivos rechazados
    if (invalidFiles.length > 0) {
        showError(`❌ Archivos rechazados (no son DICOM):<br><br>${invalidFiles.join('<br>')}`);
    }

    // Validar que hay archivos válidos
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

/**
 * Iniciar subida en lote de archivos
 */
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
            console.error(`Error uploading ${file.name}:`, error);
        }
    }

    // Finalizar
    isUploading = false;
    hideProgress();
    showBatchSummary();
    loadUploadedFiles(); // Recargar lista de archivos
    fileInput.value = ''; // Limpiar input
}

/**
 * Subir un archivo individual
 */
async function uploadFile(file) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();

        // Evento de carga completada
        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    console.log('✅ Upload exitoso:', file.name);
                    console.log('   DICOM Info:', response.data?.dicom_info);
                    console.log('   PACS Status:', response.data?.pacs_status);
                    resolve(response);
                } catch (e) {
                    reject(new Error('Error al parsear respuesta del servidor'));
                }
            } else {
                try {
                    const error = JSON.parse(xhr.responseText);
                    console.error('❌ Error en upload:', file.name, error);
                    reject(new Error(error.error || 'Error desconocido'));
                } catch (e) {
                    reject(new Error(`Error HTTP ${xhr.status}`));
                }
            }
        });

        // Evento de error de red
        xhr.addEventListener('error', () => {
            console.error('❌ Error de red:', file.name);
            reject(new Error('Error de conexión'));
        });

        // Abrir conexión y enviar
        xhr.open('POST', `${API_URL}/api/dicom/upload`);
        xhr.send(formData);
    });
}

/**
 * Actualizar barra de progreso
 */
function updateProgress(current, total) {
    const percent = Math.round(((current + 1) / total) * 100);
    if (progressBar) {
        progressBar.style.width = `${percent}%`;
    }
    if (progressText) {
        progressText.textContent = `Procesando archivos... ${current + 1}/${total}`;
    }
    if (progressDetails) {
        progressDetails.textContent = `${successCount} exitosos, ${errorCount} errores`;
    }
}

/**
 * Mostrar contenedor de progreso
 */
function showProgress() {
    if (progressContainer) {
        progressContainer.style.display = 'block';
        if (progressBar) progressBar.style.width = '0%';
        if (progressText) progressText.textContent = 'Iniciando...';
        if (progressDetails) progressDetails.textContent = '';
    }
}

/**
 * Ocultar contenedor de progreso
 */
function hideProgress() {
    setTimeout(() => {
        if (progressContainer) {
            progressContainer.style.display = 'none';
        }
    }, 1000);
}

/**
 * Mostrar cola de archivos
 */
function showQueue() {
    if (!queueContainer || !queueList) return;
    
    queueContainer.style.display = 'block';
    queueList.innerHTML = uploadQueue.map((file, index) => `
        <div class="queue-item" id="queue-item-${index}">
            <span class="queue-item-name">📄 ${file.name}</span>
            <span class="queue-item-status">⏳ En espera</span>
        </div>
    `).join('');
    
    showProgress();
}

/**
 * Actualizar estado de un item en la cola
 */
function updateQueueItem(index, status, message) {
    const item = document.getElementById(`queue-item-${index}`);
    if (item) {
        item.className = `queue-item ${status}`;
        const statusSpan = item.querySelector('.queue-item-status');
        if (statusSpan) {
            statusSpan.textContent = message;
        }
    }
}

/**
 * Mostrar resumen del proceso de carga
 */
function showBatchSummary() {
    if (!resultContent || !resultContainer) return;
    
    const total = uploadQueue.length;
    const isSuccess = errorCount === 0;
    const isPartial = successCount > 0 && errorCount > 0;
    const resultType = isSuccess ? 'success' : (isPartial ? 'warning' : 'error');
    
    resultContent.innerHTML = `
        <div class="result-${resultType}">
            <div class="result-title">
                <span>${isSuccess ? '✅' : (isPartial ? '⚠️' : '❌')}</span>
                <span>Proceso completado</span>
            </div>
            
            <div class="result-info">
                <div class="result-info-item">
                    <span class="result-info-label">Total de archivos:</span>
                    <span class="result-info-value">${total}</span>
                </div>
                <div class="result-info-item">
                    <span class="result-info-label">Subidos exitosamente:</span>
                    <span class="result-info-value" style="color: #10b981;">${successCount}</span>
                </div>
                <div class="result-info-item">
                    <span class="result-info-label">Enviados al PACS:</span>
                    <span class="result-info-value" style="color: #10b981;">${successCount}</span>
                </div>
                ${errorCount > 0 ? `
                <div class="result-info-item">
                    <span class="result-info-label">Con errores:</span>
                    <span class="result-info-value" style="color: #ef4444;">${errorCount}</span>
                </div>
                ` : ''}
            </div>

            <p style="margin-top: 20px; font-weight: 600; color: ${isSuccess ? '#10b981' : '#f59e0b'};">
                ${isSuccess 
                    ? '🎉 Todos los archivos fueron enviados al PACS exitosamente' 
                    : isPartial
                        ? '⚠️ Algunos archivos tuvieron errores durante el envío'
                        : '❌ No se pudieron enviar los archivos al PACS'
                }
            </p>
        </div>
    `;
    
    resultContainer.style.display = 'block';
}

/**
 * Mostrar mensaje de error
 */
function showError(message) {
    if (!resultContent || !resultContainer) return;
    
    resultContent.innerHTML = `
        <div class="result-error">
            <div class="result-title">
                <span>❌</span>
                <span>Error</span>
            </div>
            <p style="margin-top: 15px; color: #ef4444; line-height: 1.6;">${message}</p>
        </div>
    `;
    
    resultContainer.style.display = 'block';
}

/**
 * Ocultar contenedor de resultados
 */
function hideResult() {
    if (resultContainer) resultContainer.style.display = 'none';
    if (queueContainer) queueContainer.style.display = 'none';
}

/**
 * Cargar lista de archivos DICOM subidos
 */
async function loadUploadedFiles() {
    if (!filesList) return;
    
    console.log('📂 Cargando lista de archivos subidos...');
    
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
                    <p>No hay archivos DICOM subidos todavía</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('❌ Error cargando archivos:', error);
        filesList.innerHTML = `
            <p class="loading" style="color: #ef4444;">
                Error al cargar archivos. Verifica que el servidor esté funcionando.
            </p>
        `;
    }
}

/**
 * Mostrar lista de archivos
 */
function displayFiles(files) {
    if (!filesList) return;
    
    filesList.innerHTML = files.map(file => {
        const dicomInfo = file.dicom_info;
        const hasInfo = dicomInfo && dicomInfo.patient_name !== 'Unknown';
        
        return `
            <div class="file-item">
                <div class="file-header">
                    <span class="file-icon">📄</span>
                    <span class="file-name">${file.filename}</span>
                </div>
                <div class="file-meta">
                    <span>📦 ${file.size_mb} MB</span>
                    <span>🕒 ${formatDate(file.upload_time)}</span>
                    ${hasInfo ? `
                        <span>👤 ${dicomInfo.patient_name}</span>
                        <span>🏥 ${dicomInfo.modality}</span>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Formatear fecha para visualización
 */
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

/**
 * Utilidad para mostrar notificaciones toast (opcional)
 */
function showToast(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
    // Aquí puedes implementar un sistema de notificaciones toast si lo deseas
}

/**
 * ============================================================================
 * VINCULACIÓN DE ESTUDIOS - Pestaña "Vincular Imagen"
 * ============================================================================
 */

// Variables globales para vinculación
let selectedUploadGuid = null;
let selectedExamGuid = null;
let unlinkedStudies = [];
let examsWithoutImage = [];

/**
 * Inicializar funcionalidad de vinculación
 */
function initLinkFunctionality() {
    const btnRefreshUnlinked = document.getElementById('btn-refresh-unlinked');
    const btnRefreshExams = document.getElementById('btn-refresh-exams');
    const btnSearchExams = document.getElementById('btn-search-exams');
    const btnLinkSelected = document.getElementById('btn-link-selected');

    if (btnRefreshUnlinked) {
        btnRefreshUnlinked.addEventListener('click', loadUnlinkedStudies);
    }

    if (btnRefreshExams) {
        btnRefreshExams.addEventListener('click', () => loadExamsWithoutImage());
    }

    if (btnSearchExams) {
        btnSearchExams.addEventListener('click', searchExams);
    }

    if (btnLinkSelected) {
        btnLinkSelected.addEventListener('click', linkSelectedStudy);
    }

    // Cargar datos iniciales
    loadUnlinkedStudies();
    loadExamsWithoutImage();
}

/**
 * Cargar estudios no vinculados de tbmanual_uploads
 */
async function loadUnlinkedStudies() {
    try {
        const response = await fetch(`${API_URL}/api/dicom/unlinked-studies`);
        const data = await response.json();

        if (data.success) {
            unlinkedStudies = data.data.data;
            renderUnlinkedStudies(unlinkedStudies);
            document.getElementById('unlinked-count').textContent = unlinkedStudies.length;
        } else {
            showError('Error al cargar estudios no vinculados: ' + data.error);
        }
    } catch (error) {
        console.error('Error loading unlinked studies:', error);
        showError('Error de conexión al cargar estudios no vinculados');
    }
}

/**
 * Renderizar tabla de estudios no vinculados
 */
function renderUnlinkedStudies(studies) {
    const tbody = document.getElementById('unlinked-tbody');
    
    if (!studies || studies.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center text-muted py-4">
                    <i class="ni ni-fat-remove"></i><br>
                    No hay estudios sin vincular
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = studies.map((study, index) => `
        <tr class="study-row" data-guid="${study.guid}">
            <td>
                <input type="radio" name="selected-upload" value="${study.guid}" 
                       class="form-check-input upload-radio">
            </td>
            <td>
                <div class="fw-bold text-sm">${study.patient_name || 'N/A'}</div>
                <div class="text-xs text-muted">${study.patient_id || ''}</div>
            </td>
            <td><span class="badge badge-sm bg-primary">${study.modality || 'N/A'}</span></td>
            <td class="text-sm">${formatDate(study.study_date)}</td>
            <td>
                <span class="badge badge-sm ${study.pacs_status === 'success' ? 'bg-success' : 'bg-warning'}">
                    ${study.pacs_status === 'success' ? 'OK' : 'Pendiente'}
                </span>
            </td>
        </tr>
    `).join('');

    // Agregar eventos a los radios
    document.querySelectorAll('.upload-radio').forEach(radio => {
        radio.addEventListener('change', (e) => {
            selectedUploadGuid = e.target.value;
            updateLinkButton();
            showSelectionInfo();
        });
    });
}

/**
 * Cargar exámenes sin imagen (isimage = 0)
 */
async function loadExamsWithoutImage(searchParams = {}) {
    try {
        const params = new URLSearchParams(searchParams);
        const response = await fetch(`${API_URL}/api/dicom/search-examinations?${params}`);
        const data = await response.json();

        if (data.success) {
            examsWithoutImage = data.data.data;
            renderExamsWithoutImage(examsWithoutImage);
            document.getElementById('exams-count').textContent = examsWithoutImage.length;
        } else {
            showError('Error al cargar órdenes: ' + data.error);
        }
    } catch (error) {
        console.error('Error loading exams:', error);
        showError('Error de conexión al cargar órdenes');
    }
}

/**
 * Renderizar tabla de exámenes sin imagen
 */
function renderExamsWithoutImage(exams) {
    const tbody = document.getElementById('exams-tbody');
    
    if (!exams || exams.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center text-muted py-4">
                    <i class="ni ni-fat-remove"></i><br>
                    No hay órdenes sin imagen
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = exams.map(exam => `
        <tr class="exam-row" data-guid="${exam.guid}">
            <td>
                <input type="radio" name="selected-exam" value="${exam.guid}" 
                       class="form-check-input exam-radio">
            </td>
            <td>
                <div class="fw-bold text-sm">${exam.patient_name || 'N/A'}</div>
                <div class="text-xs text-muted">${exam.patient_id || ''}</div>
            </td>
            <td class="text-xs">${exam.study_type || 'N/A'}</td>
            <td class="text-sm">${exam.accession || 'N/A'}</td>
            <td class="text-sm">${formatDate(exam.date)}</td>
        </tr>
    `).join('');

    // Agregar eventos a los radios
    document.querySelectorAll('.exam-radio').forEach(radio => {
        radio.addEventListener('change', (e) => {
            selectedExamGuid = e.target.value;
            updateLinkButton();
            showSelectionInfo();
        });
    });
}

/**
 * Buscar exámenes con filtros
 */
function searchExams() {
    const patientName = document.getElementById('exam-search-name').value;
    const patientDni = document.getElementById('exam-search-dni').value;

    const searchParams = {};
    if (patientName) searchParams.patient_name = patientName;
    if (patientDni) searchParams.patient_id = patientDni;

    loadExamsWithoutImage(searchParams);
}

/**
 * Actualizar estado del botón de vincular
 */
function updateLinkButton() {
    const btnLink = document.getElementById('btn-link-selected');
    if (selectedUploadGuid && selectedExamGuid) {
        btnLink.disabled = false;
        btnLink.classList.remove('btn-secondary');
        btnLink.classList.add('btn-success');
    } else {
        btnLink.disabled = true;
        btnLink.classList.remove('btn-success');
        btnLink.classList.add('btn-secondary');
    }
}

/**
 * Mostrar información de la selección
 */
function showSelectionInfo() {
    const infoDiv = document.getElementById('link-selection-info');
    const uploadInfo = document.getElementById('selected-upload-info');
    const examInfo = document.getElementById('selected-exam-info');

    if (selectedUploadGuid && selectedExamGuid) {
        const upload = unlinkedStudies.find(s => s.guid === selectedUploadGuid);
        const exam = examsWithoutImage.find(e => e.guid === selectedExamGuid);

        if (upload && exam) {
            uploadInfo.innerHTML = `
                <strong>${upload.patient_name}</strong><br>
                Modalidad: ${upload.modality} | Fecha: ${formatDate(upload.study_date)}
            `;
            examInfo.innerHTML = `
                <strong>${exam.patient_name}</strong><br>
                ${exam.study_type} | Acc: ${exam.accession}
            `;
            infoDiv.style.display = 'block';
        }
    } else {
        infoDiv.style.display = 'none';
    }
}

/**
 * Vincular estudio seleccionado
 */
async function linkSelectedStudy() {
    if (!selectedUploadGuid || !selectedExamGuid) {
        showError('Debes seleccionar un estudio y una orden');
        return;
    }

    const btnLink = document.getElementById('btn-link-selected');
    btnLink.disabled = true;
    btnLink.innerHTML = '<i class="fa fa-spinner fa-spin me-2"></i> Vinculando...';

    try {
        const response = await fetch(`${API_URL}/api/dicom/link-study`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                upload_guid: selectedUploadGuid,
                examination_guid: selectedExamGuid
            })
        });

        const data = await response.json();
        const resultDiv = document.getElementById('link-result');

        if (data.success) {
            resultDiv.innerHTML = `
                <div class="alert alert-success">
                    <h5><i class="fa fa-check-circle me-2"></i> Vinculación Exitosa</h5>
                    <p class="mb-0">El estudio DICOM ha sido vinculado correctamente con la orden.</p>
                </div>
            `;
            resultDiv.style.display = 'block';

            // Recargar listas
            setTimeout(() => {
                loadUnlinkedStudies();
                loadExamsWithoutImage();
                selectedUploadGuid = null;
                selectedExamGuid = null;
                document.getElementById('link-selection-info').style.display = 'none';
                resultDiv.style.display = 'none';
            }, 2000);
        } else {
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fa fa-exclamation-triangle me-2"></i> Error</h5>
                    <p class="mb-0">${data.error}</p>
                </div>
            `;
            resultDiv.style.display = 'block';
        }
    } catch (error) {
        console.error('Error linking study:', error);
        const resultDiv = document.getElementById('link-result');
        resultDiv.innerHTML = `
            <div class="alert alert-danger">
                <h5><i class="fa fa-exclamation-triangle me-2"></i> Error de Conexión</h5>
                <p class="mb-0">No se pudo conectar con el servidor.</p>
            </div>
        `;
        resultDiv.style.display = 'block';
    } finally {
        btnLink.disabled = false;
        btnLink.innerHTML = '<i class="fa fa-link me-2"></i> Vincular Estudio Seleccionado';
    }
}

/**
 * Formatear fecha para mostrar
 */
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    
    // Si es formato YYYYMMDD
    if (dateString.length === 8 && !dateString.includes('-')) {
        const year = dateString.substring(0, 4);
        const month = dateString.substring(4, 6);
        const day = dateString.substring(6, 8);
        return `${day}/${month}/${year}`;
    }
    
    // Si es formato ISO
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString('es-ES');
    } catch {
        return dateString;
    }
}

// Exportar funciones útiles para uso externo si es necesario
window.UploadStudies = {
    loadFiles: loadUploadedFiles,
    uploadFiles: handleFiles,
    showError: showError,
    initLink: initLinkFunctionality,
    loadUnlinked: loadUnlinkedStudies,
    loadExams: loadExamsWithoutImage
};

console.log('✅ Upload Studies - Módulo cargado correctamente');
