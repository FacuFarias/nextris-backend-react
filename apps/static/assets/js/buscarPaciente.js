// Este archivo contiene funciones JavaScript para la gestión de pacientes y su historial en la aplicación NextRIS.
// Muchas funciones que se utilizan en esta sección están definidas en otros archivos JS, como loader.js y toast.js, principalmente nrframework.js.
// No se deberán crear funciones duplicadas aquí si ya existen en esos archivos.

// ============================================
// FUNCIÓN PERSONALIZADA PARA TABLA DE PACIENTES
// ============================================

/**
 * Rellena la tabla de pacientes sin convertir el número de estudios (1) en checkbox
 * @param {string} TablaId - ID de la tabla a llenar
 * @param {string} route - Ruta del endpoint que devuelve los datos
 */
function RellenarTablaPacientes(TablaId, route) {
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

                // Iterar sobre los elementos de item (omitir el primer elemento que es Guid)
                for (var i = 1; i < item.length; i++) {
                    var cell = document.createElement('td');
                    
                    // La última columna es el conteo de estudios, debe mostrarse como número
                    // Las demás columnas con 0 o 1 pueden ser checkboxes (ej: sexo)
                    var isLastColumn = (i === item.length - 1);
                    
                    if ((item[i] === 0 || item[i] === 1) && !isLastColumn) {             
                        const checkbox = document.createElement('input');
                        checkbox.type = 'checkbox';
                        checkbox.classList.add('form-check-input');
                        checkbox.checked = item[i];
                        checkbox.style.opacity = 2;
                        checkbox.disabled = true;
                        cell.appendChild(checkbox);
                    } else {
                        // Para otras columnas, incluyendo el conteo de estudios, mostrar como texto
                        cell.textContent = item[i];
                    }

                    row.appendChild(cell);
                }

                tbody_.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error al cargar tabla de pacientes:', error);
        });
}

// ============================================
// GESTIÓN DE MODALES DINÁMICOS
// ============================================

// Función para cargar el modal dinámicamente
function cargarModalNuevoPaciente(callback) {
    // Verificar si el modal ya está cargado
    var modalElement = document.getElementById('modal_np');
    if (modalElement) {
        // Si ya existe, ejecutar el callback directamente
        if (callback) callback();
        return;
    }
    
    // Si no existe, cargarlo
    fetch('/modal_nuevo_paciente.html')
        .then(response => {
            if (!response.ok) {
                throw new Error('Error al cargar modal');
            }
            return response.text();
        })
        .then(data => {
            // Inyectar el modal en el contenedor GLOBAL (fuera de main-content)
            var modalContent = `
                <div class="modal-wrapper" id="modal_data">
                    ${data}
                </div>
            `;
            document.getElementById('global_modal_container').innerHTML = modalContent;
            
            console.log('Modal cargado correctamente en contenedor global');
            
            // Esperar un momento para que el DOM se actualice
            setTimeout(function() {
                // Inicializar configuración del modal
                ConfigDefaultModal('Form_ag','/agregar_pacientes','#modal_np',"tabla-pacientes");
                
                // Ejecutar callback si existe
                if (callback) callback();
            }, 100);
        })
        .catch(error => {
            console.error('Error al cargar modal_nuevo_paciente.html:', error);
        });
}

// Función para abrir modal de nuevo paciente
function abrirModalNuevoPaciente() {
    cargarModalNuevoPaciente(function() {
        // Mostrar el modal usando Bootstrap
        var modalElement = document.getElementById('modal_np');
        if (modalElement) {
            var modal = new bootstrap.Modal(modalElement);
            modal.show();
        } else {
            console.error('No se encontró el elemento modal_np');
        }
    });
}

