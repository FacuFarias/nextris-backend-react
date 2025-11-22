// Este archivo contiene funciones JavaScript para la gestión de la distribución de informes en la aplicación NextRIS.
// Muchas funciones que se utilizan en esta sección están definidas en otros archivos JS, como loader.js y toast.js, principalmente nrframework.js.
// No se deberán crear funciones duplicadas aquí si ya existen en esos archivos.

//Objeto con datos de la orden
let OrderData = {
    patientId: null,
    exams:[],
    medico_solicitante: null,
    obra_social:null,
};

function AdmisionarCita(TablaId) {


    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    
    if (filaSeleccionada) {
        var dataId = filaSeleccionada.getAttribute('data-id');
        console.log(dataId)
    fetch('/api/admisionar_cita', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            
            body: JSON.stringify({ cita_id: dataId })
        })
        .then(response => response.json())
        .then(data => {
            // Manejar la respuesta del servidor
            if (data.success) {
                // Eliminar la fila visualmente
                filaSeleccionada.remove();
                
                // Verificar si la tabla quedó vacía después de eliminar
                verificarYMostrarMensajeTablaVacia(TablaId);
                
                // Mostrar notificación toast de éxito
                showToast('Éxito', `Cita admisionada correctamente. Admisión: ${data.admision || 'N/A'}`, '/templates/includes/toast/toast_success.html');
            } else {
                // Mostrar error con toast
                showToast('Error', `Hubo un problema al admisionar la cita: ${data.error || data.message}`, '/templates/includes/toast/toast_alert.html');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('Error', 'Hubo un error al admisionar la cita.', '/templates/includes/toast/toast_alert.html');
        });
    }

}

function AbrirCalendarioParaEditar(TablaId) {
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    
    if (filaSeleccionada) {
        var dataId = filaSeleccionada.getAttribute('data-id');
        
        // Extraer el nombre del paciente de la segunda columna
        var OrderId = filaSeleccionada.getAttribute('data-id');
        var celdas = filaSeleccionada.querySelectorAll('td');
        var nombrePaciente = celdas[0] ? celdas[0].textContent.trim() : '';
        var fecha = celdas[1] ? celdas[1].textContent.trim() : '';
        var mref = celdas[2] ? celdas[2].textContent.trim() : '';
        var examen = celdas[3] ? celdas[3].textContent.trim() : '';
        // Cargar el contenido HTML del archivo y establecer el data-id
        $.get('/b_agenda_editar_cita.html', function(data) {
            // Reemplazar los marcadores en el contenido HTML
            var informeContent = `
              <div class="informe-details" id="data" data-id="${dataId}">
                ${data} <!-- Contenido del archivo generacion_informe.html -->
              </div>
            `;
            // Reemplazar el marcador de nombre del paciente y examen
            informeContent = informeContent.replace('<!--Nombre del paciente-->', nombrePaciente);
            informeContent = informeContent.replace('<!--examen-->', examen);
            $('#calendario-content').html(informeContent);
            $('#calendario-content').attr('data-id', dataId);
            
            // Configuro la funcion para el boton de confirmar
            var evento = []
            document.getElementById('editar_fecha_cita').addEventListener('click',function(){
                evento._instance.range.guid=OrderId
                fetch('/actualizar_evento_cita', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    
                    body: JSON.stringify(evento._instance.range),
                })
                .then(response => response.json())
                .then(data => {
                    // Manejar la respuesta del servidor
                    if (data.success) {
                        alert("La cita se ha editado correctamente.");
                        window.location.reload();
                        // Aquí puedes limpiar OrderData o realizar cualquier otra acción necesaria
                    } else {
                        alert("Hubo un problema al insertar las citas: " + data.message);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert("Hubo un error al insertar las citas.");
                });
            })

            fetch('/get_events', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ prof_ag_text: mref })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Received events and work hours:', data);
                document.getElementById('card-agenda').hidden = false;

                var calendarEl = document.getElementById('calendario');
                if (window.calendar) {
                    window.calendar.destroy();
                }

                var businessHours = data.work_hours.map(wh => ({
                    daysOfWeek: [wh.day],
                    startTime: wh.start,
                    endTime: wh.end
                }));

                // Iterar sobre data.events y modificar eventos con guid = OrderId
                var events = data.events.map(event => {
                    if (event.guid === OrderId) {
                        event.backgroundColor = 'green';
                        event.editable = true;
                    }
                    return event;
                });

                window.calendar = new FullCalendar.Calendar(calendarEl, {
                    timeZone: 'local', // Usa la zona horaria local del navegador
                    droppable: false,
                    eventChange: function(info) {
                        evento=info.event
                        console.log('Evento cambiado:', info.event);
                    },
                    initialView: 'timeGridWeek',
                    editable: true,
                    selectable: true,
                    events: events,
                    headerToolbar: {
                        left: 'prev,next today',
                        center: 'title',
                        right: 'timeGridDay,timeGridWeek,dayGridMonth'
                    },
                    slotDuration: '00:20:00',
                    slotMinTime: '00:00:00',
                    slotMaxTime: '24:00:00',
                    businessHours: businessHours,
                    selectConstraint: businessHours,
                    eventConstraint: businessHours,
                });

                new FullCalendar.Draggable(document.getElementById('external-events'), {
                    itemSelector: '.fc-event',
                    eventData: function(eventEl) {
                        return JSON.parse(eventEl.dataset.event);
                    }
                });

                window.calendar.render();
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }).fail(function() {
            console.error('Error al cargar el archivo generacion_informe.html');
        });

        // Ocultar los elementos #card_ordenes y #card_buscar
        $('#card_citas').hide();
        $('#card_buscar').hide();

    } else {
        console.log('No hay fila seleccionada.');
    }

    
}

