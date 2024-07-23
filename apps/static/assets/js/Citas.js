
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

function ConfigTablaEstudios(Tabla1Id,Button1Id,Tabla2Id,TablaFinalId){
    var tablaEstudios = document.getElementById(Tabla1Id);
    var tbodyest = tablaEstudios.querySelector('tbody');

    var boton_sel = document.getElementById(Button1Id);
    boton_sel.addEventListener('click', AgregarEstudio);

    function AgregarEstudio() {
        var filaSeleccionada = tbodyest.querySelector('.fila-seleccionada');
        if (filaSeleccionada) {
        // Clona la fila seleccionada
        filaSeleccionada.classList.remove('fila-seleccionada');
        var filaClonada = filaSeleccionada.cloneNode(true);

        // Añade la fila clonada a la tabla de Estudios Seleccionados
        var tablaEstudiosSelec = document.getElementById(Tabla2Id);
        var tbodyEstudiosSelec = tablaEstudiosSelec.querySelector('tbody');
        tbodyEstudiosSelec.appendChild(filaClonada);


        //en esta seccion agrego el evento para la agenda
        var columnas = filaSeleccionada.getElementsByTagName('td');
        var contenidoColumna1 = columnas[0].textContent.trim(); // Contenido de la primera columna
        var contenidoColumna2 = columnas[1].textContent.trim();  

        
        var tablaEstudiosAgenda = document.getElementById(TablaFinalId);
        var tbodyEstudiosAgenda = tablaEstudiosAgenda.querySelector('tbody');
        var nuevaFila = document.createElement('tr');
        var nuevaColumna1 = document.createElement('td');
        var nuevaColumna2 = document.createElement('td');

        nuevaColumna1.textContent = contenidoColumna1;
        nuevaColumna2.textContent = contenidoColumna2;
        
        nuevaFila.appendChild(nuevaColumna1);
        nuevaFila.appendChild(nuevaColumna2);

        tbodyEstudiosAgenda.appendChild(nuevaFila);

        
        // Quita la clase 'fila-seleccionada' de la fila original
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


function CrearPosibleCita(Tabla1Id,Button1Id){

    console.log("estoy entrando")
    var tablaEstudios = document.getElementById(Tabla1Id);
    var tbodyest = tablaEstudios.querySelector('tbody');

    var boton_sel = document.getElementById(Button1Id);

    var filaSeleccionada = tbodyest.querySelector('.fila-seleccionada');
    if (filaSeleccionada) {
    // Clona la fila seleccionada
    filaSeleccionada.classList.remove('fila-seleccionada');
    var filaClonada = filaSeleccionada.cloneNode(true);
    var estudioSeleccionado = filaClonada.cells[1].textContent;
    var codigo = filaClonada.cells[0].textContent;

    // Quita la clase 'fila-seleccionada' de la fila original
    filaSeleccionada.remove();
    
    // Restaura el estilo del botón
    boton_sel.classList.remove('btn-success');
    boton_sel.classList.add('btn-secondary');
    boton_sel.disabled = true;
    }

    //Aqui necesito colocar un bloque HTML con la posible cita. Esto es un card
    var citaContainer = document.getElementById('cita_conteiner'); // Reemplaza 'cita-container' con el ID adecuado de tu contenedor
    var nuevaCita = document.createElement('div');
    nuevaCita.classList.add('row', 'cita');
    nuevaCita.innerHTML = `
    <div class="row" class="cita">
    <div class="col-12">
    <div class="card mb-4 shadow">
        <div class="card-header pb-0">
            <div class="row">
                <div class="col-md-12">
                    <h6>${estudioSeleccionado}</h6>
                </div>
            </div> 
        </div>

        <div class="card-body card-tabla-cita px-0 pt-0 pb-2">
            <div class="row">
                <div class="col-md-6">
                    <div class="row">
                        <div class="col-md-6">
                            <label for="">
                                Equipo deseado:
                            </label>
                        </div>
                        <div class="col-md-6">
                            <select id="s_${codigo}" name="s_${codigo}" class="equip_select">
                            </select>
                        </div>
                    </div>   
                </div>

                <div class="col-md-6">
                    <div class="row">
                        <div class="col-md-6">
                            <label for="wd_${codigo}">
                                Fecha deseada:
                            </label>
                        </div>
                        <div class="col-md-6">
                            <input type="date" id="wd_${codigo}" name="wd_${codigo}" min="2023-01-01" max="2024-12-31" />
                        </div>
                    </div>   
                </div>
            </div>

        </div> 


            </div>
        </div>
    </div>
    `;
    // RellenarSelect(SelectId, dNeeded, TableId)

    // Agrega la nueva cita al contenedor
    citaContainer.appendChild(nuevaCita);
    SelectId="s_"+codigo
    RellenarSelect(SelectId, "AETitle", "public.IsEquipment")


}

function ConfigTablaSeleccionados(Tabla1Id,Button1Id,Tabla2Id,TablaFinalId){
    var tablaSelec = document.getElementById(Tabla1Id);
    var tbodySelec = tablaSelec.querySelector('tbody');
    
    var boton_quitar = document.getElementById(Button1Id);
    boton_quitar.addEventListener('click', QuitarEstudio);

    function QuitarEstudio() {
        var filaSeleccionadaSelec = tbodySelec.querySelector('.fila-seleccionada');
        
        if (filaSeleccionadaSelec) {
            // Obtén la información de las columnas 1 y 2 de la fila seleccionada
            var columnas = filaSeleccionadaSelec.getElementsByTagName('td');
            var contenidoColumna1 = columnas[0].textContent.trim();
            
            
            var tablaEstudiosAgenda = document.getElementById(TablaFinalId);
            var tbodyEstudiosAgenda = tablaEstudiosAgenda.querySelector('tbody');
            var filasAgenda = tbodyEstudiosAgenda.querySelectorAll('tr');
    
            for (var i = 0; i < filasAgenda.length; i++) {
                var filaAgenda = filasAgenda[i];
                var columnasAgenda = filaAgenda.getElementsByTagName('td');
                var contenidoColumna1Agenda = columnasAgenda[0].textContent.trim();
    
                // Compara el contenido de las columnas de la fila seleccionada y la fila de la tabla-estudios-agenda
                if (contenidoColumna1 === contenidoColumna1Agenda) {
                    // Si coinciden, elimina la fila de la tabla-estudios-agenda
                    filaAgenda.remove();
                    break;  // No es necesario seguir buscando
                }
            }
    
            // Ahora puedes continuar con el resto de la lógica para quitar el estudio seleccionado
            filaSeleccionadaSelec.classList.remove('fila-seleccionada');
            var filaClonada = filaSeleccionadaSelec.cloneNode(true);
    
            var tablaEstudios = document.getElementById(Tabla2Id);
            var tbodyEstudios = tablaEstudios.querySelector('tbody');
            tbodyEstudios.appendChild(filaClonada);
    
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

    var boton=document.getElementById("b_sel_pac_para_cita")
    boton.addEventListener("click",function(){SeleccionarPaciente('tabla-paciente')})

    RellenarSelect("tipo_examen","Description","public.IsModality")
    RellenarSelect("parte_cuerpo","Description","public.IsAnatomicalPart")

    ConfigurarTabla('tabla-paciente','botones_sp')
    ConfigurarTabla('tabla-estudios','boton_est')
    configSearchForm('search_patient','/buscar_pacientes2',"tabla-paciente")

    // ConfigTablaEstudios('tabla-estudios','seleccionar-estudio','tabla-estudios-selec','tabla-estudios-agenda')
    // ConfigTablaSeleccionados('tabla-estudios-selec','quitar-estudio','tabla-estudios','tabla-estudios-agenda')

    var boton=document.getElementById("seleccionar-estudio")
    boton.addEventListener("click",function(){CrearPosibleCita('tabla-estudios',"seleccionar-estudio")})
    
    


    


    

})