// Función para editar paciente (carga modal si es necesario)
function editarPacienteConModal() {
    cargarModalNuevoPaciente(function() {
        // Una vez cargado el modal, ejecutar la lógica de edición
        var FormModalId = "Form_ag";
        var modalId = "modal_np";
        var tablaId = "tabla-pacientes";
        var FormAction = "/editar_paciente";
        var IdId = "id_np";
        
        var configNP = [
            { modalFieldId: 'p_name', type: 'text' },
            { modalFieldId: 'p_surname', type: 'text' },
            { modalFieldId: 'p_dni', type: 'number' },
            { modalFieldId: 'sex', type: 'select-one' },
            { modalFieldId: 'fecha_nacimiento', type: 'date' },
            { modalFieldId: 'telefono', type: 'text' },
            { modalFieldId: 'mail', type: 'text' },
            { modalFieldId: 'p_healthcard', type: 'text' },
        ];
        
        // Obtener la fila seleccionada
        var Form = document.getElementById(FormModalId);
        
        if (!Form) {
            console.error('No se encontró el formulario:', FormModalId);
            return;
        }
        
        // Asignar la acción del formulario directamente
        Form.action = FormAction;
        
        var tabla = document.getElementById(tablaId);
        var tbody_ = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');

        if (filaSeleccionada) {
            // Obtener los datos de la fila
            var id_span = document.getElementById(IdId);
            id_span.value = filaSeleccionada.dataset.id;
            
            // Obtener todas las celdas de la fila
            var celdas = filaSeleccionada.querySelectorAll('td');

            // Almacenar los valores en un arreglo
            var valores = Array.from(celdas).map(function (celda) {
                var checkbox = celda.querySelector('input[type="checkbox"]');
                if (checkbox) {
                    return checkbox.checked;
                } else {
                    return celda.innerText;
                }
            });
            
            // Colocar los datos en el modal
            configNP.forEach(function (item, index) {
                var modalField = document.getElementById(item.modalFieldId);
                if (modalField.type === 'checkbox') {
                    modalField.checked = valores[index];
                } else if (modalField.type === 'select-one') {
                    var options = modalField.options;
                    for (var i = 0; i < options.length; i++) {
                        if (options[i].text === valores[index]) {
                            options[i].selected = true;
                            break;
                        }
                    }
                } else if (modalField.type === 'date') {
                    var dateString = valores[index];
                    modalField.valueAsDate = new Date(dateString);
                } else {
                    modalField.value = valores[index];
                }
            });

            // Mostrar el modal
            var modal = new bootstrap.Modal(document.getElementById(modalId));
            modal.show();
        } else {
            console.warn('No hay fila seleccionada.');
        }
    });
}

// ============================================
// GESTIÓN DE PACIENTES
// ============================================


// Chequea la cantidad de estudios de un paciente por su id
function CheckearCantEstudios(idpaciente) {
    // Esta función debe consultar al backend para obtener la cantidad de estudios
    // Por simplicidad, aquí se hace de forma síncrona (puedes adaptarla a async si lo necesitas)
    var cantidad = 0;
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/get_cantidad_estudios', false); // false = síncrono
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify({ id: idpaciente }));
    if (xhr.status === 200) {
        var resp = JSON.parse(xhr.responseText);
        cantidad = resp.cantidad || 0;
    }
    return cantidad;
}

// Elimina un paciente por su id
function EliminarPaciente(idpaciente) {
    // Llama al backend para eliminar el paciente
    fetch('/eliminar_paciente', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id: idpaciente })
    })
    .then(response => response.json())
    .then(data => {
        if(data.success){
            // alert('Paciente eliminado correctamente');
            showToast('Éxito', 'Paciente eliminado correctamente.', "/templates/includes/toast/toast_success.html");
            // Recargar la tabla de pacientes
            RellenarTablaPacientes('tabla-pacientes',`/get_patients`);
        } else {
            showToast('Error', 'No se pudo eliminar el paciente.', "/templates/includes/toast/toast_error.html");
        }
    })
    .catch(error => {
        showToast('Error', 'Error al eliminar el paciente.', "/templates/includes/toast/toast_error.html");
        console.error(error);
    });
}
// Tengo que poner los nombres de los campos del modal. Es necesario que tengan un id diferente para campos que sean iguales y tienen que ser en el orden que aparecen en la fila. Por ejemplo, description
var configNP = [
    { modalFieldId: 'p_name', type: 'text' },
    { modalFieldId: 'p_surname', type: 'text' },
    { modalFieldId: 'p_dni', type: 'number' },
    { modalFieldId: 'sex', type: 'select-one' },
    { modalFieldId: 'fecha_nacimiento', type: 'date' },
    
    { modalFieldId: 'telefono', type: 'text' },
    { modalFieldId: 'mail', type: 'text' },
    { modalFieldId: 'p_healthcard', type: 'text' },
    
];

function getHistory() {
    // Si hay una fila seleccionada
    var tabla = document.getElementById("tabla-pacientes");
    var tbody_g = tabla.querySelector('tbody');

    var filaSeleccionada = tbody_g.querySelector('tr.fila-seleccionada');
    if (filaSeleccionada) {
        var idpat = filaSeleccionada.getAttribute('data-id');
        
        console.log("Paciente seleccionado con ID:", idpat);
        // Hacer una llamada al back-end para obtener el historial del paciente
        fetch(`/get_patient_history`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ id: idpat }) // Enviamos el ID del paciente en el body
        })
        .then(response => response.json())
        .then(data => {
            // Procesar los datos del historial obtenidos del back-end
            console.log("Historial del paciente:", data);
            
            // Aquí actualizamos la tabla del historial con los datos recibidos
            updateHistorialTable(data);
            
            // Cambiar a la pestaña de historial
            var triggerEl = document.querySelector('#pills-examen-tab');
            var tab = new bootstrap.Tab(triggerEl);
            tab.show();
        })
        .catch(error => {
            console.error('Error al obtener el historial del paciente:', error);
        });
    } else {
        console.log("No hay paciente seleccionado.");
    }
}

