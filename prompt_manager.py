# prompt_manager.py
import os
import shutil
from typing import List, Optional

class PromptManager:
    def __init__(self, prompt_type: str):
        """
        Initializes the PromptManager for a specific type (e.g., 'DataFilterer').

        Args:
            prompt_type: A string identifying the type of prompts (used for subdirectory).
        """
        self.base_dir = "Prompts"
        self.prompt_type_dir = os.path.join(self.base_dir, prompt_type)
        self._ensure_directories()

    def _ensure_directories(self):
        """Create the base and type-specific prompt directories if they don't exist."""
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.prompt_type_dir, exist_ok=True)

    def _get_prompt_path(self, name: str) -> str:
        """Construct the full path for a given prompt name."""
        # Basic sanitization: replace potentially problematic characters for filenames
        # For simplicity, we'll just replace spaces, but more robust sanitization might be needed.
        # Alternatively, allow spaces but handle potential OS issues. Let's keep it simple for now.
        filename = f"{name}.txt"
        return os.path.join(self.prompt_type_dir, filename)

    def list_prompts(self) -> List[str]:
        """Returns a list of available prompt names."""
        prompts = []
        try:
            for filename in os.listdir(self.prompt_type_dir):
                if filename.endswith(".txt"):
                    # Extract name from filename (remove .txt)
                    prompt_name = os.path.splitext(filename)[0]
                    prompts.append(prompt_name)
        except FileNotFoundError:
            pass # Directory might not exist yet, which is handled by _ensure_directories
        except Exception as e:
            print(f"Error listing prompts: {e}")
        return sorted(prompts)

    def load_prompt(self, name: str) -> Optional[str]:
        """Loads the content of a specific prompt."""
        prompt_path = self._get_prompt_path(name)
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Prompt file not found: {prompt_path}")
            return None
        except Exception as e:
            print(f"Error loading prompt '{name}': {e}")
            return None

    def save_prompt(self, name: str, content: str, original_name: Optional[str] = None) -> bool:
        """
        Saves a prompt. If original_name is provided and differs from name,
        it handles renaming (deletes old file).

        Args:
            name: The new name for the prompt.
            content: The content of the prompt.
            original_name: The original name if editing/renaming.

        Returns:
            True if successful, False otherwise.
        """
        if not name or not name.strip():
            print("Error: Prompt name cannot be empty.")
            return False

        new_path = self._get_prompt_path(name)

        # Handle renaming: Delete the old file if names differ
        if original_name and original_name != name:
            old_path = self._get_prompt_path(original_name)
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception as e:
                    print(f"Warning: Could not remove old prompt file '{old_path}': {e}")
            # Check if a file with the new name already exists (after potentially deleting old one)
            if os.path.exists(new_path):
                 print(f"Error: A prompt with the name '{name}' already exists.")
                 # Recreate the old file? Or just fail? Let's fail for now.
                 # If we were more robust, we'd handle this better, maybe confirm overwrite.
                 return False

        elif os.path.exists(new_path) and name == original_name:
             pass # Overwriting the same file is expected during edit without rename
        elif os.path.exists(new_path) and original_name is None:
             print(f"Error: A prompt with the name '{name}' already exists.")
             return False # Prevent overwrite on initial creation if name exists


        try:
            with open(new_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error saving prompt '{name}': {e}")
            return False

    def delete_prompt(self, name: str) -> bool:
        """Deletes a specific prompt file."""
        prompt_path = self._get_prompt_path(name)
        try:
            if os.path.exists(prompt_path):
                os.remove(prompt_path)
                return True
            else:
                print(f"Prompt file not found for deletion: {prompt_path}")
                return False
        except Exception as e:
            print(f"Error deleting prompt '{name}': {e}")
            return False

    def ensure_default_prompt(self, default_name: str, default_content_path: str):
        """
        Checks if the prompt directory is empty. If so, copies the default
        prompt content file to the directory with the default_name.
        """
        if not self.list_prompts(): # Check if directory is empty
            if os.path.exists(default_content_path):
                try:
                    default_target_path = self._get_prompt_path(default_name)
                    shutil.copyfile(default_content_path, default_target_path)
                    print(f"Default prompt '{default_name}' created from '{default_content_path}'.")
                except Exception as e:
                    print(f"Error creating default prompt '{default_name}': {e}")
            else:
                print(f"Warning: Default prompt content file '{default_content_path}' not found.")