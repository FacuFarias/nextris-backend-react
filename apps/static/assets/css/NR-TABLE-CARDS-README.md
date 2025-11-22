# NR Table Cards - Guía de Uso

## 📋 Descripción
Sistema de estilos reutilizable para cards con tablas scrollables, sticky headers y badges personalizados.

## 🎨 Clases Disponibles

### Cards con Tablas

#### `.nr-table-card`
Card principal con sombra y header con degradado.

```html
<div class="card nr-table-card">
  <div class="card-header">
    <h6>Título de la Card</h6>
  </div>
  <div class="card-body nr-table-card-body">
    <table class="nr-table table">
      <!-- contenido -->
    </table>
  </div>
</div>
```

#### `.nr-table-card-body`
Cuerpo de la card con scroll y altura controlada (50vh / 300px mín).

**Características:**
- ✅ Max height: 50vh
- ✅ Min height: 300px
- ✅ Scroll vertical automático
- ✅ Scrollbar personalizado

#### `.nr-table-card-body-sm`
Versión pequeña para cards secundarias (25vh).

**Uso:** Ideal para columnas laterales o cards complementarias.

```html
<div class="card-body nr-table-card-body-sm">
  <!-- contenido reducido -->
</div>
```

### Tablas

#### `.nr-table`
Tabla estilizada con header sticky y degradado púrpura.

**Características:**
- ✅ Header fijo al hacer scroll
- ✅ Degradado púrpura en header
- ✅ Filas con hover effect
- ✅ Selección con clase `.fila-seleccionada`

```html
<table class="nr-table table">
  <thead>
    <tr>
      <th>Columna 1</th>
      <th>Columna 2</th>
    </tr>
  </thead>
  <tbody>
    <tr class="fila-seleccionada">
      <td>Dato 1</td>
      <td>Dato 2</td>
    </tr>
  </tbody>
</table>
```

### Badges

#### `.nr-badge`
Badge/pill genérico reutilizable.

```html
<span class="nr-badge">TEXTO</span>
```

#### Variantes de Color

```html
<span class="nr-badge nr-badge-primary">PRIMARY</span>
<span class="nr-badge nr-badge-success">SUCCESS</span>
<span class="nr-badge nr-badge-danger">DANGER</span>
<span class="nr-badge nr-badge-warning">WARNING</span>
<span class="nr-badge nr-badge-info">INFO</span>
```

**Colores:**
- `nr-badge-primary` → Púrpura (#667eea)
- `nr-badge-success` → Verde (#10b981)
- `nr-badge-danger` → Rojo (#ef4444)
- `nr-badge-warning` → Naranja (#f59e0b)
- `nr-badge-info` → Cyan (#06b6d4)

### Estado Vacío

#### `.nr-table-empty`
Mensaje centrado para tablas sin datos.

```html
<tbody>
  <tr>
    <td colspan="3" class="nr-table-empty">
      <i class="fas fa-inbox"></i>
      No hay datos disponibles
    </td>
  </tr>
</tbody>
```

## 📱 Responsividad

En pantallas < 768px:
- Card body reduce a 40vh (min 200px)
- Card body-sm reduce a 20vh
- Fuentes y padding reducidos automáticamente

## 🔧 Ejemplo Completo

```html
<div class="row">
  <!-- Tabla principal -->
  <div class="col-8">
    <div class="card nr-table-card">
      <div class="card-header">
        <h6>Estudios Disponibles</h6>
      </div>
      <div class="card-body nr-table-card-body">
        <table class="nr-table table">
          <thead>
            <tr>
              <th>Código</th>
              <th>Descripción</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            <tr class="fila-seleccionada">
              <td>EST001</td>
              <td>Tomografía</td>
              <td><span class="nr-badge nr-badge-success">ACTIVO</span></td>
            </tr>
            <tr>
              <td>EST002</td>
              <td>Ecografía</td>
              <td><span class="nr-badge nr-badge-warning">PENDIENTE</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Tabla secundaria -->
  <div class="col-4">
    <div class="card nr-table-card">
      <div class="card-header">
        <h6>Detalles</h6>
      </div>
      <div class="card-body nr-table-card-body-sm">
        <table class="nr-table table">
          <thead>
            <tr>
              <th>Equipo</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Equipo A</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
```

## 🎯 Casos de Uso

### ✅ Usar cuando:
- Necesites tablas con scroll y header fijo
- Quieras badges de estado/categoría
- Tengas listas largas en cards
- Necesites selección visual de filas

### ❌ No usar cuando:
- Tabla tiene pocas filas (< 5)
- No necesitas scroll
- Prefieres paginación en lugar de scroll

## 🔗 Archivos Relacionados

- **CSS:** `/static/assets/css/nr-table-cards.css`
- **Ejemplo:** `apps/templates/includes/admision_templates/exam.html`

## 📝 Notas

- Las clases `.tabla-estudios` son específicas de admisión espontánea
- Para badges de modalidades médicas, ver estilos específicos en `admision_espontanea.html`
- Compatible con Bootstrap 5
