// Este archivo contiene funciones JavaScript para la gestión de citas en la aplicación NextRIS.
// Muchas funciones que se utilizan en esta sección están definidas en otros archivos JS, como loader.js y toast.js, principalmente nrframework.js.
// No se deberán crear funciones duplicadas aquí si ya existen en esos archivos.

// ============================================
// INICIALIZACIÓN Y CONFIGURACIÓN
// ============================================

// Función para inicialización segura del dashboard
function safeInitDashboard() {
    // Prevenir errores de argon-dashboard cuando elementos no existen
    const originalConsoleError = console.error;
    console.error = function(message) {
        if (typeof message === 'string' && message.includes('Cannot set properties of null')) {
            // Silenciar errores específicos de elementos faltantes
            return;
        }
        originalConsoleError.apply(console, arguments);
    };
}

// Inicialización de tabs y navegación
function initNavTabs() {
    var navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(function (navLink) {
        navLink.addEventListener('click', function () {
            navLinks.forEach(function (link) { 
                link.classList.remove('active');
            });
            navLink.classList.add('active');
        });
    });
}

// ============================================
// VARIABLES GLOBALES Y CONFIGURACIÓN
// ============================================


// Variables globales para la configuración de workflow
let globalAgendaTipo = null;
let globalAgendaEstudios = null;
let selectedLocationId = null; // Variable global para ubicación seleccionada
// Consulta la configuración de workflow antes de cualquier acción
function obtenerConfigWorkflow() {
    return fetch('/get_config_workflow')
        .then(response => response.json())
        .then(data => {
            // Devuelve los datos para usarlos en el flujo principal
            return data;
        })
        .catch(error => {
            console.error('Error al obtener config_workflow:', error);
            return { agenda_tipo: null, agenda_estudios: null };
        });
}

function RellenarSelectRads(selectClass="rads") {
    fetch('/get_rads_list',{
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        })
        .then(response => response.json())
        .then(data => {
            // Rellenar los selects con los datos obtenidos
            var selectElements = document.querySelectorAll(`.${selectClass}`);
            selectElements.forEach(selectElement => {
                // Limpiar cualquier opción existente en el <select>
                selectElement.innerHTML = '';

                // Agregar la opción "Sin Asignar" al principio
                var todasOption = document.createElement('option');
                todasOption.value = '';
                todasOption.text = 'Sin Asignar';
                selectElement.appendChild(todasOption);

                // Llenar el <select> con las opciones de los datos
                data.data.forEach(item => {
                    var option = document.createElement('option');
                    option.value = item[0];
                    option.text = item[1];
                    selectElement.appendChild(option);
                });
            });
        })
        .catch(error => {
            console.error('Error al obtener rads_list:', error);
        });
}

//Objeto con datos de la orden
let OrderData = {
    patientId: null,
    exams:[],
    medico_solicitante: null,
    obra_social:null,
    location_id: null,
};

cacheEvents={
    events:[]
}

var uniqueEventId = 0; // Mueve esta línea fuera de la función para asegurarte de que el contador es global
var selectedEvent = null; // Variable global para almacenar el evento seleccionado
var eventHistory = []; // Pila para almacenar el historial de eventos
var calendar = null; // Inicializar la variable global para el calendario

function FinalizarOrden() {
    // Obtener los valores seleccionados de los select
    const urgencia = document.getElementById('urgencia').value;
    const obraSocial = document.getElementById('obra_social').value;
    const medicoSolicitante = document.getElementById('medico_solicitante').value;

    // Asignar los valores a las propiedades correspondientes de OrderData
    OrderData.urgencia = urgencia;
    OrderData.obra_social = obraSocial;
    OrderData.medico_solicitante = medicoSolicitante;

    // Checkear si patientId está vacío
    if (!OrderData.patientId) {
        alert('Por favor, seleccione un paciente.');
        return;
    }

    // Checkear si exams está vacío
    if (OrderData.exams.length === 0) {
        alert('Por favor, seleccione un examen.');
        return;
    }

    // Verificar que solo haya un examen (nueva lógica de un estudio por admisión)
    if (OrderData.exams.length > 1) {
        alert('Solo se puede agendar un estudio por admisión. Por favor, seleccione únicamente un examen.');
        return;
    }

    // Enviar OrderData al backend si todos los datos están completos
    fetch('/crear_worklist', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(OrderData)
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error('Error en el envío de la orden.');
        }
    })
    .then(data => {
        console.log('Orden enviada exitosamente:', data);
        // Aquí puedes agregar lógica adicional después de enviar la orden exitosamente
    })
    .catch(error => {
        console.error('Error:', error);
    });

    console.log('Datos de la orden finalizada:', OrderData);
}
//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)

function SeleccionarPaciente(TablaId){
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    var li_dni = document.getElementById('dni-item');
    var divPaciente = document.getElementById('pills-paciente-tab');
    

    if (filaSeleccionada) {
        // console.log("filaseleccionada:",filaSeleccionada.dataset.id)
        OrderData.patientId=filaSeleccionada.dataset.id
        var tds = filaSeleccionada.querySelectorAll('td');
        li_dni.innerText = "Paciente seleccionado: " + tds[0].innerText + ", " + tds[1].innerText;
        divPaciente.classList.add('bg-success'); // Agrega la clase de Bootstrap para fondo verde

        // Le quito la clase bg-danger si es que la tiene.
        var divPaciente = document.getElementById('pills-paciente-tab');
        divPaciente.classList.remove('bg-danger');

        var pillExamenButton = document.querySelector('[data-bs-target="#pills-examen"]');
        if (pillExamenButton) {
            var tab = new bootstrap.Tab(pillExamenButton);
            tab.show();
        }
    } else {
        li_dni.innerText = "No hay paciente seleccionado";
        divPaciente.classList.remove('bg-success'); // Remueve la clase de Bootstrap para fondo verde si no hay fila seleccionada
    }
} 

