// Muchas de estas funciones hacen referencia a nr-framework.js y nr-tables.js
// En caso de que una funcion llame a otra no definida, no se debe createRef, si no usar la funcion directamente.
function GenerarInforme(TablaId) {
  // Mostrar loader
  const loader = document.getElementById('loader-overlay');
  if (loader) loader.classList.add('active');

  // --- [A] Ajuste de layout y ocultar modal ---
  const main = document.querySelector('.main-content');
  if (main) main.style.marginLeft = '-18px';
  const modal = document.querySelector('#modal_content');
  if (modal) modal.style.display = 'none';

  // --- [B] Obtener tabla y fila seleccionada ---
  const tabla = document.getElementById(TablaId);
  if (!tabla) return;

  const filaSeleccionada = tabla.querySelector('tbody .fila-seleccionada');
  if (!filaSeleccionada) {
    console.log('No hay fila seleccionada.');
    return;
  }
 
    // --- [C] Extraer datos de la fila seleccionada ---
    const dataId = filaSeleccionada.getAttribute('data-id');
    const celdas = filaSeleccionada.querySelectorAll('td');
    const nombrePaciente = (celdas[1]?.textContent || '').trim();
    const examen = (celdas[4]?.textContent || '').trim();
    console.log("DataId:", dataId, "Paciente:", nombrePaciente, "Examen:", examen);

    // --- [C.1] La carga de historial se hace después de montar el template con fetch ---

  // --- [D] Cargar template de informe y montar en el DOM ---
  $.get('/generacion_informe.html', function (data) {
    // [D1] Parsear y quitar <script> para evitar re-declaraciones
    const $frag = $($.parseHTML(data, document, true));
    $frag.find('script').remove();

    // [D2] Montar el fragmento en el contenedor
    const $wrapper = $(`<div class="informe-details" id="data" data-id="${dataId}"></div>`);
    $wrapper.append($frag);
    const $container = $('#informe-content');
    $container.empty().append($wrapper).attr('data-id', dataId);

        // --- [D.1] Traer estudios previos del paciente y mostrarlos en el historial usando fetch ---
        fetch('/get_patient_history_for_report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: dataId })
        })
        .then(response => response.json())
        .then(result => {
            let html = '';
            if (Array.isArray(result) && result.length > 0) {
                result.forEach(function(row) {
                    // row: [guid, createdon, estudio, username, status, reportdate]
                    html += `<tr>` +
                        `<td class="modalidad-col">${row[2] || ''}</td>` +
                        `<td class="fecha-col">${row[1] ? row[1].split('T')[0] : ''}</td>` +
                        `<td class="accion-col"><button class="btn btn-sm" onclick="alert('Ver estudio: ${row[0]}')">Ver</button></td>` +
                    `</tr>`;
                });
            } else {
                html = '<tr><td colspan="3">sin info</td></tr>';
            }
            const tabla = document.getElementById('tabla_historial_estudios');
            if (tabla) {
                tabla.querySelector('tbody').innerHTML = html;
            }
        })
        .catch(() => {
            const tabla = document.getElementById('tabla_historial_estudios');
            if (tabla) {
                tabla.querySelector('tbody').innerHTML = '<tr><td colspan="3">sin info</td></tr>';
            }
        });


    // --- [E] Llamada al backend para obtener datos del informe ---
    $.ajax({
      url: '/get_data_report',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ id: dataId }),
      success: function (response) {
        console.log("response:", response);

        // [E1] Extraer datos del backend
        const report_id = response.report?.[0];
        const acc_number = response.report?.[1];
        const fecha = response.report?.[9];
        const isreported = !!response.isreported;
        window.wassaved = !!response.wassaved; // Hacer global
        const predefinido = response.predefinido || {};
        const isimage = !!response.isimage;
        const study_instance_uid = response.study_instance_uid;
        const descripcion_predef = response.descripcion_predef || '';
        const fecha_examen = response.fecha_examen || '';
        const modality = response.modality || '';
        const medico = response.medico || '';
        const tittle = predefinido.tittle || 'Sin Titulo';
        const number_of_views = response.number_of_views || '';
        const stat = response.stat || '';
        const others_details = response.others_details || '';
        const lateralidad = response.lateralidad || '';
        const history = response.history || '';
        const clinical_question = response.clinical_question || '';

        console.log("pre:", predefinido);

        // [E2] Reemplazar placeholders adicionales
        replacePlaceholders($container, {
        '[[AdmNumber]]': acc_number,
        '[[examen]]': examen,
        '[[pregunta_clinica]]': `${nombrePaciente}`,
        '[[Nombre del paciente]]': `${nombrePaciente}`,
        '[[Fecha]]': `${fecha_examen}`,
        '[[modalidad]]': `${modality}`,
        '[[medico]]': `${medico}`,
        '[[tittle]]': `${tittle}`,
        '[[numberofviews]]': `${number_of_views}`,
        '[[stat]]': `${stat}`,
        '[[others_details]]': `${others_details}`,
        '[[lateralidad]]': `${lateralidad}`,
        '[[history]]': `${history}`,
        '[[clinical_question]]': `${clinical_question}`
        });

        // [E2.1] Ocultar campos vacíos en la barra lateral
        $container.find('.sidebar-datos').each(function() {
        if (!this.textContent.trim() || this.textContent.trim() === '') {
            var field = this.closest('.field');
            if (field) field.style.display = 'none';
        }
        });

        // [E3] Cargar valores en los campos del informe
        if (window.wassaved && Array.isArray(response.report)) {
          // Si wassaved es true, usar los datos de tbreport
          $('#text_findings').val(response.report[4] || ''); // Hallazgos
          $('#text_tecnicas').val(response.report[6] || ''); // Val Sub
          $('#text_impresiones').val(response.report[5] || ''); // Val Obj
          $('#text_conclusiones').val(response.report[7] || ''); // Indicaciones
        } else {
          // Si wassaved es false, usar los datos del informe predefinido
          $('#text_findings').val(predefinido.findings || '');
          $('#text_tecnicas').val(predefinido.techniques || '');
          $('#text_impresiones').val(predefinido.impressions || '');
          $('#text_conclusiones').val(predefinido.conclusions || '');
        }

        // [E4] NUEVO: Inicializar detección de cambios después de cargar valores
        const textareas = ['#text_findings', '#text_tecnicas', '#text_impresiones', '#text_conclusiones'];
        
        // Guardar valores originales en data attributes
        textareas.forEach(function(selector) {
          const $textarea = $(selector);
          $textarea.data('original-value', $textarea.val());
        });
        
        // Detectar cambios en tiempo real
        textareas.forEach(function(selector) {
          $(selector).on('input', function() {
            const currentValue = $(this).val();
            const originalValue = $(this).data('original-value');
            
            console.log('Cambio detectado en', selector, ':', currentValue !== originalValue);
            
            if (currentValue !== originalValue) {
              // Marcar como modificado con morado claro
              $(this).addClass('field-modified');
            } else {
              // Quitar marca si vuelve al valor original
              $(this).removeClass('field-modified');
            }
          });
        });

        // --- [F] Configuración de botones y eventos ---
        const $bFirmar = $('#b_firmar_reporte');
        const $bGuardar = $('#b_guardar_reporte');
        const $bVerPdf = $('#b_ver_pdf');
        const $bVerImgs = $('#b_ver_imagenes');
        const $bAtras = $('#b_atras_report');

        // [F0] Verificar si el status contiene "R" (Reportado) para mostrar/ocultar botón PDF
        const hasReportStatus = stat && stat.includes('R');
        
        // Ocultar/mostrar botón PDF basado en el status
        if (hasReportStatus) {
          $bVerPdf.show().prop('disabled', false);
        } else {
          $bVerPdf.hide(); // Ocultar completamente el botón si no hay "R" en el status
        }

        // $bVerPdf.prop('disabled', !isimage);

        // [F1] Estado de edición/firmado
        if (isreported) {
          $('#text_findings,#text_tecnicas,#text_impresiones,#text_conclusiones').prop('disabled', true);
          
          // Agregar clase visual para campos bloqueados
          $('#text_findings,#text_tecnicas,#text_impresiones,#text_conclusiones').addClass('field-locked');

          $bFirmar.text('Quitar Firma').off('click').on('click', function () {
            QuitarDefinitivo();
          });
          $bGuardar.prop('disabled', true);
          // Solo habilitar PDF si tiene el status "R" 
          if (hasReportStatus) {
            $bVerPdf.prop('disabled', false);
          }
          alert('Este examen ya está firmado. No se puede editar');
        } else {
          // Campos editables - eventos de cambio ya configurados arriba en [E4]
          
          $bFirmar.off('click').on('click', function () {
            // Validar credenciales antes de guardar y firmar
            validarCredencialesUsuario().then(function(valido) {
              if (valido) {
                GuardarReporteConAnimacion();
                FirmarReporte();
              } else {
                alert('Credenciales inválidas. No se puede firmar el informe.');
              }
            });
          });
          $bGuardar.prop('disabled', false).off('click').on('click', function() {
            GuardarReporteConAnimacion();
          });
        }

        // [F2] Botón ver imágenes
        $bVerImgs.prop('disabled', !isimage).off('click').on('click', function () {
          VerDcm(study_instance_uid);
        });
        var dataId = document.getElementById('data').getAttribute('data-id');
        
        // Solo agregar el evento click si el botón está visible (tiene status "R")
        if (hasReportStatus) {
          $bVerPdf.off('click').on('click', function() {
            VerPDF(dataId);
          });
        }

        // [F3] Botón atrás
        $bAtras.off('click').on('click', function () {
          if (confirm('¿Estás seguro de que quieres volver atrás? Se eliminarán los cambios realizados.')) location.reload();
        });

        // [F4] Botones de colapsado y expansión
        $('#b_toggle_collapse').off('click').on('click', ConfigBtnDatos);
        $('#b_subjetivas_expand').off('click').on('click', function () {
          ConfigBtnExpandMulti('card-subjetivas', 'b_subjetivas_expand', 'col2');
        });
        $('#b_objetivas_expand').off('click').on('click', function () {
          ConfigBtnExpandMulti('card-objetivas', 'b_objetivas_expand', 'col2');
        });
        $('#b_indic_expand').off('click').on('click', function () {
          ConfigBtnExpandMulti('card-indicaciones', 'b_indic_expand', 'col2');
        });

        // [F5] Tabla de informes predefinidos
        // IMPORTANTE: Mover el modal al body para evitar problemas de z-index con stacking contexts
        const modalPredef = document.getElementById('predefinedReportsModal');
        if (modalPredef && modalPredef.parentElement.className.includes('informe-details')) {
            console.log('Moviendo modal de informes predefinidos al body...');
            document.body.appendChild(modalPredef);
        }
        
        ConfigurarTabla('tabla_inf_predef', 'boton_modal');
        $('#btnAceptarInforme').off('click').on('click', CompletarConPredef);

        RellenarTabla('tabla_inf_predef', '/get_inf_predefinidos')
        ConfigFiltrarText('filtroMedico', 'tabla_inf_predef', 1);

        // --- [G] Filtrado por tipo de estudio propio ---
        var miTipoEstudio = descripcion_predef;
        var checkBox = document.getElementById('checkMyStudyType');
        if (checkBox) {
            checkBox.addEventListener('change', function() {
                var mostrarSoloMios = this.checked;
                var tabla = document.getElementById('tabla_inf_predef');
                var filas = tabla.querySelectorAll('tbody tr');
                filas.forEach(function(fila) {
                    var tipoEstudio = fila.cells[1]?.innerText?.trim() || '';
                    if (mostrarSoloMios) {
                        fila.style.display = (tipoEstudio === miTipoEstudio) ? '' : 'none';
                    } else {
                        fila.style.display = '';
                    }
                });
            });
        }
        // --- FIN [G] ---

        // Ocultar loader cuando todo está cargado
        const loader = document.getElementById('loader-overlay');
        if (loader) loader.classList.remove('active');
        
      },
      error: function () {
        console.error('Error al obtener los datos del informe');
        // Ocultar loader en caso de error
        const loader = document.getElementById('loader-overlay');
        if (loader) loader.classList.remove('active');
      }
    });
  }).fail(function () {
    console.error('Error al cargar el archivo generacion_informe.html');
    // Ocultar loader en caso de error
    const loader = document.getElementById('loader-overlay');
    if (loader) loader.classList.remove('active');
  });

  // --- [H] Ocultar cards de órdenes y búsqueda ---
  $('#card_ordenes').hide();
  $('#card_buscar').hide();

  // ---- [I] Helper para reemplazo de placeholders ----
  function replacePlaceholders($root, map) {
    const keys = Object.keys(map);
    if (!keys.length) return;

    // Reemplazar en nodos de texto
    $root.find('*').addBack().contents().filter(function () {
      return this.nodeType === 3 && keys.some(k => this.nodeValue.includes(k));
    }).each(function () {
      let v = this.nodeValue;
      keys.forEach(k => { v = v.split(k).join(map[k]); });
      this.nodeValue = v;
    });

    // Reemplazar en value/placeholder/title de inputs y textareas
    $root.find('textarea, input, [placeholder], [title]').each(function () {
      keys.forEach(k => {
        if (this.value && this.value.includes(k)) this.value = this.value.split(k).join(map[k]);
        const ph = this.getAttribute && this.getAttribute('placeholder');
        if (ph && ph.includes(k)) this.setAttribute('placeholder', ph.split(k).join(map[k]));
        const tt = this.getAttribute && this.getAttribute('title');
        if (tt && tt.includes(k)) this.setAttribute('title', tt.split(k).join(map[k]));
      });
    });
  }
}

