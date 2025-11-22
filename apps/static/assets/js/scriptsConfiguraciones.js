// Tengo que poner los nombres de los campos del modal. Es necesario que tengan un id diferente para campos que sean iguales y tienen que ser en el orden que aparecen en la fila. Por ejemplo, description
var configBU = [
    { modalFieldId: 'Description_bu', type: 'text' },
    { modalFieldId: 'code_bu', type: 'text' },
    { modalFieldId: 'ex_code_bu', type: 'text' },
    { modalFieldId: 'IsAc_bu', type: 'checkbox' },
    { modalFieldId: 'http_pacs', type: 'text' },
    
    { modalFieldId: 'tecnico_obl', type: 'checkbox' },
    { modalFieldId: 'questions_manda', type: 'checkbox' },
    
];

var configAgenda = [
    { modalFieldId: 'Description_agenda', type: 'text' },
    { modalFieldId: 's_equip', type: 'select-one' },
    { modalFieldId: 'Ex_agenda', type: 'text' },
    { modalFieldId: 'IsAc_ag', type: 'checkbox' },
    { modalFieldId: 'fecha_inicio_agenda_input', type: 'text' },
    { modalFieldId: 'fecha_fin_agenda_input', type: 'text' }
    
];

var configItemAgenda = [
    { modalFieldId: 'day', type: 'select' },
    { modalFieldId: 'timefrom', type: 'time' },
    { modalFieldId: 'timeto', type: 'time' },
    { modalFieldId: 'initday', type: 'date' },
    { modalFieldId: 'finishday', type: 'date' }
];


var configUser = [
    { modalFieldId: 'username', type: 'text' },
    { modalFieldId: 's_type_of_user', type: 'select-one' },
    { modalFieldId: 'name', type: 'text' },
    { modalFieldId: 'surname', type: 'text' },
    { modalFieldId: 'nationalnumber', type: 'text' },
    { modalFieldId: 'text_mail', type: 'text' }
    
];

var configPatient = [
    { modalFieldId: 'patient_name', type: 'text' },
    { modalFieldId: 'patient_surname', type: 'text' },
    { modalFieldId: 'patient_dni', type: 'text' },
    { modalFieldId: 'patient_gender', type: 'select-one' },
    { modalFieldId: 'patient_birthdate', type: 'date' },
    { modalFieldId: 'patient_phone', type: 'text' },
    { modalFieldId: 'patient_email', type: 'email' },
    { modalFieldId: 'patient_cuil', type: 'text' },
    { modalFieldId: 'patient_insurance_number', type: 'text' },
    { modalFieldId: 'patient_username', type: 'text' }
];

var configMedSol = [
    { modalFieldId: 'description', type: 'text' },
    { modalFieldId: 'phone', type: 'text' },
    { modalFieldId: 'mail', type: 'text' },
    { modalFieldId: 'notes', type: 'text' },
];

var configDias = [
    { modalFieldId: 'dia_ag', type: 'number' },
    { modalFieldId: 'hora_inicio_dia', type: 'text' },
    { modalFieldId: 'hora_final_dia', type: 'text' },
    { modalFieldId: 'n_slots', type: 'number' },
    { modalFieldId: 'lugares_x_slots', type: 'number' },
    
];

var configDiasEquipo = [
    { modalFieldId: 'day', type: 'select-one' },
    { modalFieldId: 'timefrom', type: 'select-one' },
    { modalFieldId: 'timeto', type: 'select-one' }
];

var configCode = [
    { modalFieldId: 'ministerial_code', type: 'text' },
    { modalFieldId: 'Description_code', type: 'text' },
    { modalFieldId: 'group_code', type: 'select-one' },
    { modalFieldId: 'bodypart_code', type: 'select-one' },
    { modalFieldId: 'modality_code', type: 'select-one' },
    { modalFieldId: 'rvu_code', type: 'text' },
    { modalFieldId: 'nofviews_code', type: 'text' }
];

var configMach = [
    { modalFieldId: 'Description_mach', type: 'text' },      // 1. Descripción (columna 1)
    { modalFieldId: 'AETitle', type: 'text' },               // 2. AETitle (columna 2)
    { modalFieldId: 'Ext_code_equip', type: 'text' },        // 3. Codigo Externo (columna 3)
    { modalFieldId: 's_moda', type: 'select-one' },          // 4. Modalidad (columna 4)
    { modalFieldId: 'equip_ip', type: 'text' },              // 5. IP (columna 5)
    { modalFieldId: 'equip_brand', type: 'text' },           // 6. Marca (columna 6)
    { modalFieldId: 'equip_model', type: 'text' },           // 7. Modelo (columna 7)
    { modalFieldId: 'equip_sn', type: 'text' },              // 8. N.Serie (columna 8)
    { modalFieldId: 'IsAc_mach', type: 'checkbox' }          // 9. Activo (columna 9)
];

var configRoom = [
    { modalFieldId: 'Description_room', type: 'text' },
    
    { modalFieldId: 'IsAc_room', type: 'checkbox' },
    { modalFieldId: 'ExtCode_room', type: 'text' },
];

var configFacility = [
    { modalFieldId: 'name_facility', type: 'text' },
    { modalFieldId: 'code_facility', type: 'text' },
    { modalFieldId: 'email_facility', type: 'text' },
    { modalFieldId: 'contact_person_facility', type: 'text' },
    { modalFieldId: 'status_facility', type: 'select-one' }
];

var configLocation = [
    { modalFieldId: 'name_location', type: 'text' },
    { modalFieldId: 'code_location', type: 'text' },
    { modalFieldId: 'facility_location', type: 'select-one' },
    { modalFieldId: 'patientdomain_location', type: 'text' },
    { modalFieldId: 'email_location', type: 'text' },
    { modalFieldId: 'address_location', type: 'text' },
    { modalFieldId: 'phone_location', type: 'text' },
    { modalFieldId: 'has_logo', type: 'text' }
];

var configExamen = [
    { modalFieldId: 'Description_ex', type: 'text' },
    { modalFieldId: 's_cod_min', type: 'select-one' },
    { modalFieldId: 's_modality', type: 'select-one' },
    { modalFieldId: 'time_execution', type: 'text' },
    { modalFieldId: 'IsAc_ex', type: 'checkbox' },
    { modalFieldId: 'precio', type: 'text' }
];

var configAp = [
    { modalFieldId: 'Description_ap', type: 'text' },
];

var configMod = [
    { modalFieldId: 'Description_mod', type: 'text' },
    { modalFieldId: 'ext_code_mod', type: 'text' },
    { modalFieldId: 'IsMandatoryEquipmentChange', type: 'checkbox' }
];

var configGo = [
    { modalFieldId: 'Description', type: 'text' },
    { modalFieldId: 'IsEx', type: 'checkbox' },
    { modalFieldId: 'ps', type: 'checkbox' },
    { modalFieldId: 'delaydays', type: 'text' }
];

// Configuración específica para el modal_or
var configOr = [
    { modalFieldId: 'Description_o', type: 'text' },
    { modalFieldId: 's_go', type: 'select' },
    { modalFieldId: 'IsAc', type: 'checkbox' },
    { modalFieldId: 'AltCode_or', type: 'text' },
    { modalFieldId: 'PatientCD', type: 'checkbox' },
    { modalFieldId: 'IsEditingExaminationDisabled', type: 'checkbox' },
    { modalFieldId: 'PublicationWeb', type: 'checkbox' },
    { modalFieldId: 'IsPriceListMandatory', type: 'checkbox' },
    { modalFieldId: 'IsChargeMandatory', type: 'checkbox' },
    { modalFieldId: 'IsOrderToNotify', type: 'checkbox' },
    
];