function ConfigTablaEstudios(Tabla1Id,Button1Id,Tabla2Id){
    var tablaEstudios = document.getElementById(Tabla1Id);
    var tbodyest = tablaEstudios.querySelector('tbody');

    var boton_sel = document.getElementById(Button1Id);
    boton_sel.addEventListener('click', AgregarEstudio);

    tablaEstudios.addEventListener('dblclick', AgregarEstudio);

    function AgregarEstudio() {

        var filaSeleccionada = tbodyest.querySelector('.fila-seleccionada');
        if (filaSeleccionada) {
            
            // Verificar si ya hay un estudio seleccionado (límite de 1 estudio por admisión)
            var tablaEstudiosSelec = document.getElementById(Tabla2Id);
            var tbodyEstudiosSelec = tablaEstudiosSelec.querySelector('tbody');
            var estudiosYaSeleccionados = tbodyEstudiosSelec.querySelectorAll('tr');
            
            if (estudiosYaSeleccionados.length >= 1) {
                alert('Solo se puede agendar un estudio por admisión. Debe quitar el estudio actual para seleccionar otro.');
                return;
            }

        // Clona la fila seleccionada
        filaSeleccionada.classList.remove('fila-seleccionada');
        var fullRowData = filaSeleccionada.innerHTML;
        var dataId = filaSeleccionada.getAttribute('data-id'); // Obtener el atributo data-id

        // Añade la fila clonada a la tabla de Estudios Seleccionados
        var tbodyEstudiosSelec = tablaEstudiosSelec.querySelector('tbody');
        var columnas = filaSeleccionada.getElementsByTagName('td');
        var contenidoColumna1 = columnas[0].textContent.trim(); // Contenido de la primera columna
        var contenidoColumna2 = columnas[1].textContent.trim(); 
        var nuevaFila = document.createElement('tr');
        nuevaFila.innerHTML = `<td>${contenidoColumna1}</td><td>${contenidoColumna2}</td>`;
        nuevaFila.setAttribute('data-full',fullRowData)
        nuevaFila.setAttribute('data-id', dataId);
        tbodyEstudiosSelec.appendChild(nuevaFila);
        filaSeleccionada.remove();

        // Forzar actualización inmediata del estado de la tabla
        actualizarEstadoTablaEstudios();

        // Restaura el estilo del botón
        boton_sel.classList.remove('btn-success');
        boton_sel.classList.add('btn-secondary');
        boton_sel.disabled = true;

        // Ahora haremos el evento para la agenda
        var columnas = filaSeleccionada.querySelectorAll('td');
        var codigoEst = columnas[0].textContent.trim(); // Contenido de la primera columna
        var descEst = columnas[1].textContent.trim();
        var modalidadEst = columnas[2] ? columnas[2].textContent.trim() : null; // Modalidad del estudio (columna 2)
        var idExam=filaSeleccionada.getAttribute('data-id');
        console.log("Estudio seleccionado:", idExam, "Modalidad:", modalidadEst);
        
        // Si es agenda por equipo, filtrar equipos por modalidad del estudio
        if (globalAgendaTipo === 'equipo' && idExam) {
            filtrarEquiposPorEstudio(idExam, modalidadEst);
        }
        }
        const newEvent = {
            title: codigoEst + " - " + descEst,
            start: wish_date + 'T09:00:00', // Ajustar la hora según sea necesario
            end: wish_date + 'T10:00:00',   // Ajustar la duración según sea necesario
            editable: true, // Este evento será editable
            idExam: idExam,
            id: idExam, // Asegúrate de que cada evento tenga un ID único
            isNew: true // Marcar como evento nuevo
        };


        // Agrego la clase al pill para indicar que ya está en condiciones esta pestana. Ademas le saco el bg-danger
        var divExamen = document.getElementById('pills-examen-tab');
        divExamen.classList.add('bg-success');
        divExamen.classList.remove('bg-danger');

        // Ahora le saco la clase bg-success a agenda, ya que agregue un nuevo que debe ser colocado.
        var divAgenda = document.getElementById('pills-agenda-tab');
        divAgenda.classList.remove('bg-success');

        
        // Crear nuevo div en external-events
        var externalEventsContainer = document.getElementById('external-events');
        
        // Limpiar cualquier evento existente (solo un estudio por admisión)
        externalEventsContainer.innerHTML = '';
        
        var newEventDiv = document.createElement('div');
        newEventDiv.className = 'fc-event fc-h-event fc-daygrid-event fc-daygrid-block-event';
        newEventDiv.innerHTML = `<div class='fc-event-main'>${newEvent.title}</div>`;
        newEventDiv.dataset.event = JSON.stringify(newEvent);
        newEventDiv.style.backgroundColor = '#522073'; // Cambia esto al color deseado
        newEventDiv.style.borderColor = '#7021BF'; // Cambia esto al color deseado
        newEventDiv.setAttribute('idExam',idExam)
        externalEventsContainer.appendChild(newEventDiv);

        //Ahora lo siguiente es crear el examen en orderData
        var examen = {
            examId: idExam,
            title:codigoEst + " - " + descEst
        }
        
        // Limpiar array de exámenes y agregar solo el nuevo (solo un estudio por admisión)
        OrderData.exams = [];
        OrderData.exams.push(examen);

        // Ahora creo una card
        var endpointCard = (globalAgendaTipo === 'equipo') ? '/get_block_prestacion_per_equipo' : '/get_block_prestacion_per_med';
        fetch(endpointCard)
        .then(response => response.text())
        .then(data => {
            var container = document.getElementById('conteiner_blocks_prest');
            
            // Limpiar cualquier card existente (solo una prestación por admisión)
            container.innerHTML = '';
            
            // console.log("idprefix: ",examen)
            var idPrefix = examen.title.substring(0, 3);
            var uniqueIdMedicoSolicitante = `${idPrefix}_ms`;
            var uniqueIdObraSocial = `${idPrefix}_os`;
            var uniqueIdRads = `${idPrefix}_rads`;
            var insertId=`id='${dataId}'`
            // console.log("dataid:",dataId)
            var cardHtml = data
                .replace('<!-- IdEstudio -->', examen.title)
                .replace('id="cardId"', insertId)
                .replace('class="modern-select medico_solicitante"', `class="modern-select medico_solicitante" id="${uniqueIdMedicoSolicitante}" name="${uniqueIdMedicoSolicitante}"`)
                .replace('class="modern-select obra_social"', `class="modern-select obra_social" id="${uniqueIdObraSocial}" name="${uniqueIdObraSocial}"`)
                .replace('class="modern-select rads"', `class="modern-select rads" id="${idPrefix}_rads" name="${idPrefix}_rads"`);
                
            container.insertAdjacentHTML('beforeend', cardHtml);

            // Añadir event listeners a los selects creados con validación
            const medicoSelect = document.getElementById(uniqueIdMedicoSolicitante);
            if (medicoSelect) {
                medicoSelect.addEventListener('change', function(event) {
                    console.log('Cambio en medico solicitante:', event.target.id);
                    codigo=event.target.id.substring(0, 3)
                    OrderData.exams.forEach(function(examen){
                        var idPrefix = examen.title.substring(0, 3)
                        console.log("idprefix:",idPrefix)
                        if(idPrefix==codigo){
                            examen.medico_solicitante=document.getElementById(event.target.id).value
                        }
                    })
                });
            }

            const obraSocialSelect = document.getElementById(uniqueIdObraSocial);
            if (obraSocialSelect) {
                obraSocialSelect.addEventListener('change', function(event) {
                    console.log('Cambio en obra social:', event.target.id);
                    codigo=event.target.id.substring(0, 3)
                    OrderData.exams.forEach(function(examen){
                        var idPrefix = examen.title.substring(0, 3)
                        if(idPrefix==codigo){
                            examen.obra_social=document.getElementById(event.target.id).value
                        }
                    })
                });
            }

            const radsSelect = document.getElementById(uniqueIdRads);
            if (radsSelect) {
                radsSelect.addEventListener('change', function(event) {
                    console.log('Cambio en rads:', event.target.id);
                    codigo=event.target.id.substring(0, 3)
                    OrderData.exams.forEach(function(examen){
                        var idPrefix = examen.title.substring(0, 3)
                        console.log("idprefix:",idPrefix)
                        if(idPrefix==codigo){
                            examen.rads=document.getElementById(event.target.id).value
                        }
                    })
                });
            }
                // Rellenar los selects
            
            // Si hay una ubicación seleccionada, filtrar por ubicación
            if (selectedLocationId) {
                cargarMedicosSolicitantesPorLocation(selectedLocationId);
                cargarObrasSocialesPorLocation(selectedLocationId);
            } else {
                // Si no hay ubicación, cargar todos
                RellenarSelectByClass("medico_solicitante","Description","nextris.isrequestingphysician");
                RellenarSelectByClass("obra_social","Description","nextris.ispricelist");
            }
            RellenarSelectRads('rads')

        })
        .catch(error => {
            console.error('Error al cargar el archivo block_prestacion.html:', error);
        });

        // Actualizar estado visual de la tabla de estudios con un pequeño delay
        setTimeout(function() {
            actualizarEstadoTablaEstudios();
        }, 100);

        // Cambiar automáticamente a la pestaña de agenda
        setTimeout(function() {
            var agendaTab = document.getElementById('pills-agenda-tab');
            if (agendaTab) {
                agendaTab.click();
            }
        }, 300);

    }

    tbodyest.addEventListener('click', function (event) {
        // Verificar si la tabla está deshabilitada
        var tablaEstudios = document.getElementById(Tabla1Id);
        if (tablaEstudios && tablaEstudios.classList.contains('table-disabled')) {
            event.preventDefault();
            event.stopPropagation();
            return false;
        }
        
        // Verificar si ya hay un estudio seleccionado (límite de 1 estudio por admisión)
        var tablaEstudiosSelec = document.getElementById(Tabla2Id);
        var tbodyEstudiosSelec = tablaEstudiosSelec.querySelector('tbody');
        var estudiosYaSeleccionados = tbodyEstudiosSelec.querySelectorAll('tr');
        
        if (estudiosYaSeleccionados.length >= 1) {
            // Si ya hay un estudio seleccionado, no permitir seleccionar otro
            boton_sel.classList.remove('btn-success');
            boton_sel.classList.add('btn-secondary');
            boton_sel.disabled = true;
            event.preventDefault();
            event.stopPropagation();
            return false;
        }

        var filas = tbodyest.querySelectorAll('tr');
        for (var i = 0; i < filas.length; i++) {
            filas[i].classList.remove('fila-seleccionada');
        }

        var fila = event.target.closest('tr');
        if (fila) {
            fila.classList.add('fila-seleccionada');

            boton_sel.classList.remove('btn-secondary');
            boton_sel.classList.add('btn-success');
            boton_sel.disabled = false;
            
        } else {
            boton_sel.classList.remove('btn-success');
            boton_sel.classList.add('btn-secondary');
            boton_sel.disabled = true;
        }
        
        // Actualizar estado visual
        actualizarEstadoTablaEstudios();
    });

}

// Función para actualizar el estado visual de la tabla de estudios según el límite de selección
function actualizarEstadoTablaEstudios() {
    var tablaEstudios = document.getElementById('tabla-estudios');
    var tablaEstudiosSelec = document.getElementById('tabla-estudios-selec');
    var botonSeleccionar = document.getElementById('seleccionar-estudio');
    
    console.log('Iniciando actualizarEstadoTablaEstudios...');
    console.log('Elementos encontrados:', {
        tablaEstudios: !!tablaEstudios,
        tablaEstudiosSelec: !!tablaEstudiosSelec,
        botonSeleccionar: !!botonSeleccionar
    });
    
    if (tablaEstudios && tablaEstudiosSelec && botonSeleccionar) {
        var tbodyEstudios = tablaEstudios.querySelector('tbody');
        var tbodyEstudiosSelec = tablaEstudiosSelec.querySelector('tbody');
        var estudiosYaSeleccionados = tbodyEstudiosSelec.querySelectorAll('tr');
        
        console.log('Actualizando estado tabla estudios. Estudios seleccionados:', estudiosYaSeleccionados.length);
        
        if (estudiosYaSeleccionados.length >= 1) {
            console.log('DESHABILITANDO tabla - hay estudios seleccionados');
            
            // Deshabilitar la tabla de estudios disponibles
            tablaEstudios.style.opacity = '0.5';
            tablaEstudios.style.pointerEvents = 'none';
            tablaEstudios.style.cursor = 'not-allowed';
            tablaEstudios.classList.add('table-disabled');
            
            // También deshabilitar el tbody específicamente
            if (tbodyEstudios) {
                tbodyEstudios.style.pointerEvents = 'none';
                tbodyEstudios.style.cursor = 'not-allowed';
            }
            
            // Deshabilitar el botón de seleccionar
            botonSeleccionar.classList.remove('btn-success');
            botonSeleccionar.classList.add('btn-secondary');
            botonSeleccionar.disabled = true;
            
            // Quitar selección de cualquier fila
            var filasEstudios = tablaEstudios.querySelectorAll('tr');
            filasEstudios.forEach(fila => fila.classList.remove('fila-seleccionada'));
            
            console.log('Tabla deshabilitada. Estilos aplicados:', {
                opacity: tablaEstudios.style.opacity,
                pointerEvents: tablaEstudios.style.pointerEvents,
                hasClass: tablaEstudios.classList.contains('table-disabled')
            });
        } else {
            console.log('HABILITANDO tabla - no hay estudios seleccionados');
            
            // Habilitar la tabla de estudios disponibles
            tablaEstudios.style.opacity = '1';
            tablaEstudios.style.pointerEvents = 'auto';
            tablaEstudios.style.cursor = 'default';
            tablaEstudios.classList.remove('table-disabled');
            
            // También habilitar el tbody específicamente
            if (tbodyEstudios) {
                tbodyEstudios.style.pointerEvents = 'auto';
                tbodyEstudios.style.cursor = 'default';
            }
            
            // Resetear el botón de seleccionar al estado inicial (deshabilitado pero disponible)
            botonSeleccionar.classList.remove('btn-success');
            botonSeleccionar.classList.add('btn-secondary');
            botonSeleccionar.disabled = true;
            
            // Quitar cualquier selección previa en la tabla de estudios
            var filasEstudios = tbodyEstudios.querySelectorAll('tr');
            filasEstudios.forEach(fila => fila.classList.remove('fila-seleccionada'));
        }
    } else {
        console.error('No se encontraron todos los elementos necesarios para actualizar estado');
    }
}

