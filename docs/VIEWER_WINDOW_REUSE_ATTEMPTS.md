# Intentos de reutilizar ventana del visor DICOM

## Objetivo
Que al abrir imágenes desde NextRIS (:3001), si ya hay una ventana del visor (:3000) abierta, se reutilice en vez de abrir una nueva.

## Intentos fallidos

### 1. `window.open(url, "dicom-viewer", features)` con nombre fijo
Se usó `window.open(url, "dicom-viewer", "width=1400,...")` esperando que Chrome reutilizara la ventana por nombre.
**Fallo**: Chrome ignora el parámetro `name` cuando se especifican `features` (width, height, etc). Siempre abre una nueva ventana.

### 2. Guardar referencia en `window.__dicomViewerWindow`
Se almacenó la referencia del `Window` retornado en `window.__dicomViewerWindow` y se verificaba con `existing && !existing.closed`.
**Fallo**: Aparentemente Vite HMR reinicia el contexto del módulo, perdiendo la referencia. La propiedad en `window` debería persistir, pero no funcionó en pruebas.

### 3. Guardar referencia en `window.__dicomViewerRef` + `window.open("", name)` sin features
Se intentó `window.open("", "dicom-viewer")` sin features para recuperar la ventana existente por nombre, antes de abrir una nueva.
**Fallo**: `window.open("", name)` en Chrome retorna `null` cuando la ventana fue abierta originalmente con features (popup). Chrome trata popups y tabs/ventanas como contextos distintos.

### 4. Módulo ES compartido (`use-viewer-window.ts`) con `let viewerWindowRef`
Se creó un módulo ES con una variable `let` compartida entre Imagenes.tsx y columns.tsx.
**Fallo**: Vite HMR re-ejecuta el módulo y resetea la variable `let viewerWindowRef = null`, perdiendo la referencia guardada.

### 5. `sessionStorage` como flag de persistencia
Se usó `sessionStorage.setItem("dicomViewerOpen", "1")` para sobrevivir a HMR, y `window.open("", name)` para recuperar la referencia.
**Fallo**: `window.open("", name)` no puede acceder a la ventana popup cross-origin (:3000 vs :3001). Además abre una tab nueva en vez de reutilizar la popup.

### 6. Features solo en primera apertura, luego `window.open(url, name)` sin features
La idea: primer click con features (popup), siguientes clicks sin features (navega ventana existente por nombre).
**Fallo**: Aunque Chrome reutiliza el nombre cuando no hay features, no mantiene las dimensiones de la ventana original ni el comportamiento de popup.

## Causa raíz
- **Cross-origin**: NextRIS (:3001) y Visor (:3000) son orígenes distintos (puertos diferentes). El acceso a propiedades de `Window` cross-origin está restringido.
- **Chrome popup behavior**: `window.open` con features siempre crea nueva ventana, ignorando el nombre.
- **Vite HMR**: Recarga módulos y resetea variables, rompiendo referencias en memoria.

## Conclusión
No es viable reutilizar la ventana del visor desde JavaScript usando `window.open` en este escenario (cross-origin + popups + HMR). Alternativas serían:
- Mover el visor al mismo origen que NextRIS (mismo puerto, mismo dominio)
- Usar un iframe dentro de la misma página en vez de `window.open`
- Comunicación vía `BroadcastChannel` o `postMessage` entre ventanas (requiere cooperación del visor)
