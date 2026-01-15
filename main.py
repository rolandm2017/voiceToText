# main.py

import tkinter as tk
import os
import config

def main():
    # Ensure directories exist
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TEMP_DIR, exist_ok=True)

    # Import here to delay whisperx import until needed
    from gui import VoiceToVibeApp

    root = tk.Tk()
    app = VoiceToVibeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()