// Función para filtrar equipos por modalidad del estudio seleccionado
function filtrarEquiposPorEstudio(estudoId, modalidadTexto) {
    console.log('Filtrando equipos para estudio ID:', estudoId, 'Modalidad texto:', modalidadTexto);
    console.log('Location ID actual:', OrderData.location_id);
    
    // Usar el endpoint que filtra por el ID del estudio y obtiene equipos compatibles
    // IMPORTANTE: Enviar también el location_id para filtrar solo equipos de la ubicación seleccionada
    fetch('/get_equipos_por_modalidad', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
            estudio_id: estudoId,
            location_id: OrderData.location_id  // Agregar location_id del OrderData
        })
    })
        .then(response => response.json())
        .then(equiposFiltrados => {
            console.log('Equipos filtrados recibidos:', equiposFiltrados);
            
            // Actualizar la tabla de equipos
            var tablaEquipos = document.getElementById('tabla-equipos');
            var tbody = tablaEquipos.querySelector('tbody');
            var select = document.getElementById('prof_ag');
            
            // Limpiar tabla y select
            tbody.innerHTML = '';
            select.innerHTML = '';
            
            // Agregar opción por defecto al select oculto
            var optionDefault = document.createElement('option');
            optionDefault.value = '';
            optionDefault.text = `Seleccione un equipo compatible con ${modalidadTexto}`;
            select.appendChild(optionDefault);
            
            // Llenar la tabla y el select solo con equipos compatibles
            if (equiposFiltrados.length > 0) {
                equiposFiltrados.forEach(function(item) {
                    // Agregar fila a la tabla
                    var fila = document.createElement('tr');
                    fila.style.cursor = 'pointer';
                    fila.setAttribute('data-equipo-id', item[0]); // guid
                    fila.innerHTML = `
                        <td>
                            <div class="d-flex px-2 py-1">
                                <div class="d-flex flex-column justify-content-center">
                                    <h6 class="mb-0 text-sm">${item[1] || ''}</h6>
                                </div>
                            </div>
                        </td>
                        <td>
                            <p class="text-xs font-weight-bold mb-0">${modalidadTexto || 'N/A'}</p>
                        </td>
                    `;
                    tbody.appendChild(fila);
                    
                    // Agregar opción al select oculto (para compatibilidad)
                    var option = document.createElement('option');
                    option.value = item[0]; // guid
                    option.text = item[1]; // aetitle
                    select.appendChild(option);
                });
                
                console.log(`Se agregaron ${equiposFiltrados.length} equipos compatibles con modalidad ${modalidadTexto}`);
            } else {
                // Mostrar mensaje si no hay equipos compatibles
                var filaVacia = document.createElement('tr');
                filaVacia.innerHTML = `
                    <td colspan="2" class="text-center">
                        <p class="text-sm text-muted mb-0">No hay equipos disponibles para ${modalidadTexto}</p>
                    </td>
                `;
                tbody.appendChild(filaVacia);
                
                console.warn(`No se encontraron equipos compatibles con modalidad ${modalidadTexto}`);
            }
            
            // Deshabilitar wish_date hasta que se seleccione un equipo
            var wishDateInput = document.getElementById('wish_date');
            if (wishDateInput) {
                wishDateInput.disabled = true;
            }
            
            // Re-agregar event listener para selección de fila (ya que se reemplazó el tbody)
            tbody.addEventListener('click', function(event) {
                var fila = event.target.closest('tr');
                if (fila && fila.hasAttribute('data-equipo-id')) {
                    // Remover selección previa
                    var filas = tbody.querySelectorAll('tr');
                    filas.forEach(f => f.classList.remove('fila-seleccionada'));
                    
                    // Seleccionar nueva fila
                    fila.classList.add('fila-seleccionada');
                    
                    // Actualizar el select oculto
                    var equipoId = fila.getAttribute('data-equipo-id');
                    select.value = equipoId;
                    
                    // Habilitar wish_date
                    var wishDateInput = document.getElementById('wish_date');
                    if (wishDateInput) {
                        wishDateInput.disabled = false;
                    }
                    
                    // Trigger del evento change para que se ejecute la lógica existente
                    var event = new Event('change', { bubbles: true });
                    select.dispatchEvent(event);
                }
            });
        })
        .catch(error => {
            console.error('Error al filtrar equipos por modalidad:', error);
            
            // En caso de error, mostrar mensaje
            var tablaEquipos = document.getElementById('tabla-equipos');
            var tbody = tablaEquipos.querySelector('tbody');
            tbody.innerHTML = `
                <tr>
                    <td colspan="2" class="text-center">
                        <p class="text-sm text-danger mb-0">Error al cargar equipos</p>
                    </td>
                </tr>
            `;
        });
}

// Función para restablecer la lista completa de equipos (sin filtro de modalidad)
function restablecerListaComplataEquipos() {
    console.log('Restableciendo lista completa de equipos...');
    
    fetch('/get_lista_de_equipos')
        .then(response => response.json())
        .then(data => {
            var select = document.getElementById('prof_ag');
            if (select) {
                select.innerHTML = '';
                var optionDefault = document.createElement('option');
                optionDefault.value = '';
                optionDefault.text = 'Seleccione un equipo';
                select.appendChild(optionDefault);
                
                data.forEach(function(item) {
                    var option = document.createElement('option');
                    option.value = item[0]; // guid
                    option.text = item[1]; // aetitle
                    select.appendChild(option);
                });
                
                console.log(`Lista de equipos restablecida: ${data.length} equipos disponibles`);
                
                // Deshabilitar wish_date hasta que se seleccione un equipo
                var wishDateInput = document.getElementById('wish_date');
                if (wishDateInput) {
                    wishDateInput.disabled = true;
                }
            }
        })
        .catch(error => {
            console.error('Error al restablecer lista de equipos:', error);
        });
}

