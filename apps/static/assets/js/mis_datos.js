/**
 * Mis Datos - JavaScript
 * Gestión de datos personales del paciente
 */

// Variable global para almacenar los datos del paciente
let datosPaciente = {};

$(document).ready(function() {
    console.log('[MIS DATOS] Iniciando...');
    cargarDatosPaciente();
    
    // Configurar botón editar
    $('#editar-datos').on('click', editarDatos);
    
    // Configurar cambio de campo en el modal
    $('#campo-a-modificar').on('change', actualizarValorActual);
    
    // Configurar botón enviar solicitud
    $('#btn-enviar-solicitud').on('click', enviarSolicitudCambio);
});

function cargarDatosPaciente() {
    console.log('[MIS DATOS] Cargando datos del paciente...');
    
    fetch('/get_my_patient_data')
        .then(response => response.json())
        .then(data => {
            console.log('[MIS DATOS] Datos recibidos:', data);
            
            if (data.error) {
                console.error('[MIS DATOS] Error en respuesta:', data.error);
                mostrarError(data.error);
                return;
            }
            
            // Guardar datos globalmente
            datosPaciente = data;
            
            renderizarDatos(data);
        })
        .catch(error => {
            console.error('[MIS DATOS] Error en petición:', error);
            mostrarError('No se pudieron cargar tus datos. Por favor, intenta nuevamente.');
        });
}