function RellenarTablaUsuarios(TablaId, route) {
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

                // Verificar si el usuario está inactivo (isactive = 0, que está en índice 7)
                if (item[7] === 0) {
                    row.classList.add('user-inactive');
                }

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

// Función genérica de filtrado de búsqueda

function ConfigurarFiltro(botonId, labelId, tablaId) {
    document.getElementById(botonId).addEventListener('click', function() {
        var filtro = document.getElementById(labelId).value.toLowerCase();
        var filas = document.getElementById(tablaId).getElementsByTagName('tbody')[0].getElementsByTagName('tr');

        for (var i = 0; i < filas.length; i++) {
            var descripcion = filas[i].getElementsByTagName('td')[0].innerText.toLowerCase();

            // Ocultar o mostrar la fila según el filtro
            filas[i].style.display = descripcion.includes(filtro) ? '' : 'none';
        }
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
            fila.classList.add('fila-seleccionada');            
            var botones = document.getElementsByClassName(botonesClass);
            
            // Verificar si es tabla de usuarios y si el usuario está inactivo
            var isUserTable = TablaId === 'tabla_usuarios';
            var isPatientTable = TablaId === 'tabla_pacientes';
            var isInactiveUser = fila.classList.contains('user-inactive');
            
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
            
            // Lógica específica para usuarios
            if (isUserTable) {
                var btnEliminar = document.getElementById('b_eliminar_user');
                var btnActivar = document.getElementById('b_activar_user');
                var btnEditar = document.getElementById('b_editar_user');
                var btnResetPassword = document.getElementById('b_reset_password');
                
                // Actualizar el botón dinámico según el estado del usuario
                if (btnEliminar && btnEliminar.updateForUserState) {
                    btnEliminar.updateForUserState(isInactiveUser);
                }
                
                // Ocultar el botón de activar separado ya que ahora usamos el dinámico
                if (btnActivar) btnActivar.style.display = 'none';
                
                // Manejar el botón de editar y reset password
                if (btnEditar) {
                    btnEditar.disabled = isInactiveUser;
                }
                
                if (btnResetPassword) {
                    btnResetPassword.disabled = isInactiveUser;
                }
            }
            
            // Lógica específica para pacientes
            if (isPatientTable) {
                var btnEliminar = document.getElementById('b_eliminar_patient');
                var btnActivar = document.getElementById('b_activar_patient');
                var btnEditar = document.getElementById('b_editar_patient');
                var btnResetPassword = document.getElementById('b_reset_password_patient');
                
                // Actualizar el botón dinámico según el estado del paciente
                if (btnEliminar && btnEliminar.updateForUserState) {
                    btnEliminar.updateForUserState(isInactiveUser);
                }
                
                // Ocultar el botón de activar separado ya que ahora usamos el dinámico
                if (btnActivar) btnActivar.style.display = 'none';
                
                // Manejar el botón de editar y reset password
                if (btnEditar) {
                    btnEditar.disabled = isInactiveUser;
                }
                
                if (btnResetPassword) {
                    btnResetPassword.disabled = isInactiveUser;
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

                // Verificar si es la tabla de usuarios y si el usuario está desactivado
                var isUserTable = TablaId === 'tabla_usuarios';
                var isInactive = false;
                
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
                        
                        // Si es la tabla de usuarios y es la última columna (isactive)
                        if (isUserTable && i === item.length - 1) {
                            isInactive = !item[i]; // Si isactive es 0, entonces está inactivo
                        }
                        
                        cell.appendChild(checkbox);
                    
                    } else {
                        // Para otras columnas, simplemente agrega el texto
                        cell.textContent = item[i];
                    }

                    row.appendChild(cell);
                }

                // Aplicar clase CSS para usuarios desactivados (sin estilos inline)
                if (isUserTable && isInactive) {
                    row.classList.add('user-inactive');
                }

                tbody_.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

function RellenarModalCheck(FormId, route) {
    var Form = document.getElementById(FormId);
    var hTitulo = document.getElementById('Titulo_dom');
    var titulo = hTitulo.textContent

    final_route = route + "?BU=" + titulo;
    fetch(final_route)
        .then(response => response.json())
        .then(data => {
            createCheckboxes(Form, data);
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

function createCheckboxes(form, data) {
    var checkboxesContainer = form.querySelector('.form-group .col-md-12');

    // Limpiar contenido existente en el contenedor
    checkboxesContainer.innerHTML = "";

    // Iterar sobre la data y agregar checkboxes
    data.forEach(item => {
        var [checkboxChecked, checkboxValue, checkboxLabel] = item;

        var checkboxDiv = document.createElement('div');
        checkboxDiv.classList.add('form-check');

        var checkboxInput = document.createElement('input');
        checkboxInput.classList.add('form-check-input');
        checkboxInput.type = 'checkbox';
        checkboxInput.value = checkboxValue;
        checkboxInput.name = 'seleccion_multiple[]';
        checkboxInput.checked = checkboxChecked;

        var checkboxLabelElement = document.createElement('label');
        checkboxLabelElement.classList.add('form-check-label');
        checkboxLabelElement.textContent = checkboxLabel;

        checkboxDiv.appendChild(checkboxInput);
        checkboxDiv.appendChild(checkboxLabelElement);

        checkboxesContainer.appendChild(checkboxDiv);
    });
}

//Me configura el modal para trabajar como para insertar uno nuevo.
function ConfigModalForm(FormId, TablaId, FormAction,modalId) {
    var Form = document.getElementById(FormId);
    
    // Validar que el formulario existe
    if (!Form) {
        console.warn(`ConfigModalForm: No se encontró el formulario con ID "${FormId}". Puede que el modal no se haya cargado aún.`);
        return;
    }
    
    Form.action = FormAction

    Form.addEventListener('submit', function (event) {
        event.preventDefault(); // Evitar la recarga de la página

        var formData = new FormData(Form);
        
        // Detectar si es una edición (tiene id de edición)
        var isEdit = false;
        var editIdField = null;
        
        // Buscar campos que indiquen edición (id_patient, id_user, etc.)
        for (var pair of formData.entries()) {
            if (pair[0].startsWith('id_') && pair[1]) {
                isEdit = true;
                editIdField = pair[0];
                break;
            }
        }

        // Realizar la solicitud AJAX para guardar en la base de datos
        fetch(Form.action, {
            method: 'POST',
            body: formData,
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Error en la solicitud');
                }
                return response.json(); // Aquí convertimos la respuesta a JSON
            })
            .then(data => {
                $(modalId).modal('hide');
                
                // Verificar si la operación fue exitosa
                if (data.status === 'OK') {
                    // Si es edición y es tabla de pacientes o usuarios, recargar la tabla
                    if (isEdit && (TablaId === 'tabla_pacientes' || TablaId === 'tabla_usuarios')) {
                        console.log('[DEBUG] Edición detectada, recargando tabla:', TablaId);
                        
                        // Determinar la ruta según la tabla
                        var reloadRoute = TablaId === 'tabla_pacientes' ? '/get_user_patients' : '/get_users';
                        
                        // Verificar si se deben incluir inactivos
                        var includeInactiveCheckbox = document.getElementById(
                            TablaId === 'tabla_pacientes' ? 'show_inactive_patients' : 'show_inactive_users'
                        );
                        
                        if (includeInactiveCheckbox && includeInactiveCheckbox.checked) {
                            reloadRoute += '?include_inactive=true';
                        }
                        
                        // Recargar la tabla
                        RellenarTablaUsuarios(TablaId, reloadRoute);
                        
                        // Mostrar notificación de éxito
                        showToast('¡Éxito!', data.message || 'Elemento actualizado correctamente', '/templates/includes/toast/toast_success.html');
                        return;
                    }
                    
                    // Código original para crear nueva fila (cuando no es edición)
                    // Crear una nueva fila
                    console.log(data)
                    var row = document.createElement('tr');

                    // Iterar sobre las propiedades en data.data
                    for (var prop in data.data) {
                        // console.log(prop)
                        if (data.data.hasOwnProperty(prop)) {

                            // Crear un nuevo td para cada propiedad
                            var td = document.createElement('td');
                            if ((data.data[prop]==0)||(data.data[prop]==1)){             
                                // Si es la última propiedad (columna activo), mostrar tick verde o X roja
                                var isLastProperty = Object.keys(data.data).indexOf(prop) === Object.keys(data.data).length - 1;
                                if (isLastProperty) {
                                    if (data.data[prop] === 1 || data.data[prop] === true) {
                                        td.innerHTML = '<i class="fas fa-check-circle text-success" title="Activo"></i>';
                                    } else {
                                        td.innerHTML = '<i class="fas fa-times-circle text-danger" title="Inactivo"></i>';
                                    }
                                } else {
                                    // Para otras columnas booleanas, usar checkbox
                                    const checkbox = document.createElement('input');
                                    checkbox.type = 'checkbox';
                                    checkbox.classList.add('form-check-input')
                                    
                                    checkbox.checked = data.data[prop]
                                    checkbox.style.opacity = 2;
                                    checkbox.disabled = true;
                                    
                                    td.appendChild(checkbox);
                                }
                            } else {
                                // Para otras columnas, simplemente agrega el texto
                                td.textContent = data.data[prop];
                            }
                            row.appendChild(td);
                        }
                    }

                    // Obtener la tabla y su cuerpo
                    var tabla = document.getElementById(TablaId);
                    var tbody_ = tabla.querySelector('tbody');

                    // Verificar si existe una fila de "mensaje vacío" y eliminarla
                    var filas = tbody_.querySelectorAll('tr');
                    for (var i = 0; i < filas.length; i++) {
                        var celdas = filas[i].querySelectorAll('td');
                        if (celdas.length === 1 && celdas[0].colSpan > 1) {
                            var texto = celdas[0].textContent.toLowerCase();
                            if (texto.includes('no se han configurado') || 
                                texto.includes('no tiene grupos') || 
                                texto.includes('este equipo no tiene') ||
                                texto.includes('no hay')) {
                                filas[i].remove();
                                break;
                            }
                        }
                    }

                    // Añadir la fila al cuerpo de la tabla
                    tbody_.appendChild(row);

                    // Eliminar la fila seleccionada
                    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
                    if (filaSeleccionada) {
                        filaSeleccionada.remove();
                    }
                    
                    // Mostrar notificación de éxito
                    showToast('¡Éxito!', data.message || 'Elemento agregado correctamente', '/templates/includes/toast/toast_success.html');
                } else {
                    // Mostrar notificación de error
                    showToast('Error', data.error || 'Error al procesar la solicitud', '/templates/includes/toast/toast_error.html');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                // Mostrar notificación de error de conexión
                showToast('Error', 'Error de conexión', '/templates/includes/toast/toast_error.html');
            });
    });
}

//Me configura el modal para trabajar como para insertar uno nuevo, pero recarga la página al finalizar
function ConfigModalFormWithReload(FormId, TablaId, FormAction, modalId, pillId) {
    var Form = document.getElementById(FormId);
    
    // Validar que el formulario existe
    if (!Form) {
        console.warn(`ConfigModalFormWithReload: No se encontró el formulario con ID "${FormId}". Puede que el modal no se haya cargado aún.`);
        return;
    }
    
    Form.action = FormAction

    Form.addEventListener('submit', function (event) {
        event.preventDefault(); // Evitar la recarga de la página

        // Realizar la solicitud AJAX para guardar en la base de datos
        fetch(Form.action, {
            method: 'POST',
            body: new FormData(Form),
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Error en la solicitud');
                }
                return response.json(); // Aquí convertimos la respuesta a JSON
            })
            .then(data => {
                // Cerrar el modal
                $(modalId).modal('hide');
                
                // Verificar si fue exitoso
                if (data.status === 'OK') {
                    // Guardar información del toast para mostrar después del reload
                    localStorage.setItem('toastAfterReload', JSON.stringify({
                        type: 'success',
                        title: '¡Éxito!',
                        message: data.message || 'Elemento agregado correctamente'
                    }));
                    
                    // Guardar en localStorage qué pill debe estar activo después del reload
                    if (pillId) {
                        localStorage.setItem('activePill', pillId);
                    }
                    
                    // Recargar la página inmediatamente
                    location.reload();
                } else {
                    // Si hay error, mostrar toast de error sin recargar
                    showToast('Error', data.error || 'Error al procesar la solicitud', '/templates/includes/toast/toast_error.html');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                // Mostrar toast de error de conexión sin recargar
                showToast('Error', 'Error de conexión', '/templates/includes/toast/toast_error.html');
            });
    });
}


//Me configura el modal para trabajar como para insertar uno nuevo.
function ConfigModalCheckForm(FormId, FormAction,modalId,buId_to_form,get_route,TableId) {
    var Form = document.getElementById(FormId);
    var div_id_proce= document.getElementById(buId_to_form);
    var hTitulo= document.getElementById("Titulo_dom");
    div_id_proce.value=hTitulo.textContent
    Form.action = FormAction
    Form.addEventListener('submit', function (event) {
        event.preventDefault(); // Evitar la recarga de la página

        // Realizar la solicitud AJAX para guardar en la base de datos
        fetch(Form.action, {
            method: 'POST',
            body: new FormData(Form),
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Error en la solicitud');
                }
                return response.json(); // Aquí convertimos la respuesta a JSON
            })
            .then(data => {
                route_get=get_route+`?BU=`+hTitulo.textContent
                RellenarTabla(TableId,route_get)
                $(modalId).modal('hide');
                // console.log(data)
            })
            .catch(error => {
                console.error('Error:', error);
            });
    });
}

function SetActivateUserButton(buttonId, TablaId, routeActivate){
    var boton = document.getElementById(buttonId);
    
    // Determinar si es tabla de pacientes o usuarios
    var isPatientTable = TablaId === 'tabla_pacientes';
    var entityName = isPatientTable ? 'paciente' : 'usuario';
    
    boton.addEventListener('click', function (event) {
        event.preventDefault();
        console.log("Activando " + entityName + " de la tabla: " + TablaId);
        
        // Obtener la fila seleccionada
        var tabla = document.getElementById(TablaId);
        var tbody_= tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
        
        if (filaSeleccionada) {
            var id = filaSeleccionada.dataset.id;
            
            fetch(routeActivate, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ id: id }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Remover la clase de inactivo
                    filaSeleccionada.classList.remove('user-inactive');
                    
                    // Obtener botones según el tipo de tabla
                    var btnActivar = document.getElementById(buttonId);
                    var btnEliminar = document.getElementById(isPatientTable ? 'b_eliminar_patient' : 'b_eliminar_user');
                    var btnEditar = document.getElementById(isPatientTable ? 'b_editar_patient' : 'b_editar_user');
                    
                    if (btnActivar) btnActivar.style.display = 'none';
                    if (btnEliminar) btnEliminar.style.display = 'inline-block';
                    if (btnEditar) btnEditar.disabled = false;
                    
                    // Mostrar mensaje de éxito
                    showSuccessToast('Éxito', entityName.charAt(0).toUpperCase() + entityName.slice(1) + ' activado correctamente');
                } else {
                    showErrorToast('Error', 'Error al activar ' + entityName + ': ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showErrorToast('Error', 'Error al activar ' + entityName);
            });
        } else {
            console.warn('No hay fila seleccionada.');
            showAlertToast('Advertencia', 'Por favor selecciona un ' + entityName);
        }
    });
}

function showConfirmationModal(title, message, onConfirm, onCancel) {
    // Crear el modal dinámicamente
    var modalId = 'confirmationModal_' + Date.now();
    var modalHtml = `
        <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}Label" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="${modalId}Label">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        ${message}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" id="${modalId}_cancel">Cancelar</button>
                        <button type="button" class="btn btn-primary" id="${modalId}_confirm">Confirmar</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Agregar modal al DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    var modal = document.getElementById(modalId);
    var bsModal = new bootstrap.Modal(modal);
    
    // Configurar eventos
    document.getElementById(modalId + '_confirm').addEventListener('click', function() {
        bsModal.hide();
        if (onConfirm) onConfirm();
    });
    
    document.getElementById(modalId + '_cancel').addEventListener('click', function() {
        bsModal.hide();
        if (onCancel) onCancel();
    });
    
    // Limpiar modal después de cerrar
    modal.addEventListener('hidden.bs.modal', function() {
        modal.remove();
    });
    
    // Mostrar modal
    bsModal.show();
}

function SetDynamicUserButton(buttonId, TablaId){
    var boton = document.getElementById(buttonId);
    
    // Determinar si es tabla de pacientes o usuarios
    var isPatientTable = TablaId === 'tabla_pacientes';
    var entityName = isPatientTable ? 'paciente' : 'usuario';
    
    // Función para actualizar el botón según el estado del usuario/paciente
    function updateButtonForUserState(isInactive) {
        var iconElement = boton.querySelector('i');
        
        if (isInactive) {
            // Inactivo: configurar para activar
            boton.classList.remove('btn-danger');
            boton.classList.add('btn-success');
            if (iconElement) {
                iconElement.className = 'fas fa-user-plus'; // Icono de activar
            }
            boton.title = 'Activar ' + entityName;
        } else {
            // Activo: configurar para desactivar
            boton.classList.remove('btn-success');
            boton.classList.add('btn-danger');
            if (iconElement) {
                iconElement.className = 'fas fa-user-times'; // Icono de desactivar
            }
            boton.title = 'Desactivar ' + entityName;
        }
    }
    
    boton.addEventListener('click', function (event) {
        event.preventDefault();
        
        // Obtener la fila seleccionada
        var tabla = document.getElementById(TablaId);
        var tbody_= tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
        
        if (filaSeleccionada) {
            var id = filaSeleccionada.dataset.id;
            var isInactive = filaSeleccionada.classList.contains('user-inactive');
            
            // Determinar acción y mensaje de confirmación
            var actionText = isInactive ? 'activar' : 'desactivar';
            var confirmTitle = isInactive ? 'Confirmar Activación' : 'Confirmar Desactivación';
            var confirmMessage = `¿Estás seguro de que deseas ${actionText} este ${entityName}?`;
            
            // Mostrar modal de confirmación
            showConfirmationModal(confirmTitle, confirmMessage, function() {
                // Función que se ejecuta al confirmar
                executeUserAction(filaSeleccionada, id, isInactive, TablaId);
            });
        } else {
            console.warn('No hay fila seleccionada.');
            showAlertToast('Advertencia', 'Por favor selecciona un ' + entityName);
        }
    });
    
    // Función separada para ejecutar la acción del usuario/paciente
    function executeUserAction(filaSeleccionada, id, isInactive, TablaId) {
        // Determinar endpoint según el tipo de tabla
        var activateEndpoint = isPatientTable ? '/activate_patient' : '/activate_user';
        var deactivateEndpoint = isPatientTable ? '/deactivate_patient' : '/deactivate_user';
        var endpoint = isInactive ? activateEndpoint : deactivateEndpoint;
        var action = isInactive ? 'Activando' : 'Desactivando';
        
        console.log(action + " " + entityName + " de la tabla: " + TablaId);
        
        fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ id: id }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (isInactive) {
                    // Se activó
                    filaSeleccionada.classList.remove('user-inactive');
                    
                    // Actualizar el checkbox de la columna "Activado"/"Estado" 
                    // Pacientes: columna 4 (Estado), Usuarios: columna 6 (Activado)
                    var checkboxCell = filaSeleccionada.getElementsByTagName('td')[isPatientTable ? 4 : 6];
                    if (checkboxCell) {
                        var checkbox = checkboxCell.querySelector('input[type="checkbox"]');
                        if (checkbox) {
                            checkbox.checked = true;
                        }
                    }
                    
                    showSuccessToast('Éxito', entityName.charAt(0).toUpperCase() + entityName.slice(1) + ' activado correctamente');
                } else {
                    // Se desactivó
                    filaSeleccionada.classList.add('user-inactive');
                    
                    // Actualizar el checkbox de la columna "Activado"/"Estado"
                    // Pacientes: columna 4 (Estado), Usuarios: columna 6 (Activado)
                    var checkboxCell = filaSeleccionada.getElementsByTagName('td')[isPatientTable ? 4 : 6];
                    if (checkboxCell) {
                        var checkbox = checkboxCell.querySelector('input[type="checkbox"]');
                        if (checkbox) {
                            checkbox.checked = false;
                        }
                    }
                    
                    showSuccessToast('Éxito', entityName.charAt(0).toUpperCase() + entityName.slice(1) + ' desactivado correctamente');
                }
                
                // Actualizar el botón para el nuevo estado
                updateButtonForUserState(!isInactive);
                
            } else {
                var errorMsg = isInactive ? 'Error al activar ' + entityName + ': ' : 'Error al desactivar ' + entityName + ': ';
                showErrorToast('Error', errorMsg + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            var errorMsg = isInactive ? 'Error al activar ' + entityName : 'Error al desactivar ' + entityName;
            showErrorToast('Error', errorMsg);
        });
    }
    
    // Exponer la función para que pueda ser llamada desde ConfigurarTabla
    boton.updateForUserState = updateButtonForUserState;
}

// Función para configurar el botón de resetear contraseña
function SetResetPasswordButton(buttonId, TablaId) {
    var boton = document.getElementById(buttonId);
    
    // Determinar si es tabla de pacientes o usuarios
    var isPatientTable = TablaId === 'tabla_pacientes';
    
    boton.addEventListener('click', function (event) {
        event.preventDefault();
        
        // Obtener la fila seleccionada
        var tabla = document.getElementById(TablaId);
        var tbody_ = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
        
        if (filaSeleccionada) {
            var id = filaSeleccionada.dataset.id;
            var celdas = filaSeleccionada.querySelectorAll('td');
            
            var username, nombre, apellido, fullname;
            
            if (isPatientTable) {
                // Para pacientes: Nombre, DNI, Fecha Nacimiento, Usuario, Estado, Última conexión
                // Estructura: índice 0=Nombre, 1=DNI, 2=Fecha Nacimiento, 3=Usuario, 4=Estado, 5=Última conexión
                fullname = celdas[0] ? celdas[0].textContent.trim() : ''; // Nombre completo
                username = celdas[3] ? celdas[3].textContent.trim() : ''; // Username del paciente
                
                // Separar nombre completo si viene junto (apellido nombre)
                var partes = fullname.split(' ');
                if (partes.length > 1) {
                    apellido = partes[0] || '';
                    nombre = partes.slice(1).join(' ') || '';
                } else {
                    nombre = fullname;
                    apellido = '';
                }
            } else {
                // Para usuarios: username, tipo, nombre, apellido, DNI, email, activado
                username = celdas[0] ? celdas[0].textContent.trim() : '';
                nombre = celdas[2] ? celdas[2].textContent.trim() : '';
                apellido = celdas[3] ? celdas[3].textContent.trim() : '';
                fullname = nombre + ' ' + apellido;
            }
            
            // Llenar los datos en el modal
            document.getElementById('reset_username').textContent = username;
            document.getElementById('reset_fullname').textContent = fullname;
            
            // Limpiar contraseña temporal anterior
            document.getElementById('temp_password').value = '';
            
            // Mostrar el modal
            var resetModal = new bootstrap.Modal(document.getElementById('modal_reset_password'));
            resetModal.show();
            
            // Configurar eventos del modal si no están configurados
            setupResetPasswordModal(id, isPatientTable);
            
        } else {
            console.warn('No hay fila seleccionada.');
            showAlertToast('Advertencia', isPatientTable ? 'Por favor selecciona un paciente' : 'Por favor selecciona un usuario');
        }
    });
}

// Función para configurar los eventos del modal de reset password
function setupResetPasswordModal(userId, isPatientTable) {
    // Configurar botón generar contraseña
    var generateBtn = document.getElementById('generate_temp_password');
    var tempPasswordInput = document.getElementById('temp_password');
    var confirmBtn = document.getElementById('confirm_reset_password');
    var copyBtn = document.getElementById('copy_temp_password');
    
    // Remover listeners anteriores para evitar duplicados
    var newGenerateBtn = generateBtn.cloneNode(true);
    generateBtn.parentNode.replaceChild(newGenerateBtn, generateBtn);
    
    var newConfirmBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
    
    var newCopyBtn = copyBtn.cloneNode(true);
    copyBtn.parentNode.replaceChild(newCopyBtn, copyBtn);
    
    // Configurar nuevo evento para generar contraseña
    newGenerateBtn.addEventListener('click', function() {
        fetch('/generate_temp_password')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                tempPasswordInput.value = data.temp_password;
                newConfirmBtn.disabled = false;
            } else {
                showErrorToast('Error', 'Error al generar contraseña temporal');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showErrorToast('Error', 'Error al generar contraseña temporal');
        });
    });
    
    // Configurar evento para copiar contraseña
    newCopyBtn.addEventListener('click', function() {
        if (tempPasswordInput.value) {
            navigator.clipboard.writeText(tempPasswordInput.value).then(function() {
                showSuccessToast('Éxito', 'Contraseña copiada al portapapeles');
            });
        }
    });
    
    // Configurar evento para confirmar reset
    newConfirmBtn.addEventListener('click', function() {
        var tempPassword = tempPasswordInput.value;
        
        if (!tempPassword) {
            showAlertToast('Advertencia', 'Debe generar una contraseña temporal primero');
            return;
        }
        
        // Confirmar acción
        showConfirmationModal(
            'Confirmar Reset de Contraseña',
            '¿Está seguro de que desea resetear la contraseña de este ' + (isPatientTable ? 'paciente' : 'usuario') + '?',
            function() {
                // Determinar el endpoint correcto según el tipo de tabla
                var resetEndpoint = isPatientTable ? '/reset_patient_password' : '/reset_user_password';
                
                // Realizar el reset
                fetch(resetEndpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        user_id: userId,
                        temp_password: tempPassword
                    }),
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showSuccessToast('Éxito', 'Contraseña reseteada correctamente');
                        // Cerrar modal
                        var resetModal = bootstrap.Modal.getInstance(document.getElementById('modal_reset_password'));
                        resetModal.hide();
                    } else {
                        showErrorToast('Error', 'Error al resetear contraseña: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showErrorToast('Error', 'Error al resetear contraseña');
                });
            }
        );
    });
}

// Función para configurar el botón de datos médicos
function SetMedicalDataButton(buttonId, TablaId) {
    var boton = document.getElementById(buttonId);
    
    boton.addEventListener('click', function (event) {
        event.preventDefault();
        
        // Obtener la fila seleccionada
        var tabla = document.getElementById(TablaId);
        var tbody_ = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
        
        if (filaSeleccionada) {
            var id = filaSeleccionada.dataset.id;
            var celdas = filaSeleccionada.querySelectorAll('td');
            
            // Obtener datos del usuario (username)
            var username = celdas[0] ? celdas[0].textContent.trim() : '';
            
            // Llenar los datos en el modal
            document.getElementById('user_id_medical').value = id;
            document.getElementById('medical_username').textContent = username;
            
            // Limpiar el formulario
            document.getElementById('form_medical_data').reset();
            document.getElementById('user_id_medical').value = id; // Mantener el ID después del reset
            document.getElementById('current_signature_section').style.display = 'none';
            
            // Cargar datos existentes
            loadMedicalData(id);
            
            // Mostrar el modal
            var medicalModal = new bootstrap.Modal(document.getElementById('modal_medical_data'));
            
            // Configurar eventos del modal cuando se abra completamente
            document.getElementById('modal_medical_data').addEventListener('shown.bs.modal', function () {
                setupMedicalDataModal();
            });
            
            medicalModal.show();
            
        } else {
            console.warn('No hay fila seleccionada.');
            showAlertToast('Advertencia', 'Por favor selecciona un usuario');
        }
    });
}

// Función para cargar datos médicos existentes
function loadMedicalData(userId) {
    fetch(`/get_medical_data?user_id=${userId}`)
    .then(response => response.json())
    .then(data => {
        if (data.success && data.data) {
            // Llenar campos del formulario
            document.getElementById('aclaracion_firma').value = data.data.aclaracion_firma || '';
            document.getElementById('matricula_nacional').value = data.data.matricula_nacional || '';
            document.getElementById('firma_habilitada').checked = data.data.firma_habilitada || false;
            
            // Mostrar firma actual si existe
            if (data.data.firma_digital) {
                document.getElementById('current_signature_section').style.display = 'block';
                // Usar directamente el nombre del archivo que viene de la BD
                document.getElementById('current_signature_img').src = `/media/firmas/${data.data.firma_digital}`;
            }
        }
    })
    .catch(error => {
        console.error('Error al cargar datos médicos:', error);
    });
}

// Función para configurar los eventos del modal de datos médicos
function setupMedicalDataModal() {
    var form = document.getElementById('form_medical_data');
       
    // Remover listeners anteriores para evitar duplicados en el formulario
    var newForm = form.cloneNode(true);
    form.parentNode.replaceChild(newForm, form);

    // Configurar evento de envío del formulario
    newForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        var formData = new FormData(newForm);
        
        fetch('/save_medical_data', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showSuccessToast('Éxito', 'Datos médicos guardados correctamente');
                // Cerrar modal
                var medicalModal = bootstrap.Modal.getInstance(document.getElementById('modal_medical_data'));
                medicalModal.hide();
            } else {
                showErrorToast('Error', 'Error al guardar datos médicos: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showErrorToast('Error', 'Error al guardar datos médicos');
        });
    });
    
    // Validar archivo de firma
    var fileInput = newForm.querySelector('#firma_digital');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            var file = e.target.files[0];
            if (file) {
                // Validar tamaño (máximo 2MB)
                if (file.size > 2 * 1024 * 1024) {
                    showErrorToast('Error', 'El archivo es demasiado grande (máximo 2MB)');
                    e.target.value = '';
                    return;
                }
                
                // Validar tipo
                var allowedTypes = ['image/png', 'image/jpeg', 'image/jpg'];
                if (!allowedTypes.includes(file.type)) {
                    showErrorToast('Error', 'Tipo de archivo no permitido (solo PNG, JPG, JPEG)');
                    e.target.value = '';
                    return;
                }
            }
        });
    }
    // Configurar eventos después de que el modal se haya mostrado completamente
    var modalElement = document.getElementById('modal_medical_data');
    if (modalElement) {
        console.log('Modal médico encontrado:', modalElement);
        modalElement.addEventListener('shown.bs.modal', function() {
            console.log('Modal médico completamente mostrado');
            
            // Buscar y configurar el botón de eliminar firma
            var removeButton = modalElement.querySelector('#remove_signature');
            console.log('Botón eliminar firma encontrado:', removeButton);
            
            if (removeButton) {
                // Remover listeners anteriores
                var newRemoveButton = removeButton.cloneNode(true);
                removeButton.parentNode.replaceChild(newRemoveButton, removeButton);
                
                // Añadir el nuevo listener
                newRemoveButton.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    console.log('Click en eliminar firma detectado');
                    
                    // Obtener el user_id del modal
                    var userIdInput = modalElement.querySelector('#user_id_modal');
                    if (!userIdInput || !userIdInput.value) {
                        console.error('No se encontró el user_id');
                        showErrorToast('Error', 'No se pudo identificar el usuario');
                        return;
                    }
                    
                    var userId = userIdInput.value;
                    console.log('User ID encontrado:', userId);
                    
                    // Mostrar confirmación
                    if (confirm('¿Está seguro de que desea eliminar la firma?')) {
                        console.log('Usuario confirmó eliminación');
                        
                        // Realizar la petición al servidor
                        fetch('/remove_signature', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({ user_id: userId })
                        })
                        .then(response => {
                            console.log('Respuesta del servidor:', response);
                            return response.json();
                        })
                        .then(data => {
                            console.log('Datos de respuesta:', data);
                            if (data.success) {
                                showSuccessToast('Éxito', 'Firma eliminada correctamente');
                                
                                // Ocultar la sección de firma actual
                                var currentSignature = modalElement.querySelector('#current_signature_section');
                                if (currentSignature) {
                                    currentSignature.style.display = 'none';
                                }
                                
                                // Mostrar el input de carga de nueva firma
                                var newSignatureSection = modalElement.querySelector('#new_signature_section');
                                if (newSignatureSection) {
                                    newSignatureSection.style.display = 'block';
                                }
                            } else {
                                showErrorToast('Error', 'Error al eliminar firma: ' + (data.message || 'Error desconocido'));
                            }
                        })
                        .catch(error => {
                            console.error('Error en la petición:', error);
                            showErrorToast('Error', 'Error al eliminar firma');
                        });
                    } else {
                        console.log('Usuario canceló la eliminación');
                    }
                });
                
                console.log('Listener de eliminar firma configurado correctamente');
            } else {
                console.warn('No se encontró el botón de eliminar firma');
            }
        });
    }
}

// Función específica para editar pacientes - carga datos desde el backend
function SetEditPatientButton(buttonId, FormModalId, modalId, tablaId, FormAction, IdId) {
    var boton = document.getElementById(buttonId);

    boton.addEventListener('click', function () {
        // Obtener la fila seleccionada
        var tabla = document.getElementById(tablaId);
        var tbody_ = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');

        if (filaSeleccionada) {
            var patientId = filaSeleccionada.dataset.id;
            
            // Hacer petición al backend para obtener los datos completos del paciente
            fetch(`/get_patient_data?patient_id=${patientId}`)
                .then(response => response.json())
                .then(result => {
                    if (result.status === 'OK') {
                        var data = result.data;
                        
                        // Obtener el formulario
                        var Form = document.getElementById(FormModalId);
                        Form.action = FormAction;
                        
                        // Llenar el campo oculto con el ID del paciente
                        document.getElementById(IdId).value = data.patient_id;
                        
                        // Llenar los campos del modal con los datos del paciente
                        document.getElementById('patient_name').value = data.name || '';
                        document.getElementById('patient_surname').value = data.surname || '';
                        document.getElementById('patient_dni').value = data.nationalcode || '';
                        document.getElementById('patient_gender').value = data.sexcode || '';
                        document.getElementById('patient_birthdate').value = data.birthdate || '';
                        document.getElementById('patient_phone').value = data.phone || '';
                        document.getElementById('patient_email').value = data.email || '';
                        document.getElementById('patient_cuil').value = data.patientid || '';
                        document.getElementById('patient_insurance_number').value = ''; // Este campo no está en la BD actualmente
                        document.getElementById('patient_username').value = data.username || '';
                        
                        // Cambiar el título del modal
                        document.getElementById('patientModalLabel').textContent = 'Editar paciente';
                        
                        // Cambiar el botón de submit
                        var submitBtn = document.querySelector('#modal_patients .save-changes');
                        if (submitBtn) {
                            submitBtn.textContent = 'Guardar cambios';
                        }
                        
                        // Mostrar el modal
                        var modal = new bootstrap.Modal(document.getElementById(modalId));
                        modal.show();
                    } else {
                        showErrorToast('Error', result.message || 'Error al obtener datos del paciente');
                    }
                })
                .catch(error => {
                    console.error('Error al cargar datos del paciente:', error);
                    showErrorToast('Error', 'Error al cargar datos del paciente');
                });
        } else {
            console.warn('No hay fila seleccionada.');
            showAlertToast('Advertencia', 'Por favor selecciona un paciente');
        }
    });
}

// Esta funcion selecciona el boton para editar, sobre que formulario, la ruta, y debo pasarle además el arreglo con los campos internos en orden a los campos que aparecen en la fila.
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
                    // Para selects, buscar tanto por valor como por texto
                    var options = modalField.options;
                    var encontrado = false;
                    
                    // Primero buscar por value
                    for (var i = 0; i < options.length; i++) {
                        if (options[i].value === valores[index]) {
                            options[i].selected = true;
                            encontrado = true;
                            break;
                        }
                    }
                    
                    // Si no se encontró por value, buscar por text
                    if (!encontrado) {
                        for (var i = 0; i < options.length; i++) {
                            if (options[i].text === valores[index]) {
                                options[i].selected = true;
                                break;
                            }
                        }
                    }
                } else {
                    modalField.value = valores[index];
                }

                if (modalField.classList.contains('dp')) {
                    
                    var dateString = valores[index];
                    var dateObject = moment(dateString, 'DD-MM-YYYY').toDate();
                    
                    $(modalField).datetimepicker({
                        format: 'DD-MM-YYYY', // Configura el formato de fecha deseado
                        showClear: true,
                        defaultDate: dateObject
                    });
    
                };
            });

            // Mostrar el modal
            var modal = new bootstrap.Modal(document.getElementById(modalId));
            modal.show();
        } else {
            console.warn('No hay fila seleccionada.');
        }
    });
}

function setNewButton(botonId, modalId, FormId, FormAction) {
    var b_nuevo = document.getElementById(botonId);

    b_nuevo.addEventListener('click', function (event) {
        
        // Evitar la propagación del evento para que no afecte al cierre de la modal
        event.stopPropagation();

        // Obtener el formulario y la modal
        var Form = document.getElementById(FormId);
        
        // Asignar la acción del formulario directamente
        Form.action = FormAction;
        console.log(Form)
        // Limpiar los campos del formulario
        var formElements = Form.elements;
        for (var i = 0; i < formElements.length; i++) {
            var element = formElements[i];
            // Verificar si la clase "not_delete" está presente
            if (element.type !== 'submit' && element.type !== 'button' && !element.classList.contains('not_delete')) {
                if (element.type === 'checkbox' || element.type === 'radio') {
                    element.checked = false;
                } else {
                    element.value = '';
                }
            }
        }
    });
}

function MostrarCardTableDerivada(CardId, routeGet, PrimaryTable, SecondaryTable, TituloId, IdFila) {
    var tabla = document.getElementById(PrimaryTable);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');

    if (filaSeleccionada) {
        var primeraCelda = filaSeleccionada.querySelector('td:first-child');
        var AgendaName = primeraCelda.innerText;
    } else {
        console.warn('No hay fila seleccionada.');
    }

    var Titulo = document.getElementById(TituloId);
    Titulo.textContent = AgendaName;

    var idAgendaInput = document.getElementById(IdFila);
    idAgendaInput.value = Titulo.textContent;

    route = routeGet + "?agenda=" + AgendaName;

    var tabla = document.getElementById(SecondaryTable);
    var tbody_ = tabla.querySelector('tbody');

    fetch(route)
        .then(response => response.json())
        .then(data => {
            tbody_.innerHTML = '';

            data.forEach(function (item) {
                var row = document.createElement('tr');
                row.dataset.id = item[0];

                for (var i = 1; i < item.length; i++) {
                    var cell = document.createElement('td');
                    cell.textContent = item[i];
                    row.appendChild(cell);
                }

                tbody_.appendChild(row);
            });

            // Coloca aquí el código que depende de la respuesta de fetch
            var Card = document.getElementById(CardId);
            Card.classList.remove('hidden');
        })
        .catch(error => {
            console.error('Error:', error);
        });
}


function VerDominio(PrimaryTable,cardBusqueda,CardTabla,TablaAhoraVis,TituloId){
    var card_busqueda_bu = document.getElementById(cardBusqueda);
    card_busqueda_bu.classList.add("hidden")
    var card= document.getElementById(CardTabla);
    card.classList.add("hidden")
    var card= document.getElementById(TablaAhoraVis);
    card.classList.remove("hidden")

    var tabla = document.getElementById(PrimaryTable);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');

    if (filaSeleccionada) {
        var primeraCelda = filaSeleccionada.querySelector('td:first-child');
        var nombre = primeraCelda.innerText;
    } else {
        console.warn('No hay fila seleccionada.');
    }
    var Titulo = document.getElementById(TituloId);
    Titulo.textContent = nombre;
    route_get=`/get_domain_procede?BU=`+nombre
    RellenarTabla('tabla-bu_proce',route_get)

    route_get=`/get_domain_equipment?BU=`+nombre
    RellenarTabla('tabla-bu_equip',route_get)

    route_get=`/get_domain_modalities?BU=`+nombre
    RellenarTabla('tabla-bu_modalities',route_get)


}


function DesplegarAgendaMed(TablaId){
    // Obtener la fila seleccionada
    var tabla = document.getElementById(TablaId);
    var tbody_= tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    if (filaSeleccionada) {
        var id = filaSeleccionada.dataset.id;
    }
    // Aca le coloco el id del medico en el modal
    document.getElementById('id_agenda_med').value = id;
    // Traer agenda
    fetch('/get_days_agenda', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id: id }),
    })
        .then(response => response.json())
        .then(data => {
            var tabla_agenda = document.getElementById('tabla_seg_ag');
            var tbody_ = tabla_agenda.querySelector('tbody');
            tbody_.innerHTML = '';
            data.forEach(function (item) {
                var row = document.createElement('tr');
                row.dataset.id = item.guid;
                var diaCell = document.createElement('td');
                diaCell.textContent = item.day;
                row.appendChild(diaCell);
                var inicioCell = document.createElement('td');
                inicioCell.textContent = item.timefrom;
                row.appendChild(inicioCell);
                var finalCell = document.createElement('td');
                finalCell.textContent = item.timeto;
                row.appendChild(finalCell);
                var inicioDiaCell = document.createElement('td');
                inicioDiaCell.textContent = item.initday;
                row.appendChild(inicioDiaCell);
                var finalDiaCell = document.createElement('td');
                finalDiaCell.textContent = item.finishday;
                row.appendChild(finalDiaCell);
                tbody_.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error:', error);
        });

    // Traer grupos del médico y llenar tabla grupos_del_medico
    fetch('/get_grupos_medico', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id: id }),
    })
        .then(response => response.json())
        .then(data => {
            var tabla_grupos = document.getElementById('grupos_del_medico');
            var tbody_grupos = tabla_grupos.querySelector('tbody');
            tbody_grupos.innerHTML = '';
            data.forEach(function (grupo) {
                var row = document.createElement('tr');
                row.dataset.id = grupo.id;
                var cell = document.createElement('td');
                cell.textContent = grupo.description;
                row.appendChild(cell);
                tbody_grupos.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

function DesplegarAgendaEquip(TablaId) {
    // Obtener la fila seleccionada
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    if (filaSeleccionada) {
        var id = filaSeleccionada.dataset.id;
    }
    // Colocar el id del equipo en el input correspondiente (ajusta el id si es necesario)
    document.getElementById('id_agenda_equip').value = id;
    // Traer agenda del equipo
    fetch('/get_days_agenda_equip', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id: id }),
    })
        .then(response => response.json())
        .then(data => {
            var tabla_agenda = document.getElementById('tabla_seg_ag_equip');
            var tbody_ = tabla_agenda.querySelector('tbody');
            tbody_.innerHTML = '';
            data.forEach(function (item) {
                var row = document.createElement('tr');
                row.dataset.id = item.guid;
                var diaCell = document.createElement('td');
                diaCell.textContent = item.day;
                row.appendChild(diaCell);
                var inicioCell = document.createElement('td');
                inicioCell.textContent = item.timefrom;
                row.appendChild(inicioCell);
                var finalCell = document.createElement('td');
                finalCell.textContent = item.timeto;
                row.appendChild(finalCell);
                tbody_.appendChild(row);
            });
            
            // Si no hay filas, mostrar mensaje informativo
            if (tbody_.children.length === 0) {
                var row = document.createElement('tr');
                var cell = document.createElement('td');
                cell.colSpan = 3;
                cell.textContent = 'No se han configurado días de agenda para este equipo';
                cell.style.textAlign = 'center';
                cell.style.fontStyle = 'italic';
                cell.style.color = '#6c757d';
                row.appendChild(cell);
                tbody_.appendChild(row);
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });

    // Traer grupos del equipo y llenar tabla grupos_del_equipo
    fetch('/get_equipment_studygroup', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id: id }),
    })
        .then(response => response.json())
        .then(data => {
            var tabla_grupos = document.getElementById('grupos_del_equipo');
            var tbody_grupos = tabla_grupos.querySelector('tbody');
            tbody_grupos.innerHTML = '';
            data.forEach(function (grupo) {
                var row = document.createElement('tr');
                row.dataset.id = grupo.id;
                var cell = document.createElement('td');
                cell.textContent = grupo.description;
                row.appendChild(cell);
                tbody_grupos.appendChild(row);
            });
            
            // Si no hay filas, mostrar mensaje informativo
            if (tbody_grupos.children.length === 0) {
                var row = document.createElement('tr');
                var cell = document.createElement('td');
                cell.textContent = 'Este equipo no tiene grupos asignados';
                cell.style.textAlign = 'center';
                cell.style.fontStyle = 'italic';
                cell.style.color = '#6c757d';
                row.appendChild(cell);
                tbody_grupos.appendChild(row);
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

function ConfigurarTablaCheckBox(bAdd,FormId,TableId,route_getcheck,route_get_domain,route_update,ModalId,IdId){
    var b_ = document.getElementById(bAdd);
    var isConfigured_ = false;  // Variable de control

    b_.addEventListener('click', function(){    
        RellenarModalCheck(FormId,route_getcheck)
        if (!isConfigured_) {
            ConfigModalCheckForm(FormId, route_update,ModalId,IdId,route_get_domain,TableId)
            isConfigured_ = true;  // Marca como configurado después de ejecutar
        }
    })
}

function ConfigurarPestana(PillTab,TablaId,FormId,ModalId,get_route,add_route,update_route,delete_route,bNew,bEdit,bSearch,bDelete,lSearch,ClassFB,config,id){
    var bp_grupo = document.getElementById(PillTab);
    bp_grupo.addEventListener('click', RellenarTabla(TablaId,get_route))
    // ConfigurarFiltro(bSearch, lSearch, TablaId);
    ConfigFiltrarText(lSearch, TablaId,0)
    ConfigurarTabla(TablaId,ClassFB)//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    modal_hashtag='#'+ModalId
    ConfigModalForm(FormId,TablaId,add_route,modal_hashtag)// Aca modal tiene que ir con #adelante. Tengo que hacer la adaptación en la función esta
    SetDeleteButton(bDelete,TablaId,delete_route)
    SetEditButton(bEdit,FormId,ModalId,TablaId,update_route,config,id)
    setNewButton(bNew, ModalId, FormId, add_route)
}


document.addEventListener("DOMContentLoaded", function() {

    // Verificar si hay un pill que debe estar activo después del reload
    var activePill = localStorage.getItem('activePill');
    if (activePill) {
        // Activar el pill correspondiente
        var pillElement = document.getElementById(activePill);
        if (pillElement) {
            // Crear un evento click en el pill
            pillElement.click();
        }
        // Limpiar el localStorage
        localStorage.removeItem('activePill');
    }

    // Verificar si hay un toast que debe mostrarse después del reload
    var toastData = localStorage.getItem('toastAfterReload');
    if (toastData) {
        try {
            var toast = JSON.parse(toastData);
            // Esperar un momento para que la página esté completamente cargada
            setTimeout(function() {
                var toastFile = '/templates/includes/toast/toast_success.html';
                if (toast.type === 'error') {
                    toastFile = '/templates/includes/toast/toast_error.html';
                } else if (toast.type === 'alert') {
                    toastFile = '/templates/includes/toast/toast_alert.html';
                }
                showToast(toast.title, toast.message, toastFile);
            }, 500); // Esperar 500ms para que la página esté lista
        } catch (e) {
            console.error('Error al parsear toast data:', e);
        }
        // Limpiar el localStorage
        localStorage.removeItem('toastAfterReload');
    }

    // Al hacer clic en una fila de tabla_med_ag, ejecutar DesplegarAgendaMed y mostrar el id del médico
    var tablaMedAg = document.getElementById('tabla_med_ag');
    if (tablaMedAg) {
        var tbodyMedAg = tablaMedAg.querySelector('tbody');
        tbodyMedAg.addEventListener('click', function (event) {
            var fila = event.target.closest('tr');
            if (fila) {
                // Quitar selección previa
                var filas = tbodyMedAg.querySelectorAll('tr');
                for (var i = 0; i < filas.length; i++) {
                    filas[i].classList.remove('fila-seleccionada');
                }
                // Selecciona la fila y ejecuta la función
                fila.classList.add('fila-seleccionada');
                DesplegarAgendaMed('tabla_med_ag');
                var idMed = document.getElementById('id_agenda_med').value;
                console.log('id_agenda_med:', idMed);
            }
        });
    }

    // Al hacer clic en una fila de tabla-agendas, ejecutar DesplegarAgendaEquip y mostrar el id del equipo
    var tablaAgendas = document.getElementById('tabla-agendas');
    if (tablaAgendas) {
        var tbodyAgendas = tablaAgendas.querySelector('tbody');
        tbodyAgendas.addEventListener('click', function (event) {
            var fila = event.target.closest('tr');
            if (fila) {
                // Quitar selección previa
                var filas = tbodyAgendas.querySelectorAll('tr');
                for (var i = 0; i < filas.length; i++) {
                    filas[i].classList.remove('fila-seleccionada');
                }
                // Selecciona la fila y ejecuta la función
                fila.classList.add('fila-seleccionada');
                DesplegarAgendaEquip('tabla-agendas');
                var idEquip = document.getElementById('id_agenda_equip').value;
                console.log('id_agenda_equip:', idEquip);
            }
        });
    }

    



    // Configuraciones para la pestana de Codigos Ministeriales
    var bp_study_types = document.getElementById("pills-study-types-tab");
    bp_study_types.addEventListener('click', RellenarTabla('tabla-codigos',`/get_study_types`)) 
    // ConfigurarFiltro("boton-buscar-codigo", 'search_ministerial_code', 'tabla-codigos');
    ConfigFiltrarText('search_ministerial_code', 'tabla-codigos',0)
    ConfigurarTabla('tabla-codigos','botones_code')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)

    ConfigModalForm('Form_code','tabla-codigos',"/agregar_studytype","#modal_code")
    
    SetDeleteButton('b_eliminar_codigo','tabla-codigos','/eliminar_studytype')
    
    // Función personalizada para editar tipo de estudio
    var btn_editar_codigo = document.getElementById('b_editar_codigo');
    btn_editar_codigo.addEventListener('click', function () {
        var tabla = document.getElementById('tabla-codigos');
        var filaSeleccionada = tabla.querySelector('.fila-seleccionada');

        if (filaSeleccionada) {
            // Obtener el ID del tipo de estudio (primera columna oculta o atributo)
            var guid = filaSeleccionada.getAttribute('data-id') || filaSeleccionada.cells[0].innerText;
            
            // Obtener valores de la fila
            var celdas = filaSeleccionada.querySelectorAll('td');
            var valores = Array.from(celdas).map(celda => celda.innerText);
            
            // Guardar valores para después
            var codigo = valores[0];           // Código
            var descripcion = valores[1];      // Descripción
            var grupo = valores[2];            // Grupo (texto)
            var parte = valores[3];            // Parte del cuerpo (texto)
            var modalidad = valores[4];        // Modalidad (texto)
            var rvu = valores[5] || '';        // RVU
            var nofviews = valores[6] || '';   // Número de vistas
            
            // Cambiar action del formulario
            document.getElementById('Form_code').action = "/actualizar_studytype";
            
            // Primero rellenar los selectores
            Promise.all([
                new Promise((resolve) => {
                    RellenarSelect('group_code', 'Description', 'nextris.isstudytypegroup', grupo, false);
                    setTimeout(resolve, 100);
                }),
                new Promise((resolve) => {
                    RellenarSelect('bodypart_code', 'Description', 'nextris.IsAnatomicalPart', parte, false);
                    setTimeout(resolve, 100);
                }),
                new Promise((resolve) => {
                    RellenarSelect('modality_code', 'ExternalCode', 'nextris.IsModality', modalidad, false);
                    setTimeout(resolve, 100);
                })
            ]).then(() => {
                // Una vez que los selectores están llenos, asignar valores a los campos
                document.getElementById('id_code').value = guid;
                document.getElementById('ministerial_code').value = codigo;
                document.getElementById('Description_code').value = descripcion;
                document.getElementById('rvu_code').value = rvu;
                document.getElementById('nofviews_code').value = nofviews;
                
                // Los selectores ya deberían tener el valor correcto por el parámetro selectedValue
                // pero por si acaso, volvemos a seleccionar
                setTimeout(() => {
                    var selectGrupo = document.getElementById('group_code');
                    var selectParte = document.getElementById('bodypart_code');
                    var selectMod = document.getElementById('modality_code');
                    
                    // Buscar y seleccionar por texto
                    for (var i = 0; i < selectGrupo.options.length; i++) {
                        if (selectGrupo.options[i].text === grupo) {
                            selectGrupo.selectedIndex = i;
                            break;
                        }
                    }
                    
                    for (var i = 0; i < selectParte.options.length; i++) {
                        if (selectParte.options[i].text === parte) {
                            selectParte.selectedIndex = i;
                            break;
                        }
                    }
                    
                    for (var i = 0; i < selectMod.options.length; i++) {
                        if (selectMod.options[i].text === modalidad) {
                            selectMod.selectedIndex = i;
                            break;
                        }
                    }
                    
                    // Mostrar el modal
                    var modal = new bootstrap.Modal(document.getElementById('modal_code'));
                    modal.show();
                }, 200);
            });
        } else {
            console.warn('No hay fila seleccionada.');
        }
    });
    
    setNewButton('b_nuevo_codigo', 'modal_code', 'Form_code', "/agregar_studytype")
    
    // Rellenar los selects cuando se abre el modal para NUEVO tipo de estudio
    document.getElementById('b_nuevo_codigo').addEventListener('click', function () {
        // Limpiar el formulario
        document.getElementById('Form_code').reset();
        document.getElementById('id_code').value = '';
        document.getElementById('Form_code').action = "/agregar_studytype";
        
        // Rellenar select de grupos
        RellenarSelect('group_code', 'Description', 'nextris.isstudytypegroup', null, false);
        // Rellenar select de partes del cuerpo
        RellenarSelect('bodypart_code', 'Description', 'nextris.IsAnatomicalPart', null, false);
        // Rellenar select de modalidades (usando ExternalCode para que coincida con la tabla)
        RellenarSelect('modality_code', 'ExternalCode', 'nextris.IsModality', null, false);
    });


    // Configuraciones para la pestana de Modalidades/metodos
    var bp_grupo = document.getElementById("pills-methods-tab");
    bp_grupo.addEventListener('click', RellenarTabla('tabla-mod',`/get_modalities`))
    // ConfigurarFiltro("boton-buscar-mod", 'search_mod', 'tabla-mod');
    ConfigFiltrarText('search_mod', 'tabla-mod',0)
    ConfigurarTabla('tabla-mod','botones_mod')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_mod','tabla-mod',"/agregar_mod","#modal_mod")
    SetDeleteButton('b_eliminar_mod','tabla-mod','/eliminar_mod')
    SetEditButton("b_editar_mod",'Form_mod','modal_mod','tabla-mod',"/actualizar_mod",configMod,'id_mod')
    setNewButton('b_nuevo_mod', 'modal_mod', 'Form_mod', "/agregar_mod")

    // Configuraciones para la pestana de Anatomical Parts
    var bp_grupo = document.getElementById("pills-body-parts-tab");
    bp_grupo.addEventListener('click', RellenarTabla('tabla-ap',`/get_body_parts`))
    // ConfigurarFiltro("boton-buscar-ap", 'search_ap', 'tabla-ap');
    ConfigFiltrarText('search_ap', 'tabla-ap',0)
    ConfigurarTabla('tabla-ap','botones_ap')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_ap','tabla-ap',"/agregar_ap","#modal_ap")
    SetDeleteButton('b_eliminar_ap','tabla-ap','/eliminar_ap')
    SetEditButton("b_editar_ap",'Form_ap','modal_ap','tabla-ap',"/actualizar_ap",configAp,'id_ap')
    setNewButton('b_nueva_ap', 'modal_ap', 'Form_ap', "/agregar_ap")


    // Configuraciones para la pestana de Equipos
    var bp_grupo = document.getElementById("pills-machines-tab");
    bp_grupo.addEventListener('click', RellenarTabla('tabla-mach',`/get_mach`))
    // ConfigurarFiltro("boton-buscar-mach", 'search_mach', 'tabla-mach');
    ConfigFiltrarText('search_mach', 'tabla-mach',0)
    ConfigurarTabla('tabla-mach','botones_mach')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalFormWithReload('Form_mach','tabla-mach',"/agregar_mach","#modal_mach","pills-machines-tab")
    SetDeleteButton('b_eliminar_mach','tabla-mach','/eliminar_mach')
    SetEditButton("b_editar_mach",'Form_mach','modal_mach','tabla-mach',"/actualizar_mach",configMach,'id_mach')
    setNewButton('b_nuevo_mach', 'modal_mach', 'Form_mach', "/agregar_mach")
    setNewButton('b_nuevo_mach', 'modal_mach', 'Form_mach', "/agregar_mach")
    RellenarSelect("s_moda",'Description','nextris.IsModality')

    // ------------------------------------------------
    // // AGENDAS DE EQUIPOS
    // ------------------------------------------------
    var bp_grupo = document.getElementById("pills-agendas-tab");
    bp_grupo.addEventListener('click', RellenarTabla('tabla-agendas',`/get_equip_agenda`))
    // ConfigurarFiltro("boton-buscar-agenda", 'search_agenda', 'tabla-agendas');
    ConfigFiltrarText('search_agenda', 'tabla-agendas',0)
    ConfigurarTabla('tabla-agendas','botones_ag')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigurarTabla('tabla_seg_ag_equip','botones_ag2')
    SetDeleteButton('b_eliminar_dia_equip','tabla_seg_ag_equip','/eliminar_dia_agenda_equip')
    ConfigModalForm('Form_age','tabla_seg_ag_equip',"/agregar_dia_agenda_equip","#modal_age")
    SetEditButton("b_editar_dia_equip",'Form_age','modal_age','tabla_seg_ag_equip',"/actualizar_dia_agenda_equip",configDiasEquipo,'id_item_agenda')
    setNewButton('b_agregar_dia_equip', 'modal_age', 'Form_age', "/agregar_dia_agenda_equip")
    
    var bAgregarDiaAge = document.getElementById('b_agregar_dia_equip');
    if (bAgregarDiaAge) {
        bAgregarDiaAge.addEventListener('click', function() {
            console.log("Click en agregar día equipo"); 
            var idEquip = document.getElementById('id_agenda_equip') ? document.getElementById('id_agenda_equip').value : '';
            var formAge = document.getElementById('Form_age');
            if (formAge) {
                var inputIdAgendaEquip = formAge.querySelector('#id_agenda_equip');
                if (inputIdAgendaEquip) {
                    inputIdAgendaEquip.value = idEquip;
                }
            }
        });
    }

    var bAgregarGrupo = document.getElementById('b_agregar_grupo_equip');
    if (bAgregarGrupo) {
        bAgregarGrupo.addEventListener('click', function() {
            var idEquip = document.getElementById('id_agenda_equip') ? document.getElementById('id_agenda_equip').value : '';
            if (!idEquip) {
                alert('Seleccione un equipo primero.');
                return;
            }
            // Traer grupos no relacionados
            fetch('/get_grupos_no_relacionados_equip', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ id: idEquip }),
            })
            .then(response => response.json())
            .then(data => {
                var selectGrupos = document.getElementById('select_grupo_disponible');
                selectGrupos.innerHTML = '';
                data.forEach(function(grupo) {
                    var option = document.createElement('option');
                    option.value = grupo.id;
                    option.textContent = grupo.description;
                    selectGrupos.appendChild(option);
                });
                // Mostrar el modal
                var modal = new bootstrap.Modal(document.getElementById('modal_agregar_grupo_med'));
                modal.show();
            })
            .catch(error => {
                console.error('Error:', error);
            });
        });
    }

    var btnConfirmarAgregarGrupoEquip = document.getElementById('btn_confirmar_agregar_grupo_equipo');
    if (btnConfirmarAgregarGrupoEquip) {
        btnConfirmarAgregarGrupoEquip.addEventListener('click', function() {
            var idEquip = document.getElementById('id_agenda_equip') ? document.getElementById('id_agenda_equip').value : '';
            var selectGrupos = document.getElementById('select_grupo_disponible');
            var grupoId = selectGrupos ? selectGrupos.value : '';
            if (!idEquip || !grupoId) {
                alert('Seleccione un equipo y un grupo.');
                return;
            }
            fetch('/agregar_grupo_equipo', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ id_equipo: idEquip, id_grupo: grupoId }),
            })
            .then(response => response.json())
            .then(data => {
                // Cerrar modal y limpiar backdrop si queda
                var modal = bootstrap.Modal.getInstance(document.getElementById('modal_agregar_grupo_equip'));
                if (modal) modal.hide();
                // Eliminar backdrop manualmente si queda
                var backdrops = document.querySelectorAll('.modal-backdrop');
                backdrops.forEach(function(bd) { bd.parentNode.removeChild(bd); });
                document.body.classList.remove('modal-open');
                document.body.style = '';
                // Refrescar tabla de grupos del equipo
                fetch('/get_grupos_equipos', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ id: idEquip }),
                })
                .then(response => response.json())
                .then(data => {
                    var tabla_grupos = document.getElementById('grupos_del_equipo');
                    var tbody_grupos = tabla_grupos.querySelector('tbody');
                    tbody_grupos.innerHTML = '';
                    data.forEach(function (grupo) {
                        var row = document.createElement('tr');
                        row.dataset.id = grupo.id;
                        var cell = document.createElement('td');
                        cell.textContent = grupo.description;
                        row.appendChild(cell);
                        tbody_grupos.appendChild(row);
                    });
                });
            })
            .catch(error => {
                console.error('Error:', error);
            });
        });
    }

    ConfigurarTabla('grupos_del_equipo','botones_gde'); // Selección de fila y botones
    // Lógica para eliminar grupo del equipo
    var bEliminarGrupoEquip = document.getElementById('b_eliminar_grupo_equip');
    if (bEliminarGrupoEquip) {
        bEliminarGrupoEquip.addEventListener('click', function () {
            var tabla = document.getElementById('grupos_del_equipo');
            var tbody_ = tabla.querySelector('tbody');
            var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
            var idEquip = document.getElementById('id_agenda_equip') ? document.getElementById('id_agenda_equip').value : '';
            if (filaSeleccionada && idEquip) {
                var grupoId = filaSeleccionada.dataset.id;
                fetch('/eliminar_grupo_equip', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ equip_id: idEquip, grupo_id: grupoId }),
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        filaSeleccionada.remove();
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                });
            } else {
                alert('Seleccione un grupo y asegúrese de tener un equipo seleccionado.');
            }
        });
    }
    

    // ---------------------------------------------------------------------------

    // Configuraciones para la pestana de Usuarios
    var bp_grupo = document.getElementById("gestion_users");
    bp_grupo.addEventListener('click', RellenarTabla('tabla_usuarios',`/get_users_config`))
    RellenarSelect("s_type_of_user", 'Description', 'nextris.IsRole');
    // ConfigurarFiltro("boton-buscar-usuario", 'search_group_users', 'tabla_usuarios');
    ConfigFiltrarText('search_group_users', 'tabla_usuarios',0)
    ConfigurarTabla('tabla_usuarios','botones_user')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_user','tabla_usuarios',"/create_user","#modal_users")
    setNewButton('b_nuevo_user', 'modal_users', 'Form_user', "/create_user")
    SetDynamicUserButton('b_eliminar_user','tabla_usuarios')
    SetActivateUserButton('b_activar_user','tabla_usuarios','/activate_user')
    SetEditButton("b_editar_user",'Form_user','modal_users','tabla_usuarios',"/edit_user",configUser,'id_user')
    SetResetPasswordButton('b_reset_password', 'tabla_usuarios')
    SetMedicalDataButton('b_medical_data', 'tabla_usuarios')

    // Configurar checkbox para mostrar usuarios desactivados
    var showInactiveCheckbox = document.getElementById('show_inactive_users');
    if (showInactiveCheckbox) {
        showInactiveCheckbox.addEventListener('change', function() {
            var includeInactive = this.checked;
            var route = '/get_users_config';
            if (includeInactive) {
                route += '?include_inactive=true';
            }
            RellenarTablaUsuarios('tabla_usuarios', route);
        });
    }

    //------------------------------------------------------------------------------------

    var bp_patients = document.getElementById("gestion_patients");
    bp_patients.addEventListener('click', RellenarTabla('tabla_pacientes',`/get_user_patients`))
    ConfigFiltrarText('search_group_patients', 'tabla_pacientes',0)
    ConfigurarTabla('tabla_pacientes','botones_patient')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_patient','tabla_pacientes',"/create_patient","#modal_patients")
    setNewButton('b_nuevo_patient', 'modal_patients', 'Form_patient', "/create_patient")
    SetDynamicUserButton('b_eliminar_patient','tabla_pacientes')
    SetActivateUserButton('b_activar_patient','tabla_pacientes','/activate_patient')
    SetEditPatientButton("b_editar_patient",'Form_patient','modal_patients','tabla_pacientes',"/edit_patient",'id_patient')
    SetResetPasswordButton('b_reset_password_patient', 'tabla_pacientes')
    
    // Configurar checkbox para mostrar pacientes inactivos
    var showInactivePatientsCheckbox = document.getElementById('show_inactive_patients');
    if (showInactivePatientsCheckbox) {
        showInactivePatientsCheckbox.addEventListener('change', function() {
            var includeInactive = this.checked;
            var route = '/get_user_patients';
            if (includeInactive) {
                route += '?include_inactive=true';
            }
            RellenarTablaUsuarios('tabla_pacientes', route);
        });
    }

    // Configuraciones para la pestana de Medicos solicitantes
    var bp_grupo = document.getElementById("pills_med_request");
    bp_grupo.addEventListener('click', RellenarTabla('tabla_med_sol',`/get_med_sol`))
    // ConfigurarFiltro("boton_buscar_med_sol", 'label_med_sol', 'tabla_med_sol');
    ConfigFiltrarText('label_med_sol', 'tabla_med_sol',0)
    ConfigurarTabla('tabla_med_sol','botones_ms')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_med_sol','tabla_med_sol',"/agregar_med_sol","#modal_med_sol")
    setNewButton('b_nuevo_med_sol', 'modal_med_sol', 'Form_med_sol', "/agregar_med_sol")
    SetDeleteButton('b_eliminar_med_sol','tabla_med_sol','/eliminar_med_sol')
    SetEditButton("b_editar_med_sol",'Form_med_sol','modal_med_sol','tabla_med_sol',"/actualizar_med_sol",configMedSol,'id_ms')
    
    // ------------------------------------------------
    // // AGENDAS DE MEDICOS
    // ------------------------------------------------
    var bp_grupo = document.getElementById("pills_med_agenda");
    bp_grupo.addEventListener('click', RellenarTabla('tabla_med_ag',`/get_agenda_med`))
    ConfigurarTabla('tabla_med_ag','botones_va')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigurarTabla('tabla_seg_ag','botones_am')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_am','tabla_seg_ag',"/agregar_item","#modal_am")

    // Antes de abrir el modal, setear el valor de id_agenda_med en el input del formulario
    var bAgregarItem = document.getElementById('b_agregar_item');
    if (bAgregarItem) {
        bAgregarItem.addEventListener('click', function() {
            // Obtener el valor actual de id_agenda_med (set por selección de médico)
            var idMed = document.getElementById('id_agenda_med') ? document.getElementById('id_agenda_med').value : '';
            // Setear ese valor en el input oculto del formulario del modal de ítem de agenda
            var formAm = document.getElementById('Form_am');
            if (formAm) {
                var inputIdAgendaMed = formAm.querySelector('#id_agenda_med');
                if (inputIdAgendaMed) {
                    inputIdAgendaMed.value = idMed;
                }
            }
        });
    }
    setNewButton('b_agregar_item', 'modal_am', 'Form_am', "/agregar_item")
    SetDeleteButton('b_eliminar_item','tabla_seg_ag','/eliminar_item_agenda')
    SetEditButton("b_editar_item",'Form_am','modal_am','tabla_seg_ag',"/actualizar_item_agenda",configItemAgenda,'id_item_agenda')
    // Configuración para la tabla de grupos del médico
    ConfigurarTabla('grupos_del_medico','botones_ag'); // Selección de fila y botones

    // Botón para agregar grupo (el + de la card de abajo)
    var bAgregarGrupo = document.getElementById('b_agregar_grupo_med');
    if (bAgregarGrupo) {
        bAgregarGrupo.addEventListener('click', function() {
            var idMed = document.getElementById('id_agenda_med') ? document.getElementById('id_agenda_med').value : '';
            if (!idMed) {
                alert('Seleccione un médico primero.');
                return;
            }
            // Traer grupos no relacionados
            fetch('/get_grupos_no_relacionados', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ id: idMed }),
            })
            .then(response => response.json())
            .then(data => {
                var selectGrupos = document.getElementById('select_grupo_disponible');
                selectGrupos.innerHTML = '';
                data.forEach(function(grupo) {
                    var option = document.createElement('option');
                    option.value = grupo.id;
                    option.textContent = grupo.description;
                    selectGrupos.appendChild(option);
                });
                // Mostrar el modal
                var modal = new bootstrap.Modal(document.getElementById('modal_agregar_grupo_med'));
                modal.show();
            })
            .catch(error => {
                console.error('Error:', error);
            });
        });
    }

    // Lógica para guardar grupo al médico
    var btnConfirmarAgregarGrupo = document.getElementById('btn_confirmar_agregar_grupo');
    if (btnConfirmarAgregarGrupo) {
        btnConfirmarAgregarGrupo.addEventListener('click', function() {
            var idMed = document.getElementById('id_agenda_med') ? document.getElementById('id_agenda_med').value : '';
            var selectGrupos = document.getElementById('select_grupo_disponible');
            var grupoId = selectGrupos ? selectGrupos.value : '';
            if (!idMed || !grupoId) {
                alert('Seleccione un médico y un grupo.');
                return;
            }
            fetch('/agregar_grupo_medico', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ id_medico: idMed, id_grupo: grupoId }),
            })
            .then(response => response.json())
            .then(data => {
                // Cerrar modal y limpiar backdrop si queda
                var modal = bootstrap.Modal.getInstance(document.getElementById('modal_agregar_grupo_med'));
                if (modal) modal.hide();
                // Eliminar backdrop manualmente si queda
                var backdrops = document.querySelectorAll('.modal-backdrop');
                backdrops.forEach(function(bd) { bd.parentNode.removeChild(bd); });
                document.body.classList.remove('modal-open');
                document.body.style = '';
                // Refrescar tabla de grupos del médico
                fetch('/get_grupos_medico', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ id: idMed }),
                })
                .then(response => response.json())
                .then(data => {
                    var tabla_grupos = document.getElementById('grupos_del_medico');
                    var tbody_grupos = tabla_grupos.querySelector('tbody');
                    tbody_grupos.innerHTML = '';
                    data.forEach(function (grupo) {
                        var row = document.createElement('tr');
                        row.dataset.id = grupo.id;
                        var cell = document.createElement('td');
                        cell.textContent = grupo.description;
                        row.appendChild(cell);
                        tbody_grupos.appendChild(row);
                    });
                });
            })
            .catch(error => {
                console.error('Error:', error);
            });
        });
    }

    // ------------------------------------------------
    // // CONFIGURACIONES DE BACKEND
    // ------------------------------------------------

    fetch('/get_backend_config')
        .then(r => r.json())
        .then(data => {
            if(data.config) {
                document.getElementById('db_user').value = data.config.user || '';
                document.getElementById('db_password').value = data.config.password || '';
                document.getElementById('db_host').value = data.config.host || '';
                document.getElementById('db_port').value = data.config.port || '';
                document.getElementById('db_name').value = data.config.database || '';
            }
            document.getElementById('base_folder').value = data.BASE_FOLDER || '';
            document.getElementById('ip_server').value = data.IPSERVER || '';
        });

    // ------------------------------------------------
    // // FACILITIES
    // ------------------------------------------------
    var bp_facilities = document.getElementById("pills-facilities-tab");
    if (bp_facilities) {
        bp_facilities.addEventListener('click', function() {
            RellenarTabla('tabla-facility', '/get_facilities');
        });
    }
    
    // Configurar filtro de búsqueda para facilities
    ConfigFiltrarText('search_facility', 'tabla-facility');
    
    // Configurar selección de filas y botones
    ConfigurarTabla('tabla-facility', 'botones_facility');
    
    // Configurar modal y formulario
    ConfigModalForm('Form_facility','tabla-facility',"/agregar_facility","#modal_facility");
    
    // Configurar botones CRUD
    SetDeleteButton('b_eliminar_facility','tabla-facility','/eliminar_facility');
    SetEditButton("b_editar_facility",'Form_facility','modal_facility','tabla-facility',"/actualizar_facility",configFacility,'id_facility');
    setNewButton('b_nuevo_facility', 'modal_facility', 'Form_facility', "/agregar_facility");

    // ------------------------------------------------
    // // LOCATIONS
    // ------------------------------------------------
    var bp_locations = document.getElementById("pills-locations-tab");
    if (bp_locations) {
        bp_locations.addEventListener('click', function() {
            RellenarTabla('tabla-location', '/get_locations');
        });
    }
    
    // Configurar filtro de búsqueda para locations
    ConfigFiltrarText('search_location', 'tabla-location');
    
    // Configurar selección de filas y botones
    ConfigurarTabla('tabla-location', 'botones_location');
    
    // Configurar modal y formulario
    ConfigModalForm('Form_location','tabla-location',"/agregar_location","#modal_location");
    
    // Configurar botones CRUD
    SetDeleteButton('b_eliminar_location','tabla-location','/eliminar_location');
    
    // Configurar botón editar con lógica personalizada para cargar facilities
    var btn_editar_location = document.getElementById('b_editar_location');
    if (btn_editar_location) {
        btn_editar_location.addEventListener('click', function() {
            var tabla = document.getElementById('tabla-location');
            var tbody = tabla.querySelector('tbody');
            var filaSeleccionada = tbody.querySelector('.fila-seleccionada');
            
            if (filaSeleccionada) {
                var Form = document.getElementById('Form_location');
                Form.action = "/actualizar_location";
                
                // Obtener el ID de la fila
                var guid = filaSeleccionada.dataset.id;
                document.getElementById('id_location').value = guid;
                
                // Cargar facilities en el select primero
                RellenarSelect('facility_location', 'name', 'nextris.tbfacility', 'guid', false);
                
                // Obtener datos completos de la location desde el backend
                fetch('/get_location_data?location_id=' + guid)
                    .then(response => response.json())
                    .then(data => {
                        // Llenar los campos del formulario
                        document.getElementById('name_location').value = data.name || '';
                        document.getElementById('code_location').value = data.code || '';
                        document.getElementById('patientdomain_location').value = data.patientdomain || '';
                        document.getElementById('email_location').value = data.mail || '';
                        document.getElementById('address_location').value = data.address || '';
                        document.getElementById('phone_location').value = data.phone || '';
                        
                        // Esperar a que el select se cargue y seleccionar la facility por ID
                        setTimeout(function() {
                            var selectFacility = document.getElementById('facility_location');
                            if (data.facility_id) {
                                selectFacility.value = data.facility_id;
                            }
                            
                            // Mostrar el modal
                            var modal = new bootstrap.Modal(document.getElementById('modal_location'));
                            modal.show();
                        }, 300);
                    })
                    .catch(error => {
                        console.error('Error al cargar datos de location:', error);
                        alert('Error al cargar los datos de la location');
                    });
            }
        });
    }
    
    setNewButton('b_nuevo_location', 'modal_location', 'Form_location', "/agregar_location");
    
    // Cargar facilities en el select cuando se abre el modal de nueva location
    document.getElementById('b_nuevo_location').addEventListener('click', function() {
        RellenarSelect('facility_location', 'name', 'nextris.tbfacility', 'guid', false);
    });

    // Botón de ver/editar logo
    var btn_logo_location = document.getElementById('b_logo_location');
    if (btn_logo_location) {
        btn_logo_location.addEventListener('click', function() {
            var tabla = document.getElementById('tabla-location');
            var filaSeleccionada = tabla.querySelector('tr.table-active');
            
            if (filaSeleccionada) {
                var locationId = filaSeleccionada.dataset.id;
                
                // Obtener datos de la location incluyendo logo_path
                fetch(`/get_location_data?location_id=${locationId}`)
                    .then(response => response.json())
                    .then(data => {
                        // Establecer el ID en el formulario
                        document.getElementById('location_id_logo').value = locationId;
                        
                        // Actualizar título del modal con el nombre de la location
                        document.getElementById('modalLogoLocationLabel').textContent = `Logo de ${data.name}`;
                        
                        // Mostrar logo actual si existe
                        var logoPreview = document.getElementById('logo_preview');
                        var noLogoMessage = document.getElementById('no_logo_message');
                        
                        if (data.logo_path) {
                            logoPreview.src = data.logo_path;
                            logoPreview.style.display = 'block';
                            noLogoMessage.style.display = 'none';
                        } else {
                            logoPreview.style.display = 'none';
                            noLogoMessage.style.display = 'block';
                        }
                        
                        // Limpiar inputs
                        document.getElementById('logo_file').value = '';
                        document.getElementById('new_logo_preview').style.display = 'none';
                        document.getElementById('remove_logo').checked = false;
                        
                        // Mostrar el modal
                        var modal = new bootstrap.Modal(document.getElementById('modal_logo_location'));
                        modal.show();
                    })
                    .catch(error => {
                        console.error('Error al cargar datos de location:', error);
                        alert('Error al cargar los datos de la location');
                    });
            }
        });
    }

    // Botón para abrir selector de archivo de logo
    var btnLogoSelectLocation = document.getElementById('btn_logo_select_location');
    if (btnLogoSelectLocation) {
        btnLogoSelectLocation.addEventListener('click', function() {
            document.getElementById('logo_file').click();
        });
    }

    // Vista previa del nuevo archivo seleccionado
    var logoFileInput = document.getElementById('logo_file');
    if (logoFileInput) {
        logoFileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const preview = document.getElementById('new_logo_preview');
                    preview.src = e.target.result;
                    preview.style.display = 'block';
                }
                reader.readAsDataURL(file);
                // Desmarcar el checkbox de eliminar si se selecciona un archivo
                document.getElementById('remove_logo').checked = false;
            } else {
                document.getElementById('new_logo_preview').style.display = 'none';
            }
        });
    }

    // Si se marca eliminar, limpiar el input de archivo
    var removeLogoCheckbox = document.getElementById('remove_logo');
    if (removeLogoCheckbox) {
        removeLogoCheckbox.addEventListener('change', function(e) {
            if (e.target.checked) {
                document.getElementById('logo_file').value = '';
                document.getElementById('new_logo_preview').style.display = 'none';
            }
        });
    }

    // Manejar el envío del formulario de logo
    var formLogoLocation = document.getElementById('Form_logo_location');
    if (formLogoLocation) {
        formLogoLocation.addEventListener('submit', function(e) {
            e.preventDefault();
            
            var formData = new FormData(this);
            
            fetch('/actualizar_logo_location', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'OK') {
                    alert('Logo actualizado correctamente');
                    // Cerrar modal
                    var modal = bootstrap.Modal.getInstance(document.getElementById('modal_logo_location'));
                    modal.hide();
                    // Recargar la tabla
                    RellenarTabla('tabla-location', 'nextris.tblocation', configLocation);
                } else {
                    alert('Error: ' + (data.error || 'Error desconocido'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error al actualizar el logo');
            });
        });
    }
        
});