function ConfigTablaSeleccionados(Tabla1Id, Button1Id, Tabla2Id) {
    var tablaSelec = document.getElementById(Tabla1Id);
    var tbodySelec = tablaSelec.querySelector('tbody');

    var botonQuitar = document.getElementById(Button1Id);
    botonQuitar.addEventListener('click', QuitarEstudio);
    tablaSelec.addEventListener('dblclick', QuitarEstudio);

    function QuitarEstudio() {
        var filaSeleccionadaSelec = tbodySelec.querySelector('.fila-seleccionada');

        if (filaSeleccionadaSelec) {
            var filaCompleta = document.createElement('tr');
            filaCompleta.innerHTML = filaSeleccionadaSelec.getAttribute('data-full');

            var data2delete = filaSeleccionadaSelec.getAttribute('data-id');

            var columnas = filaCompleta.getElementsByTagName('td');
            var cod = columnas[0].textContent.trim();
            var descr = columnas[1].textContent.trim();

            // Buscar y eliminar el evento de la tabla de external-events
            var externalEventsContainer = document.getElementById('external-events');
            var events = externalEventsContainer.querySelectorAll('.fc-event');

            events.forEach(event => {
                var eventData = JSON.parse(event.dataset.event);
                if (eventData.idExam === data2delete) {
                    event.remove();
                }
            });

            // Buscar y eliminar el evento del calendario
            if (calendar) {
                var eventToRemove = calendar.getEventById(data2delete);
                if (eventToRemove) {
                    eventToRemove.remove();
                    eventHistory = eventHistory.filter(event => event.id !== data2delete);
                    if (selectedEvent && selectedEvent.id === data2delete) {
                        selectedEvent = null;
                    }
                    
                    // Filtrar solo los eventos nuevos
                    var eventosNuevos = calendar.getEvents().filter(ev => ev.extendedProps && ev.extendedProps.isNew);
                    console.log("Eventos nuevos restantes en el calendario:", eventosNuevos.length);
                    if (eventosNuevos.length === 0) {
                        calendar.destroy();
                        calendar = null;
                        var cardAgenda = document.getElementById('card-agenda');
                        if (cardAgenda) cardAgenda.hidden = true;
                        // Ocultar el calendario
                        var calendarEl = document.getElementById('calendar');
                        if (calendarEl) calendarEl.style.display = 'none';
                        // Resetear el select prof_ag
                        var selectProfAg = document.getElementById('prof_ag');
                        if (selectProfAg) selectProfAg.selectedIndex = 0;
                    }
                }
            }

            // Eliminar de OrderData
            OrderData.exams = OrderData.exams.filter(examen => examen.examId !== data2delete);

            // Eliminar el evento del historial
            eventHistory = eventHistory.filter(event => event.id !== data2delete);

            // Limpiar completamente el contenedor de prestaciones (solo un estudio por admisión)
            var container = document.getElementById('conteiner_blocks_prest');
            if (container) {
                container.innerHTML = '';
            }

            // También eliminar de la tabla external-events (compatibilidad con código anterior)
            var cardIdPrefix = cod.substring(0, 3);
            var card = document.querySelector(`[data-id="${cardIdPrefix}"]`);
            if (card) {
                card.remove();
            }

            // Insertar la fila en la posición correcta en la tabla de estudios
            var tablaEstudios = document.getElementById(Tabla2Id);
            var tbodyEstudios = tablaEstudios.querySelector('tbody');

            // Encontrar la posición correcta para insertar la fila
            var inserted = false;
            var filas = tbodyEstudios.querySelectorAll('tr');
            filas.forEach(function (fila) {
                var filaCod = fila.getElementsByTagName('td')[0].textContent.trim();
                if (cod == (filaCod-1)) {
                    console.log("entre aca")
                    tbodyEstudios.insertBefore(filaCompleta, fila);
                    inserted = true;
                    return false; // Salir del bucle
                }
            });
            // Si no se ha insertado, añadir al final
            if (!inserted) {
                tbodyEstudios.appendChild(filaCompleta);
            }

            botonQuitar.classList.remove('btn-success');
            botonQuitar.classList.add('btn-secondary');
            botonQuitar.disabled = true;

            console.log("data2delete: ", data2delete);
            filaSeleccionadaSelec.remove();

            // Verificar si ya no hay ninguna fila en tbodySelec y retirar la clase bg-success
            if (tbodySelec.querySelectorAll('tr').length === 0) {
                var divExamen = document.getElementById('pills-examen-tab');
                divExamen.classList.remove('bg-success');
            }

            // Actualizar estado visual de la tabla de estudios
            actualizarEstadoTablaEstudios();
            
            // Si es agenda por equipo, restablecer la lista completa de equipos
            if (globalAgendaTipo === 'equipo') {
                restablecerListaComplataEquipos();
            }
        }
    }

    tbodySelec.addEventListener('click', function (event) {
        var filas = tbodySelec.querySelectorAll('tr');
        filas.forEach(fila => fila.classList.remove('fila-seleccionada'));

        var fila = event.target.closest('tr');
        if (fila) {
            fila.classList.add('fila-seleccionada');
            botonQuitar.classList.remove('btn-secondary');
            botonQuitar.classList.add('btn-success');
            botonQuitar.disabled = false;
        } else {
            botonQuitar.classList.remove('btn-success');
            botonQuitar.classList.add('btn-secondary');
            botonQuitar.disabled = true;
        }
        
        // Actualizar estado visual por si hay cambios
        actualizarEstadoTablaEstudios();
    });
}