// Validación de credenciales del usuario
function validarCredencialesUsuario() {
    var usernameInput = document.getElementById('current_username');
    var username = usernameInput ? usernameInput.value : null;
    
  return new Promise(function(resolve) {
    // Mostrar el modal
    var modal = new bootstrap.Modal(document.getElementById('modal_firmar_informe'));
    var passwordInput = document.getElementById('password_firma');
    var btnConfirmar = document.getElementById('btn_confirmar_firma');
    var form = document.getElementById('form_firmar_informe');
    
    // Limpiar el input de contraseña
    passwordInput.value = '';
    passwordInput.classList.remove('is-invalid');
    
    // Mostrar el modal
    modal.show();
    
    // Enfocar el input cuando se muestre el modal
    document.getElementById('modal_firmar_informe').addEventListener('shown.bs.modal', function () {
      passwordInput.focus();
    }, { once: true });
    
    // Función para validar
    var validar = function() {
      var password = passwordInput.value.trim();
      
      if (!password) {
        passwordInput.classList.add('is-invalid');
        return;
      }
      
      // Deshabilitar botón mientras valida
      btnConfirmar.disabled = true;
      btnConfirmar.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Validando...';
      
      // Llamada al backend para validar
      console.log("Validando para usuario y contraseña:", username+" / "+password);
      fetch('/validar_credenciales', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username, password: password })
      })
      .then(response => response.json())
      .then(data => {
        console.log("Respuesta del servidor:", data);
        
        if (data.success === true) {
          // Credenciales válidas
          modal.hide();
          resolve(true);
        } else {
          // Credenciales inválidas
          passwordInput.classList.add('is-invalid');
          passwordInput.value = '';
          passwordInput.focus();
          
          // Mostrar toast de error
          if (typeof showErrorToast === 'function') {
            showErrorToast('Error', 'Contraseña incorrecta. Por favor intente nuevamente.');
          }
          
          // Restaurar botón
          btnConfirmar.disabled = false;
          btnConfirmar.innerHTML = '<i class="fas fa-signature me-1"></i>Confirmar y Firmar';
        }
      })
      .catch(error => {
        console.error('Error al validar credenciales:', error);
        passwordInput.classList.add('is-invalid');
        
        if (typeof showErrorToast === 'function') {
          showErrorToast('Error', 'Error al validar las credenciales. Intente nuevamente.');
        }
        
        // Restaurar botón
        btnConfirmar.disabled = false;
        btnConfirmar.innerHTML = '<i class="fas fa-signature me-1"></i>Confirmar y Firmar';
      });
    };
    
    // Evento para el botón confirmar
    var confirmarHandler = function() {
      validar();
    };
    
    // Evento para presionar Enter en el input
    var enterHandler = function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        validar();
      }
    };
    
    // Agregar eventos
    btnConfirmar.addEventListener('click', confirmarHandler, { once: true });
    passwordInput.addEventListener('keypress', enterHandler);
    
    // Evento cuando se cierra el modal sin confirmar
    document.getElementById('modal_firmar_informe').addEventListener('hidden.bs.modal', function () {
      // Remover event listeners
      btnConfirmar.removeEventListener('click', confirmarHandler);
      passwordInput.removeEventListener('keypress', enterHandler);
      
      // Restaurar botón
      btnConfirmar.disabled = false;
      btnConfirmar.innerHTML = '<i class="fas fa-signature me-1"></i>Confirmar y Firmar';
      
      // Si no se resolvió la promesa, resolver como false
      if (btnConfirmar.disabled === false) {
        resolve(false);
      }
    }, { once: true });
  });
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

