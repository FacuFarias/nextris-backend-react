document.addEventListener("DOMContentLoaded", function() {
    var tablaPacientes = document.getElementById('tabla-paciente');
    var tbody = tablaPacientes.querySelector('tbody');
    
    var idPaciente = null;
    if(botonhistorial = document.getElementById('historial-x-id')){
    var botonhistorial = document.getElementById('historial-x-id');
    botonhistorial.addEventListener('click', historialClickHandler);}

    function historialClickHandler() {
        if (idPaciente) {
            
            fetch(`/obtener_historial?id=${idPaciente}`)
                .then(response => response.json())
                .then(data => {
                    console.log(data);
                    const tabla = document.getElementById('tabla-reportes');
                    data.forEach(informe => {
                        const fila = document.createElement('tr');
                        fila.className = 'report-row'; // Agrega una clase para identificación
    
                        // Crea celdas y llena con datos
                        
    
                        const lastUpdatedCell = document.createElement('td');
                        lastUpdatedCell.textContent = informe.lastUpdated;
                        fila.appendChild(lastUpdatedCell);

                        const idCell = document.createElement('td');
                        idCell.textContent = informe.code;
                        fila.appendChild(idCell);
    
                        const sourceCell = document.createElement('td');
                        sourceCell.textContent = informe.source;
                        fila.appendChild(sourceCell);
    
                        const statusCell = document.createElement('td');
                        statusCell.textContent = informe.status;
                        fila.appendChild(statusCell);
    
                        // Agrega la fila a la tabla
                        tabla.querySelector('tbody').appendChild(fila);
                    });

                })
                .catch(error => {
                    console.error('Error:', error);
                });
        }
    }

    tbody.addEventListener('click', function (event) {
        var filas = tbody.querySelectorAll('tr');
        for (var i = 0; i < filas.length; i++) {
            filas[i].classList.remove('fila-seleccionada');
        }

        var fila = event.target.closest('tr');
        if (fila) {
            fila.classList.add('fila-seleccionada');
            idPaciente = fila.cells[0].textContent;
            var nombre = fila.cells[1].textContent;
            var sexo = fila.cells[2].textContent;
            var fechaNacimiento = fila.cells[3].textContent;
            var dni = fila.cells[4].textContent;

            var botonEliminar = document.getElementById('eliminar-paciente');
            botonEliminar.setAttribute('patient-id', idPaciente);

            var botonEditar = document.getElementById('editar-paciente');
            botonEditar.setAttribute('patient-id', idPaciente);
            botonEditar.addEventListener('click', function () {
                $("#modal_np #nombrePaciente").val(nombre);
                $("#modal_np #dni").val(dni);
                $("#modal_np #sex").val(sexo);
                $("#modal_np #id").val(idPaciente);
                $("#modal_np #fecha_nacimiento").val(fechaNacimiento);
                $("#modal_np").find('form').attr('action', '/editar_paciente');
                $("#modal_np").modal("show");
            });

            botonEliminar.addEventListener('click', function () {
                if (confirm('¿Seguro que desea eliminar este paciente?')) {
                    fetch('/eliminar_paciente?id=' + idPaciente, { method: 'GET' })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                fila.remove();
                                alert('Paciente eliminado con éxito');
                            } else {
                                alert('Error al eliminar el paciente.');
                            }
                        })
                        .catch(error => {
                            console.error('Error:', error);
                        });
                }
            });

            var botones = document.getElementsByClassName('botones');
            for (var i = 0; i < botones.length; i++) {
                var boton = botones[i];
                boton.disabled = false;
                boton.classList.remove('btn-secondary');
                boton.classList.add('btn-primary');
            }
        } else {
            var botones = document.getElementsByClassName('botones');
            for (var i = 0; i < botones.length; i++) {
                var boton = botones[i];
                boton.disabled = true;
                boton.classList.remove('btn-primary');
                boton.classList.add('btn-secondary');
            }
        }
    });

    var closeButton = document.getElementById('btn-close');
    if (closeButton) {
        closeButton.addEventListener('click', function () {
            var alertSuccess = document.getElementById('notif-carga');
            if (alertSuccess) {
                alertSuccess.remove();
            }
        });
    }
});
