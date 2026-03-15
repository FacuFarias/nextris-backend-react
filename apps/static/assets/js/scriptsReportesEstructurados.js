document.addEventListener('DOMContentLoaded', function () {
  const facilitySelect = document.getElementById('sr-facility');
  const fileInput = document.getElementById('sr-file');
  const form = document.getElementById('sr-create-parser-form');
  const statusContainer = document.getElementById('sr-status');
  const resultContainer = document.getElementById('sr-result');
  const clearButton = document.getElementById('sr-clear');
  const submitButton = document.getElementById('sr-submit');
  const criteriaParserSelect = document.getElementById('criteria-parser');
  const criteriaRefreshButton = document.getElementById('criteria-refresh');
  const criteriaStatusContainer = document.getElementById('criteria-status');
  const criteriaTableBody = document.getElementById('criteria-table-body');

  function showStatus(type, message) {
    statusContainer.innerHTML = `<div class="alert alert-${type} mb-2">${message}</div>`;
  }

  function showCriteriaStatus(type, message) {
    if (!criteriaStatusContainer) {
      return;
    }
    criteriaStatusContainer.innerHTML = `<div class="alert alert-${type} mb-2">${message}</div>`;
  }

  function clearCriteriaStatus() {
    if (!criteriaStatusContainer) {
      return;
    }
    criteriaStatusContainer.innerHTML = '';
  }

  function showResult(data) {
    resultContainer.style.display = 'block';
    resultContainer.textContent = JSON.stringify(data, null, 2);
  }

  function clearResult() {
    statusContainer.innerHTML = '';
    resultContainer.style.display = 'none';
    resultContainer.textContent = '';
  }

  function renderCriteriaEmpty(message) {
    if (!criteriaTableBody) {
      return;
    }
    criteriaTableBody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center text-muted py-3">${message}</td>
      </tr>
    `;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatRule(ruleDefinition) {
    if (!ruleDefinition || typeof ruleDefinition !== 'object') {
      return '-';
    }

    const all = Array.isArray(ruleDefinition.all) ? ruleDefinition.all : null;
    const cond = all && all.length > 0 ? all[0] : null;
    if (!cond || typeof cond !== 'object') {
      return JSON.stringify(ruleDefinition);
    }

    const variable = String(cond.variable || '-');
    const operator = String(cond.operator || '-');
    const value = cond.value !== undefined && cond.value !== null ? String(cond.value) : '-';
    const valueTo = cond.value_to !== undefined && cond.value_to !== null ? String(cond.value_to) : '';

    if (operator.toLowerCase() === 'between') {
      return `${variable} between ${value} y ${valueTo || '-'}`;
    }

    return `${variable} ${operator} ${value}`;
  }

  function renderCriteriaRows(criteria) {
    if (!criteriaTableBody) {
      return;
    }

    if (!Array.isArray(criteria) || criteria.length === 0) {
      renderCriteriaEmpty('No hay criterios creados para este parser.');
      return;
    }

    criteriaTableBody.innerHTML = criteria
      .map((item) => {
        const active = Boolean(item.active);
        const activeBadge = active
          ? '<span class="badge bg-success">Si</span>'
          : '<span class="badge bg-secondary">No</span>';

        const safeCriterionName = escapeHtml(String(item.criterion_name || '-'));
        const safeOutputText = escapeHtml(String(item.output_text || '-'));
        const safeRule = escapeHtml(formatRule(item.rule_definition));

        return `
          <tr>
            <td>${safeCriterionName}</td>
            <td><code>${safeRule}</code></td>
            <td>${safeOutputText}</td>
            <td class="text-end">${Number(item.priority || 100)}</td>
            <td class="text-center">${activeBadge}</td>
          </tr>
        `;
      })
      .join('');
  }

  async function loadCriteriaParsers() {
    if (!criteriaParserSelect) {
      return;
    }

    try {
      const response = await fetch('/api/structured-reports/parsers');
      const payload = await response.json();

      if (!response.ok || !payload.success) {
        throw new Error(payload.error || 'No se pudieron obtener parser');
      }

      criteriaParserSelect.innerHTML = '<option value="">Seleccione un parser...</option>';
      const parserList = Array.isArray(payload.data) ? payload.data : [];
      parserList.forEach((item) => {
        const option = document.createElement('option');
        option.value = item.id;
        option.textContent = item.parser_version
          ? `${item.parser_name} (${item.parser_version})`
          : item.parser_name;
        criteriaParserSelect.appendChild(option);
      });
    } catch (error) {
      showCriteriaStatus('danger', error.message || 'Error cargando parser');
    }
  }

  async function loadCriteriaForSelectedParser() {
    if (!criteriaParserSelect) {
      return;
    }

    const parserManifestId = criteriaParserSelect.value;
    if (!parserManifestId) {
      clearCriteriaStatus();
      renderCriteriaEmpty('Seleccione un parser para ver criterios.');
      return;
    }

    clearCriteriaStatus();
    renderCriteriaEmpty('Cargando criterios...');

    try {
      const response = await fetch(`/api/structured-reports/criteria?parser_manifest_id=${encodeURIComponent(parserManifestId)}&include_inactive=true`);
      const payload = await response.json();

      if (!response.ok || !payload.success) {
        throw new Error(payload.error || 'No se pudieron cargar criterios');
      }

      const criteria = Array.isArray(payload.data) ? payload.data : [];
      renderCriteriaRows(criteria);
    } catch (error) {
      renderCriteriaEmpty('No se pudieron cargar los criterios.');
      showCriteriaStatus('danger', error.message || 'Error cargando criterios');
    }
  }

  async function loadFacilities() {
    try {
      const response = await fetch('/api/structured-reports/facilities');
      const payload = await response.json();

      if (!response.ok || !payload.success) {
        throw new Error(payload.error || 'No se pudieron obtener facilities');
      }

      facilitySelect.innerHTML = '<option value="">Seleccione una facility...</option>';
      payload.data.forEach((facility) => {
        const option = document.createElement('option');
        option.value = facility.guid;
        option.textContent = facility.code ? `${facility.name} (${facility.code})` : facility.name;
        facilitySelect.appendChild(option);
      });
    } catch (error) {
      showStatus('danger', error.message || 'Error cargando facilities');
    }
  }

  function activateTabByHash() {
    const hash = window.location.hash;
    const tabMap = {
      '#crear-nuevo-parser': 'tab-crear-parser',
      '#mapeo-de-variables': 'tab-mapeo',
      '#conceptos-y-criterios': 'tab-conceptos',
      '#plantillas-inteligentes': 'tab-plantillas'
    };

    const tabId = tabMap[hash];
    if (!tabId) return;

    const tabButton = document.getElementById(tabId);
    if (!tabButton) return;

    const tab = new bootstrap.Tab(tabButton);
    tab.show();
  }

  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    clearResult();

    const facilityGuid = facilitySelect.value;
    const file = fileInput.files[0];

    if (!facilityGuid) {
      showStatus('warning', 'Debe seleccionar una facility.');
      return;
    }

    if (!file) {
      showStatus('warning', 'Debe seleccionar un archivo DICOM SR.');
      return;
    }

    const formData = new FormData();
    formData.append('facility_guid', facilityGuid);
    formData.append('file', file);

    submitButton.disabled = true;
    submitButton.textContent = 'Procesando...';

    try {
      const response = await fetch('/api/structured-reports/create-parser', {
        method: 'POST',
        body: formData
      });

      const payload = await response.json();

      if (!response.ok || !payload.success) {
        throw new Error(payload.error || 'No se pudo procesar el DICOM SR');
      }

      showStatus('success', payload.message || 'Proceso completado.');
      showResult(payload.data);
    } catch (error) {
      showStatus('danger', error.message || 'Error procesando DICOM SR.');
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = 'Procesar y crear parser';
    }
  });

  clearButton.addEventListener('click', function () {
    form.reset();
    clearResult();
  });

  if (criteriaRefreshButton) {
    criteriaRefreshButton.addEventListener('click', function () {
      loadCriteriaForSelectedParser();
    });
  }

  if (criteriaParserSelect) {
    criteriaParserSelect.addEventListener('change', function () {
      loadCriteriaForSelectedParser();
    });
  }

  loadFacilities();
  loadCriteriaParsers();
  activateTabByHash();
  window.addEventListener('hashchange', activateTabByHash);
});
