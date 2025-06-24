//Objeto con datos de la orden
let OrderData = {
    patientId: null,
    exams:[],
    medico_solicitante: null,
    obra_social:null,
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
        alert('Por favor, seleccione al menos un examen.');
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
        console.log("filaseleccionada:",filaSeleccionada.dataset.id)
        OrderData.patientId=filaSeleccionada.dataset.id
        var tds = filaSeleccionada.querySelectorAll('td');
        li_dni.innerText = "Paciente seleccionado: " + tds[0].innerText + ", " + tds[1].innerText;
        divPaciente.classList.add('bg-success'); // Agrega la clase de Bootstrap para fondo verde

        // Le quito la clase bg-danger si es que la tiene.
        var divPaciente = document.getElementById('pills-paciente-tab');
        divPaciente.classList.remove('bg-danger');
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
        // Clona la fila seleccionada
        filaSeleccionada.classList.remove('fila-seleccionada');
        var fullRowData = filaSeleccionada.innerHTML;
        var dataId = filaSeleccionada.getAttribute('data-id'); // Obtener el atributo data-id

        // Añade la fila clonada a la tabla de Estudios Seleccionados
        var tablaEstudiosSelec = document.getElementById(Tabla2Id);
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

        // Restaura el estilo del botón
        boton_sel.classList.remove('btn-success');
        boton_sel.classList.add('btn-secondary');
        boton_sel.disabled = true;

        // Ahora haremos el evento para la agenda
        var columnas = filaSeleccionada.querySelectorAll('td');
        var codigoEst = columnas[0].textContent.trim(); // Contenido de la primera columna
        var descEst = columnas[1].textContent.trim();
        var idExam=filaSeleccionada.getAttribute('data-id');
        console.log(idExam)    
        }

        const newEvent = {
            title: codigoEst + " - " + descEst,
            start: wish_date + 'T09:00:00', // Ajustar la hora según sea necesario
            end: wish_date + 'T10:00:00',   // Ajustar la duración según sea necesario
            editable: true, // Este evento será editable
            idExam:idExam
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
        OrderData.exams.push(examen);

        // Ahora creo una card
        fetch('/get_block_prestacion')
        .then(response => response.text())
        .then(data => {
            var container = document.getElementById('conteiner_blocks_prest');
            console.log("idprefix: ",examen)
            var idPrefix = examen.title.substring(0, 3);
            var uniqueIdMedicoSolicitante = `${idPrefix}_ms`;
            var uniqueIdObraSocial = `${idPrefix}_os`;
            var insertId=`id='${dataId}'`
            console.log("dataid:",dataId)
            var cardHtml = data
                .replace('<!-- IdEstudio -->', examen.title)
                .replace('id="cardId"', insertId)
                .replace('class="form-control medico_solicitante"', `class="form-control medico_solicitante"" id="${uniqueIdMedicoSolicitante}" name="${uniqueIdMedicoSolicitante}"`)
                .replace('class="form-control obra_social"', `class="form-control obra_social" id="${uniqueIdObraSocial}" name="${uniqueIdObraSocial}"`);
                
            container.insertAdjacentHTML('beforeend', cardHtml);

            // Añadir event listeners a los selects creados
            document.getElementById(uniqueIdMedicoSolicitante).addEventListener('change', function(event) {
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
            document.getElementById(uniqueIdObraSocial).addEventListener('change', function(event) {
                console.log('Cambio en obra social:', event.target.id);
                codigo=event.target.id.substring(0, 3)
                OrderData.exams.forEach(function(examen){
                    var idPrefix = examen.title.substring(0, 3)
                    if(idPrefix==codigo){
                        examen.obra_social=document.getElementById(event.target.id).value
                    }
                })
            });
            
            RellenarSelectByClass("medico_solicitante","Description","public.isrequestingphysician")
            RellenarSelectByClass("obra_social","Description","public.ispricelist")

        })
        .catch(error => {
            console.error('Error al cargar el archivo block_prestacion.html:', error);
        });

    }

    tbodyest.addEventListener('click', function (event) {
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
                }
            }

            // Eliminar de OrderData
            OrderData.exams = OrderData.exams.filter(examen => examen.examId !== data2delete);

            // Eliminar el evento del historial
            eventHistory = eventHistory.filter(event => event.id !== data2delete);

            // Eliminar de la tabla external-events
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

            document.getElementById(data2delete).remove();

            // Verificar si ya no hay ninguna fila en tbodySelec y retirar la clase bg-success
            if (tbodySelec.querySelectorAll('tr').length === 0) {
                var divExamen = document.getElementById('pills-examen-tab');
                divExamen.classList.remove('bg-success');
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
    });
}


