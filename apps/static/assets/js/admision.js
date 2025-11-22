// Este archivo contiene funciones JavaScript para la gestión de la distribución de informes en la aplicación NextRIS.
// Muchas funciones que se utilizan en esta sección están definidas en otros archivos JS, como loader.js y toast.js, principalmente nrframework.js.
// No se deberán crear funciones duplicadas aquí si ya existen en esos archivos.

// Variable global para almacenar la ubicación seleccionada
let selectedLocationId = null;

//Objeto con datos de la orden - SIMPLIFICADO: Solo un estudio por admisión
let OrderData = {
    patientId: null,
    exam: null, // Ahora solo un examen en lugar de array
    equip: null, // Equipo seleccionado
    urgencia: null,
    medico_solicitante: null,
    obra_social: null,
};

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

function AsignarEquipo(TablaId) {
    var tabla = document.getElementById(TablaId);
    var tbody_g = tabla.querySelector('tbody');

    var filaSeleccionada = tbody_g.querySelector('tr.fila-seleccionada');
    if (filaSeleccionada) {
        var columna = filaSeleccionada.querySelector('td');
        var textoColumna = columna.textContent.trim();
        var idequip = filaSeleccionada.getAttribute('data-id');
        console.log('Id del equipo:', textoColumna);

        // Guardar el equipo en OrderData
        OrderData.equip = idequip;

        // Marcar visualmente que se seleccionó el equipo
        var divExamen = document.getElementById('pills-examen-tab');
        divExamen.classList.add('bg-success');
        divExamen.classList.remove('bg-danger');

        // Mostrar el equipo seleccionado en la UI
        var equipoSeleccionadoSpan = document.getElementById('equipo-seleccionado');
        if (equipoSeleccionadoSpan) {
            equipoSeleccionadoSpan.textContent = `Equipo: ${textoColumna}`;
            equipoSeleccionadoSpan.classList.remove('d-none');
        }

        // Actualizar resumen en prestación
        var resumenEquipo = document.getElementById('resumen-equipo');
        if (resumenEquipo) {
            resumenEquipo.textContent = textoColumna;
        }

        // Ir automáticamente a la pestaña de Prestación
        var pillPrestButton = document.querySelector('[data-bs-target="#pills-prest"]');
        if (pillPrestButton) {
            var tab = new bootstrap.Tab(pillPrestButton);
            tab.show();
        }
    }
}

function FinalizarOrden() {
    var pillPaciente = document.getElementById('pills-paciente-tab');
    var pillExamen = document.getElementById('pills-examen-tab');

    // Verificar si los objetos tienen la clase 'bg-success'
    var allSuccess = true;
    var messages = [];

    if (!pillPaciente.classList.contains('bg-success')) {
        pillPaciente.classList.add('bg-danger');
        messages.push("No se ha seleccionado paciente");
        allSuccess = false;
    }

    if (!pillExamen.classList.contains('bg-success')) {
        pillExamen.classList.add('bg-danger');
        messages.push("No se ha seleccionado examen / Equipo");
        allSuccess = false;
    }

    if (allSuccess) {
        // Preparar datos para enviar (estructura simplificada)
        const orderToSend = {
            patientId: OrderData.patientId,
            exams: [{
                examId: OrderData.exam.examId,
                title: OrderData.exam.title,
                equip: OrderData.equip,
                medico_solicitante: OrderData.medico_solicitante,
                obra_social: OrderData.obra_social
            }],
            urgencia: OrderData.urgencia
        };

        // Enviar OrderData al backend si todos los datos están completos
        fetch('/crear_worklist', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(orderToSend)
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error('Error en el envío de la orden.');
            }
        })
        .then(data => {
            showToast('Perfecto!', 'Orden creada exitosamente:', "/templates/includes/toast/toast_success.html");
            
            // Limpiar OrderData
            OrderData.patientId = null;
            OrderData.exam = null;
            OrderData.equip = null;
            OrderData.medico_solicitante = null;
            OrderData.obra_social = null;

            // Limpiar la UI
            var estudioSeleccionadoDiv = document.getElementById('estudio-seleccionado-container');
            if (estudioSeleccionadoDiv) {
                estudioSeleccionadoDiv.innerHTML = '';
                estudioSeleccionadoDiv.classList.add('d-none');
            }

            var equipoSeleccionadoSpan = document.getElementById('equipo-seleccionado');
            if (equipoSeleccionadoSpan) {
                equipoSeleccionadoSpan.textContent = '';
                equipoSeleccionadoSpan.classList.add('d-none');
            }

            // Limpiar resúmenes
            var resumenPaciente = document.getElementById('resumen-paciente');
            var resumenEstudio = document.getElementById('resumen-estudio');
            var resumenEquipo = document.getElementById('resumen-equipo');
            if (resumenPaciente) resumenPaciente.textContent = 'No seleccionado';
            if (resumenEstudio) resumenEstudio.textContent = 'No seleccionado';
            if (resumenEquipo) resumenEquipo.textContent = 'No seleccionado';

            // Limpiar li_dni
            var li_dni = document.getElementById('dni-item');
            if (li_dni) li_dni.innerText = '';

            // Rellenar nuevamente tabla-estudios
            RellenarTabla('tabla-estudios', `/get_exams_adm`);

            // Remover clases de éxito en las pestañas
            pillPaciente.classList.remove('bg-success', 'bg-danger');
            pillExamen.classList.remove('bg-success', 'bg-danger');

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
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('Error', 'No se pudo crear la orden', "/templates/includes/toast/toast_alert.html");
        });

        console.log('Datos de la orden finalizada:', orderToSend);
    } else {
        // Mostrar el toast con los mensajes de error
        showToast('Ha ocurrido un problema', messages.join('<br>'), "/templates/includes/toast/toast_alert.html");
    }
    
}

