// --- static/repair_form.js (CORRECCIÓN CRÍTICA FINAL - Endpoint) ---

document.addEventListener('DOMContentLoaded', () => {
    // 1. Obtener contexto de la URL (MSN y Repair ID)
    const pathSegments = window.location.pathname.split('/');
    const MSN = pathSegments[2];
    const REPAIR_ID_FROM_URL = pathSegments[3]; // Usamos la URL para saber si es nuevo
    
    const USER_ROLE = localStorage.getItem('userRole') || 'UNKNOWN'; 
    const USER_NAME = localStorage.getItem('userName') || 'N/A';
    
    document.getElementById('page-title').textContent = `Edit/Add Record: ${REPAIR_ID_FROM_URL}`;

    const OPTIONS = {
        Record_Type: ["Damage Assessment Only", "Repair Embodied"],
        ATA_Chapter: ["ATA 51", "ATA 52", "ATA 53", "ATA 54", "ATA 55", "ATA 56", "ATA 57", "ATA 58", "ATA 59"],
        Position_Lateral: ["Left (LH)", "Right (RH)", "Center (CL)", "N/A"],
        Position_Vertical: ["Upper", "Lower", "Side", "N/A"],
        Aero_Performance_Effect: ["N/A", "Affects RVSM", "Affects RNAV", "Affects Performance", "Weight/Balance Change"],
        NDT_Required_Performed: ["N/A", "Yes, Complied", "Yes, Not Complied", "No, Not Required"],
        Repair_Status: ["Permanent", "Interim", "Time-Limited", "Repetitive", "Allowable Damage (Cat A)", "Allowable Damage (Cat B)"],
        Classification: ["Major", "Minor"],
        Approval_Basis: ["SRM", "EASA DOA", "FAA DER 8110-3", "FAA AR 8100-9", "TC Holder", "STC Holder"],
        Audit_Physical_Status: ["Conforming", "Non-Conforming", "N/A"],
        Audit_OIL_Status: ["Open", "Closed", "N/A"]
    };
    
    const DOCUMENT_FIELDS = [
        'Doc_CRS_Path', 'Doc_Approval_Path', 'Doc_NDT_Report_Path', 
        'Doc_Material_Cert_Path', 'Doc_Work_Order_Path', 'Doc_Correspondence_Path', 
        'Doc_Photo_Pre', 'Doc_Photo_Post', 'Doc_Drawing_Pre', 'Doc_Drawing_Post'
    ];
    
    const statusMessage = document.getElementById('status-message');
    const repairForm = document.getElementById('repairForm');
    const repairIdInput = document.getElementById('Repair_ID'); 

    // --- Lógica de Pestañas y Elementos ---
    
    const populateDropdown = (id, values) => {
        const select = document.getElementById(id);
        if (select) {
            select.innerHTML = values.map(v => `<option value="${v}">${v}</option>`).join('');
        }
    };
    
    const populateAllDropdowns = () => {
        Object.keys(OPTIONS).forEach(key => {
            populateDropdown(key, OPTIONS[key]);
        });
    };
    
    const handleConditionalFields = () => {
        const statusSelect = document.getElementById('Repair_Status');
        const thresholdInput = document.getElementById('Threshold_Limit');
        const repeatInput = document.getElementById('Repeat_Interval');
        
        if (!statusSelect || !thresholdInput || !repeatInput) return;

        const status = statusSelect.value;
        const isConditional = ["Time-Limited", "Repetitive", "Interim", "Allowable Damage (Cat B)"].includes(status);
        
        thresholdInput.disabled = !isConditional;
        repeatInput.disabled = !isConditional;
    };

    const handleAuditFieldPermissions = () => {
        const auditSection = document.getElementById('audit-fields-section');
        if (auditSection) {
            const isAuditorOrLessor = ['Auditor', 'Lessor'].includes(USER_ROLE);
            
            const elements = auditSection.querySelectorAll('input, select, textarea');
            elements.forEach(el => {
                el.disabled = !isAuditorOrLessor;
                if (!isAuditorOrLessor) {
                    el.style.backgroundColor = '#f7f7f7';
                } else {
                    el.style.backgroundColor = '#fff';
                }
            });
        }
    };

    /** Carga los datos existentes y rellena el formulario */
    const loadRepairData = async () => {
        const isNewRecord = REPAIR_ID_FROM_URL.toLowerCase() === 'new';

        if (isNewRecord) {
            repairIdInput.value = 'NEW-REC-';
            repairIdInput.removeAttribute('readonly'); // Habilitar edición para nuevo registro
            repairIdInput.style.backgroundColor = '#fff'; 
            handleConditionalFields();
            handleAuditFieldPermissions();
            generateDocumentFields({});
            document.getElementById('audit-trail-container').innerHTML = '<p>No history for new records.</p>';
            return;
        }

        try {
            // CORRECCIÓN: Usar la URL correcta de la API (con MSN)
            const response = await fetch(`/api/repairs/${MSN}/${REPAIR_ID_FROM_URL}`);
            if (response.status === 404) {
                statusMessage.textContent = `Error: Repair ID ${REPAIR_ID_FROM_URL} not found. Please check the URL.`;
                statusMessage.style.display = 'block';
                return;
            }
            const data = await response.json();
            
            Object.keys(data).forEach(key => {
                const element = document.getElementById(key);
                if (element) {
                    const value = data[key] || '';
                    if (element.tagName === 'SELECT' || element.tagName === 'TEXTAREA' || element.tagName === 'INPUT') {
                         element.value = value;
                    }
                }
            });
            
            repairIdInput.setAttribute('readonly', true); 
            repairIdInput.style.backgroundColor = '#eee';

            handleConditionalFields();
            handleAuditFieldPermissions();
            generateDocumentFields(data);
            loadAuditTrail();

        } catch (error) {
            console.error('Failed to load repair data:', error);
            statusMessage.textContent = `An error occurred while loading repair data: ${error.message}`;
            statusMessage.style.display = 'block';
        }
    };

    // --- (Inicio de Funciones Auxiliares - Sin Duplicados) ---

    const generateDocumentFields = (recordData) => {
        const container = document.getElementById('document-fields-container');
        if (!container) return;
        
        container.innerHTML = DOCUMENT_FIELDS.map(field => {
            const existingFilename = recordData[field] || 'No file stored.';
            const fieldLabel = field.replace(/_/g, ' '); 
            
            return `
                <div class="form-row">
                    <div class="form-group full-width">
                        <label>${fieldLabel}:</label>
                        <p><strong>Stored File:</strong> <span id="filename-${field}">${existingFilename}</span> 
                        ${existingFilename !== 'No file stored.' ? 
                            `<a href="/api/documents/download/${MSN}/${existingFilename}" target="_blank" style="margin-left: 10px;">(Download)</a>` : ''}
                        </p>
                        <input type="file" id="file-${field}" name="file-${field}" 
                               data-doc-field="${field}" onchange="window.uploadFile(this, '${field}')">
                        <progress id="progress-${field}" value="0" max="100" style="display:none; margin-top: 5px;"></progress>
                    </div>
                </div>
            `;
        }).join('');
    };
    
    const loadAuditTrail = async () => {
        const container = document.getElementById('audit-trail-container');
        if (!container || REPAIR_ID_FROM_URL.toLowerCase() === 'new') return;
        
        try {
            // CORRECCIÓN: Usar la URL correcta de la API (con MSN)
            const response = await fetch(`/api/audit_trail/${MSN}/${REPAIR_ID_FROM_URL}`);
            const logs = await response.json();
            
            if (logs.length === 0) {
                container.innerHTML = '<p>No history for this record.</p>';
                return;
            }
            
            let html = '<table><thead><tr><th>Date/Time</th><th>User</th><th>Operation</th><th>Changes Summary</th></tr></thead><tbody>';
            
            logs.reverse().forEach(log => {
                const changes = Object.keys(log.changes).map(key => `${key}: ${log.changes[key]}`).join('; ');
                html += `
                    <tr>
                        <td>${new Date(log.timestamp).toLocaleString()}</td>
                        <td>${log.user_name} (${log.user_role})</td>
                        <td>${log.operation}</td>
                        <td title="${changes}">${changes.substring(0, 80)}...</td>
                    </tr>
                `;
            });
            html += '</tbody></table>';
            container.innerHTML = html;
        } catch (error) {
            container.innerHTML = `<p style="color:red;">Error loading audit trail: ${error.message}</p>`;
        }
    };
    
    window.uploadFile = async (fileInput, docField) => {
        const file = fileInput.files[0];
        if (!file) return;

        const currentId = repairIdInput.value.trim(); 
        
        if (!currentId || currentId.startsWith('NEW-REC-')) {
             alert("Error: Save the record first to get a permanent ID before uploading documents.");
             fileInput.value = ''; 
             return;
        }

        const formData = new FormData();
        formData.append('file', file);
        
        const progressBar = document.getElementById(`progress-${docField}`);
        progressBar.style.display = 'block';
        
        statusMessage.textContent = `Uploading ${file.name}...`;
        statusMessage.className = 'error-message';
        statusMessage.style.display = 'block';

        try {
            const response = await fetch(`/api/documents/upload/${MSN}/${currentId}/${docField}`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-User-Role': USER_ROLE,
                    'X-User-Name': USER_NAME
                }
            });
            
            const result = await response.json();
            progressBar.style.display = 'none';

            if (result.success) {
                statusMessage.textContent = `Success! File stored as: ${result.stored_filename}.`;
                statusMessage.className = 'error-message green';
                
                const filenameSpan = document.getElementById(`filename-${docField}`);
                filenameSpan.textContent = result.stored_filename;
                
                loadAuditTrail(); 
            } else {
                statusMessage.textContent = `Upload Error: ${result.message}`;
                statusMessage.className = 'error-message red';
            }

        } catch (error) {
            progressBar.style.display = 'none';
            statusMessage.textContent = `Network Error during upload: ${error.message}`;
            statusMessage.className = 'error-message red';
        }
    };

    // --- (Fin de Funciones Auxiliares) ---


    // --- Lógica de Guardado del Formulario (POST/PUT) ---
    repairForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const currentId = repairIdInput.value.trim();
        
        // 1. Recolectar datos
        const formData = new FormData(e.target);
        const data = {};
        formData.forEach((value, key) => {
            // VERIFICAR SI ES STRING antes de llamar a .replace()
            if (typeof value === 'string') {
                data[key] = value.replace(',', '.').trim(); 
            }
            // Si es un objeto File (de la Pestaña 4), se ignora aquí.
        });
        
        // CRÍTICO: Validar que el ID no sea temporal
        if (!currentId || currentId.startsWith('NEW-REC-')) {
            statusMessage.textContent = "Error: Provide a valid Repair ID (remove 'NEW-REC-').";
            statusMessage.className = 'error-message red';
            statusMessage.style.display = 'block';
            return;
        }
        
        // 2. Determinar Endpoint (Usando la URL original para decidir POST vs PUT)
        const isNewRecord = REPAIR_ID_FROM_URL.toLowerCase() === 'new';
        const method = isNewRecord ? 'POST' : 'PUT';
        
        // --- CORRECCIÓN CRÍTICA DE LA URL (Añadir MSN) ---
        const endpoint = isNewRecord ? `/api/repairs/add/${MSN}` : `/api/repairs/update/${MSN}/${currentId}`;
        
        try {
            statusMessage.textContent = 'Saving changes...';
            statusMessage.className = 'error-message';
            statusMessage.style.display = 'block';
            
            const response = await fetch(endpoint, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-User-Role': USER_ROLE,
                    'X-User-Name': USER_NAME 
                },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (response.ok) {
                statusMessage.textContent = `Successfully saved record ${currentId}!`;
                statusMessage.className = 'error-message green';
                
                // Si fue una nueva adición, forzar la navegación a la URL de edición permanente
                if (isNewRecord) {
                     alert(`Record ${currentId} created. Navigating to the permanent Edit Page.`);
                     window.location.href = `/edit/${MSN}/${currentId}`;
                } else {
                    loadAuditTrail(); // Recargar el historial
                }
            } else {
                statusMessage.textContent = `Save Failed (Error ${response.status}): ${result.message}`;
                statusMessage.className = 'error-message red';
            }

        } catch (error) {
            statusMessage.textContent = `Network Error: ${error.message}`;
            statusMessage.className = 'error-message red';
        }
    });

    // Asignar listeners y cargar datos
    document.getElementById('Repair_Status').addEventListener('change', handleConditionalFields);
    populateAllDropdowns();
    loadRepairData();
});