function renderizarDatos(data) {
    console.log('[MIS DATOS] Renderizando datos del paciente...');
    
    const fullName = `${data.name || ''} ${data.surname || ''}`.trim();
    const genderText = data.gender === 'M' ? 'Masculino' : 
                      data.gender === 'F' ? 'Femenino' : '-';
    
    const html = `
        <!-- Información Personal -->
        <div class="col-12">
            <div class="info-section">
                <div class="section-title">
                    <i class="ni ni-single-02"></i>
                    Información Personal
                </div>
                <div class="info-grid">
                    <div class="info-field">
                        <span class="info-label">Nombre Completo</span>
                        <div class="info-value">
                            <i class="ni ni-circle-08"></i>
                            <span>${fullName || '-'}</span>
                        </div>
                    </div>
                    
                    <div class="info-field">
                        <span class="info-label">DNI</span>
                        <div class="info-value">
                            <i class="ni ni-badge"></i>
                            <span>${data.nationalcode || '-'}</span>
                        </div>
                    </div>
                    
                    <div class="info-field">
                        <span class="info-label">Fecha de Nacimiento</span>
                        <div class="info-value">
                            <i class="ni ni-calendar-grid-58"></i>
                            <span>${data.birthdate || '-'}</span>
                        </div>
                    </div>
                    
                    <div class="info-field">
                        <span class="info-label">Género</span>
                        <div class="info-value">
                            <i class="ni ni-user-run"></i>
                            <span>${genderText}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Información de Contacto -->
        <div class="col-12">
            <div class="info-section">
                <div class="section-title">
                    <i class="ni ni-email-83"></i>
                    Información de Contacto
                </div>
                <div class="info-grid">
                    <div class="info-field">
                        <span class="info-label">Teléfono</span>
                        <div class="info-value">
                            <i class="ni ni-mobile-button"></i>
                            <span>${data.phone || '-'}</span>
                        </div>
                    </div>
                    
                    <div class="info-field">
                        <span class="info-label">Celular</span>
                        <div class="info-value">
                            <i class="ni ni-mobile-button"></i>
                            <span>${data.cellphone || '-'}</span>
                        </div>
                    </div>
                    
                    <div class="info-field">
                        <span class="info-label">Email</span>
                        <div class="info-value">
                            <i class="ni ni-email-83"></i>
                            <span>${data.email || '-'}</span>
                        </div>
                    </div>
                    
                    <div class="info-field">
                        <span class="info-label">Dirección</span>
                        <div class="info-value">
                            <i class="ni ni-pin-3"></i>
                            <span>${data.address || '-'}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Información de Obra Social -->
        <div class="col-12">
            <div class="info-section">
                <div class="section-title">
                    <i class="ni ni-world-2"></i>
                    Obra Social
                </div>
                <div class="info-grid">
                    <div class="info-field">
                        <span class="info-label">Obra Social</span>
                        <div class="info-value">
                            <i class="ni ni-building"></i>
                            <span>${data.healthinsurance || '-'}</span>
                        </div>
                    </div>
                    
                    <div class="info-field">
                        <span class="info-label">Número de Afiliado</span>
                        <div class="info-value">
                            <i class="ni ni-collection"></i>
                            <span>${data.healthinsurance_number || '-'}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Usuario del Sistema -->
        <div class="col-12">
            <div class="info-section">
                <div class="section-title">
                    <i class="ni ni-lock-circle-open"></i>
                    Información de Usuario
                </div>
                <div class="info-grid">
                    <div class="info-field">
                        <span class="info-label">Nombre de Usuario</span>
                        <div class="info-value">
                            <i class="ni ni-circle-08"></i>
                            <span>${data.username || '-'}</span>
                        </div>
                    </div>
                    
                    <div class="info-field">
                        <span class="info-label">Estado de Usuario</span>
                        <div class="info-value">
                            <i class="ni ni-check-bold"></i>
                            <span>${data.status === 'Active' || data.status === 'active' || data.status === 1 ? 'Activo' : 'Inactivo'}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    $('#datos-paciente').html(html);
}

function editarDatos() {
    console.log('[MIS DATOS] Abriendo modal de solicitud de cambio...');
    
    // Resetear formulario
    $('#formSolicitudCambio')[0].reset();
    $('#valor-actual').val('');
    
    // Precargar email de contacto
    if (datosPaciente.email) {
        $('#email-contacto').val(datosPaciente.email);
    }
    
    // Abrir modal
    const modal = new bootstrap.Modal(document.getElementById('modalSolicitudCambio'));
    modal.show();
}

function actualizarValorActual() {
    const campo = $('#campo-a-modificar').val();
    let valorActual = '';
    
    const fullName = `${datosPaciente.name || ''} ${datosPaciente.surname || ''}`.trim();
    
    switch(campo) {
        case 'nombre':
            valorActual = fullName;
            break;
        case 'telefono':
            valorActual = datosPaciente.phone || '';
            break;
        case 'celular':
            valorActual = datosPaciente.cellphone || '';
            break;
        case 'email':
            valorActual = datosPaciente.email || '';
            break;
        case 'direccion':
            valorActual = datosPaciente.address || '';
            break;
        case 'obra_social':
            valorActual = datosPaciente.healthinsurance || '';
            break;
        case 'numero_afiliado':
            valorActual = datosPaciente.healthinsurance_number || '';
            break;
        default:
            valorActual = '';
    }
    
    $('#valor-actual').val(valorActual);
    $('#nuevo-valor').val('').focus();
}

function enviarSolicitudCambio() {
    console.log('[MIS DATOS] Validando solicitud de cambio...');
    
    // Validar formulario
    const campo = $('#campo-a-modificar').val();
    const valorActual = $('#valor-actual').val();
    const nuevoValor = $('#nuevo-valor').val().trim();
    const motivo = $('#motivo-cambio').val().trim();
    const emailContacto = $('#email-contacto').val().trim();
    
    if (!campo || !nuevoValor || !motivo || !emailContacto) {
        showAlertToast('Campos Incompletos', 'Por favor completa todos los campos obligatorios.');
        return;
    }
    
    if (nuevoValor === valorActual) {
        showAlertToast('Sin Cambios', 'El nuevo valor es igual al actual. No hay cambios que solicitar.');
        return;
    }
    
    // Deshabilitar botón y mostrar loading
    const btnEnviar = $('#btn-enviar-solicitud');
    const originalHTML = btnEnviar.html();
    btnEnviar.html('<i class="fa fa-spinner fa-spin"></i> Enviando...').prop('disabled', true);
    
    // Preparar datos de la solicitud
    const solicitud = {
        campo: campo,
        valor_actual: valorActual,
        nuevo_valor: nuevoValor,
        motivo: motivo,
        email_contacto: emailContacto,
        paciente_username: datosPaciente.username,
        paciente_nombre: `${datosPaciente.name || ''} ${datosPaciente.surname || ''}`.trim()
    };
    
    console.log('[MIS DATOS] Enviando solicitud:', solicitud);
    
    // Enviar solicitud al backend
    fetch('/request_patient_data_change', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(solicitud)
    })
    .then(response => response.json())
    .then(data => {
        btnEnviar.html(originalHTML).prop('disabled', false);
        
        if (data.success) {
            // Cerrar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('modalSolicitudCambio'));
            modal.hide();
            
            // Mostrar mensaje de éxito con toast
            showSuccessToast(
                '¡Solicitud Enviada!', 
                'Tu solicitud ha sido registrada y será revisada por el administrador. Te contactaremos al email proporcionado.'
            );
            
            // Resetear formulario
            $('#formSolicitudCambio')[0].reset();
        } else {
            showErrorToast('Error', data.error || 'Error desconocido al enviar la solicitud.');
        }
    })
    .catch(error => {
        console.error('[MIS DATOS] Error enviando solicitud:', error);
        btnEnviar.html(originalHTML).prop('disabled', false);
        showErrorToast('Error de Conexión', 'Ocurrió un error al enviar la solicitud. Por favor, intenta nuevamente.');
    });
}

function mostrarError(mensaje) {
    const html = `
        <div class="col-12 text-center py-5">
            <i class="fa fa-exclamation-triangle text-danger" style="font-size: 3rem;"></i>
            <p class="text-danger mt-3">${mensaje}</p>
            <button class="btn btn-primary mt-3" onclick="location.reload()">
                <i class="fa fa-refresh"></i> Reintentar
            </button>
        </div>
    `;
    $('#datos-paciente').html(html);
}
