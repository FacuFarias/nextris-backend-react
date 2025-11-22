

document.addEventListener("DOMContentLoaded", function() {

    var guardarConfiguracionBtn = document.getElementById('guardar-configuracion');
    if (guardarConfiguracionBtn) {
        guardarConfiguracionBtn.addEventListener('click', function() {
            var agendaTipo = document.getElementById('agenda-tipo').value;
            var agendaEstudios = document.getElementById('agenda-estudios').value;
            console.log('Tipo de agenda:', agendaTipo);
            console.log('Estudios en agenda:', agendaEstudios); 

            fetch('/guardar_config_workflow', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    tipo: agendaTipo,
                    estudios: agendaEstudios
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Configuración guardada exitosamente.');
                } else {
                    alert('Error al guardar la configuración.');
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
        });
    }
    

});