function CrearCalendario() {
    var prof_ag = document.getElementById('prof_ag').value;

    if (prof_ag) {
        fetch('/get_events', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ prof_ag: prof_ag })
        })
        .then(response => response.json())
        .then(data => {
            //console.log('Received events and work hours:', data);
            document.getElementById('card-agenda').hidden = false;

            var calendarEl = document.getElementById('calendario');
            var businessHours = data.work_hours.map(wh => ({
                daysOfWeek: [wh.day],
                startTime: wh.start,
                endTime: wh.end
            }));

            //Aca verifico si en orderData ya existen otros eventos que se hayan puesto con anterioridad en esta misma orden (Yo entro a esta funcion cada vez que cambio el prof_ag, por lo que se pudo haber colocado en un cambio anterior)
            var filteredExams = OrderData.exams.filter(exam => exam.profesional === prof_ag);

            var additionalEvents = filteredExams.map(exam => ({
                id: exam.examenId,
                title: exam.examenId,
                start: exam.init,
                end: exam.finish,
                editable: true
            }));

            console.log("eventos colocados recien: ",additionalEvents);
            var allEvents = data.events.concat(additionalEvents);

            calendar = new FullCalendar.Calendar(calendarEl, {
                timeZone: 'local',
                droppable: true,
                eventReceive: function(info) {
                    var eventObj = info.event;
                    var idExam = info.draggedEl.getAttribute('idExam');
                    console.log("idexam ", idExam);
                
                    var examId = idExam;
                    var profesional = document.getElementById('prof_ag').value;
                
                    var init = eventObj.start;
                    var finish = eventObj.end || new Date(init.getTime() + 60 * 60 * 1000);
                
                    var examenExistente = OrderData.exams.find(examen => examen.examId == examId);
                
                    if (examenExistente) {
                        examenExistente.profesional = profesional;
                        examenExistente.init = init;
                        examenExistente.finish = finish;
                    } else {
                        OrderData.exams.push({
                            examId: examId,
                            profesional: profesional,
                            init: init,
                            finish: finish
                        });
                    }
                
                    // Asignar un ID único al evento
                    var newEventId = idExam;
                    eventObj.setProp('id', newEventId); // Usa el método setProp para asignar el ID
                
                    // Guardar el evento seleccionado globalmente
                    selectedEvent = {
                        id: newEventId,
                        title: eventObj.title,
                        start: init,
                        end: finish,
                        editable: true
                    };
                
                    // Añadir el evento al historial
                    eventHistory.push(selectedEvent);
                
                    // Eliminar el evento de external-events
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
                slotMinTime: '00:00:00',
                slotMaxTime: '24:00:00',
                businessHours: businessHours,
                selectConstraint: businessHours,
                eventConstraint: businessHours,
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
        })
        .catch(error => {
            console.error('Error:', error);
        });
    } else {
        alert("Por favor, seleccione un profesional.");
    }
}
function ReconfigurarCalendario(calendar) {
    var prof_ag = document.getElementById('prof_ag').value;

    if (prof_ag) {
        fetch('/get_events', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ prof_ag: prof_ag })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Received events and work hours:', data);

            var businessHours = data.work_hours.map(wh => ({
                daysOfWeek: [wh.day],
                startTime: wh.start,
                endTime: wh.end
            }));

            // Verificar si en OrderData ya existen otros eventos que se hayan puesto con anterioridad en esta misma orden
            console.log("OrderData: ", OrderData.exams);
            var filteredExams = OrderData.exams.filter(exam => exam.profesional === prof_ag);
            var additionalEvents = filteredExams.map(exam => ({
                examId: exam.examId,
                title: exam.title,
                start: exam.init,
                end: exam.finish,
                editable: true
            }));

            console.log("eventos colocados recien: ", additionalEvents);
            var allEvents = data.events.concat(additionalEvents);

            // Reconfigurar el calendario con nuevos eventos y horas laborales
            calendar.setOption('businessHours', businessHours);
            calendar.removeAllEvents(); // Eliminar todos los eventos actuales
            allEvents.forEach(event => {
                calendar.addEvent(event); // Añadir los nuevos eventos
            });

            calendar.render(); // Renderizar el calendario con los nuevos datos
        })
        .catch(error => {
            console.error('Error:', error);
        });
    } else {
        alert("Por favor, seleccione un profesional.");
    }
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
    fetch('/insertar_citas', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(OrderData),
    })
    .then(response => response.json())
    .then(data => {
        // Manejar la respuesta del servidor
        if (data.success) {
            showToast("Éxito", "Las citas se han insertado correctamente.", "/static/templates/includes/toast/toast_success.html");
            
            // Limpiar OrderData
            OrderData.patientId = null;
            OrderData.exams = [];
            OrderData.medico_solicitante = null;
            OrderData.obra_social = null;

            // Vaciar la tabla de estudios seleccionados
            var tablaEstudiosSelec = document.getElementById('tabla-estudios-selec');
            var tbodyEstudiosSelec = tablaEstudiosSelec.querySelector('tbody');
            while (tbodyEstudiosSelec.firstChild) {
                tbodyEstudiosSelec.removeChild(tbodyEstudiosSelec.firstChild);
            }

            // Rellenar nuevamente tabla-estudios
            RellenarTabla('tabla-estudios', `/get_exams_adm`);

            // Destruir el calendario
            if (calendar) {
                calendar.destroy();
                calendar = null;
            }

            // Limpiar external-events
            var externalEventsContainer = document.getElementById('external-events');
            while (externalEventsContainer.firstChild) {
                externalEventsContainer.removeChild(externalEventsContainer.firstChild);
            }

            // Limpiar eventHistory
            eventHistory = [];

            // Remover clases de éxito en las pestañas
            var pillPaciente = document.getElementById('pills-paciente-tab');
            var pillExamen = document.getElementById('pills-examen-tab');
            var pillAgenda = document.getElementById('pills-agenda-tab');

            pillPaciente.classList.remove('bg-success', 'bg-danger');
            pillExamen.classList.remove('bg-success', 'bg-danger');
            pillAgenda.classList.remove('bg-success', 'bg-danger');

            // Activar la pestaña de paciente
            var pillPacienteButton = document.querySelector('[data-bs-target="#pills-paciente"]');
            var tab = new bootstrap.Tab(pillPacienteButton);
            tab.show();

            // Remover la clase fila-seleccionada de cualquier fila en la tabla-paciente
            var tablaPaciente = document.getElementById('tabla-paciente');
            var filasSeleccionadas = tablaPaciente.querySelectorAll('.fila-seleccionada');
            filasSeleccionadas.forEach(fila => {
                fila.classList.remove('fila-seleccionada');
            });

        } else {
            showToast("Error", "Hubo un problema al insertar las citas: " + data.message, "/static/templates/includes/toast/toast_alert.html");
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast("Error", "Hubo un error al insertar las citas.", "/static/templates/includes/toast/toast_alert.html");
    });
}

