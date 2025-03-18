from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QSpinBox, 
    QDoubleSpinBox, QLabel, QGroupBox
)

class AccidentSettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create group box for accident detection settings
        group_box = QGroupBox("Accident Detection Settings")
        form_layout = QFormLayout()

        # Speed threshold setting
        self.speed_threshold = QSpinBox()
        self.speed_threshold.setRange(0, 100)
        self.speed_threshold.setValue(10)  # Default 10 km/h
        self.speed_threshold.setSuffix(" km/h")
        form_layout.addRow("Speed Threshold:", self.speed_threshold)

        # Time threshold setting
        self.time_threshold = QDoubleSpinBox()
        self.time_threshold.setRange(0.1, 10.0)
        self.time_threshold.setValue(0.5)  # Default 0.5 seconds
        self.time_threshold.setSuffix(" seconds")
        self.time_threshold.setSingleStep(0.1)
        form_layout.addRow("Time Threshold:", self.time_threshold)

        # Accident proximity time setting
        self.proximity_time = QDoubleSpinBox()
        self.proximity_time.setRange(0.1, 10.0)
        self.proximity_time.setValue(4.0)  # Default 4 seconds
        self.proximity_time.setSuffix(" seconds")
        self.proximity_time.setSingleStep(0.1)
        form_layout.addRow("Accident Proximity Time:", self.proximity_time)

        group_box.setLayout(form_layout)
        layout.addWidget(group_box)
        layout.addStretch()