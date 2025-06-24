
// Tengo que poner los nombres de los campos del modal. Es necesario que tengan un id diferente para campos que sean iguales y tienen que ser en el orden que aparecen en la fila. Por ejemplo, description
var configNP = [
    { modalFieldId: 'p_name', type: 'text' },
    { modalFieldId: 'p_surname', type: 'text' },
    { modalFieldId: 'p_dni', type: 'number' },
    { modalFieldId: 'sex', type: 'select-one' },
    { modalFieldId: 'fecha_nacimiento', type: 'date' },
    
    { modalFieldId: 'telefono', type: 'text' },
    { modalFieldId: 'mail', type: 'text' },
    { modalFieldId: 'p_healthcard', type: 'text' },
    
];


document.addEventListener("DOMContentLoaded", function() {
    // configuracion de busqueda y llenado de tabla
    RellenarTabla('tabla-pacientes',`/get_patients`)

    ConfigurarTabla('tabla-pacientes','botones_sp')

    // Configuro agregar paciente
    ConfigDefaultModal('Form_ag','/agregar_pacientes','#modal_np',"tabla-pacientes")
    SetEditButton('editar-paciente', "Form_ag", "modal_np", "tabla-pacientes", '/editar_paciente', configNP,'id_np')
    SetDeleteButton('eliminar-paciente','tabla-pacientes','/eliminar_paciente')

    ConfigFiltrarText('l_name', 'tabla-pacientes',0)
    ConfigFiltrarText('l_surname', 'tabla-pacientes',1)
    ConfigFiltrarText('documento', 'tabla-pacientes',2)
    ConfigFiltrarSelect('l_sex', 'tabla-pacientes',3)
    ConfigFiltrarFecha('fecha_nac', 'tabla-pacientes',4)
    ConfigFiltrarText('l_Telefono', 'tabla-pacientes',5)
    ConfigFiltrarText('buscar_mail', 'tabla-pacientes',5)
    ConfigFiltrarText('tarjeta_sanitaria', 'tabla-pacientes',7)

    const searchCard = document.querySelector(".nr-card-1");
    const backgroundElement = document.querySelector(".position-absolute");

    function adjustBackgroundSize() {
        // Aumentamos el tiempo de espera para asegurar que los estilos se han aplicado completamente
        setTimeout(() => {
            const searchCardHeight = searchCard.getBoundingClientRect().height;
            backgroundElement.style.height = `${searchCardHeight + 30}px`;
        }, 150); // Aumentamos a 300ms, puedes ajustar si es necesario
    }

    // Ajusta el tamaño del fondo al cargar la página
    adjustBackgroundSize();

    // Ajusta el tamaño del fondo cuando la tarjeta de búsqueda se colapsa o expande
    searchCard.addEventListener('transitionend', adjustBackgroundSize);

    // Para asegurar que el tamaño se ajuste si hay cambios en el tamaño de la ventana
    window.addEventListener('resize', adjustBackgroundSize);

});
