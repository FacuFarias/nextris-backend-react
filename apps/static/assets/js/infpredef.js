function ConfigBtnExpandMulti(activeCardId, btnId, columnContainerId) {
    console.log('[Expand] Params:', {activeCardId, btnId, columnContainerId});
    const column = document.getElementById(columnContainerId);
    if (!column) {
        console.warn('[Expand] No se encontró la columna:', columnContainerId);
        return;
    }
    const activeCard = document.getElementById(activeCardId);
    if (!activeCard) {
        console.warn('[Expand] No se encontró la card:', activeCardId);
    }
    const btn = document.getElementById(btnId);
    if (!btn) {
        console.warn('[Expand] No se encontró el botón:', btnId);
    }
    const iconElement = btn ? btn.querySelector('i') : null;
    const allCards = column.querySelectorAll('.card');

    allCards.forEach(card => {
        if (!card) return;
        const collapseSection = card.querySelector('.collapse');
        const buttonIcon = card.querySelector('button i');

        if (card.id === activeCardId) {
            // Siempre expandir la card seleccionada
            if (collapseSection && !collapseSection.classList.contains('show')) {
                console.log('[Expand] Expandiendo card:', card.id);
                collapseSection.classList.add('show');
            }
            if (iconElement) {
                iconElement.classList.remove('fa-expand-arrows-alt');
                iconElement.classList.add('fa-crosshairs');
            }
            card.classList.add('expand-card');
        } else {
            // Contraer todas las demás
            if (collapseSection && collapseSection.classList.contains('show')) {
                collapseSection.classList.remove('show');
            }
            if (buttonIcon) {
                buttonIcon.classList.remove('fa-crosshairs');
                buttonIcon.classList.add('fa-expand-arrows-alt');
            }
            card.classList.remove('expand-card');
        }
    });
}

function CrearNuevoInformePredef() {
    // Resetear estados de modificación
    resetFormStates();
    
    // Habilitar campos para edición
    document.getElementById('l_title').removeAttribute('disabled');
    document.getElementById('text_hallazgos').removeAttribute('disabled');
    document.getElementById('text_tecnicas').removeAttribute('disabled');
    document.getElementById('text_impresiones').removeAttribute('disabled');
    document.getElementById('text_conclusiones').removeAttribute('disabled');
    document.getElementById('s_tipo_estudio').removeAttribute('disabled');

    // Limpiar los valores
    document.getElementById('l_title').value = '';
    document.getElementById('text_hallazgos').value = '';
    document.getElementById('text_tecnicas').value = '';
    document.getElementById('text_impresiones').value = '';
    document.getElementById('text_conclusiones').value = '';
    document.getElementById('s_tipo_estudio').selectedIndex = 0;

    // Estilo visual opcional
    document.getElementById('l_title').style.backgroundColor = '#fff3cd'; // amarillo suave

    // Marcar estado de creación
    const botonGuardar = document.getElementById('b_guardar_predef');
    botonGuardar.setAttribute('data-status', 'new');
    botonGuardar.removeAttribute('data-id');
    botonGuardar.removeAttribute('disabled');

    // Verificar si el tipo de estudio seleccionado tiene default_predef_id no nulo
    const chkDefault = document.getElementById('chk_default_report');
    chkDefault.checked = false;
    chkDefault.removeAttribute('disabled');

    // Si hay select, verificar el valor actual
    const selectEstudio = document.getElementById('s_tipo_estudio');
    let tipoEstudioId = selectEstudio.value;
    if (!tipoEstudioId) {
        tipoEstudioId = selectEstudio.options[0]?.value;
    }
    if (tipoEstudioId) {
        fetch(`/api/isstudytype/${tipoEstudioId}/default_predef_id`)
            .then(res => res.json())
            .then(data => {
                if (data.default_predef_id) {
                    chkDefault.setAttribute('disabled', true);
                    chkDefault.checked = true;
                } else {
                    chkDefault.removeAttribute('disabled');
                    chkDefault.checked = false;
                }
            })
            .catch(() => {
                chkDefault.removeAttribute('disabled');
                chkDefault.checked = false;
            });
    }else {
        console.error('No se pudo obtener el tipo de estudio seleccionado');
    }
}