function SetDeleteButton(buttonId,TablaId,routeDelete){
    var boton = document.getElementById(buttonId);
    boton.addEventListener('click', function (event) {
        event.preventDefault();
    
        // Obtener la fila seleccionada
        var tabla = document.getElementById(TablaId);
        var tbody_= tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
        if (filaSeleccionada) {
            var id = filaSeleccionada.dataset.id;
            
            fetch(routeDelete, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ id: id }),
            })
            .then(response => response.json())
            .then(data => {
                filaSeleccionada.remove();
            })
            .catch(error => {
                console.error('Error:', error);
            });
        } else {
            console.warn('No hay fila seleccionada.');
        }
    });
}

/**
 * Muestra el mensaje de tabla vacía
 */
function mostrarMensajeTablaVacia(tabla, tbody_) {
    // Obtener número de columnas
    var numCols = tabla.querySelectorAll('thead th').length;
    console.log('[mostrarMensajeTablaVacia] Número de columnas:', numCols);
    
    // Limpiar por si acaso
    tbody_.innerHTML = '';
    
    // Crear mensaje
    var row = document.createElement('tr');
    row.className = 'mensaje-tabla-vacia fila-blocked'; // Clase para identificar y bloquear
    row.style.pointerEvents = 'none'; // No clickeable
    row.style.cursor = 'default'; // Cursor normal
    var cell = document.createElement('td');
    cell.colSpan = numCols;
    cell.className = 'text-center text-muted py-5';
    cell.style.fontSize = '1.1rem';
    cell.style.backgroundColor = '#f8f9fa';
    cell.innerHTML = `
        <div class="d-flex flex-column align-items-center justify-content-center py-3">
            <i class="fas fa-check-circle text-success mb-3" style="font-size: 3rem;"></i>
            <strong class="mb-2">¡Todo al día!</strong>
            <p class="text-muted mb-0">No hay citas pendientes de admisión</p>
        </div>
    `;
    row.appendChild(cell);
    tbody_.appendChild(row);
    
    console.log('[mostrarMensajeTablaVacia] Fila de mensaje creada y agregada');
    console.log('[mostrarMensajeTablaVacia] Contenido del tbody:', tbody_.innerHTML.substring(0, 100) + '...');
    console.log('[mostrarMensajeTablaVacia] Número de filas en tbody:', tbody_.children.length);
    
    // Deshabilitar todos los botones de acción
    var botones = document.getElementsByClassName('botones_ec');
    console.log('[mostrarMensajeTablaVacia] Deshabilitando', botones.length, 'botones');
    for (var i = 0; i < botones.length; i++) {
        botones[i].disabled = true;
        botones[i].classList.remove('btn-success', 'btn-danger');
        botones[i].classList.add('btn-secondary');
    }
}

