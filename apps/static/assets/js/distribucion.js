// Este archivo contiene funciones JavaScript para la gestión de la distribución de informes en la aplicación NextRIS.
// Muchas funciones que se utilizan en esta sección están definidas en otros archivos JS, como loader.js y toast.js, principalmente nrframework.js.
// No se deberán crear funciones duplicadas aquí si ya existen en esos archivos.


function RellenarTablaDistribucion(TablaId, route) {
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
                
                // Verificar si el estudio está publicado (último elemento del array)
                var isPublicado = item[item.length - 1] === 1;
                
                // Agregar clase especial si está publicado
                if (isPublicado) {
                    row.classList.add('estudio-publicado');
                }

                // Iterar sobre los elementos de item (omitir el primer elemento y el último que es ispublicated)
                for (var i = 1; i < item.length - 1; i++) {
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
                
                // Agregar indicador visual si está publicado
                if (isPublicado) {
                    var firstCell = row.querySelector('td');
                    if (firstCell) {
                        var badge = document.createElement('span');
                        badge.innerHTML = '<i class="fas fa-check-circle me-1"></i>';
                        badge.className = 'badge-enviado';
                        firstCell.prepend(badge);
                    }
                }

                tbody_.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

function Modaledit() {
    var tabla = document.getElementById('tabla-pacientes');
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    
    if (filaSeleccionada) {
        var dataId = filaSeleccionada.getAttribute('data-id');
        var name = filaSeleccionada.children[2].textContent.trim(); // Obtener el contenido del tercer td
        var mail = filaSeleccionada.children[3].textContent.trim(); // Obtener el contenido del cuarto td
    }
    
    // Cargar el contenido del archivo modal_edit_mail.html
    $.get('/modal_edit_mail.html', function(data) {
        // Reemplazar los marcadores en el contenido HTML
        var modalContent = `
            <div class="informe-details" id="modal_data">
                ${data} <!-- Contenido del archivo generacion_informe.html -->
            </div>
        `;
        // Usar el contenedor global (definido en base.html)
        $('#global_modal_container').html(modalContent);

        if (filaSeleccionada) {
            document.getElementById('name').value = name;
            document.getElementById('mail').value = mail;
        }

        var Form = document.getElementById('modal_edit_mail');
        Form.addEventListener('submit', function (event) {
            event.preventDefault();
            console.log("evite la redireccion"); // Evitar la recarga de la página

            // Obtener el valor del mail del campo del formulario
            var updatedMail = document.getElementById('mail').value;

            // Enviar los datos al backend
            fetch('/edit_mail', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ id_order: dataId, mail: updatedMail }),
            })
            .then(response => response.json())
            .then(data => {
                console.log(data)
                var updatedMail = document.getElementById('mail').value;
                filaSeleccionada.children[3].textContent = updatedMail;
                //colocar lo contenido en id="mail" en el tercer td de fila-seleccionada
                $('#modal_edit_mail').modal('hide');
            })
            .catch(error => {
                console.error('Error:', error);
            });
        });

        $('#modal_edit_mail').modal('show');
    });
}

function VolverAtras() {
    $('#card_ordenes').show();
    $('#card_buscar').show();
    $('#data').remove(); // Eliminar el elemento #data
}


function EnviarInforme() {
    var tabla = document.getElementById('tabla-pacientes');
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    
    if (!filaSeleccionada) {
        showToast('Error', 'Debe seleccionar una fila primero.', '/templates/includes/toast/toast_error.html');
        return;
    }
    
    var mail = filaSeleccionada.children[3].textContent.trim(); // Obtener el contenido del cuarto td
    var dataId = filaSeleccionada.getAttribute('data-id');
    
    if (!mail || mail === '') {
        showToast('Error', 'No hay email asociado al paciente.', '/templates/includes/toast/toast_error.html');
        return;
    }

    var url = `/send_mail/${dataId}?mail=${encodeURIComponent(mail)}`;

    // Mostrar notificación de procesando
    showToast('Enviando...', 'Enviando informe por email, por favor espere...', '/templates/includes/toast/toast_alert.html');

    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                showToast('Éxito', data.message, '/templates/includes/toast/toast_success.html');
                console.log('Resultado:', data.message);
                
                // Eliminar la fila después de enviar exitosamente
                filaSeleccionada.remove();
                
                // Verificar si quedan estudios
                verificarEstudiosVacios();
            } else if (data.error) {
                showToast('Error', data.error, '/templates/includes/toast/toast_error.html');
                console.error('Error:', data.error);
            } else {
                showToast('Éxito', 'Correo enviado exitosamente', '/templates/includes/toast/toast_success.html');
                console.log('Resultado: Correo enviado exitosamente');
                
                // Eliminar la fila después de enviar exitosamente
                filaSeleccionada.remove();
                
                // Verificar si quedan estudios
                verificarEstudiosVacios();
            }
        })
        .catch(error => {
            showToast('Error', 'Error al enviar el correo: ' + error.message, '/templates/includes/toast/toast_error.html');
            console.error('Error:', error);
        });
}


