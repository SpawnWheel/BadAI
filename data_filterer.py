import os
import requests
from PyQt5.QtCore import QThread, pyqtSignal
from datetime import datetime, timedelta
import anthropic
from openai import OpenAI

class DataFilterer(QThread):
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
            
        self.prompt = self.load_prompt("data_filterer_prompt.txt")

    def run(self):
        self.output_signal.emit("Starting data filtering...")
        self.progress_signal.emit(0)

        try:
            race_data = self.get_file_content(self.input_path)
            self.progress_signal.emit(10)

            filtered_content = self.filter_race_data(race_data)
            if not isinstance(filtered_content, str):
                filtered_content = str(filtered_content)
            self.progress_signal.emit(50)

            processed_events = filtered_content.split('\n')
            processed_events = [event for event in processed_events if event.strip()]
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
        if self.settings["api"] == "claude":
            return self._filter_with_claude(race_data)
        else:
            return self._filter_with_openai(race_data)

    def _filter_with_claude(self, race_data):
        try:
            message = self.client.messages.create(
                model=self.settings["model"],
                max_tokens=4000,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": f"{self.prompt}\n\nHere is the race data to filter:\n\n<race_data>\n{race_data}\n</race_data>"
                    }
                ]
            )
            content = message.content[0].text if isinstance(message.content, list) else message.content
            return str(content) if content is not None else ""
            
        except Exception as e:
            self.output_signal.emit(f"Error in Claude filtering: {str(e)}")
            return ""

    def _filter_with_openai(self, race_data):
        try:
            messages = []
            
            # For O models that don't support system messages, combine with user content
            if self.settings["model"].startswith(("o-", "o1-")):
                messages.append({
                    "role": "user",
                    "content": f"You are a race data filterer that processes racing telemetry and events into a clean, organized format.\n\n{self.prompt}\n\nHere is the race data to filter:\n\n<race_data>\n{race_data}\n</race_data>"
                })
            else:
                # Standard OpenAI models that support system messages
                messages.extend([
                    {
                        "role": "system",
                        "content": "You are a race data filterer that processes racing telemetry and events into a clean, organized format."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"{self.prompt}\n\nHere is the race data to filter:\n\n<race_data>\n{race_data}\n</race_data>"
                            }
                        ]
                    }
                ])
            
            kwargs = {
                "model": self.settings["model"],
                "messages": messages
            }
            
            # Only add parameters for non-O models
            if not self.settings["model"].startswith(("o-", "o1-")):
                kwargs.update({
                    "temperature": 0.1,
                    "max_tokens": 4000
                })
            
            response = self.client.chat.completions.create(**kwargs)
            
            # Extract the content from OpenAI's response
            content = response.choices[0].message.content
            return str(content) if content is not None else ""
            
        except Exception as e:
            self.output_signal.emit(f"Error in OpenAI filtering: {str(e)}")
            return ""

    def create_filtered_file(self, filtered_content):
        base_name = os.path.basename(self.input_path)
        file_name, file_extension = os.path.splitext(base_name)
        new_file_name = f"{file_name}_filtered{file_extension}"

        original_dir = os.path.dirname(self.input_path)
        new_file_path = os.path.join(original_dir, new_file_name)

        # Ensure we're writing a string
        content_to_write = '\n'.join(str(line) for line in filtered_content)
        
        with open(new_file_path, 'w', encoding='utf-8') as f:
            f.write(content_to_write)

        return new_file_path

    def get_output_path(self):
        return self.output_path