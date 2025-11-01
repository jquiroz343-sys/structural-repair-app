import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import data_manager
import pandas as pd
import os
import re # Importar regex para validación

# --- DROPDOWN OPTIONS (Final IATA Standards) ---
OPTIONS_RECORD_TYPE = ["Damage Assessment Only", "Repair Embodied"]
OPTIONS_CLASSIFICATION = ["Major", "Minor"]
OPTIONS_APPROVAL_BASIS = ["SRM", "EASA DOA", "FAA DER 8110-3", "FAA AR 8100-9", "TC Holder", "STC Holder"]
OPTIONS_REPAIR_STATUS = ["Permanent", "Interim", "Time-Limited", "Repetitive", "Allowable Damage (Cat A)", "Allowable Damage (Cat B)"] # <-- INCLUDES ALLOWABLE DAMAGE
OPTIONS_AERO_PERFORMANCE = ["N/A", "Affects RVSM", "Affects RNAV", "Affects Performance", "Weight/Balance Change"]
OPTIONS_POSITION_LATERAL = ["Left (LH)", "Right (RH)", "Center (CL)"]
OPTIONS_POSITION_VERTICAL = ["Upper", "Lower", "Side", "N/A"]
OPTIONS_ATA_CHAPTER = [f"ATA {i}" for i in range(51, 60)] # ATA 51 to 57 are structural
OPTIONS_NDT = ["N/A", "Yes, Complied", "Yes, Not Complied", "No, Not Required"]

# Global variables for the current session
class Session:
    """Manages the current project and user role."""
    current_msn = None
    current_role = None 
    # New global to hold the ID of the record being edited
    current_edit_repair_id = None 

# --- Shared Components ---

class BasePage(tk.Frame):
    def __init__(self, parent, controller, title):
        super().__init__(parent)
        self.controller = controller
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        title_label = ttk.Label(self, text=title, font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=10, padx=10, sticky="nw")
        
        status_text = f"Role: {Session.current_role or 'N/A'} | MSN: {Session.current_msn or 'N/A'}"
        status_label = ttk.Label(self, text=status_text, font=("Arial", 10))
        status_label.grid(row=0, column=2, pady=10, padx=10, sticky="ne")

        logout_button = ttk.Button(self, text="Log Out / Change Role", 
                                 command=lambda: self.reset_session())
        logout_button.grid(row=0, column=3, pady=10, padx=10, sticky="ne")

    def reset_session(self):
        Session.current_msn = None
        Session.current_role = None
        # Clear the ID when logging out
        Session.current_edit_repair_id = None 
        self.controller.show_frame(RoleSelectionPage)

# --- Functional Pages: ADD, EDIT, VIEW ---

