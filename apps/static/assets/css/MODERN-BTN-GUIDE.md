# Modern Buttons - Guía de Uso

## Descripción
Sistema de botones moderno y reutilizable para NextRIS con estilo "pills" (píldoras), efectos glassmorphism y hover elegantes.

## Instalación

Importar el archivo CSS en tu template HTML:

```html
<link rel="stylesheet" href="/static/assets/css/modern-btn.css">
```

## Estructura Básica

### Botón Estándar
```html
<button type="button" class="btn-header">
    <i class="fas fa-icon"></i>
    <span class="btn-text">Texto</span>
</button>
```

## Variantes de Botones

### 1. Botón DCM (Ver Imágenes DICOM)
```html
<button type="button" class="btn-header btn-dcm">
    <i class="fas fa-image"></i>
    <span class="btn-text">DCM</span>
</button>
```

### 2. Botón Guardar
```html
<button type="button" class="btn-header btn-save">
    <i class="fa fa-save"></i>
    <span class="btn-text">Guardar</span>
</button>
```

### 3. Botón Firmar
```html
<button type="button" class="btn-header btn-sign">
    <i class="fas fa-signature"></i>
    <span class="btn-text">Firmar</span>
</button>
```

### 4. Botón PDF
```html
<button type="button" class="btn-header btn-pdf">
    <i class="far fa-file-pdf"></i>
    <span class="btn-text">PDF</span>
</button>
```

### 5. Botón Volver (Especial)
```html
<button type="button" class="btn-header btn-back">
    <i class="fa fa-arrow-left"></i>
    <span class="btn-text">Volver</span>
</button>
```

### 6. Botón Email
```html
<button type="button" class="btn-header btn-email">
    <i class="fas fa-envelope"></i>
    <span class="btn-text">Email</span>
</button>
```

### 7. Botón Imprimir
```html
<button type="button" class="btn-header btn-print">
    <i class="fas fa-print"></i>
    <span class="btn-text">Imprimir</span>
</button>
```

### 8. Botón Compartir
```html
<button type="button" class="btn-header btn-share">
    <i class="fas fa-share-alt"></i>
    <span class="btn-text">Compartir</span>
</button>
```

### 9. Botón Editar
```html
<button type="button" class="btn-header btn-edit">
    <i class="fas fa-edit"></i>
    <span class="btn-text">Editar</span>
</button>
```

### 10. Botón Eliminar/Danger
```html
<button type="button" class="btn-header btn-danger">
    <i class="fas fa-trash"></i>
    <span class="btn-text">Eliminar</span>
</button>
```

### 11. Botón Success/Confirmar
```html
<button type="button" class="btn-header btn-success">
    <i class="fas fa-check"></i>
    <span class="btn-text">Confirmar</span>
</button>
```

## Tamaños

### Botón Pequeño
```html
<button type="button" class="btn-header btn-header-sm btn-save">
    <i class="fa fa-save"></i>
    <span class="btn-text">Guardar</span>
</button>
```

### Botón Grande
```html
<button type="button" class="btn-header btn-header-lg btn-sign">
    <i class="fas fa-signature"></i>
    <span class="btn-text">Firmar</span>
</button>
```

### Solo Ícono (Circular)
```html
<button type="button" class="btn-header btn-header-icon btn-pdf">
    <i class="far fa-file-pdf"></i>
</button>
```

## Estados

### Botón Deshabilitado
```html
<button type="button" class="btn-header btn-save" disabled>
    <i class="fa fa-save"></i>
    <span class="btn-text">Guardar</span>
</button>

<!-- O usando clase -->
<button type="button" class="btn-header btn-save disabled">
    <i class="fa fa-save"></i>
    <span class="btn-text">Guardar</span>
</button>
```

### Botón Activo/Seleccionado
```html
<button type="button" class="btn-header btn-dcm active">
    <i class="fas fa-image"></i>
    <span class="btn-text">DCM</span>
</button>
```

### Botón con Animación de Pulso
```html
<button type="button" class="btn-header btn-sign pulse">
    <i class="fas fa-signature"></i>
    <span class="btn-text">Firmar</span>
</button>
```

### Botón con Carga (Spinner)
```html
<button type="button" class="btn-header btn-save loading">
    <i class="fas fa-spinner"></i>
    <span class="btn-text">Guardando...</span>
</button>
```

## Grupos de Botones

### Con Container
```html
<div class="btn-group-header">
    <button type="button" class="btn-header btn-dcm">
        <i class="fas fa-image"></i>
        <span class="btn-text">DCM</span>
    </button>
    <button type="button" class="btn-header btn-save">
        <i class="fa fa-save"></i>
        <span class="btn-text">Guardar</span>
    </button>
    <button type="button" class="btn-header btn-sign">
        <i class="fas fa-signature"></i>
        <span class="btn-text">Firmar</span>
    </button>
</div>
```