function CrearCalendario() {
    var prof_ag = document.getElementById('prof_ag').value;

    // Consultar la configuración antes de crear el calendario
    obtenerConfigWorkflow().then(config => {
        // Puedes condicionar el flujo aquí según los valores
        if (config.agenda_tipo === 'medico') {
            // Flujo actual para médicos
            fetch('/get_events_per_med', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ prof_ag: prof_ag })
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('card-agenda').hidden = false;
                var calendarEl = document.getElementById('calendario');
                var businessHours = data.work_hours.map(wh => ({
                    daysOfWeek: [wh.day],
                    startTime: wh.start,
                    endTime: wh.end
                }));
                var filteredExams = OrderData.exams.filter(exam => exam.profesional === prof_ag);
                var additionalEvents = filteredExams.map(exam => ({
                    id: exam.examenId,
                    title: exam.examenId,
                    start: exam.init,
                    end: exam.finish,
                    editable: true
                }));
                var eventosAjustados = data.events.map(ev => {
                    let start = new Date(ev.start);
                    start.setHours(start.getHours()-2);
                    let end = new Date(ev.end);
                    end.setHours(end.getHours()-2);
                    return { ...ev, start: start.toISOString(), end: end.toISOString() };
                });
                var allEvents = eventosAjustados.concat(additionalEvents);
                calendar = new FullCalendar.Calendar(calendarEl, {
                    timeZone: 'America/Argentina/Buenos_Aires',
                    droppable: true,
                    eventOverlap: function(stillEvent, movingEvent) {
                        // No permitir solapamiento
                        var stillStart = stillEvent.start;
                        var stillEnd = stillEvent.end || new Date(stillEvent.start.getTime() + 60 * 60 * 1000);
                        var movingStart = movingEvent.start;
                        var movingEnd = movingEvent.end || new Date(movingEvent.start.getTime() + 60 * 60 * 1000);
                        // Si mismo día y se solapan
                        return !(stillStart.toDateString() === movingStart.toDateString() &&
                            movingStart < stillEnd && movingEnd > stillStart);
                    },
                    eventReceive: function(info) {
                        console.log('[MEDICO] eventReceive disparado', info.event);
                        
                        // Verificar si ya existe un evento con el mismo ID
                        var idExam = info.draggedEl.getAttribute('idExam');
                        var eventosExistentes = calendar.getEvents().filter(ev => {
                            return ev.id === idExam && ev !== info.event;
                        });
                        
                        if (eventosExistentes.length > 0) {
                            console.log('[MEDICO] Evento duplicado detectado, removiendo...');
                            info.event.remove();
                            return;
                        }
                        
                        // Verificar si ya hay un evento nuevo en el calendario (límite de 1 estudio)
                        var eventosNuevos = calendar.getEvents().filter(ev => ev.extendedProps && ev.extendedProps.isNew && ev !== info.event);
                        if (eventosNuevos.length >= 1) {
                            info.event.remove();
                            alert('Solo se puede agendar un estudio por admisión. Ya hay un estudio programado en el calendario.');
                            return;
                        }

                        var eventObj = info.event;
                        var examId = idExam;
                        var profesional = document.getElementById('prof_ag').value;
                        var init = eventObj.start;
                        var finish = eventObj.end || new Date(init.getTime() + 60 * 60 * 1000);
                        
                        // CRÍTICO: Buscar si el examen ya existe en OrderData para preservar todas sus propiedades
                        var examenExistente = OrderData.exams.find(examen => examen.examId == examId);
                        if (examenExistente) {
                            // Actualizar solo las propiedades de calendario, preservando medico_solicitante, rads, title, etc.
                            examenExistente.profesional = profesional;
                            examenExistente.init = init;
                            examenExistente.finish = finish;
                            console.log('[MEDICO] Examen existente actualizado con nuevas fechas:', examenExistente);
                        } else {
                            // Si es un examen completamente nuevo (no debería pasar en el flujo normal)
                            console.warn('[MEDICO] Examen no encontrado en OrderData, creando nuevo objeto básico');
                            OrderData.exams.push({
                                examId: examId,
                                title: eventObj.title,
                                profesional: profesional,
                                init: init,
                                finish: finish
                            });
                        }
                        var newEventId = idExam;
                        eventObj.setProp('id', newEventId);
                        // Marcar como evento nuevo
                        eventObj.setExtendedProp('isNew', true);
                        selectedEvent = {
                            id: newEventId,
                            title: eventObj.title,
                            start: init,
                            end: finish,
                            editable: true
                        };
                        eventHistory.push(selectedEvent);
                        info.draggedEl.parentNode.removeChild(info.draggedEl);
                        var tablaEstudiosSelec = document.getElementById('tabla-estudios-selec');
                        var externalEvents = document.getElementById('external-events');
                        if (tablaEstudiosSelec.querySelectorAll('tr').length > 0 &&
                            externalEvents.querySelectorAll('.fc-event').length === 0) {
                            var divAgenda = document.getElementById('pills-agenda-tab');
                            divAgenda.classList.add('bg-success');
                            divAgenda.classList.remove('bg-danger');
                        }
                    },
                    eventChange: function(info) {
                        // ...existing code...
                        // Verificar duplicados visuales de eventos nuevos
                        var eventosDuplicados = info.event.calendar.getEvents().filter(ev => {
                            return ev.id === info.event.id &&
                                ev.extendedProps && ev.extendedProps.isNew &&
                                ev.start.getTime() === info.event.start.getTime() &&
                                ev.end.getTime() === info.event.end.getTime() &&
                                ev !== info.event;
                        });
                        if (eventosDuplicados.length > 0) {
                            // Si hay duplicado, eliminar el evento actual
                            info.event.remove();
                            return;
                        }
                    },
                    initialView: 'timeGridWeek',
                    editable: true,
                    selectable: true,
                    events: allEvents,
                    headerToolbar: {
                        left: 'prev,next today',
                        center: 'title',
                        right: 'timeGridDay,timeGridWeek,dayGridMonth'
                    },
                    slotDuration: '00:20:00',
                    slotMinTime: '07:00:00', // Empieza a las 7am
                    slotMaxTime: '21:00:00', // Termina a las 21pm
                    businessHours: businessHours,
                    selectConstraint: businessHours,
                    eventConstraint: businessHours,
                    allDaySlot: false, // Oculta la fila all-day
                    slotLabelFormat: {
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false
                    },
                    slotLaneClassNames: '', // Elimina estilos extra
                    dayHeaderClassNames: '', // Elimina estilos extra
                });
                new FullCalendar.Draggable(document.getElementById('external-events'), {
                    itemSelector: '.fc-event',
                    eventData: function(eventEl) {
                        return {
                            id: 'event-' + (uniqueEventId++),
                            title: eventEl.innerText
                        };
                    }
                });
                calendar.render();
                // Ajuste de estilos para quitar el fondo morado de los slots
                setTimeout(function() {
                    let slotEls = calendarEl.querySelectorAll('.fc-timegrid-slot, .fc-timegrid-axis');
                    slotEls.forEach(el => {
                        el.style.backgroundColor = '#fff';
                        // Agregar efecto hover para resaltar solo la fila bajo el mouse
                        el.addEventListener('mouseover', function() {
                            slotEls.forEach(e => e.classList.remove('fc-slot-hover'));
                            el.classList.add('fc-slot-hover');
                        });
                        el.addEventListener('mouseout', function() {
                            el.classList.remove('fc-slot-hover');
                        });
                    });
                }, 100);
                // Agregar la clase CSS para el hover
                if (!document.getElementById('fc-slot-hover-style')) {
                    var style = document.createElement('style');
                    style.id = 'fc-slot-hover-style';
                    style.innerHTML = '.fc-slot-hover { background-color: #e5e5ff !important; }';
                    document.head.appendChild(style);
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
        } else if (config.agenda_tipo === 'equipo') {
            // Flujo para equipos
            fetch('/get_events_per_equip', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ equipo_id: prof_ag })
            })
            .then(response => response.json())
            .then(data => {
                // Mostrar la card de la agenda
                document.getElementById('card-agenda').hidden = false;
                var calendarEl = document.getElementById('calendario');
                var businessHours = data.work_hours.map(wh => ({
                    daysOfWeek: [wh.day],
                    startTime: wh.start,
                    endTime: wh.end
                }));
                var filteredExams = OrderData.exams.filter(exam => exam.profesional === prof_ag);
                var additionalEvents = filteredExams.map(exam => ({
                    id: exam.examenId,
                    title: exam.examenId,
                    start: exam.init,
                    end: exam.finish,
                    editable: true
                }));
                var eventosAjustados = data.events.map(ev => {
                    let start = new Date(ev.start);
                    start.setHours(start.getHours()-2);
                    let end = new Date(ev.end);
                    end.setHours(end.getHours()-2);
                    return { ...ev, start: start.toISOString(), end: end.toISOString() };
                });
                var allEvents = eventosAjustados.concat(additionalEvents);
                calendar = new FullCalendar.Calendar(calendarEl, {
                    timeZone: 'America/Argentina/Buenos_Aires',
                    droppable: true,
                    eventOverlap: function(stillEvent, movingEvent) {
                        var stillStart = stillEvent.start;
                        var stillEnd = stillEvent.end || new Date(stillEvent.start.getTime() + 60 * 60 * 1000);
                        var movingStart = movingEvent.start;
                        var movingEnd = movingEvent.end || new Date(movingEvent.start.getTime() + 60 * 60 * 1000);
                        return !(stillStart.toDateString() === movingStart.toDateString() &&
                            movingStart < stillEnd && movingEnd > stillStart);
                    },
                    eventReceive: function(info) {
                        console.log('[EQUIPO] eventReceive disparado', info.event);
                        
                        // Verificar si ya existe un evento con el mismo ID
                        var idExam = info.draggedEl.getAttribute('idExam');
                        var eventosExistentes = calendar.getEvents().filter(ev => {
                            return ev.id === idExam && ev !== info.event;
                        });
                        
                        if (eventosExistentes.length > 0) {
                            console.log('[EQUIPO] Evento duplicado detectado, removiendo...');
                            info.event.remove();
                            return;
                        }
                        
                        // Verificar si ya hay un evento nuevo en el calendario (límite de 1 estudio)
                        var eventosNuevos = calendar.getEvents().filter(ev => ev.extendedProps && ev.extendedProps.isNew && ev !== info.event);
                        if (eventosNuevos.length >= 1) {
                            info.event.remove();
                            alert('Solo se puede agendar un estudio por admisión. Ya hay un estudio programado en el calendario.');
                            return;
                        }

                        var eventObj = info.event;
                        var idExam = info.draggedEl.getAttribute('idExam');
                        var examId = idExam;
                        var profesional = document.getElementById('prof_ag').value;
                        var init = eventObj.start;
                        var finish = eventObj.end || new Date(init.getTime() + 60 * 60 * 1000);
                        
                        // CRÍTICO: Buscar si el examen ya existe en OrderData para preservar todas sus propiedades
                        var examenExistente = OrderData.exams.find(examen => examen.examId == examId);
                        if (examenExistente) {
                            // Actualizar solo las propiedades de calendario, preservando medico_solicitante, rads, title, etc.
                            examenExistente.profesional = profesional;
                            examenExistente.init = init;
                            examenExistente.finish = finish;
                            console.log('[EQUIPO] Examen existente actualizado con nuevas fechas:', examenExistente);
                        } else {
                            // Si es un examen completamente nuevo (no debería pasar en el flujo normal)
                            console.warn('[EQUIPO] Examen no encontrado en OrderData, creando nuevo objeto básico');
                            OrderData.exams.push({
                                examId: examId,
                                title: eventObj.title,
                                profesional: profesional,
                                init: init,
                                finish: finish
                            });
                        }
                        var newEventId = idExam;
                        eventObj.setProp('id', newEventId);
                        // Marcar como evento nuevo
                        eventObj.setExtendedProp('isNew', true);
                        selectedEvent = {
                            id: newEventId,
                            title: eventObj.title,
                            start: init,
                            end: finish,
                            editable: true
                        };
                        eventHistory.push(selectedEvent);
                        info.draggedEl.parentNode.removeChild(info.draggedEl);
                        var tablaEstudiosSelec = document.getElementById('tabla-estudios-selec');
                        var externalEvents = document.getElementById('external-events');
                        if (tablaEstudiosSelec.querySelectorAll('tr').length > 0 &&
                            externalEvents.querySelectorAll('.fc-event').length === 0) {
                            var divAgenda = document.getElementById('pills-agenda-tab');
                            divAgenda.classList.add('bg-success');
                            divAgenda.classList.remove('bg-danger');
                        }
                    },
                    eventChange: function(info) {

                        console.log('Evento cambiado:', info.event);

                        var examen = OrderData.exams.find(e => e.examenId === info.event.examId);
                        console.log('Buscando examen con ID:',  examen);
                        if (examen) {
                            examen.init = info.event.start;
                            examen.finish = info.event.end || new Date(info.event.start.getTime() + 60 * 60 * 1000);

                            console.log('Examen actualizado:', examen);
                        } else {
                            console.error('Examen no encontrado:', info.event.examId);
                        }
                        console.log('Eventos:', OrderData.exams);
                    },
                    initialView: 'timeGridWeek',
                    editable: true,
                    selectable: true,
                    events: allEvents,
                    headerToolbar: {
                        left: 'prev,next today',
                        center: 'title',
                        right: 'timeGridDay,timeGridWeek,dayGridMonth'
                    },
                    slotDuration: '00:20:00',
                    slotMinTime: '07:00:00', // Empieza a las 7am
                    slotMaxTime: '21:00:00', // Termina a las 21pm
                    businessHours: businessHours,
                    selectConstraint: businessHours,
                    eventConstraint: businessHours,
                    allDaySlot: false, // Oculta la fila all-day
                    slotLabelFormat: {
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false
                    },
                    slotLaneClassNames: '', // Elimina estilos extra
                    dayHeaderClassNames: '', // Elimina estilos extra
                });
                new FullCalendar.Draggable(document.getElementById('external-events'), {
                    itemSelector: '.fc-event',
                    eventData: function(eventEl) {
                        return {
                            id: 'event-' + (uniqueEventId++),
                            title: eventEl.innerText
                        };
                    }
                });
                calendar.render();
                // Ajuste de estilos para quitar el fondo morado de los slots y agregar hover
                setTimeout(function() {
                    let slotEls = calendarEl.querySelectorAll('.fc-timegrid-slot, .fc-timegrid-axis');
                    slotEls.forEach(el => {
                        el.style.backgroundColor = '#fff';
                        // Agregar efecto hover para resaltar solo la fila bajo el mouse
                        el.addEventListener('mouseover', function() {
                            slotEls.forEach(e => e.classList.remove('fc-slot-hover'));
                            el.classList.add('fc-slot-hover');
                        });
                        el.addEventListener('mouseout', function() {
                            el.classList.remove('fc-slot-hover');
                        });
                    });
                }, 100);
                // Agregar la clase CSS para el hover
                if (!document.getElementById('fc-slot-hover-style')) {
                    var style = document.createElement('style');
                    style.id = 'fc-slot-hover-style';
                    style.innerHTML = '.fc-slot-hover { background-color: #e5e5ff !important; }';
                    document.head.appendChild(style);
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
        } else {
            alert('La configuración de agenda no está definida correctamente.');
        }
    });
}
function ReconfigurarCalendario(calendar) {
    var prof_ag = document.getElementById('prof_ag').value;
    // Consultar la configuración para decidir el endpoint
    obtenerConfigWorkflow().then(config => {
        let endpoint = '';
        let body = {};
        if (config.agenda_tipo === 'medico') {
            endpoint = '/get_events_per_med';
            body = { prof_ag: prof_ag };
        } else if (config.agenda_tipo === 'equipo') {
            endpoint = '/get_events_per_equip';
            body = { equipo_id: prof_ag };
        } 
        fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
        })
        .then(response => response.json())
        .then(data => {
            var businessHours = data.work_hours.map(wh => ({
                daysOfWeek: [wh.day],
                startTime: wh.start,
                endTime: wh.end
            }));
            var filteredExams = OrderData.exams.filter(exam => exam.profesional === prof_ag);
            var additionalEvents = filteredExams.map(exam => ({
                examId: exam.examId,
                title: exam.title,
                start: exam.init,
                end: exam.finish,
                editable: true
            }));
            // Ajustar la hora de los eventos del backend (restar 3 horas)
            var eventosAjustados = data.events.map(ev => {
                let start = new Date(ev.start);
                start.setHours(start.getHours()-2);
                let end = new Date(ev.end);
                end.setHours(end.getHours()-2);
                return { ...ev, start: start.toISOString(), end: end.toISOString() };
            });
            var allEvents = eventosAjustados.concat(additionalEvents);
            calendar.setOption('businessHours', businessHours);
            calendar.removeAllEvents();
            allEvents.forEach(event => {
                calendar.addEvent(event);
            });
            calendar.render();
        })
        .catch(error => {
            console.error('Error:', error);
        });
    });
}

