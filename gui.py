# gui.py (updated)

import tkinter as tk
from tkinter import scrolledtext, ttk
import threading
import os
import config
from recorder import Recorder
from transcriber import Transcriber

class VoiceToVibeApp:
    def __init__(self, root):
        self.root = root
        self.recorder = Recorder()
        self.transcriber = Transcriber()
        self.input_devices = []
        self.setup_ui()
        self.refresh_devices()

    def setup_ui(self):
        self.root.title("voiceToVibe")
        self.root.geometry("550x480")
        self.root.configure(bg="#2b2b2b")

        # === Device selector frame ===
        device_frame = tk.Frame(self.root, bg="#2b2b2b")
        device_frame.pack(pady=(15, 5), padx=15, fill=tk.X)

        device_label = tk.Label(
            device_frame,
            text="Input:",
            bg="#2b2b2b",
            fg="#aaaaaa",
            font=("Segoe UI", 10)
        )
        device_label.pack(side=tk.LEFT)

        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(
            device_frame,
            textvariable=self.device_var,
            state="readonly",
            width=45,
            font=("Segoe UI", 9)
        )
        self.device_combo.pack(side=tk.LEFT, padx=(10, 5))
        self.device_combo.bind("<<ComboboxSelected>>", self.on_device_change)

        self.btn_refresh = tk.Button(
            device_frame,
            text="↻",
            command=self.refresh_devices,
            width=3,
            bg="#3a3a3a",
            fg="white",
            font=("Segoe UI", 10)
        )
        self.btn_refresh.pack(side=tk.LEFT)

        # === Button frame ===
        btn_frame = tk.Frame(self.root, bg="#2b2b2b")
        btn_frame.pack(pady=15)

        self.btn_record = tk.Button(
            btn_frame,
            text="🎤 Record",
            command=self.on_record,
            width=15,
            height=2,
            bg="#4a9f4a",
            fg="white",
            font=("Segoe UI", 11)
        )
        self.btn_record.pack(side=tk.LEFT, padx=10)

        self.btn_stop = tk.Button(
            btn_frame,
            text="⏹ Stop & Transcribe",
            command=self.on_stop,
            width=18,
            height=2,
            bg="#cf6a4c",
            fg="white",
            font=("Segoe UI", 11),
            state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=10)

        # === Status label ===
        self.status_var = tk.StringVar(value="Idle")
        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            bg="#2b2b2b",
            fg="#aaaaaa",
            font=("Segoe UI", 10)
        )
        self.status_label.pack(pady=5)

        # === Text output ===
        self.text_output = scrolledtext.ScrolledText(
            self.root,
            wrap=tk.WORD,
            width=60,
            height=12,
            font=("Consolas", 11),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white"
        )
        self.text_output.pack(padx=15, pady=10)

        # === Copy button ===
        self.btn_copy = tk.Button(
            self.root,
            text="📋 Copy to Clipboard",
            command=self.on_copy,
            width=20,
            bg="#3a3a3a",
            fg="white",
            font=("Segoe UI", 10)
        )
        self.btn_copy.pack(pady=5)

        # === File path label ===
        self.path_label = tk.Label(
            self.root,
            text=f"Saves to: {config.OUTPUT_DIR}/{config.LATEST_FILE}",
            bg="#2b2b2b",
            fg="#666666",
            font=("Segoe UI", 9)
        )
        self.path_label.pack(pady=5)

    def refresh_devices(self):
        """Refresh the list of input devices."""
        self.input_devices = Recorder.get_input_devices()

        # Build display list with "Default" option first
        display_names = ["(System Default)"]
        display_names += [name for _, name in self.input_devices]

        self.device_combo['values'] = display_names
        self.device_combo.current(0)  # Select default
        self.recorder.set_device(None)

    def on_device_change(self, event=None):
        """Handle device selection change."""
        idx = self.device_combo.current()
        if idx == 0:
            # System default
            self.recorder.set_device(None)
        else:
            # Specific device (idx-1 because of "Default" offset)
            device_id, device_name = self.input_devices[idx - 1]
            self.recorder.set_device(device_id)

    def on_record(self):
        self.btn_record.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.device_combo.config(state=tk.DISABLED)  # Lock during recording
        self.status_var.set("🔴 Recording...")
        self.text_output.delete(1.0, tk.END)
        self.recorder.start()

    def on_stop(self):
        self.btn_stop.config(state=tk.DISABLED)
        self.status_var.set("Saving audio...")

        wav_path = self.recorder.stop()

        if wav_path is None:
            self.status_var.set("No audio recorded")
            self.btn_record.config(state=tk.NORMAL)
            self.device_combo.config(state="readonly")
            return

        self.status_var.set("Transcribing... (loading model if first run)")

        thread = threading.Thread(target=self._transcribe_thread, args=(wav_path,))
        thread.daemon = True
        thread.start()

    def _transcribe_thread(self, wav_path):
        try:
            text = self.transcriber.transcribe(wav_path)
            self.root.after(0, lambda: self._on_transcription_done(text))
        except Exception as e:
            self.root.after(0, lambda: self._on_transcription_error(str(e)))

    def _on_transcription_done(self, text):
        self.text_output.delete(1.0, tk.END)
        self.text_output.insert(1.0, text)

        self.root.clipboard_clear()
        self.root.clipboard_append(text)

        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(config.OUTPUT_DIR, config.LATEST_FILE)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)

        self.status_var.set("✓ Done - copied to clipboard")
        self.btn_record.config(state=tk.NORMAL)
        self.device_combo.config(state="readonly")  # Unlock

    def _on_transcription_error(self, error_msg):
        self.text_output.delete(1.0, tk.END)
        self.text_output.insert(1.0, f"Error: {error_msg}")
        self.status_var.set("Error during transcription")
        self.btn_record.config(state=tk.NORMAL)
        self.device_combo.config(state="readonly")

    def on_copy(self):
        text = self.text_output.get(1.0, tk.END).strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status_var.set("📋 Copied!")
            self.root.after(2000, lambda: self.status_var.set("Idle"))