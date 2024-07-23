

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
        console.log('Texto de la columna:', textoColumna);

        // Buscar la fila seleccionada en la otra tabla
        var tablaEstudiosSelec = document.getElementById('tabla-estudios-selec');
        var tbodyEstudiosSelec = tablaEstudiosSelec.querySelector('tbody');
        var filaSeleccionadaEstudiosSelec = tbodyEstudiosSelec.querySelector('tr.fila-seleccionada');

        if (filaSeleccionadaEstudiosSelec) {
            var columnasEstudiosSelec = filaSeleccionadaEstudiosSelec.querySelectorAll('td');
            columnasEstudiosSelec[2].textContent = textoColumna; // Insertar el texto en la tercera columna
        }
    } 
}

function generarOrdenes() {
    // Obtener la tabla de estudios seleccionados
    var tablaEstudiosSelec = document.getElementById('tabla-estudios-selec');
    var tbodyEstudiosSelec = tablaEstudiosSelec.querySelector('tbody');

    // Iterar sobre las filas de la tabla de estudios seleccionados
    tbodyEstudiosSelec.querySelectorAll('tr').forEach(fila => {
        // Obtener las columnas 1 y 2 de cada fila
        var columnas = fila.querySelectorAll('td');
        if (columnas.length >= 2) {
            var examenId = columnas[1].textContent.trim();
            var equipo = columnas[2].textContent.trim();

            // Verificar si el examen ya existe en OrderData.exams
            var examenExistente = OrderData.exams.find(examen => examen.examenId === examenId);

            if (examenExistente) {
                // Si el examen ya existe, actualizar sus valores
                examenExistente.equipo = equipo;
            } else {
                // Si el examen no existe, agregarlo como un nuevo objeto
                var examen = {
                    examenId: examenId,
                    equipo: equipo
                };
                OrderData.exams.push(examen);
            }
        } else {
            console.error('La fila seleccionada no tiene suficientes columnas.');
        }
    });

    // Mostrar OrderData para verificar los datos
    console.log('OrderData:', OrderData);
}

function FinalizarOrden() {
    // Obtener los valores seleccionados de los select
    const urgencia = document.getElementById('urgencia').value;
    const obraSocial = document.getElementById('obra_social').value;
    const medicoSolicitante = document.getElementById('medico_solicitante').value;

    // Asignar los valores a las propiedades correspondientes de OrderData
    OrderData.urgencia = urgencia;
    OrderData.obra_social = obraSocial;
    OrderData.medico_solicitante = medicoSolicitante;

    // Checkear si patientId está vacío
    if (!OrderData.patientId) {
        alert('Por favor, seleccione un paciente.');
        return;
    }

    // Checkear si exams está vacío
    if (OrderData.exams.length === 0) {
        alert('Por favor, seleccione al menos un examen.');
        return;
    }

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
        console.log('Orden enviada exitosamente:', data);
        // Aquí puedes agregar lógica adicional después de enviar la orden exitosamente
    })
    .catch(error => {
        console.error('Error:', error);
    });

    console.log('Datos de la orden finalizada:', OrderData);
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
    } else {
        li_dni.innerText = "No hay paciente seleccionado";
        divPaciente.classList.remove('bg-success'); // Remueve la clase de Bootstrap para fondo verde si no hay fila seleccionada
    }
} 


// Funcion de examenes 
function filtrar_estudios(){
    // Obtiene el valor seleccionado en el select
    var tipoExamenSelect = document.getElementById("tipo_examen");
    var filtro_modalidad = tipoExamenSelect.options[tipoExamenSelect.selectedIndex].innerText
    console.log(filtro_modalidad)
    tablaEstudios=document.getElementById("tabla-estudios");
    // Obtiene todas las filas de la tabla
    var filas = tablaEstudios.getElementsByClassName("patient-row");
 
    // Itera a través de las filas y las muestra u oculta según la selección
    for (var i = 1; i < filas.length; i++) {
       var fila = filas[i];
       var modalidad = fila.querySelector(".modalidad").textContent// Suponiendo que la modalidad está en la tercera columna
       
       // Compara la modalidad con la selección
       if ((filtro_modalidad === "Todas" || modalidad === filtro_modalidad)) {
          fila.style.display = "table-row"; // Muestra la fila
       } else {
          fila.style.display = "none"; // Oculta la fila
       }
    }

}
// Funcion de examenes 
function filtrar_por_partes(){
    // Obtiene el valor seleccionado en el select
    
    var seleccion = document.getElementById("parte_cuerpo").value;
    
    // Obtiene todas las filas de la tabla
    var filas = document.getElementsByClassName("patient-row");
 
    // Itera a través de las filas y las muestra u oculta según la selección
    for (var i = 0; i < filas.length; i++) {
       var fila = filas[i];
       var modalidad = fila.getElementsByTagName("td")[3].textContent; // Suponiendo que la modalidad está en la tercera columna
 
       // Compara la modalidad con la selección
       if (seleccion === "Todas" || modalidad === seleccion) {

          fila.style.display = "table-row"; // Muestra la fila
       } else {
          fila.style.display = "none"; // Oculta la fila
       }
       console.log(fila.style.display)
    }
 
}

