"""
Modelos de datos para el sistema RIS
"""

class Cita:
    """Modelo para representar una cita médica"""
    
    def __init__(self, paciente_id=None, fecha=None, time=None, paciente_dni=None, machine=None, codigo_examen=None,
                 coste=None, urgencia=None, medico=None, cons_investigacion=None, exp_sanitario=None,
                 exp_san_elec=None):
        self.fecha = fecha
        self.time = time
        self.paciente_dni = paciente_dni
        self.machine = machine
        self.codigo_examen = codigo_examen
        self.coste = coste
        self.urgencia = urgencia
        self.medico = medico
        self.cons_investigacion = cons_investigacion
        self.exp_sanitario = exp_sanitario
        self.exp_san_elec = exp_san_elec
        self.paciente_id = paciente_id

    def to_dict(self):
        """Convertir el objeto a un diccionario"""
        return {
            'fecha': self.fecha,
            'time': self.time,
            'paciente_dni': self.paciente_dni,
            'machine': self.machine,
            'codigo_examen': self.codigo_examen,
            'coste': self.coste,
            'urgencia': self.urgencia,
            'medico': self.medico,
            'cons_investigacion': self.cons_investigacion,
            'exp_sanitario': self.exp_sanitario,
            'exp_san_elec': self.exp_san_elec,
            'paciente_id': self.paciente_id
        }

    @classmethod
    def from_dict(cls, data):
        """Crear un objeto Cita a partir de un diccionario"""
        return cls(**data)


class Orden:
    """Modelo para representar una orden médica"""
    
    def __init__(self, paciente_id=None, fecha=None, time=None, EquipmentId=None, ExamId=None,
                 coste=None, urgencia=None, medico_solicitante=None, cons_investigacion=None, exp_sanitario=None,
                 exp_san_elec=None):
        self.fecha = fecha
        self.time = time
        self.EquipmentId = EquipmentId
        self.ExamId = ExamId
        self.coste = coste
        self.urgencia = urgencia
        self.medico_solicitante = medico_solicitante
        self.cons_investigacion = cons_investigacion
        self.exp_sanitario = exp_sanitario
        self.exp_san_elec = exp_san_elec
        self.paciente_id = paciente_id

    def to_dict(self):
        """Convertir el objeto a un diccionario"""
        return {
            'fecha': self.fecha,
            'time': self.time,
            'EquipmentId': self.EquipmentId,
            'ExamId': self.ExamId,
            'coste': self.coste,
            'urgencia': self.urgencia,
            'medico_solicitante': self.medico_solicitante,
            'cons_investigacion': self.cons_investigacion,
            'exp_sanitario': self.exp_sanitario,
            'exp_san_elec': self.exp_san_elec,
            'paciente_id': self.paciente_id
        }

    @classmethod
    def from_dict(cls, data):
        """Crear un objeto Orden a partir de un diccionario"""
        return cls(**data)