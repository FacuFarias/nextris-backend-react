//Objeto con datos de la orden
let OrderData = {
    patientId: null,
    exams:[],
    medico_solicitante: null,
    obra_social:null,
};
var businessHours;
var evento; // Declarar evento como una variable global


function AbrirCalendarioParaEditar(TablaId) {
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    
    if (filaSeleccionada) {
        var dataId = filaSeleccionada.getAttribute('data-id');
        var OrderId = dataId;
        var nombrePaciente = filaSeleccionada.querySelectorAll('td')[0].textContent.trim();
        var fecha = filaSeleccionada.querySelectorAll('td')[1].textContent.trim();
        var mref = filaSeleccionada.querySelectorAll('td')[2].textContent.trim();
        var examen = filaSeleccionada.querySelectorAll('td')[3].textContent.trim();
        var equipo = filaSeleccionada.querySelectorAll('td')[4].textContent.trim();

        // Cargar el contenido HTML del archivo y establecer el data-id
        $.get('/b_agenda_editar_cita.html', function(data) {
            var informeContent = `
              <div class="informe-details" id="data" data-id="${dataId}">
                ${data}
              </div>
            `;
            informeContent = informeContent.replace('<!--Nombre del paciente-->', nombrePaciente);
            informeContent = informeContent.replace('<!--examen-->', examen);
            $('#calendario-content').html(informeContent);
            $('#calendario-content').attr('data-id', dataId);

            var evento = null;
            document.getElementById('editar_fecha_cita').addEventListener('click', function() {
                if (evento) {
                    evento.setProp('guid', OrderId);
                    fetch('/actualizar_evento_cita', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            id: evento.id,
                            start: evento.start,
                            end: evento.end,
                            guid: evento.extendedProps.guid
                        }),
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            showToast("Éxito", "La cita se ha editado correctamente.", "/templates/includes/toast/toast_success.html");
                            $('#card_citas').show();
                            $('#card_buscar').show();
                            $('#data').remove();
                            var tablaCitas = document.getElementById('tabla-citas');
                            var filaSeleccionadaCita = tablaCitas.querySelector('.fila-seleccionada');
                            if (filaSeleccionadaCita) {
                                filaSeleccionadaCita.querySelectorAll('td')[1].textContent = evento.start.toISOString().split('T')[0] + " " + evento.start.toTimeString().split(' ')[0];
                            }
                        } else {
                            showToast("Error", "Hubo un problema al insertar las citas: " + data.message, "/templates/includes/toast/toast_alert.html");
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        showToast("Error", "Hubo un error al insertar las citas.", "/templates/includes/toast/toast_alert.html");
                    });
                }
            });

            // Ahora envío equipo y guid al backend para obtener los eventos correctos
            fetch('/get_events_para_editar', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ guid: OrderId, equipo: equipo })
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('card-agenda').hidden = false;
                var calendarEl = document.getElementById('calendario');
                if (window.calendar) {
                    window.calendar.destroy();
                }
                businessHours = data.work_hours.map(wh => ({
                    daysOfWeek: [wh.day],
                    startTime: wh.start,
                    endTime: wh.end
                }));
                console.log(data);
                var events = data.events.map(event => {
                    let ev = {
                        id: event.guid,
                        guid: event.guid,
                        start: event.start,
                        end: event.end,
                        editable: event.editable,
                        backgroundColor: event.editable ? '#800080' : '#bdbdbd', // morado para editable, gris para fijo
                        borderColor: event.editable ? '#800080' : '#bdbdbd',
                        title: `${event.nombre} - ${event.exam}`,
                    };
                    if (event.editable) {
                        evento = ev;
                    }
                    return ev;
                });
                window.calendar = new FullCalendar.Calendar(calendarEl, {
                    timeZone: 'local',
                    droppable: false,
                    eventChange: function(info) {
                        evento = info.event;
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
                    allDaySlot: false,
                });
                window.calendar.render();
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
                evento = window.calendar.getEventById(OrderId);
            })
            .catch(error => {
                console.error('Error:', error);
            });

            document.getElementById('wish_date').addEventListener('change', function() {
                var nuevaFecha = this.value;
                if (evento) {
                    var nuevaFechaDate = new Date(nuevaFecha + 'T00:00:00');
                    var startTime = businessHours.find(bh => bh.daysOfWeek.includes(nuevaFechaDate.getDay())).startTime;
                    var nuevaFechaConHora = new Date(nuevaFechaDate.setHours(parseInt(startTime.split(':')[0]), parseInt(startTime.split(':')[1])));
                    var duracion = evento.end.getTime() - evento.start.getTime();
                    var nuevaFechaFin = new Date(nuevaFechaConHora.getTime() + duracion);
                    evento.setStart(nuevaFechaConHora);
                    evento.setEnd(nuevaFechaFin);
                    window.calendar.gotoDate(nuevaFechaConHora);
                }
            });

            document.getElementById('volver').addEventListener('click',function(){
                $('#card_citas').show();
                $('#card_buscar').show();
                $('#data').remove();
            })
        }).fail(function() {
            console.error('Error al cargar el archivo generacion_informe.html');
        });

        $('#card_citas').hide();
        $('#card_buscar').hide();
    } else {
        console.log('No hay fila seleccionada.');
    }
}



    function FiltroSumatorioCitas() {
        FiltroSumatorioTabla(
            'tabla-citas',
            [
                {inputId: 'nombre_pat', colIdx: 0},
                {inputId: 'medico_referente', colIdx: 2},
                {inputId: 'medico_solicitante', colIdx: 5},
                {inputId: 'equipo', colIdx: 4}
            ],
            {desdeId: 'fecha_desde', hastaId: 'fecha_hasta', colIdx: 1}
        );
    }


