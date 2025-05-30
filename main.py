# main.py
import sys
import os # Added for path joining
import time # Keep for potential fallback, but QTimer is preferred
from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtGui import QPixmap       # Added for image loading
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer # Added for splash timing and control
from main_window import MainWindow # MainWindow now holds VERSION

# --- Splash Screen Minimum Display Time (milliseconds) ---
MIN_SPLASH_TIME_MS = 3000 # 3 seconds

def main():
    app = QApplication(sys.argv)

    # --- Splash Screen Setup ---
    splash = None
    script_dir = os.path.dirname(__file__) # Get the directory where main.py is located
    image_path = os.path.join(script_dir, "Graphics", "Welcome.png")

    if not os.path.exists(image_path):
        print(f"Warning: Splash screen image not found at '{image_path}'. Skipping splash.")
    else:
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            print(f"Warning: Failed to load splash screen image from '{image_path}'. Skipping splash.")
        else:
            splash = QSplashScreen(pixmap)
            splash.showMessage("Loading Bad AI Commentary...", Qt.AlignBottom | Qt.AlignHCenter, Qt.white)
            splash.show()
            app.processEvents() # Ensure the splash screen is displayed immediately

    # --- Timer for Minimum Splash Duration ---
    start_time = QElapsedTimer()
    start_time.start()

    # --- Create Main Window (this might take time) ---
    window = MainWindow()

    # --- Calculate remaining time and show window ---
    elapsed = start_time.elapsed()
    remaining_time = MIN_SPLASH_TIME_MS - elapsed

    def show_main_window():
        if splash:
            splash.finish(window)
        window.show()

    if splash and remaining_time > 0:
        # If splash exists and minimum time hasn't passed, wait
        QTimer.singleShot(remaining_time, show_main_window)
    else:
        # If no splash or minimum time already passed, show immediately
        show_main_window()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()