# race_commentator.py
import os
import re
from PyQt5.QtCore import QThread, pyqtSignal
import anthropic
from openai import OpenAI
# --- Add Google Gemini import ---
import google.generativeai as genai
# ------------------------------

class RaceCommentator(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, input_path, settings):
        super().__init__()
        self.input_path = input_path
        self.output_path = None
        self.settings = settings

        # Initialize appropriate client based on settings
        # Note: Gemini client is configured just before use with the API key
        if self.settings["api"] == "claude":
            self.client = anthropic.Anthropic(api_key=settings["claude_key"])
        elif self.settings["api"] == "openai":
            self.client = OpenAI(api_key=settings["openai_key"])
        elif self.settings["api"] == "gemini":
            self.client = None # No persistent client needed for google-generativeai v0.x.x
        else:
             self.client = None # Handle unknown case


        # Use the custom prompt from settings for main commentary
        # Ensure 'main_prompt' exists in settings, provide fallback if not
        self.system_prompt = settings.get('main_prompt', "You are a race commentator.") # Basic fallback

    def run(self):
        self.output_signal.emit("Starting race commentary generation...")
        self.progress_signal.emit(0)

        try:
            # Create output file for first pass
            self.output_path = self.create_output_file()
            if not self.output_path: # Check if file creation failed
                 raise Exception("Failed to create output file path.")

            race_events = self.read_race_events()
            self.progress_signal.emit(20)

            # Generate commentary
            commentary = self.get_ai_commentary(race_events)
            if commentary is None: # Check if commentary generation failed
                 raise Exception("Commentary generation returned None.")
            if not isinstance(commentary, str):
                commentary = str(commentary)

            self.write_commentary(commentary)

            self.output_signal.emit(f"Commentary generation complete. Output saved to {self.output_path}")
            self.progress_signal.emit(100)

        except Exception as e:
            self.output_signal.emit(f"An error occurred during commentary generation: {str(e)}")
            # Optionally re-raise if needed
            # raise

    def read_race_events(self):
        try:
            with open(self.input_path, 'r', encoding='utf-8') as input_file:
                return input_file.read()
        except FileNotFoundError:
             self.output_signal.emit(f"Error: Input file not found at {self.input_path}")
             raise # Re-raise the error to stop execution if file is critical
        except Exception as e:
             self.output_signal.emit(f"Error reading input file {self.input_path}: {str(e)}")
             raise # Re-raise

    def get_ai_commentary(self, race_events):
        if self.settings["api"] == "claude":
            return self._get_claude_commentary(race_events)
        elif self.settings["api"] == "openai":
            return self._get_openai_commentary(race_events)
        # --- Add Gemini handling ---
        elif self.settings["api"] == "gemini":
            return self._get_gemini_commentary(race_events)
        # --------------------------
        else:
            self.output_signal.emit(f"Error: Unknown API type '{self.settings['api']}'")
            return ""

    def _get_claude_commentary(self, race_events):
        if not self.client:
            self.output_signal.emit("Error: Claude client not initialized.")
            return ""
        try:
            response = self.client.messages.create(
                model=self.settings["model"],
                max_tokens=8000,
                temperature=0.99,
                system=self.system_prompt, # Use the loaded system prompt
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
            if hasattr(response, 'content') and isinstance(response.content, list) and response.content:
                content = response.content[0].text
            elif hasattr(response, 'content'): # Handle non-list content attribute if applicable
                content = response.content
            else: # Fallback if content structure is unexpected
                content = str(response)

            return str(content) if content is not None else ""

        except Exception as e:
            self.output_signal.emit(f"Error in Claude commentary generation: {str(e)}")
            return ""

    def _get_openai_commentary(self, race_events):
        if not self.client:
            self.output_signal.emit("Error: OpenAI client not initialized.")
            return ""
        try:
            messages = []

            # Prepare messages based on model type
            if self.settings["model"].startswith(("o-", "o1-")):
                 messages.append({
                    "role": "user",
                     # Combine system prompt and user content for 'O' models
                    "content": f"{self.system_prompt}\n\nHere's the complete race event log:\n\n{race_events}\n\nPlease provide commentary for each event, maintaining the original timecodes."
                })
            else:
                 # Standard OpenAI model message structure
                messages.extend([
                    {
                        "role": "system",
                        "content": self.system_prompt # Use the loaded system prompt
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

            # Add parameters only for non-'O' models if needed
            if not self.settings["model"].startswith(("o-", "o1-")):
                kwargs.update({
                    "temperature": 0.99,
                    "max_tokens": 8000
                })

            response = self.client.chat.completions.create(**kwargs)

            # Handle OpenAI's response format
            if response.choices and hasattr(response.choices[0].message, 'content'):
                content = response.choices[0].message.content
            else: # Fallback if structure is unexpected
                content = str(response.choices[0].message) if response.choices else ""


            return str(content) if content is not None else ""

        except Exception as e:
            self.output_signal.emit(f"Error in OpenAI commentary generation: {str(e)}")
            return ""

    # --- Add Gemini Commentary Function ---
    def _get_gemini_commentary(self, race_events):
        """Generates race commentary using the Google Gemini API."""
        try:
            api_key = self.settings.get("google_key")
            if not api_key:
                self.output_signal.emit("Error: Google API Key not found in settings.")
                return ""

            # Configure the Gemini client
            genai.configure(api_key=api_key)

            # Instantiate the model
            model = genai.GenerativeModel(self.settings["model"])

            # Combine system prompt and race events into a single prompt
            full_prompt = (
                f"{self.system_prompt}\n\n"
                f"Here's the complete race event log:\n\n{race_events}\n\n"
                "Please provide commentary for each event, maintaining the original timecodes."
            )

             # Add safety settings to potentially reduce refusals
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]

            # Generate content
            response = model.generate_content(full_prompt, safety_settings=safety_settings)


            # Extract the text, checking for blocks
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
            self.output_signal.emit(f"Error in Gemini commentary generation: {str(e)}")
            return ""
    # ------------------------------------

    def create_output_file(self):
        """Create the output file path for the commentary."""
        try:
             # Ensure input path exists
             if not self.input_path or not os.path.exists(self.input_path):
                 self.output_signal.emit(f"Error: Input file path '{self.input_path}' does not exist.")
                 return None

             base_name = os.path.basename(self.input_path)
             file_name, file_extension = os.path.splitext(base_name)
             # Handle cases where input might not have an extension
             if not file_extension:
                 file_extension = ".txt" # Default to .txt

             new_file_name = f"{file_name}_commentary{file_extension}"

             original_dir = os.path.dirname(self.input_path)
             # Ensure original_dir is valid
             if not original_dir or not os.path.isdir(original_dir):
                  original_dir = os.getcwd() # Fallback
                  self.output_signal.emit(f"Warning: Could not determine input directory, saving commentary file to current directory: {original_dir}")

             return os.path.join(original_dir, new_file_name)
        except Exception as e:
             self.output_signal.emit(f"Error creating output file path: {str(e)}")
             return None


    def write_commentary(self, commentary):
        """Write the commentary to the output file and emit progress signals."""
        if not self.output_path:
             self.output_signal.emit("Error: Output path is not set, cannot write commentary.")
             return
        # Ensure commentary is a string and properly encoded
        if not isinstance(commentary, str):
            commentary = str(commentary)

        try:
            # Write the file
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(commentary)

            # Emit progress updates based on lines written (optional refinement)
            lines = commentary.split('\n')
            total_lines = len(lines) if lines else 1 # Avoid division by zero
            # Basic progress emit after writing is complete
            self.progress_signal.emit(90) # Indicate writing is nearly done
            # for i, line in enumerate(lines):
            #     # self.output_signal.emit(line) # Avoid emitting every line to UI
            #     progress = int(((i + 1) / total_lines) * 100)
            #     # Emit progress less frequently if needed
            #     if i % 10 == 0 or i == total_lines - 1:
            #          self.progress_signal.emit(progress)

        except Exception as e:
             self.output_signal.emit(f"Error writing commentary to {self.output_path}: {str(e)}")


    def get_output_path(self):
        """Get the path to the output file."""
        return self.output_path