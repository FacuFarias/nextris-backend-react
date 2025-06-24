function GenerarInforme(TablaId) {
    var tabla = document.getElementById(TablaId);
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');
    
    if (filaSeleccionada) {
        var dataId = filaSeleccionada.getAttribute('data-id');
        
        // Extraer el nombre del paciente de la segunda columna
        var nombrePaciente = filaSeleccionada.querySelectorAll('td')[1].textContent.trim();
        var examen = filaSeleccionada.querySelectorAll('td')[4].textContent.trim();
        
        // Cargar el contenido HTML del archivo y establecer el data-id
        $.get('/generacion_informe.html', function(data) {
            // Reemplazar los marcadores en el contenido HTML
            var informeContent = `
              <div class="informe-details" id="data" data-id="${dataId}">
                ${data} <!-- Contenido del archivo generacion_informe.html -->
              </div>
            `;
            // Reemplazar el marcador de nombre del paciente y examen
            informeContent = informeContent.replace('<!--Nombre del paciente-->', nombrePaciente);
            informeContent = informeContent.replace('<!--examen-->', examen);

            // Obtener datos del backend
            $.ajax({
                url: '/get_data_report', // URL de tu API
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ id: dataId }),
                success: function(response) {
                    
                    var report = response.report[0]; // El reporte debería ser la primera entrada en la lista
                    var isreported = response.isreported[0]; // El estado de IsReported debería ser la primera entrada en la lista
                    console.log("isreported:",isreported[0])
                    // Reemplazar los campos de texto en el contenido HTML
                    informeContent = informeContent.replace('<!--AdmNumber-->', report[2]);
                    informeContent = informeContent.replace('<!--Pregunta clínica-->', report[7]);
                    informeContent = informeContent.replace('<!--Tecnicas de examen-->', report[4]);
                    informeContent = informeContent.replace('<!--Informe-->', report[5]);
                    informeContent = informeContent.replace('<!--Conclusión-->', report[6]);
                    // Insertar el contenido HTML en el contenedor
                    $('#informe-content').html(informeContent);
                    $('#informe-content').attr('data-id', dataId);
                    if(isreported[0]==1){
                        
                        document.getElementById('text_pc').disabled = true;
                        document.getElementById('text_te').disabled = true;
                        document.getElementById('text_inf').disabled = true;
                        document.getElementById('text_conc').disabled = true;
                        document.getElementById('b_firmar_reporte').textContent = "Quitar definitivo";
                        document.getElementById('b_firmar_reporte').addEventListener('click', function() {
                            if (confirm('¿Estás seguro de que quieres quitar el definitivo?')) {
                                QuitarDefinitivo();
                            }
                        });
                        // Voy a ocupar este boton para ver el pdf
                        document.getElementById('b_guardar_reporte').textContent = "Guardar Reporte";
                        document.getElementById('b_guardar_reporte').disabled=true
                        alert("Este examen ya está firmado. No se puede editar")
                    }else{

                    var botonVerPdf = document.getElementById('b_ver_pdf');
                    botonVerPdf.disabled = false;
                        // Agregar el event listener al botón guardar_reporte
                        


                    document.getElementById('b_firmar_reporte').addEventListener('click', function() {
                        GuardarReporte();
                        FirmarReporte();

                    });

                    }
                    document.getElementById('b_ver_imagenes').addEventListener('click', function() {
                        VerImagenes();
                    });


                    document.getElementById('b_ver_pdf').addEventListener('click', function() {
                        VerPDF();
                    });

                    document.getElementById('b_atras_report').addEventListener('click', function() {
                        if (confirm('¿Estás seguro de que quieres volver atrás? Se eliminarán los cambios realizados.')) {
                            VolverAtras();
                        }
                    });

                    document.getElementById('b_toggle_collapse').addEventListener('click', function () {
                        ConfigBtnDatos()
                    });

                    document.getElementById('b_tecnicas_expand').addEventListener('click', function () {
                        ConfigBtnExpand('card-tecnicas','collapse_tecnicas','collapse_conclusion','b_tecnicas_expand','card-conclusion')
                    });

                    document.getElementById('b_conclusion_expand').addEventListener('click', function () {
                        ConfigBtnExpand('card-conclusion','collapse_conclusion','collapse_tecnicas','b_conclusion_expand','card-tecnicas')
                    });
                
                    
                },
                error: function() {
                    console.error('Error al obtener los datos del informe');
                }
            });
        }).fail(function() {
            console.error('Error al cargar el archivo generacion_informe.html');
        });

        // Ocultar los elementos #card_ordenes y #card_buscar
        $('#card_ordenes').hide();
        $('#card_buscar').hide();

    } else {
        console.log('No hay fila seleccionada.');
    }
}


