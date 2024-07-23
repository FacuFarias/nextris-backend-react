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

function OpenModal(modal_html) {
    $.get(modal_html, function(data) {
        // Reemplazar los marcadores en el contenido HTML
        var modalContent = `
            <div class="informe-details" id="modal_data">
                ${data} <!-- Contenido del archivo generacion_informe.html -->
            </div>
        `;
        
        modalContent = modalContent.replace('<!-- titulo modal -->', 'CREAR USUARIO');
        $('#modal_content').html(modalContent);
        RellenarSelect("s_type_of_user", 'Description', 'public.IsRole');

        var Form = document.getElementById('Form_user');
        Form.addEventListener('submit', function(event) {
            event.preventDefault();
            console.log("Evité la redirección"); // Evitar la recarga de la página

            // Obtener los valores de los campos del formulario
            var name = document.getElementById('name').value;
            var surname = document.getElementById('surname').value;
            var username = document.getElementById('username').value;
            var dni = document.getElementById('nationalnumber').value;
            var rol = document.getElementById('s_type_of_user').value;

            // Enviar los datos al backend
            fetch('/create_user', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ name: name, surname: surname, username: username, dni: dni, rol: rol }),
            })
            .then(response => response.json())
            .then(data => {
                console.log(data);
                $('#modal_users').modal('hide');
                // Aquí puedes agregar lógica para actualizar la tabla con el nuevo usuario
            })
            .catch(error => {
                console.error('Error:', error);
            });
        });

        $('#modal_users').modal('show');
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
    RellenarTabla('tabla_usuarios',`/get_users`)
    ConfigurarTabla('tabla_usuarios','botones_sp')

});