class BaseRepairForm(BasePage):
    """
    Base class for AddRepairPage and EditRepairPage to reduce code duplication
    and ensure consistency of the 47 field structure.
    """
    def __init__(self, parent, controller, title, is_edit_mode=False):
        super().__init__(parent, controller, title)
        
        self.fields = data_manager.COLUMNS
        self.entries = {}
        self.file_vars = {} 
        self.attached_files = {} 
        self.is_edit_mode = is_edit_mode
        
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, columnspan=4, pady=10, padx=20, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)
        
        self.tab1 = self.create_tab("1. ID & LOCATION")
        self.tab2 = self.create_tab("2. DIMENSIONS & LIMITS")
        self.tab3 = self.create_tab("3. CERTIFICATION & AUDIT") # Renamed tab 3 to include AUDIT focus
        self.tab4 = self.create_tab("4. DOCUMENTATION")
        
        self.notebook.add(self.tab1, text='1. ID & LOCATION')
        self.notebook.add(self.tab2, text='2. DIMENSIONS & LIMITS')
        self.notebook.add(self.tab3, text='3. CERTIFICATION & AUDIT')
        self.notebook.add(self.tab4, text='4. DOCUMENTATION')
        
        self.populate_tabs()
        
        button_text = "Save Updated Repair Record" if is_edit_mode else "Save Complete Repair Record"
        submit_button = ttk.Button(self, text=button_text, command=self.save_record)
        submit_button.grid(row=2, column=0, columnspan=4, pady=10)

        # In edit mode, we may want a back button
        if is_edit_mode:
             ttk.Button(self, text="Cancel / Back to View", command=lambda: controller.show_frame(ViewRepairsPage)).grid(row=2, column=1, columnspan=2, pady=10)


    def create_tab(self, name):
        frame = ttk.Frame(self.notebook, padding="10 10 10 10")
        frame.columnconfigure(1, weight=1)
        return frame

    def populate_tabs(self):
        # Calls the original population methods
        self._populate_tab_1()
        self._populate_tab_2()
        self._populate_tab_3()
        self._populate_tab_4()
        self.update_conditional_fields() # Initial call

    def add_label_entry(self, frame, row, label_text, field_name, is_dropdown=False, options=None, is_multiline=False):
        label = ttk.Label(frame, text=label_text + ":", width=25)
        label.grid(row=row, column=0, padx=5, pady=5, sticky="w")
        
        if is_dropdown:
            entry = ttk.Combobox(frame, values=options, state="readonly", width=47)
            entry.grid(row=row, column=1, padx=5, pady=5, sticky="ew")
            
            if field_name == 'Repair_Status':
                entry.bind("<<ComboboxSelected>>", self.update_conditional_fields)
            elif options:
                # Set default value only in Add mode
                if not self.is_edit_mode:
                    entry.set(options[0])

        else:
            if is_multiline:
                entry = tk.Text(frame, height=3, width=50)
                entry.grid(row=row, column=1, padx=5, pady=5, sticky="ew")
            else:
                entry = ttk.Entry(frame, width=50)
                entry.grid(row=row, column=1, padx=5, pady=5, sticky="ew")

        self.entries[field_name] = entry
        return entry

    def add_file_attachment(self, frame, row, label_text, field_name):
        ttk.Label(frame, text=label_text + ":", width=25).grid(row=row, column=0, padx=5, pady=5, sticky="w")
        
        # In edit mode, the variable will hold the existing path
        var = tk.StringVar(self, value="No file attached.") 
        self.file_vars[field_name] = var
        
        ttk.Label(frame, textvariable=var, wraplength=350).grid(row=row, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Button(frame, text="Attach File", 
                   command=lambda f=field_name: self.select_single_file(f)).grid(row=row, column=2, padx=5, pady=5)
    
    def select_single_file(self, field_name):
        file_path = filedialog.askopenfilename(title=f"Select {field_name.replace('_', ' ')} Document")
        
        if file_path:
            # We store the *new* selected path here
            self.attached_files[field_name] = file_path 
            self.file_vars[field_name].set(os.path.basename(file_path))
        else:
            # If selection is cancelled, keep the old path if in edit mode
            if field_name not in self.attached_files and self.is_edit_mode:
                # Do nothing, keep the current value in self.file_vars[field_name]
                pass 
            else:
                # If we were adding a new one or overriding an old one, clear it
                self.attached_files.pop(field_name, None) 
                self.file_vars[field_name].set("No file attached.")


    def update_conditional_fields(self, event=None):
        status = self.entries['Repair_Status'].get()
        # Include Allowable Damage (Cat B) as time-limited requires attention, even if not a 'repair'
        is_conditional = (status in ["Time-Limited", "Repetitive", "Interim", "Allowable Damage (Cat B)"]) 
        
        state = 'normal' if is_conditional else 'disabled'
        
        # Handle conditional fields (Threshold and Interval)
        try:
            self.entries['Threshold_Limit'].config(state=state)
            self.entries['Repeat_Interval'].config(state=state)
            
            if not is_conditional and not self.is_edit_mode:
                # Only clear fields if not in edit mode (don't clear existing data)
                self.entries['Threshold_Limit'].delete(0, tk.END)
                self.entries['Repeat_Interval'].delete(0, tk.END)
        except Exception:
            pass 
        
        # Handle Audit/OIL fields (only visible in Edit mode and for Auditor)
        if self.is_edit_mode:
            self._update_audit_fields_state()
            

    def _update_audit_fields_state(self):
        """Disables/enables Audit fields based on user role."""
        if not hasattr(self, 'audit_entries'):
            return 
            
        state = 'normal' if Session.current_role in ['Auditor', 'Lessor'] else 'disabled'
        
        for widget in self.audit_entries.values():
            if isinstance(widget, tk.Text):
                # We need to configure text fields with 'normal' then 'disabled'
                widget.config(state='normal')
                if state == 'disabled':
                    widget.config(state='disabled')
            elif isinstance(widget, ttk.Combobox):
                widget.config(state='readonly' if state == 'normal' else 'disabled')
            else:
                widget.config(state=state)

    # --- TAB POPULATION METHODS (Omitted for brevity, assumed unchanged) ---
    # ... (Omitted _populate_tab_1, _populate_tab_2, _populate_tab_3, _populate_tab_4) ...
    # Placeholder for the population methods from the previous step
    def _populate_tab_1(self):
        row = 0
        ttk.Label(self.tab1, text="--- I. GENERAL IDENTIFICATION ---", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, pady=(10, 5), sticky="w")
        row += 1
        self.add_label_entry(self.tab1, row, "Repair ID", 'Repair_ID').config(state='readonly' if self.is_edit_mode else 'normal') 
        row += 1
        self.add_label_entry(self.tab1, row, "Record Type", 'Record_Type', is_dropdown=True, options=OPTIONS_RECORD_TYPE)
        row += 1
        
        self.add_label_entry(self.tab1, row, "Date Completed", 'Date_Completed')
        row += 1
        self.add_label_entry(self.tab1, row, "FH Completed", 'FH_Completed')
        row += 1
        self.add_label_entry(self.tab1, row, "FC Completed", 'FC_Completed')
        row += 1
        
        ttk.Label(self.tab1, text="--- II. DAMAGE LOCATION ---", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, pady=(10, 5), sticky="w")
        row += 1
        self.add_label_entry(self.tab1, row, "ATA Chapter", 'ATA_Chapter', is_dropdown=True, options=OPTIONS_ATA_CHAPTER)
        row += 1
        self.add_label_entry(self.tab1, row, "Position Lateral (LH/RH)", 'Position_Lateral', is_dropdown=True, options=OPTIONS_POSITION_LATERAL)
        row += 1
        self.add_label_entry(self.tab1, row, "Position Vertical (Up/Low)", 'Position_Vertical', is_dropdown=True, options=OPTIONS_POSITION_VERTICAL)
        row += 1
        self.add_label_entry(self.tab1, row, "Location Description (STA/Stringer)", 'Location_Desc', is_multiline=True)
        row += 1
        self.add_label_entry(self.tab1, row, "Adjacent Damage ID", 'Adjacent_Damage_ID')
        row += 1
        self.add_label_entry(self.tab1, row, "Component Details (S/N or P/N)", 'Component_Details')
        row += 1

    def _populate_tab_2(self):
        row = 0
        ttk.Label(self.tab2, text="--- III. DIMENSIONS & CONSEQUENCES ---", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, pady=(10, 5), sticky="w")
        row += 1
        
        self.add_label_entry(self.tab2, row, "Dim Length/Width (Pre-Repair)", 'Dim_Length_Width') 
        row += 1
        self.add_label_entry(self.tab2, row, "Dim Depth (Pre-Repair)", 'Dim_Depth')
        row += 1

        self.add_label_entry(self.tab2, row, "Dim Remaining Thickness (Final T)", 'Dim_Remaining_Thk')
        row += 1
        self.add_label_entry(self.tab2, row, "Dim Post-Repair Depth/Patch", 'Dim_Post_Repair_Depth')
        row += 1

        self.add_label_entry(self.tab2, row, "External Repair Area (sq. in)", 'Ext_Repair_Area_SqIn')
        row += 1
        self.add_label_entry(self.tab2, row, "Aero/Performance Effect", 'Aero_Performance_Effect', is_dropdown=True, options=OPTIONS_AERO_PERFORMANCE)
        row += 1
        self.add_label_entry(self.tab2, row, "Fatigue Life Data", 'Fatigue_Life_Data')
        row += 1
        self.add_label_entry(self.tab2, row, "NDT Required/Performed Status", 'NDT_Required_Performed', is_dropdown=True, options=OPTIONS_NDT)
        row += 1

        ttk.Label(self.tab2, text="--- IV. STATUS & LIMITATIONS ---", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, pady=(10, 5), sticky="w")
        row += 1
        
        self.add_label_entry(self.tab2, row, "Repair Status", 'Repair_Status', is_dropdown=True, options=OPTIONS_REPAIR_STATUS)
        row += 1
        
        self.add_label_entry(self.tab2, row, "Threshold Limit (FH/FC/CAL)", 'Threshold_Limit')
        row += 1
        self.add_label_entry(self.tab2, row, "Repeat Interval (FH/FC/CAL)", 'Repeat_Interval')
        row += 1
        
    def _populate_tab_3(self):
        row = 0
        ttk.Label(self.tab3, text="--- V. CERTIFICATION BASIS & ORGS ---", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, pady=(10, 5), sticky="w")
        row += 1
        self.add_label_entry(self.tab3, row, "Classification (Maj/Min)", 'Classification', is_dropdown=True, options=OPTIONS_CLASSIFICATION)
        row += 1
        self.add_label_entry(self.tab3, row, "Approval Basis", 'Approval_Basis', is_dropdown=True, options=OPTIONS_APPROVAL_BASIS)
        row += 1
        self.add_label_entry(self.tab3, row, "Evaluation SRM Reference", 'Evaluation_SRM_Ref') 
        row += 1
        self.add_label_entry(self.tab3, row, "Design Organization Ref", 'Design_Org_Ref')
        row += 1
        self.add_label_entry(self.tab3, row, "Repair MRO Ref", 'Repair_MRO_Ref')
        row += 1

        ttk.Label(self.tab3, text="--- VI. MATERIAL TRACEABILITY ---", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, pady=(10, 5), sticky="w")
        row += 1
        self.add_label_entry(self.tab3, row, "Material P/N", 'Material_PN')
        row += 1
        self.add_label_entry(self.tab3, row, "Material Trace Ref (Lot/Batch/S/N)", 'Material_Trace_Ref')
        row += 1
        self.add_label_entry(self.tab3, row, "Material Cert Ref (8130-3/CoC)", 'Material_Cert_Ref')
        row += 1

        ttk.Label(self.tab3, text="--- VII. CERTIFICATE REFERENCES ---", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, pady=(10, 5), sticky="w")
        row += 1
        self.add_label_entry(self.tab3, row, "CRS Reference", 'CRS_Ref')
        row += 1
        self.add_label_entry(self.tab3, row, "Logbook Reference", 'Logbook_Ref')
        row += 1
        self.add_label_entry(self.tab3, row, "Repair Notes (Internal)", 'Repair_Notes', is_multiline=True)
        row += 1
        
        if self.is_edit_mode:
            self.audit_entries = {}
            ttk.Label(self.tab3, text="--- G. AUDIT / OIL STATUS (Auditor/Lessor Only) ---", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, pady=(10, 5), sticky="w")
            row += 1
            
            audit_fields = [
                ('Audit Physical Status', 'Audit_Physical_Status', ['Conforming', 'Non-Conforming', 'N/A']),
                ('Audit OIL Status', 'Audit_OIL_Status', ['Open', 'Closed', 'N/A']),
                ('Physical Audit Note', 'Audit_Physical_Note', None),
                ('Documentation Audit Note', 'Audit_Documentation_Note', None),
                ('OIL Closure Note', 'OIL_Closure_Note', None),
                ('Operator Response Note', 'Operator_Response_Note', None)
            ]
            
            for label, field_name, options in audit_fields:
                if options:
                    entry = self.add_label_entry(self.tab3, row, label, field_name, is_dropdown=True, options=options)
                else:
                    entry = self.add_label_entry(self.tab3, row, label, field_name, is_multiline=True)
                self.audit_entries[field_name] = entry
                row += 1
            
            self._update_audit_fields_state()

    def _populate_tab_4(self):
        row = 0
        ttk.Label(self.tab4, text="--- VIII. MANDATORY DOCUMENTATION PATHS ---", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, pady=(10, 5), sticky="w")
        row += 1

        self.add_file_attachment(self.tab4, row, "CRS File", 'Doc_CRS_Path')
        row += 1
        self.add_file_attachment(self.tab4, row, "Approval Data File (8110-3/DOA)", 'Doc_Approval_Path')
        row += 1
        self.add_file_attachment(self.tab4, row, "NDT Inspection Report File", 'Doc_NDT_Report_Path')
        row += 1

        self.add_file_attachment(self.tab4, row, "Material Certification File (8130-3/CoC)", 'Doc_Material_Cert_Path')
        row += 1
        self.add_file_attachment(self.tab4, row, "Work Order / Engineering File", 'Doc_Work_Order_Path') 
        row += 1
        self.add_file_attachment(self.tab4, row, "Correspondence File (OEM/DOA)", 'Doc_Correspondence_Path') 
        row += 1
        
        self.add_file_attachment(self.tab4, row, "Photo: Pre-Repair (Damage)", 'Doc_Photo_Pre')
        row += 1
        self.add_file_attachment(self.tab4, row, "Photo: Post-Repair (Final Work)", 'Doc_Photo_Post')
        row += 1
        self.add_file_attachment(self.tab4, row, "Drawing: Pre-Repair (Evaluation)", 'Doc_Drawing_Pre')
        row += 1
        self.add_file_attachment(self.tab4, row, "Drawing: Post-Repair (Final Design)", 'Doc_Drawing_Post')
        row += 1
    # --- END TAB POPULATION METHODS ---

    # --- NEW VALIDATION FUNCTIONS ---
    def _validate_time_and_numeric(self, value, field_name):
        """Validates if a value is empty or contains only non-negative integers."""
        if not value:
            return True, None # Empty is acceptable for optional numeric fields
            
        # Regex: optional negative sign, at least one digit, optional comma/period + more digits
        # For simplicity in FH/FC, we enforce non-negative integer or float format.
        # Since FH/FC are typically hours/cycles (integers), we enforce integer structure.
        if field_name in ['FH_Completed', 'FC_Completed']:
            if not value.isdigit() or int(value) < 0:
                return False, f"'{field_name}' must be a non-negative integer (Full Cycles/Hours)."
        
        # Validation for dimensional fields that allow decimals (e.g., thickness, length)
        elif field_name in ['Dim_Length_Width', 'Dim_Depth', 'Dim_Remaining_Thk', 'Ext_Repair_Area_SqIn']:
            # Allows integers or decimals (with comma or period as separator)
            if not re.match(r'^\d+(\.\d+)?$', value) and not re.match(r'^\d+(,\d+)?$', value):
                 return False, f"'{field_name}' must be a positive number (integer or decimal)."

        return True, None

    def _validate_input(self, record_data):
        """Runs all critical IATA-required format validations."""
        
        # V1. Mandatory Field Check
        if not record_data.get('Repair_ID'):
            return False, "Validation Error: Repair ID is mandatory."
            
        # V2. ATA Format Check (Ensures it's selected from the dropdown, but double-checks the format)
        if not record_data.get('ATA_Chapter') or not record_data.get('ATA_Chapter').startswith('ATA '):
            return False, "Validation Error: ATA Chapter is mandatory and must be selected."
            
        # V3. Date Format Check (Enforces YYYY-MM-DD or is empty)
        date_val = record_data.get('Date_Completed', '')
        if date_val and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_val):
            return False, "Validation Error: Date Completed must be in YYYY-MM-DD format (or left empty)."

        # V4. Numeric/Time Field Check (FH, FC, Dimensions)
        numeric_fields = [
            'FH_Completed', 'FC_Completed', 
            'Dim_Length_Width', 'Dim_Depth', 'Dim_Remaining_Thk', 
            'Ext_Repair_Area_SqIn',
            # Threshold/Interval must be validated if status is conditional
            'Threshold_Limit', 'Repeat_Interval'
        ]

        status = record_data.get('Repair_Status')
        is_conditional = (status in ["Time-Limited", "Repetitive", "Interim", "Allowable Damage (Cat B)"])

        for field in numeric_fields:
            value = record_data.get(field, '').strip()
            
            # Check mandatory fields for conditional status
            if is_conditional and field in ['Threshold_Limit', 'Repeat_Interval'] and not value:
                return False, f"Validation Error: '{field}' is mandatory for the selected Repair Status ('{status}')."
            
            # Skip validation if field is empty and not mandatory
            if not value:
                 continue

            # Run strict format validation
            valid, error_msg = self._validate_time_and_numeric(value, field)
            if not valid:
                return False, f"Validation Error: {error_msg}"
                
        return True, None


    # --- Save Logic (Modified to include validation) ---
    
    def collect_data(self):
        record_data = {}
        # Collect data from all entries (41 + 6 fields)
        for field in data_manager.COLUMNS:
            widget = self.entries.get(field)
            if widget:
                if isinstance(widget, ttk.Combobox):
                    value = widget.get().strip()
                elif isinstance(widget, tk.Text):
                    # Text widgets return a string including the final newline
                    value = widget.get("1.0", tk.END).strip()
                else:
                    value = widget.get().strip()
                record_data[field] = value
            # If it's an Audit field not included in Add mode, default to empty string
            elif field not in record_data:
                record_data[field] = ''

        # Overwrite documentation paths with newly attached files
        for field in self.file_vars.keys():
            if field in self.attached_files:
                record_data[field] = self.attached_files[field]
            elif self.is_edit_mode:
                 # In edit mode, if a file wasn't replaced, use the value shown in the file_vars (which holds the original path)
                 record_data[field] = self.file_vars[field].get().replace("No file attached.", "").strip()

        return record_data

    def save_record(self):
        if not Session.current_msn:
            messagebox.showerror("Error", "No aircraft selected. Please select a project first.")
            return

        record_data = self.collect_data()
        repair_id = record_data.get('Repair_ID')
            
        # --- NEW STEP: Validation Check ---
        is_valid, validation_message = self._validate_input(record_data)
        if not is_valid:
            messagebox.showerror("Data Validation Failed", validation_message)
            return
        # --- END NEW STEP ---
            
        if self.is_edit_mode:
            success, message = data_manager.update_repair_record(Session.current_msn, repair_id, record_data)
        else:
            # Check for duplicate ID on Add mode is still handled by data_manager.add_repair_record
            success, message = data_manager.add_repair_record(Session.current_msn, record_data)
        
        if success:
            messagebox.showinfo("Success", message)
            if not self.is_edit_mode:
                self.reset_form()
            else:
                 # After saving an edit, go back to the view page
                 if self.controller.frames[AuditOilPage].winfo_ismapped():
                      self.controller.show_frame(AuditOilPage)
                 else:
                      self.controller.show_frame(ViewRepairsPage)
                 Session.current_edit_repair_id = None
        else:
            messagebox.showerror("Error", message)

    def reset_form(self):
        # ... (Reset logic remains the same) ...
        for field, widget in self.entries.items():
            if isinstance(widget, ttk.Combobox):
                if widget['values']:
                    widget.current(0)
            elif isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
            else:
                widget.delete(0, tk.END)
        
        self.attached_files = {}
        for var in self.file_vars.values():
            var.set("No file attached.")
        
        self.update_conditional_fields() 


