// --- static/audit_app.js (CORRECCIÓN CRÍTICA FINAL - TypeError: 'trim') ---

document.addEventListener('DOMContentLoaded', () => {
    // --- CORRECCIÓN CRÍTICA ---
    // Leer el MSN de forma segura desde el 'div' oculto
    const contextEl = document.getElementById('context-data');
    const MSN = contextEl.dataset.msn;
    
    const USER_ROLE = localStorage.getItem('userRole') || 'UNKNOWN';
    const USER_NAME = localStorage.getItem('userName') || 'N/A';
    
    // Encabezados de Trazabilidad (Obligatorios para todas las llamadas API)
    const API_HEADERS = {
        'Content-Type': 'application/json',
        'X-User-Role': USER_ROLE,
        'X-User-Name': USER_NAME
    };
    
    let currentRepairId = null; // ID del registro actualmente en el modal

    // Opciones de Dropdown (Solo las de Auditoría)
    const AUDIT_OPTIONS = {
        Audit_Physical_Status: ["Conforming", "Non-Conforming", "N/A"],
        Audit_OIL_Status: ["Open", "Closed", "N/A"]
    };

    // Mapeo para llenar el modal
    const MODAL_FIELD_MAP = [
        'Audit_Physical_Status', 'Audit_OIL_Status', 
        'Audit_Physical_Note', 'Audit_Documentation_Note', 
        'OIL_Closure_Note', 'Operator_Response_Note'
    ];
    
    // Función de inicialización
    const init = () => {
        // Llenar dropdowns del modal
        Object.keys(AUDIT_OPTIONS).forEach(key => {
            const select = document.getElementById(`Modal_${key}`);
            if (select) {
                AUDIT_OPTIONS[key].forEach(value => {
                    const option = document.createElement('option');
                    option.value = value;
                    option.textContent = value;
                    select.appendChild(option);
                });
            }
        });
        
        loadAuditData();

        // Control de permisos: Solo Auditor/Lessor puede usar el formulario
        if (!['Auditor', 'Lessor'].includes(USER_ROLE)) {
            document.getElementById('fetch-error').textContent = "ACCESS DENIED: Only Auditors or Lessors can manage OIL/Discrepancies.";
            document.getElementById('audit-table-container').innerHTML = '';
        }
    };

    // Carga de Datos de Auditoría
    const loadAuditData = async () => {
        const container = document.getElementById('audit-table-container');
        const summaryContainer = document.getElementById('summary-container');
        container.innerHTML = 'Loading audit data...';

        try {
            // Usa la URL correcta de la API (con MSN) y envía Headers
            const response = await fetch(`/api/repairs/${MSN}`, {
                method: 'GET',
                headers: API_HEADERS
            });
            
            if (!response.ok) {
                 throw new Error(`Failed to fetch repairs: ${response.status}`);
            }
            
            const allData = await response.json();
            
            updateSummary(allData); // Llama al resumen
            renderAuditTable(allData);
            
        } catch (error) {
            document.getElementById('fetch-error').textContent = `Error fetching data: ${error.message}.`;
            container.innerHTML = `<p style="color:red;">Could not load records.</p>`;
        }
    };

    const updateSummary = (data) => {
        // Cálculos IATA/Directivos (para el reporte OIL)
        const total = data.length;
        const oilOpen = data.filter(r => r.Audit_OIL_Status === 'Open').length;
        const oilClosed = data.filter(r => r.Audit_OIL_Status === 'Closed').length;
        const physNonConforming = data.filter(r => r.Audit_Physical_Status === 'Non-Conforming').length;
        const progressPercent = total > 0 ? (oilClosed / total) * 100 : 0;
        
        const container = document.getElementById('summary-container');
        container.innerHTML = `
            <div class="summary-item oil-total"><h3>TOTAL RECORDS</h3><strong>${total}</strong></div>
            <div class="summary-item oil-closed"><h3>OIL CLOSED</h3><strong>${oilClosed}</strong></div>
            <div class="summary-item oil-open"><h3>OIL OPEN</h3><strong>${oilOpen}</strong></div>
            <div class="summary-item oil-progress"><h3>% COMPLETE</h3><strong>${progressPercent.toFixed(1)}%</strong></div>
        `;
    };

    const renderAuditTable = (data) => {
        const container = document.getElementById('audit-table-container');
        if (data.length === 0) {
            container.innerHTML = '<p>No repair records found.</p>';
            return;
        }

        const AUDIT_COLUMNS = ['Repair_ID', 'ATA_Chapter', 'Repair_Status', 'Audit_Physical_Status', 'Audit_OIL_Status', 'Audit_Physical_Note', 'OIL_Closure_Note'];
        const AUDIT_HEADINGS = {
            'Repair_ID': 'ID', 'ATA_Chapter': 'ATA', 'Repair_Status': 'Status', 
            'Audit_Physical_Status': 'Phys Audit', 'Audit_OIL_Status': 'OIL Status', 
            'Audit_Physical_Note': 'Physical Discrepancy', 'OIL_Closure_Note': 'Final Sign-off'
        };

        let tableHTML = '<table><thead><tr>';
        AUDIT_COLUMNS.forEach(col => {
            tableHTML += `<th>${AUDIT_HEADINGS[col] || col}</th>`;
        });
        tableHTML += '</tr></thead><tbody>';

        data.forEach(record => {
            // Doble clic para abrir el modal de carga rápida
            tableHTML += `<tr ondblclick="openDiscrepancyModal('${record.Repair_ID}')">`;
            AUDIT_COLUMNS.forEach(col => {
                const value = record[col] || '';
                tableHTML += `<td>${value}</td>`;
            });
            tableHTML += '</tr>';
        });
        
        tableHTML += '</tbody></table>';
        container.innerHTML = tableHTML;
    };

    // --- Lógica del Modal ---

    window.openDiscrepancyModal = async (repairId) => {
        if (!['Auditor', 'Lessor'].includes(USER_ROLE)) {
            alert("Permission Denied: Quick Sign-off is restricted to Auditor/Lessor roles.");
            return;
        }

        currentRepairId = repairId;
        document.getElementById('modal-repair-id').textContent = repairId;
        document.getElementById('discrepancyModal').style.display = 'block';
        document.getElementById('discrepancy-file-status').textContent = 'No file attached yet.';
        
        // Cargar datos existentes en el modal (con Headers)
        const response = await fetch(`/api/repairs/${MSN}/${repairId}`, {
             method: 'GET',
             headers: API_HEADERS
        });
        const data = await response.json();

        MODAL_FIELD_MAP.forEach(field => {
            const element = document.getElementById(`Modal_${field}`);
            if (element) {
                element.value = data[field] || '';
            }
        });
    };

    window.closeModal = () => {
        document.getElementById('discrepancyModal').style.display = 'none';
        currentRepairId = null;
    };

    // --- Lógica de Subida de Archivos de Discrepancia ---
    window.uploadDiscrepancyFile = async (fileInput) => {
        const file = fileInput.files[0];
        if (!file || !currentRepairId) return;
        
        // Campo para subir la foto de la discrepancia (Doc_Photo_Pre)
        const docField = 'Doc_Photo_Pre'; 
        const statusEl = document.getElementById('discrepancy-file-status');
        
        const formData = new FormData();
        formData.append('file', file);
        
        statusEl.textContent = `Uploading ${file.name}...`;
        statusEl.style.color = 'orange';

        try {
            const response = await fetch(`/api/documents/upload/${MSN}/${currentRepairId}/${docField}`, {
                method: 'POST',
                body: formData,
                headers: { // Los headers de Trazabilidad se envían aquí
                     'X-User-Role': USER_ROLE,
                     'X-User-Name': USER_NAME
                 }
            });
            
            const result = await response.json();

            if (result.success) {
                statusEl.style.color = 'green';
                statusEl.textContent = `Success! File stored as: ${result.stored_filename} (Open record to view).`;
            } else {
                statusEl.style.color = 'red';
                statusEl.textContent = `Upload Error: ${result.message}`;
            }
        } catch (error) {
            statusEl.style.color = 'red';
            statusEl.textContent = `Network Error during upload.`;
        }
    };


    // --- Lógica de Guardado del Formulario Rápido (PUT) ---
    document.getElementById('quickDiscrepancyForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const form = e.target;
        const updateData = {};
        
        MODAL_FIELD_MAP.forEach(field => {
            const element = document.getElementById(`Modal_${field}`);
            if (element) {
                updateData[field] = element.value.trim();
            }
        });

        const statusMessage = document.getElementById('modal-status-message');
        
        try {
            statusMessage.textContent = 'Saving changes...';
            
            // CORRECCIÓN: Usar la URL correcta de la API (con MSN) y enviar Headers
            const response = await fetch(`/api/repairs/update/${MSN}/${currentRepairId}`, {
                method: 'PUT',
                headers: API_HEADERS, // Envía el contexto completo
                body: JSON.stringify(updateData)
            });
            
            const result = await response.json();
            
            if (response.ok) {
                statusMessage.textContent = `Successfully updated record ${currentRepairId}!`;
                statusMessage.style.color = 'green';
                
                // Recargar los datos de la tabla y resumen en el fondo
                setTimeout(() => {
                    closeModal();
                    loadAuditData(); 
                }, 1000); 
                
            } else {
                statusMessage.textContent = `Save Failed (Error ${response.status}): ${result.message}`;
                statusMessage.style.color = 'red';
            }

        } catch (error) {
            statusMessage.textContent = `Network Error: ${error.message}`;
            statusMessage.style.color = 'red';
        }
    });

    init();
});