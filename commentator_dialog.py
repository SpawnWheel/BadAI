from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit,
    QPushButton, QLabel, QDialogButtonBox
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
        form_layout.addRow("ElevenLabs Voice ID:", self.voice_id_edit)

        # Main prompt field
        self.main_prompt_edit = QTextEdit()
        form_layout.addRow("Main Commentary Prompt:", self.main_prompt_edit)

        # Second pass prompt field
        self.second_pass_prompt_edit = QTextEdit()
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
        return {
            'name': self.name_edit.text(),
            'personality': self.personality_edit.text(),
            'style': self.style_edit.text(),
            'examples': [line for line in self.examples_edit.toPlainText().split('\n') if line.strip()],
            'voice_id': self.voice_id_edit.text(),
            'main_prompt': self.main_prompt_edit.toPlainText(),
            'second_pass_prompt': self.second_pass_prompt_edit.toPlainText()
        }