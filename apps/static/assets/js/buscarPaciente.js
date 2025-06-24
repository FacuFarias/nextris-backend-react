function getHistory() {
    // Si hay una fila seleccionada
    var tabla = document.getElementById("tabla-pacientes");
    var tbody_g = tabla.querySelector('tbody');

    var filaSeleccionada = tbody_g.querySelector('tr.fila-seleccionada');
    if (filaSeleccionada) {
        var idpat = filaSeleccionada.getAttribute('data-id');
        

        // Hacer una llamada al back-end para obtener el historial del paciente
        fetch(`/get_patient_history`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ id: idpat }) // Enviamos el ID del paciente en el body
        })
        .then(response => response.json())
        .then(data => {
            // Procesar los datos del historial obtenidos del back-end
            console.log("Historial del paciente:", data);
            
            // Aquí actualizamos la tabla del historial con los datos recibidos
            updateHistorialTable(data);
            
            // Cambiar a la pestaña de historial
            var triggerEl = document.querySelector('#pills-examen-tab');
            var tab = new bootstrap.Tab(triggerEl);
            tab.show();
        })
        .catch(error => {
            console.error('Error al obtener el historial del paciente:', error);
        });
    } else {
        console.log("No hay paciente seleccionado.");
    }
}

function updateHistorialTable(data) {
    // Seleccionar la tabla de historial
    var tablaHistorial = document.getElementById('tabla-historial');
    var tbody = tablaHistorial.querySelector('tbody');

    // Limpiar la tabla antes de llenarla
    tbody.innerHTML = '';

    // Llenar la tabla con los datos recibidos
    data.forEach(historial => {
        var fila = document.createElement('tr');

        // El primer elemento es el 'guid', lo almacenamos en 'data-id' del <tr>
        var guid = historial[0];
        fila.setAttribute('data-id', guid);

        // Iteramos sobre el resto de los elementos (desde el segundo en adelante)
        for (var i = 1; i < historial.length; i++) {
            var item = historial[i];
            var celda = document.createElement('td');
            celda.textContent = item !== null ? item : 'N/A'; // Si el item es null, colocar 'N/A'
            fila.appendChild(celda);
        }

        // Añadir la fila a la tabla
        tbody.appendChild(fila);
    });
}



document.addEventListener("DOMContentLoaded", function() {

    var triggerEl = document.querySelector('#pills-examen-tab');
    var tab = new bootstrap.Tab(triggerEl);
    tab.show();

    var triggerEl = document.querySelector('#pills-paciente-tab');
    var tab = new bootstrap.Tab(triggerEl);
    tab.show();
    
    // configuracion de busqueda y llenado de tabla
    RellenarTabla('tabla-pacientes',`/get_patients`)
    ConfigurarTabla('tabla-pacientes','botones_sp')
    ConfigurarTabla('tabla-historial','botones_hp')

    // Event listener para el botón de seleccionar paciente
    var seleccionarPacienteBtn = document.getElementById('seleccionar-paciente');
    seleccionarPacienteBtn.addEventListener('click', function() {
        getHistory()
    });

    var verInformeBtn = document.getElementById('ver-informe');
    verInformeBtn.addEventListener('click', function() {
        var tabla = document.getElementById("tabla-historial");
        var tbody_g = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_g.querySelector('tr.fila-seleccionada');
        if (filaSeleccionada) {
            var idest = filaSeleccionada.getAttribute('data-id');
        }
        VerPDF(idest)        
    });
    var verImagenBtn = document.getElementById('ver-imagen');
    verImagenBtn.addEventListener('click', function() {
        var tabla = document.getElementById("tabla-historial");
        var tbody_g = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_g.querySelector('tr.fila-seleccionada');
        if (filaSeleccionada) {
            var idest = filaSeleccionada.getAttribute('data-id');
        }
        VerImagenes(idest)


    })

});
