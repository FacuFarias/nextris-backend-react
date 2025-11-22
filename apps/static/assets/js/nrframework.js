/**
 * Filtra una tabla por múltiples campos de texto y rango de fechas (sumatorio).
 * @param {string} tablaId - ID de la tabla a filtrar
 * @param {Array} campos - Array de objetos: {inputId, colIdx} para campos de texto
 * @param {Object} fechas - {desdeId, hastaId, colIdx} para rango de fechas
 */
function FiltroSumatorioTabla(tablaId, campos, fechas) {
    var tabla = document.getElementById(tablaId);
    var tbody = tabla.querySelector('tbody');
    var filas = tbody.querySelectorAll('tr');

    // Obtener valores de los campos de texto
    var valores = campos.map(c => document.getElementById(c.inputId).value.toLowerCase());
    // Obtener valores de fechas solo si fechas está definido y tiene propiedades
    var desdeDate = null, hastaDate = null, colFecha = null;
    if (fechas && typeof fechas === 'object' && fechas.desdeId && fechas.hastaId && typeof fechas.colIdx === 'number') {
        var desdeElem = document.getElementById(fechas.desdeId);
        var hastaElem = document.getElementById(fechas.hastaId);
        var desde = desdeElem ? desdeElem.value : null;
        var hasta = hastaElem ? hastaElem.value : null;
        desdeDate = desde ? new Date(desde) : null;
        hastaDate = hasta ? new Date(hasta) : null;
        colFecha = fechas.colIdx;
    }

    filas.forEach(function(fila) {
        var celdas = fila.querySelectorAll('td');
        var mostrar = true;
        // Filtrar por texto
        campos.forEach(function(campo, idx) {
            if (valores[idx] && !celdas[campo.colIdx].textContent.toLowerCase().includes(valores[idx])) {
                mostrar = false;
            }
        });
        // Filtrar por fecha solo si está configurado
        if (colFecha !== null && (desdeDate || hastaDate)) {
            var fechaTexto = celdas[colFecha].textContent.trim();
            var fechaFila = new Date(fechaTexto);
            if (desdeDate && fechaFila < desdeDate) mostrar = false;
            if (hastaDate && fechaFila > hastaDate) mostrar = false;
        }
        fila.style.display = mostrar ? '' : 'none';
    });
}

/**
 * Función para visualizar imágenes DICOM
 * @param {string} study_instance_uid - UID del estudio DICOM
 */
function VerDcm(study_instance_uid) {
    if (!study_instance_uid) {
        console.error('StudyInstanceUID no proporcionado');
        return;
    }
    
    // URL del visualizador DICOM (puede ser un servidor PACS o visualizador web)
    // Ejemplo: OHIF Viewer, Cornerstone.js, o servidor PACS personalizado
    var dicomViewerUrl = `http://192.168.1.45:8082/viewer.html?studyInstanceUID=${encodeURIComponent(study_instance_uid)}`;
    
    // Abrir en nueva ventana/pestaña
    var ventana = window.open(dicomViewerUrl, '_blank', 'width=1200,height=800,scrollbars=yes,resizable=yes');
    
    if (!ventana) {
        // Si el popup fue bloqueado, mostrar mensaje
        alert('Por favor, permite las ventanas emergentes para visualizar las imágenes DICOM.');
    } else {
        // Opcional: enfocar la nueva ventana
        ventana.focus();
    }
}

