# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from flask import Blueprint

blueprint = Blueprint(
    'home_blueprint',
    __name__,
    url_prefix=''
)

# Registrar controladores adicionales
from apps.home.controllers.report_controller import report_bp
from apps.home.controllers.admin_controller import admin_bp
from apps.home.controllers.appointment_controller import appointment_bp, appointment_legacy_bp
from apps.home.controllers.medical_controller import medical_bp
from apps.home.controllers.institutional_controller import institutional_bp
from apps.home.controllers.config_controller import config_bp

# Importar patient_controller para registrar sus rutas
from apps.home.controllers import patient_controller

# Importar config_controller para registrar sus rutas
from apps.home.controllers import config_controller

# Importar examination_controller para registrar sus rutas
from apps.home.controllers import examination_controller

# Importar routes.py para registrar endpoints globales
from apps.home import routes
# from apps.home import routes_backup_masivo  # Comentado por conflictos de rutas duplicadas

# Importar funciones específicas para el blueprint principal
from apps.home.controllers.report_controller import verpdf, get_inf_predefinidos, get_predefinido, quitar_definitivo, guardar_reporte, firmar_reporte, editar_predefinido, guardar_predefinido, send_mail
from apps.home.controllers.appointment_controller import obtener_agenda, get_citas, get_citas_for_today, actualizar_datos_cita, get_events_para_editar, actualizar_evento_cita, eliminar_cita
from apps.home.controllers.medical_controller import get_exams_modal, get_users
from apps.home.controllers.examination_controller import get_examination_details, ejecutar_orden, get_examination_items, get_data_report, get_orders_to_distribution
from apps.home.controllers.patient_controller import edit_mail
from apps.home.controllers.config_controller import (
    get_origins_group, get_origins, get_modalities, get_body_parts, 
    get_exams, get_mach, get_equip_agenda, get_med_sol, get_agenda_med, 
    get_days_agenda_equip, get_equipment_studygroup, get_days_agenda, 
    get_grupos_medico
)

blueprint.register_blueprint(report_bp)
blueprint.register_blueprint(admin_bp)
blueprint.register_blueprint(appointment_bp)
blueprint.register_blueprint(appointment_legacy_bp)
blueprint.register_blueprint(medical_bp)
blueprint.register_blueprint(institutional_bp)
blueprint.register_blueprint(config_bp)

# Agregar rutas de compatibilidad (sin prefijo /api)
blueprint.add_url_rule('/verpdf/<report_id>', 'verpdf', verpdf, methods=['GET'])
blueprint.add_url_rule('/get_inf_predefinidos', 'get_inf_predefinidos', get_inf_predefinidos, methods=['GET'])
blueprint.add_url_rule('/get_predefinido/<guid>', 'get_predefinido', get_predefinido, methods=['GET'])
blueprint.add_url_rule('/obtener_agenda', 'obtener_agenda', obtener_agenda, methods=['GET', 'POST'])
blueprint.add_url_rule('/get_citas', 'get_citas', get_citas, methods=['GET'])
blueprint.add_url_rule('/get_citas_for_today', 'get_citas_for_today', get_citas_for_today, methods=['GET'])
blueprint.add_url_rule('/get_exams_modal', 'get_exams_modal', get_exams_modal, methods=['GET'])
blueprint.add_url_rule('/get_users', 'get_users', get_users, methods=['GET'])
blueprint.add_url_rule('/actualizar_datos_cita', 'actualizar_datos_cita', actualizar_datos_cita, methods=['POST'])
blueprint.add_url_rule('/get_events_para_editar', 'get_events_para_editar', get_events_para_editar, methods=['POST'])
blueprint.add_url_rule('/actualizar_evento_cita', 'actualizar_evento_cita', actualizar_evento_cita, methods=['POST'])
blueprint.add_url_rule('/eliminar_cita', 'eliminar_cita', eliminar_cita, methods=['POST'])

# Rutas de examination_controller (compatibilidad)
blueprint.add_url_rule('/get_examination_details', 'get_examination_details', get_examination_details, methods=['POST'])
blueprint.add_url_rule('/ejecutar_orden', 'ejecutar_orden', ejecutar_orden, methods=['POST'])
blueprint.add_url_rule('/get_examination_items', 'get_examination_items', get_examination_items, methods=['GET'])
blueprint.add_url_rule('/get_data_report', 'get_data_report', get_data_report, methods=['POST'])
blueprint.add_url_rule('/get_orders_to_distribution', 'get_orders_to_distribution', get_orders_to_distribution, methods=['GET'])

# Rutas de patient_controller (compatibilidad)
blueprint.add_url_rule('/edit_mail', 'edit_mail', edit_mail, methods=['POST'])

# Rutas de config_controller (compatibilidad)
blueprint.add_url_rule('/get_origins_group', 'get_origins_group', get_origins_group, methods=['GET'])
blueprint.add_url_rule('/get_origins', 'get_origins', get_origins, methods=['GET'])
blueprint.add_url_rule('/get_modalities', 'get_modalities', get_modalities, methods=['GET'])
blueprint.add_url_rule('/get_body_parts', 'get_body_parts', get_body_parts, methods=['GET'])
blueprint.add_url_rule('/get_exams', 'get_exams', get_exams, methods=['GET'])
blueprint.add_url_rule('/get_mach', 'get_mach', get_mach, methods=['GET'])
blueprint.add_url_rule('/get_equip_agenda', 'get_equip_agenda', get_equip_agenda, methods=['GET'])
blueprint.add_url_rule('/get_med_sol', 'get_med_sol', get_med_sol, methods=['GET'])
blueprint.add_url_rule('/get_agenda_med', 'get_agenda_med', get_agenda_med, methods=['GET'])
blueprint.add_url_rule('/get_days_agenda_equip', 'get_days_agenda_equip', get_days_agenda_equip, methods=['POST'])
blueprint.add_url_rule('/get_equipment_studygroup', 'get_equipment_studygroup', get_equipment_studygroup, methods=['POST'])
blueprint.add_url_rule('/get_days_agenda', 'get_days_agenda', get_days_agenda, methods=['POST'])
blueprint.add_url_rule('/get_grupos_medico', 'get_grupos_medico', get_grupos_medico, methods=['POST'])

# Rutas de report_controller (compatibilidad)
blueprint.add_url_rule('/quitar_definitivo', 'quitar_definitivo', quitar_definitivo, methods=['POST'])
blueprint.add_url_rule('/guardar_reporte', 'guardar_reporte', guardar_reporte, methods=['POST'])
blueprint.add_url_rule('/firmar_reporte', 'firmar_reporte', firmar_reporte, methods=['POST'])
blueprint.add_url_rule('/editar_predefinido', 'editar_predefinido', editar_predefinido, methods=['POST'])
blueprint.add_url_rule('/guardar_predefinido', 'guardar_predefinido', guardar_predefinido, methods=['POST'])
blueprint.add_url_rule('/send_mail/<report_id>', 'send_mail', send_mail, methods=['GET'])
