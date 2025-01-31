import os
import re
from PyQt5.QtCore import QThread, pyqtSignal
import anthropic
from openai import OpenAI

class RaceCommentator(QThread):
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
            
        self.system_prompt = self.load_prompt("race_commentator_prompt.txt")

    def run(self):
        self.output_signal.emit("Starting race commentary generation...")
        self.progress_signal.emit(0)

        try:
            self.output_path = self.create_output_file()
            race_events = self.read_race_events()
            commentary = self.get_ai_commentary(race_events)
            
            # Ensure commentary is a string
            if not isinstance(commentary, str):
                commentary = str(commentary)
                
            self.write_commentary(commentary)
            self.output_signal.emit(f"Commentary generation complete. Output saved to {self.output_path}")
            self.progress_signal.emit(100)

        except Exception as e:
            self.output_signal.emit(f"An error occurred: {str(e)}")
            raise  # Re-raise the exception for debugging

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
        if self.settings["api"] == "claude":
            return self._get_claude_commentary(race_events)
        else:
            return self._get_openai_commentary(race_events)

    def _get_claude_commentary(self, race_events):
        try:
            response = self.client.messages.create(
                model=self.settings["model"],
                max_tokens=8000,
                temperature=0.99,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Here's the complete race event log:\n\n{race_events}\n\n"
                            "Please provide commentary for each event, maintaining the original timecodes."
                        )
                    }
                ]
            )
            
            # Handle Claude's response format
            if hasattr(response, 'content') and isinstance(response.content, list):
                content = response.content[0].text
            elif hasattr(response, 'content'):
                content = response.content
            else:
                content = str(response)
                
            return str(content) if content is not None else ""
            
        except Exception as e:
            self.output_signal.emit(f"Error in Claude commentary generation: {str(e)}")
            return ""

    def _get_openai_commentary(self, race_events):
        try:
            messages = []
            
            # For O models that don't support system messages, combine with user content
            if self.settings["model"].startswith(("o-", "o1-")):
                messages.append({
                    "role": "user",
                    "content": f"{self.system_prompt}\n\nHere's the complete race event log:\n\n{race_events}\n\nPlease provide commentary for each event, maintaining the original timecodes."
                })
            else:
                # Standard OpenAI models that support system messages
                messages.extend([
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Here's the complete race event log:\n\n{race_events}\n\n"
                            "Please provide commentary for each event, maintaining the original timecodes."
                        )
                    }
                ])
            
            kwargs = {
                "model": self.settings["model"],
                "messages": messages
            }
            
            # Only add parameters for non-O models
            if not self.settings["model"].startswith(("o-", "o1-")):
                kwargs.update({
                    "temperature": 0.99,
                    "max_tokens": 8000
                })
            
            response = self.client.chat.completions.create(**kwargs)
            
            # Handle OpenAI's response format
            if hasattr(response.choices[0].message, 'content'):
                content = response.choices[0].message.content
            else:
                content = str(response.choices[0].message)
                
            return str(content) if content is not None else ""
            
        except Exception as e:
            self.output_signal.emit(f"Error in OpenAI commentary generation: {str(e)}")
            return ""

    def create_output_file(self):
        base_name = os.path.basename(self.input_path)
        file_name, file_extension = os.path.splitext(base_name)
        new_file_name = f"{file_name}_commentary{file_extension}"

        original_dir = os.path.dirname(self.input_path)
        return os.path.join(original_dir, new_file_name)

    def write_commentary(self, commentary):
        # Ensure commentary is a string and properly encoded
        if not isinstance(commentary, str):
            commentary = str(commentary)
        
        # Write the file
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