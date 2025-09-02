"""
Main GUI class for the Speeds and Feeds Calculator.

Contains the simplified GUI class with updated imports.
"""

import logging
from PySide6 import QtWidgets, QtCore

from .ui.boxes import ToolBox, MaterialBox, CuttingBox, MachineBox, ResultsBox
from .calculators.base import FeedsAndSpeeds
from .constants.units import FT_TO_M
from .constants.machining import MACHINE_RIGIDITY_FACTORS
from .formulas.validation import validate_machining_parameters


class GUI(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(GUI, self).__init__(parent)
        self.settings = None

        self.setWindowTitle(
            "⚙️ Speeds & Feeds Calculator v2.0 - Enhanced with HSM"
        )
        self.setMinimumSize(1000, 1100)  # Set to match successful large size test
        self.resize(1200, 1100)
        settings = QtCore.QSettings("speeds-and-feeds-calc", "SpeedsAndFeedsCalculator")

        try:
            self.restoreGeometry(settings.value("geometry"))

        except Exception as e:
            logging.warning(
                "Unable to load settings. First time opening the tool?\n" + str(e)
            )

        # Layouts with improved spacing
        main_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        sections_layout = QtWidgets.QHBoxLayout()
        sections_layout.setSpacing(15)

        self.setCentralWidget(main_widget)
        main_widget.setLayout(main_layout)
        form = QtWidgets.QFormLayout()

        self.tool_box = ToolBox(self)
        self.material_box = MaterialBox(self)
        self.cutting_box = CuttingBox(self)
        self.machine_box = MachineBox(self)

        self.results_box = ResultsBox()

        # Add Widgets
        main_layout.addLayout(form)
        main_layout.addLayout(sections_layout)
        sections_layout.addWidget(self.tool_box)
        sections_layout.addWidget(self.material_box)
        sections_layout.addWidget(self.cutting_box)
        sections_layout.addWidget(self.machine_box)
        main_layout.addWidget(self.results_box)

        # Logic - Use valueChanged for real-time updates
        self.tool_box.fluteNum.valueChanged.connect(self.update)
        self.cutting_box.DOC.valueChanged.connect(self.update)
        self.cutting_box.WOC.valueChanged.connect(self.update)
        self.cutting_box.surface_speed.valueChanged.connect(self.update)
        self.cutting_box.feed_per_tooth.valueChanged.connect(self.update)
        self.cutting_box.Kc.valueChanged.connect(self.update)
        self.tool_box.toolDiameter.valueChanged.connect(self.toolDiameterChanged)
        
        # Connect unit switching - connect to both handlers
        self.tool_box.unit_group.buttonClicked.connect(self.tool_box.on_unit_changed)
        self.tool_box.unit_group.buttonClicked.connect(self.on_unit_changed)
        
        # Material box signals
        self.material_box.materialChanged.connect(self.on_material_changed)
        self.material_box.coatingChanged.connect(self.update)  # Update calculations when coating changes
        
        # Machine box signals
        self.machine_box.rigidityCombo.currentTextChanged.connect(self.update)  # Update when rigidity changes

        self.cutting_box.init()
        self.update()

    def toolDiameterChanged(self):
        self.cutting_box.init()
        self.update()
    
    def on_material_changed(self, material_key: str, kc: float, sfm: float, smm: float, chip_load: float, name: str):
        """Handle material selection and auto-populate cutting parameters."""
        # Auto-populate material-specific parameters
        self.cutting_box.Kc.setValue(kc)
        
        # Set surface speed (convert based on current units)
        self.cutting_box.surface_speed.blockSignals(True)
        if self.tool_box.is_metric():
            self.cutting_box.surface_speed.setValue(smm)
        else:
            self.cutting_box.surface_speed.setValue(sfm)
        self.cutting_box.surface_speed.blockSignals(False)
        
        # Set feed per tooth (convert based on current units)
        from .constants.units import MM_TO_IN
        self.cutting_box.feed_per_tooth.blockSignals(True)
        if self.tool_box.is_metric():
            self.cutting_box.feed_per_tooth.setValue(chip_load)
        else:
            self.cutting_box.feed_per_tooth.setValue(chip_load * MM_TO_IN)
        self.cutting_box.feed_per_tooth.blockSignals(False)
        
        # Set material context for UI adaptation
        self.cutting_box.set_material_context(material_key)
        
        # Update the calculations
        self.update()
    
    def on_unit_changed(self):
        """Handle unit system change"""
        # Update tool box units (this will be called automatically by the signal)
        # But we need to make sure the ToolBox handles its own conversion
        
        # Update cutting box units
        self.cutting_box.update_units()
        
        # Update calculations
        self.update()

    def closeEvent(self, event):
        self.settings = QtCore.QSettings(
            "speeds-and-feeds-calc", "SpeedsAndFeedsCalculator"
        )
        self.settings.setValue("geometry", self.saveGeometry())
        QtWidgets.QWidget.closeEvent(self, event)

    def get_rpm_status(self, rpm):
        """Determine RPM status based on machine limits and preferred RPM"""
        min_rpm = self.machine_box.minRPM.value()
        preferred_rpm = self.machine_box.preferredRPM.value()
        max_rpm = self.machine_box.maxRPM.value()
        
        # Check if outside machine limits (danger)
        if rpm < min_rpm:
            return "danger", f"below minimum ({min_rpm:,} RPM)"
        elif rpm > max_rpm:
            return "danger", f"above maximum ({max_rpm:,} RPM)"
        
        # Check if close to preferred RPM (good)
        preferred_tolerance = preferred_rpm * 0.1  # 10% tolerance around preferred
        if abs(rpm - preferred_rpm) <= preferred_tolerance:
            return "good", f"near preferred ({preferred_rpm:,} RPM)"
        
        # Check if approaching limits (warning)
        elif rpm > max_rpm * 0.9:  # Within 90% of max
            return "warning", "approaching maximum"
        elif rpm < min_rpm * 1.1:  # Within 110% of min
            return "warning", "near minimum"
        else:
            return "info", "within safe range"
    

    def update(self):
        fs = FeedsAndSpeeds()

        # Tool
        fs.diameter = self.tool_box.get_diameter_mm()
        fs.flute_num = self.tool_box.fluteNum.value()

        # Cutting
        fs.doc = self.cutting_box.get_doc_mm()
        fs.woc = self.cutting_box.get_woc_mm()
        fs.smm = self.cutting_box.get_surface_speed_sfm() * FT_TO_M  # Convert SFM to SMM
        fs.mmpt = self.cutting_box.get_feed_per_tooth_mm()
        fs.kc = self.cutting_box.Kc.value()
        
        # HSM and chip thinning parameters
        fs.hsm_enabled = self.cutting_box.is_hsm_enabled()
        fs.chip_thinning_enabled = self.cutting_box.is_chip_thinning_enabled()
        fs.tool_stickout = self.cutting_box.get_tool_stickout_mm()
        
        # Machine rigidity
        fs.rigidity_level = self.machine_box.get_selected_rigidity()
        
        # Material type for rigidity-aware adjustments
        if hasattr(self.material_box, 'current_material') and self.material_box.current_material:
            material_key, _, _, _, _, _ = self.material_box.current_material
            fs.material_type = material_key

        # Do the formulas (now includes rigidity adjustments and warnings)
        calculation_warnings = fs.calculate()
        
        # Get additional validation warnings
        validation_warnings = validate_machining_parameters(fs.rpm, fs.feed, fs.doc, fs.woc, fs.diameter)
        all_warnings = calculation_warnings + validation_warnings
        
        # Get RPM status for color coding  
        rpm_status, rpm_message = self.get_rpm_status(fs.rpm)
        
        # Update dashboard widgets
        machine_limits = (
            self.machine_box.minRPM.value(),
            self.machine_box.preferredRPM.value(), 
            self.machine_box.maxRPM.value()
        )
        spindle_capacity = self.machine_box.spindlePower.value()
        
        # Get current material info if available
        material_info = None
        if hasattr(self.material_box, 'current_material') and self.material_box.current_material:
            material_info = self.material_box.current_material
        
        # Pass rigidity info to results display
        rigidity_level = fs.rigidity_level
        rigidity_name = MACHINE_RIGIDITY_FACTORS[rigidity_level]['name']
        rigidity_info = (rigidity_level, rigidity_name)
        
        self.results_box.update_dashboard_values(fs, rpm_status, rpm_message, machine_limits, spindle_capacity, material_info, all_warnings, rigidity_info)
        
        # Update material box with warnings if any
        if all_warnings:
            warning_text = "⚠️ Warnings:\n" + "\n".join(all_warnings[:3])  # Show first 3 warnings
            self.material_box.materialInfo.setStyleSheet("color: #ff8c00; font-size: 11px; padding: 5px;")
            if hasattr(self.material_box, 'current_material') and self.material_box.current_material:
                # Preserve material info and add warnings
                material_key, kc, sfm, smm, chip_load, name = self.material_box.current_material
                current_info = self.material_box.materialInfo.text()
                if not current_info.startswith("⚠️"):
                    self.material_box.materialInfo.setText(current_info + "\n\n" + warning_text)
        else:
            # Reset to normal color if no warnings
            self.material_box.materialInfo.setStyleSheet("color: #888; font-size: 11px; padding: 5px;")