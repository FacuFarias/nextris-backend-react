idestudio = null;

function seleccionarEstudio() {
    var tabla = document.getElementById("tabla-estudios");
    var tbody_g = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_g.querySelector('tr.fila-seleccionada');
    if (filaSeleccionada) {
        var idestudio = filaSeleccionada.getAttribute('data-id');
        var idpaciente = filaSeleccionada.getAttribute('data-patient-id');
        console.log("Estudio seleccionado:", idestudio, "Paciente ID:", idpaciente);
        var tds = filaSeleccionada.querySelectorAll('td');
        var estudio = {
            fecha: tds[0].textContent,
            accession: tds[1].textContent,
            id_paciente: tds[2].textContent,
            nombre_paciente: tds[3].textContent,
            nacimiento: tds[4].textContent,
            descripcion: tds[5].textContent,
            estado: tds[6].textContent,
            id: filaSeleccionada.getAttribute('data-id')
        };
        console.log("Estudio seleccionado:", estudio);
        // Rellenar los campos del modal con los datos del estudio
        document.getElementById('estudio_nombre').value = estudio.nombre_paciente || '';
        document.getElementById('estudio_accesion').value = estudio.accession || '';
        document.getElementById('estudio_fecha').value = estudio.fecha || '';
        document.getElementById('estudio_descripcion').value = estudio.descripcion || '';
        document.getElementById('estudio_id').value = estudio.id || '';
        var triggerPaciente = document.querySelector('#pills-paciente-tab');
        if (triggerPaciente) {
            var pacienteTab = new bootstrap.Tab(triggerPaciente);
            pacienteTab.show();
        }
    }
}

function seleccionarPaciente() {
    var tabla = document.getElementById('tabla-pacientes');
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    if (filaSeleccionada) {
        // Obtener datos del paciente
        var tds = filaSeleccionada.querySelectorAll('td');
        var paciente = {
            nombre: tds[0].textContent,
            apellido: tds[1].textContent,
            dni: tds[2].textContent,
            id: filaSeleccionada.getAttribute('data-id')
        };
        // Obtener datos del estudio guardados previamente
        var estudio = window.estudioSeleccionadoDatos || {};
        mostrarModalReasignar(estudio, paciente);
    }
}

function mostrarModalReasignar(estudio, paciente) {
    document.getElementById('paciente_nombre').value = paciente.nombre || '';
    document.getElementById('paciente_apellido').value = paciente.apellido || '';
    document.getElementById('paciente_dni').value = paciente.dni || '';
    document.getElementById('paciente_id').value = paciente.id || '';
    var myModal = new bootstrap.Modal(document.getElementById('modal_reasignar'));
    myModal.show();
}

document.addEventListener("DOMContentLoaded", function() {
    var triggerEstudio = document.querySelector('#pills-paciente-tab');
    if (triggerEstudio) {
        var estudioTab = new bootstrap.Tab(triggerEstudio);
        estudioTab.show();
    }

    var triggerEl = document.querySelector('#pills-estudio-tab');
    var tab = new bootstrap.Tab(triggerEl);
    tab.show();
    
    // configuracion de busqueda y llenado de tabla
    RellenarTabla('tabla-estudios',`/get_estudios_reasignar`)
    RellenarTabla('tabla-pacientes',`/get_pacientes_reasignar`)
    ConfigurarTabla('tabla-estudios','botones_est')
    ConfigurarTabla('tabla-pacientes','botones_p')

    // Doble click en la tabla de estudios ejecuta getHistory
    var tablaEstudios = document.getElementById('tabla-estudios');
    var tbodyEstudios = tablaEstudios.querySelector('tbody');
    tbodyEstudios.addEventListener('dblclick', function(e) {
        var tr = e.target.closest('tr');
        if(tr) {
            // Marcar la fila como seleccionada
            tbodyEstudios.querySelectorAll('tr').forEach(fila => fila.classList.remove('fila-seleccionada'));
            tr.classList.add('fila-seleccionada');
            seleccionarEstudio();
        }
    });

    // Doble click en la tabla de pacientes ejecuta seleccionarPaciente
    var tablaPacientes = document.getElementById('tabla-pacientes');
    var tbodyPacientes = tablaPacientes.querySelector('tbody');
    tbodyPacientes.addEventListener('dblclick', function(e) {
        var tr = e.target.closest('tr');
        if(tr) {
            // Marcar la fila como seleccionada
            tbodyPacientes.querySelectorAll('tr').forEach(fila => fila.classList.remove('fila-seleccionada'));
            tr.classList.add('fila-seleccionada');
            seleccionarPaciente();
        }
    });

    let tablaBusquedaActiva = 'tabla-estudios';
    const inputBusqueda = document.getElementById('busquedaSwitch');

    function aplicarBusqueda() {
        ConfigFiltrarText('busquedaSwitch', tablaBusquedaActiva, 1);
    }

    // Detectar cambio de pestaña y actualizar tabla activa
    document.getElementById('pills-estudio-tab').addEventListener('shown.bs.tab', function() {
        tablaBusquedaActiva = 'tabla-estudios';
        aplicarBusqueda();
    });
    document.getElementById('pills-paciente-tab').addEventListener('shown.bs.tab', function() {
        tablaBusquedaActiva = 'tabla-pacientes';
        aplicarBusqueda();
    });

    // Ejecutar búsqueda al escribir
    inputBusqueda.addEventListener('input', function() {
        aplicarBusqueda();
    });

    // Inicializar búsqueda sobre la tabla activa al cargar
    aplicarBusqueda();

    var verInformeBtn = document.getElementById('ver-informe');
    verInformeBtn.addEventListener('click', function() {
        var tabla = document.getElementById("tabla-estudios");
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

    // Asignar evento al botón de seleccionar estudio
    var btnSeleccionarEstudio = document.getElementById('seleccionar-estudio');
    if (btnSeleccionarEstudio) {
        btnSeleccionarEstudio.addEventListener('click', seleccionarEstudio);
    }
    // Asignar evento al botón de seleccionar paciente
    var btnSeleccionarPaciente = document.getElementById('seleccionar-paciente');
    if (btnSeleccionarPaciente) {
        btnSeleccionarPaciente.addEventListener('click', seleccionarPaciente);
    }

    var formReasignar = document.getElementById('Form_reasignar');
    if (formReasignar) {
        formReasignar.addEventListener('submit', function(e) {
            // Solo ejecutar si el botón submit fue el disparador
            if (e.submitter && e.submitter.type === 'submit') {
                e.preventDefault();
                var estudioId = document.getElementById('estudio_id').value;
                var pacienteId = document.getElementById('paciente_id').value;
                var payload = {
                    estudio_id: estudioId,
                    paciente_id: pacienteId
                };
                fetch('/reasignar_estudio', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Guardar flag para mostrar toast después de recargar
                        localStorage.setItem('showReasignarToast', '1');
                        window.location.reload();
                    } else {
                        alert('Error al reasignar estudio: ' + (data.message || ''));
                    }
                })
                .catch(err => {
                    alert('Error de red o backend');
                });
            } else {
                // Si no fue el botón submit, solo cerrar el modal
                e.preventDefault();
                var modal = bootstrap.Modal.getInstance(document.getElementById('modal_reasignar'));
                if (modal) modal.hide();
            }
        });
    }
    // Mostrar toast si corresponde al cargar la página
    if (localStorage.getItem('showReasignarToast')) {
        showToast('Éxito', 'Estudio reasignado correctamente.', "/templates/includes/toast/toast_success.html");
        localStorage.removeItem('showReasignarToast');
    }
});