function ConfigBtnExpand(CardId,colapseShowId,collapseId,btnId,otherCardId){
    var collapseElement = document.getElementById(collapseId);
    var colapseShow = document.getElementById(colapseShowId);
    var iconElement = document.getElementById(btnId).querySelector('i'); // Selecciona el icono dentro del botón
    var card = document.getElementById(CardId); // Contenedor del informe
    var othercard = document.getElementById(otherCardId); // Contenedor del informe
    

    if (collapseElement.classList.contains('show')) {
        collapseElement.classList.remove('show');
        colapseShow.classList.add('show');
        iconElement.classList.remove('fa-expand-arrows-alt'); // Cambia el icono a flecha hacia abajo
        iconElement.classList.add('fa-crosshairs');
        card.classList.add('expand-card');
        othercard.classList.remove('expand-card');
        console.log("expando")
    } else {
        collapseElement.classList.add('show');
        iconElement.classList.remove('fa-crosshairs'); // Cambia el icono a flecha hacia arriba
        iconElement.classList.add('fa-expand-arrows-alt');
        card.classList.remove('expand-card');
        console.log("contraigo")
    }

}


function ConfigBtnDatos(){

    //con esto controlo el collapse de datos de examen
    var collapseElement = document.getElementById('collapseDatosExamen');
    var iconElement = document.getElementById('b_toggle_collapse').querySelector('i'); // Selecciona el icono dentro del botón
    var reportContainer = document.getElementById('card-informe'); // Contenedor del informe

    if (collapseElement.classList.contains('show')) {
        collapseElement.classList.remove('show');
        iconElement.classList.remove('fa-angle-up'); // Cambia el icono a flecha hacia abajo
        iconElement.classList.add('fa-angle-down');
        reportContainer.classList.add('expand-report');
        console.log("expando")
    } else {
        collapseElement.classList.add('show');
        iconElement.classList.remove('fa-angle-down'); // Cambia el icono a flecha hacia arriba
        iconElement.classList.add('fa-angle-up');
        reportContainer.classList.remove('expand-report');
        console.log("contraigo")
    }

    //Ahora debo controllar el collapse del

}
function ModalPredef() {
    // Cargar el contenido del archivo modal_predef.html
    $.get('/modal_predef.html', function(data) {
        // Reemplazar los marcadores en el contenido HTML
        var modalContent = `
            <div class="informe-details" id="modal_data">
                ${data} <!-- Contenido del archivo generacion_informe.html -->
            </div>
        `;
        $('#modal_content').html(modalContent);
        RellenarSelect("s_moda",'Description','public.Ismodality');
        RellenarSelect("s_predef",'name','public.tbreportdefault');

        document.getElementById('s_moda').addEventListener('change', function() {
            var selectedValue = this.value;
            RellenarSelectCondicionalId("s_predef", 'name', 'public.tbreportdefault', selectedValue, 'idmodality');
            sendValue(selectedValue);
        });

        document.getElementById('s_predef').addEventListener('change', function() {
            var idpredef = this.value;
            fetch('/get_inf_predef', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ idpredef: idpredef }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'OK') {
                    var execElement = document.getElementById('tecnica');
                    var findingElement = document.getElementById('informe');
                    var concluElement = document.getElementById('conclu');

                    // Rellenar los campos con los datos obtenidos
                    execElement.value = data.data.executiontext || '';
                    findingElement.value = data.data.findingtext || '';
                    concluElement.value = data.data.conclusiontext || '';

                    // Deshabilitar los campos para que el usuario no pueda realizar cambios
                    execElement.disabled = true;
                    findingElement.disabled = true;
                    concluElement.disabled = true;
                } else {
                    console.error('Error:', data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
        });

        var Form = document.getElementById('modal_predef');
        Form.addEventListener('submit', function (event) {
            event.preventDefault();
            console.log("evite la redireccionddd")// Evitar la recarga de la página
            // Transferir el contenido de los campos del modal a los campos correspondientes en la página principal
            var mode = document.querySelector('input[name="mode"]:checked').value;

            // Obtener los elementos de los campos en la página principal
            var textTe = document.getElementById('text_te');
            var textInf = document.getElementById('text_inf');
            var textConc = document.getElementById('text_conc');

            // Obtener los valores de los campos del modal
            var tecnica = document.getElementById('tecnica').value;
            var informe = document.getElementById('informe').value;
            var conclu = document.getElementById('conclu').value;

            // Actualizar los campos de la página principal según el modo seleccionado
            if (mode === 'replace') {
                textTe.value = tecnica;
                textInf.value = informe;
                textConc.value = conclu;
            } else if (mode === 'add') {
                textTe.value += tecnica;
                textInf.value += informe;
                textConc.value += conclu;
            }
            $('#modal_predef').modal('hide')}) 
        $('#modal_predef').modal('show');
    });
}


function QuitarDefinitivo() {
    var dataId = document.getElementById('data').getAttribute('data-id'); 
    console.log("dataid: ", dataId);
    $.ajax({
        url: '/quitar_definitivo',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ id: dataId }),
        success: function(response) {
            console.log('Se ha quitado el definitivo:', response);
            // Habilitar los campos de texto
            document.getElementById('text_pc').disabled = false;
            document.getElementById('text_te').disabled = false;
            document.getElementById('text_inf').disabled = false;
            document.getElementById('text_conc').disabled = false;

            // Modificar el botón "b_firmar_reporte"
            var botonFirmar = document.getElementById('b_firmar_reporte');
            botonFirmar.innerText = "Firmar";

            // Clonar el botón para eliminar todos los event listeners actuales
            var nuevoBotonFirmar = botonFirmar.cloneNode(true);
            botonFirmar.parentNode.replaceChild(nuevoBotonFirmar, botonFirmar);

            // Agregar los nuevos event listeners
            nuevoBotonFirmar.addEventListener('click', function() {
                GuardarReporte();
                FirmarReporte();
            });

            // Inhabilitar el botón "b_ver_pdf"
            var botonVerPdf = document.getElementById('b_ver_pdf');
            botonVerPdf.disabled = true;
            document.getElementById('b_guardar_reporte').disabled=false
        },
        error: function(xhr, status, error) {
            console.error('Error al quitar el definitivo:', error);
            alert('Error al quitar el definitivo');
        }
    });
}


