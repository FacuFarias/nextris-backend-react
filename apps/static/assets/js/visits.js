

//Objeto con datos de la orden
let OrderData = {
    patientId: null,
    exams:[],
    urgencia: null,
    medico_solicitante: null,
    obra_social:null,
};

function AsignarEquipo(TablaId) {
    var tabla = document.getElementById(TablaId);
    var tbody_g = tabla.querySelector('tbody');

    var filaSeleccionada = tbody_g.querySelector('tr.fila-seleccionada');
    if (filaSeleccionada) {
        var columna = filaSeleccionada.querySelector('td');
        var textoColumna = columna.textContent.trim();
        var idequip = filaSeleccionada.getAttribute('data-id');
        console.log('Id del equipo:', textoColumna);

        // Buscar la fila seleccionada en la otra tabla
        var tablaEstudiosSelec = document.getElementById('tabla-estudios-selec');
        var tbodyEstudiosSelec = tablaEstudiosSelec.querySelector('tbody');
        var filaSeleccionadaEstudiosSelec = tbodyEstudiosSelec.querySelector('tr.fila-seleccionada');

        if (filaSeleccionadaEstudiosSelec) {
            var columnasEstudiosSelec = filaSeleccionadaEstudiosSelec.querySelectorAll('td');
            columnasEstudiosSelec[2].textContent = textoColumna; // Insertar el texto en la tercera columna
            var idExam = filaSeleccionadaEstudiosSelec.getAttribute('data-id');
            var examenExistente = OrderData.exams.find(examen => examen.examId === idExam);
            if (examenExistente) {
                examenExistente.equip = idequip;
            }

            // Iterar sobre la tabla-estudios-selec para verificar si todas las filas tienen asignado un equipo
            var todasAsignadas = true;
            var filas = tbodyEstudiosSelec.querySelectorAll('tr');
            filas.forEach(fila => {
                var columnas = fila.querySelectorAll('td');
                if (!columnas[2].textContent.trim()) {
                    todasAsignadas = false;
                }
            });

            if (todasAsignadas) {
                var divExamen = document.getElementById('pills-examen-tab');
                divExamen.classList.add('bg-success');
                divExamen.classList.remove('bg-danger');
            }
        }
    }
}



