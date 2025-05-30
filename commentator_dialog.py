from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit,
    QPushButton, QLabel, QDialogButtonBox, QComboBox, QCheckBox, QGroupBox, QHBoxLayout
)


class CommentatorDialog(QDialog):
    def __init__(self, parent=None, existing_metadata=None):
        super().__init__(parent)
        self.existing_metadata = existing_metadata
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Add Commentator" if not self.existing_metadata else "Edit Commentator")
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        # Name field
        self.name_edit = QLineEdit()
        if self.existing_metadata:
            self.name_edit.setText(self.existing_metadata.name)
        form_layout.addRow("Name:", self.name_edit)

        # Personality field
        self.personality_edit = QLineEdit()
        if self.existing_metadata:
            self.personality_edit.setText(self.existing_metadata.personality)
        form_layout.addRow("Personality:", self.personality_edit)

        # Style field
        self.style_edit = QLineEdit()
        if self.existing_metadata:
            self.style_edit.setText(self.existing_metadata.style)
        form_layout.addRow("Style:", self.style_edit)

        # Examples field
        self.examples_edit = QTextEdit()
        if self.existing_metadata:
            self.examples_edit.setText("\n".join(self.existing_metadata.examples))
        form_layout.addRow("Examples (one per line):", self.examples_edit)

        # Voice ID field
        self.voice_id_edit = QLineEdit()
        if self.existing_metadata:
            self.voice_id_edit.setText(self.existing_metadata.voice_id)
        form_layout.addRow("Cartesia Voice ID:", self.voice_id_edit)

        # Add Cartesia-specific voice settings
        voice_settings_group = QGroupBox("Voice Settings")
        voice_settings_layout = QFormLayout()

        # Speed setting
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["slowest", "slow", "normal", "fast", "fastest"])
        if self.existing_metadata and hasattr(self.existing_metadata, 'voice_speed'):
            index = self.speed_combo.findText(self.existing_metadata.voice_speed)
            if index >= 0:
                self.speed_combo.setCurrentIndex(index)
            else:
                self.speed_combo.setCurrentText("normal")  # Default
        else:
            self.speed_combo.setCurrentText("normal")  # Default
        voice_settings_layout.addRow("Speech Speed:", self.speed_combo)

        # Emotion settings
        emotion_group = QGroupBox("Emotions")
        emotion_layout = QVBoxLayout()

        self.emotion_checkboxes = {}
        emotions = ["positivity", "negativity", "enthusiasm", "curiosity", "confidence"]
        for emotion in emotions:
            checkbox = QCheckBox(emotion.capitalize())
            self.emotion_checkboxes[emotion] = checkbox
            emotion_layout.addWidget(checkbox)

            # Check if we should set it based on existing metadata
            if self.existing_metadata and hasattr(self.existing_metadata, 'voice_emotions'):
                # Check if the emotion is in the list (with or without intensity suffix)
                for e in self.existing_metadata.voice_emotions:
                    if e == emotion or e.startswith(f"{emotion}:"):
                        checkbox.setChecked(True)
                        break

        emotion_group.setLayout(emotion_layout)
        voice_settings_layout.addRow("Emotions:", emotion_group)

        # Emotion intensity
        self.intensity_combo = QComboBox()
        self.intensity_combo.addItems(["low", "medium", "high"])
        if self.existing_metadata and hasattr(self.existing_metadata, 'voice_intensity'):
            index = self.intensity_combo.findText(self.existing_metadata.voice_intensity)
            if index >= 0:
                self.intensity_combo.setCurrentIndex(index)
            else:
                self.intensity_combo.setCurrentText("medium")  # Default
        else:
            self.intensity_combo.setCurrentText("medium")  # Default
        voice_settings_layout.addRow("Emotion Intensity:", self.intensity_combo)

        voice_settings_group.setLayout(voice_settings_layout)
        form_layout.addRow("", voice_settings_group)

        # Main prompt field
        self.main_prompt_edit = QTextEdit()
        if self.existing_metadata and hasattr(self.existing_metadata, 'main_prompt'):
            self.main_prompt_edit.setText(self.existing_metadata.main_prompt)
        form_layout.addRow("Main Commentary Prompt:", self.main_prompt_edit)

        # Second pass prompt field
        self.second_pass_prompt_edit = QTextEdit()
        if self.existing_metadata and hasattr(self.existing_metadata, 'second_pass_prompt'):
            self.second_pass_prompt_edit.setText(self.existing_metadata.second_pass_prompt)
        form_layout.addRow("Second Pass Commentary Prompt:", self.second_pass_prompt_edit)

        layout.addLayout(form_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_data(self):
        # Get the selected emotions
        selected_emotions = []
        for emotion, checkbox in self.emotion_checkboxes.items():
            if checkbox.isChecked():
                # Add intensity for selected emotions
                if self.intensity_combo.currentText() != "medium":
                    selected_emotions.append(f"{emotion}:{self.intensity_combo.currentText()}")
                else:
                    selected_emotions.append(emotion)

        return {
            'name': self.name_edit.text(),
            'personality': self.personality_edit.text(),
            'style': self.style_edit.text(),
            'examples': [line for line in self.examples_edit.toPlainText().split('\n') if line.strip()],
            'voice_id': self.voice_id_edit.text(),
            'voice_speed': self.speed_combo.currentText(),
            'voice_emotions': selected_emotions,
            'voice_intensity': self.intensity_combo.currentText(),
            'main_prompt': self.main_prompt_edit.toPlainText(),
            'second_pass_prompt': self.second_pass_prompt_edit.toPlainText()
        }