document.addEventListener("DOMContentLoaded", function() {

    // Escuchar todos los campos de filtro
    document.getElementById('fecha_desde').addEventListener('change', FiltroSumatorioCitas);
    document.getElementById('fecha_hasta').addEventListener('change', FiltroSumatorioCitas);
    document.getElementById('nombre_pat').addEventListener('input', FiltroSumatorioCitas);
    document.getElementById('medico_referente').addEventListener('input', FiltroSumatorioCitas);
    document.getElementById('medico_solicitante').addEventListener('input', FiltroSumatorioCitas);
    document.getElementById('equipo').addEventListener('input', FiltroSumatorioCitas);
 
    RellenarTabla('tabla-citas', '/get_citas')
    ConfigurarTabla('tabla-citas','botones_ec')
    


    // mostrar un modal de confirmación para eliminar cita
    document.getElementById('eliminar_cita').addEventListener('click', function() {
            var tabla = document.getElementById('tabla-citas');
            var tbody_ = tabla.querySelector('tbody');
            var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
            if (filaSeleccionada) {
                    var celdas = filaSeleccionada.querySelectorAll('td');
                    var paciente = celdas[0].textContent;
                    var fecha = celdas[1].textContent;
                    var med_ref = celdas[2].textContent;
                    var examen = celdas[3].textContent;
                    var med_sol = celdas[4].textContent;
                    var dataId = filaSeleccionada.getAttribute('data-id');

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
                            // Aquí va la lógica de eliminación real
                            console.log('Eliminando cita con ID:', dataId);
                            fetch('/eliminar_cita', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ id_cita: dataId })
                            })
                            .then(response => response.json())
                            .then(data => {
                                    if (data.success) {
                                            modal.hide();
                                            // Elimino la fila de la tabla
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


    document.getElementById('editar_cita').addEventListener('click', function(){
        var tabla = document.getElementById('tabla-citas');
        var tbody_ = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');

        if (filaSeleccionada) {
            var celdas = filaSeleccionada.querySelectorAll('td');
            var dataId = filaSeleccionada.getAttribute('data-id');
            var paciente= celdas[0].textContent
            var med_ref = celdas[2].textContent
            var examen = celdas[3].textContent
            var equipo = celdas[4].textContent
            var med_sol = celdas[5].textContent
            var fecha = celdas[1].textContent
            document.getElementById('ex_old').value=examen
            document.getElementById('t_mod_ec').textContent=paciente
            document.getElementById('nombre_modal').value=paciente
            document.getElementById('id_ec').value=dataId
            document.getElementById('fecha').value=fecha
        }
        RellenarSelect('s_msol', 'description', 'nextris.isrequestingphysician', med_sol);
        RellenarSelectCondicionalId('s_mref', 'username', 'nextris.tbuser', '88e340f5-6fa5-4df1-aef6-c911625a4427', 'idrole', med_ref);
        // Mostrar el modal
        var modal = new bootstrap.Modal(document.getElementById('modal_ec'));
        modal.show();
    })

    RellenarTabla('tabla-exam-modal', '/get_exams_modal')
    ConfigurarTabla('tabla-exam-modal','botones_ecm')
    tabla_modal=document.getElementById('tabla-exam-modal')

    tabla_modal.addEventListener('dblclick', function(){
        var tbodyest = tabla_modal.querySelector('tbody');
        var filaSeleccionada = tbodyest.querySelector('.fila-seleccionada');
        if (filaSeleccionada) {
        // Clona la fila seleccionada
            filaSeleccionada.classList.remove('fila-seleccionada');
            var dataId = filaSeleccionada.getAttribute('data-id');
            var columnas = filaSeleccionada.getElementsByTagName('td');
            var examen = columnas[1].textContent.trim(); 
            console.log(dataId)
            document.getElementById('ex_old').value =examen
            document.getElementById('id_est').value=dataId
            
        }
    });

    document.getElementById('Form_ec').addEventListener('submit', function(event) {
        event.preventDefault(); // Evita que el formulario se envíe de forma predeterminada
    
        // Obtén los datos del formulario
        var formData = new FormData(this);
    
        // Realiza la lógica que necesites con los datos del formulario
        fetch('/actualizar_datos_cita', {
            method: 'POST',
            body: formData,
        }) 
        .then(response => response.json())
        .then(data => {
            // Maneja la respuesta del servidor
            if (data.success) {
                // Mostrar notificación de éxito
                showToast("Éxito", "Cita actualizada exitosamente", "/templates/includes/toast/toast_success.html");
                
                // Cierra el modal y realiza cualquier otra acción necesaria
                var modal = bootstrap.Modal.getInstance(document.getElementById('modal_ec'));
                modal.hide();
    
                // Reemplaza el contenido de la fila seleccionada en la tabla
                actualizarFilaSeleccionada(data.data);
            } else {
                // Maneja los errores
                showToast("Error", "Error al editar la cita: " + (data.error || data.message), "/templates/includes/toast/toast_alert.html");
                console.error('Error al editar la cita:', data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast("Error", "Hubo un error al actualizar la cita", "/templates/includes/toast/toast_alert.html");
        });
    });
    
    function actualizarFilaSeleccionada(datos) {
        var filaSeleccionada = document.querySelector('.fila-seleccionada');
        if (filaSeleccionada) {
            // Limpia el contenido actual de la fila
            while (filaSeleccionada.firstChild) {
                filaSeleccionada.removeChild(filaSeleccionada.firstChild);
            }
    
            // Crea las nuevas celdas y agrega los datos
            for (var i = 0; i < datos.length; i++) {
                var nuevaCelda = document.createElement('td');
                var nuevoTexto = document.createTextNode(datos[i]);
                nuevaCelda.appendChild(nuevoTexto);
                filaSeleccionada.appendChild(nuevaCelda);
            }
        } else {
            console.error('No se encontró ninguna fila con la clase .fila-seleccionada');
        }
    }
    
    document.getElementById('b_editar_fecha').addEventListener('click', function(){
        // Ocultar el card de búsqueda y el card de citas
        const cardBuscar = document.getElementById('card_buscar');
        const cardCitas = document.getElementById('card_citas');
        
        if (cardBuscar) {
            cardBuscar.style.display = 'none';
        }
        if (cardCitas) {
            cardCitas.style.display = 'none';
        }
        
        AbrirCalendarioParaEditar('tabla-citas')
    })
    
    
})
