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

function VolverAtras() {
    $('#card_ordenes').show();
    $('#card_buscar').show();
    $('#data').remove(); // Eliminar el elemento #data
}


function Facturar(){
    var tabla = document.getElementById('tabla-pacientes');
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    
    if (filaSeleccionada) {
        var dataId = filaSeleccionada.getAttribute('data-id');
        var name = filaSeleccionada.children[2].textContent.trim(); // Obtener el contenido del tercer td
        var mail = filaSeleccionada.children[3].textContent.trim(); // Obtener el contenido del cuarto td
    }
}

function ConfigModalOs(){
    RellenarSelect('os','description','public.ispricelist');

    document.getElementById('mount_os').addEventListener('change',function(){
        tipo = document.getElementById('type_os').value;
        let cobertura = 0;

        if (tipo === 'porcentual'){
            cobertura = document.getElementById('price_order').value * document.getElementById('mount_os').value / 100;
            document.getElementById('cover').value = cobertura;
            document.getElementById('to_bill').value = document.getElementById('price_order').value - cobertura;
        } else {
            cobertura = document.getElementById('mount_os').value;
            document.getElementById('cover').value = cobertura;
        }
        document.getElementById('to_bill').value = document.getElementById('price_order').value - cobertura;
    });

    const isOsCheckbox = document.getElementById('IsOs');
    isOsCheckbox.addEventListener('change', function(){
        toggleFields();
    });

    const form_modal = document.getElementById('Form_factura');
    form_modal.addEventListener('submit', function(event) {
        event.preventDefault();

        const totalcost = document.getElementById('price_order').value;
        const os = document.getElementById('os').value;
        const oscover = document.getElementById('cover').value;
        const id_examination = document.getElementById('id_order').value;
        const billnotes= document.getElementById('bill_notes').value;

        fetch(form_modal.action, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                os:os,
                totalcost: totalcost,
                oscover: oscover,
                id_examination: id_examination,
                billnotes:billnotes
            }),
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
            // Mantén el modal visible si hay un error
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
const osFields = document.querySelectorAll('#os, #type_os, #mount_os');
document.addEventListener("DOMContentLoaded", function() {
    // configuracion de busqueda y llenado de tabla
    RellenarTabla('tabla-ordenes',`/get_orders_to_bill`)
    ConfigurarTabla('tabla-ordenes','botones_sp')
    RellenarSelect('medico_solicitante', 'description', 'public.isrequestingphysician')
    RellenarSelectCondicionalId('medico_referente','username','public.tbuser','88e340f5-6fa5-4df1-aef6-c911625a4427','idrole')
    ConfigFiltrarText('nombre_pat', 'tabla-ordenes',2)

    
    ConfigModalOs()
    toggleFields()
    
    document.getElementById('b_facturar').addEventListener('click',function(){
        var tabla = document.getElementById('tabla-ordenes');
        var tbody_ = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
        
        
        if (filaSeleccionada) {
            var dataId = filaSeleccionada.getAttribute('data-id');
            document.getElementById('id_order').value=dataId
            var orden = filaSeleccionada.children[1].textContent.trim(); // Obtener el contenido del tercer td
            var paciente = filaSeleccionada.children[2].textContent.trim(); // Obtener el contenido del cuarto td
            var os = filaSeleccionada.children[4].textContent.trim(); // Obtener el contenido del cuarto td
            var precio = filaSeleccionada.children[7].textContent.trim(); // Obtener el contenido del cuarto td
        }
        
        document.getElementById('os').value=os
        document.getElementById('price_order').value=precio
        var modal = new bootstrap.Modal(document.getElementById('modal_fact_orden'));

        modal.show();

    })



   
    
});
