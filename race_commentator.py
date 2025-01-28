import os
import re
from PyQt5.QtCore import QThread, pyqtSignal
import anthropic

class RaceCommentator(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, input_path, api_key):
        super().__init__()
        self.input_path = input_path
        self.output_path = None
        self.client = anthropic.Anthropic(api_key=api_key)
        self.system_prompt = self.load_prompt("race_commentator_prompt.txt")

    def run(self):
        self.output_signal.emit("Starting race commentary generation...")
        self.progress_signal.emit(0)

        try:
            self.output_path = self.create_output_file()
            race_events = self.read_race_events()
            commentary = self.get_ai_commentary(race_events)
            self.write_commentary(commentary)

            self.output_signal.emit(f"Commentary generation complete. Output saved to {self.output_path}")
            self.progress_signal.emit(100)

        except Exception as e:
            self.output_signal.emit(f"An error occurred: {str(e)}")

    def read_race_events(self):
        with open(self.input_path, 'r', encoding='utf-8') as input_file:
            return input_file.read()

    def load_prompt(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            return f"Error: {filename} not found. Please create this file with the desired prompt."

    def get_ai_commentary(self, race_events):
        messages = [
            {
                "role": "user",
                "content": (
                    f"Here's the complete race event log:\n\n{race_events}\n\n"
                    "Please provide commentary for each event, maintaining the original timecodes."
                )
            }
        ]

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8000,  # Adjust this value based on your needs
            temperature=0.99,
            system=self.system_prompt,
            messages=messages
        )

        return response.content[0].text

    def create_output_file(self):
        base_name = os.path.basename(self.input_path)
        file_name, file_extension = os.path.splitext(base_name)
        new_file_name = f"{file_name}_commentary{file_extension}"

        original_dir = os.path.dirname(self.input_path)
        return os.path.join(original_dir, new_file_name)

    def write_commentary(self, commentary):
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write(commentary)

        # Emit progress updates
        lines = commentary.split('\n')
        total_lines = len(lines)
        for i, line in enumerate(lines):
            self.output_signal.emit(line)
            progress = int(((i + 1) / total_lines) * 100)
            self.progress_signal.emit(progress)

    def get_output_path(self):
        return self.output_path
