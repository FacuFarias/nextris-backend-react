var patId
var nom
var apellido
var dni

function SeleccionarPacienteToDelete(){
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
    };

function SeleccionarPacienteToDeleteTD(){
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
        console.log("Paciente a eliminar:", patTD, nomtd, apellidotd, dnitd);

        // También obtengo los datos del paciente correcto (de la otra tabla)
        var tablaCorrecto = document.getElementById('tabla-pacientes');
        var filaCorrecta = tablaCorrecto.querySelector('tbody .fila-seleccionada');
        var nom = '', apellido = '', dni = '', patId = '';
        if (filaCorrecta) {
            var tds = filaCorrecta.querySelectorAll('td');
            nom = tds[0].textContent;
            apellido = tds[1].textContent;
            dni = tds[2].textContent;
            patId = filaCorrecta.getAttribute('data-id');
        }

        // Rellenar los campos del modal
        document.getElementById('p_name').value = nom;
        document.getElementById('p_surname').value = apellido;
        document.getElementById('p_dni').value = dni;
        document.getElementById('p_id').value = patId;
        document.getElementById('p_name_td').value = nomtd;
        document.getElementById('p_surname_td').value = apellidotd;
        document.getElementById('p_dni_td').value = dnitd;
        document.getElementById('p_id_td').value = patTD;
        console.log("Pacientes:", patId, patTD);

        // Abrir el modal
        var myModal = new bootstrap.Modal(document.getElementById('modal_ptd'));
        myModal.show();
    }
}

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
    seleccionarPacienteBtn.addEventListener('click', function() {SeleccionarPacienteToDelete()});

    // Ejecutar SeleccionarPacienteToDelete al hacer doble clic en la tabla-pacientes
    var tablaPacientes = document.getElementById('tabla-pacientes');
    var tbodyPacientes = tablaPacientes.querySelector('tbody');
    tbodyPacientes.addEventListener('dblclick', function() {
        SeleccionarPacienteToDelete();
    });

    var seleccionarPacienteTDBtn = document.getElementById('btn-ptd');
    seleccionarPacienteTDBtn.addEventListener('click', function() {SeleccionarPacienteToDeleteTD()
    });

    // Ejecutar SeleccionarPacienteToDeleteTD al hacer doble clic en la tabla-pacientestodelete
    var tablaPacientesTD = document.getElementById('tabla-pacientestodelete');
    var tbodyPacientesTD = tablaPacientesTD.querySelector('tbody');
    tbodyPacientesTD.addEventListener('dblclick', function() {
        SeleccionarPacienteToDeleteTD();
    });

    // Interceptar el submit del formulario del modal
    var form = document.getElementById('Form_ag');
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        // Obtener los IDs de los campos ocultos
        var idCorrecto = document.getElementById('p_id').value;
        var idEliminar = document.getElementById('p_id_td').value;

        // Crear el payload
        var payload = {
            id_correcto: idCorrecto,
            id_eliminar: idEliminar
        };

        fetch('/unificar_paciente', {
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
                localStorage.setItem('showUnificarToast', '1');
                window.location.reload();
            } else {
                alert('Error al unificar pacientes: ' + (data.message || '')); 
            }
        })
        .catch(err => {
            alert('Error de red o backend');
        });
    });

    // Mostrar toast si corresponde al cargar la página
    if (localStorage.getItem('showUnificarToast')) {
        showSuccessToast('Éxito', 'Pacientes unificados correctamente.');
        localStorage.removeItem('showUnificarToast');
    }
});