/**
 * Verifica si el tbody de una tabla está vacío y muestra mensaje si es necesario
 */
function verificarYMostrarMensajeTablaVacia(tablaId) {
    console.log('[verificarYMostrarMensajeTablaVacia] Verificando tabla:', tablaId);
    
    var tabla = document.getElementById(tablaId);
    if (!tabla) {
        console.error('[verificarYMostrarMensajeTablaVacia] No se encontró la tabla con ID:', tablaId);
        return;
    }
    
    var tbody = tabla.querySelector('tbody');
    if (!tbody) {
        console.error('[verificarYMostrarMensajeTablaVacia] No se encontró tbody en la tabla');
        return;
    }
    
    // Contar filas (tr) dentro del tbody, excluyendo el mensaje si ya existe
    var filas = tbody.querySelectorAll('tr:not(.mensaje-tabla-vacia)');
    console.log('[verificarYMostrarMensajeTablaVacia] Cantidad de filas encontradas:', filas.length);
    
    // Si no hay filas de datos, mostrar mensaje
    if (filas.length === 0) {
        console.log('[verificarYMostrarMensajeTablaVacia] ✓ Tbody vacío - Mostrando mensaje');
        mostrarMensajeTablaVacia(tabla, tbody);
    } else {
        console.log('[verificarYMostrarMensajeTablaVacia] ✓ Hay', filas.length, 'filas con datos');
    }
}



//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)