function flashCards() {
    const cards = document.querySelectorAll('.card.bg-green');

    cards.forEach(card => {
        card.classList.remove('bg-green'); // quitar verde
        card.classList.add('bg-purple-flash'); // agregar morado

        setTimeout(() => {
            card.classList.remove('bg-purple-flash'); // volver a blanco (por defecto)
        }, 1000);
    });
}

// Estado para saber si l_title fue modificado
let lTitleChanged = false;

function resetFormStates() {
    // Resetear el estado de título cambiado
    lTitleChanged = false;
    
    // Remover la clase field-modified de todos los campos
    const modifiedFields = document.querySelectorAll('.field-modified');
    modifiedFields.forEach(field => {
        field.classList.remove('field-modified');
    });
    
    // Remover la clase campo-error de todos los campos
    const errorFields = document.querySelectorAll('.campo-error');
    errorFields.forEach(field => {
        field.classList.remove('campo-error');
    });
    
    // Deshabilitar el botón guardar
    document.getElementById('b_guardar_predef').setAttribute('disabled', 'disabled');
}

function checkIfShouldEnableGuardar() {
    // Verificar si algún campo ha sido modificado
    const anyFieldModified = document.querySelector('.field-modified') !== null;
    
    // Verificar si el título ha cambiado Y algún campo ha sido modificado
    if (lTitleChanged && anyFieldModified) {
        document.getElementById('b_guardar_predef').removeAttribute('disabled');
    } else if (anyFieldModified || lTitleChanged) {
        // Si hay cambios en campos o título, habilitar el botón
        document.getElementById('b_guardar_predef').removeAttribute('disabled');
    }
}

function validarCamposObligatorios() {
    // Valida que todos los campos obligatorios estén llenos
    const camposObligatorios = [
        { id: 'l_title', nombre: 'Título del informe' },
        { id: 's_tipo_estudio', nombre: 'Tipo de estudio' },
        { id: 'text_tecnicas', nombre: 'Técnica de examen' },
        { id: 'text_hallazgos', nombre: 'Hallazgos' },
        { id: 'text_impresiones', nombre: 'Impresiones' },
        { id: 'text_conclusiones', nombre: 'Conclusiones' }
    ];

    const camposFaltantes = [];
    
    for (const campo of camposObligatorios) {
        const elemento = document.getElementById(campo.id);
        const valor = elemento.value.trim();
        
        if (!valor || valor === '') {
            camposFaltantes.push(campo.nombre);
            // Agregar clase de error visual
            elemento.classList.add('campo-error');
        } else {
            // Remover clase de error si el campo tiene contenido
            elemento.classList.remove('campo-error');
        }
    }
    
    return {
        esValido: camposFaltantes.length === 0,
        camposFaltantes: camposFaltantes
    };
}

function mostrarNotificacionCamposFaltantes(camposFaltantes) {
    // Muestra notificación de campos faltantes usando toast
    const titulo = 'Campos obligatorios faltantes';
    const mensaje = `
        <div>
            <p class="mb-2">Por favor, complete los siguientes campos antes de guardar:</p>
            <ul class="mb-0">
                ${camposFaltantes.map(campo => `<li>${campo}</li>`).join('')}
            </ul>
        </div>
    `;
    
    // Usar el sistema de toast existente
    showToast(titulo, mensaje, "/templates/includes/toast/toast_alert.html");
    
    // También destacar visualmente los campos faltantes
    setTimeout(() => {
        const primerCampoError = document.querySelector('.campo-error');
        if (primerCampoError) {
            primerCampoError.focus();
            primerCampoError.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }, 500); // Aumentar delay para que aparezca después del toast
}

function GuardarPredef() {
    // Validar campos obligatorios antes de guardar
    const validacion = validarCamposObligatorios();
    
    if (!validacion.esValido) {
        mostrarNotificacionCamposFaltantes(validacion.camposFaltantes);
        return; // No continuar con el guardado
    }

    const botonGuardar = document.getElementById('b_guardar_predef');
    const status = botonGuardar.getAttribute('data-status');
    const id = botonGuardar.getAttribute('data-id'); // Puede ser null si es nuevo

    const data = {
        title: document.getElementById('l_title').value,
        studytype_id: document.getElementById('s_tipo_estudio').value,
        tecnicastext: document.getElementById('text_tecnicas').value,
        hallazgostext: document.getElementById('text_hallazgos').value,
        impresionestext: document.getElementById('text_impresiones').value,
        conclusionestext: document.getElementById('text_conclusiones').value,
        isdefault: document.getElementById('chk_default_report').checked ? 1 : 0
    };
    console.log('[GuardarPredef] Enviando:', data);

    // Si estamos editando, agregamos el ID
    let url = '/guardar_predefinido';
    if (status === 'editing' && id) {
        url = '/editar_predefinido';
        data.guid = id;
    }

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    }).then(response => {
        if (response.ok) {
            showToast('¡Éxito!', 'Informe predefinido guardado correctamente', "/templates/includes/toast/toast_success.html");
            flashCards();
            resetFormStates(); // Resetear estados después de guardar
            botonGuardar.setAttribute('disabled', true);
        } else {
            showToast('Error', 'No se pudo guardar el informe. Intente nuevamente.', "/templates/includes/toast/toast_error.html");
        }
    }).catch(error => {
        console.error('Error en la solicitud:', error);
        showToast('Error de conexión', 'No se pudo conectar al servidor. Verifique su conexión.', "/templates/includes/toast/toast_error.html");
    });
}