function SeleccionarPaciente(TablaId){
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    var li_dni = document.getElementById('dni-item');
    var divPaciente = document.getElementById('pills-paciente-tab');

    if (filaSeleccionada) {
        console.log(filaSeleccionada.dataset.id)
        OrderData.patientId=filaSeleccionada.dataset.id
        var tds = filaSeleccionada.querySelectorAll('td');
        var nombreCompleto = tds[0].innerText + ", " + tds[1].innerText;
        li_dni.innerText = "Paciente seleccionado: " + nombreCompleto;
        divPaciente.classList.add('bg-success'); // Agrega la clase de Bootstrap para fondo verde
        divPaciente.classList.remove('bg-danger'); // Agrega la clase de Bootstrap para fondo verde

        // Actualizar resumen en prestación
        var resumenPaciente = document.getElementById('resumen-paciente');
        if (resumenPaciente) {
            resumenPaciente.textContent = nombreCompleto;
        }

        // Ir automáticamente a la pestaña de Examen
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



// NUEVA FUNCIÓN SIMPLIFICADA: Seleccionar un solo estudio y mostrar equipos
function ConfigTablaEstudiosSimplificada(TablaId) {
    var tablaEstudios = document.getElementById(TablaId);
    var tbodyest = tablaEstudios.querySelector('tbody');

    // Al hacer click en un estudio
    tbodyest.addEventListener('click', function (event) {
        var fila = event.target.closest('tr');
        if (!fila) return;

        // Remover selección previa
        var filas = tbodyest.querySelectorAll('tr');
        filas.forEach(f => f.classList.remove('fila-seleccionada'));

        // Marcar la fila como seleccionada
        fila.classList.add('fila-seleccionada');

        // Obtener datos del estudio
        var columnas = fila.querySelectorAll('td');
        var codigoEst = columnas[0].textContent.trim();
        var descEst = columnas[1].textContent.trim();
        var idExam = fila.getAttribute('data-id');

        // Guardar en OrderData
        OrderData.exam = {
            examId: idExam,
            title: codigoEst + " - " + descEst
        };

        console.log('Estudio seleccionado:', OrderData.exam);

        // Mostrar el estudio seleccionado en la UI
        MostrarEstudioSeleccionado(codigoEst, descEst);

        // Cargar equipos disponibles para este estudio
        CargarEquiposParaEstudio(descEst);
    });

    // Doble click también selecciona
    document.getElementById(TablaId).addEventListener("dblclick", function(event) {
        var fila = event.target.closest('tr');
        if (fila) {
            fila.click(); // Simular click simple
        }
    });
}

// Mostrar el estudio seleccionado visualmente
function MostrarEstudioSeleccionado(codigo, descripcion) {
    var container = document.getElementById('estudio-seleccionado-container');
    if (!container) return;

    container.innerHTML = `
        <div class="card shadow-lg mb-3">
            <div class="card-header bg-gradient-primary">
                <h6 class="mb-0">
                    <i class="fas fa-check-circle me-2"></i>Estudio Seleccionado
                </h6>
            </div>
            <div class="card-body">
                <p class="mb-1"><strong>Código:</strong> ${codigo}</p>
                <p class="mb-0"><strong>Descripción:</strong> ${descripcion}</p>
                <span id="equipo-seleccionado" class="badge bg-success mt-2 d-none"></span>
            </div>
        </div>
    `;
    container.classList.remove('d-none');

    // Actualizar resumen en prestación
    var resumenEstudio = document.getElementById('resumen-estudio');
    if (resumenEstudio) {
        resumenEstudio.textContent = `${codigo} - ${descripcion}`;
    }
}

// Cargar equipos disponibles para el estudio seleccionado (filtrados por ubicación)
function CargarEquiposParaEstudio(descripcionEstudio) {
    var tbodyEquipos = document.getElementById('tbody-equipos');
    
    // Construir URL con location_id si está seleccionado
    let final_route = "/get_equip_for_exam?exam=" + descripcionEstudio;
    if (selectedLocationId) {
        final_route += "&location_id=" + selectedLocationId;
        console.log('[DEBUG CargarEquiposParaEstudio] Cargando equipos para estudio:', descripcionEstudio, 'location_id:', selectedLocationId);
    } else {
        console.log('[DEBUG CargarEquiposParaEstudio] Cargando equipos sin filtro de ubicación para estudio:', descripcionEstudio);
    }
    
    fetch(final_route)
        .then(response => response.json())
        .then(data => {
            tbodyEquipos.innerHTML = '';
            // Llenar la tabla con los datos recibidos
            data.forEach(item => {
                const nuevaFila = document.createElement('tr');
                nuevaFila.setAttribute('data-id', item[0]); // Almacenar el primer valor como ID
                nuevaFila.innerHTML = `<td>${item[1]}</td>`; // Mostrar solo el segundo valor
                tbodyEquipos.appendChild(nuevaFila);
            });

            // Mostrar mensaje si no hay equipos
            if (data.length === 0) {
                const mensajeUbicacion = selectedLocationId ? ' para esta ubicación' : '';
                tbodyEquipos.innerHTML = `<tr><td class="text-center text-muted">No hay equipos disponibles${mensajeUbicacion}</td></tr>`;
            }
            
            console.log('[DEBUG CargarEquiposParaEstudio] Equipos cargados:', data.length);
        })
        .catch(error => {
            console.error('Error:', error);
            tbodyEquipos.innerHTML = '<tr><td class="text-center text-danger">Error al cargar equipos</td></tr>';
        });
}

// Función global para cargar médicos solicitantes por ubicación
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
        
        // Actualizar el select de médico solicitante
        const selectElement = document.getElementById('medico_solicitante');
        if (!selectElement) return;
        
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
    })
    .catch(error => {
        console.error('Error al cargar médicos solicitantes:', error);
    });
}

