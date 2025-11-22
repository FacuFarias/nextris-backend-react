/**
 * Mis Estudios - JavaScript
 * Gestión de estudios médicos para pacientes
 */

$(document).ready(function() {
    console.log('[MIS ESTUDIOS] Iniciando...');
    
    // Configurar tabla y rellenar con datos
    ConfigurarTabla('tabla-estudios', 'botones_hp');
    cargarEstudiosDelPaciente();
    
    // Configurar botones
    $('#ver-informe').on('click', verInforme);
    $('#ver-imagen').on('click', verImagen);
    $('#enviar-medico').on('click', enviarAMedicoReferente);
    
});

function verInforme() {
    const tabla = document.getElementById('tabla-estudios');
    const tbody = tabla.querySelector('tbody');
    const filaSeleccionada = tbody.querySelector('.fila-seleccionada');
    
    if (filaSeleccionada) {
        const guid = filaSeleccionada.getAttribute('data-id');
        const hasReport = filaSeleccionada.getAttribute('data-has-report') === 'true';
        
        console.log('[MIS ESTUDIOS] Ver informe - GUID:', guid, 'Has report:', hasReport);
        
        if (hasReport && guid) {
            VerPDF(guid);
        } else {
            alert('Este estudio no tiene informe disponible.');
        }
    } else {
        alert('Por favor, selecciona un estudio primero.');
    }
}

function verImagen() {
    const tabla = document.getElementById('tabla-estudios');
    const tbody = tabla.querySelector('tbody');
    const filaSeleccionada = tbody.querySelector('.fila-seleccionada');
    
    if (filaSeleccionada) {
        const guid = filaSeleccionada.getAttribute('data-id');
        const hasImage = filaSeleccionada.getAttribute('data-has-image') === 'true';
        
        console.log('[MIS ESTUDIOS] Ver imagen - GUID:', guid, 'Has image:', hasImage);
        
        if (hasImage && guid) {
            obtenerUrlVisorDicom(function(viewerUrl) {
                VerImagenes(guid);
            });
        } else {
            alert('Este estudio no tiene imágenes disponibles.');
        }
    } else {
        alert('Por favor, selecciona un estudio primero.');
    }
}

function enviarAMedicoReferente() {
    const tabla = document.getElementById('tabla-estudios');
    const tbody = tabla.querySelector('tbody');
    const filaSeleccionada = tbody.querySelector('.fila-seleccionada');
    
    if (!filaSeleccionada) {
        alert('Por favor, selecciona un estudio primero.');
        return;
    }
    
    const guid = filaSeleccionada.getAttribute('data-id');
    const hasReport = filaSeleccionada.getAttribute('data-has-report') === 'true';
    
    if (!hasReport) {
        alert('Este estudio aún no tiene informe finalizado para enviar.');
        return;
    }
    
    // Obtener información del estudio de las celdas
    const celdas = filaSeleccionada.querySelectorAll('td');
    const estudio = celdas[0].textContent.trim();
    const medicoReferente = celdas[2].textContent.trim();
    
    if (!medicoReferente || medicoReferente === '-') {
        alert('Este estudio no tiene un médico referente asignado.');
        return;
    }
    
    const confirmar = confirm(`¿Deseas enviar el informe de "${estudio}" al Dr./Dra. ${medicoReferente}?`);
    
    if (confirmar) {
        console.log('[MIS ESTUDIOS] Enviando estudio al médico referente - GUID:', guid);
        
        // Mostrar loader
        const btnEnviar = document.getElementById('enviar-medico');
        const originalHTML = btnEnviar.innerHTML;
        btnEnviar.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Enviando...';
        btnEnviar.disabled = true;
        
        fetch('/send_report_to_referring_physician', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                exam_guid: guid
            })
        })
        .then(response => response.json())
        .then(data => {
            btnEnviar.innerHTML = originalHTML;
            
            if (data.success) {
                alert(`Informe enviado exitosamente al Dr./Dra. ${medicoReferente}`);
            } else {
                alert(`Error al enviar el informe: ${data.error || 'Error desconocido'}`);
            }
        })
        .catch(error => {
            console.error('[MIS ESTUDIOS] Error enviando informe:', error);
            btnEnviar.innerHTML = originalHTML;
            alert('Ocurrió un error al enviar el informe. Por favor, intenta nuevamente.');
        });
    }
}