function VerPDF(idest){
    
    var url = `/verpdf/${idest}`;

    fetch(url)
        .then(response => {
            if (response.ok) {
                return response.blob();
            } else {
                throw new Error('No se pudo obtener el PDF');
            }
        })
        .then(blob => {
            var url = window.URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.target = '_blank';
            a.click();
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

function VerImagenes(idest){

    console.log("Ver imagenes DCM para ID: " + idest);
    $.ajax({
        url: '/get_image_link', // URL de tu API
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ id: idest }),
        success: function(response) {
            console.log(response)
            if (response[1]==1) {
                console.log(response[0]);
                
                // Obtener la URL del visor DICOM desde el backend
                $.ajax({
                    url: '/get_dicom_viewer_url',
                    method: 'GET',
                    success: function(config) {
                        var viewerUrl = config.url || 'http://192.168.1.45:8085/viewer.html';
                        var link = viewerUrl + '?studyUID=' + response[0];
                        console.log('Abriendo visor DICOM: ' + link);
                        window.open(link, '_blank');
                    },
                    error: function() {
                        // Si falla la obtención de la URL, usar la URL por defecto
                        var link = 'http://192.168.1.45:8085/viewer.html?studyUID=' + response[0];
                        console.log('Usando URL por defecto: ' + link);
                        window.open(link, '_blank');
                    }
                });
            } else {
                alert('No hay imágenes disponibles para este ID.');
            }
        },
        error: function() {
            alert('Hubo un error al comunicarse con el servidor.');
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
                        // Si es la última columna (columna activo), mostrar tick verde o X roja
                        if (i === item.length - 1) {
                            if (item[i] === 1 || item[i] === true) {
                                cell.innerHTML = '<i class="fas fa-check-circle text-success" title="Activo"></i>';
                            } else {
                                cell.innerHTML = '<i class="fas fa-times-circle text-danger" title="Inactivo"></i>';
                            }
                        } else {
                            // Para otras columnas booleanas, usar checkbox como antes
                            const checkbox = document.createElement('input');
                            checkbox.type = 'checkbox';
                            checkbox.classList.add('form-check-input')
                            
                            checkbox.checked = item[i]
                            checkbox.style.opacity = 2;
                            checkbox.disabled = true;
                            
                            cell.appendChild(checkbox);
                        }
                    } else {
                        // Para otras columnas, simplemente agrega el texto
                        cell.textContent = item[i];
                        
                        // AGREGAR ATRIBUTO data-modalidad para la columna de modalidad (índice 3, tercera columna)
                        // Solo para tabla-estudios (tablas de exámenes)
                        if (TablaId === 'tabla-estudios' && i === 3) {
                            cell.setAttribute('data-modalidad', item[i]);
                        }
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

// ===============================
// FUNCIONES HELPER PARA TOAST 
// ===============================

/**
 * Muestra un toast de éxito
 * @param {string} title - Título del toast
 * @param {string} message - Mensaje del toast
 */
function showSuccessToast(title, message) {
    showToast(title, message, "/templates/includes/toast/toast_success.html");
}

/**
 * Muestra un toast de error
 * @param {string} title - Título del toast
 * @param {string} message - Mensaje del toast
 */
function showErrorToast(title, message) {
    showToast(title, message, "/templates/includes/toast/toast_error.html");
}

/**
 * Muestra un toast de alerta/advertencia
 * @param {string} title - Título del toast
 * @param {string} message - Mensaje del toast
 */
function showAlertToast(title, message) {
    showToast(title, message, "/templates/includes/toast/toast_alert.html");
}

/**
 * Sistema de toast persistente usando localStorage
 * Útil para mostrar toast después de recargar la página
 */
if (typeof ToastSystem === 'undefined') {
    const ToastSystem = {
        /**
         * Programa un toast para mostrarse al cargar la página
         * @param {string} type - Tipo de toast: 'success', 'error', 'alert'
         * @param {string} title - Título del toast
         * @param {string} message - Mensaje del toast
     */
    scheduleToast: function(type, title, message) {
        localStorage.setItem('scheduledToast', JSON.stringify({
            type: type,
            title: title,
            message: message
        }));
    },
    
    /**
     * Muestra el toast programado si existe y lo elimina del localStorage
     */
    showScheduledToast: function() {
        const scheduledToast = localStorage.getItem('scheduledToast');
        if (scheduledToast) {
            const toast = JSON.parse(scheduledToast);
            switch(toast.type) {
                case 'success':
                    showSuccessToast(toast.title, toast.message);
                    break;
                case 'error':
                    showErrorToast(toast.title, toast.message);
                    break;
                case 'alert':
                    showAlertToast(toast.title, toast.message);
                    break;
            }
            localStorage.removeItem('scheduledToast');
        }
    }
};

// Hacer ToastSystem disponible globalmente si se creó exitosamente
if (typeof window !== 'undefined' && typeof ToastSystem !== 'undefined') {
    window.ToastSystem = ToastSystem;
}
}

// Auto-ejecutar toast programado al cargar la página
document.addEventListener('DOMContentLoaded', function() {
    ToastSystem.showScheduledToast();
});

function RellenarSelect(SelectId, dNeeded, TableId, selectedValue = null, showAllOption = true) {
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
        selectElement.innerHTML = '';

        if (showAllOption) {
            var todasOption = document.createElement('option');
            todasOption.value = 'default';
            todasOption.text = 'Todo';
            selectElement.appendChild(todasOption);
        }

        for (var i = 0; i < data.data.length; i++) {
            var option = document.createElement('option');
            option.value = data.data[i][0];
            option.text = data.data[i][1];
            selectElement.appendChild(option);
        }

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
        // Agregar la opción "Todas" al principio
        var todasOption = document.createElement('option');
        todasOption.value = 'sdef';
        todasOption.text = 'Sin definir';
        selectElement.appendChild(todasOption);
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

function RellenarSelectByClass(selectClass, dNeeded, TableId) {
    fetch('/rellenar_select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ dNeeded: dNeeded, TableId: TableId }),
    })
    .then(response => response.json())
    .then(data => {
        var selectElements = document.querySelectorAll(`.${selectClass}`);

        selectElements.forEach(selectElement => {
            // Limpiar cualquier opción existente en el <select>
            selectElement.innerHTML = '';

            // Agregar la opción "Todas" al principio
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
        console.error('Error:', error);
    });
}

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
                    // Si el botón tiene la clase boton_dcm, consultar al backend
                    if (boton.classList.contains('boton_dcm')) {
                        boton.disabled = true; // Desactivar por defecto
                        var idFila = fila.getAttribute('data-id');
                        fetch('/verificar_dcm', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({ id: idFila })
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                boton.disabled = false;
                            } else {
                                boton.disabled = true;
                            }
                        })
                        .catch(() => {
                            boton.disabled = true;
                        });
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


function configSearchForm(FormId,action,TableId){
    var FormPacientes = document.getElementById(FormId);

    FormPacientes.addEventListener('submit', function(event) {
        // Evitar el envío predeterminado del formulario
        event.preventDefault();
        // Realizar la solicitud HTTP usando fetch
        fetch(action, {
            method: 'POST',  // Puedes cambiarlo a 'POST' si prefieres enviar datos en el cuerpo
            body: new FormData(FormPacientes)
        })
        .then(response => response.json())
        .then(data => {
            var tablaPacientes = document.getElementById(TableId);
            var tbody_ = tablaPacientes.querySelector('tbody');
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
    });
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
                // Verificar si la eliminación fue exitosa
                if (data.status === 'OK') {
                    // Eliminar la fila de la tabla
                    filaSeleccionada.remove();
                    // Mostrar toast de éxito
                    showToast('¡Éxito!', data.message || 'Elemento eliminado correctamente', '/templates/includes/toast/toast_success.html');
                } else {
                    // Mostrar toast de error
                    showToast('Error', data.error || 'Error al eliminar elemento', '/templates/includes/toast/toast_error.html');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                // Mostrar toast de error de conexión
                showToast('Error', 'Error de conexión', '/templates/includes/toast/toast_error.html');
            });
        } else {
            console.warn('No hay fila seleccionada.');
            // Mostrar toast de advertencia
            showToast('Advertencia', 'Por favor selecciona una fila para eliminar', '/templates/includes/toast/toast_alert.html');
        }
    });
}

//el IdId hace referencia al div hidden donde se colocara el id.
function SetEditButton(buttonId, FormModalId, modalId, tablaId, FormAction, config,IdId) {
    var boton = document.getElementById(buttonId);

    boton.addEventListener('click', function () {
        // Obtener la fila seleccionada
        var Form = document.getElementById(FormModalId);
        
        // Asignar la acción del formulario directamente
        Form.action = FormAction;
        
        var tabla = document.getElementById(tablaId);
        var tbody_ = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');

        if (filaSeleccionada) {
            // Obtener los datos de la fila
            var id_span=document.getElementById(IdId)
            id_span.value=filaSeleccionada.dataset.id;
            
            // Obtener todas las celdas de la fila
            var celdas = filaSeleccionada.querySelectorAll('td');

            // Almacenar los valores en un arreglo
            var valores = Array.from(celdas).map(function (celda) {
                // Verifica si la celda contiene un checkbox
                var checkbox = celda.querySelector('input[type="checkbox"]');
                
                if (checkbox) {
                    // Si es un checkbox, devuelve el estado (checked o no) como valor
                    return checkbox.checked;
                } else {
                    // Si no es un checkbox, devuelve el contenido de texto de la celda
                    return celda.innerText;
                }
            });
            
            
            // Colocar los datos en el modal
            config.forEach(function (item, index) {
                var modalField = document.getElementById(item.modalFieldId);
                if (modalField.type === 'checkbox') {
                    modalField.checked = valores[index];
                } else if (modalField.type === 'select-one') {
                    // Encuentra la opción con el texto y selecciónala
                    var options = modalField.options;
                    for (var i = 0; i < options.length; i++) {
                        if (options[i].text === valores[index]) {
                            options[i].selected = true;
                            break; // Sal del bucle una vez que encuentres la opción
                        }
                    }
                } else if (modalField.type === 'date') {
                    var dateString = valores[index];
                    modalField.valueAsDate= new Date(dateString);
                    
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

function FiltrarSelect(labelId, tablaId, column) {
// Filtrado acumulativo por dos selects

    var selectElement = document.getElementById(labelId);
    var selectedOptionText = selectElement.options[selectElement.selectedIndex].text.toLowerCase();
    var ElementValue=selectElement.value
    var filas = document.getElementById(tablaId).getElementsByTagName('tbody')[0].getElementsByTagName('tr');

    for (var i = 0; i < filas.length; i++) {
        var descripcion = filas[i].getElementsByTagName('td')[column].innerText.toLowerCase();

        // Ocultar o mostrar la fila según el filtro
        if (ElementValue == "default") {
            filas[i].style.display = ''; // Mostrar todas las filas
        } else {
            filas[i].style.display = descripcion.includes(selectedOptionText) ? '' : 'none';
        }
    }
}

function filtrarSelectMulti(tablaId, labelId1, column1, labelId2, column2) {
    // Obtener los elementos select por sus IDs
    var selectElement1 = document.getElementById(labelId1); // Primer select
    var selectElement2 = document.getElementById(labelId2); // Segundo select
    // Obtener todas las filas de la tabla a filtrar
    var filas = document.getElementById(tablaId).getElementsByTagName('tbody')[0].getElementsByTagName('tr');

    // Obtener el valor y el texto seleccionado de cada select
    var val1 = selectElement1.value; // Valor del primer select
    var val2 = selectElement2.value; // Valor del segundo select
    var text1 = selectElement1.options[selectElement1.selectedIndex].text.toLowerCase(); // Texto del primer select
    var text2 = selectElement2.options[selectElement2.selectedIndex].text.toLowerCase(); // Texto del segundo select
    console.log(`Filtrando por: ${text1} (columna ${column1}), ${text2} (columna ${column2})`);

    // Recorrer todas las filas de la tabla
    for (var i = 0; i < filas.length; i++) {
        // Obtener el texto de la columna correspondiente a cada filtro
        var desc1 = filas[i].getElementsByTagName('td')[column1].innerText.toLowerCase();
        var desc2 = filas[i].getElementsByTagName('td')[column2].innerText.toLowerCase();
        var mostrar = true; // Bandera para mostrar u ocultar la fila
        // Si el valor del primer select no es 'default' y no coincide con el texto de la columna, ocultar la fila
        if (val1 !== 'default' && !desc1.includes(text1)) {
            mostrar = false;
        }
        
        // Si el valor del segundo select no es 'default' y no coincide con el texto de la columna, ocultar la fila
        if (val2 !== 'default' && !desc2.includes(text2)) {
            mostrar = false;
        }


        console.log(`Fila ${i}: desc1='${desc1}', desc2='${desc2}', mostrar=${mostrar}`);
        // Mostrar u ocultar la fila según los filtros
        filas[i].style.display = mostrar ? '' : 'none';
    }
}

function FiltrarFecha(labelId, tablaId, column) {
    var filtro = document.getElementById(labelId).value;
    if (filtro) {
        var filtroFecha = new Date(filtro);
        filtroFecha.setHours(0, 0, 0, 0); // Establecer las horas a 00:00:00 para comparar solo la fecha
    }
    var filas = document.getElementById(tablaId).getElementsByTagName('tbody')[0].getElementsByTagName('tr');

    for (var i = 0; i < filas.length; i++) {
        var fechaTexto = filas[i].getElementsByTagName('td')[column].innerText;
        var fecha = new Date(fechaTexto);
        fecha.setHours(0, 0, 0, 0); // Establecer las horas a 00:00:00 para comparar solo la fecha

        // Ocultar o mostrar la fila según el filtro
        if (filtro) {
            filas[i].style.display = fecha.getTime() === filtroFecha.getTime() ? '' : 'none';
        } else {
            filas[i].style.display = '';
        }
    }
}

function ConfigDefaultModal(FormId,route_action,ModalId,TablaId){
    var form_modal_p = document.getElementById(FormId);
    form_modal_p.action=route_action
    
    form_modal_p.addEventListener('submit', function(event) {
    // Evitar el envío predeterminado del formulario
    event.preventDefault();

    fetch(form_modal_p.action, {
        method: 'POST',
        body: new FormData(form_modal_p),
    })
    .then(response => response.json())
    .then(data => {
        console.log(data)
        var tabla = document.getElementById(TablaId);
        var tbody_=tabla.querySelector('tbody')
        var filas= tbody_.querySelectorAll('tr')

        // Detectar si hay una fila seleccionada (edición)
        var filaEdit = null;
        for (var i = 0; i < filas.length; i++) {
            if(filas[i].classList.contains('fila-seleccionada')){
                filaEdit = filas[i];
                break;
            }
        }
        if (filaEdit) {
            // Actualizar la fila seleccionada con los datos nuevos
            var celdas=filaEdit.querySelectorAll('td');
            var keys = Object.keys(data);
            for (var j = 0; j < celdas.length && j < keys.length; j++) {
                celdas[j].innerText = data[keys[j]];
            }
            showToast('Éxito', 'Paciente actualizado correctamente.', "/templates/includes/toast/toast_success.html");
        } else {
            // Alta: agregar nueva fila solo si no hay edición
            var nuevaFila = document.createElement('tr');
            var keys = Object.keys(data);
            keys.forEach(function(key) {
                var nuevaCelda = document.createElement('td');
                nuevaCelda.innerText = data[key];
                nuevaFila.appendChild(nuevaCelda);
            });
            tbody_.appendChild(nuevaFila);
        }
        $(ModalId).modal('hide');
        
    })
    .catch(error => {
        console.error('Error:', error);
        });
    });
}

function ConfigFiltrarText(labelId, tablaId) {
    const element = document.getElementById(labelId);
    if (element) {
        element.addEventListener("change", function() {
            FiltrarText(labelId, tablaId);
        });
    } else {
        console.warn(`ConfigFiltrarText: Elemento con ID '${labelId}' no encontrado`);
    }
}


function FiltrarText1Col(labelId, tablaId,column) {
    var filtro = document.getElementById(labelId).value.toLowerCase();
    var filas = document.getElementById(tablaId).getElementsByTagName('tbody')[0].getElementsByTagName('tr');

    for (var i = 0; i < filas.length; i++) {
        var descripcion = filas[i].getElementsByTagName('td')[column].innerText.toLowerCase();

        // Ocultar o mostrar la fila según el filtro
        filas[i].style.display = descripcion.includes(filtro) ? '' : 'none';
    }
}

function FiltrarText(labelId, tablaId /* column ignorado */) {
  const filtro = normalizar(document.getElementById(labelId).value);
  const tbody = document.getElementById(tablaId).tBodies[0];
  const filas = tbody ? tbody.rows : [];

  for (let i = 0; i < filas.length; i++) {
    const celdas = filas[i].cells;
    let textoFila = '';
    for (let j = 0; j < celdas.length; j++) {
      textoFila += ' ' + normalizar(celdas[j].innerText || celdas[j].textContent);
    }
    filas[i].style.display = (filtro === '' || textoFila.indexOf(filtro) !== -1) ? '' : 'none';
  }

  function normalizar(s) {
    return (s || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '') // sin acentos
      .trim();
  }
}

function ConfigFiltrarSelect(labelId, tablaId, column) {
    const element = document.getElementById(labelId);
    if (element) {
        element.addEventListener("change", function() {
            FiltrarSelect(labelId, tablaId, column);
        });
    } else {
        console.warn(`ConfigFiltrarSelect: Elemento con ID '${labelId}' no encontrado`);
    }
}

function ConfigFiltrarFecha(labelId, tablaId, column) {
    const element = document.getElementById(labelId);
    if (element) {
        element.addEventListener("change", function() {
            FiltrarFecha(labelId, tablaId, column);
        });
    } else {
        console.warn(`ConfigFiltrarFecha: Elemento con ID '${labelId}' no encontrado`);
    }
}

function ConfigMultiSelect(tablaId, labelId1, column1, labelId2, column2) {
    const element1 = document.getElementById(labelId1);
    const element2 = document.getElementById(labelId2);
    
    if (element1) {
        element1.addEventListener("change", function() {
            console.log("cambio 1");
            filtrarSelectMulti(tablaId, labelId1, column1, labelId2, column2);
        });
    } else {
        console.warn(`ConfigMultiSelect: Elemento con ID '${labelId1}' no encontrado`);
    }
    
    if (element2) {
        element2.addEventListener("change", function() {
            console.log("cambio 2");
            filtrarSelectMulti(tablaId, labelId1, column1, labelId2, column2);
        });
    } else {
        console.warn(`ConfigMultiSelect: Elemento con ID '${labelId2}' no encontrado`);
    }
}

/**
 * Inicializa el efecto blur en modales globalmente
 * Aplica desenfoque al contenido cuando se abre un modal
 * y lo remueve cuando se cierra
 */
function initModalBlurEffect() {
    // Función que aplica el blur
    function applyBlur() {
        const mainContent = document.querySelector('.main-content');
        const contentWrapper = document.querySelector('.content-wrapper');
        const sidenav = document.querySelector('.sidenav');
        const app = document.querySelector('main.app');
        
        if (mainContent) mainContent.style.filter = 'blur(8px)';
        if (contentWrapper) contentWrapper.style.filter = 'blur(8px)';
        if (sidenav) sidenav.style.filter = 'blur(8px)';
        if (app) app.style.filter = 'blur(8px)';
    }
    
    // Función que remueve el blur
    function removeBlur() {
        const mainContent = document.querySelector('.main-content');
        const contentWrapper = document.querySelector('.content-wrapper');
        const sidenav = document.querySelector('.sidenav');
        const app = document.querySelector('main.app');
        
        if (mainContent) mainContent.style.filter = 'none';
        if (contentWrapper) contentWrapper.style.filter = 'none';
        if (sidenav) sidenav.style.filter = 'none';
        if (app) app.style.filter = 'none';
    }
    
    // Registrar event listeners en un modal
    function registerModalEvents(modal) {
        // Evitar registrar múltiples veces
        if (modal.dataset.blurRegistered) return;
        modal.dataset.blurRegistered = 'true';
        
        modal.addEventListener('show.bs.modal', applyBlur);
        modal.addEventListener('hidden.bs.modal', removeBlur);
    }
    
    // Inicializar en DOMContentLoaded
    document.addEventListener('DOMContentLoaded', function() {
        // Registrar modales existentes
        document.querySelectorAll('.modal').forEach(registerModalEvents);
        
        // Observar modales que se agreguen dinámicamente
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1) { // Es un elemento
                        // Si el nodo es un modal
                        if (node.classList && node.classList.contains('modal')) {
                            registerModalEvents(node);
                        }
                        // O si contiene modales
                        node.querySelectorAll && node.querySelectorAll('.modal').forEach(registerModalEvents);
                    }
                });
            });
        });
        
        // Observar cambios en el body
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    });
}

// Inicializar el efecto blur automáticamente
initModalBlurEffect();

