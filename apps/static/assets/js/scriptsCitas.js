
// Funcion de examenes 
function filtrar_estudios(){
    // Obtiene el valor seleccionado en el select
    
    var filtro_modalidad = document.getElementById("tipo_examen").value;
    var filtro_partes = document.getElementById("parte_cuerpo").value;
    
    // Obtiene todas las filas de la tabla
    var filas = document.getElementsByClassName("patient-row");
 
    // Itera a través de las filas y las muestra u oculta según la selección
    for (var i = 0; i < filas.length; i++) {
       var fila = filas[i];
       var modalidad = fila.getElementsByTagName("td")[2].textContent; // Suponiendo que la modalidad está en la tercera columna
       var parte = fila.getElementsByTagName("td")[3].textContent; 
       // Compara la modalidad con la selección
       if ((filtro_modalidad === "Todas" || modalidad === filtro_modalidad) && (filtro_partes === "Todas" || parte === filtro_partes)) {
          fila.style.display = "table-row"; // Muestra la fila
       } else {
          fila.style.display = "none"; // Oculta la fila
       }
    }
 
}
// Funcion de examenes 
function filtrar_por_partes(){
    // Obtiene el valor seleccionado en el select
    
    var seleccion = document.getElementById("parte_cuerpo").value;
    
    // Obtiene todas las filas de la tabla
    var filas = document.getElementsByClassName("patient-row");
 
    // Itera a través de las filas y las muestra u oculta según la selección
    for (var i = 0; i < filas.length; i++) {
       var fila = filas[i];
       var modalidad = fila.getElementsByTagName("td")[3].textContent; // Suponiendo que la modalidad está en la tercera columna
 
       // Compara la modalidad con la selección
       if (seleccion === "Todas" || modalidad === seleccion) {

          fila.style.display = "table-row"; // Muestra la fila
       } else {
          fila.style.display = "none"; // Oculta la fila
       }
       console.log(fila.style.display)
    }
 
}