document.getElementById('b_sel_pac_para_adm').addEventListener('click', function() {
    if (selectedEvent && selectedEvent.id) {
        // Elimina el evento del calendario
        var eventToRemove = calendar.getEventById(selectedEvent.id);
        if (eventToRemove) {
            eventToRemove.remove();
        }

        // Vuelve a crear el evento en el contenedor external-events
        var externalEventsContainer = document.getElementById('external-events');
        var newEventDiv = document.createElement('div');
        newEventDiv.className = 'fc-event fc-h-event fc-daygrid-event fc-daygrid-block-event';
        newEventDiv.innerHTML = `<div class='fc-event-main'>${selectedEvent.title}</div>`;
        newEventDiv.dataset.event = JSON.stringify(selectedEvent);

        externalEventsContainer.appendChild(newEventDiv);

        // Elimina el evento de OrderData.exams
        var examIndex = OrderData.exams.findIndex(exam => exam.examenId === selectedEvent.title);
        if (examIndex > -1) {
            OrderData.exams.splice(examIndex, 1);
        }

        console.log('Evento eliminado y recreado en external-events:', selectedEvent.title);
        selectedEvent = null; // Resetear el evento seleccionado
    } else {
        alert("No hay ningún evento seleccionado para eliminar.");
    }
});

function InsertarCitas() {
    // Verificar que OrderData tenga datos válidos antes de enviarlo
    console.log('=== INSERTANDO CITAS ===');
    console.log('OrderData completo:', JSON.stringify(OrderData, null, 2));
    console.log('Exámenes a enviar:', OrderData.exams);
    
    // Validar solo los campos OBLIGATORIOS (title, init, finish)
    // medico_solicitante, obra_social y rads son OPCIONALES
    var validacionOK = true;
    OrderData.exams.forEach((exam, index) => {
        console.log(`Validando examen ${index}:`, exam);
        
        if (!exam.title) {
            console.error(`❌ Examen ${index} sin title (OBLIGATORIO)`);
            validacionOK = false;
        }
        
        if (!exam.init || !exam.finish) {
            console.error(`❌ Examen ${index} sin init/finish - El estudio debe estar en el calendario (OBLIGATORIO)`);
            validacionOK = false;
        }
        
        // Log de campos opcionales (solo informativo)
        if (!exam.medico_solicitante) {
            console.log(`ℹ️ Examen ${index} sin medico_solicitante (opcional)`);
        }
        if (!exam.obra_social) {
            console.log(`ℹ️ Examen ${index} sin obra_social (opcional)`);
        }
        if (!exam.rads) {
            console.log(`ℹ️ Examen ${index} sin rads (opcional)`);
        }
    });
    
    if (!validacionOK) {
        alert('Error: Faltan datos obligatorios. El estudio debe tener título y estar colocado en el calendario. Revisa la consola para más detalles.');
        return;
    }
    
    let endpoint = globalAgendaTipo === 'equipo' ? '/insertar_citas_per_equip' : '/insertar_citas_per_med';
    console.log('Enviando a endpoint:', endpoint);
    
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(OrderData),
    })
    .then(response => {
        console.log('Respuesta del servidor - Status:', response.status);
        if (!response.ok) {
            return response.text().then(text => {
                console.error('Error del servidor:', text);
                throw new Error(`Error ${response.status}: ${text}`);
            });
        }
        return response.json();
    })
    .then(data => {
        // Manejar la respuesta del servidor
        if (data.success) {
            localStorage.setItem('showCitasToast', '1');
            console.log("Citas insertadas correctamente.");
            window.location.reload();
        } else {
            showToast("Error", "Hubo un problema al insertar las citas: " + data.message, "/static/templates/includes/toast/toast_alert.html");
        }
    })
    .catch(error => { 
        console.error('Error:', error);
        showToast("Error", "Hubo un error al insertar las citas.", "/static/templates/includes/toast/toast_alert.html");
    });
}

// Mostrar toast si corresponde al cargar la página
if (localStorage.getItem('showCitasToast')) {
    showToast("Éxito", "Las citas se han insertado correctamente.", "/static/templates/includes/toast/toast_success.html");
    localStorage.removeItem('showCitasToast');
}
// ...existing code...
function QuitarEvento() {
    if (eventHistory.length > 0) {
        // Obtener el último evento del historial
        var lastEvent = eventHistory.pop();

        // Eliminar el evento del calendario
        var eventToRemove = calendar.getEventById(lastEvent.id);
        console.log("Quitando evento con ID: ", lastEvent.id);
        if (eventToRemove) {
            console.log("Removiendo evento del calendario");
            eventToRemove.remove();
        }

        // Vuelve a crear el evento en el contenedor external-events
        var externalEventsContainer = document.getElementById('external-events');
        var newEventDiv = document.createElement('div');
        newEventDiv.className = 'fc-event fc-h-event fc-daygrid-event fc-daygrid-block-event';
        newEventDiv.innerHTML = `<div class='fc-event-main'>${lastEvent.title}</div>`;
        newEventDiv.dataset.event = JSON.stringify(lastEvent);
        newEventDiv.style.backgroundColor = '#522073';
        newEventDiv.style.borderColor = '#7021BF';
        
        // IMPORTANTE: Agregar el atributo idExam necesario para el drag & drop
        newEventDiv.setAttribute('idExam', lastEvent.id);

        externalEventsContainer.appendChild(newEventDiv);

        // CRÍTICO: NO eliminar el examen de OrderData.exams
        // Solo limpiar las propiedades de calendario (profesional, init, finish)
        // para que el usuario tenga que volver a arrastrarlo al calendario
        var examIndex = OrderData.exams.findIndex(exam => exam.examId == lastEvent.id);
        if (examIndex > -1) {
            // Limpiar solo las propiedades de calendario, preservando medico_solicitante, rads, title
            delete OrderData.exams[examIndex].profesional;
            delete OrderData.exams[examIndex].init;
            delete OrderData.exams[examIndex].finish;
            console.log('Propiedades de calendario limpiadas, manteniendo datos del estudio:', OrderData.exams[examIndex]);
        }

        console.log('Evento eliminado del calendario y recreado en external-events:', lastEvent.id);
        selectedEvent = null; // Resetear el evento seleccionado

        // Le quito la clase bg-success al tab de agenda
        var divAgenda = document.getElementById('pills-agenda-tab');
        divAgenda.classList.remove('bg-success');
        
        console.log('Estado después de quitar evento:', {
            eventHistory: eventHistory.length,
            orderDataExams: OrderData.exams.length,
            calendarEvents: calendar ? calendar.getEvents().length : 0
        });
    } else {
        // Mostrar el toast en lugar del alert
        showToast('Ha ocurrido un problema', 'No hay ningún evento en el historial para eliminar.', "/static/templates/includes/toast/toast_alert.html");
    }
}

// ============================================
// FUNCIONES DE FILTRADO POR UBICACIÓN (SCOPE GLOBAL)
// ============================================

// Función para cargar médicos solicitantes por ubicación
function cargarMedicosSolicitantesPorLocation(locationId) {
    console.log('[DEBUG] Cargando médicos solicitantes para location_id:', locationId);
    
    fetch('/rellenar_select_cond_id', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            dNeeded: 'Description',
            TableId: 'nextris.isrequestingphysician',
            idCond: locationId,
            colCond: 'location_id'
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('[DEBUG] Médicos solicitantes recibidos:', data.data ? data.data.length : 0);
        
        // Actualizar todos los selects con clase medico_solicitante
        var selectElements = document.querySelectorAll('.medico_solicitante');
        selectElements.forEach(selectElement => {
            // Guardar valor actual
            const currentValue = selectElement.value;
            
            // Limpiar opciones
            selectElement.innerHTML = '';
            
            // Agregar opción por defecto
            var defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.text = 'Sin Asignar';
            selectElement.appendChild(defaultOption);
            
            // Llenar con nuevos datos
            if (data.data && data.data.length > 0) {
                data.data.forEach(item => {
                    var option = document.createElement('option');
                    option.value = item[0]; // guid
                    option.text = item[1];  // description
                    selectElement.appendChild(option);
                });
            }
            
            // Restaurar valor si existe
            if (currentValue) {
                selectElement.value = currentValue;
            }
        });
    })
    .catch(error => {
        console.error('Error al cargar médicos solicitantes:', error);
    });
}

