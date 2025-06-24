

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
        fetch('/admisionar_cita', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            
            body: JSON.stringify({ dataId: dataId })
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


function RellenarTabla(TablaId, route) {
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    fetch(route)
        .then(response => response.json())
        .then(data => {
            tbody_.innerHTML = '';
            // Iterar sobre los datos y agregar filas a la tabla
            data.forEach(function (item) {
                var row = document.createElement('tr');
                row.dataset.id = item[0];

                // Iterar sobre los elementos de item (omitir el primer elemento) y agregar un <td> por cada uno
                for (var i = 1; i < item.length; i++) {
                    var cell = document.createElement('td');
                    if ((item[i]===0)||(item[i]===1)){             
                        const checkbox = document.createElement('input');
                        checkbox.type = 'checkbox';
                        checkbox.classList.add('form-check-input')
                        
                        checkbox.checked = item[i]
                        checkbox.style.opacity = 2;
                        checkbox.disabled = true;
                        
                        cell.appendChild(checkbox);
                    
                    } else {
                        // Para otras columnas, simplemente agrega el texto
                        cell.textContent = item[i];
                    }

                    row.appendChild(cell);
                }

                tbody_.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error:', error);
        });
}


function RellenarSelect(SelectId, dNeeded, TableId, selectedValue = null) {
    fetch('/rellenar_select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ dNeeded: dNeeded, TableId: TableId }),
    })
    .then(response => response.json())
    .then(data => {
        var selectElement = document.getElementById(SelectId);

        // Limpiar cualquier opción existente en el <select>
        selectElement.innerHTML = '';

        // Agregar la opción "Todas" al principio
        var todasOption = document.createElement('option');
        todasOption.value = 'Todas';
        todasOption.text = 'Todas';
        selectElement.appendChild(todasOption);

        // Llenar el <select> con las opciones de los datos
        for (var i = 0; i < data.data.length; i++) {
            var option = document.createElement('option');
            option.value = data.data[i][0];
            option.text = data.data[i][1];
            selectElement.appendChild(option);
        }

        // Seleccionar la opción con el texto específico si está presente
        if (selectedValue) {
            for (var i = 0; i < selectElement.options.length; i++) {
                if (selectElement.options[i].text === selectedValue) {
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


document.addEventListener("DOMContentLoaded", function() {
 
    RellenarTabla('tabla-citas', '/get_citas_for_today')
    ConfigurarTabla('tabla-citas','botones_ec')
    RellenarSelect('medico_solicitante', 'description', 'public.isrequestingphysician')
    RellenarSelectCondicionalId('medico_referente','username','public.tbuser','88e340f5-6fa5-4df1-aef6-c911625a4427','idrole')
    SetDeleteButton('eliminar_cita','tabla-citas','/eliminar_cita')

    // Configuración de filtros
    document.getElementById("nombre_pat").addEventListener("change",function(){
        FiltrarText('nombre_pat', 'tabla-citas',0)
    })
    document.getElementById("medico_referente").addEventListener("change",function(){
        FiltrarSelect('medico_referente', 'tabla-citas',2)
    })
    document.getElementById("medico_solicitante").addEventListener("change",function(){
        FiltrarSelect('medico_solicitante', 'tabla-citas',4)
    })
    //---------------------------

    document.getElementById('b_editar_fecha').addEventListener('click', function(){

        AbrirCalendarioParaEditar('tabla-citas')
    })
    
    // document.getElementById('b_admisionar_cita').addEventListener('click', function(){
    //     AdmisionarCita('tabla-citas')
    // })

    document.getElementById('b_admisionar_cita').addEventListener('click', function(){
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
            document.getElementById('idevent').value=dataId
        }
        RellenarTabla('tabla-equipo-modal', '/get_equipo_modal')
        ConfigurarTabla('tabla-equipo-modal','botones_adm_cita')
        // Mostrar el modal

        document.getElementById('tabla-equipo-modal').addEventListener('click',function(){
            document.getElementById('idequip').value = document.getElementById('tabla-equipo-modal').querySelector('tbody').querySelector('.fila-seleccionada').getAttribute('data-id');
            console.log(document.getElementById('idequip').value)
        })
        var modal = new bootstrap.Modal(document.getElementById('modal_adm_cita'));
        modal.show();
    })


    document.getElementById('Form_adm_cita').addEventListener('submit', function(event) {
        event.preventDefault(); // Evita que el formulario se envíe de forma predeterminada
        
        // Obtén los datos del formulario
        var idevent=document.getElementById('idevent')
        var idequip=document.getElementById('idequip')
        var formData = new FormData(this);
        // Añade idevent e idequip al FormData
        formData.append('idevent', idevent);
        formData.append('idequip', idequip);
    
    
        // Realiza la lógica que necesites con los datos del formulario
        fetch('/admisionar_cita', {
            method: 'POST',
            body: formData,
        })
        .then(response => response.json())
        .then(data => {
            // Maneja la respuesta del servidor
            if (data.success) {
                // Cierra el modal y realiza cualquier otra acción necesaria
                var modal = bootstrap.Modal.getInstance(document.getElementById('modal_adm_cita'));
                modal.hide();
    
                // Reemplaza el contenido de la fila seleccionada en la tabla
                // Obtener la fila seleccionada
            var tabla = document.getElementById('tabla-citas');
            var tbody_= tabla.querySelector('tbody');
            var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
            if (filaSeleccionada) {
                var id = filaSeleccionada.dataset.id;
                
                fetch('/eliminar_cita', {
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
            } else {
                // Maneja los errores
                console.error('Error al editar la cita:', data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
    });
    
    
})