class AddRepairPage(BaseRepairForm):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Add New Repair Record", is_edit_mode=False)
        self.reset_form() 

class EditRepairPage(BaseRepairForm):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Edit Repair Record (ID: N/A)", is_edit_mode=True)
        self.original_repair_id = None
        self.bind("<Visibility>", self.on_show)
        
    def on_show(self, event):
        # ... (on_show logic remains the same) ...
        repair_id = Session.current_edit_repair_id
        
        if not repair_id or not Session.current_msn:
            messagebox.showerror("Error", "No Repair ID or MSN selected for editing.")
            self.controller.show_frame(ViewRepairsPage) # Fallback to View page
            return

        self.original_repair_id = repair_id
        self.set_title(f"Edit Repair Record (ID: {repair_id})")
        
        self.load_and_populate_form(repair_id)

    def set_title(self, new_title):
        # ... (set_title logic remains the same) ...
        title_label = self.winfo_children()[0]
        if isinstance(title_label, ttk.Label):
            title_label.config(text=new_title)

    def load_and_populate_form(self, repair_id):
        # ... (load_and_populate_form logic remains the same) ...
        record_data = data_manager.get_repair_record_by_id(Session.current_msn, repair_id)

        if not record_data:
            messagebox.showerror("Error", f"Record ID {repair_id} not found.")
            self.controller.show_frame(ViewRepairsPage)
            return

        self.attached_files = {} 

        for field, value in record_data.items():
            widget = self.entries.get(field)
            if widget:
                
                if isinstance(widget, (ttk.Entry, ttk.Combobox)):
                    widget.delete(0, tk.END)
                elif isinstance(widget, tk.Text):
                    widget.delete("1.0", tk.END)
                
                value = str(value)
                if isinstance(widget, ttk.Combobox):
                    widget.set(value)
                elif isinstance(widget, tk.Text):
                    widget.insert("1.0", value)
                else:
                    widget.insert(0, value)
            
            if field in self.file_vars:
                if value:
                    self.file_vars[field].set(os.path.basename(value))
                else:
                    self.file_vars[field].set("No file attached.")
        
        self.update_conditional_fields()


