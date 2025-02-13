from PyQt5.QtCore import QThread, pyqtSignal
import anthropic
from openai import OpenAI
import os
import re


class SecondPassCommentator(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, input_path, settings):
        super().__init__()
        self.input_path = input_path
        self.output_path = None
        self.settings = settings

        # Initialize appropriate client based on settings
        if self.settings["api"] == "claude":
            self.client = anthropic.Anthropic(api_key=settings["claude_key"])
        else:
            self.client = OpenAI(api_key=settings["openai_key"])

        self.prompt = self.load_prompt("second_commentator.txt")

    def run(self):
        self.output_signal.emit("Starting second pass commentary generation...")
        self.progress_signal.emit(0)

        try:
            race_data = self.read_input_file()
            self.progress_signal.emit(25)

            commentary = self.generate_commentary(race_data)
            self.progress_signal.emit(75)

            self.save_commentary(commentary)
            self.progress_signal.emit(100)

            self.output_signal.emit(f"Second pass commentary saved to {self.output_path}")

        except Exception as e:
            self.output_signal.emit(f"Error in second pass commentary: {str(e)}")

    def read_input_file(self):
        with open(self.input_path, 'r', encoding='utf-8') as f:
            return f.read()

    def load_prompt(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return f"Error: {filename} not found"

    def generate_commentary(self, race_data):
        if self.settings["api"] == "claude":
            return self._generate_with_claude(race_data)
        else:
            return self._generate_with_openai(race_data)

    def _generate_with_claude(self, race_data):
        try:
            response = self.client.messages.create(
                model=self.settings["model"],
                max_tokens=4000,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": f"{self.prompt}\n\nHere is the race data to commentate:\n\n{race_data}"
                    }
                ]
            )

            content = response.content[0].text if isinstance(response.content, list) else response.content
            return str(content) if content is not None else ""

        except Exception as e:
            self.output_signal.emit(f"Error in Claude commentary: {str(e)}")
            return ""

    def _generate_with_openai(self, race_data):
        try:
            messages = []

            # Handle different model types appropriately
            if self.settings["model"].startswith(("o-", "o1-")):
                messages.append({
                    "role": "user",
                    "content": f"{self.prompt}\n\nHere is the race data to commentate:\n\n{race_data}"
                })
            else:
                messages.extend([
                    {
                        "role": "system",
                        "content": "You are a racing commentator providing expert analysis."
                    },
                    {
                        "role": "user",
                        "content": f"{self.prompt}\n\nHere is the race data to commentate:\n\n{race_data}"
                    }
                ])

            kwargs = {
                "model": self.settings["model"],
                "messages": messages
            }

            if not self.settings["model"].startswith(("o-", "o1-")):
                kwargs.update({
                    "temperature": 0.7,
                    "max_tokens": 4000
                })

            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            return str(content) if content is not None else ""

        except Exception as e:
            self.output_signal.emit(f"Error in OpenAI commentary: {str(e)}")
            return ""

    def save_commentary(self, commentary):
        base_name = os.path.basename(self.input_path)
        file_name, _ = os.path.splitext(base_name)
        new_file_name = f"{file_name}_filled.txt"

        self.output_path = os.path.join(os.path.dirname(self.input_path), new_file_name)

        # Ensure the commentary maintains proper formatting
        formatted_lines = []
        for line in commentary.split('\n'):
            line = line.strip()
            if line and re.match(r'\d{2}:\d{2}:\d{2} - ', line):
                formatted_lines.append(line)

        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(formatted_lines))

    def get_output_path(self):
        return self.output_path