### Con Separadores
```html
<div class="btn-group-header">
    <button type="button" class="btn-header btn-dcm">
        <i class="fas fa-image"></i>
        <span class="btn-text">DCM</span>
    </button>
    
    <div class="btn-separator"></div>
    
    <button type="button" class="btn-header btn-save">
        <i class="fa fa-save"></i>
        <span class="btn-text">Guardar</span>
    </button>
    <button type="button" class="btn-header btn-sign">
        <i class="fas fa-signature"></i>
        <span class="btn-text">Firmar</span>
    </button>
    
    <div class="btn-separator"></div>
    
    <button type="button" class="btn-header btn-back">
        <i class="fa fa-arrow-left"></i>
        <span class="btn-text">Volver</span>
    </button>
</div>
```

## Ejemplo de Header Completo

```html
<header class="topbar">
    <div class="avatar">
        <i class="fa fa-user-circle" aria-hidden="true"></i>
    </div>
    <div class="pt-info">
        <div class="pt-name">Juan Pérez</div>
        <div class="pt-meta">
            <span class="badge-info">ADM-12345</span> · DNI 12.345.678
        </div>
    </div>
    <div class="crumb">
        <button type="button" class="btn-header btn-dcm" id="b_ver_imagenes">
            <i class="fas fa-image"></i>
            <span class="btn-text">DCM</span>
        </button>
        <button type="button" class="btn-header btn-save" id="b_guardar_reporte">
            <i class="fa fa-save"></i>
            <span class="btn-text">Guardar</span>
        </button>
        <button type="button" class="btn-header btn-sign" id="b_firmar_reporte">
            <i class="fas fa-signature"></i>
            <span class="btn-text">Firmar</span>
        </button>
        <button type="button" class="btn-header btn-pdf" id="b_ver_pdf">
            <i class="far fa-file-pdf"></i>
            <span class="btn-text">PDF</span>
        </button>
        
        <div class="btn-separator"></div>
        
        <button type="button" class="btn-header btn-back" id="b_atras">
            <i class="fa fa-arrow-left"></i>
            <span class="btn-text">Volver</span>
        </button>
    </div>
</header>
```

## JavaScript - Controlar Estados

### Deshabilitar/Habilitar Botón
```javascript
// Deshabilitar
document.getElementById('b_guardar_reporte').disabled = true;
// O con clase
document.getElementById('b_guardar_reporte').classList.add('disabled');

// Habilitar
document.getElementById('b_guardar_reporte').disabled = false;
document.getElementById('b_guardar_reporte').classList.remove('disabled');
```

### Agregar Pulso
```javascript
document.getElementById('b_firmar_reporte').classList.add('pulse');

// Quitar después de 3 segundos
setTimeout(() => {
    document.getElementById('b_firmar_reporte').classList.remove('pulse');
}, 3000);
```

### Estado de Carga
```javascript
const btn = document.getElementById('b_guardar_reporte');
const icon = btn.querySelector('i');
const text = btn.querySelector('.btn-text');

// Iniciar carga
btn.classList.add('loading');
btn.disabled = true;
icon.className = 'fas fa-spinner';
text.textContent = 'Guardando...';

// Terminar carga
setTimeout(() => {
    btn.classList.remove('loading');
    btn.disabled = false;
    icon.className = 'fa fa-save';
    text.textContent = 'Guardar';
}, 2000);
```

## Responsive

Los botones son **completamente responsive**:

- **Desktop**: Muestran ícono + texto
- **Tablet (< 768px)**: Solo muestran ícono
- **Móvil (< 480px)**: Ícono más pequeño y compacto

No necesitas hacer nada especial, es automático.

## Colores de Variantes

- **btn-dcm**: Azul (imágenes DICOM)
- **btn-save**: Verde (guardar)
- **btn-sign**: Púrpura (firmar)
- **btn-pdf**: Rojo (PDF)
- **btn-back**: Rojo gradiente (volver)
- **btn-email**: Amarillo (email)
- **btn-print**: Gris (imprimir)
- **btn-share**: Azul claro (compartir)
- **btn-edit**: Naranja (editar)
- **btn-danger**: Rojo (eliminar)
- **btn-success**: Verde (confirmar)

## Compatibilidad

- ✅ Compatible con todos los navegadores modernos
- ✅ Funciona con Font Awesome 5.x y 6.x
- ✅ Responsive por defecto
- ✅ Accesibilidad incluida (ARIA labels recomendados)
- ✅ No requiere JavaScript (excepto para estados dinámicos)

## Notas

1. Todos los estilos usan `!important` para evitar conflictos con otros CSS
2. Los botones usan `backdrop-filter` para efecto glassmorphism (puede no funcionar en navegadores muy antiguos)
3. Las animaciones usan `cubic-bezier` para transiciones suaves
4. El texto se oculta automáticamente en pantallas pequeñas
