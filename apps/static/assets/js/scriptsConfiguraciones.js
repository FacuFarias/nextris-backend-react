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

var configDias = [
    { modalFieldId: 'dia_ag', type: 'number' },
    { modalFieldId: 'hora_inicio_dia', type: 'text' },
    { modalFieldId: 'hora_final_dia', type: 'text' },
    { modalFieldId: 'n_slots', type: 'number' },
    { modalFieldId: 'lugares_x_slots', type: 'number' },
    
];

var configCode = [
    { modalFieldId: 'ministerial_code', type: 'text' },
    { modalFieldId: 'Description_code', type: 'text' },
    { modalFieldId: 'group_code', type: 'text' }
];

var configMach = [
    { modalFieldId: 'Description_mach', type: 'text' },
    { modalFieldId: 'AETitle', type: 'text' },
    { modalFieldId: 'Ext_code_equip', type: 'text' },

    { modalFieldId: 's_sala', type: 'select-one' },
    { modalFieldId: 's_moda', type: 'select-one' },
    { modalFieldId: 'IsAc_mach', type: 'checkbox' },

    { modalFieldId: 's_proc', type: 'select-one' },
    { modalFieldId: 'equip_ip', type: 'text' },
    { modalFieldId: 'equip_brand', type: 'text' },
    { modalFieldId: 'equip_model', type: 'text' },
    { modalFieldId: 'equip_sn', type: 'text' },
];

var configRoom = [
    { modalFieldId: 'Description_room', type: 'text' },
    
    { modalFieldId: 'IsAc_room', type: 'checkbox' },
    { modalFieldId: 'ExtCode_room', type: 'text' },
];

