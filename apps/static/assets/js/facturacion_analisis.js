function aplicarEstilosTipo(TablaId, columnaTipoIndex) {
    
    var tabla = document.getElementById(TablaId);
    var filas = tabla.querySelectorAll('tbody tr');
    
    filas.forEach(function(fila) {
        var celdaTipo = fila.cells[columnaTipoIndex];
        var valorTipo = celdaTipo.textContent.trim();
        // Crear el badge basado en el valor del tipo
        const badge = document.createElement('span');
        badge.classList.add('badge', 'rounded-pill', 'px-3', 'py-2');

        if (valorTipo == 'ingreso') {
            badge.classList.add('bg-success');
            badge.textContent = 'entry';
        } else if (valorTipo == 'egreso') {
            badge.classList.add('bg-danger');
            badge.textContent = 'out';
        }

        // Reemplazar el contenido de la celda con el badge
        celdaTipo.innerHTML = '';
        celdaTipo.appendChild(badge);
    });
}

let chartInstance = null;

function CreateChart() {
    var ctx1 = document.getElementById("chart-line").getContext("2d");

    // Realizar una solicitud AJAX para obtener los datos
    fetch('/api/montos')
        .then(response => response.json())
        .then(data => {
            console.log(data)
            var gradientStroke1 = ctx1.createLinearGradient(0, 0, 0, 400); // Ajuste de la posición del gradiente

            gradientStroke1.addColorStop(0, 'rgba(117, 33, 148, 1.0)');
            gradientStroke1.addColorStop(0.5, 'rgba(117, 33, 148, 0.5)');
            gradientStroke1.addColorStop(1, 'rgba(117, 33, 148, 0.1)');

            chartInstance = new Chart(ctx1, {
                type: "line",
                data: {
                    labels: data.labels, // Fechas obtenidas desde el backend
                    datasets: [{
                        label: "Ingresos/egresos",
                        data: data.data, // Montos obtenidos desde el backend
                        borderColor: "#752194",
                        backgroundColor: gradientStroke1,
                        fill: true,
                        tension: 0.4,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false, // Desactivado para que ocupe todo el ancho disponible
                },
            });
        })
        .catch(error => console.error('Error fetching data:', error));
}

function RellenarTabs(){

    fetch('/ingresos_ultima_semana')
        .then(response => response.json())
        .then(data => {
            document.getElementById('ingresos_semanales').textContent = `$${data.ingresos_ultima_semana}`;
        });

    fetch('/delta_ingresos')
        .then(response => response.json())
        .then(data => {
            document.getElementById('delta_ingresos').textContent = `${data.delta_ingresos}%`;
            // document.querySelector('span.text-success.text-sm.font-weight-bolder').textContent = `${data.delta_ingresos}%`;
        });

    fetch('/estudios_ultima_semana')
        .then(response => response.json())
        .then(data => {
            document.getElementById('estudios_realizados').textContent = `${data.estudios_ultima_semana} estudios`;
            // document.querySelector('h5.font-weight-bolder').textContent = `${data.estudios_ultima_semana} estudios`;
        });

    fetch('/delta_estudios')
        .then(response => response.json())
        .then(data => {
            document.getElementById('delta_estudios').textContent = `${data.delta_estudios}%`;
            // document.querySelector('span.text-success.text-sm.font-weight-bolder').textContent = `${data.delta_estudios}%`;
        });

    fetch('/get_best_med')
        .then(response => response.json())
        .then(data => {
            // Insertar el nombre del médico y la cantidad de estudios realizados
            document.getElementById('best_med_estudios').textContent = `${data.cantidad_estudios} Estudios este mes`;
            document.getElementById('nombre_best_med').textContent = `${data.profesional}`;
            // document.querySelector('h5.font-weight-bolder').textContent = `${data.cantidad_estudios} Estudios este mes`;
            // document.querySelector('p.text-sm.mb-0.text-uppercase.font-weight-bold').textContent = `Medico de mayor produccion: ${data.profesional}`;
        })
        .catch(error => console.error('Error fetching data:', error));

    fetch('/get_best_os')
        .then(response => response.json())
        .then(data => {
            // Inserta el nombre de la obra social y la cantidad de estudios realizados
            document.getElementById('monto_best_os').textContent = `$${data.total_monto} de Ganancia`;
            document.getElementById('nombre_best_os').textContent = data.obra_social;
            // document.querySelector('#best-os-name').textContent = data.obra_social;
            // document.querySelector('#best-os-studies').textContent = `${data.cantidad_estudios} Estudios realizados`;
            // document.querySelector('#best-os-amount').textContent = `$${data.total_monto} generados`;
        })
        .catch(error => console.error('Error fetching data:', error));
}

function FiltrarChart(TablaId,route){
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    if (filaSeleccionada) {
        var id = filaSeleccionada.getAttribute('data-id');
        fetch(route, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ id: id }),
        })
        .then(response => response.json())
        .then(data => {
            // Actualiza el gráfico con los nuevos datos
            if (chartInstance) {
                chartInstance.data.labels = data.labels; // Nuevas etiquetas
                chartInstance.data.datasets[0].data = data.data; // Nuevos datos
                chartInstance.update(); // Actualiza el gráfico para reflejar los cambios
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
        if(route=='/filter_by_med'){
        document.getElementById('titulo_chart').textContent=`Historial de Ingresos (Medico: ${id})`;
        }else{
            document.getElementById('titulo_chart').textContent=`Historial de Ingresos (Obra Social: ${id})`;
        }


    }
}


document.addEventListener("DOMContentLoaded", function() {
    // configuracion de busqueda y llenado de tabla
    RellenarTabla('tabla-ordenes',`/get_historial_prueba`)
    RellenarTabla('tabla-medicos',`/get_comp_med`)
    RellenarTabla('tabla-os',`/get_comp_os`)

    setTimeout(function() {
        aplicarEstilosTipo('tabla-ordenes', 1);
    }, 1000); 

    ConfigurarTabla('tabla-ordenes','botones_sp')
    ConfigurarTabla('tabla-medicos','botones_med')
    ConfigurarTabla('tabla-os','botones_os')

    RellenarTabs()
    CreateChart()

    document.getElementById('filtrar_med').addEventListener('click',function(){
        FiltrarChart('tabla-medicos','/filter_by_med')
    })

    document.getElementById('filtrar_os').addEventListener('click',function(){
        FiltrarChart('tabla-os','/filter_by_os')
    })


   
    
});
