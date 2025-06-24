var patId
var nom
var apellido
var dni


document.addEventListener("DOMContentLoaded", function() {

    var triggerEl = document.querySelector('#pills-examen-tab');
    var examtab = new bootstrap.Tab(triggerEl);
    examtab.show();

    var triggerEl = document.querySelector('#pills-paciente-tab');
    var pattab = new bootstrap.Tab(triggerEl);
    pattab.show();
    
    // configuracion de busqueda y llenado de tabla
    RellenarTabla('tabla-pacientes',`/get_patients`)
    RellenarTabla('tabla-pacientestodelete',`/get_patients`)
    ConfigurarTabla('tabla-pacientes','botones_sp')
    ConfigurarTabla('tabla-pacientestodelete','botones_ptd')

    // Event listener para el botón de seleccionar paciente
    var seleccionarPacienteBtn = document.getElementById('seleccionar-paciente');
    seleccionarPacienteBtn.addEventListener('click', function() {
        // Obtengo el patient id
        var tabla = document.getElementById('tabla-pacientes');
        var tbody_ = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
        
        if (filaSeleccionada) {
            // Obtengo el patient id
            patId = filaSeleccionada.getAttribute('data-id');

            // Obtengo los datos de los respectivos tds
            var tds = filaSeleccionada.querySelectorAll('td');
            nom = tds[0].textContent;       // Primer td (nombre)
            apellido = tds[1].textContent;  // Segundo td (apellido)
            dni = tds[2].textContent;       // Tercer td (dni)
        }
        
        // coloco en verde la tab de Paciente correcto agregandole la clase success
        pacientetab=document.getElementById("pills-paciente-tab")
        pacientetab.classList.add("nav-link-success");
        
        var examenTabEl = document.querySelector('#pills-examen-tab');
        var examenTab = new bootstrap.Tab(examenTabEl);
        examenTab.show();
    });

    var seleccionarPacienteTDBtn = document.getElementById('btn-ptd');
    seleccionarPacienteTDBtn.addEventListener('click', function() {
        // Obtengo el patient id
        var tabla = document.getElementById('tabla-pacientestodelete');
        var tbody_ = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
        
        if (filaSeleccionada) {
            var patTD = filaSeleccionada.getAttribute('data-id');
            // Obtengo los datos de los respectivos tds
            var tdsTd = filaSeleccionada.querySelectorAll('td');
            var nomtd = tdsTd[0].textContent;       // Primer td (nombre)
            var apellidotd = tdsTd[1].textContent;  // Segundo td (apellido)
            var dnitd = tdsTd[2].textContent;       // Tercer td (dni)

            // Abrir el modal
            var myModal = new bootstrap.Modal(document.getElementById('modal_ptd'));
            myModal.show();
        }


    })

});