function cargarEstudiosDelPaciente() {
    console.log('[MIS ESTUDIOS] Cargando estudios del paciente...');
    
    fetch('/get_patient_studies')
        .then(response => response.json())
        .then(data => {
            console.log('[MIS ESTUDIOS] Respuesta recibida:', data);
            
            if (data.error) {
                console.error('[MIS ESTUDIOS] Error en respuesta:', data.error);
                mostrarError(data.error);
                return;
            }
            
            const studies = data.studies || [];
            console.log('[MIS ESTUDIOS] Estudios encontrados:', studies.length);
            
            if (studies.length === 0) {
                mostrarTablaVacia();
                return;
            }
            
            // Renderizar estudios directamente
            renderizarEstudios(studies);
        })
        .catch(error => {
            console.error('[MIS ESTUDIOS] Error en petición:', error);
            mostrarError('No se pudieron cargar los estudios. Por favor, intenta nuevamente.');
        });
}

function obtenerUrlVisorDicom(callback) {
    fetch('/get_dicom_viewer_url')
        .then(response => response.json())
        .then(data => {
            const viewerUrl = data.url || 'http://192.168.1.45:8085/viewer.html';
            callback(viewerUrl);
        })
        .catch(error => {
            console.error('[MIS ESTUDIOS] Error obteniendo URL del visor:', error);
            callback('http://192.168.1.45:8085/viewer.html'); // URL por defecto
        });
}

function renderizarEstudios(studies) {
    console.log('[MIS ESTUDIOS] Renderizando', studies.length, 'estudios');
    
    const tbody = $('#tabla-estudios tbody');
    tbody.empty();
    
    studies.forEach(study => {
        const hasReport = study.informe_finalizado ? true : false;
        const hasImage = study.has_dicom ? true : false;
        
        const row = `
            <tr data-id="${study.guid}" 
                data-has-report="${hasReport}" 
                data-has-image="${hasImage}">
                <td>${study.exam_description || 'Sin descripción'}</td>
                <td class="d-none d-md-table-cell">${study.medico_autor || '-'}</td>
                <td class="d-none d-lg-table-cell">${study.medico_referente || '-'}</td>
                <td>${study.fecha || '-'}</td>
                <td class="d-none d-md-table-cell">${study.modalidad || '-'}</td>
                <td class="d-none d-lg-table-cell">
                    <span class="badge badge-sm ${getStatusClass(study.status)}">
                        ${study.status || 'Pendiente'}
                    </span>
                </td>
                <td class="d-none d-lg-table-cell text-center">
                    ${hasReport ? '<i class="fa fa-check text-success"></i>' : '<i class="fa fa-times text-danger"></i>'}
                </td>
                <td class="d-none d-lg-table-cell text-center">
                    ${hasImage ? '<i class="fa fa-check text-success"></i>' : '<i class="fa fa-times text-danger"></i>'}
                </td>
            </tr>
        `;
        tbody.append(row);
    });
}

function getStatusClass(status) {
    if (!status) return 'bg-secondary';
    
    const statusLower = status.toLowerCase();
    if (statusLower.includes('finalizado') || statusLower.includes('completed')) {
        return 'bg-success';
    } else if (statusLower.includes('proceso') || statusLower.includes('progress')) {
        return 'bg-info';
    } else if (statusLower.includes('pendiente') || statusLower.includes('pending')) {
        return 'bg-warning';
    } else {
        return 'bg-secondary';
    }
}

function mostrarTablaVacia() {
    const tbody = $('#tabla-estudios tbody');
    tbody.html(`
        <tr>
            <td colspan="8" class="text-center py-5">
                <i class="ni ni-folder-17 text-muted" style="font-size: 3rem;"></i>
                <p class="text-muted mt-3">No tienes estudios registrados</p>
                <small class="text-muted">Cuando tengas estudios realizados, aparecerán aquí.</small>
            </td>
        </tr>
    `);
}