function showToast(title, message, toastFile) {
    fetch(toastFile)
    .then(response => response.text())
    .then(html => {
        // Insertar el HTML del toast en el contenedor
        var toastContainer = document.getElementById('toastContainer');
        toastContainer.innerHTML = html;

        // Actualizar el contenido del toast
        var toastTitle = document.getElementById('toastTitle');
        var toastBody = document.getElementById('toastBody');
        
        toastTitle.innerHTML = title;
        toastBody.innerHTML = message;

        var toastEl = document.getElementById('toastMessage');
        var toast = new bootstrap.Toast(toastEl);
        toast.show();
    })
    .catch(error => {
        console.error('Error al cargar el archivo de toast:', error);
    });
}

function QuitarEvento() {
    if (eventHistory.length > 0) {
        // Obtener el último evento del historial
        var lastEvent = eventHistory.pop();

        // Eliminar el evento del calendario
        var eventToRemove = calendar.getEventById(lastEvent.id);
        console.log("lastevent.id: ", lastEvent);
        if (eventToRemove) {
            console.log("removi el evento");
            eventToRemove.remove();
        }

        // Vuelve a crear el evento en el contenedor external-events
        var externalEventsContainer = document.getElementById('external-events');
        var newEventDiv = document.createElement('div');
        newEventDiv.className = 'fc-event fc-h-event fc-daygrid-event fc-daygrid-block-event';
        newEventDiv.innerHTML = `<div class='fc-event-main'>${lastEvent.title}</div>`;
        newEventDiv.dataset.event = JSON.stringify(lastEvent);

        externalEventsContainer.appendChild(newEventDiv);

        // Elimina el evento de OrderData.exams
        var examIndex = OrderData.exams.findIndex(exam => exam.examId == lastEvent.id);
        if (examIndex > -1) {
            OrderData.exams.splice(examIndex, 1);
        }

        console.log('Evento eliminado y recreado en external-events:', lastEvent.id);
        selectedEvent = null; // Resetear el evento seleccionado

        // Le quito la clase bg-danger si es que la tiene.
        var divAgenda = document.getElementById('pills-agenda-tab');
        divAgenda.classList.remove('bg-success');
    } else {
        // Mostrar el toast en lugar del alert
        showToast('Ha ocurrido un problema', 'No hay ningún evento en el historial para eliminar.', "/static/templates/includes/toast/toast_alert.html");
    }
}




