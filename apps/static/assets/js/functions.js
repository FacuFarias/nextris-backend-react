document.addEventListener("DOMContentLoaded", function() {
   
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