// Función para cargar obras sociales por ubicación
function cargarObrasSocialesPorLocation(locationId) {
    console.log('[DEBUG] Cargando obras sociales para location_id:', locationId);
    
    fetch('/rellenar_select_cond_id', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            dNeeded: 'Description',
            TableId: 'nextris.ispricelist',
            idCond: locationId,
            colCond: 'location_id'
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('[DEBUG] Obras sociales recibidas:', data.data ? data.data.length : 0);
        
        // Actualizar todos los selects con clase obra_social
        var selectElements = document.querySelectorAll('.obra_social');
        selectElements.forEach(selectElement => {
            // Guardar valor actual
            const currentValue = selectElement.value;
            
            // Limpiar opciones
            selectElement.innerHTML = '';
            
            // Agregar opción por defecto
            var defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.text = 'Sin Asignar';
            selectElement.appendChild(defaultOption);
            
            // Llenar con nuevos datos
            if (data.data && data.data.length > 0) {
                data.data.forEach(item => {
                    var option = document.createElement('option');
                    option.value = item[0]; // guid
                    option.text = item[1];  // description
                    selectElement.appendChild(option);
                });
            }
            
            // Restaurar valor si existe
            if (currentValue) {
                selectElement.value = currentValue;
            }
        });
    })
    .catch(error => {
        console.error('Error al cargar obras sociales:', error);
    });
}

