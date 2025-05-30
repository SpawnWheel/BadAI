# second_pass_commentator.py
from PyQt5.QtCore import QThread, pyqtSignal
import anthropic
from openai import OpenAI
import os
import re
import traceback # Import traceback
# --- Add Google Gemini import ---
import google.generativeai as genai
# ------------------------------


class SecondPassCommentator(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, input_path, settings):
        super().__init__()
        self.input_path = input_path
        self.output_path = None
        # Ensure settings is a dictionary, even if None is passed
        self.settings = settings if isinstance(settings, dict) else {}
        self.client = None # Initialize client to None

        # Initialize appropriate client based on settings
        api_type = self.settings.get("api") # Get API type
        # Use print initially as signals might not be connected yet
        print(f"[SecondPass Init] Using API type: {api_type}")

        try:
            if api_type == "claude":
                claude_key = self.settings.get("claude_key")
                if claude_key:
                    self.client = anthropic.Anthropic(api_key=claude_key)
                    print("[SecondPass Init] Claude client initialized.")
                else:
                    print("Error [SecondPass Init]: Claude API Key missing in settings.")
            elif api_type == "openai":
                openai_key = self.settings.get("openai_key")
                if openai_key:
                    self.client = OpenAI(api_key=openai_key)
                    print("[SecondPass Init] OpenAI client initialized.")
                else:
                    print("Error [SecondPass Init]: OpenAI API Key missing in settings.")
            elif api_type == "gemini":
                google_key = self.settings.get("google_key")
                if not google_key:
                    print("Error [SecondPass Init]: Google API Key missing in settings for Gemini.")
                else:
                    try:
                         genai.configure(api_key=google_key)
                         print("[SecondPass Init] Gemini API key seems valid (configuration successful).")
                    except Exception as gemini_init_e:
                         print(f"Error [SecondPass Init]: Failed to configure Gemini API: {gemini_init_e}")
            else:
                print(f"Warning [SecondPass Init]: Unknown API type '{api_type}'. No client initialized.")

        except Exception as client_init_e:
             print(f"Error [SecondPass Init]: Failed during API client initialization: {client_init_e}")
             self.client = None

        # --- Load Prompt ---
        self.prompt = self.settings.get('second_pass_prompt')
        prompt_source = "settings"
        if not self.prompt:
             self.prompt = self.load_prompt_from_file("second_commentator.txt")
             prompt_source = "file"
        if not self.prompt:
             prompt_source = "fallback"
             print("Error [SecondPass Init]: Could not load prompt from settings or file. Using basic fallback.")
             self.prompt = ("You are a secondary commentator filling in gaps in the primary commentary. "
                            "Analyze the provided script which contains existing commentary lines and placeholders "
                            "like '<COMMENTATE HERE IN X WORDS>'. Replace the placeholders with relevant, concise "
                            "commentary fitting the time gap and word count indicated. Maintain the original timecodes. "
                            "ONLY output the filled script lines, do not add any explanation.")
        print(f"[SecondPass Init] Loaded prompt from: {prompt_source}")
        # --------------------


    def run(self):
        # Ensure signals can be emitted now that thread has started
        self.output_signal.emit("Starting second pass commentary TEXT generation...")
        self.progress_signal.emit(0)

        try:
            # --- Pre-checks ---
            api_type = self.settings.get("api")
            if api_type == "claude" and not self.client: raise Exception("Claude client not initialized.")
            if api_type == "openai" and not self.client: raise Exception("OpenAI client not initialized.")
            if api_type == "gemini" and not self.settings.get("google_key"): raise Exception("Google API key missing for Gemini.")
            if not self.prompt: raise Exception("Second pass prompt is missing.")
            # ----------------

            self.output_signal.emit(f"[SecondPass Run] Reading input file: {self.input_path}")
            race_data = self.read_input_file()
            self.progress_signal.emit(25)

            self.output_signal.emit(f"[SecondPass Run] Generating commentary using API: {api_type}")
            commentary = self.generate_commentary(race_data)

            # --- Check AI Response ---
            if commentary is None or commentary == "" or "Blocked by API" in commentary:
                 self.output_signal.emit(f"Error [SecondPass Run]: AI commentary generation failed or returned empty/blocked. Response: '{commentary}'. Aborting save.")
                 self.progress_signal.emit(100)
                 return
            self.output_signal.emit("[SecondPass Run] AI commentary generated successfully (content received).")
            # -----------------------

            self.progress_signal.emit(75)

            # --- Save the processed commentary ---
            self.output_signal.emit("[SecondPass Run] Attempting to save filled commentary...")
            self.save_commentary(commentary)
            # -----------------------------------

            self.progress_signal.emit(100)

            # --- Final Status Log ---
            if self.output_path and os.path.exists(self.output_path):
                self.output_signal.emit(f"[SecondPass Run] Completed. Output saved to: {self.output_path}")
            else:
                 self.output_signal.emit(f"[SecondPass Run] Completed, but saving appears to have failed. Expected output path was: {getattr(self, '_intended_output_path', self.output_path)}") # Log intended path if save failed

        except Exception as e:
            self.output_signal.emit(f"Error in second pass commentary thread: {str(e)}")
            self.output_signal.emit(traceback.format_exc())
            self.progress_signal.emit(0)


    def read_input_file(self):
        """Reads the content of the input file (_second_commentator.txt)."""
        if not self.input_path or not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Input file for second pass not found: {self.input_path}")
        try:
            with open(self.input_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                if not content.strip():
                     self.output_signal.emit(f"Warning [SecondPass Read]: Input file '{self.input_path}' is empty.")
                return content
        except Exception as e:
            self.output_signal.emit(f"Error [SecondPass Read]: Reading input file {self.input_path}: {str(e)}")
            raise


    def load_prompt_from_file(self, filename):
        """Loads prompt content from a file (fallback mechanism)."""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_path = os.path.join(script_dir, filename)
            if not os.path.exists(prompt_path):
                 prompt_path = os.path.join(os.path.dirname(script_dir), filename) # Check parent dir

            if not os.path.exists(prompt_path):
                 self.output_signal.emit(f"Warning [SecondPass Prompt]: Prompt file '{filename}' not found in standard locations.")
                 return None

            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.output_signal.emit(f"Error [SecondPass Prompt]: Loading prompt file '{filename}': {e}")
            return None


    def generate_commentary(self, race_data):
        """Calls the appropriate AI generation method based on settings."""
        api_type = self.settings.get("api")
        self.output_signal.emit(f"[SecondPass Generate] Calling API: {api_type}, Model: {self.settings.get('model')}")
        if api_type == "claude":
            return self._generate_with_claude(race_data)
        elif api_type == "openai":
            return self._generate_with_openai(race_data)
        elif api_type == "gemini":
            return self._generate_with_gemini(race_data)
        else:
            self.output_signal.emit(f"Error [SecondPass Generate]: Unknown API type '{api_type}'.")
            return ""


    def _generate_with_claude(self, race_data):
        """Generates filled commentary using Claude."""
        if not self.client: self.output_signal.emit("Error [SecondPass Claude]: Client not initialized."); return ""
        if not self.prompt: self.output_signal.emit("Error [SecondPass Claude]: Prompt not loaded."); return ""
        try:
            self.output_signal.emit("[SecondPass Claude] Sending request...")
            response = self.client.messages.create(
                model=self.settings.get("model", "claude-3-haiku-20240307"),
                max_tokens=8000, temperature=0.7, system=self.prompt,
                messages=[{"role": "user", "content": f"Here is the commentary script with placeholders to fill:\n\n<script>\n{race_data}\n</script>\n\nFill the placeholders according to the instructions in the system prompt, providing only the completed script."}]
            )
            content = response.content[0].text if isinstance(response.content, list) and response.content else ""
            if not content: self.output_signal.emit("Warning [SecondPass Claude]: Received empty content.")
            else: self.output_signal.emit("[SecondPass Claude] Received non-empty response.")
            return content.strip()
        except Exception as e:
            self.output_signal.emit(f"Error [SecondPass Claude]: {str(e)}")
            self.output_signal.emit(traceback.format_exc())
            return ""


    def _generate_with_openai(self, race_data):
        """Generates filled commentary using OpenAI."""
        if not self.client: self.output_signal.emit("Error [SecondPass OpenAI]: Client not initialized."); return ""
        if not self.prompt: self.output_signal.emit("Error [SecondPass OpenAI]: Prompt not loaded."); return ""
        try:
            self.output_signal.emit("[SecondPass OpenAI] Sending request...")
            messages = [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": f"Here is the commentary script with placeholders to fill:\n\n<script>\n{race_data}\n</script>\n\nFill the placeholders according to the instructions in the system prompt, providing only the completed script."}
            ]
            kwargs = {"model": self.settings.get("model", "gpt-4o-mini"), "messages": messages, "temperature": 0.7, "max_tokens": 4090}
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content if response.choices and response.choices[0].message else ""
            if not content: self.output_signal.emit("Warning [SecondPass OpenAI]: Received empty content.")
            else: self.output_signal.emit("[SecondPass OpenAI] Received non-empty response.")
            return content.strip()
        except Exception as e:
            self.output_signal.emit(f"Error [SecondPass OpenAI]: {str(e)}")
            self.output_signal.emit(traceback.format_exc())
            return ""


    def _generate_with_gemini(self, race_data):
        """Generates second pass commentary using the Google Gemini API."""
        api_key = self.settings.get("google_key")
        if not api_key: self.output_signal.emit("Error [SecondPass Gemini]: Google API Key missing."); return ""
        if not self.prompt: self.output_signal.emit("Error [SecondPass Gemini]: Prompt not loaded."); return ""
        try:
            self.output_signal.emit("[SecondPass Gemini] Configuring client...")
            genai.configure(api_key=api_key)
            model_name = self.settings.get("model", "gemini-1.5-flash-latest")
            model = genai.GenerativeModel(model_name)
            self.output_signal.emit(f"[SecondPass Gemini] Sending request to model: {model_name}...")

            full_prompt = (f"{self.prompt}\n\nHere is the commentary script...\n<script>\n{race_data}\n</script>\n\nFill placeholders...")
            safety_settings = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
            generation_config = genai.types.GenerationConfig(temperature=0.7)

            response = model.generate_content(full_prompt, generation_config=generation_config, safety_settings=safety_settings)

            response_text = ""
            try:
                 if response.parts: response_text = response.text.strip()
                 if response.prompt_feedback and response.prompt_feedback.block_reason:
                     block_reason = response.prompt_feedback.block_reason
                     self.output_signal.emit(f"Warning [SecondPass Gemini]: Response BLOCKED. Reason: {block_reason}")
                     return f"Blocked by API: {block_reason}"
                 elif not response_text and hasattr(response, 'text'):
                      try: response_text = response.text.strip()
                      except ValueError: response_text = ""
                 if not response_text:
                     self.output_signal.emit("Warning [SecondPass Gemini]: Received empty content.")
                     try: self.output_signal.emit(f"[SecondPass Gemini] Full Response Object (for debug): {response}")
                     except: pass
                 else:
                      self.output_signal.emit("[SecondPass Gemini] Received non-empty response.")

            except ValueError as ve:
                 self.output_signal.emit(f"Warning [SecondPass Gemini]: Error accessing response text: {ve}")
                 if response.prompt_feedback and response.prompt_feedback.block_reason:
                      block_reason = response.prompt_feedback.block_reason
                      self.output_signal.emit(f"Warning [SecondPass Gemini]: Response BLOCKED (detected during text access error). Reason: {block_reason}")
                      return f"Blocked by API: {block_reason}"
                 response_text = ""
            except Exception as resp_err:
                 self.output_signal.emit(f"Error [SecondPass Gemini]: Unexpected error accessing response content: {resp_err}")
                 response_text = ""

            return response_text

        except Exception as e:
            self.output_signal.emit(f"Error [SecondPass Gemini]: {str(e)}")
            self.output_signal.emit(traceback.format_exc())
            return ""


    def save_commentary(self, commentary):
        """Saves the generated commentary, filtering out placeholders and non-script lines."""
        self.output_path = None # Reset path initially
        self._intended_output_path = None # Store the path we intend to write to

        if not self.input_path or not os.path.exists(self.input_path):
             self.output_signal.emit(f"Error [SecondPass Save]: Input file path '{self.input_path}' is invalid or does not exist.")
             return

        try:
             base_name = os.path.basename(self.input_path)
             file_name_match = re.match(r"^(.*?)_second_commentator$", os.path.splitext(base_name)[0])
             if file_name_match: file_name_base = file_name_match.group(1)
             else: file_name_base = os.path.splitext(base_name)[0]; self.output_signal.emit(f"Warning [SecondPass Save]: Input filename '{base_name}' did not match '*_second_commentator.txt'. Using base '{file_name_base}'.")

             new_file_name = f"{file_name_base}_filled.txt"
             original_dir = os.path.dirname(self.input_path)
             if not original_dir or not os.path.isdir(original_dir): original_dir = os.getcwd(); self.output_signal.emit(f"Warning [SecondPass Save]: Could not determine input directory, saving to current: {original_dir}")

             self._intended_output_path = os.path.join(original_dir, new_file_name) # Store intended path

             # --- Filtering Logic ---
             formatted_lines = []
             raw_ai_lines = commentary.split('\n') if isinstance(commentary, str) else [str(commentary)]
             script_started, placeholders_found, non_timecoded_discarded, preamble_discarded = False, 0, 0, 0

             for line in raw_ai_lines:
                 stripped_line = line.strip()
                 if not stripped_line: continue
                 is_script_line = re.match(r'\d{2}:\d{2}:\d{2}\s*-\s*', stripped_line)
                 if is_script_line:
                     script_started = True
                     if "<COMMENTATE HERE" in stripped_line: placeholders_found += 1; continue
                     formatted_lines.append(stripped_line)
                 elif script_started: non_timecoded_discarded += 1
                 else: preamble_discarded += 1

             # --- Log Filtering Results ---
             self.output_signal.emit(f"[SecondPass Save] Filtering complete: {len(formatted_lines)} valid lines found.")
             if placeholders_found > 0: self.output_signal.emit(f"  - Placeholders skipped (AI failed): {placeholders_found}")
             # Optionally log discarded lines if needed for debugging
             # if non_timecoded_discarded > 0: self.output_signal.emit(f"  - Post-script non-timecoded lines discarded: {non_timecoded_discarded}")
             # if preamble_discarded > 0: self.output_signal.emit(f"  - Preamble lines discarded: {preamble_discarded}")
             # ---------------------------

             if not formatted_lines:
                  self.output_signal.emit("Error [SecondPass Save]: No valid commentary lines remain after filtering AI response. Saving failed.")
                  raw_output_path = self._intended_output_path + ".raw_error"
                  try:
                      with open(raw_output_path, 'w', encoding='utf-8') as f_raw: f_raw.write(str(commentary))
                      self.output_signal.emit(f"[SecondPass Save] Saved raw AI output for debugging to: {raw_output_path}")
                  except Exception as raw_e: self.output_signal.emit(f"[SecondPass Save] Failed to save raw error output: {raw_e}")
                  return # Do not set self.output_path

             # --- Save the filtered lines ---
             with open(self._intended_output_path, 'w', encoding='utf-8') as f:
                 f.write('\n'.join(formatted_lines))
             self.output_signal.emit(f"[SecondPass Save] Successfully saved filtered commentary to {self._intended_output_path}")
             self.output_path = self._intended_output_path # Set official path ONLY on success

        except Exception as e:
             self.output_signal.emit(f"Error [SecondPass Save]: Failed during saving commentary to {getattr(self, '_intended_output_path', 'intended path')}: {str(e)}")
             self.output_signal.emit(traceback.format_exc())
             self.output_path = None


    def get_output_path(self):
        """Returns the path to the saved output file (_filled.txt), or None if saving failed."""
        # Check if the path was set *and* the file actually exists
        if self.output_path and os.path.exists(self.output_path):
            return self.output_path
        else:
            if self.output_path and not os.path.exists(self.output_path):
                 self.output_signal.emit(f"Warning [SecondPass get_output_path]: Output path '{self.output_path}' was set, but file does not exist.")
            elif not self.output_path and hasattr(self, '_intended_output_path'):
                 # Log if path was never set, likely due to save failure
                 self.output_signal.emit(f"Debug [SecondPass get_output_path]: Output path was not set (intended: '{self._intended_output_path}'). Saving likely failed.")
            return None