function HabilitarEdicion() {
    // Resetear estados de modificación
    resetFormStates();
    
    document.getElementById('text_tecnicas').removeAttribute('disabled');
    document.getElementById('text_hallazgos').removeAttribute('disabled');
    document.getElementById('text_impresiones').removeAttribute('disabled');
    document.getElementById('text_conclusiones').removeAttribute('disabled');
    document.getElementById('l_title').removeAttribute('disabled');

    const botonGuardar = document.getElementById('b_guardar_predef');
    // Estado de edición
    botonGuardar.setAttribute('data-status', 'editing');

    // Buscar fila seleccionada y extraer su data-id
    const filaSeleccionada = document.querySelector('.fila-seleccionada');
    if (filaSeleccionada) {
        const idSeleccionado = filaSeleccionada.getAttribute('data-id');
        botonGuardar.setAttribute('data-id', idSeleccionado);
    }
}


function ConfigurarTablaIP(TablaId, botonesClass) {
    var tabla = document.getElementById(TablaId);
    var tbody_g = tabla.querySelector('tbody');

    tbody_g.addEventListener('click', function (event) {
        var filas = tbody_g.querySelectorAll('tr');
        for (var i = 0; i < filas.length; i++) {
            filas[i].classList.remove('fila-seleccionada');
        }

        var fila = event.target.closest('tr');

        if (fila && !fila.classList.contains('fila-blocked')) {
            fila.classList.add('fila-seleccionada');

            // 🔥 Obtener el data-id de la fila seleccionada
            var reportId = fila.getAttribute('data-id');

            // 🔥 Enviar al backend
            fetch(`/get_predefinido/${reportId}`)
                .then(response => response.json())
                .then(data => {
                    console.log(data)
                    // Cargar los datos en los campos
                    document.getElementById('l_title').value = data.title || '';
                    document.getElementById('text_hallazgos').value = data.findings || '';
                    document.getElementById('text_tecnicas').value = data.technique || '';
                    document.getElementById('text_impresiones').value = data.impression || '';
                    document.getElementById('text_conclusiones').value = data.conclusion || '';
                    
                    // Seleccionar el tipo de estudio correspondiente
                    const selectEstudio = document.getElementById('s_tipo_estudio');
                    if (data.studytype_id && selectEstudio) {
                        selectEstudio.value = data.studytype_id;
                    }
                    
                    // Resetear estados de modificación después de cargar datos
                    resetFormStates();
                    
                    // Reflejar isdefault en el checkbox
                    const chkDefault = document.getElementById('chk_default_report');
                    if (typeof data.isdefault !== 'undefined') {
                        chkDefault.checked = (data.isdefault === true || data.isdefault === 1 || data.isdefault === '1');
                    } else {
                        chkDefault.checked = false;
                    }
                })
                .catch(error => {
                    console.error('Error al obtener el informe:', error);
                });

            // 🔁 Activar botones
            var botones = document.getElementsByClassName(botonesClass);
            for (var i = 0; i < botones.length; i++) {
                var boton = botones[i];
                boton.disabled = false;

                if (boton.classList.contains('delete_b')) {
                    boton.classList.remove('btn-secondary');
                    boton.classList.add('btn-danger');
                } else {
                    boton.classList.remove('btn-secondary');
                    boton.classList.add('btn-success');
                }
            }

        } else {
            // 🔁 Desactivar botones si no hay selección válida
            var botones = document.getElementsByClassName(botonesClass);
            for (var i = 0; i < botones.length; i++) {
                var boton = botones[i];
                boton.disabled = true;

                if (boton.classList.contains('delete_b')) {
                    boton.classList.remove('btn-danger');
                    boton.classList.add('btn-secondary');
                } else {
                    boton.classList.remove('btn-success');
                    boton.classList.add('btn-secondary');
                }
            }
        }
    });
}