document.addEventListener("DOMContentLoaded", function() {

    //Pestaña de paciente config
    RellenarTabla('tabla-paciente',`/get_patients_min`)
    ConfigFiltrarText('l_name', 'tabla-paciente',0)
    ConfigFiltrarText('l_surname', 'tabla-paciente',1)
    ConfigFiltrarSelect('l_sex', 'tabla-pacientes',2)
    ConfigFiltrarFecha('fecha_nac', 'tabla-pacientes',3)
    ConfigFiltrarText('documento', 'tabla-pacientes',4)

    //Aca selecciono al paciente
    var boton=document.getElementById("b_sel_pac_para_adm")
    boton.addEventListener("click",function(){SeleccionarPaciente('tabla-paciente')})

    document.getElementById("tabla-paciente").addEventListener("dblclick",function(){SeleccionarPaciente('tabla-paciente')})
    //-------------------------------

    
    // Examen
    RellenarSelect("tipo_examen","Description","public.IsModality")
    RellenarSelect("parte_cuerpo","Description","public.IsAnatomicalPart")
    RellenarTabla('tabla-estudios',`/get_exams_adm`)
    ConfigTablaEstudios('tabla-estudios','seleccionar-estudio','tabla-estudios-selec')
    ConfigTablaSeleccionados('tabla-estudios-selec','quitar-estudio','tabla-estudios','tabla-estudios-agenda')

    ConfigFiltrarSelect('tipo_examen', 'tabla-estudios',2)
    ConfigFiltrarSelect('parte_cuerpo', 'tabla-estudios',3)
    

    
    ConfigurarTabla('tabla-paciente','botones_sp')

    // Prestacion
    RellenarSelectByClass("general_ms","Description","public.isrequestingphysician")
    RellenarSelectByClass("general_os","Description","public.ispricelist")
   

    document.getElementById('cb_same_info').addEventListener('change', function() {
        var allin1Div = document.getElementById('allin1');
        // allin1Div.hidden = !this.checked;
    });


    document.getElementById('general_ms').addEventListener('change', function(event) {
        console.log('Cambio en medico solicitante:', event.target.id);
        codigo=event.target.id.substring(0, 3)
        OrderData.exams.forEach(function(examen){
            examen.medico_solicitante=document.getElementById(event.target.id).value
        })
    });
    document.getElementById('general_os').addEventListener('change', function(event) {
        console.log('Cambio en obra social:', event.target.id);
        codigo=event.target.id.substring(0, 3)
        OrderData.exams.forEach(function(examen){
            examen.obra_social=document.getElementById(event.target.id).value
        })
    });


    const cbSameInfo = document.getElementById('cb_same_info');
    const cbIcon = document.getElementById('cb_icon');
    const collapseTarget = document.getElementById('allin1');
    var blPrestElements = document.querySelectorAll('.bl_prest');

    cbIcon.addEventListener('click', function() {
    cbSameInfo.checked = !cbSameInfo.checked;
    cbIcon.classList.toggle('fa-toggle-on', cbSameInfo.checked);
    cbIcon.classList.toggle('fa-toggle-off', !cbSameInfo.checked);

    if (cbSameInfo.checked) {
        $(collapseTarget).collapse('show');
        blPrestElements = document.querySelectorAll('.bl_prest');
        blPrestElements.forEach(function(element) {
            element.classList.add('hidden');
            element.classList.remove('visible');
        });
    } else {
        $(collapseTarget).collapse('hide');
        blPrestElements = document.querySelectorAll('.bl_prest');
        blPrestElements.forEach(function(element) {
            element.classList.add('visible');
            element.classList.remove('hidden');
        });
    }
    });

    // Ensure the icon matches the initial state of the checkbox
    cbIcon.classList.toggle('fa-toggle-on', cbSameInfo.checked);
    cbIcon.classList.toggle('fa-toggle-off', !cbSameInfo.checked);

    //Agenda
    
    RellenarSelectCondicionalId('prof_ag', 'username', 'public.tbuser','88e340f5-6fa5-4df1-aef6-c911625a4427','idrole')


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
            if (calendar) {
                ReconfigurarCalendario(calendar)
            }else{
                CrearCalendario()   
            }
    });

    //Con este codigo volvemos para atrás los cambios realizados en el calendario.
    document.getElementById('b_undo').addEventListener('click', function() {
        QuitarEvento()
    });
    //--------------------
    
});