function mostrarError(mensaje) {
    const tbody = $('#tabla-estudios tbody');
    tbody.html(`
        <tr>
            <td colspan="8" class="text-center py-5">
                <i class="fa fa-exclamation-triangle text-danger" style="font-size: 3rem;"></i>
                <p class="text-danger mt-3">${mensaje}</p>
            </td>
        </tr>
    `);
}

// ==================== MODAL DE CAMBIO DE CONTRASEÑA ====================

document.addEventListener('DOMContentLoaded', function() {
    // Verificar si se requiere cambio de contraseña
    const modalElement = document.getElementById('changePasswordModal');
    if (!modalElement) return; // Si no existe el modal, salir
    
    const requiresPasswordChange = modalElement.getAttribute('data-requires-change') === 'true';
    
    console.log('[PASSWORD MODAL] data-requires-change:', modalElement.getAttribute('data-requires-change'));
    console.log('[PASSWORD MODAL] requiresPasswordChange:', requiresPasswordChange);
    
    if (requiresPasswordChange) {
        console.log('[PASSWORD MODAL] Mostrando modal automáticamente');
        // Mostrar modal automáticamente
        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    } else {
        console.log('[PASSWORD MODAL] No se requiere cambio de contraseña');
    }
    
    // Toggle para mostrar/ocultar contraseñas
    document.getElementById('toggleNewPassword').addEventListener('click', function() {
        const input = document.getElementById('newPassword');
        const icon = this.querySelector('i');
        if (input.type === 'password') {
            input.type = 'text';
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
        } else {
            input.type = 'password';
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
        }
    });
    
    document.getElementById('toggleConfirmPassword').addEventListener('click', function() {
        const input = document.getElementById('confirmPassword');
        const icon = this.querySelector('i');
        if (input.type === 'password') {
            input.type = 'text';
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
        } else {
            input.type = 'password';
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
        }
    });
    
    // Manejar envío del formulario
    document.getElementById('savePasswordBtn').addEventListener('click', function() {
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        const alertDiv = document.getElementById('passwordAlert');
        
        // Limpiar alertas previas
        alertDiv.className = 'alert d-none';
        alertDiv.innerHTML = '';
        
        // Validaciones
        if (!newPassword || !confirmPassword) {
            showPasswordAlert('Todos los campos son requeridos', 'danger');
            return;
        }
        
        if (newPassword.length < 4) {
            showPasswordAlert('La contraseña debe tener al menos 4 caracteres', 'danger');
            return;
        }
        
        if (newPassword === '1234' || newPassword === 'next') {
            showPasswordAlert('No puedes usar contraseñas temporales', 'danger');
            return;
        }
        
        if (newPassword !== confirmPassword) {
            showPasswordAlert('Las contraseñas no coinciden', 'danger');
            return;
        }
        
        // Deshabilitar botón durante el envío
        this.disabled = true;
        this.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Cambiando...';
        
        // Enviar solicitud
        fetch('/change-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                new_password: newPassword,
                confirm_password: confirmPassword
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showPasswordAlert(data.message, 'success');
                setTimeout(() => {
                    // Cerrar modal y recargar página
                    const modal = bootstrap.Modal.getInstance(document.getElementById('changePasswordModal'));
                    modal.hide();
                    location.reload();
                }, 2000);
            } else {
                showPasswordAlert(data.message, 'danger');
                // Rehabilitar botón
                this.disabled = false;
                this.innerHTML = '<i class="ni ni-check-bold me-1"></i>Cambiar Contraseña';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showPasswordAlert('Error de conexión. Intenta nuevamente.', 'danger');
            // Rehabilitar botón
            this.disabled = false;
            this.innerHTML = '<i class="ni ni-check-bold me-1"></i>Cambiar Contraseña';
        });
    });
    
    function showPasswordAlert(message, type) {
        const alertDiv = document.getElementById('passwordAlert');
        alertDiv.className = `alert alert-${type}`;
        alertDiv.innerHTML = `<i class="ni ni-notification-70 me-2"></i>${message}`;
        alertDiv.classList.remove('d-none');
    }
});