function verificarEstudiosVacios() {
    var tabla = document.getElementById('tabla-pacientes');
    var tbody = tabla.querySelector('tbody');
    var filas = tbody.querySelectorAll('tr:not(.no-estudios-row)');
    
    // Si no hay filas o todas son filas de "no estudios"
    if (filas.length === 0) {
        // Verificar si ya existe la fila de mensaje
        var existeFilaMensaje = tbody.querySelector('.no-estudios-row');
        
        if (!existeFilaMensaje) {
            // Crear la fila de mensaje
            var row = document.createElement('tr');
            row.classList.add('no-estudios-row');
            
            // Crear la celda que ocupará todas las columnas
            var cell = document.createElement('td');
            
            // Obtener el número de columnas de la tabla
            var thead = tabla.querySelector('thead');
            var numColumnas = thead ? thead.querySelectorAll('th').length : 4;
            cell.setAttribute('colspan', numColumnas);
            
            // Agregar el contenido con el icono y el mensaje
            cell.innerHTML = '<i class="fas fa-check-circle" style="color: #2dce89; font-size: 24px; margin-right: 10px;"></i>' +
                           '<span style="color: #2dce89; font-size: 16px; font-weight: 500;">No hay más estudios para distribuir</span>';
            cell.style.textAlign = 'center';
            cell.style.padding = '30px';
            
            row.appendChild(cell);
            tbody.appendChild(row);
        }
    }
}

function cargarOrdenes() {
    var checkboxYaEnviados = document.getElementById('checkbox_ya_enviados');
    var incluirEnviados = checkboxYaEnviados ? checkboxYaEnviados.checked : false;
    
    var url = `/get_orders_to_distribution?incluir_enviados=${incluirEnviados}`;
    
    RellenarTablaDistribucion('tabla-pacientes', url);
    
    // Esperar un momento para que la tabla se llene y luego verificar
    setTimeout(verificarEstudiosVacios, 500);
}

document.addEventListener("DOMContentLoaded", function() {
    console.log('DOM Loaded - Iniciando distribucion.js');
    
    // configuracion de busqueda y llenado de tabla
    cargarOrdenes();

    var boton_vi = document.getElementById("b_ver_info");
    if (boton_vi) {
        console.log('Botón b_ver_info encontrado');
        boton_vi.addEventListener("click", function() {
            var tabla = document.getElementById('tabla-pacientes');
            var tbody_ = tabla.querySelector('tbody');
            var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
            if (filaSeleccionada) {
                var dataId = filaSeleccionada.getAttribute('data-id');
                VerPDF(dataId);
            }
        });
    } else {
        console.error('Botón b_ver_info NO encontrado');
    }

    var boton_ver_ima = document.getElementById("b_ver_dicom");
    if (boton_ver_ima) {
        console.log('Botón b_ver_dicom encontrado');
        boton_ver_ima.addEventListener("click", function() {
            console.log('Click en b_ver_dicom detectado');
            
            // Obtener la fila seleccionada
            var tabla = document.getElementById('tabla-pacientes');
            var tbody_ = tabla.querySelector('tbody');
            var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
            
            if (!filaSeleccionada) {
                showToast('Error', 'Debe seleccionar una fila primero.', '/templates/includes/toast/toast_error.html');
                return;
            }
            
            // Obtener el ID del estudio
            var dataId = filaSeleccionada.getAttribute('data-id');
            
            if (!dataId) {
                showToast('Error', 'No se pudo obtener el ID del estudio.', '/templates/includes/toast/toast_error.html');
                return;
            }
            
            console.log('ID del estudio seleccionado: ' + dataId);
            
            // Llamar a la función de nrframework.js con el ID
            VerImagenes(dataId);
        });
    } else {
        console.error('Botón b_ver_dicom NO encontrado');
    }

    var b_enviar_inf = document.getElementById("b_enviar_inf");
    if (b_enviar_inf) {
        console.log('Botón b_enviar_inf encontrado');
        b_enviar_inf.addEventListener("click", function() {
            EnviarInforme();
        });
    } else {
        console.error('Botón b_enviar_inf NO encontrado');
    }

    ConfigurarTabla('tabla-pacientes','botones_sp');
    
    // Agregar evento al checkbox de "Ya enviados"
    var checkboxYaEnviados = document.getElementById('checkbox_ya_enviados');
    if (checkboxYaEnviados) {
        console.log('Checkbox checkbox_ya_enviados encontrado');
        checkboxYaEnviados.addEventListener('change', function() {
            cargarOrdenes();
        });
    } else {
        console.log('Checkbox checkbox_ya_enviados NO encontrado');
    }
    
    console.log('distribucion.js - Inicialización completada');
});