function ConfigBtnExpandMulti(activeCardId, btnId, columnContainerId) {
    const column = document.getElementById(columnContainerId); // columna que contiene todas las cards
    const activeCard = document.getElementById(activeCardId);  // la card que quiero expandir
    const iconElement = document.getElementById(btnId).querySelector('i'); // el ícono del botón que fue clickeado

    // Recorre todas las cards dentro de la columna
    const allCards = column.querySelectorAll('.card');

    allCards.forEach(card => {
        const collapseSection = card.querySelector('.collapse');
        const buttonIcon = card.querySelector('button i');

        if (card.id === activeCardId) {
            // Si es la card elegida esta colapsada:
            if (collapseSection && !collapseSection.classList.contains('show')) {
                collapseSection.classList.add('show');
                iconElement.classList.remove('fa-expand-arrows-alt');
                iconElement.classList.add('fa-crosshairs');
                card.classList.add('expand-card');
            } else {
                // Si ya está expandida, la contraigo
                collapseSection.classList.remove('show');
                iconElement.classList.remove('fa-crosshairs');
                iconElement.classList.add('fa-expand-arrows-alt');
                card.classList.remove('expand-card');
            }
        } else {
            // Colapsar todas las demás
            if (collapseSection && collapseSection.classList.contains('show')) {
                collapseSection.classList.remove('show');
            }
            if (buttonIcon) {
                buttonIcon.classList.remove('fa-crosshairs');
                buttonIcon.classList.add('fa-expand-arrows-alt');
            }
            card.classList.remove('expand-card');
        }
    });
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


function CompletarConPredef() {
    var tabla = document.getElementById('tabla_inf_predef');
    var tbody_ = tabla.querySelector('tbody');
    var filaSeleccionada = tbody_.querySelector('.fila-seleccionada');

    if (filaSeleccionada) {
        var guid = filaSeleccionada.dataset.id;
        fetch('/get_predefinido/' + guid)
            .then(response => response.json())
            .then(data => {
                console.log("Datos de la plantilla:", data);
                if (window.wassaved) {
                    if (!confirm('Este estudio ya tiene datos guardados, ¿quieres reemplazar todo?')) {
                        return;
                    }
                }
                document.getElementById('text_findings').value = data.findings || '';
                document.getElementById('text_tecnicas').value = data.technique || '';
                document.getElementById('text_impresiones').value = data.impression || '';
                document.getElementById('text_conclusiones').value = data.conclusion || '';

                // Actualizar el título del predefinido seleccionado en la sidebar
                const allLabels = document.querySelectorAll('.field label');
                allLabels.forEach(label => {
                    if (label.textContent.trim() === 'Predef Seleccionado') {
                        const sidebarTittleValue = label.parentElement.querySelector('.sidebar-datos');
                        if (sidebarTittleValue) {
                            sidebarTittleValue.textContent = data.tittle || 'Sin Titulo';
                        }
                    }
                });

                // cerrar modal si querés
                const modal = bootstrap.Modal.getInstance(document.getElementById('predefinedReportsModal'));
                modal.hide();
                document.body.classList.remove('modal-open');
                document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
            })
            .catch(error => {
                console.error("Error al obtener la plantilla:", error);
            });
    } else {
        alert("Seleccioná una plantilla primero.");
    }
}

function QuitarDefinitivo() {
    var dataId = document.getElementById('data').getAttribute('data-id'); 
    console.log("dataid: ", dataId);
    validarCredencialesUsuario().then(function(valido) {
        if (!valido) {
            alert('Credenciales inválidas. No se puede quitar el informe definitivo.');
            return;
        }
        $.ajax({
            url: '/quitar_definitivo',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ id: dataId }),
            success: function(response) {
                console.log('Se ha quitado el definitivo:', response);
                // Habilitar los campos de texto
                document.getElementById('text_findings').disabled = false;
                document.getElementById('text_tecnicas').disabled = false;
                document.getElementById('text_impresiones').disabled = false;
                document.getElementById('text_conclusiones').disabled = false;

                // Modificar el botón "b_firmar_reporte"
                var botonFirmar = document.getElementById('b_firmar_reporte');
                botonFirmar.innerHTML = '<i class="fas fa-signature"></i><span class="btn-text">Firmar</span>';

                // Clonar el botón para eliminar todos los event listeners actuales
                var nuevoBotonFirmar = botonFirmar.cloneNode(true);
                botonFirmar.parentNode.replaceChild(nuevoBotonFirmar, botonFirmar);
                nuevoBotonFirmar.addEventListener('click', function() {
                    // Validar credenciales antes de guardar y firmar
                    validarCredencialesUsuario().then(function(valido) {
                        if (valido) {
                            GuardarReporteConAnimacion();
                            FirmarReporte();
                        } else {
                            alert('Credenciales inválidas. No se puede firmar el informe.');
                        }
                    });
                });

                // Después de quitar definitivo, el status ya no debería incluir "R", así que ocultar el botón PDF
                var botonVerPdf = document.getElementById('b_ver_pdf');
                botonVerPdf.style.display = 'none'; // Ocultar el botón completamente
                botonVerPdf.disabled = true;
                
                // Remover eventos click
                $(botonVerPdf).off('click');
            },
            error: function(xhr, status, error) {
                console.error('Error al quitar el definitivo:', error);
                alert('Error al quitar el definitivo');
            }
        });
    });
}

