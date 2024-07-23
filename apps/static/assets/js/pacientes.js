

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

function ConfigDefaultModal(FormId,route_action,ModalId,TablaId){
    var form_modal_p = document.getElementById(FormId);
    form_modal_p.action=route_action
    console.log(form_modal_p.action)
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
            // En este else entra cuando form_modal_p.action==='http://127.0.0.1:5000/agregar_pacientes'
            // Crear una nueva fila
            var nuevaFila = document.createElement('tr');

            // Especificar el orden deseado de las propiedades
            var keys = ['p_name', 'p_surname', 'p_dni', 'sex', 'fecha_nacimiento', 'telefono', 'mail', 'p_healthcard'];

            // Agregar celdas a la nueva fila con los datos recibidos en el orden especificado
            keys.forEach(function(key) {
                var nuevaCelda = document.createElement('td');
                nuevaCelda.innerText = data[key];
                nuevaFila.appendChild(nuevaCelda);
            });

            // Agregar la nueva fila al tbody
            tbody_.appendChild(nuevaFila);
        }
        // console.log(data)
        $(ModalId).modal('hide');
        
    })
    .catch(error => {
        console.error('Error:', error);
        });
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



document.addEventListener("DOMContentLoaded", function() {
    // configuracion de busqueda y llenado de tabla
    RellenarTabla('tabla-pacientes',`/get_patients`)

    var myForm = document.querySelector('.my-form');
    
    myForm.addEventListener('submit', function(event) {
        // Evitar el envío predeterminado del formulario
        event.preventDefault();

        // Obtener los valores del formulario
        var name = document.getElementById("name").value;
        var surname = document.getElementById("surname").value;
        var documento = document.getElementById("documento").value;
        var Telefono = document.getElementById("Telefono").value;
        var buscar_mail = document.getElementById("buscar_mail").value;
        var sex = document.getElementById("sex").value;
        var fecha_nacimiento = document.getElementById("fecha_nac").value;
        var tarjeta_sanitaria = document.getElementById("tarjeta_sanitaria").value;
        var idP = document.getElementById("idP").value;

        // Construir el cuerpo de la solicitud
        var requestBody = {
            name: name,
            surname: surname,
            documento: documento,
            Telefono: Telefono,
            buscar_mail: buscar_mail,
            sex: sex,
            fecha_nacimiento: fecha_nacimiento,
            tarjeta_sanitaria: tarjeta_sanitaria,
            idP: idP
        };

        // Realizar la solicitud HTTP usando fetch
        fetch('/buscar_pacientes', {
            method: 'POST',  // Puedes cambiarlo a 'POST' si prefieres enviar datos en el cuerpo
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        })
        .then(response => response.json())
        .then(data => {
            var tablaPacientes = document.getElementById("tabla-pacientes");
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

    ConfigurarTabla('tabla-pacientes','botones_sp')

    // Configuro agregar paciente
    ConfigDefaultModal('Form_ag','/agregar_pacientes','#modal_np',"tabla-pacientes")
    SetEditButton('editar-paciente', "Form_ag", "modal_np", "tabla-pacientes", '/editar_paciente', configNP,'id_np')
    SetDeleteButton('eliminar-paciente','tabla-pacientes','/eliminar_paciente')



    
    
});