document.addEventListener("DOMContentLoaded", function() {

    var tablaPacientes = document.getElementById('tabla-paciente');
    var tbody = tablaPacientes.querySelector('tbody');
    
    var idPaciente = null;
    var dniPaciente = null;

    var boton_sel_pac_para_cita = document.getElementById('b_sel_pac_para_cita');
    boton_sel_pac_para_cita.addEventListener('click', precargarPaciente);

    function precargarPaciente() {
        const dniItem = document.getElementById('dni-item');
    
        if (idPaciente) {
            fetch(`/set_patient?id=${idPaciente}&dni=${dniPaciente}`)
                .then(response => response.json())
                .then(data => {
                    
    
                    // Actualiza el contenido del DNI
                    var dniValue = document.getElementById('dni-value');
                    if (dniValue) {
                        dniValue.textContent = 'Paciente seleccionado: '+data.paciente_dni; // Ajusta según la propiedad correcta de tu objeto Cita
                    }
    
                    // Muestra el elemento li
                    console.log(data.paciente_dni);
                    dniValue.classList.remove('hidden');

                    var pill = document.getElementById('pills-paciente-tab');
                    pill.classList.add('success_back');
                })
                .catch(error => {
                    console.error('Error:', error);
                });
        } else {
            // Oculta el elemento li si no tienes el ID del paciente
            dniItem.classList.add('hidden');
        }
    }
    

    tbody.addEventListener('click', function (event) {
        var filas = tbody.querySelectorAll('tr');
        for (var i = 0; i < filas.length; i++) {
            filas[i].classList.remove('fila-seleccionada');
        }
        

        var fila = event.target.closest('tr');
        if (fila) {
            fila.classList.add('fila-seleccionada');
            idPaciente = fila.cells[0].textContent;
            dniPaciente = fila.cells[4].textContent;
            var boton_sel_pac_para_cita = document.getElementById('b_sel_pac_para_cita');
            boton_sel_pac_para_cita.setAttribute('patient-id', idPaciente);
            var nombre = fila.cells[1].textContent;
            var sexo = fila.cells[2].textContent;
            var fechaNacimiento = fila.cells[3].textContent;

            var botones = document.getElementsByClassName('botones');
            for (var i = 0; i < botones.length; i++) {
                var boton = botones[i];
                boton.disabled = false;
                boton.classList.remove('btn-secondary');
                boton.classList.add('btn-success');
            }
        } else {
            var botones = document.getElementsByClassName('botones');
            for (var i = 0; i < botones.length; i++) {
                var boton = botones[i];
                boton.disabled = true;
                boton.classList.remove('btn-primary');
                boton.classList.add('btn-secondary');
            }
        }
    });


    var closeButton = document.getElementById('btn-close');
    if (closeButton) {
        closeButton.addEventListener('click', function () {
            var alertSuccess = document.getElementById('notif-carga');
            if (alertSuccess) {
                alertSuccess.remove();
            }
        });
    }


    /* -----------------------------------------------------------
    -------------------TABLA DE ESTUDIOS--------------------------
    ------------------------------------------------------------*/

    var tablaEstudios = document.getElementById('tabla-estudios');
    var tbodyest = tablaEstudios.querySelector('tbody');
    
    var boton_sel = document.getElementById('seleccionar-estudio');
    boton_sel.addEventListener('click', AgregarEstudio);

    function AgregarEstudio() {
        var filaSeleccionada = tbodyest.querySelector('.fila-seleccionada');
        if (filaSeleccionada) {
        // Clona la fila seleccionada
        filaSeleccionada.classList.remove('fila-seleccionada');
        var filaClonada = filaSeleccionada.cloneNode(true);

        // Añade la fila clonada a la tabla de Estudios Seleccionados
        var tablaEstudiosSelec = document.getElementById('tabla-estudios-selec');
        var tbodyEstudiosSelec = tablaEstudiosSelec.querySelector('tbody');
        tbodyEstudiosSelec.appendChild(filaClonada);


        //en esta seccion agrego el evento para la agenda
        var columnas = filaSeleccionada.getElementsByTagName('td');
        var contenidoColumna1 = columnas[0].textContent.trim(); // Contenido de la primera columna
        var contenidoColumna2 = columnas[1].textContent.trim();  

        
        var tablaEstudiosAgenda = document.getElementById('tabla-estudios-agenda');
        var tbodyEstudiosAgenda = tablaEstudiosAgenda.querySelector('tbody');
        var nuevaFila = document.createElement('tr');
        var nuevaColumna1 = document.createElement('td');
        var nuevaColumna2 = document.createElement('td');

        nuevaColumna1.textContent = contenidoColumna1;
        nuevaColumna2.textContent = contenidoColumna2;
        
        nuevaFila.appendChild(nuevaColumna1);
        nuevaFila.appendChild(nuevaColumna2);

        tbodyEstudiosAgenda.appendChild(nuevaFila);

        
        // Quita la clase 'fila-seleccionada' de la fila original
        filaSeleccionada.remove();
        
        // Restaura el estilo del botón
        boton_sel.classList.remove('btn-success');
        boton_sel.classList.add('btn-secondary');
        boton_sel.disabled = true;
        }
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


    /* -----------------------------------------------------------
    -------------TABLA DE ESTUDIOS SELECCIONADOS-----------------
    ------------------------------------------------------------*/

    var tablaSelec = document.getElementById('tabla-estudios-selec');
    var tbodySelec = tablaSelec.querySelector('tbody');
    
    var boton_quitar = document.getElementById('quitar-estudio');
    boton_quitar.addEventListener('click', QuitarEstudio);

    function QuitarEstudio() {
        var filaSeleccionadaSelec = tbodySelec.querySelector('.fila-seleccionada');
        
        if (filaSeleccionadaSelec) {
            // Obtén la información de las columnas 1 y 2 de la fila seleccionada
            var columnas = filaSeleccionadaSelec.getElementsByTagName('td');
            var contenidoColumna1 = columnas[0].textContent.trim();
            
            
            var tablaEstudiosAgenda = document.getElementById('tabla-estudios-agenda');
            var tbodyEstudiosAgenda = tablaEstudiosAgenda.querySelector('tbody');
            var filasAgenda = tbodyEstudiosAgenda.querySelectorAll('tr');
    
            for (var i = 0; i < filasAgenda.length; i++) {
                var filaAgenda = filasAgenda[i];
                var columnasAgenda = filaAgenda.getElementsByTagName('td');
                var contenidoColumna1Agenda = columnasAgenda[0].textContent.trim();
    
                // Compara el contenido de las columnas de la fila seleccionada y la fila de la tabla-estudios-agenda
                if (contenidoColumna1 === contenidoColumna1Agenda) {
                    // Si coinciden, elimina la fila de la tabla-estudios-agenda
                    filaAgenda.remove();
                    break;  // No es necesario seguir buscando
                }
            }
    
            // Ahora puedes continuar con el resto de la lógica para quitar el estudio seleccionado
            filaSeleccionadaSelec.classList.remove('fila-seleccionada');
            var filaClonada = filaSeleccionadaSelec.cloneNode(true);
    
            var tablaEstudios = document.getElementById('tabla-estudios');
            var tbodyEstudios = tablaEstudios.querySelector('tbody');
            tbodyEstudios.appendChild(filaClonada);
    
            // Quita la clase 'fila-seleccionada' de la fila original
            filaSeleccionadaSelec.remove();
            
            // Restaura el estilo del botón
            boton_quitar.classList.remove('btn-success');
            boton_quitar.classList.add('btn-secondary');
            boton_quitar.disabled = true;
        }
    }

    tbodySelec.addEventListener('click', function (event) {
        var filas = tbodySelec.querySelectorAll('tr');
        for (var i = 0; i < filas.length; i++) {
            filas[i].classList.remove('fila-seleccionada');
        }

        var fila = event.target.closest('tr');
        if (fila) {
            fila.classList.add('fila-seleccionada');

            boton_quitar.classList.remove('btn-secondary');
            boton_quitar.classList.add('btn-success');
            boton_quitar.disabled = false;
            
        } else {
            boton_quitar.classList.remove('btn-success');
            boton_quitar.classList.add('btn-secondary');
            boton_quitar.disabled = true;
        }
    });

    var Calendar = FullCalendar.Calendar;
    var Draggable = FullCalendar.Draggable;
    var calendarEl = document.getElementById('calendario');
    var containerEl = document.getElementById('external-events');

    var calendar = new FullCalendar.Calendar(calendarEl, {
        headerToolbar: {
            left: 'prev,next',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay' // user can switch between the two
          },
      initialView: 'timeGridWeek', // Asegúrate de usar 'timeGridWeek' para la vista semanal con horarios detallados
      editable: true,
      droppable: false, // Evita que los eventos se puedan soltar en cualquier parte del calendario
        businessHours: {
            // Define tu horario comercial aquí
            daysOfWeek: [1, 2, 3, 4], // De lunes a viernes
            startTime: '08:00', // Hora de inicio (por ejemplo, 8:00 AM)
            endTime: '18:00'    // Hora de finalización (por ejemplo, 5:00 PM)
        },

    //   droppable: true,
      drop: function(info) {
        
        info.draggedEl.parentNode.removeChild(info.draggedEl);
        var filaSeleccionada = document.querySelector('#tabla-estudios-agenda .fila-seleccionada');
        if(filaSeleccionada){
            filaSeleccionada.classList.remove('fila-seleccionada');
            filaSeleccionada.classList.add('evento-creado')
        }
      },
      
      
    });

    calendar.render();

    new Draggable(containerEl, {
        itemSelector: '.fc-event',
        eventData: function(eventEl) {
          return {
            title: eventEl.innerText,
            constraint: 'businessHours'
          };
        },
        
      });


      /* -----------------------------------------------------------
    -------------SELECCIONAR AGENNDA-----------------
    ------------------------------------------------------------*/
    
    var boton_buscar_agenda = document.getElementById('boton-buscar-agenda');
    boton_buscar_agenda.addEventListener('click', BuscarAgenda);

    function BuscarAgenda() {

        var cardagenda=document.getElementById('card-agenda')
        cardagenda.removeAttribute('hidden');

        calendar.removeAllEvents();

        var fecha_central=document.getElementById('wish_date').value
        var machine=document.getElementById('machine').value
        console.log(fecha_central, machine)
        var fecha = new Date(fecha_central);
        calendar.gotoDate(fecha);

        var filaSeleccionada = document.querySelector('#tabla-estudios-agenda .fila-seleccionada');

        if (filaSeleccionada) {
            var contenidoColumna1 = filaSeleccionada.querySelector('td:first-child').textContent.trim();
            var contenidoColumna2 = filaSeleccionada.querySelector('td:nth-child(2)').textContent.trim();
            var divEvento = document.createElement('div');
            divEvento.className = 'fc-event fc-h-event fc-daygrid-event fc-daygrid-block-event';
            
            var divEventoMain = document.createElement('div');
            divEventoMain.className = 'fc-event-main';
            divEventoMain.textContent = contenidoColumna1 + ' - ' + contenidoColumna2;
            
            // Agrega el contenido al elemento div
            divEvento.appendChild(divEventoMain);

            // Agrega el evento al área de eventos externos
            var eventosExternos = document.getElementById('external-events');
            eventosExternos.appendChild(divEvento);
        }

        // calendar.render();
        fetch(`/obtener_agenda?machine=${machine}`)
                .then(response => response.json())
                .then(data => {
                    data.forEach(evento => {
                        var nuevoEvento = {
                            title: evento[1],
                            start: evento[2],
                            end: evento[3],
                            editable: false,
                            color: '#333333'
                        };
                        // Agrega el evento al calendario
                        calendar.addEvent(nuevoEvento);
                    });
                })
                .catch(error => {
                    console.error('Error:', error);
                });
    }
     /* -----------------------------------------------------------
    -------------CREAR EVENTOS PARA AGREGAR A LA AGENDA----------------
    ------------------------------------------------------------*/
    
    var tablaestudiosAgenda = document.getElementById('tabla-estudios-agenda');
    var tbodyAgenda = tablaestudiosAgenda.querySelector('tbody');
    
    tbodyAgenda.addEventListener('click', function (event) {
        var filas = tbodyAgenda.querySelectorAll('tr');
        for (var i = 0; i < filas.length; i++) {
            filas[i].classList.remove('fila-seleccionada');
        }

        var fila = event.target.closest('tr');
        if ((fila)&&(!fila.classList.contains('evento-creado'))){
            fila.classList.add('fila-seleccionada');
            var contenidoColumna1 = fila.querySelector('td:first-child').textContent.trim().substring(0, 3).toLowerCase();;
            var codigos = document.querySelectorAll('#machine option');
            // Recorrer los códigos y ocultar/mostrar según coincidan
            codigos.forEach(function (codigo) {
                var codigoValor = codigo.value.toLowerCase();;
                if (codigoValor.startsWith(contenidoColumna1)) {
                    // Coincide, mostrar la opción
                    codigo.style.display = 'block';
                } else {
                    // No coincide, ocultar la opción
                    codigo.style.display = 'none';
            }
        });
 
        }  
    });
});