function RellenarSelect(SelectId, dNeeded, TableId) {
    fetch('/rellenar_select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ dNeeded: dNeeded, TableId: TableId }),
    })
        .then(response => response.json())
        .then(data => {
            var selectElement = document.getElementById(SelectId);

            // Limpiar cualquier opción existente en el <select>
            selectElement.innerHTML = '';

            // Agregar la opción "Todas" al principio
            var todasOption = document.createElement('option');
            todasOption.value = 'Todas';
            todasOption.text = 'Todas';
            selectElement.appendChild(todasOption);

            // Llenar el <select> con las opciones de los datos
            for (var i = 0; i < data.data.length; i++) {
                var option = document.createElement('option');
                option.value = data.data[i][0];
                option.text = data.data[i][1];
                selectElement.appendChild(option);
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
}


function configSearchForm(FormId,action,TableId){
    var FormPacientes = document.getElementById(FormId);

    FormPacientes.addEventListener('submit', function(event) {
        // Evitar el envío predeterminado del formulario
        event.preventDefault();
        // Realizar la solicitud HTTP usando fetch
        fetch(action, {
            method: 'POST',  // Puedes cambiarlo a 'POST' si prefieres enviar datos en el cuerpo
            body: new FormData(FormPacientes)
        })
        .then(response => response.json())
        .then(data => {
            var tablaPacientes = document.getElementById(TableId);
            var tbody_ = tablaPacientes.querySelector('tbody');
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
    });
}

function ConfigTablaEstudios(Tabla1Id,Button1Id,Tabla2Id){
    var tablaEstudios = document.getElementById(Tabla1Id);
    var tbodyest = tablaEstudios.querySelector('tbody');

    var boton_sel = document.getElementById(Button1Id);
    boton_sel.addEventListener('click', AgregarEstudio);

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
        tbodyEstudiosSelec.appendChild(nuevaFila);
        filaSeleccionada.remove();
        
        // Restaura el estilo del botón
        boton_sel.classList.remove('btn-success');
        boton_sel.classList.add('btn-secondary');
        boton_sel.disabled = true;
        }
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


function ConfigTablaSeleccionados(Tabla1Id,Button1Id,Tabla2Id){
    var tbodyEquipos = document.getElementById('tbody-equipos');
    var tablaSelec = document.getElementById(Tabla1Id);
    var tbodySelec = tablaSelec.querySelector('tbody');
    
    var boton_quitar = document.getElementById(Button1Id);
    boton_quitar.addEventListener('click', QuitarEstudio);

    function QuitarEstudio() {
        var filaSeleccionadaSelec = tbodySelec.querySelector('.fila-seleccionada');
        console.log(filaSeleccionadaSelec.getAttribute('data-full'))
        
        if (filaSeleccionadaSelec) {
   
            // Ahora puedes continuar con el resto de la lógica para quitar el estudio seleccionado
            filaSeleccionadaSelec.classList.remove('fila-seleccionada');
    
            var tablaEstudios = document.getElementById(Tabla2Id);
            var tbodyEstudios = tablaEstudios.querySelector('tbody');
            var filaCompleta = document.createElement('tr');
            filaCompleta.innerHTML = filaSeleccionadaSelec.getAttribute('data-full')
            tbodyEstudios.appendChild(filaCompleta);
    
            // Quita la clase 'fila-seleccionada' de la fila original
            filaSeleccionadaSelec.remove();
            
            // Restaura el estilo del botón
            boton_quitar.classList.remove('btn-success');
            boton_quitar.classList.add('btn-secondary');
            boton_quitar.disabled = true;
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

    RellenarSelect("tipo_examen","Description","public.IsModality")
    RellenarSelect("parte_cuerpo","Description","public.IsAnatomicalPart")

    ConfigurarTabla('tabla-paciente','botones_sp')
    ConfigurarTabla('tabla-equipos-p-exam','sel_equip')

    var boton=document.getElementById("sel-equip")
    boton.addEventListener("click",function(){AsignarEquipo('tabla-equipos-p-exam')})

    // Prestacion

    RellenarSelect("medico_solicitante","Description","public.isrequestingphysician")
    RellenarSelect("obra_social","Description","public.ispricelist")

    var boton=document.getElementById("finalizar_orden")
    boton.addEventListener("click",function(){FinalizarOrden()})



    //-------------

    var boton=document.getElementById("generar-ordenes")
    boton.addEventListener("click",function(){generarOrdenes()})




    configSearchForm('search_patient','/buscar_pacientes2',"tabla-paciente")

    ConfigTablaEstudios('tabla-estudios','seleccionar-estudio','tabla-estudios-selec')
    ConfigTablaSeleccionados('tabla-estudios-selec','quitar-estudio','tabla-estudios','tabla-estudios-agenda')


    
    


    


    

})