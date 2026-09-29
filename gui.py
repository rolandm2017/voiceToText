"""Tkinter GUI. All app state lives here, mutated only on the GUI thread.

Worker threads (audio, transcriber) communicate exclusively by putting event
tuples on self.events; _poll() drains it every 40 ms. Each recording gets a
session id so results from a cancelled recording are ignored if they arrive
late.
"""

import datetime
import os
import queue
import subprocess
import sys
import tkinter as tk
from tkinter import scrolledtext, ttk

import pyperclip

import audio
import config
from transcriber import Transcriber

_TEXT_FONT = ("Helvetica Neue", 14) if sys.platform == "darwin" else ("Segoe UI", 11)

# app states
LOADING, READY, RECORDING, FINALIZING = "loading", "ready", "recording", "finalizing"


class VoiceToTextApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.events: queue.Queue = queue.Queue()
        self.state = LOADING
        self.session = 0          # bumped on every Record/Cancel; stale results ignored
        self.pending = 0          # segments emitted but not yet transcribed
        self.model_desc = ""

        self._build_ui()
        self.engine = audio.AudioEngine(config.VAD_MODEL_PATH)
        self.transcriber = Transcriber(self.events.put)
        self._set_status("Loading model… (first ever run also downloads it)")
        self.root.after(40, self._poll)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        self.root.title("voiceToText")
        self.root.minsize(520, 360)

        top = ttk.Frame(self.root, padding=(10, 8, 10, 0))
        top.pack(fill="x")
        ttk.Label(top, text="Mic:").pack(side="left")
        self.device_var = tk.StringVar()
        self.device_box = ttk.Combobox(top, textvariable=self.device_var, state="readonly")
        self.device_box.pack(side="left", fill="x", expand=True, padx=(4, 2))
        self.refresh_btn = ttk.Button(top, text="↻", width=3, command=self._refresh_devices)
        self.refresh_btn.pack(side="left")
        self.topmost_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            top, text="📌 On top", variable=self.topmost_var,
            command=lambda: self.root.attributes("-topmost", self.topmost_var.get()),
        ).pack(side="left", padx=(8, 0))

        mid = ttk.Frame(self.root, padding=(10, 8))
        mid.pack(fill="x")
        self.record_btn = ttk.Button(mid, text="🎤 Record", command=self._on_record_done,
                                     state="disabled")
        self.record_btn.pack(side="left")
        self.cancel_btn = ttk.Button(mid, text="✕ Cancel", command=self._on_cancel,
                                     state="disabled")
        self.cancel_btn.pack(side="left", padx=(6, 6))
        ttk.Button(mid, text="¶ Paragraph (Ctrl+Enter)",
                   command=self._insert_paragraph).pack(side="left", padx=(0, 12))
        self.level = tk.Canvas(mid, width=140, height=14, highlightthickness=1,
                               highlightbackground="#999")
        self.level.pack(side="left", fill="x", expand=True)
        self._level_bar = self.level.create_rectangle(0, 0, 0, 14, fill="#bbb", width=0)

        self.status_var = tk.StringVar()
        ttk.Label(self.root, textvariable=self.status_var, padding=(10, 0)).pack(fill="x")

        self.text = scrolledtext.ScrolledText(self.root, wrap="word", height=10,
                                              font=_TEXT_FONT, undo=True)
        self.text.pack(fill="both", expand=True, padx=10, pady=8)

        bottom = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        bottom.pack(fill="x")
        self.autocopy_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bottom, text="Autocopy to clipboard",
                        variable=self.autocopy_var).pack(side="left")
        ttk.Button(bottom, text="📋 Copy", command=self._copy).pack(side="right")
        ttk.Button(bottom, text="📁 Open folder", command=self._open_folder).pack(
            side="right", padx=(0, 6))

        self.root.bind("<Control-Shift-D>", lambda e: self._on_cancel())
        self.root.bind("<Control-Shift-d>", lambda e: self._on_cancel())
        self.root.bind("<Control-Return>", self._insert_paragraph)
        if sys.platform == "darwin":  # Mac users reach for Cmd, not Ctrl
            self.root.bind("<Command-Shift-D>", lambda e: self._on_cancel())
            self.root.bind("<Command-Shift-d>", lambda e: self._on_cancel())
            self.root.bind("<Command-Return>", self._insert_paragraph)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_devices()

    def _on_close(self):
        if self.state in (RECORDING, FINALIZING):
            self.engine.stop(flush=False)
        self.root.destroy()

    def _refresh_devices(self):
        try:
            audio.refresh_devices()
        except Exception:
            pass
        self.devices = audio.list_input_devices()
        self.device_box["values"] = [name for _idx, name in self.devices]
        if not self.device_var.get() or self.device_var.get() not in self.device_box["values"]:
            self.device_box.current(0)

    def _selected_device(self):
        i = self.device_box.current()
        return self.devices[i][0] if 0 <= i < len(self.devices) else None

    def _set_status(self, msg: str):
        self.status_var.set(msg)

    def _set_level(self, rms: float, is_speech: bool):
        width = self.level.winfo_width() or 140
        frac = min(1.0, rms * 8.0)
        self.level.coords(self._level_bar, 0, 0, int(width * frac), 14)
        self.level.itemconfig(self._level_bar, fill="#3c3" if is_speech else "#bbb")

    # ----------------------------------------------------------- actions

    def _on_record_done(self):
        if self.state == READY:
            self.session += 1
            self.pending = 0
            self.text.delete("1.0", "end")
            try:
                self.engine.start(self._selected_device(), self.events.put)
            except Exception as e:
                self._set_status(f"Mic error: {e}")
                return
            self.state = RECORDING
            self.record_btn.config(text="⏹ Done")
            self.cancel_btn.config(state="normal")
            self.device_box.config(state="disabled")
            self.refresh_btn.config(state="disabled")
            self._set_status("Recording — pause briefly and text will appear")
        elif self.state == RECORDING:
            self.engine.stop(flush=True)   # blocks until the final segment event is queued
            self.state = FINALIZING
            self.record_btn.config(state="disabled")
            self.cancel_btn.config(state="disabled")
            self._drain_events()           # pick up that final segment now
            if self.pending == 0:
                self._finalize()
            else:
                self._set_status("Finishing transcription…")

    def _on_cancel(self, *_):
        if self.state not in (RECORDING, FINALIZING):
            return
        self.engine.stop(flush=False)
        self.session += 1                  # orphan any in-flight results
        self.pending = 0
        self.text.delete("1.0", "end")
        self._to_ready("Cancelled — nothing saved")

    def _finalize(self):
        text = self.text.get("1.0", "end-1c").strip()
        if not text:
            self._to_ready("Nothing transcribed")
            return
        os.makedirs(config.PROMPTS_DIR, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        path = os.path.join(config.PROMPTS_DIR, f"{stamp}.txt")
        for p in (path, os.path.join(config.PROMPTS_DIR, config.LATEST_FILE)):
            with open(p, "w", encoding="utf-8") as f:
                f.write(text + "\n")
        copied = ""
        if self.autocopy_var.get():
            pyperclip.copy(text)
            copied = " · copied to clipboard ✓"
        self._to_ready(f"Saved {os.path.basename(path)}{copied}")

    def _to_ready(self, msg: str):
        self.state = READY
        self.record_btn.config(text="🎤 Record", state="normal")
        self.cancel_btn.config(state="disabled")
        self.device_box.config(state="readonly")
        self.refresh_btn.config(state="normal")
        self._set_level(0.0, False)
        self._set_status(msg)

    def _insert_paragraph(self, *_):
        """Start a new paragraph at the end of the transcript (works while
        recording: the next segment lands on the fresh line)."""
        self.text.insert("end", "\n\n")
        self.text.see("end")
        return "break"  # keep Ctrl+Enter from also inserting a newline at the cursor

    def _copy(self):
        text = self.text.get("1.0", "end-1c").strip()
        if text:
            pyperclip.copy(text)
            self._set_status("Copied to clipboard ✓")

    def _open_folder(self):
        folder = os.path.abspath(config.PROMPTS_DIR)
        os.makedirs(folder, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    # ------------------------------------------------------------ events

    def _poll(self):
        self._drain_events()
        self.root.after(40, self._poll)

    def _drain_events(self):
        while True:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                return
            self._handle(ev)

    def _handle(self, ev):
        kind = ev[0]
        if kind == "level":
            if self.state == RECORDING:
                self._set_level(ev[1], ev[2])
        elif kind == "segment":
            if self.state not in (RECORDING, FINALIZING):
                return  # cancelled while segment was in flight
            self.pending += 1
            tail = self.text.get("1.0", "end-1c")[-200:].strip() or None
            self.transcriber.submit(ev[1], self.session, tail)
        elif kind == "segment_text":
            _, session_id, text = ev
            if session_id != self.session:
                return  # from a cancelled recording
            self.pending -= 1
            if text:
                current = self.text.get("1.0", "end-1c")
                if current.strip() and not current[-1].isspace():
                    self.text.insert("end", config.SEGMENT_JOIN)
                self.text.insert("end", text)
                self.text.see("end")
            if self.state == FINALIZING and self.pending <= 0:
                self._finalize()
        elif kind == "model_ready":
            self.model_desc = ev[1]
            if self.state == LOADING:
                self._to_ready(f"Ready · {self.model_desc}")
        elif kind == "model_error":
            self._set_status(ev[1])
            if self.state == LOADING:
                self.record_btn.config(state="disabled")
        elif kind == "audio_error":
            self._set_status(f"Audio error: {ev[1]}")
            if self.state == RECORDING:
                self._on_cancel()


def run():
    root = tk.Tk()
    VoiceToTextApp(root)
    root.mainloop()