# --- ViewRepairsPage (Omitted for brevity, assumed unchanged) ---
class ViewRepairsPage(BasePage):
    # Campos clave visibles para el operador (15 campos seleccionados)
    VISIBLE_COLUMNS = [
        'Repair_ID', 'Record_Type', 'ATA_Chapter', 'Location_Desc', 'Date_Completed', 
        'FH_Completed', 'FC_Completed', 'Repair_Status', 'Classification', 
        'Approval_Basis', 'Dim_Length_Width', 'Dim_Remaining_Thk', 
        'Threshold_Limit', 'Repeat_Interval', 'CRS_Ref'
    ]
    
    COLUMN_HEADINGS = {
        'Repair_ID': 'Repair ID', 'Record_Type': 'Type', 'ATA_Chapter': 'ATA',
        'Location_Desc': 'Location Desc.', 'Date_Completed': 'Date', 
        'FH_Completed': 'FH', 'FC_Completed': 'FC', 'Repair_Status': 'Status',
        'Classification': 'Class', 'Approval_Basis': 'Approval Basis', 
        'Dim_Length_Width': 'Dim (L/W)', 'Dim_Remaining_Thk': 'Rem. Thk', 
        'Threshold_Limit': 'Threshold', 'Repeat_Interval': 'Interval', 
        'CRS_Ref': 'CRS Ref'
    }

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "View All Structural Repair Records")
        
        self.search_var = tk.StringVar()
        self.search_column_var = tk.StringVar(value='Repair_ID')
        
        search_frame = ttk.LabelFrame(self, text="Search Filters")
        search_frame.grid(row=1, column=0, columnspan=4, pady=10, padx=20, sticky="ew")
        search_frame.columnconfigure(1, weight=1)

        ttk.Label(search_frame, text="Search Value:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(search_frame, text="Search By:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttk.Combobox(search_frame, textvariable=self.search_column_var, 
                     values=['Repair_ID', 'ATA_Chapter', 'Location_Desc'], 
                     state='readonly', width=15).grid(row=0, column=3, padx=5, pady=5, sticky="w")

        ttk.Button(search_frame, text="Search", command=self.apply_search).grid(row=0, column=4, padx=5, pady=5, sticky="e")
        ttk.Button(search_frame, text="Reset View", command=self.load_repairs).grid(row=0, column=5, padx=5, pady=5, sticky="e")
        
        table_frame = ttk.Frame(self)
        table_frame.grid(row=2, column=0, columnspan=4, pady=10, padx=20, sticky="nsew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        self.tree = ttk.Treeview(table_frame, columns=self.VISIBLE_COLUMNS, show='headings')
        
        for col in self.VISIBLE_COLUMNS:
            self.tree.heading(col, text=self.COLUMN_HEADINGS.get(col, col))
            if col in ['Repair_ID', 'CRS_Ref']:
                self.tree.column(col, width=100, anchor=tk.W)
            elif col in ['Location_Desc']:
                self.tree.column(col, width=200, anchor=tk.W)
            elif col in ['FH_Completed', 'FC_Completed', 'Dim_Remaining_Thk']:
                self.tree.column(col, width=50, anchor=tk.CENTER)
            else:
                self.tree.column(col, width=80, anchor=tk.W)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.bind('<Double-1>', self.open_edit_page)

        self.bind("<Visibility>", self.update_content) 

    def update_content(self, event):
        if Session.current_msn:
            self.load_repairs()
        else:
            self.clear_tree()
            messagebox.showinfo("Context Error", "Please select an aircraft project (MSN) first.")

    def clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def load_repairs(self, search_results=None):
        self.clear_tree()
        
        if not Session.current_msn:
            return

        df = search_results if search_results is not None else data_manager.get_all_repairs(Session.current_msn)

        if df.empty:
            self.tree.insert('', tk.END, values=["No records found." + (" (Try 'Reset View')" if search_results is not None else "")] + ['']*(len(self.VISIBLE_COLUMNS)-1), tags=('empty',))
            return
            
        for index, row in df.iterrows():
            values = [row[col] for col in self.VISIBLE_COLUMNS]
            self.tree.insert('', tk.END, values=values, iid=row['Repair_ID']) 
            
        if search_results is None:
            self.search_var.set('')


    def apply_search(self):
        if not Session.current_msn:
            messagebox.showerror("Error", "No aircraft project selected.")
            return

        search_value = self.search_var.get().strip()
        search_col = self.search_column_var.get()

        if not search_value:
            self.load_repairs() 
            return

        try:
            results_df = data_manager.search_repairs(Session.current_msn, search_col, search_value)
            
            if results_df.empty:
                 messagebox.showinfo("Search Result", f"No records found matching '{search_value}' in column '{search_col}'.")
                 self.clear_tree()
            else:
                self.load_repairs(search_results=results_df)

        except Exception as e:
            messagebox.showerror("Search Error", f"An error occurred during search: {e}")
            self.load_repairs()

    def open_edit_page(self, event):
        selected_item = self.tree.selection()
        
        if not selected_item:
            return

        repair_id = self.tree.item(selected_item[0], 'iid')
        
        if not repair_id:
             messagebox.showerror("Error", "Could not retrieve Repair ID.")
             return
             
        Session.current_edit_repair_id = repair_id
        
        self.controller.frames[EditRepairPage].on_show(None) 
        self.controller.show_frame(EditRepairPage)
        
# --- AuditOilPage (Omitted for brevity, assumed unchanged) ---
class AuditOilPage(BasePage):
    AUDIT_COLUMNS = [
        'Repair_ID', 'ATA_Chapter', 'Repair_Status', 'CRS_Ref', 
        'Audit_Physical_Status', 'Audit_OIL_Status', 
        'Audit_Documentation_Note', 'OIL_Closure_Note'
    ]
    
    AUDIT_HEADINGS = {
        'Repair_ID': 'Repair ID', 'ATA_Chapter': 'ATA', 'Repair_Status': 'Status', 
        'CRS_Ref': 'CRS Ref', 'Audit_Physical_Status': 'Audit Phys', 
        'Audit_OIL_Status': 'OIL Status', 
        'Audit_Documentation_Note': 'Doc Note', 'OIL_Closure_Note': 'OIL Closure Note'
    }

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Audit and OIL Management Dashboard")
        
        if Session.current_role not in ['Auditor', 'Lessor']:
            ttk.Label(self, text="ACCESS DENIED: Only Auditors or Lessors can use this feature.", 
                      font=("Arial", 14, "bold"), foreground="red").grid(row=1, column=0, pady=50, padx=20)
            self.grid_rowconfigure(2, weight=0)
            return

        self.search_var = tk.StringVar()
        
        info_frame = ttk.LabelFrame(self, text="Audit Status Summary")
        info_frame.grid(row=1, column=0, columnspan=4, pady=10, padx=20, sticky="ew")
        self.status_labels = {}
        
        search_frame = ttk.LabelFrame(self, text="Quick Filter")
        search_frame.grid(row=2, column=0, columnspan=4, pady=10, padx=20, sticky="ew")
        search_frame.columnconfigure(1, weight=1)

        ttk.Label(search_frame, text="Filter by Repair ID/Status:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Button(search_frame, text="Filter", command=self.apply_filter).grid(row=0, column=2, padx=5, pady=5, sticky="e")
        ttk.Button(search_frame, text="Show All", command=self.load_repairs).grid(row=0, column=3, padx=5, pady=5, sticky="e")

        table_frame = ttk.Frame(self)
        table_frame.grid(row=3, column=0, columnspan=4, pady=10, padx=20, sticky="nsew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        self.tree = ttk.Treeview(table_frame, columns=self.AUDIT_COLUMNS, show='headings')
        
        for col in self.AUDIT_COLUMNS:
            self.tree.heading(col, text=self.AUDIT_HEADINGS.get(col, col))
            if col in ['Repair_ID', 'CRS_Ref']:
                self.tree.column(col, width=100, anchor=tk.W)
            elif col in ['Audit_Documentation_Note', 'OIL_Closure_Note']:
                self.tree.column(col, width=200, anchor=tk.W)
            else:
                self.tree.column(col, width=80, anchor=tk.CENTER)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.bind('<Double-1>', self.open_edit_page)

        self.bind("<Visibility>", self.update_content)

    def update_content(self, event):
        if Session.current_role not in ['Auditor', 'Lessor']:
            return
            
        if Session.current_msn:
            self.load_repairs()
            self.update_summary()
        else:
            self.clear_tree()
            messagebox.showinfo("Context Error", "Please select an aircraft project (MSN) first.")

    def clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def load_repairs(self, search_results=None):
        self.clear_tree()
        
        if not Session.current_msn:
            return

        df = search_results if search_results is not None else data_manager.get_all_repairs(Session.current_msn)

        if df.empty:
            self.tree.insert('', tk.END, values=["No records found."] + ['']*(len(self.AUDIT_COLUMNS)-1), tags=('empty',))
            return
            
        for index, row in df.iterrows():
            values = [row.get(col, '') for col in self.AUDIT_COLUMNS]
            self.tree.insert('', tk.END, values=values, iid=row['Repair_ID']) 
            
        if search_results is None:
            self.search_var.set('')

    def apply_filter(self):
        if not Session.current_msn:
            return

        search_value = self.search_var.get().strip()
        df = data_manager.get_all_repairs(Session.current_msn)

        if not search_value:
            self.load_repairs(df)
            return

        results_df = df[
            df['Repair_ID'].astype(str).str.contains(search_value, case=False, na=False) |
            df['Audit_Physical_Status'].astype(str).str.contains(search_value, case=False, na=False) |
            df['Audit_OIL_Status'].astype(str).str.contains(search_value, case=False, na=False)
        ]
        
        if results_df.empty:
             messagebox.showinfo("Filter Result", f"No records found matching '{search_value}'.")
             self.clear_tree()
        else:
            self.load_repairs(search_results=results_df)

    def update_summary(self):
        df = data_manager.get_all_repairs(Session.current_msn)
        
        total = len(df)
        oil_open = len(df[df['Audit_OIL_Status'].astype(str) == 'Open'])
        oil_closed = len(df[df['Audit_OIL_Status'].astype(str) == 'Closed'])
        phys_non_conforming = len(df[df['Audit_Physical_Status'].astype(str) == 'Non-Conforming'])
        
        for widget in self.winfo_children()[1].winfo_children():
             widget.destroy()

        summary_frame = self.winfo_children()[1] 

        ttk.Label(summary_frame, text=f"Total Records: {total}", font=("Arial", 10, "bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        ttk.Label(summary_frame, text=f"OIL Status Open: {oil_open}", foreground="red" if oil_open > 0 else "green").grid(row=0, column=1, padx=10, pady=5, sticky="w")
        ttk.Label(summary_frame, text=f"OIL Status Closed: {oil_closed}", foreground="green").grid(row=0, column=2, padx=10, pady=5, sticky="w")
        ttk.Label(summary_frame, text=f"Physical Non-Conforming: {phys_non_conforming}", foreground="orange" if phys_non_conforming > 0 else "green").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        
    def open_edit_page(self, event):
        selected_item = self.tree.selection()
        
        if not selected_item:
            return

        repair_id = self.tree.item(selected_item[0], 'iid')
        
        if not repair_id:
             messagebox.showerror("Error", "Could not retrieve Repair ID.")
             return
             
        Session.current_edit_repair_id = repair_id
        
        self.controller.frames[EditRepairPage].on_show(None) 
        self.controller.show_frame(EditRepairPage)
# --- DocumentManagementPage, StructuralRepairLog, RoleSelectionPage, ProjectSetupPage, ProjectHomePage (Omitted for brevity, assumed unchanged) ---
# ... (The remaining pages and main execution logic are the same as the previous step) ...

class DocumentManagementPage(BasePage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Document Management (Placeholder)")
        ttk.Label(self, text="Functionality moved to Add New Repair / Edit Repair forms.").grid(row=1, column=0, pady=50)

class StructuralRepairLog(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IATA Structural Repair Log and Audit Tool")
        self.geometry("1000x700") 
        
        self.container = tk.Frame(self)
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        
        for F in (RoleSelectionPage, ProjectSetupPage, ProjectHomePage, AddRepairPage, EditRepairPage, ViewRepairsPage, AuditOilPage):
            frame = F(self.container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(RoleSelectionPage)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()

class RoleSelectionPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        label = ttk.Label(self, text="Select Your Role (IATA Redelivery Process)", 
                          font=("Arial", 18, "bold"))
        label.pack(pady=40, padx=10)

        role_frame = ttk.Frame(self)
        role_frame.pack(pady=20)
        
        ttk.Label(role_frame, text="Current Roles:", font=("Arial", 12, "underline")).pack(pady=10)
        
        roles = ['Lessor', 'Auditor', 'Operator']
        for role in roles:
            btn = ttk.Button(role_frame, text=f"Log in as {role}", 
                             command=lambda r=role: self.select_role(r), width=30)
            btn.pack(pady=10)

    def select_role(self, role):
        Session.current_role = role
        self.controller.show_frame(ProjectSetupPage) 
        messagebox.showinfo("Role Set", f"You are logged in as: {role}")

class ProjectSetupPage(BasePage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Project Selection and Setup")
        
        self.msn_var = tk.StringVar()
        self.current_projects = data_manager.get_all_projects()
        
        self.grid_rowconfigure(1, weight=1)
        
        select_frame = ttk.LabelFrame(self, text="Select Existing Aircraft Project")
        select_frame.grid(row=1, column=0, pady=20, padx=20, sticky="nsw")
        
        self.project_listbox = tk.Listbox(select_frame, height=10, width=40)
        self.project_listbox.pack(padx=10, pady=10)
        self.project_listbox.bind('<<ListboxSelect>>', self.on_project_select)
        
        self.load_project_list()
        
        ttk.Button(select_frame, text="Select Aircraft", command=self.finalize_selection).pack(pady=10)
        
        create_frame = ttk.LabelFrame(self, text="Create New Aircraft Project (Lessor/Auditor Only)")
        create_frame.grid(row=1, column=1, pady=20, padx=20, sticky="nsw")
        
        ttk.Label(create_frame, text="Aircraft MSN:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.msn_entry = ttk.Entry(create_frame, width=25)
        self.msn_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        fields = ['Aircraft_Reg', 'Date_Initiated', 'FH_Initiated', 'FC_Initiated', 'Lease_Agreement_Ref']
        self.project_entries = {}
        for i, field in enumerate(fields):
            ttk.Label(create_frame, text=f"{field.replace('_', ' ')}:").grid(row=i+1, column=0, padx=5, pady=5, sticky="w")
            entry = ttk.Entry(create_frame, width=25)
            entry.grid(row=i+1, column=1, padx=5, pady=5, sticky="w")
            self.project_entries[field] = entry

        self.create_button = ttk.Button(create_frame, text="Create Project", command=self.create_project)
        self.create_button.grid(row=len(fields)+1, column=0, columnspan=2, pady=10)
        
        if Session.current_role == 'Operator':
            for widget in create_frame.winfo_children():
                if widget != create_frame:
                    widget.configure(state='disabled')
        
    def load_project_list(self):
        self.project_listbox.delete(0, tk.END)
        self.current_projects = data_manager.get_all_projects()
        for msn in sorted(self.current_projects.keys()):
            reg = self.current_projects[msn].get('Aircraft_Reg', 'N/A')
            self.project_listbox.insert(tk.END, f"{msn} - Reg: {reg}")
        
        if Session.current_role != 'Operator':
            try:
                create_frame = self.winfo_children()[2] 
                for widget in create_frame.winfo_children():
                    widget.configure(state='normal')
            except IndexError:
                pass 

    def on_project_select(self, event):
        selection = self.project_listbox.curselection()
        if selection:
            msn_string = self.project_listbox.get(selection[0])
            msn = msn_string.split(' - ')[0].strip()
            self.msn_var.set(msn)

    def finalize_selection(self):
        msn = self.msn_var.get()
        if not msn:
            messagebox.showerror("Error", "Please select an Aircraft MSN from the list.")
            return

        Session.current_msn = msn
        
        self.controller.frames[ProjectHomePage].update_content(None) 
        
        self.controller.show_frame(ProjectHomePage)
        
    def create_project(self):
        if Session.current_role not in ['Lessor', 'Auditor']:
            messagebox.showerror("Permission Denied", "Only Lessor or Auditor can create a new project.")
            return
            
        msn = self.msn_entry.get().strip().upper()
        if not msn:
            messagebox.showerror("Input Error", "Aircraft MSN is mandatory.")
            return
            
        project_data = {}
        is_complete = True
        for field, entry in self.project_entries.items():
            value = entry.get().strip()
            project_data[field] = value
            if field in ['Aircraft_Reg', 'Date_Initiated'] and not value: 
                 is_complete = False
                 
        if not is_complete:
            messagebox.showerror("Input Error", "Registration and Initiation Date are mandatory.")
            return
            
        success, message = data_manager.create_new_project(msn, project_data)
        
        if success:
            messagebox.showinfo("Success", message)
            self.msn_var.set(msn)
            self.load_project_list() 
            self.msn_entry.delete(0, tk.END)
            for entry in self.project_entries.values():
                entry.delete(0, tk.END)
        else:
            messagebox.showerror("Error", message)

class ProjectHomePage(BasePage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Project Management Home")
        
        self.detail_frame = ttk.LabelFrame(self, text="Aircraft Details")
        self.detail_frame.grid(row=1, column=0, columnspan=4, pady=10, padx=20, sticky="ew")
        
        button_frame = ttk.Frame(self)
        button_frame.grid(row=2, column=0, columnspan=4, pady=30, sticky="n")

        self.btn_view = ttk.Button(button_frame, text="View All Repairs & Search", 
                                   command=lambda: controller.show_frame(ViewRepairsPage), width=35)
        self.btn_view.pack(pady=10)
        
        self.btn_add = ttk.Button(button_frame, text="Add New Repair (Operator)", 
                                  command=lambda: controller.show_frame(AddRepairPage), width=35)
        self.btn_add.pack(pady=10)
        
        self.btn_audit = ttk.Button(button_frame, text="Audit / OIL Process (Auditor)", 
                                    command=lambda: controller.show_frame(AuditOilPage), width=35)
        self.btn_audit.pack(pady=10)
        
        self.btn_docs = ttk.Button(button_frame, text="Manage Repair Documents", 
                                   command=lambda: controller.show_frame(DocumentManagementPage), width=35)
        self.btn_docs.pack(pady=10)
        
        self.bind("<Visibility>", self.update_content)

    def update_content(self, event):
        for widget in self.detail_frame.winfo_children():
            widget.destroy()
            
        msn = Session.current_msn
        role = Session.current_role
        
        if not msn:
            ttk.Label(self.detail_frame, text="No aircraft selected.").pack(pady=10, padx=10)
            return

        details = data_manager.get_project_details(msn)
        
        if details:
            ttk.Label(self.detail_frame, text=f"MSN: {msn}", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
            ttk.Label(self.detail_frame, text=f"Registration: {details.get('Aircraft_Reg', 'N/A')}").grid(row=1, column=0, padx=10, sticky="w")
            ttk.Label(self.detail_frame, text=f"FH / FC Start: {details.get('FH_Initiated', 'N/A')} / {details.get('FC_Initiated', 'N/A')}").grid(row=1, column=1, padx=10, sticky="w")
            ttk.Label(self.detail_frame, text=f"Lease Ref: {details.get('Lease_Agreement_Ref', 'N/A')}").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        
        self.btn_add.config(state='normal' if role == 'Operator' else 'disabled')
        self.btn_audit.config(state='normal' if role == 'Auditor' or role == 'Lessor' else 'disabled')
        self.btn_docs.config(state='disabled') 
        
# --- Main Execution ---

if __name__ == "__main__":
    app = StructuralRepairLog()
    app.mainloop()