document.addEventListener("DOMContentLoaded", function() {

    // Inicializar funciones de seguridad y navegación
    safeInitDashboard();
    initNavTabs();

    // Toda la inicialización espera a obtener la configuración global
    // console.log("Obteniendo configuración de workflow...");
    obtenerConfigWorkflow().then(config => {
        globalAgendaTipo = config.agenda_tipo;
        globalAgendaEstudios = config.agenda_estudios;

        // --- Alta rápida de paciente ---
        var formPacienteRapido = document.getElementById('form_paciente_rapido');
        console.log('Buscando formulario de paciente rápido:', formPacienteRapido);
        
        if (formPacienteRapido) {
            console.log('Formulario encontrado, agregando event listener');
            formPacienteRapido.addEventListener('submit', function(e) {
                e.preventDefault();
                console.log('Formulario enviado, procesando datos...');
                
                const form = e.target;
                
                // Obtener valores de los campos
                const nombre = form.querySelector('[name="nombre"]').value;
                const apellido = form.querySelector('[name="apellido"]').value;
                const dni = form.querySelector('[name="dni"]').value;
                const fecha_nac = form.querySelector('[name="fecha_nac"]').value;
                const sexo = form.querySelector('[name="sexo"]').value;
                
                const datos = {
                    nombre: nombre,
                    apellido: apellido,
                    dni: dni,
                    fecha_nac: fecha_nac,
                    sexo: sexo
                };
                
                console.log('Datos a enviar:', datos);
                
                fetch('/agregar_paciente_rapido', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(datos)
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success && data.guid) {
                        showToast('Paciente agregado', 'El paciente fue creado correctamente.', '/static/templates/includes/toast/toast_success.html');
                        // Cerrar el modal
                        var modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modal_np_para_cita'));
                        modal.hide();
                        // Limpiar el formulario
                        form.reset();

                        // Refrescar la tabla de pacientes y seleccionar el nuevo
                        RellenarTabla('tabla-paciente',`/get_patients_min`);
                        setTimeout(function() {
                            var tabla = document.getElementById('tabla-paciente');
                            var tbody_ = tabla.querySelector('tbody');
                            var filas = tbody_.querySelectorAll('tr');
                            let found = false;
                            filas.forEach(function(fila) {
                                if (fila.dataset.id === data.guid) {
                                    // Simular selección
                                    filas.forEach(f => f.classList.remove('fila-seleccionada'));
                                    fila.classList.add('fila-seleccionada');
                                    // Ejecutar SeleccionarPaciente
                                    SeleccionarPaciente('tabla-paciente');
                                    found = true;
                                }
                            });
                            if (!found) {
                                showToast('Advertencia', 'Paciente agregado pero no se pudo seleccionar automáticamente.', '/static/templates/includes/toast/toast_alert.html');
                            }
                        }, 600);
                    } else {
                        showToast('Error', 'No se pudo agregar el paciente.', '/static/templates/includes/toast/toast_alert.html');
                    }
                })
                .catch(() => {
                    showToast('Error', 'No se pudo agregar el paciente.', '/static/templates/includes/toast/toast_alert.html');
                });
            });
        } else {
            console.error('No se encontró el formulario form_paciente_rapido en el DOM');
        }
        
        console.log('Configuración global:', globalAgendaTipo, globalAgendaEstudios);
        
        //Pestaña de paciente config - Cargar ubicaciones del usuario
        // selectedLocationId ya está declarada como variable global
        
        const locationSelector = document.getElementById('location_selector');
        const inputBusqueda = document.getElementById('busquedaSwitch');
        const btnSearch = document.getElementById('b_search');
        
        // Cargar ubicaciones del usuario
        fetch('/get_user_locations')
            .then(response => response.json())
            .then(locations => {
                if (locations && locations.length > 0) {
                    locations.forEach(loc => {
                        const option = document.createElement('option');
                        option.value = loc[0]; // guid
                        option.textContent = `${loc[1]} (${loc[2]})`; // name (code)
                        if (loc[4]) { // is_default
                            option.selected = true;
                            selectedLocationId = loc[0];
                            OrderData.location_id = loc[0]; // Asignar location_id a OrderData
                        }
                        locationSelector.appendChild(option);
                    });
                    
                    // Si hay una ubicación por defecto, cargar pacientes
                    if (selectedLocationId) {
                        cargarPacientesPorLocation(selectedLocationId);
                        inputBusqueda.disabled = false;
                        btnSearch.disabled = false;
                    }
                } else {
                    showToast('Advertencia', 'No tiene ubicaciones asignadas.', '/static/templates/includes/toast/toast_alert.html');
                }
            })
            .catch(error => {
                console.error('Error cargando ubicaciones:', error);
                showToast('Error', 'No se pudieron cargar las ubicaciones.', '/static/templates/includes/toast/toast_alert.html');
            });
        
        // Evento cambio de ubicación
        locationSelector.addEventListener('change', function() {
            selectedLocationId = this.value;
            if (selectedLocationId) {
                inputBusqueda.value = '';
                OrderData.location_id = selectedLocationId; // Actualizar location_id en OrderData
                cargarPacientesPorLocation(selectedLocationId);
                inputBusqueda.disabled = false;
                btnSearch.disabled = false;
                
                // Si es agenda por equipo, recargar equipos de esta ubicación
                if (globalAgendaTipo === 'equipo') {
                    cargarEquiposPorLocation(selectedLocationId);
                }
                
                // Recargar médicos solicitantes y obras sociales de esta ubicación
                cargarMedicosSolicitantesPorLocation(selectedLocationId);
                cargarObrasSocialesPorLocation(selectedLocationId);
            } else {
                // Limpiar tabla si no hay ubicación seleccionada
                const tabla = document.getElementById('tabla-paciente');
                const tbody = tabla.querySelector('tbody');
                tbody.innerHTML = '<tr><td colspan="5" class="text-center">Seleccione una ubicación</td></tr>';
                inputBusqueda.disabled = true;
                btnSearch.disabled = true;
            }
        });
        
        // Función para cargar pacientes por ubicación
        function cargarPacientesPorLocation(locationId, searchTerm = '') {
            console.log('[DEBUG] Cargando pacientes - locationId:', locationId, 'searchTerm:', searchTerm);
            fetch('/get_patients_by_location', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    location_id: locationId,
                    search_term: searchTerm
                })
            })
            .then(response => response.json())
            .then(data => {
                console.log('[DEBUG] Pacientes recibidos:', data.length, 'pacientes');
                const tabla = document.getElementById('tabla-paciente');
                const tbody = tabla.querySelector('tbody');
                tbody.innerHTML = '';
                
                if (data && data.length > 0) {
                    data.forEach(paciente => {
                        const tr = document.createElement('tr');
                        tr.classList.add('patient-row');
                        tr.dataset.id = paciente[0]; // guid
                        tr.innerHTML = `
                            <td>${paciente[1] || ''}</td>
                            <td>${paciente[2] || ''}</td>
                            <td>${paciente[3] || ''}</td>
                            <td>${paciente[4] || ''}</td>
                            <td>${paciente[5] || ''}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="5" class="text-center">No se encontraron pacientes</td></tr>';
                }
            })
            .catch(error => {
                console.error('Error cargando pacientes:', error);
                showToast('Error', 'No se pudieron cargar los pacientes.', '/static/templates/includes/toast/toast_alert.html');
            });
        }
        
        // Búsqueda con el botón
        if (btnSearch) {
            btnSearch.addEventListener('click', function() {
                if (selectedLocationId) {
                    cargarPacientesPorLocation(selectedLocationId, inputBusqueda.value);
                }
            });
        }
        
        // Buscar al presionar Enter en el input
        if (inputBusqueda) {
            inputBusqueda.addEventListener('keyup', function(e) {
                if (e.key === 'Enter' && selectedLocationId) {
                    cargarPacientesPorLocation(selectedLocationId, inputBusqueda.value);
                }
            });
        }

        //Aca selecciono al paciente
        var boton=document.getElementById("b_sel_pac_para_adm")
        boton.addEventListener("click",function(){SeleccionarPaciente('tabla-paciente')})

        document.getElementById("tabla-paciente").addEventListener("dblclick",function(){SeleccionarPaciente('tabla-paciente')})
        //-------------------------------

        // Examen
        RellenarSelect("tipo_examen","externalcode","nextris.IsModality")
        RellenarSelect("parte_cuerpo","Description","nextris.IsAnatomicalPart")
        RellenarTabla('tabla-estudios',`/get_exams_adm`)
        ConfigTablaEstudios('tabla-estudios','seleccionar-estudio','tabla-estudios-selec')
        ConfigTablaSeleccionados('tabla-estudios-selec','quitar-estudio','tabla-estudios','tabla-estudios-agenda')

        // ConfigFiltrarSelect('tipo_examen', 'tabla-estudios',2)
        // ConfigFiltrarSelect('parte_cuerpo', 'tabla-estudios',3)
        ConfigMultiSelect('tabla-estudios', 'tipo_examen', 2, 'parte_cuerpo', 3);

        // Inicializar el estado visual de la tabla de estudios
        setTimeout(function() {
            actualizarEstadoTablaEstudios();
        }, 500); // Dar tiempo a que se carguen las tablas

        // Agregar estilos CSS para tabla deshabilitada
        if (!document.getElementById('tabla-disabled-style')) {
            var style = document.createElement('style');
            style.id = 'tabla-disabled-style';
            style.innerHTML = `
                .table-disabled {
                    pointer-events: none !important;
                    cursor: not-allowed !important;
                    user-select: none !important;
                }
                .table-disabled tbody {
                    pointer-events: none !important;
                    cursor: not-allowed !important;
                }
                .table-disabled tr {
                    pointer-events: none !important;
                    cursor: not-allowed !important;
                }
                .table-disabled td {
                    pointer-events: none !important;
                    cursor: not-allowed !important;
                }
            `;
            document.head.appendChild(style);
        }

        ConfigurarTabla('tabla-paciente','botones_sp')
        ConfigurarTabla('tabla-estudios','boton_est')

        
        //Vericicamos si la configuracion es de agenda por medico o por equipo
        if (globalAgendaTipo === 'medico') {
            // Cargar profesionales mostrando nombre y apellido en vez de username
            fetch('/get_lista_de_med')
                .then(response => response.json())
                .then(data => {
                    var select = document.getElementById('prof_ag');
                    select.innerHTML = '';
                    var optionDefault = document.createElement('option');
                    optionDefault.value = '';
                    optionDefault.text = 'Seleccione un profesional';
                    select.appendChild(optionDefault);
                    data.forEach(function(item) {
                        // console.log("item: ", item);
                        var option = document.createElement('option');
                        option.value = item[0]; // guid
                        option.text = (item[2] || '') + ' ' + (item[3] || ''); // name + surname
                        select.appendChild(option);
                    });
                });
        }else if (globalAgendaTipo === 'equipo') {
            // Cargar equipos inicialmente (sin filtro o con ubicación por defecto)
            if (selectedLocationId) {
                cargarEquiposPorLocation(selectedLocationId);
            } else {
                cargarEquiposPorLocation(null); // Cargar todos
            }
        }
        
        // Función para cargar equipos por ubicación
        function cargarEquiposPorLocation(locationId) {
            console.log('[DEBUG] Cargando equipos para location_id:', locationId);
            
            let fetchOptions = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    location_id: locationId
                })
            };
            
            fetch('/get_lista_de_equipos', fetchOptions)
                .then(response => response.json())
                .then(data => {
                    console.log('[DEBUG] Equipos recibidos:', data.length);
                    
                    var tablaEquipos = document.getElementById('tabla-equipos');
                    var tbody = tablaEquipos.querySelector('tbody');
                    var select = document.getElementById('prof_ag');
                    
                    // Limpiar tabla y select
                    tbody.innerHTML = '';
                    select.innerHTML = '';
                    
                    // Agregar opción por defecto al select oculto
                    var optionDefault = document.createElement('option');
                    optionDefault.value = '';
                    optionDefault.text = 'Seleccione un equipo';
                    select.appendChild(optionDefault);
                    
                    if (data && data.length > 0) {
                        // Llenar la tabla y el select
                        data.forEach(function(item) {
                            // Agregar fila a la tabla
                            var fila = document.createElement('tr');
                            fila.style.cursor = 'pointer';
                            fila.setAttribute('data-equipo-id', item[0]); // guid
                            fila.innerHTML = `
                                <td>
                                    <div class="d-flex px-2 py-1">
                                        <div class="d-flex flex-column justify-content-center">
                                            <h6 class="mb-0 text-sm">${item[1] || ''}</h6>
                                        </div>
                                    </div>
                                </td>
                                <td>
                                    <p class="text-xs font-weight-bold mb-0">${item[2] || 'N/A'}</p>
                                </td>
                            `;
                            tbody.appendChild(fila);
                            
                            // Agregar opción al select oculto (para compatibilidad)
                            var option = document.createElement('option');
                            option.value = item[0]; // guid
                            option.text = (item[1] || ''); // aetitle
                            select.appendChild(option);
                        });
                    } else {
                        // Mostrar mensaje si no hay equipos
                        tbody.innerHTML = `
                            <tr>
                                <td colspan="2" class="text-center">
                                    <p class="text-sm text-muted mb-0">No hay equipos disponibles en esta ubicación</p>
                                </td>
                            </tr>
                        `;
                    }
                    
                    // Agregar event listener para selección de fila (solo una vez)
                    tbody.removeEventListener('click', equipoClickHandler);
                    tbody.addEventListener('click', equipoClickHandler);
                })
                .catch(error => {
                    console.error('Error al cargar equipos:', error);
                });
        }
        
        // Handler para clicks en tabla de equipos (definido fuera para poder removerlo)
        function equipoClickHandler(event) {
            var fila = event.target.closest('tr');
            if (fila && fila.hasAttribute('data-equipo-id')) {
                var tablaEquipos = document.getElementById('tabla-equipos');
                var tbody = tablaEquipos.querySelector('tbody');
                var select = document.getElementById('prof_ag');
                
                // Remover selección previa
                var filas = tbody.querySelectorAll('tr');
                filas.forEach(f => f.classList.remove('fila-seleccionada'));
                
                // Seleccionar nueva fila
                fila.classList.add('fila-seleccionada');
                
                // Actualizar el select oculto
                var equipoId = fila.getAttribute('data-equipo-id');
                select.value = equipoId;
                
                // Habilitar wish_date
                var wishDateInput = document.getElementById('wish_date');
                if (wishDateInput) {
                    wishDateInput.disabled = false;
                }
                
                // Trigger del evento change para que se ejecute la lógica existente
                var changeEvent = new Event('change', { bubbles: true });
                select.dispatchEvent(changeEvent);
            }
        }

        var boton = document.getElementById("b_conf_datos");
        boton.addEventListener("click", function() {
            var pillPaciente = document.getElementById('pills-paciente-tab');
            var pillExamen = document.getElementById('pills-examen-tab');
            var pillAgenda = document.getElementById('pills-agenda-tab');

            // Verificar si los objetos tienen la clase 'bg-success'
            var allSuccess = true;
            var messages = [];

            if (!pillPaciente.classList.contains('bg-success')) {
                pillPaciente.classList.add('bg-danger');
                messages.push("No es posible insertar citas: 'Paciente' no tiene la clase 'bg-success'");
                allSuccess = false;
            }

            if (!pillExamen.classList.contains('bg-success')) {
                pillExamen.classList.add('bg-danger');
                messages.push("No es posible insertar citas: 'Examen' no tiene la clase 'bg-success'");
                allSuccess = false;
            }

            if (!pillAgenda.classList.contains('bg-success')) {
                pillAgenda.classList.add('bg-danger');
                messages.push("No es posible insertar citas: 'Agenda' no tiene la clase 'bg-success'");
                allSuccess = false;
            }

            // Si todos los objetos tienen la clase 'bg-success', ejecutar InsertarCitas
            if (allSuccess) {
                InsertarCitas();
            } else {
                // Mostrar el toast con los mensajes de error
                showToast('Ha ocurrido un problema', messages.join('<br>'), "/static/templates/includes/toast/toast_alert.html");
            }
        });

        document.getElementById('prof_ag').addEventListener('change', function() {
            var calendarEl = document.getElementById('calendario');
            var profesional = document.getElementById('prof_ag').value;
            var externalEventsContainer = document.getElementById('external-events');
            var eventDivs = externalEventsContainer.querySelectorAll('.fc-event');
            var wishDateInput = document.getElementById('wish_date');
            wishDateInput.disabled = false;
            // ...validación y lógica de colores...
            if (globalAgendaTipo === 'equipo') {
                eventDivs.forEach(function(eventDiv) {
                    eventDiv.style.backgroundColor = '#28a745';
                    eventDiv.style.borderColor = '#218838';
                });
            } else {
                eventDivs.forEach(function(eventDiv) {
                    var eventData = JSON.parse(eventDiv.dataset.event);
                    var studytype_id = eventData.idExam || eventData.examId;
                    if (profesional && studytype_id) {
                        fetch('/verificar_asignabilidad_estudio', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ med_id: profesional, studytype_id: studytype_id })
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success && data.asignable) {
                                eventDiv.style.backgroundColor = '#28a745';
                                eventDiv.style.borderColor = '#218838';
                            } else {
                                eventDiv.style.backgroundColor = '#dc3545';
                                eventDiv.style.borderColor = '#b21f2d';
                            }
                        })
                        .catch(() => {
                            eventDiv.style.backgroundColor = '#ffc107';
                            eventDiv.style.borderColor = '#856404';
                        });
                    } else {
                        eventDiv.style.backgroundColor = '#6c757d';
                        eventDiv.style.borderColor = '#343a40';
                    }
                });
            }
            if (calendar) {
                ReconfigurarCalendario(calendar)
            } else {
                CrearCalendario()
            }
        });

        // Al cambiar wish_date, posicionar el calendario en esa fecha
        var wishDateInput = document.getElementById('wish_date');
        wishDateInput.addEventListener('change', function() {
            if (calendar && wishDateInput.value) {
                calendar.gotoDate(wishDateInput.value);}
        });
        //Con este codigo volvemos para atrás los cambios realizados en el calendario.
        document.getElementById('b_undo').addEventListener('click', function() {
            QuitarEvento()
        });
        //--------------------
    });});