var configExamen = [
    { modalFieldId: 'Description_ex', type: 'text' },
    { modalFieldId: 's_cod_min', type: 'select-one' },
    { modalFieldId: 's_modality', type: 'select-one' },
    { modalFieldId: 'time_execution', type: 'text' },
    { modalFieldId: 'IsAc_ex', type: 'checkbox' }
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
                $(modalId).modal('hide');
                // Crear una nueva fila
                var row = document.createElement('tr');

                // Iterar sobre las propiedades en data.data
                for (var prop in data.data) {
                    console.log(prop)
                    if (data.data.hasOwnProperty(prop)) {

                        // Crear un nuevo td para cada propiedad
                        var td = document.createElement('td');
                        if ((data.data[prop]==0)||(data.data[prop]==1)){             
                            const checkbox = document.createElement('input');
                            checkbox.type = 'checkbox';
                            checkbox.classList.add('form-check-input')
                            
                            checkbox.checked = data.data[prop]
                            checkbox.style.opacity = 2;
                            checkbox.disabled = true;
                            
                            td.appendChild(checkbox);
                        
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

                // Añadir la fila al cuerpo de la tabla
                tbody_.appendChild(row);

                // Eliminar la fila seleccionada
                var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
                if (filaSeleccionada) {
                    filaSeleccionada.remove();
                }
            })
            .catch(error => {
                console.error('Error:', error);
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
                    // Encuentra la opción con el texto y selecciónala
                    var options = modalField.options;
                    for (var i = 0; i < options.length; i++) {
                        if (options[i].text === valores[index]) {
                            options[i].selected = true;
                            break; // Sal del bucle una vez que encuentres la opción
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

        // Limpiar los campos del formulario
        var formElements = Form.elements;
        for (var i = 0; i < formElements.length; i++) {
            var element = formElements[i];
            // Verificar si la clase "noborrar" está presente
            if (element.type !== 'submit' && element.type !== 'button' && !element.classList.contains('noborrar')) {
                if (element.type === 'checkbox' || element.type === 'radio') {
                    element.checked = false;
                } else {
                    element.value = '';
                }
            }
        }
    });
}


function RellenarSelect(SelectId,dNeeded,TableId){
    fetch('/rellenar_select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ dNeeded: dNeeded, TableId:TableId }),
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
    })
    .catch(error => {
        console.error('Error:', error);
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


document.addEventListener("DOMContentLoaded", function() {

    
    ConfigurarPestana('pills-group-origins-tab','tabla-grupos','grupoForm','modal_go',`/get_origins_group`,"/agregar_go","/actualizar_go",'/eliminar_grupo','b_nuevo_grupo',"b_editar_grupo",'boton-buscar-grupo','b_eliminar_grupo','label_group_origins','botones',configGo,'id_go')
    
    // Cada grupo de configuraciones tiene 4 rutas> las rutas `/get_origins_group`,"/agregar_go","/eliminar_", "/actualizar_go"
    // var bp_grupo = document.getElementById('pills-group-origins-tab');
    // bp_grupo.addEventListener('click', RellenarTabla('tabla-grupos',`/get_origins_group`))

    // ConfigurarFiltro('boton-buscar-grupo', 'label_group_origins', 'tabla-grupos');
    // ConfigurarTabla('tabla-grupos','botones')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    // ConfigModalForm('grupoForm','tabla-grupos',"/agregar_go","#modal_go")
    // SetDeleteButton('b_eliminar_grupo','tabla-grupos','/eliminar_grupo')
    // SetEditButton("b_editar_grupo",'grupoForm','modal_go','tabla-grupos',"/actualizar_go",configGo,'id_go')
    // setNewButton('b_nuevo_grupo', 'modal_go', 'grupoForm', "/agregar_go")


    // Configuraciones para la pestana de Procedencias
    var bp_grupo = document.getElementById('pills-origins-tab');
    bp_grupo.addEventListener('click', RellenarTabla('tabla-origenes',`/get_origins`))
    ConfigurarFiltro("boton-buscar-origen", 'label_origins', 'tabla-origenes');
    ConfigurarTabla('tabla-origenes','botones_or')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_origen','tabla-origenes',"/agregar_origen","#modal_or")
    SetDeleteButton('b_eliminar_origen','tabla-origenes','/eliminar_procedencia')
    SetEditButton("b_editar_origen",'Form_origen','modal_or','tabla-origenes',"/actualizar_origen",configOr,'id_origin')
    setNewButton('b_nuevo_origen', 'modal_or', 'Form_origen', "/agregar_origen")

    RellenarSelect("s_go",'Description','public.IsProvenanceGroup')
    
    function ConfigurarPestana(PillTab,TablaId,FormId,ModalId,get_route,add_route,update_route,delete_route,bNew,bEdit,bSearch,bDelete,lSearch,ClassFB,config,id){
        var bp_grupo = document.getElementById(PillTab);
        bp_grupo.addEventListener('click', RellenarTabla(TablaId,get_route))
        ConfigurarFiltro(bSearch, lSearch, TablaId);
        ConfigurarTabla(TablaId,ClassFB)//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
        modal_hashtag='#'+ModalId
        ConfigModalForm(FormId,TablaId,add_route,modal_hashtag)// Aca modal tiene que ir con #adelante. Tengo que hacer la adaptación en la función esta
        SetDeleteButton(bDelete,TablaId,delete_route)
        SetEditButton(bEdit,FormId,ModalId,TablaId,update_route,config,id)
        setNewButton(bNew, ModalId, FormId, add_route)
    }


    // Configuraciones para la pestana de Codigos Ministeriales
    var bp_grupo = document.getElementById("pills-ministerial-codes-tab");
    bp_grupo.addEventListener('click', RellenarTabla('tabla-codigos',`/get_ministerial_codes`)) 
    ConfigurarFiltro("boton-buscar-codigo", 'search_ministerial_code', 'tabla-codigos');
    ConfigurarTabla('tabla-codigos','botones_code')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)

    ConfigModalForm('Form_code','tabla-codigos',"/agregar_codigo","#modal_code")
    
    SetDeleteButton('b_eliminar_codigo','tabla-codigos','/eliminar_codigo')
    SetEditButton("b_editar_codigo",'Form_code','modal_code','tabla-codigos',"/actualizar_codigo",configCode,'id_code')
    setNewButton('b_nuevo_codigo', 'modal_code', 'Form_code', "/agregar_codigo")


    // Configuraciones para la pestana de Modalidades/metodos
    var bp_grupo = document.getElementById("pills-methods-tab");
    bp_grupo.addEventListener('click', RellenarTabla('tabla-mod',`/get_modalities`))
    ConfigurarFiltro("boton-buscar-mod", 'search_mod', 'tabla-mod');
    ConfigurarTabla('tabla-mod','botones_mod')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_mod','tabla-mod',"/agregar_mod","#modal_mod")
    SetDeleteButton('b_eliminar_mod','tabla-mod','/eliminar_mod')
    SetEditButton("b_editar_mod",'Form_mod','modal_mod','tabla-mod',"/actualizar_mod",configMod,'id_mod')
    setNewButton('b_nuevo_mod', 'modal_mod', 'Form_mod', "/agregar_mod")

    // Configuraciones para la pestana de Anatomical Parts
    var bp_grupo = document.getElementById("pills-body-parts-tab");
    bp_grupo.addEventListener('click', RellenarTabla('tabla-ap',`/get_body_parts`))
    ConfigurarFiltro("boton-buscar-ap", 'search_ap', 'tabla-ap');
    ConfigurarTabla('tabla-ap','botones_ap')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_ap','tabla-ap',"/agregar_ap","#modal_ap")
    SetDeleteButton('b_eliminar_ap','tabla-ap','/eliminar_ap')
    SetEditButton("b_editar_ap",'Form_ap','modal_ap','tabla-ap',"/actualizar_ap",configAp,'id_ap')
    setNewButton('b_nueva_ap', 'modal_ap', 'Form_ap', "/agregar_ap")


     // Configuraciones para la pestana de Examenes
     var bp_grupo = document.getElementById("pills-body-parts-tab");
     bp_grupo.addEventListener('click', RellenarTabla('tabla-examen',`/get_exams`))
    ConfigurarFiltro("boton-buscar-examen", 'search_exam', 'tabla-examen');
    ConfigurarTabla('tabla-examen','botones_ex')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_exams','tabla-examen',"/agregar_examen","#modal_exam")
    SetDeleteButton('b_eliminar_examen','tabla-examen','/eliminar_examen')
    SetEditButton("b_editar_examen",'Form_exams','modal_exam','tabla-examen',"/actualizar_examen",configExamen,'id_examen')
    setNewButton('b_nuevo_examen', 'modal_exam', 'modal_exam', "/agregar_examen")

    RellenarSelect("s_cod_min",'Description','public.IsMinisterialCode')
    RellenarSelect("s_modality",'Description','public.IsModality')


    var bp_grupo = document.getElementById("pills-rooms-tab");
     bp_grupo.addEventListener('click', RellenarTabla('tabla-salas',`/get_rooms`))
    ConfigurarFiltro("boton-buscar-room", 'search_room', 'tabla-salas');
    ConfigurarTabla('tabla-salas','botones_room')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_rooms','tabla-salas',"/agregar_room","#modal_rooms")
    SetDeleteButton('b_eliminar_room','tabla-salas','/eliminar_room')
    SetEditButton("b_editar_room",'Form_rooms','modal_rooms','tabla-salas',"/actualizar_room",configRoom,'id_room')
    setNewButton('b_nuevo_room', 'modal_rooms', 'Form_rooms', "/agregar_room")

// Configuraciones para la pestana de Equipos
    var bp_grupo = document.getElementById("pills-machines-tab");
    bp_grupo.addEventListener('click', RellenarTabla('tabla-mach',`/get_mach`))
    ConfigurarFiltro("boton-buscar-mach", 'search_mach', 'tabla-mach');
    ConfigurarTabla('tabla-mach','botones_mach')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_mach','tabla-mach',"/agregar_mach","#modal_mach")
    SetDeleteButton('b_eliminar_mach','tabla-mach','/eliminar_mach')
    SetEditButton("b_editar_mach",'Form_mach','modal_mach','tabla-mach',"/actualizar_mach",configMach,'id_mach')
    setNewButton('b_nuevo_mach', 'modal_mach', 'Form_mach', "/agregar_mach")

    RellenarSelect("s_sala",'Description','public.IsRoom')
    RellenarSelect("s_proc",'Description','public.IsProvenance')
    RellenarSelect("s_moda",'Description','public.IsModality')

    // Configuraciones para la pestana de Agendas
    var bp_grupo = document.getElementById("pills-agendas-tab");
    bp_grupo.addEventListener('click', RellenarTabla('tabla-agendas',`/get_agendas`))
    ConfigurarFiltro("boton-buscar-agenda", 'search_agenda', 'tabla-agendas');
    ConfigurarTabla('tabla-agendas','botones_ag')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_agenda','tabla-agendas',"/agregar_agendas","#modal_agenda")
    SetDeleteButton('b_eliminar_agenda','tabla-agendas','/eliminar_agenda')
    SetEditButton("b_editar_agenda",'Form_agenda','modal_agenda','tabla-agendas',"/actualizar_agenda",configAgenda,'id_agenda')
    setNewButton('b_nueva_agenda', 'modal_agenda', 'Form_agenda', "/agregar_agendas")

    RellenarSelect("s_equip",'Description','public.IsEquipment')


    // Configuraciones para dias por agenda
    var bp_grupo = document.getElementById("b_dias_horas");
    bp_grupo.addEventListener('click', function() {
        MostrarCardTableDerivada('card_dias','get_days','tabla-agendas',"tabla-dias","titulo_dias","id_agenda_");
        ConfigurarTabla('tabla-dias','botones_dia');
        ConfigModalForm('Form_dia','tabla-dias',"/agregar_dia","#modal_dias")
        setNewButton('b_agregar_dia', 'modal_dias', 'Form_dia', "/agregar_dia")
        SetEditButton("b_editar_dia",'Form_dia','modal_dias','tabla-dias',"/actualizar_dia",configDias,'id_dia')
        SetDeleteButton('b_eliminar_dia','tabla-dias','/eliminar_dia')
        
    });


    // Configuraciones para la pestana de Agendas
    var bp_grupo = document.getElementById("pills-agendas-tab");
    bp_grupo.addEventListener('click', RellenarTabla('tabla-bu',`/get_business_units`))
    ConfigurarFiltro("boton-buscar-bu", 'search_bu', 'tabla-bu');
    ConfigurarTabla('tabla-bu','botones_bu')//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)
    ConfigModalForm('Form_bu','tabla-bu',"/agregar_business_units","#modal_bu")
    SetDeleteButton('b_eliminar_bu','tabla-bu','/eliminar_bu')
    SetEditButton("b_editar_bu",'Form_bu','modal_bu','tabla-bu',"/actualizar_business_units",configBU,'id_bu')
    setNewButton('b_nuevo_bu', 'modal_bu', 'Form_bu', "/agregar_business_units")

    var b_dominio = document.getElementById("b_dominio_bu");

    b_dominio.addEventListener('click', function(){
        VerDominio("tabla-bu","card_busqueda_bu","card_tabla_bu","card_tabla_dominios","Titulo_dom")
    })


    ConfigurarTablaCheckBox("b_agregar_procede",'Form_bu_pro',"tabla-bu_proce",`/get_check_procede`,"/get_domain_procede",`/update_procede`,'#modal_bu_pro',"name_bu")

    ConfigurarTablaCheckBox("b_agregar_equip",'Form_bu_equip',"tabla-bu_equip",'/get_check_equip',"/get_domain_equipment",'/update_equip','#modal_bu_equip',"name_bu_equip")

    ConfigurarTablaCheckBox("b_agregar_mod",'Form_bu_mod',"tabla-bu_modalities",`/get_check_mod`,"/get_domain_modalities",`/update_mod`,'#modal_bu_mod',"name_bu_mod")
    

    var b_back = document.getElementById("b_volver_bu");
    b_back.addEventListener('click', function(){
        var card_busqueda_bu = document.getElementById("card_busqueda_bu");
        card_busqueda_bu.classList.remove("hidden")
        var card= document.getElementById("card_tabla_bu");
        card.classList.remove("hidden")
        var card= document.getElementById("card_tabla_dominios");
        card.classList.add("hidden")
    })

});