function ConfigurarTabla(TablaId,botonesClass){
    
    var tabla = document.getElementById(TablaId);
    var tbody_g= tabla.querySelector('tbody');
    tbody_g.addEventListener('click', function (event) {
        var filas = tbody_g.querySelectorAll('tr');
        for (var i = 0; i < filas.length; i++) {
            filas[i].classList.remove('fila-seleccionada');
        }
        
        var fila = event.target.closest('tr');
        if (fila) {
            if(!fila.classList.contains('fila-blocked')){
            fila.classList.add('fila-seleccionada');            
            var botones = document.getElementsByClassName(botonesClass);
            for (var i = 0; i < botones.length; i++) {
                var boton = botones[i];
                boton.disabled = false;
        
                // Verificar si el botón tiene la clase 'delete_b'
                if (boton.classList.contains('delete_b')) {
                    boton.classList.remove('btn-secondary');
                    boton.classList.add('btn-danger');
                } else {
                    boton.classList.remove('btn-secondary');
                    boton.classList.add('btn-success');
                }
            }
        }
        } else {
            var botones = document.getElementsByClassName('botones');
            for (var i = 0; i < botones.length; i++) {
                var boton = botones[i];
                boton.disabled = true;
                
        
                // Verificar si el botón tiene la clase 'delete_b'
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

// IdCond sería el dato que quiero para filtrar en la columna colCond
function RellenarSelectCondicionalId(SelectId,dNeeded,TableId,idCond,colCond,selectedText = null){
    fetch('/rellenar_select_cond_id', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ dNeeded: dNeeded, TableId:TableId, idCond:idCond,colCond:colCond }),
    })
    .then(response => response.json())
    .then(data => {
        var selectElement = document.getElementById(SelectId);

    // Limpiar cualquier opción existente en el <select>
        selectElement.innerHTML = '';
        for (var i = 0; i < data.data.length; i++) {
            var option = document.createElement('option');
            option.value= data.data[i][0]
            option.text= data.data[i][1]
            selectElement.appendChild(option);
        }
        // Seleccionar la opción con el texto específico si está presente
        if (selectedText) {
            for (var i = 0; i < selectElement.options.length; i++) {
                if (selectElement.options[i].text === selectedText) {
                    selectElement.selectedIndex = i;
                    break;
                }
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function FiltrarText(labelId, tablaId,column) {
        var filtro = document.getElementById(labelId).value.toLowerCase();
        var filas = document.getElementById(tablaId).getElementsByTagName('tbody')[0].getElementsByTagName('tr');

        for (var i = 0; i < filas.length; i++) {
            var descripcion = filas[i].getElementsByTagName('td')[column].innerText.toLowerCase();

            // Ocultar o mostrar la fila según el filtro
            filas[i].style.display = descripcion.includes(filtro) ? '' : 'none';
        }
}

function FiltrarSelect(labelId, tablaId,column) {
    var selectElement = document.getElementById(labelId);
    var selectedOptionText = selectElement.options[selectElement.selectedIndex].text.toLowerCase();;
    
    var filas = document.getElementById(tablaId).getElementsByTagName('tbody')[0].getElementsByTagName('tr');

    for (var i = 0; i < filas.length; i++) {
        var descripcion = filas[i].getElementsByTagName('td')[column].innerText.toLowerCase();

        // Ocultar o mostrar la fila según el filtro
        filas[i].style.display = descripcion.includes(selectedOptionText) ? '' : 'none';
    }
}

// Configuración de filtros sumatorios
function FiltroSumatorioCitasAdmision() {
    console.log("FiltroSumatorioCitasAdmision called");
    FiltroSumatorioTabla(
        'tabla-citas',
        [
            {inputId: 'nombre_pat', colIdx: 0},
            {inputId: 'medico_referente', colIdx: 2},
            {inputId: 'medico_solicitante', colIdx: 4},
            {inputId: 'equipo', colIdx: 3}
        ],
        null // No hay fechas
    );
}

document.addEventListener("DOMContentLoaded", function() {
    // Imprimir lista en PDF
    document.getElementById('imprimir_lista').addEventListener('click', function() {
        var tabla = document.getElementById('tabla-citas');
        var filas = tabla.querySelectorAll('tbody tr');
        var columnas = Array.from(tabla.querySelectorAll('thead th')).map(th => th.textContent.trim());
        var datos = [];
        filas.forEach(function(fila) {
            if (fila.style.display !== 'none') {
                var celdas = fila.querySelectorAll('td');
                var filaDatos = [];
                celdas.forEach(function(celda) {
                    filaDatos.push(celda.textContent.trim());
                });
                datos.push(filaDatos);
            }
        });

        // Generar PDF usando jsPDF y autoTable
        var doc = new window.jspdf.jsPDF();
        doc.autoTable({
            head: [columnas],
            body: datos,
            styles: { fontSize: 10 },
            margin: { top: 20 }
        });
        doc.save('citas_admisionar.pdf');
    });
 
    RellenarTabla('tabla-citas', '/get_citas_for_today')
    ConfigurarTabla('tabla-citas','botones_ec')
    
    // Verificar si la tabla está vacía después de cargar los datos
    // Usar setTimeout para esperar a que termine el fetch
    setTimeout(function() {
        verificarYMostrarMensajeTablaVacia('tabla-citas');
    }, 1000); // Esperar 1 segundo para que termine de cargar
    
    RellenarSelect('medico_solicitante', 'description', 'nextris.isrequestingphysician')
    RellenarSelectCondicionalId('medico_referente','username','nextris.tbuser','88e340f5-6fa5-4df1-aef6-c911625a4427','idrole')
    // Modal de confirmación para eliminar cita
    document.getElementById('eliminar_cita').addEventListener('click', function() {
        var tabla = document.getElementById('tabla-citas');
        var tbody_ = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
        if (filaSeleccionada) {
            var celdas = filaSeleccionada.querySelectorAll('td');
            var paciente = celdas[0] ? celdas[0].textContent : '';
            var fecha = celdas[1] ? celdas[1].textContent : '';
            var med_ref = celdas[2] ? celdas[2].textContent : '';
            var examen = celdas[3] ? celdas[3].textContent : '';
            var med_sol = celdas[4] ? celdas[4].textContent : '';
            var dataId = filaSeleccionada.getAttribute('data-id') || '';

            // Construyo el contenido del modal
            var modalHtml = `
                <div class="modal fade" id="modalEliminarCita" tabindex="-1" aria-labelledby="modalEliminarCitaLabel" aria-hidden="true">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="modalEliminarCitaLabel">Confirmar eliminación de cita</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <p>¿Está seguro que desea eliminar la siguiente cita?</p>
                                <ul>
                                    <li><strong>Paciente:</strong> ${paciente}</li>
                                    <li><strong>Fecha:</strong> ${fecha}</li>
                                    <li><strong>Médico referente:</strong> ${med_ref}</li>
                                    <li><strong>Examen:</strong> ${examen}</li>
                                    <li><strong>Médico solicitante:</strong> ${med_sol}</li>
                                </ul>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                                <button type="button" class="btn btn-danger" id="confirmarEliminarCita">Eliminar</button>
                            </div>
                        </div>
                    </div>
                </div>`;

            // Agrego el modal al body si no existe
            if (!document.getElementById('modalEliminarCita')) {
                document.body.insertAdjacentHTML('beforeend', modalHtml);
            }

            var modal = new bootstrap.Modal(document.getElementById('modalEliminarCita'));
            modal.show();

            // Elimino cualquier listener previo para evitar duplicados
            var btnConfirmar = document.getElementById('confirmarEliminarCita');
            btnConfirmar.onclick = function() {
                // Lógica de eliminación real
                fetch('/eliminar_cita', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: dataId })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        modal.hide();
                        filaSeleccionada.remove();
                        showToast('Éxito', 'La cita ha sido eliminada correctamente.', '/templates/includes/toast/toast_success.html');
                    } else {
                        showToast('Error', 'No se pudo eliminar la cita.', '/templates/includes/toast/toast_alert.html');
                    }
                })
                .catch(error => {
                    showToast('Error', 'Error al eliminar la cita.', '/templates/includes/toast/toast_alert.html');
                });
            };
        } else {
            showToast('Error', 'Seleccione una cita para eliminar.', '/templates/includes/toast/toast_alert.html');
        }
    });

    

    document.getElementById('nombre_pat').addEventListener('input', FiltroSumatorioCitasAdmision);
    document.getElementById('medico_referente').addEventListener('input', FiltroSumatorioCitasAdmision);
    document.getElementById('medico_solicitante').addEventListener('input', FiltroSumatorioCitasAdmision);
    document.getElementById('equipo').addEventListener('input', FiltroSumatorioCitasAdmision);

       
    // document.getElementById('b_admisionar_cita').addEventListener('click', function(){
    //     AdmisionarCita('tabla-citas')
    // })

    document.getElementById('b_admisionar_cita').addEventListener('click', async function(){
        var tabla = document.getElementById('tabla-citas');
        var tbody_ = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');

        if (filaSeleccionada) {
            var celdas = filaSeleccionada.querySelectorAll('td');
            var dataId = filaSeleccionada.getAttribute('data-id');
            var paciente = celdas[0] ? celdas[0].textContent : ''
            var fecha = celdas[1] ? celdas[1].textContent : ''
            var med_ref = celdas[2] ? celdas[2].textContent : ''
            var examen = celdas[3] ? celdas[3].textContent : ''
            var med_sol = celdas[4] ? celdas[4].textContent : ''
            document.getElementById('idevent').value = dataId || ''
        }
        
        // Cargar equipos con el ID del evento para obtener preselección
        try {
            const response = await fetch(`/get_equipo_modal?idevent=${dataId}`);
            const data = await response.json();
            
            console.log('Datos recibidos:', data); // Debug
            
            // Validar que existan equipos
            if (!data || !data.equipos || !Array.isArray(data.equipos)) {
                console.error('Respuesta inválida del servidor:', data);
                showToast('Error', 'No se pudieron cargar los equipos disponibles', '/templates/includes/toast/toast_error.html');
                return;
            }
            
            // Limpiar tabla
            const tbody = document.getElementById('tabla-equipo-modal').querySelector('tbody');
            tbody.innerHTML = '';
            
            // Validar que haya equipos disponibles
            if (data.equipos.length === 0) {
                tbody.innerHTML = '<tr><td colspan="2" class="text-center text-muted">No hay equipos disponibles para este tipo de examen</td></tr>';
            } else {
                // Llenar tabla con equipos
                data.equipos.forEach(equipo => {
                    const row = document.createElement('tr');
                    row.setAttribute('data-id', equipo[0]);
                    
                    // Si es el equipo asignado, agregarlo con clase preseleccionada y badge
                    if (equipo[4] === 1) { // es_asignado
                        row.classList.add('fila-seleccionada');
                        row.innerHTML = `
                            <td>${equipo[1]}</td>
                            <td>
                                ${equipo[2]}
                                <span class="badge bg-success ms-2">
                                    <i class="fas fa-check me-1"></i>Asignado
                                </span>
                            </td>
                        `;
                        // Establecer el idequip preseleccionado
                        document.getElementById('idequip').value = equipo[0];
                    } else {
                        row.innerHTML = `
                            <td>${equipo[1]}</td>
                            <td>${equipo[2]}</td>
                        `;
                    }
                    
                    tbody.appendChild(row);
                });
            }
            
            // Configurar tabla con clicks
            ConfigurarTabla('tabla-equipo-modal','botones_adm_cita');
            
        } catch (error) {
            console.error('Error cargando equipos:', error);
            showToast('Error', 'Error al cargar equipos: ' + error.message, '/templates/includes/toast/toast_error.html');
            return;
        }
        
        // Configurar selección de equipo
        document.getElementById('tabla-equipo-modal').addEventListener('click',function(){
            var filaSeleccionada = document.getElementById('tabla-equipo-modal').querySelector('tbody').querySelector('.fila-seleccionada');
            var dataId = filaSeleccionada ? filaSeleccionada.getAttribute('data-id') : '';
            document.getElementById('idequip').value = dataId;
            console.log('Equipo seleccionado:', document.getElementById('idequip').value)
        })
        
        // Mostrar el modal SIN backdrop (solución definitiva al problema)
        var modalElement = document.getElementById('modal_adm_cita');
        var modal = new bootstrap.Modal(modalElement, {
            backdrop: false,  // No crear backdrop
            keyboard: true
        });
        modal.show();
    })


    document.getElementById('Form_adm_cita').addEventListener('submit', function(event) {
        event.preventDefault(); // Evita que el formulario se envíe de forma predeterminada
        
        // Obtén los datos del formulario
        var idevent=document.getElementById('idevent').value;
        var idequip=document.getElementById('idequip').value;
        
        // Crear objeto JSON con los datos del formulario
        var formData = {
            cita_id: idevent,
            equipo_id: idequip
        };
    
        // Realiza la lógica que necesites con los datos del formulario
        fetch('/api/admisionar_cita', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData),
        })
        .then(response => response.json())
        .then(data => {
            // Maneja la respuesta del servidor
            if (data.success) {
                // Cierra el modal correctamente
                var modalElement = document.getElementById('modal_adm_cita');
                var modal = bootstrap.Modal.getInstance(modalElement);
                if (modal) {
                    modal.hide();
                }
    
                // Obtener y eliminar la fila seleccionada visualmente
                var tabla = document.getElementById('tabla-citas');
                var tbody_= tabla.querySelector('tbody');
                var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
                
                if (filaSeleccionada) {
                    // Eliminar la fila de la tabla
                    filaSeleccionada.remove();
                    console.log('Fila de cita eliminada visualmente');
                    
                    // Verificar si la tabla quedó vacía después de eliminar
                    verificarYMostrarMensajeTablaVacia('tabla-citas');
                } else {
                    console.warn('No hay fila seleccionada.');
                }
                
                // Mostrar notificación toast de éxito
                showToast('Éxito', `Cita admisionada correctamente. Admisión: ${data.admision || 'N/A'}`, '/templates/includes/toast/toast_success.html');
            } else {
                // Maneja los errores
                console.error('Error al admisionar la cita:', data.error);
                showToast('Error', `Error al admisionar la cita: ${data.error}`, '/templates/includes/toast/toast_alert.html');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('Error', 'Error de conexión al admisionar la cita.', '/templates/includes/toast/toast_alert.html');
        });
    });
    
    // Ya no necesitamos event listeners de limpieza porque usamos backdrop: false
    
})
