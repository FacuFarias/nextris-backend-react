function ConfigDefaultModal(FormId, route_action, ModalId) {
    var form_modal_p = document.getElementById(FormId);
    form_modal_p.action = route_action;
    console.log("hola", form_modal_p.action);
    
    form_modal_p.addEventListener('submit', function(event) {
        // Evitar el envío predeterminado del formulario
        event.preventDefault();
        var executionNotes = document.getElementById('execution_notes').value;
        var hiddenInput = document.getElementById('id_np');
        var dataId = hiddenInput.value;
        console.log("Event prevented", executionNotes, dataId);

        fetch(form_modal_p.action, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                execution_notes: executionNotes,
                data_id: dataId
            }),
        })
        .then(response => response.json())
        .then(data => {
            console.log(data);
            // Usar Bootstrap 5 modal hide method
            var modalElement = document.getElementById(ModalId.substring(1));
            var modal = bootstrap.Modal.getInstance(modalElement);
            modal.hide();
            // Remover manualmente el backdrop
            removeModalBackdrop();
        }) 
        .catch(error => {
            console.error('Error:', error);
            var modalElement = document.getElementById(ModalId.substring(1));
            var modal = bootstrap.Modal.getInstance(modalElement);
            modal.hide();
            // Remover manualmente el backdrop
            removeModalBackdrop();
        });
    });
}

function removeModalBackdrop() {
    var backdrop = document.querySelector('.modal-backdrop');
    if (backdrop) {
        backdrop.parentNode.removeChild(backdrop);
    }
}

function AgregarNotas(TablaId) {
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    
    if (filaSeleccionada) {
        var dataId = filaSeleccionada.getAttribute('data-id');
        var hiddenInput = document.getElementById('id_np');
        hiddenInput.value = dataId;

        // Mostrar el modal
        var modal = new bootstrap.Modal(document.getElementById('modal_notas_ex'));
        modal.show();
    } else {
        alert('Por favor, seleccione una fila.');
    }
}

function CancelarOrden(TablaId) {
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    if (filaSeleccionada) {
        var dataId = filaSeleccionada.getAttribute('data-id');

        // Enviar el data-id al backend
        
        fetch('/cancelar_worklist', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ id: dataId }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Eliminar la fila si la respuesta es exitosa
                filaSeleccionada.remove();
            } else {
                console.error('Error en la respuesta del servidor:', data.error);
            }
        })
        .catch(error => {
            console.error('Error al enviar la solicitud:', error);
        });
    } else {
        console.log('No hay fila seleccionada.');
    }
}
function EjecutarOrden(TablaId) {
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    if (filaSeleccionada) {
        var dataId = filaSeleccionada.getAttribute('data-id');

        // Enviar el data-id al backend
        fetch('/ejecutar_orden', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ id: dataId }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Eliminar la fila si la respuesta es exitosa
                filaSeleccionada.remove();
            } else {
                console.error('Error en la respuesta del servidor:', data.error);
            }
        })
        .catch(error => {
            console.error('Error al enviar la solicitud:', error);
        });
    } else {
        console.log('No hay fila seleccionada.');
    }
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



function RellenarSelect(SelectId, dNeeded, TableId) {
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
        })
        .catch(error => {
            console.error('Error:', error);
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

document.addEventListener("DOMContentLoaded", function() {

    ConfigDefaultModal('Form_notas','/agregar_notas','#modal_notas_ex',"tabla_ordenes")

    var boton=document.getElementById("b_ejecutar_orden")
    boton.addEventListener("click",function(){EjecutarOrden('tabla_ordenes')})

    var boton=document.getElementById("b_cancelar_orden")
    boton.addEventListener("click",function(){CancelarOrden('tabla_ordenes')})

    var boton=document.getElementById("b_agregar_notas")
    boton.addEventListener("click",function(){AgregarNotas('tabla_ordenes')})

    RellenarTabla('tabla_ordenes',`/get_orders_ex`)
    RellenarSelect("s_modalidad","Description","public.IsModality")
    ConfigurarTabla('tabla_ordenes','botones_sp')
    configSearchForm('search_patient','/buscar_pacientes2',"tabla_ordenes")
    
})