function FirmarReporte() {
    var dataId = document.getElementById('data').getAttribute('data-id'); 
    var userGuid = document.getElementById('current_user_guid')?.value;
    
    console.log("dataid: ", dataId);
    console.log("user_guid: ", userGuid);
    
    // Preparar datos para enviar
    var dataToSend = { id: dataId };
    if (userGuid && userGuid !== 'SIN GUID') {
        dataToSend.reporter_physician_id = userGuid;
    }
    
    $.ajax({
        url: '/firmar_reporte',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(dataToSend),
        success: function(response) {
            console.log('Reporte firmado correctamente:', response);
            showToast('Exito', 'Reporte firmado correctamente', "/templates/includes/toast/toast_success.html")
            // Deshabilitar los campos de texto
            document.getElementById('text_findings').disabled = true;
            document.getElementById('text_tecnicas').disabled = true;
            document.getElementById('text_impresiones').disabled = true;
            document.getElementById('text_conclusiones').disabled = true;

            // Modificar el botón "b_firmar_reporte"
            var botonFirmar = document.getElementById('b_firmar_reporte');
            botonFirmar.innerText = "Quitar Firma";

            // Clonar el botón para eliminar todos los event listeners actuales
            var nuevoBotonFirmar = botonFirmar.cloneNode(true);
            botonFirmar.parentNode.replaceChild(nuevoBotonFirmar, botonFirmar);

            // Agregar el nuevo event listener
            nuevoBotonFirmar.addEventListener('click', function() {
                QuitarDefinitivo();
            });

            // Después de firmar, el status debería incluir "R", así que mostrar el botón PDF
            var botonVerPdf = document.getElementById('b_ver_pdf');
            botonVerPdf.style.display = 'inline-block'; // Mostrar el botón
            botonVerPdf.disabled = false;
            
            // Agregar el evento click si no lo tiene
            $(botonVerPdf).off('click').on('click', function() {
                var dataId = document.getElementById('data').getAttribute('data-id');
                VerPDF(dataId);
            });
            
            document.getElementById('b_guardar_reporte').disabled=true
        },
        error: function(xhr, status, error) {
            console.error('Error al firmar el reporte:', error);
            alert('Error al firmar el reporte');
        }
    });
}


