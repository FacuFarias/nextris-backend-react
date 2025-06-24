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
        $('#modal_content').html(modalContent);

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

function VerImagenes(){
    var tabla = document.getElementById('tabla-pacientes');
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    if (filaSeleccionada) {
        var dataId = filaSeleccionada.getAttribute('data-id');}
    $.ajax({
        url: '/get_image_link', // URL de tu API
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ id: dataId }),
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

function VerPDF() {
    var tabla = document.getElementById('tabla-pacientes');
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    if (filaSeleccionada) {
        var dataId = filaSeleccionada.getAttribute('data-id');}

    var url = `/verpdf/${dataId}`;

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

function EnviarInforme() {
    var tabla = document.getElementById('tabla-pacientes');
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    var mail = filaSeleccionada.children[3].textContent.trim(); // Obtener el contenido del cuarto td
    if (filaSeleccionada) {
        var dataId = filaSeleccionada.getAttribute('data-id');
    }

    var url = `/send_mail/${dataId}?mail=${encodeURIComponent(mail)}`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            console.log('Resultado:', data.message || 'Correo enviado exitosamente');
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

function RellenarSelectCondicional(SelectId,dNeeded,TableId,dCond,IdCond){
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

// IdCond sería el dato que quiero para filtrar en la columna colCond
function RellenarSelectCondicionalId(SelectId,dNeeded,TableId,idCond,colCond){
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
    })
    .catch(error => {
        console.error('Error:', error);
    });
}


document.addEventListener("DOMContentLoaded", function() {
    // configuracion de busqueda y llenado de tabla
    RellenarTabla('tabla-pacientes',`/get_orders_to_distribution`)

    var boton_vi=document.getElementById("b_ver_info")
    boton_vi.addEventListener("click",function(){VerPDF()})

    var boton_ver_ima=document.getElementById("b_ver_dicom")
    boton_ver_ima.addEventListener("click",function(){VerImagenes()})

    var b_enviar_inf=document.getElementById("b_enviar_inf")
    b_enviar_inf.addEventListener("click",function(){EnviarInforme()})

    ConfigurarTabla('tabla-pacientes','botones_sp')

   
    
});