function VolverAtras() {
    $('#card_ordenes').show();
    $('#card_buscar').show();
    $('#data').remove(); // Eliminar el elemento #data
}

function VerImagenes(){
    var dataId = document.getElementById('data').getAttribute('data-id');
    $.ajax({
        url: '/get_image_link', // URL de tu API
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ id: dataId }),
        success: function(response) {
            console.log(response)
            if (response[1]==1) {
                console.log(response[0]);
                var link = 'http://192.168.31.56/viewer.html?studyUID=' + response[0];
                
                window.open(link, '_blank');
            } else {
                alert('No hay imágenes disponibles para este ID.');
            }
        },
        error: function() {
            alert('Hubo un error al comunicarse con el servidor.');
        }
    });
}

function VerPDF() {
    var dataId = document.getElementById('data').getAttribute('data-id');
    var url = `/verpdf/${dataId}`;

    fetch(url)
        .then(response => {
            if (response.ok) {
                return response.blob();
            } else {
                throw new Error('No se pudo obtener el PDF');
            }
        })
        .then(blob => {
            var url = window.URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.target = '_blank';
            a.click();
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

function FirmarReporte() {
    var dataId = document.getElementById('data').getAttribute('data-id'); 
    console.log("dataid: ", dataId);
    $.ajax({
        url: '/firmar_reporte',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ id: dataId }),
        success: function(response) {
            console.log('Reporte firmado correctamente:', response);
            alert('Reporte firmado correctamente');
            // Deshabilitar los campos de texto
            document.getElementById('text_pc').disabled = true;
            document.getElementById('text_te').disabled = true;
            document.getElementById('text_inf').disabled = true;
            document.getElementById('text_conc').disabled = true;

            // Modificar el botón "b_firmar_reporte"
            var botonFirmar = document.getElementById('b_firmar_reporte');
            botonFirmar.innerText = "Quitar definitivo";

            // Clonar el botón para eliminar todos los event listeners actuales
            var nuevoBotonFirmar = botonFirmar.cloneNode(true);
            botonFirmar.parentNode.replaceChild(nuevoBotonFirmar, botonFirmar);

            // Agregar el nuevo event listener
            nuevoBotonFirmar.addEventListener('click', function() {
                if (confirm('¿Estás seguro de que quieres quitar el definitivo?')) {
                    QuitarDefinitivo();
                }
            });

            var botonVerPdf = document.getElementById('b_ver_pdf');
            botonVerPdf.disabled = false;
            document.getElementById('b_guardar_reporte').disabled=true
        },
        error: function(xhr, status, error) {
            console.error('Error al firmar el reporte:', error);
            alert('Error al firmar el reporte');
        }
    });
}


function GuardarReporte() {

    var text_pc = document.getElementById('text_pc').value;
    var text_te = document.getElementById('text_te').value;
    var text_inf = document.getElementById('text_inf').value;
    var text_conc = document.getElementById('text_conc').value;
    var dataId = document.getElementById('data').getAttribute('data-id'); // Asumimos que tienes el ID almacenado en algún lugar

    var reporteData = {
        id: dataId,
        pregunta_clinica: text_pc,
        tecnicas_examen: text_te,
        informe: text_inf,
        conclusion: text_conc
    };

    $.ajax({
        url: '/guardar_reporte',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(reporteData),
        success: function(response) {
            console.log('Reporte guardado correctamente:', response);
            alert('Reporte guardado correctamente');
        },
        error: function(xhr, status, error) {
            console.error('Error al guardar el reporte:', error);
            alert('Error al guardar el reporte');
        }
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



//el IdId hace referencia al div hidden donde se colocara el id.
function SetEditButton(buttonId, FormModalId, modalId, tablaId, FormAction, config,IdId) {
    var boton = document.getElementById(buttonId);

    boton.addEventListener('click', function () {
        // Obtener la fila seleccionada
        var Form = document.getElementById(FormModalId);
        
        // Asignar la acción del formulario directamente
        Form.action = FormAction;
        
        var tabla = document.getElementById(tablaId);
        var tbody_ = tabla.querySelector('tbody');
        var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');

        if (filaSeleccionada) {
            // Obtener los datos de la fila
            var id_span=document.getElementById(IdId)
            id_span.value=filaSeleccionada.dataset.id;
            
            // Obtener todas las celdas de la fila
            var celdas = filaSeleccionada.querySelectorAll('td');

            // Almacenar los valores en un arreglo
            var valores = Array.from(celdas).map(function (celda) {
                // Verifica si la celda contiene un checkbox
                var checkbox = celda.querySelector('input[type="checkbox"]');
                
                if (checkbox) {
                    // Si es un checkbox, devuelve el estado (checked o no) como valor
                    return checkbox.checked;
                } else {
                    // Si no es un checkbox, devuelve el contenido de texto de la celda
                    return celda.innerText;
                }
            });
            
            
            // Colocar los datos en el modal
            config.forEach(function (item, index) {
                var modalField = document.getElementById(item.modalFieldId);
                if (modalField.type === 'checkbox') {
                    modalField.checked = valores[index];
                } else if (modalField.type === 'select-one') {
                    // Encuentra la opción con el texto y selecciónala
                    var options = modalField.options;
                    for (var i = 0; i < options.length; i++) {
                        if (options[i].text === valores[index]) {
                            options[i].selected = true;
                            break; // Sal del bucle una vez que encuentres la opción
                        }
                    }
                } else if (modalField.type === 'date') {
                    var dateString = valores[index];
                    modalField.valueAsDate= new Date(dateString);
                    
                } else {
                    modalField.value = valores[index];
                }
            });

            // Mostrar el modal
            var modal = new bootstrap.Modal(document.getElementById(modalId));
            modal.show();
        } else {
            console.warn('No hay fila seleccionada.');
        }
    });
}

function RellenarSelect(SelectId,dNeeded,TableId){
    fetch('/rellenar_select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ dNeeded: dNeeded, TableId:TableId }),
    })
    .then(response => response.json())
    .then(data => {
        var selectElement = document.getElementById(SelectId);

    // Limpiar cualquier opción existente en el <select>
        selectElement.innerHTML = '';
        for (var i = 0; i < data.data.length; i++) {
            var option = document.createElement('option');
            option.value= data.data[i][0]
            option.text= data.data[i][1]
            selectElement.appendChild(option);
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function RellenarSelectCondicional(SelectId,dNeeded,TableId,dCond,IdCond){
    fetch('/rellenar_select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ dNeeded: dNeeded, TableId:TableId }),
    })
    .then(response => response.json())
    .then(data => {
        var selectElement = document.getElementById(SelectId);

    // Limpiar cualquier opción existente en el <select>
        selectElement.innerHTML = '';
        for (var i = 0; i < data.data.length; i++) {
            var option = document.createElement('option');
            option.value= data.data[i][0]
            option.text= data.data[i][1]
            selectElement.appendChild(option);
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function RellenarSelectCondicionalId(SelectId,dNeeded,TableId,idCond,colCond){
    fetch('/rellenar_select_cond_id', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ dNeeded: dNeeded, TableId:TableId, idCond:idCond,colCond:colCond }),
    })
    .then(response => response.json())
    .then(data => {
        var selectElement = document.getElementById(SelectId);

    // Limpiar cualquier opción existente en el <select>
        selectElement.innerHTML = '';
        for (var i = 0; i < data.data.length; i++) {
            var option = document.createElement('option');
            option.value= data.data[i][0]
            option.text= data.data[i][1]
            selectElement.appendChild(option);
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}


document.addEventListener("DOMContentLoaded", function() {
    // configuracion de busqueda y llenado de tabla
    RellenarTabla('tabla-pacientes',`/get_examinations`)
    var boton=document.getElementById("generar_informe")
    boton.addEventListener("click",function(){GenerarInforme('tabla-pacientes')})



    ConfigurarTabla('tabla-pacientes','botones_sp')

   
    
});