function updateHistorialTable(data) {
    // Seleccionar la tabla de historial
    var tablaHistorial = document.getElementById('tabla-historial');
    var tbody = tablaHistorial.querySelector('tbody');

    // Limpiar la tabla antes de llenarla
    tbody.innerHTML = '';

    // Llenar la tabla con los datos recibidos
    data.forEach(historial => {
        var fila = document.createElement('tr');

        // El 'guid' lo almacenamos en 'data-id' del <tr>
        fila.setAttribute('data-id', historial.guid);

        // Crear celdas para cada campo en el orden correcto:
        // Estudio | Médico Autor | Médico Referente | Fecha | Modalidad | Con imagen
        
        var celdaEstudio = document.createElement('td');
        celdaEstudio.textContent = historial.estudio || 'N/A';
        fila.appendChild(celdaEstudio);

        var celdaMedicoAutor = document.createElement('td');
        celdaMedicoAutor.textContent = historial.medico_autor || 'No asignado';
        fila.appendChild(celdaMedicoAutor);

        var celdaMedicoReferente = document.createElement('td');
        celdaMedicoReferente.textContent = historial.medico_referente || 'No asignado';
        fila.appendChild(celdaMedicoReferente);

        var celdaFecha = document.createElement('td');
        celdaFecha.textContent = historial.fecha || 'Sin fecha';
        fila.appendChild(celdaFecha);

        var celdaModalidad = document.createElement('td');
        celdaModalidad.textContent = historial.modalidad || 'N/A';
        fila.appendChild(celdaModalidad);

        var celdaConImagen = document.createElement('td');
        celdaConImagen.textContent = historial.con_imagen || 'No';
        fila.appendChild(celdaConImagen);

        // Añadir la fila a la tabla
        tbody.appendChild(fila);
    });
}



document.addEventListener("DOMContentLoaded", function() {

    var triggerEl = document.querySelector('#pills-examen-tab');
    var tab = new bootstrap.Tab(triggerEl);
    tab.show();

    var triggerEl = document.querySelector('#pills-paciente-tab');
    var tab = new bootstrap.Tab(triggerEl);
    tab.show();
    
    // configuracion de busqueda y llenado de tabla
    RellenarTablaPacientes('tabla-pacientes',`/get_patients`)
    ConfigurarTabla('tabla-pacientes','botones_sp')
    ConfigurarTabla('tabla-historial','botones_hp')


    // Event listener para el botón de seleccionar paciente
    var seleccionarPacienteBtn = document.getElementById('pills-examen-tab');
    seleccionarPacienteBtn.addEventListener('click', function() {
        getHistory();
    });

    // Doble click en la tabla de pacientes ejecuta getHistory
    var tablaPacientes = document.getElementById('tabla-pacientes');
    var tbodyPacientes = tablaPacientes.querySelector('tbody');
    tbodyPacientes.addEventListener('dblclick', function(e) {
        var tr = e.target.closest('tr');
        if(tr) {
            // Marcar la fila como seleccionada
            tbodyPacientes.querySelectorAll('tr').forEach(fila => fila.classList.remove('fila-seleccionada'));
            tr.classList.add('fila-seleccionada');
            getHistory();
        }
    });

    // NOTA: ConfigDefaultModal se llama ahora dentro de abrirModalNuevoPaciente()
    // ya que el modal se carga dinámicamente

    // Configurar botón de editar para que cargue el modal si es necesario
    var editarBtn = document.getElementById('editar-paciente');
    if (editarBtn) {
        editarBtn.addEventListener('click', function() {
            editarPacienteConModal();
        });
    }
    
    var deleteBtn = document.getElementById('eliminar-paciente');
    deleteBtn.addEventListener('click', function() {
        var tabla = document.getElementById("tabla-pacientes");
        var tbody_g = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_g.querySelector('tr.fila-seleccionada');
        if (filaSeleccionada) {
            var idpaciente = filaSeleccionada.getAttribute('data-id');
        }
        cantidad=CheckearCantEstudios(idpaciente)
        if (cantidad > 1) {
            // Si hay estudios, mostrar mensaje
            alert("No es posible eliminar. Tiene estudios disponibles asignados.");
        } else {
            // Si no hay estudios, continuar con la eliminación
            console.log("Eliminando paciente con ID:", idpaciente);
            EliminarPaciente(idpaciente);
        }
    });
    
    ConfigFiltrarText('busquedaSwitch', 'tabla-pacientes', 1);

    var verInformeBtn = document.getElementById('ver-informe');
    verInformeBtn.addEventListener('click', function() {
        var tabla = document.getElementById("tabla-historial");
        var tbody_g = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_g.querySelector('tr.fila-seleccionada');
        if (filaSeleccionada) {
            var idest = filaSeleccionada.getAttribute('data-id');
        }
        VerPDF(idest)        
    });

    var verImagenBtn = document.getElementById('ver-imagen');
    verImagenBtn.addEventListener('click', function() {
        var tabla = document.getElementById("tabla-historial");
        var tbody_g = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_g.querySelector('tr.fila-seleccionada');
        if (filaSeleccionada) {
            var idest = filaSeleccionada.getAttribute('data-id');
        }
        VerImagenes(idest)
    })

});