function GuardarReporte() {

    var text_findings = document.getElementById('text_findings').value;
    var text_tecnicas = document.getElementById('text_tecnicas').value;
    var text_impresiones = document.getElementById('text_impresiones').value;
    var text_conclusiones = document.getElementById('text_conclusiones').value;
    var dataId = document.getElementById('data').getAttribute('data-id'); // Asumimos que tienes el ID almacenado en algún lugar

    var reporteData = {
        id: dataId,
        val_findings: text_findings,
        val_tecnicas: text_tecnicas,
        val_impresiones: text_impresiones,
        val_conclusiones: text_conclusiones
    };

    $.ajax({
        url: '/guardar_reporte',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(reporteData),
        success: function(response) {
            // console.log('Reporte guardado correctamente:', response);
            // alert('Reporte guardado correctamente');
            window.wassaved = true; // Actualizar la variable global
            showToast('Exito', 'Cambios guardados', "/templates/includes/toast/toast_success.html")

        },
        error: function(xhr, status, error) {
            console.error('Error al guardar el reporte:', error);
            alert('Error al guardar el reporte');
        }
    });
}

// Nueva función con animación
function GuardarReporteConAnimacion() {
    var text_findings = document.getElementById('text_findings').value;
    var text_tecnicas = document.getElementById('text_tecnicas').value;
    var text_impresiones = document.getElementById('text_impresiones').value;
    var text_conclusiones = document.getElementById('text_conclusiones').value;
    var dataId = document.getElementById('data').getAttribute('data-id');

    var reporteData = {
        id: dataId,
        val_findings: text_findings,
        val_tecnicas: text_tecnicas,
        val_impresiones: text_impresiones,
        val_conclusiones: text_conclusiones
    };

    $.ajax({
        url: '/guardar_reporte',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(reporteData),
        success: function(response) {
            window.wassaved = true;
            showToast('Exito', 'Cambios guardados', "/templates/includes/toast/toast_success.html");
            
            // Animar campos que tenían cambios
            const textareas = ['#text_findings', '#text_tecnicas', '#text_impresiones', '#text_conclusiones'];
            textareas.forEach(function(selector) {
                const $textarea = $(selector);
                if ($textarea.hasClass('field-modified')) {
                    // Remover clase de modificado
                    $textarea.removeClass('field-modified');
                    
                    // Agregar animación de guardado (parpadeo verde)
                    $textarea.addClass('field-saved');
                    
                    // Remover la clase después de la animación
                    setTimeout(function() {
                        $textarea.removeClass('field-saved');
                    }, 1200); // Duración de la animación
                }
            });
            
            // Actualizar valores originales después de guardar
            textareas.forEach(function(selector) {
                const $textarea = $(selector);
                $textarea.data('original-value', $textarea.val());
            });
        },
        error: function(xhr, status, error) {
            console.error('Error al guardar el reporte:', error);
            alert('Error al guardar el reporte');
        }
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


document.addEventListener("DOMContentLoaded", function() {
    // Mostrar el user_guid en consola
    var userGuidInput = document.getElementById('current_user_guid');
    var userGuid = userGuidInput ? userGuidInput.value : null;
    if (userGuid) {
        console.log('User GUID:', userGuid);
    } else {
        console.log('User GUID no encontrado');
    }

    // Función para recargar la tabla con los filtros
    function recargarTablaPacientes() {
        // Limpiar selección de fila actual
        var tabla = document.getElementById('tabla-pacientes');
        if (tabla) {
            var filas = tabla.querySelectorAll('tbody tr');
            filas.forEach(function(fila) {
                fila.classList.remove('fila-seleccionada');
            });
        }

        // Deshabilitar botones
        var botones = document.getElementsByClassName('botones_sp');
        for (var i = 0; i < botones.length; i++) {
            var boton = botones[i];
            boton.disabled = true;
            
            // Restaurar clases a btn-secondary
            if (boton.classList.contains('delete_b')) {
                boton.classList.remove('btn-danger');
                boton.classList.add('btn-secondary');
            } else {
                boton.classList.remove('btn-success');
                boton.classList.add('btn-secondary');
            }
        }

        var filtroMisExamenes = document.getElementById('filtro_mis_examenes').checked;
        var filtroAsignados = document.getElementById('filtro_estudios_asignados').checked;
        var filtroVerFinalizados = document.getElementById('filtro_ver_finalizados').checked;
        console.log('Recargando tabla. Filtro mis exámenes:', filtroMisExamenes, 'Filtro asignados:', filtroAsignados, 'Ver finalizados:', filtroVerFinalizados);
        console.log('User GUID:', userGuid);

        if (filtroMisExamenes && userGuid && userGuid !== 'SIN GUID') {
            // Filtro por grupo
            fetch('/get_examination_items_filtrado', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_guid: userGuid, include_reported: filtroVerFinalizados })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Datos recibidos del filtro grupo:', data);
                LlenarTablaPacientes(data);
            })
            .catch(error => {
                console.error('Error en endpoint filtrado grupo:', error);
            });
        } else if (filtroAsignados && userGuid && userGuid !== 'SIN GUID') {
            // Filtro por asignados
            fetch('/get_examination_items_asignados', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_guid: userGuid, include_reported: filtroVerFinalizados })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Datos recibidos del filtro asignados:', data);
                LlenarTablaPacientes(data);
            })
            .catch(error => {
                console.error('Error en endpoint asignados:', error);
            });
        } else {
            // Sin filtro específico, pero puede tener filtro de finalizados
            var endpoint = filtroVerFinalizados ? '/get_examination_items_all' : '/get_examination_items';
            fetch(endpoint)
            .then(response => response.json())
            .then(data => {
                console.log('Datos recibidos sin filtro:', data);
                LlenarTablaPacientes(data);
            })
            .catch(error => {
                console.error('Error en endpoint normal:', error);
            });
        }
    }

    // Llenar la tabla con los datos recibidos
    function LlenarTablaPacientes(data) {
        var tabla = document.getElementById('tabla-pacientes');
        var tbody = tabla.querySelector('tbody');
        tbody.innerHTML = '';
        
        if (!data || data.length === 0) {
            console.log('No se encontraron datos para mostrar');
            
            // Mostrar mensaje de "No hay estudios"
            var tr = document.createElement('tr');
            tr.classList.add('no-estudios-row');
            tr.style.pointerEvents = 'none'; // No clickeable
            tr.style.userSelect = 'none'; // No seleccionable
            var td = document.createElement('td');
            td.setAttribute('colspan', '8'); // 8 columnas visibles en la tabla
            td.style.textAlign = 'center';
            td.style.padding = '3rem 1rem';
            td.style.fontSize = '1.1rem';
            td.style.color = '#2dce89';
            td.style.fontWeight = '600';
            td.innerHTML = '<i class="fas fa-check-circle" style="font-size: 2.5rem; color: #2dce89; margin-bottom: 1rem; display: block;"></i>' +
                          'No quedan estudios asignados a tu nombre';
            tr.appendChild(td);
            tbody.appendChild(tr);
            return;
        }
        
        data.forEach(function(fila) {
            var tr = document.createElement('tr');
            
            // Verificar si es un array o un objeto
            if (Array.isArray(fila)) {
                // Para datos: [Guid, createdon, nombre, dni, sex, estudio, status, severidad, isreported, isimage]
                tr.setAttribute('data-id', fila[0]);
                
                // Los últimos elementos son isreported (índice 8) e isimage (índice 9)
                var isreported = fila.length > 8 ? fila[8] : 0;
                var isimage = fila.length > 9 ? fila[9] : 0;
                
                // Aplicar clase CSS si está reportado
                if (isreported === 1) {
                    tr.classList.add('estudio-reportado');
                }
                
                // Crear las celdas (índices 1-7: fecha, nombre, dni, sexo, estudio, status, severidad)
                for (var i = 1; i <= 7; i++) {
                    var td = document.createElement('td');
                    td.textContent = fila[i];
                    tr.appendChild(td);
                }
                
                // Agregar columna DICOM (la columna ya existe en HTML, solo llenamos el contenido)
                var tdDicom = document.createElement('td');
                tdDicom.style.textAlign = 'center';
                if (isimage === 1) {
                    tdDicom.innerHTML = '<i class="fas fa-eye text-primary" style="cursor: pointer;" onclick="VerDcm(\'' + fila[0] + '\')" title="Ver imágenes DICOM"></i>';
                } else {
                    tdDicom.innerHTML = '<i class="fas fa-times text-muted" title="Sin imágenes DICOM"></i>';
                }
                tr.appendChild(tdDicom);
                
            } else {
                // Para datos no filtrados (mantener compatibilidad)
                tr.setAttribute('data-id', fila[0]);
                for (var i = 1; i < fila.length; i++) {
                    var td = document.createElement('td');
                    td.textContent = fila[i];
                    tr.appendChild(td);
                }
            }
            
            tbody.appendChild(tr);
        });
        
        console.log(`Tabla actualizada con ${data.length} registros`);
    }

    // Evento para los checkboxes de filtro
    document.getElementById('filtro_mis_examenes').addEventListener('change', recargarTablaPacientes);
    document.getElementById('filtro_estudios_asignados').addEventListener('change', recargarTablaPacientes);
    document.getElementById('filtro_ver_finalizados').addEventListener('change', recargarTablaPacientes);

    // Inicializar tabla al cargar
    recargarTablaPacientes();
    ConfigurarTabla('tabla-pacientes', 'botones_sp');

    var boton = document.getElementById("generar_informe");
    boton.addEventListener("click", function () { GenerarInforme('tabla-pacientes') });
    // Evento de doble click para abrir informe directamente
    tbody_g = document.querySelector('#tabla-pacientes tbody');
    tbody_g.addEventListener('dblclick', function () { GenerarInforme('tabla-pacientes') });
});



