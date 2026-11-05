# Directivas de Nexi

`NEXI_DIRECTIVES.md` contiene las directivas vigentes del asistente y se distribuye con el backend. `apps/api/nexi.py` lo carga de forma predeterminada.

Para usar otro archivo, definir `NEXI_DIRECTIVES_PATH` con su ruta absoluta. La antigua carpeta externa `/var/www/nexi` ya no es necesaria con la configuración predeterminada. Si falta el archivo, se usa el texto de respaldo definido en el módulo.
