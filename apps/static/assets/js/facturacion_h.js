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

function ConfigModalRetiro(){
    RellenarSelectCondicionalId('ref_med','username','public.tbuser','88e340f5-6fa5-4df1-aef6-c911625a4427','idrole')

    document.getElementById('type_of_retiro').addEventListener('change',function(){
        tipo = document.getElementById('type_of_retiro').value;
        console.log(tipo)
        if(tipo=='p_med'){
            document.getElementById('pago_medico').hidden=false
            document.getElementById('pago_insumo').hidden=true
            document.getElementById('pago_otros').hidden=true
            document.getElementById('pago_personal').hidden=true  
        }else if(tipo=='p_personal'){
            document.getElementById('pago_medico').hidden=true
            document.getElementById('pago_insumo').hidden=true
            document.getElementById('pago_otros').hidden=true
            document.getElementById('pago_personal').hidden=false 
        }else if(tipo=='p_otros'){
            document.getElementById('pago_medico').hidden=true
            document.getElementById('pago_insumo').hidden=true
            document.getElementById('pago_otros').hidden=false
            document.getElementById('pago_personal').hidden=true 
        }else if(tipo=='p_insumo'){
            document.getElementById('pago_medico').hidden=true
            document.getElementById('pago_insumo').hidden=false
            document.getElementById('pago_otros').hidden=true
            document.getElementById('pago_personal').hidden=true 
        }else{
            document.getElementById('pago_medico').hidden=true
            document.getElementById('pago_insumo').hidden=true
            document.getElementById('pago_otros').hidden=true
            document.getElementById('pago_personal').hidden=true 
        }
    });

    const form_modal = document.getElementById('Form_retirar');
    form_modal.addEventListener('submit', function(event) {
        event.preventDefault();
        if(tipo=='p_med'){
            refmed=document.getElementById('ref_med').value
            mount=document.getElementById('mount_med').value
            var body=JSON.stringify({
                tipo:tipo,
                refmed: refmed,
                mount: mount
            })
        }else if(tipo=='p_personal'){
            personal=document.getElementById('s_personal').value
            mount=document.getElementById('mount_personal').value
            var body=JSON.stringify({
                tipo:tipo,
                personal: personal,
                mount: mount
            })
        }else if(tipo=='p_insumo'){
            descripcion=document.getElementById('insumo').value
            mount=document.getElementById('mount_insumo').value
            var body=JSON.stringify({
                tipo:tipo,
                descripcion: descripcion,
                mount: mount
            })
        }else if(tipo=='p_otros'){
            descripcion=document.getElementById('otro').value
            mount=document.getElementById('mount_otro').value
            var body=JSON.stringify({
                tipo:tipo,
                descripcion: descripcion,
                mount: mount
            })
        }

        fetch(form_modal.action, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: body,
        })
        .then(response => response.json())
        .then(data => {
            console.log(data);
            var tabla = document.getElementById('tabla-ordenes');
            var tbody_ = tabla.querySelector('tbody');
            var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
            filaSeleccionada.remove()
            const modal = bootstrap.Modal.getInstance(document.getElementById('modal_fact_orden'));
            modal.hide();
            showToast('Perfecto!', 'Orden facturada Exitosamente:', "/static/templates/includes/toast/toast_success.html");
        }) 
        .catch(error => {
            console.error('Error:', error);
        });
    });
}


function toggleFields() {
    const isOsCheckbox = document.getElementById('IsOs');
    if (isOsCheckbox.checked) {
        osFields.forEach(field => field.removeAttribute('disabled'));
    } else {
        osFields.forEach(field => field.setAttribute('disabled', 'true'));
    }
}

function aplicarEstilosTipo(TablaId, columnaTipoIndex) {
    
    var tabla = document.getElementById(TablaId);
    var filas = tabla.querySelectorAll('tbody tr');
    console.log(filas)
    
    filas.forEach(function(fila) {
        var celdaTipo = fila.cells[columnaTipoIndex];
        var valorTipo = celdaTipo.textContent.trim();
        console.log(valorTipo)

        // Crear el badge basado en el valor del tipo
        const badge = document.createElement('span');
        badge.classList.add('badge', 'rounded-pill', 'px-3', 'py-2');

        if (valorTipo === 'true') {
            badge.classList.add('bg-success');
            badge.textContent = 'entry';
        } else if (valorTipo === 'false') {
            badge.classList.add('bg-danger');
            badge.textContent = 'out';
        }

        // Reemplazar el contenido de la celda con el badge
        celdaTipo.innerHTML = '';
        celdaTipo.appendChild(badge);
    });
}

document.addEventListener("DOMContentLoaded", function() {
    // configuracion de busqueda y llenado de tabla
    RellenarTabla('tabla-ordenes',`/get_historial_facturacion`)
    setTimeout(function() {
        aplicarEstilosTipo('tabla-ordenes', 1);
    }, 1000); 

    ConfigurarTabla('tabla-ordenes','botones_sp')
    RellenarSelect('medico_solicitante', 'description', 'public.isrequestingphysician')
    RellenarSelectCondicionalId('medico_referente','username','public.tbuser','88e340f5-6fa5-4df1-aef6-c911625a4427','idrole')
    ConfigFiltrarText('nombre_pat', 'tabla-ordenes',2)
    
    
    ConfigModalRetiro()
    // toggleFields()
    
    document.getElementById('b_retirar_efectivo').addEventListener('click',function(){
    
        var modal = new bootstrap.Modal(document.getElementById('modal_retirar_dinero'));
        modal.show();

    })



   
    
});
