/**
 * Loader Component - Funciones JavaScript Reutilizables
 * 
 * Uso:
 * 1. Incluir este script en tu página
 * 2. Llamar showLoader() para mostrar el loader
 * 3. Llamar hideLoader() para ocultarlo
 * 
 * Funciones disponibles:
 * - showLoader(loaderId, text) - Muestra el loader
 * - hideLoader(loaderId) - Oculta el loader
 * - updateLoaderText(loaderId, text) - Actualiza el texto del loader
 */

/**
 * Muestra el loader
 * @param {string} loaderId - ID del loader (default: "loader-overlay")
 * @param {string} text - Texto opcional para actualizar
 */
function showLoader(loaderId, text) {
  const loader = document.getElementById(loaderId || 'loader-overlay');
  if (loader) {
    if (text) {
      const textElement = loader.querySelector('.loader-text');
      if (textElement) textElement.textContent = text;
    }
    loader.classList.add('active');
  }
}

/**
 * Oculta el loader
 * @param {string} loaderId - ID del loader (default: "loader-overlay")
 */
function hideLoader(loaderId) {
  const loader = document.getElementById(loaderId || 'loader-overlay');
  if (loader) {
    loader.classList.remove('active');
  }
}

/**
 * Actualiza el texto del loader sin ocultarlo
 * @param {string} loaderId - ID del loader (default: "loader-overlay")
 * @param {string} text - Nuevo texto a mostrar
 */
function updateLoaderText(loaderId, text) {
  const loader = document.getElementById(loaderId || 'loader-overlay');
  if (loader && text) {
    const textElement = loader.querySelector('.loader-text');
    if (textElement) textElement.textContent = text;
  }
}

/**
 * Muestra el loader con progreso
 * @param {string} loaderId - ID del loader
 * @param {string} baseText - Texto base
 * @param {number} current - Valor actual
 * @param {number} total - Valor total
 */
function showLoaderWithProgress(loaderId, baseText, current, total) {
  const percentage = Math.round((current / total) * 100);
  updateLoaderText(loaderId, `${baseText} ${percentage}%`);
}

/**
 * Muestra el loader por un tiempo específico
 * @param {string} loaderId - ID del loader
 * @param {number} duration - Duración en milisegundos
 * @param {string} text - Texto opcional
 */
function showLoaderFor(loaderId, duration, text) {
  showLoader(loaderId, text);
  setTimeout(() => hideLoader(loaderId), duration);
}

// Alias para compatibilidad con código existente
window.showLoader = showLoader;
window.hideLoader = hideLoader;
window.updateLoaderText = updateLoaderText;
window.showLoaderWithProgress = showLoaderWithProgress;
window.showLoaderFor = showLoaderFor;
