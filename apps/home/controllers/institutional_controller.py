"""
Controller para gestión de información institucional
Migrado desde routes.py - función institucional_info()
"""

from flask import Blueprint, request, jsonify
import os
import uuid
from PIL import Image
from apps.home.services.database_service import DatabaseService

# Crear blueprint con URL prefix único
institutional_bp = Blueprint('institutional', __name__, url_prefix='/api')

@institutional_bp.route('/institucional-info', methods=['GET', 'POST'])
def institucional_info():
    """
    GET: Obtiene información institucional de la base de datos
    POST: Actualiza/inserta información institucional con manejo de logo
    
    Migrado desde routes.py con las siguientes mejoras:
    - Uso de DatabaseService en lugar de conexión manual
    - Mejor manejo de errores
    - Código más limpio y reutilizable
    """
    
    if request.method == 'GET':
        # 🔍 Obtener información institucional
        try:
            query = """
                SELECT guid, name, mail, address, phone, logo_path 
                FROM nextris.isbasicinformation 
                ORDER BY guid ASC 
                LIMIT 1
            """
            result = DatabaseService.execute_query(query)
            
            if result and len(result) > 0:
                row = result[0]
                return jsonify({
                    'guid': row[0],
                    'name': row[1], 
                    'mail': row[2],
                    'address': row[3],
                    'phone': row[4],
                    'logo_path': row[5]
                })
            else:
                return jsonify({})
                
        except Exception as e:
            print(f"Error obteniendo información institucional: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500
    
    elif request.method == 'POST':
        # 📝 Actualizar/insertar información institucional
        try:
            # Obtener datos del formulario
            name = request.form.get('name')
            mail = request.form.get('mail')
            address = request.form.get('address')
            phone = request.form.get('phone')
            logo_file = request.files.get('logo')
            logo_path = None
            
            # 🖼️ Procesar logo si se envió
            if logo_file and logo_file.filename:
                logo_path = _process_institutional_logo(logo_file)
            
            # 🔍 Verificar si ya existe un registro
            check_query = "SELECT guid FROM nextris.isbasicinformation LIMIT 1"
            existing = DatabaseService.execute_query(check_query)
            
            if existing and len(existing) > 0:
                # ✏️ Actualizar registro existente
                guid = existing[0][0]
                if logo_path:
                    update_query = """
                        UPDATE nextris.isbasicinformation 
                        SET name=%s, mail=%s, address=%s, phone=%s, logo_path=%s 
                        WHERE guid=%s
                    """
                    params = (name, mail, address, phone, logo_path, guid)
                else:
                    update_query = """
                        UPDATE nextris.isbasicinformation 
                        SET name=%s, mail=%s, address=%s, phone=%s 
                        WHERE guid=%s
                    """
                    params = (name, mail, address, phone, guid)
                    
                DatabaseService.execute_query(update_query, params, commit=True)
            else:
                # ➕ Crear nuevo registro
                guid = str(uuid.uuid4())
                insert_query = """
                    INSERT INTO nextris.isbasicinformation 
                    (guid, name, mail, address, phone, logo_path) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                params = (guid, name, mail, address, phone, logo_path)
                DatabaseService.execute_query(insert_query, params, commit=True)
            
            return jsonify({'success': True})
            
        except Exception as e:
            print(f"Error guardando información institucional: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500


def _process_institutional_logo(logo_file):
    """
    Procesa y guarda el logo institucional
    Redimensiona a 100x100px y maneja diferentes formatos
    
    Args:
        logo_file: Archivo de imagen desde request.files
        
    Returns:
        str: Ruta del archivo guardado o None si hay error
    """
    try:
        # 📁 Configurar directorios
        ext = os.path.splitext(logo_file.filename)[1]
        logo_filename = f"logo_institucional{ext}"
        logo_dir = os.path.join('apps', 'static', 'assets', 'img')
        os.makedirs(logo_dir, exist_ok=True)
        logo_full_path = os.path.join(logo_dir, logo_filename)
        
        # 🖼️ Procesar imagen
        img = Image.open(logo_file)
        
        # Convertir a RGBA para manipulación
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
            
        # Redimensionar manteniendo aspecto a 100x100px
        size = (100, 100)
        new_img = Image.new('RGBA', size, (255, 255, 255, 0))
        ratio = min(size[0] / img.width, size[1] / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        
        # Centrar imagen
        paste_pos = ((size[0] - new_size[0]) // 2, (size[1] - new_size[1]) // 2)
        new_img.paste(img, paste_pos)
        
        # 💾 Guardar según formato
        if ext.lower() in ['.jpg', '.jpeg']:
            # Para JPG, convertir a RGB con fondo blanco
            rgb_img = Image.new('RGB', size, (255, 255, 255))
            rgb_img.paste(new_img, mask=new_img.split()[3])
            rgb_img.save(logo_full_path, quality=95)
        else:
            # Para PNG mantener transparencia
            new_img.save(logo_full_path)
        
        # 🔄 Normalizar ruta para BD
        logo_path = logo_full_path.replace('\\', '/').replace('d:/', '/').replace('D:/', '/')
        return logo_path
        
    except Exception as e:
        print(f"Error procesando logo institucional: {e}")
        return None