// Función global para cargar obras sociales por ubicación
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
        
        // Actualizar el select de obra social
        const selectElement = document.getElementById('obra_social');
        if (!selectElement) return;
        
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
    })
    .catch(error => {
        console.error('Error al cargar obras sociales:', error);
    });
}

// Función global para cargar pacientes por ubicación (con filtrado por patientdomain)
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

document.addEventListener("DOMContentLoaded", function() {

    // --- Alta rápida de paciente ---
    var formPacienteRapido = document.getElementById('form_paciente_rapido');
    console.log('Buscando formulario de paciente rápido en admisión:', formPacienteRapido);
    
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
                    var modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modal_np'));
                    modal.hide();
                    // Limpiar el formulario
                    form.reset();

                    // Refrescar la tabla de pacientes y seleccionar el nuevo
                    if (selectedLocationId) {
                        cargarPacientesPorLocation(selectedLocationId);
                    }
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

    var boton=document.getElementById("b_sel_pac_para_adm")
    boton.addEventListener("click",function(){SeleccionarPaciente('tabla-paciente')})

    RellenarTabla('tabla-estudios',`/get_exams_adm`)

    RellenarSelect("tipo_examen","externalcode","nextris.IsModality")
    RellenarSelect("parte_cuerpo","Description","nextris.IsAnatomicalPart")
    
    // Configurar filtrado combinado de tipo_examen (columna 2) y parte_cuerpo (columna 3)
    ConfigMultiSelect('tabla-estudios', 'tipo_examen', 2, 'parte_cuerpo', 3)
    ConfigFiltrarText('l_exam', 'tabla-estudios',1)

    ConfigurarTabla('tabla-paciente','botones_sp')
    // Doble click en paciente selecciona igual que el botón
    document.getElementById('tabla-paciente').addEventListener('dblclick', function(){SeleccionarPaciente('tabla-paciente')});

    // =============================================
    // CONFIGURACIÓN DE FILTRADO POR UBICACIÓN
    // =============================================
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
                    }
                    locationSelector.appendChild(option);
                });
                
                // Si hay una ubicación por defecto, cargar pacientes y listas
                if (selectedLocationId) {
                    cargarPacientesPorLocation(selectedLocationId);
                    cargarMedicosSolicitantesPorLocation(selectedLocationId);
                    cargarObrasSocialesPorLocation(selectedLocationId);
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
            cargarPacientesPorLocation(selectedLocationId);
            cargarMedicosSolicitantesPorLocation(selectedLocationId);
            cargarObrasSocialesPorLocation(selectedLocationId);
            inputBusqueda.disabled = false;
            btnSearch.disabled = false;
            
            // Si hay un estudio seleccionado, recargar equipos con el nuevo filtro de ubicación
            if (OrderData.exam) {
                // Obtener la descripción del estudio desde la tabla
                const filaEstudio = document.querySelector('#tabla-estudios tr.fila-seleccionada');
                if (filaEstudio) {
                    const celdaDescripcion = filaEstudio.cells[0]; // Primera celda tiene la descripción
                    if (celdaDescripcion) {
                        const descripcionEstudio = celdaDescripcion.textContent.trim();
                        console.log('[DEBUG] Recargando equipos por cambio de ubicación para estudio:', descripcionEstudio);
                        CargarEquiposParaEstudio(descripcionEstudio);
                    }
                }
            }
        } else {
            // Limpiar tabla si no hay ubicación seleccionada
            const tabla = document.getElementById('tabla-paciente');
            const tbody = tabla.querySelector('tbody');
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">Seleccione una ubicación</td></tr>';
            inputBusqueda.disabled = true;
            btnSearch.disabled = true;
        }
    });
    
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

    ConfigurarTabla('tabla-equipos-p-exam','sel_equip')

    var boton=document.getElementById("sel-equip")
    boton.addEventListener("click",function(){AsignarEquipo('tabla-equipos-p-exam')})
    document.getElementById('tabla-equipos-p-exam').addEventListener("dblclick",function(){AsignarEquipo('tabla-equipos-p-exam')})

    // Prestacion - Los selects de médico y obra social se cargan por ubicación (ver más arriba)
    // Ya no usamos RellenarSelect general, sino las funciones específicas por ubicación

    // Event listeners para guardar datos en OrderData
    document.getElementById('medico_solicitante').addEventListener('change', function(event) {
        OrderData.medico_solicitante = event.target.value;
        console.log('Médico solicitante:', OrderData.medico_solicitante);
    });
    
    document.getElementById('obra_social').addEventListener('change', function(event) {
        OrderData.obra_social = event.target.value;
        console.log('Obra social:', OrderData.obra_social);
    });

    var boton=document.getElementById("finalizar_orden")
    boton.addEventListener("click",function(){FinalizarOrden()})

    //------------- NUEVA LÓGICA SIMPLIFICADA -------------
    // Configurar la tabla de estudios con la nueva función simplificada
    ConfigTablaEstudiosSimplificada('tabla-estudios');

})
