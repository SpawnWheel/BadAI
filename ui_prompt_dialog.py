# ui_prompt_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTextEdit, QLabel, QDialogButtonBox
)

class PromptEditDialog(QDialog):
    """Simple Dialog for editing prompt content."""
    def __init__(self, prompt_name, prompt_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Prompt: {prompt_name}")
        layout = QVBoxLayout(self)

        self.prompt_content_edit = QTextEdit()
        self.prompt_content_edit.setText(prompt_content)
        layout.addWidget(QLabel("Prompt Content:"))
        layout.addWidget(self.prompt_content_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_content(self):
        """Returns the text content from the editor."""
        return self.prompt_content_edit.toPlainText()