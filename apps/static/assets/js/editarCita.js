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
        
        // Extraer el nombre del paciente de la segunda columna
        var OrderId = filaSeleccionada.getAttribute('data-id');
        var nombrePaciente = filaSeleccionada.querySelectorAll('td')[0].textContent.trim();
        var fecha = filaSeleccionada.querySelectorAll('td')[1].textContent.trim();
        var mref = filaSeleccionada.querySelectorAll('td')[2].textContent.trim();
        var examen = filaSeleccionada.querySelectorAll('td')[3].textContent.trim();
        
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
            
            // Configuro la función para el botón de confirmar
            var evento = null; // Asegurarse de que evento esté inicialmente vacío
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
                        // Manejar la respuesta del servidor
                        if (data.success) {
                            showToast("Éxito", "La cita se ha editado correctamente.", "/static/templates/includes/toast/toast_success.html");
                            
                            // Mostrar card_citas y card_buscar
                            $('#card_citas').show();
                            $('#card_buscar').show();
                            
                            // Eliminar el contenido de id="data"
                            $('#data').remove();

                            // Actualizar la fecha de inicio del turno en la tabla
                            var tablaCitas = document.getElementById('tabla-citas');
                            var filaSeleccionadaCita = tablaCitas.querySelector('.fila-seleccionada');
                            if (filaSeleccionadaCita) {
                                filaSeleccionadaCita.querySelectorAll('td')[1].textContent = evento.start.toISOString().split('T')[0] + " " + evento.start.toTimeString().split(' ')[0];
                            }

                        } else {
                            showToast("Error", "Hubo un problema al insertar las citas: " + data.message, "/static/templates/includes/toast/toast_alert.html");
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        showToast("Error", "Hubo un error al insertar las citas.", "/static/templates/includes/toast/toast_alert.html");
                    });
                }
            });

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

                businessHours = data.work_hours.map(wh => ({
                    daysOfWeek: [wh.day],
                    startTime: wh.start,
                    endTime: wh.end
                }));

                // Iterar sobre data.events y modificar eventos con guid = OrderId
                var events = data.events.map(event => {
                    if (event.guid === OrderId) {
                        event.backgroundColor = 'green';
                        event.editable = true;
                        evento = event; // Asigna el evento aquí
                    }
                    // Asegúrate de que cada evento tenga un ID
                    event.id = event.guid; // Si no tiene un ID, asígale el guid como ID
                    return event;
                });

                window.calendar = new FullCalendar.Calendar(calendarEl, {
                    timeZone: 'local', // Usa la zona horaria local del navegador
                    droppable: false,
                    eventChange: function(info) {
                        evento = info.event;
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

                window.calendar.render();

                // Inicializar evento después de renderizar el calendario
                evento = window.calendar.getEventById(OrderId);
                console.log('Evento obtenido:', evento);  // Verificar que se haya obtenido el evento
            })
            .catch(error => {
                console.error('Error:', error);
            });

            document.getElementById('wish_date').addEventListener('change', function() {
                // Tomar el evento editable y moverlo a la nueva fecha seleccionada
                var nuevaFecha = this.value;
                
                if (evento) {
                    // Convertir nuevaFecha a un objeto Date
                    var nuevaFechaDate = new Date(nuevaFecha + 'T00:00:00'); // Agregar la hora para evitar problemas de zona horaria
                    // Encontrar el primer bloque de tiempo disponible en la nueva fecha
                    var startTime = businessHours.find(bh => bh.daysOfWeek.includes(nuevaFechaDate.getDay())).startTime;
                    var nuevaFechaConHora = new Date(nuevaFechaDate.setHours(parseInt(startTime.split(':')[0]), parseInt(startTime.split(':')[1])));
                    
                    // Ajustar el evento con la nueva fecha y hora
                    var duracion = evento.end.getTime() - evento.start.getTime();
                    var nuevaFechaFin = new Date(nuevaFechaConHora.getTime() + duracion);
                    
                    // Actualizar el evento con la nueva fecha
                    evento.setStart(nuevaFechaConHora); // Usar setStart para actualizar la fecha de inicio
                    evento.setEnd(nuevaFechaFin); // Usar setEnd para actualizar la fecha de fin

                    // Mover el calendario a la nueva fecha
                    window.calendar.gotoDate(nuevaFechaConHora);
                }
            });

            document.getElementById('volver').addEventListener('click',function(){
                // Mostrar card_citas y card_buscar
                $('#card_citas').show();
                $('#card_buscar').show();
                
                // Eliminar el contenido de id="data"
                $('#data').remove();
            })

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





document.addEventListener("DOMContentLoaded", function() {
 
    RellenarTabla('tabla-citas', '/get_citas')
    ConfigurarTabla('tabla-citas','botones_ec')
    RellenarSelect('medico_solicitante', 'description', 'public.isrequestingphysician')
    RellenarSelectCondicionalId('medico_referente','username','public.tbuser','88e340f5-6fa5-4df1-aef6-c911625a4427','idrole')

    document.getElementById("nombre_pat").addEventListener("change",function(){
        FiltrarText('nombre_pat', 'tabla-citas',0)
    })
    document.getElementById("medico_referente").addEventListener("change",function(){
        FiltrarSelect('medico_referente', 'tabla-citas',2)
    })
    document.getElementById("medico_solicitante").addEventListener("change",function(){
        FiltrarSelect('medico_solicitante', 'tabla-citas',4)
    })

    SetDeleteButton('eliminar_cita','tabla-citas','/eliminar_cita')


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
            var med_sol = celdas[4].textContent
            var fecha = celdas[1].textContent
            document.getElementById('ex_old').value=examen
            document.getElementById('t_mod_ec').textContent=paciente
            document.getElementById('nombre_modal').value=paciente
            document.getElementById('id_ec').value=dataId
            document.getElementById('fecha').value=fecha
        }
        RellenarSelect('s_msol', 'description', 'public.isrequestingphysician', med_sol);
        RellenarSelectCondicionalId('s_mref', 'username', 'public.tbuser', '88e340f5-6fa5-4df1-aef6-c911625a4427', 'idrole', med_ref);
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
        fetch('/actualizar_cita', {
            method: 'POST',
            body: formData,
        })
        .then(response => response.json())
        .then(data => {
            // Maneja la respuesta del servidor
            if (data.success) {
                // Cierra el modal y realiza cualquier otra acción necesaria
                var modal = bootstrap.Modal.getInstance(document.getElementById('modal_ec'));
                modal.hide();
    
                // Reemplaza el contenido de la fila seleccionada en la tabla
                actualizarFilaSeleccionada(data.data);
            } else {
                // Maneja los errores
                console.error('Error al editar la cita:', data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
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
        console.log("aca estoy pa")
        AbrirCalendarioParaEditar('tabla-citas')
    })
    
    
})