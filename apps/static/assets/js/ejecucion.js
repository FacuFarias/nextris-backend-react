// Función global para mostrar los detalles de la orden
function MostrarDetallesOrden(fila) {
    if (fila) {
        var id = fila.dataset.id;
        fetch('/get_examination_details', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ guid: id })
        })
        .then(function(response) { return response.json(); })
        .then(function(data) {
            var historiaElem = document.getElementById('historia_clinica');
            if (historiaElem) historiaElem.value = data.history || '';
            var preguntaElem = document.getElementById('pregunta_clinica');
            if (preguntaElem) preguntaElem.value = data.clinicalquestion || '';
            var lateralidadElem = document.getElementById('s_lateralidad');
            if (lateralidadElem) lateralidadElem.value = data.laterality_id || '';
            var statElem = document.getElementById('stat');
            if (statElem) statElem.value = data.stat ? 'Sí' : 'No';
            var numVistasElem = document.getElementById('num_vistas');
            if (numVistasElem) numVistasElem.value = data.numberofviews || '';
            var detalleElem = document.getElementById('detalle_tecnico');
            if (detalleElem) detalleElem.value = data.othersdetails || '';
            var detallesTab = document.getElementById('pills-detalles-tab');
            if (detallesTab) {
                detallesTab.removeAttribute('disabled');
                detallesTab.click();
                var listaPane = document.getElementById('pills-lista');
                var detallesPane = document.getElementById('pills-detalles');
                if (listaPane && detallesPane) {
                    listaPane.classList.remove('active', 'show');
                    detallesPane.classList.add('active', 'show');
                }
            }
            var accNumber = '';
            if (fila && fila.cells && fila.cells.length > 7) {
                accNumber = fila.cells[7].textContent.trim();
            }
            var detallesPane = document.getElementById('pills-detalles');
            var detallesTitulo = detallesPane ? detallesPane.querySelector('h6') : null;
            if (detallesTitulo) {
                detallesTitulo.textContent = 'Detalles de la orden: ' + accNumber;
            }
        })
        .catch(function(error) {
            console.error('Error al obtener detalles de la orden:', error);
        });
    }
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
        // Obtener los datos de los campos de detalles de la orden
    var historia = document.getElementById('historia_clinica')?.value.trim() || '';
    var pregunta = document.getElementById('pregunta_clinica')?.value.trim() || '';
    var lateralidad = document.getElementById('s_lateralidad')?.value.trim() || '';
    var statValue = document.getElementById('stat')?.value || '';
    var stat = (statValue === 'Sí') ? 1 : 0;
    var numVistas = document.getElementById('num_vistas')?.value.trim() || '';
    var detalleTecnico = document.getElementById('detalle_tecnico')?.value.trim() || '';

    // Si algún campo está vacío, enviar 'no clasifica'
    historia = historia === '' ? 'no clasifica' : historia;
    pregunta = pregunta === '' ? 'no clasifica' : pregunta;
    lateralidad = lateralidad === '' ? 'no clasifica' : lateralidad;
    numVistas = numVistas === '' ? 'no clasifica' : numVistas;
    detalleTecnico = detalleTecnico === '' ? 'no clasifica' : detalleTecnico;

        // Enviar el data-id y los datos al backend
        fetch('/ejecutar_orden', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                id: dataId,
                historia: historia,
                pregunta: pregunta,
                lateralidad: lateralidad,
                stat: stat,
                num_vistas: numVistas,
                detalle_tecnico: detalleTecnico
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Eliminar la fila si la respuesta es exitosa
                filaSeleccionada.remove();
                // Volver a la pestaña de lista
                var listaTab = document.getElementById('pills-lista-tab');
                var listaPane = document.getElementById('pills-lista');
                var detallesPane = document.getElementById('pills-detalles');
                if (listaTab) {
                    listaTab.click();
                }
                if (listaPane && detallesPane) {
                    listaPane.classList.add('active', 'show');
                    detallesPane.classList.remove('active', 'show');
                }
                // Mostrar un mensaje de éxito
                showToast('Felicitaciones', 'Ejecutaste la orden con Exito', "/templates/includes/toast/toast_success.html")
                console.log('Orden ejecutada con éxito');
                
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



function VerDetalles(TablaId){
        
    // Obtener la fila seleccionada
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    if (filaSeleccionada) {
        MostrarDetallesOrden(filaSeleccionada);
    } else {
        console.warn('No hay fila seleccionada.');
    }

}

document.addEventListener("DOMContentLoaded", function() {

    // ConfigDefaultModal('Form_notas','/agregar_notas','#modal_notas_ex',"tabla_ordenes")

    var boton=document.getElementById("b_ejecutar_orden")
    boton.addEventListener("click",function(){EjecutarOrden('tabla_ordenes')})

    var boton_ver_detalles=document.getElementById("b_ver_detalles")
    boton_ver_detalles.addEventListener("click",function(){
        var tabla = document.getElementById('tabla_ordenes');
        var tbody_ = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
        if (filaSeleccionada) {
            MostrarDetallesOrden(filaSeleccionada);
            

        } else {
            console.warn('No hay fila seleccionada.');
        }

    })

    RellenarTabla('tabla_ordenes',`/get_orders_ex`)
    RellenarSelect("s_modalidad","Description","public.IsModality")
    RellenarSelect("s_lateralidad","description","public.islaterality",'No Clasifica',false)
    ConfigurarTabla('tabla_ordenes','botones_sp')

    // Deshabilitar la pestaña de detalles al cargar
    var detallesTab = document.getElementById('pills-detalles-tab');
    if (detallesTab) {
        detallesTab.setAttribute('disabled', 'disabled');
    }

    // Listener para habilitar botón ejecutar orden cuando se selecciona una fila
    var tabla = document.getElementById('tabla_ordenes');
    var tbody = tabla.querySelector('tbody');
    
    tbody.addEventListener('click', function (event) {
        var fila = event.target.closest('tr');
        if (fila && fila.parentElement.tagName === 'TBODY') {
            // Obtener todos los botones que deben habilitarse
            var btnEjecutar = document.getElementById('b_ejecutar_orden');
            
            // Verificar si hay una fila seleccionada
            var filaSeleccionada = tbody.querySelector('.fila-seleccionada');
            
            if (filaSeleccionada) {
                // Habilitar botón ejecutar orden
                if (btnEjecutar) {
                    btnEjecutar.disabled = false;
                }
            } else {
                // Deshabilitar botón ejecutar orden
                if (btnEjecutar) {
                    btnEjecutar.disabled = true;
                }
            }
        }
    });

    // Listener para rellenar detalles al hacer doble clic en una fila
    tbody.addEventListener('dblclick', function (event) {
        var fila = event.target.closest('tr');
        if (fila) {
            MostrarDetallesOrden(fila);
        }
    });
    
})
