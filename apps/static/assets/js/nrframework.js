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
    $.ajax({
        url: '/get_image_link', // URL de tu API
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ id: idest }),
        success: function(response) {
            console.log(response)
            if (response[1]==1) {
                console.log(response[0]);
                var link = 'http://192.168.31.56/viewer.html?studyUID=' + response[0];
                
                window.open(link, '_blank');
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
        todasOption.value = 'default';
        todasOption.text = 'Todo';
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


function FiltrarText(labelId, tablaId,column) {
    var filtro = document.getElementById(labelId).value.toLowerCase();
    console.log("hola")
    var filas = document.getElementById(tablaId).getElementsByTagName('tbody')[0].getElementsByTagName('tr');

    for (var i = 0; i < filas.length; i++) {
        var descripcion = filas[i].getElementsByTagName('td')[column].innerText.toLowerCase();

        // Ocultar o mostrar la fila según el filtro
        filas[i].style.display = descripcion.includes(filtro) ? '' : 'none';
    }
}


function FiltrarSelect(labelId, tablaId, column) {
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

        if(form_modal_p.action==='http://127.0.0.1:5000/editar_paciente'){   
            for (var i = 0; i < filas.length; i++) {
                if(filas[i].classList.contains('fila-seleccionada')){
                    celdas=filas[i].querySelectorAll('td')
                    for (var j = 0; j < celdas.length; j++) {
                        celdas[j].innerText=data[j]
                        console.log(celdas[j])
                        console.log(data[j])
                    }
                }
            }
        }
        else {
            var nuevaFila = document.createElement('tr');
            var keys = ['p_name', 'p_surname', 'p_dni', 'sex', 'fecha_nacimiento', 'telefono', 'mail', 'p_healthcard'];
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

function ConfigFiltrarText(labelId, tablaId,column) {
    document.getElementById(labelId).addEventListener("change",function(){
        FiltrarText(labelId, tablaId,column)
    })
}

function ConfigFiltrarSelect(labelId, tablaId,column) {
    document.getElementById(labelId).addEventListener("change",function(){
        FiltrarSelect(labelId, tablaId,column)
    })
}
function ConfigFiltrarFecha(labelId, tablaId,column) {
    document.getElementById(labelId).addEventListener("change",function(){
        FiltrarFecha(labelId, tablaId,column)
    })
}