# data_filterer.py
import os
import requests
from PyQt5.QtCore import QThread, pyqtSignal
from datetime import datetime, timedelta
import anthropic
from openai import OpenAI
import google.generativeai as genai

class DataFilterer(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    # Modified __init__ to accept prompt_content
    def __init__(self, input_path, settings, prompt_content):
        super().__init__()
        self.input_path = input_path
        self.output_path = None
        self.settings = settings
        self.prompt = prompt_content # Store the passed prompt content

        # Initialize appropriate client based on settings
        if self.settings["api"] == "claude":
            self.client = anthropic.Anthropic(api_key=settings["claude_key"])
        elif self.settings["api"] == "openai":
            self.client = OpenAI(api_key=settings["openai_key"])
        elif self.settings["api"] == "gemini":
            self.client = None # No persistent client needed
        else:
             self.client = None

        # Removed self.load_prompt call

    def run(self):
        self.output_signal.emit("Starting data filtering...")
        self.progress_signal.emit(0)

        if not self.prompt: # Check if prompt content is missing
             self.output_signal.emit("Error: No prompt content provided to DataFilterer.")
             return # Stop execution

        try:
            race_data = self.get_file_content(self.input_path)
            self.progress_signal.emit(10)

            # Check if race_data is valid
            if race_data is None:
                 raise Exception("Failed to read race data file.")

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
        try:
            if path.startswith(('http://', 'https://')):
                response = requests.get(path)
                response.raise_for_status()
                return response.text
            else:
                with open(path, 'r', encoding='utf-8', errors='replace') as file: # Added errors='replace'
                    return file.read()
        except FileNotFoundError:
             self.output_signal.emit(f"Error: Input file not found at {path}")
             return None
        except requests.exceptions.RequestException as e:
             self.output_signal.emit(f"Error fetching file from URL {path}: {e}")
             return None
        except Exception as e:
             self.output_signal.emit(f"Error reading file {path}: {e}")
             return None

    # Removed load_prompt method

    def filter_race_data(self, race_data):
        if self.settings["api"] == "claude":
            return self._filter_with_claude(race_data)
        elif self.settings["api"] == "openai":
            return self._filter_with_openai(race_data)
        elif self.settings["api"] == "gemini":
            return self._filter_with_gemini(race_data)
        else:
            self.output_signal.emit(f"Error: Unknown API type '{self.settings['api']}'")
            return ""

    def _filter_with_claude(self, race_data):
        if not self.client:
             self.output_signal.emit("Error: Claude client not initialized.")
             return ""
        try:
            message = self.client.messages.create(
                model=self.settings["model"],
                max_tokens=4000,
                temperature=0.1,
                # Use self.prompt (which holds the content)
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
        if not self.client:
             self.output_signal.emit("Error: OpenAI client not initialized.")
             return ""
        try:
            messages = []

            if self.settings["model"].startswith(("o-", "o1-")):
                 messages.append({
                    "role": "user",
                    # Use self.prompt (which holds the content)
                    "content": f"You are a race data filterer that processes racing telemetry and events into a clean, organized format.\n\n{self.prompt}\n\nHere is the race data to filter:\n\n<race_data>\n{race_data}\n</race_data>"
                })
            else:
                 messages.extend([
                    {
                        "role": "system",
                        "content": "You are a race data filterer that processes racing telemetry and events into a clean, organized format."
                    },
                    {
                        "role": "user",
                        # Use self.prompt (which holds the content)
                        "content": f"{self.prompt}\n\nHere is the race data to filter:\n\n<race_data>\n{race_data}\n</race_data>"
                    }
                ])

            kwargs = {
                "model": self.settings["model"],
                "messages": messages
            }
            if not self.settings["model"].startswith(("o-", "o1-")):
                kwargs.update({
                    "temperature": 0.1,
                    "max_tokens": 4000
                })

            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            return str(content) if content is not None else ""

        except Exception as e:
            self.output_signal.emit(f"Error in OpenAI filtering: {str(e)}")
            return ""

    def _filter_with_gemini(self, race_data):
        """Filters race data using the Google Gemini API."""
        try:
            api_key = self.settings.get("google_key")
            if not api_key:
                self.output_signal.emit("Error: Google API Key not found in settings.")
                return ""

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(self.settings["model"])

            # Use self.prompt (which holds the content)
            full_prompt = f"{self.prompt}\n\nHere is the race data to filter:\n\n<race_data>\n{race_data}\n</race_data>"

            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
            response = model.generate_content(full_prompt, safety_settings=safety_settings)

            if response.parts:
                 return response.text
            elif response.prompt_feedback.block_reason:
                 block_reason = response.prompt_feedback.block_reason
                 self.output_signal.emit(f"Warning: Gemini response blocked. Reason: {block_reason}")
                 return f"Blocked by API: {block_reason}"
            else:
                 self.output_signal.emit("Warning: Gemini returned an empty response.")
                 return ""

        except Exception as e:
            self.output_signal.emit(f"Error in Gemini filtering: {str(e)}")
            return ""

    def create_filtered_file(self, filtered_content):
        if not self.input_path or not os.path.exists(self.input_path):
             self.output_signal.emit(f"Error: Input file path '{self.input_path}' is invalid or does not exist.")
             return None

        try:
            base_name = os.path.basename(self.input_path)
            file_name, file_extension = os.path.splitext(base_name)
            if not file_extension:
                file_extension = ".txt"
            new_file_name = f"{file_name}_filtered{file_extension}"

            original_dir = os.path.dirname(self.input_path)
            if not original_dir or not os.path.isdir(original_dir):
                 original_dir = os.getcwd()
                 self.output_signal.emit(f"Warning: Could not determine input directory, saving filtered file to current directory: {original_dir}")

            new_file_path = os.path.join(original_dir, new_file_name)
            content_to_write = '\n'.join(str(line) for line in filtered_content)

            with open(new_file_path, 'w', encoding='utf-8') as f:
                f.write(content_to_write)

            return new_file_path
        except Exception as e:
            self.output_signal.emit(f"Error creating filtered file: {str(e)}")
            return None

    def get_output_path(self):
        return self.output_path