import os
import requests
from PyQt5.QtCore import QThread, pyqtSignal
from datetime import datetime, timedelta
import anthropic

class DataFilterer(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, input_path, api_key):
        super().__init__()
        self.input_path = input_path
        self.output_path = None
        self.client = anthropic.Anthropic(api_key=api_key)
        self.prompt = self.load_prompt("data_filterer_prompt.txt")

    def run(self):
        self.output_signal.emit("Starting data filtering...")
        self.progress_signal.emit(0)

        try:
            race_data = self.get_file_content(self.input_path)
            self.progress_signal.emit(10)

            filtered_content = self.filter_race_data(race_data)
            self.progress_signal.emit(50)

            processed_events = filtered_content.split('\n')
            self.progress_signal.emit(75)

            self.output_path = self.create_filtered_file(processed_events)
            self.progress_signal.emit(100)

            self.output_signal.emit(f"Filtered data saved to {self.output_path}")
        except Exception as e:
            self.output_signal.emit(f"An error occurred: {str(e)}")

    def get_file_content(self, path):
        if path.startswith(('http://', 'https://')):
            response = requests.get(path)
            response.raise_for_status()
            return response.text
        else:
            with open(path, 'r', encoding='utf-8') as file:
                return file.read()

    def load_prompt(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            return f"Error: {filename} not found. Please create this file with the desired prompt."

    def filter_race_data(self, race_data):
        message = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.1,
            messages=[
                {
                    "role": "user",
                    "content": f"{self.prompt}\n\nHere is the race data to filter:\n\n<race_data>\n{race_data}\n</race_data>"
                }
            ]
        )

        filtered_content = message.content[0].text if isinstance(message.content, list) else message.content
        return filtered_content

    def create_filtered_file(self, filtered_content):
        base_name = os.path.basename(self.input_path)
        file_name, file_extension = os.path.splitext(base_name)
        new_file_name = f"{file_name}_filtered{file_extension}"

        original_dir = os.path.dirname(self.input_path)
        new_file_path = os.path.join(original_dir, new_file_name)

        with open(new_file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(filtered_content))

        return new_file_path

    def get_output_path(self):
        return self.output_path