function FinalizarOrden() {
    var pillPaciente = document.getElementById('pills-paciente-tab');
    var pillExamen = document.getElementById('pills-examen-tab');

    // Verificar si los objetos tienen la clase 'bg-success'
    var allSuccess = true;
    var messages = [];

    if (!pillPaciente.classList.contains('bg-success')) {
        pillPaciente.classList.add('bg-danger');
        messages.push("No se ha seleccionado paciente");
        allSuccess = false;
    }

    if (!pillExamen.classList.contains('bg-success')) {
        pillExamen.classList.add('bg-danger');
        messages.push("No se ha seleccionado examen");
        allSuccess = false;
    }

    if (allSuccess) {
        // Enviar OrderData al backend si todos los datos están completos
        fetch('/crear_worklist', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(OrderData)
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error('Error en el envío de la orden.');
            }
        })
        .then(data => {
            showToast('Perfecto!', 'Orden creada exitosamente:', "/templates/includes/toast/toast_success.html");
            // Limpiar OrderData
            OrderData.patientId = null;
            OrderData.exams = [];
            OrderData.medico_solicitante = null;
            OrderData.obra_social = null;
            // Aquí puedes agregar lógica adicional después de enviar la orden exitosamente

            // Vaciar la tabla de estudios seleccionados
            var tablaEstudiosSelec = document.getElementById('tabla-estudios-selec');
            var tbodyEstudiosSelec = tablaEstudiosSelec.querySelector('tbody');
            while (tbodyEstudiosSelec.firstChild) {
                tbodyEstudiosSelec.removeChild(tbodyEstudiosSelec.firstChild);
            }

            // Rellenar nuevamente tabla-estudios
            RellenarTabla('tabla-estudios', `/get_exams_adm`);

            // Remover clases de éxito en las pestañas
            var pillPaciente = document.getElementById('pills-paciente-tab');
            var pillExamen = document.getElementById('pills-examen-tab');

            pillPaciente.classList.remove('bg-success', 'bg-danger');
            pillExamen.classList.remove('bg-success', 'bg-danger');

            // Activar la pestaña de paciente
            var pillPacienteButton = document.querySelector('[data-bs-target="#pills-paciente"]');
            var tab = new bootstrap.Tab(pillPacienteButton);
            tab.show();

            // Remover la clase fila-seleccionada de cualquier fila en la tabla-paciente
            var tablaPaciente = document.getElementById('tabla-paciente');
            var filasSeleccionadas = tablaPaciente.querySelectorAll('.fila-seleccionada');
            filasSeleccionadas.forEach(fila => {
                fila.classList.remove('fila-seleccionada');
            });
        })
        .catch(error => {
            console.error('Error:', error);
        });

        console.log('Datos de la orden finalizada:', OrderData);
    } else {
        // Mostrar el toast con los mensajes de error
        showToast('Ha ocurrido un problema', messages.join('<br>'), "/templates/includes/toast/toast_alert.html");
    }
    
}
function RellenarTabla(TablaId, route) {
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    fetch(route)
        .then(response => response.json())
        .then(data => {
            tbody_.innerHTML = '';
            // Iterar sobre los datos y agregar filas a la tabla
            data.forEach(function (item) {
                var row = document.createElement('tr');
                row.dataset.id = item[0];

                // Iterar sobre los elementos de item (omitir el primer elemento) y agregar un <td> por cada uno
                for (var i = 1; i < item.length; i++) {
                    var cell = document.createElement('td');
                    if ((item[i]===0)||(item[i]===1)){             
                        const checkbox = document.createElement('input');
                        checkbox.type = 'checkbox';
                        checkbox.classList.add('form-check-input')
                        
                        checkbox.checked = item[i]
                        checkbox.style.opacity = 2;
                        checkbox.disabled = true;
                        
                        cell.appendChild(checkbox);
                    
                    } else {
                        // Para otras columnas, simplemente agrega el texto
                        cell.textContent = item[i];
                    }

                    row.appendChild(cell);
                }

                tbody_.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error:', error);
        });
}
//Esta funcion selecciona o deselecciona la fila, y agrega clickeable o ono a los botones)

function ConfigurarTabla(TablaId,botonesClass){
    
    var tabla = document.getElementById(TablaId);
    var tbody_g= tabla.querySelector('tbody');
    tbody_g.addEventListener('click', function (event) {
        var filas = tbody_g.querySelectorAll('tr');
        for (var i = 0; i < filas.length; i++) {
            filas[i].classList.remove('fila-seleccionada');
        }
        
        var fila = event.target.closest('tr');
        if (fila) {
            fila.classList.add('fila-seleccionada');            
            var botones = document.getElementsByClassName(botonesClass);
            for (var i = 0; i < botones.length; i++) {
                var boton = botones[i];
                boton.disabled = false;
        
                // Verificar si el botón tiene la clase 'delete_b'
                if (boton.classList.contains('delete_b')) {
                    boton.classList.remove('btn-secondary');
                    boton.classList.add('btn-danger');
                } else {
                    boton.classList.remove('btn-secondary');
                    boton.classList.add('btn-success');
                }
            }
        } else {
            var botones = document.getElementsByClassName('botones');
            for (var i = 0; i < botones.length; i++) {
                var boton = botones[i];
                boton.disabled = true;
                
        
                // Verificar si el botón tiene la clase 'delete_b'
                if (boton.classList.contains('delete_b')) {
                    boton.classList.remove('btn-danger');
                    boton.classList.add('btn-secondary');
                } else {
                    boton.classList.remove('btn-success');
                    boton.classList.add('btn-secondary');
                }
            }
        }
        
    });
}

function SeleccionarPaciente(TablaId){
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    var li_dni = document.getElementById('dni-item');
    var divPaciente = document.getElementById('pills-paciente-tab');

    if (filaSeleccionada) {
        console.log(filaSeleccionada.dataset.id)
        OrderData.patientId=filaSeleccionada.dataset.id
        var tds = filaSeleccionada.querySelectorAll('td');
        li_dni.innerText = "Paciente seleccionado: " + tds[0].innerText + ", " + tds[1].innerText;
        divPaciente.classList.add('bg-success'); // Agrega la clase de Bootstrap para fondo verde
        divPaciente.classList.remove('bg-danger'); // Agrega la clase de Bootstrap para fondo verde
    } else {
        li_dni.innerText = "No hay paciente seleccionado";
        divPaciente.classList.remove('bg-success'); // Remueve la clase de Bootstrap para fondo verde si no hay fila seleccionada
    }
} 

function ConfigTablaEstudios(Tabla1Id,Button1Id,Tabla2Id){
    var tablaEstudios = document.getElementById(Tabla1Id);
    var tbodyest = tablaEstudios.querySelector('tbody');

    var boton_sel = document.getElementById(Button1Id);
    boton_sel.addEventListener('click', AgregarEstudio);
    document.getElementById(Tabla1Id).addEventListener("dblclick",AgregarEstudio)

    function AgregarEstudio() {
        var filaSeleccionada = tbodyest.querySelector('.fila-seleccionada');
        if (filaSeleccionada) {
        // Clona la fila seleccionada
        filaSeleccionada.classList.remove('fila-seleccionada');
        var fullRowData = filaSeleccionada.innerHTML;

        // Añade la fila clonada a la tabla de Estudios Seleccionados
        var tablaEstudiosSelec = document.getElementById(Tabla2Id);
        var tbodyEstudiosSelec = tablaEstudiosSelec.querySelector('tbody');
        var columnas = filaSeleccionada.getElementsByTagName('td');
        var contenidoColumna1 = columnas[0].textContent.trim(); // Contenido de la primera columna
        var contenidoColumna2 = columnas[1].textContent.trim(); 
        var nuevaFila = document.createElement('tr');
        nuevaFila.innerHTML = `<td>${contenidoColumna1}</td><td>${contenidoColumna2}</td><td></td>`;
        nuevaFila.setAttribute('data-full',fullRowData)

        var idExam=filaSeleccionada.getAttribute('data-id');
        nuevaFila.setAttribute('data-id',idExam)
        tbodyEstudiosSelec.appendChild(nuevaFila);

        // Restaura el estilo del botón de agregar estudio
        boton_sel.classList.remove('btn-success');
        boton_sel.classList.add('btn-secondary');
        boton_sel.disabled = true;
        }

        // var divExamen = document.getElementById('pills-examen-tab');
        // divExamen.classList.add('bg-success');
        // divExamen.classList.remove('bg-danger');
        var columnas = filaSeleccionada.querySelectorAll('td');
        var codigoEst = columnas[0].textContent.trim(); // Contenido de la primera columna
        var descEst = columnas[1].textContent.trim();
        
        var examen = {
            examId: idExam,
            title:codigoEst + " - " + descEst
        }
        OrderData.exams.push(examen);
        
        // Ahora creo una card
        fetch('/get_block_prestacion')
        .then(response => response.text())
        .then(data => {
            var container = document.getElementById('conteiner_blocks_prest');
            console.log("idprefixxxxx: ",codigoEst)
            var idPrefix = codigoEst
            var uniqueIdMedicoSolicitante = `${idPrefix}_ms`;
            var uniqueIdObraSocial = `${idPrefix}_os`;
            var insertId=`id='${idExam}'`
            // console.log("dataid holam:",idExam)
            var cardHtml = data
                .replace('<!-- IdEstudio -->', examen.title)
                .replace('id="cardId"', insertId)
                .replace('class="form-control medico_solicitante"', `class="form-control medico_solicitante"" id="${uniqueIdMedicoSolicitante}" name="${uniqueIdMedicoSolicitante}"`)
                .replace('class="form-control obra_social"', `class="form-control obra_social" id="${uniqueIdObraSocial}" name="${uniqueIdObraSocial}"`);
                
            container.insertAdjacentHTML('beforeend', cardHtml);

            // Añadir event listeners a los selects creados
            console.log("medico solicitante: "+uniqueIdMedicoSolicitante)
            document.getElementById(uniqueIdMedicoSolicitante).addEventListener('change', function(event) {
                console.log('Cambio en medico solicitante:', event.target.id);
                codigo=event.target.id.substring(0, 3)
                OrderData.exams.forEach(function(examen){
                    var idPrefix = examen.title.substring(0, 3)
                    console.log("idprefix:",idPrefix)
                    if(idPrefix==codigo){
                        examen.medico_solicitante=document.getElementById(event.target.id).value
                    }
                })
            });
            document.getElementById(uniqueIdObraSocial).addEventListener('change', function(event) {
                console.log('Cambio en obra social:', event.target.id);
                codigo=event.target.id.substring(0, 3)
                OrderData.exams.forEach(function(examen){
                    var idPrefix = examen.title.substring(0, 3)
                    if(idPrefix==codigo){
                        examen.obra_social=document.getElementById(event.target.id).value
                    }
                })
            });
            
            RellenarSelectByClass("medico_solicitante","Description","public.isrequestingphysician")
            RellenarSelectByClass("obra_social","Description","public.ispricelist")

        })
        .catch(error => {
            console.error('Error al cargar el archivo block_prestacion.html:', error);
        });


        filaSeleccionada.remove();
    }

    tbodyest.addEventListener('click', function (event) {
        var filas = tbodyest.querySelectorAll('tr');
        for (var i = 0; i < filas.length; i++) {
            filas[i].classList.remove('fila-seleccionada');
        }

        var fila = event.target.closest('tr');
        if (fila) {
            fila.classList.add('fila-seleccionada');

            boton_sel.classList.remove('btn-secondary');
            boton_sel.classList.add('btn-success');
            boton_sel.disabled = false;
            
        } else {
            boton_sel.classList.remove('btn-success');
            boton_sel.classList.add('btn-secondary');
            boton_sel.disabled = true;
        }
    });

}

function ConfigTablaSeleccionados(Tabla1Id, Button1Id, Tabla2Id) {
    var tbodyEquipos = document.getElementById('tbody-equipos');
    var tablaSelec = document.getElementById(Tabla1Id);
    var tbodySelec = tablaSelec.querySelector('tbody');
    
    var boton_quitar = document.getElementById(Button1Id);
    boton_quitar.addEventListener('click', QuitarEstudio);

    document.getElementById(Tabla1Id).addEventListener("dblclick", QuitarEstudio);

    function QuitarEstudio() {
        var filaSeleccionadaSelec = tbodySelec.querySelector('.fila-seleccionada');
        console.log(filaSeleccionadaSelec.getAttribute('data-full'));

        if (filaSeleccionadaSelec) {
            // Obtener el id del examen a eliminar
            var data2delete = filaSeleccionadaSelec.getAttribute('data-id');
            filaSeleccionadaSelec.classList.remove('fila-seleccionada');

            // Mover la fila de vuelta a la tabla de estudios disponibles
            var tablaEstudios = document.getElementById(Tabla2Id);
            var tbodyEstudios = tablaEstudios.querySelector('tbody');
            var filaCompleta = document.createElement('tr');
            filaCompleta.innerHTML = filaSeleccionadaSelec.getAttribute('data-full');
            tbodyEstudios.appendChild(filaCompleta);

            // Restaurar el estilo del botón
            boton_quitar.classList.remove('btn-success');
            boton_quitar.classList.add('btn-secondary');
            boton_quitar.disabled = true;

            // Eliminar de OrderData
            console.log("data2delete:", data2delete);
            OrderData.exams = OrderData.exams.filter(examen => examen.examId !== data2delete);

            // Quitar la fila seleccionada
            filaSeleccionadaSelec.remove();

            // Verificar si no queda ningún tr en tbodySelec
            console.log(tbodySelec.querySelectorAll('tr').length)
            if (tbodySelec.querySelectorAll('tr').length == 0) {
                var divExamen = document.getElementById('pills-examen-tab');
                divExamen.classList.remove('bg-success');
            }
        }
    }

    tbodySelec.addEventListener('click', function (event) {
        var filas = tbodySelec.querySelectorAll('tr');
        for (var i = 0; i < filas.length; i++) {
            filas[i].classList.remove('fila-seleccionada');
        }

        var fila = event.target.closest('tr');
        if (fila) {
            fila.classList.add('fila-seleccionada');
            const columnas = fila.getElementsByTagName('td');
            
            var exam_orden = columnas[1].textContent.trim();

            final_route = "/get_equip_for_exam?exam=" + exam_orden;
            
            fetch(final_route)
                .then(response => response.json())
                .then(data => {
                    tbodyEquipos.innerHTML = '';
                    // Llenar la tabla con los datos recibidos
                    data.forEach(item => {
                        const nuevaFila = document.createElement('tr');
                        nuevaFila.setAttribute('data-id', item[0]); // Almacenar el primer valor como ID
                        nuevaFila.innerHTML = `<td>${item[1]}</td>`; // Mostrar solo el segundo valor
                        tbodyEquipos.appendChild(nuevaFila);
                    });
                })
                .catch(error => {
                    console.error('Error:', error);
                });

            boton_quitar.classList.remove('btn-secondary');
            boton_quitar.classList.add('btn-success');
            boton_quitar.disabled = false;
            
        } else {
            boton_quitar.classList.remove('btn-success');
            boton_quitar.classList.add('btn-secondary');
            boton_quitar.disabled = true;
        }
    });
}

document.addEventListener("DOMContentLoaded", function() {

    var boton=document.getElementById("b_sel_pac_para_adm")
    boton.addEventListener("click",function(){SeleccionarPaciente('tabla-paciente')})

    RellenarTabla('tabla-estudios',`/get_exams_adm`)
    RellenarTabla('tabla-paciente',`/get_patients_min`)
    ConfigFiltrarText('l_exam', 'tabla-estudios',1)
    ConfigurarTabla('tabla-paciente','botones_sp')
    ConfigurarTabla('tabla-equipos-p-exam','sel_equip')

    var boton=document.getElementById("sel-equip")
    boton.addEventListener("click",function(){AsignarEquipo('tabla-equipos-p-exam')})
    document.getElementById('tabla-equipos-p-exam').addEventListener("dblclick",function(){AsignarEquipo('tabla-equipos-p-exam')})

    // Prestacion

    // RellenarSelect("medico_solicitante","Description","public.isrequestingphysician")
    // RellenarSelect("obra_social","Description","public.ispricelist")

    var boton=document.getElementById("finalizar_orden")
    boton.addEventListener("click",function(){FinalizarOrden()})

    //-------------


    ConfigTablaEstudios('tabla-estudios','seleccionar-estudio','tabla-estudios-selec')
    ConfigTablaSeleccionados('tabla-estudios-selec','quitar-estudio','tabla-estudios','tabla-estudios-agenda')

    const cbSameInfo = document.getElementById('cb_same_info');
    const cbIcon = document.getElementById('cb_icon');
    const collapseTarget = document.getElementById('allin1');
    var blPrestElements = document.querySelectorAll('.bl_prest');

    cbIcon.addEventListener('click', function() {
    cbSameInfo.checked = !cbSameInfo.checked;
    cbIcon.classList.toggle('fa-toggle-on', cbSameInfo.checked);
    cbIcon.classList.toggle('fa-toggle-off', !cbSameInfo.checked);

    if (cbSameInfo.checked) {
        $(collapseTarget).collapse('show');
        blPrestElements = document.querySelectorAll('.bl_prest');
        blPrestElements.forEach(function(element) {
            element.classList.add('hidden');
            element.classList.remove('visible');
        });
    } else {
        $(collapseTarget).collapse('hide');
        blPrestElements = document.querySelectorAll('.bl_prest');
        blPrestElements.forEach(function(element) {
            element.classList.add('visible');
            element.classList.remove('hidden');
        });
    }
    });
    
    document.getElementById('general_ms').addEventListener('change', function(event) {
        console.log('Cambio en medico solicitante:', event.target.id);
        codigo=event.target.id.substring(0, 3)
        OrderData.exams.forEach(function(examen){
            examen.medico_solicitante=document.getElementById(event.target.id).value
        })
    });
    document.getElementById('general_os').addEventListener('change', function(event) {
        console.log('Cambio en obra social:', event.target.id);
        codigo=event.target.id.substring(0, 3)
        OrderData.exams.forEach(function(examen){
            
            examen.obra_social=document.getElementById(event.target.id).value
        })
    });
   

})