document.addEventListener("DOMContentLoaded", function() {

    
    RellenarTabla('tabla_inf_predef', '/get_inf_predefinidos')
    ConfigurarTablaIP('tabla_inf_predef','botones_sp')
    ConfigFiltrarText('busquedaInf', 'tabla_inf_predef',1)
    RellenarSelect('s_tipo_estudio', 'description', 'nextris.isstudytype'); 

    document.getElementById('add_predef').addEventListener('click', function () {
        CrearNuevoInformePredef()
    });

    // Evento click en el checkbox para verificar en el backend
    document.getElementById('chk_default_report').addEventListener('click', function () {
        const selectEstudio = document.getElementById('s_tipo_estudio');
        let tipoEstudioId = selectEstudio.value;
        if (!tipoEstudioId) {
            tipoEstudioId = selectEstudio.options[0]?.value;
        }
        if (tipoEstudioId) {
            fetch(`/api/isstudytype/${tipoEstudioId}/default_predef_id`)
                .then(res => res.json())
                .then(data => {
                    if (data.default_predef_id) {
                        // Si ya hay un informe por defecto, volver el checkbox a estado no marcado y mostrar alerta
                        this.checked = false;
                        alert('Ya existe un informe por defecto para este tipo de estudio.');
                    }
                })
                .catch(() => {
                    // No hacer nada especial en error
                });
        }
    });

    document.getElementById('text_tecnicas').addEventListener('input', function () {
        // Cambiar el estilo del textarea directamente o del panel padre
        this.classList.add('field-modified');
        // Quitar clase de error si el campo ahora tiene contenido
        if (this.value.trim() !== '') {
            this.classList.remove('campo-error');
        }
        checkIfShouldEnableGuardar();
    });

    document.getElementById('text_hallazgos').addEventListener('input', function () {
        // Cambiar el estilo del textarea directamente o del panel padre
        this.classList.add('field-modified');
        // Quitar clase de error si el campo ahora tiene contenido
        if (this.value.trim() !== '') {
            this.classList.remove('campo-error');
        }
        checkIfShouldEnableGuardar();
    });

    document.getElementById('text_impresiones').addEventListener('input', function () {
        // Cambiar el estilo del textarea directamente o del panel padre
        this.classList.add('field-modified');
        // Quitar clase de error si el campo ahora tiene contenido
        if (this.value.trim() !== '') {
            this.classList.remove('campo-error');
        }
        checkIfShouldEnableGuardar();
    });

    document.getElementById('text_conclusiones').addEventListener('input', function () {
        // Cambiar el estilo del textarea directamente o del panel padre
        this.classList.add('field-modified');
        // Quitar clase de error si el campo ahora tiene contenido
        if (this.value.trim() !== '') {
            this.classList.remove('campo-error');
        }
        checkIfShouldEnableGuardar();
    });

    document.getElementById('l_title').addEventListener('input', function () {
        lTitleChanged = true;
        this.classList.add('field-modified');
        // Quitar clase de error si el campo ahora tiene contenido
        if (this.value.trim() !== '') {
            this.classList.remove('campo-error');
        }
        checkIfShouldEnableGuardar();
    });

    document.getElementById('s_tipo_estudio').addEventListener('change', function () {
        // Quitar clase de error si se selecciona un tipo de estudio
        if (this.value && this.value !== '') {
            this.classList.remove('campo-error');
        }
        checkIfShouldEnableGuardar();
    });

    document.getElementById('b_guardar_predef').addEventListener('click', function () {GuardarPredef()});

    document.getElementById('b_edit_predef').addEventListener('click', function () {HabilitarEdicion()});
    

});
