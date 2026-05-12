from __future__ import annotations

import json
import os
import re
import argparse
import threading
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import END, Button, Entry, Label, StringVar, Text, Tk, filedialog, messagebox, ttk


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "audio"
DEFAULT_INTRO_TEXT = """Welcome to Valaska, the bitter north at the very edge of the known world. Endless forests of black pine stretch beneath iron-gray skies, and the wind carries the bite of distant glaciers.

Your party of four adventurers has gathered in the frontier town of Moosehearth, a stubborn settlement of timber lodges and smoking chimneys clinging to survival against the cold. Tonight you sit inside the Antlers' Rest Inn, a warm refuge of firelight, rough laughter, and the smell of spiced ale.

Just moments ago, one of you returned from the town square carrying a freshly pulled notice from the jobs board. The parchment is still stiff from the cold, promising coin, danger, and opportunity somewhere out in the frozen wilds.

Adventure calls."""

VOICES = [
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "nova",
    "onyx",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
]


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def safe_file_stem(value: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return stem or "tts-output"


class TtsStudio:
    def __init__(self) -> None:
        env = load_env(ENV_PATH)
        self.api_key = env.get("OPENAI_API_KEY", "")
        self.base_url = env.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = env.get("LLM_MODEL_TTS", "gpt-4o-mini-tts")
        self.output_dir = DEFAULT_OUTPUT_DIR

        self.root = Tk()
        self.root.title("MK4 TTS Studio")
        self.root.geometry("820x700")

        self.voice_var = StringVar(value="alloy")
        self.file_var = StringVar(value="valaska-intro")
        self.status_var = StringVar(value=f"Ready. Output folder: {self.output_dir}")
        self.instructions_var = StringVar(value="Speak as a dark fantasy narrator. Calm, clear, ominous, and inviting.")

        self.generate_button: Button | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        Label(self.root, text="Voice").grid(row=0, column=0, sticky="w", **pad)
        voice_box = ttk.Combobox(self.root, textvariable=self.voice_var, values=VOICES, state="readonly")
        voice_box.grid(row=0, column=1, sticky="ew", **pad)

        Label(self.root, text="File name").grid(row=1, column=0, sticky="w", **pad)
        Entry(self.root, textvariable=self.file_var).grid(row=1, column=1, sticky="ew", **pad)

        Label(self.root, text="Instructions").grid(row=2, column=0, sticky="w", **pad)
        Entry(self.root, textvariable=self.instructions_var).grid(row=2, column=1, sticky="ew", **pad)

        Label(self.root, text="Text").grid(row=3, column=0, sticky="nw", **pad)
        self.text_box = Text(self.root, wrap="word", height=22)
        self.text_box.grid(row=3, column=1, sticky="nsew", **pad)
        self.text_box.insert(END, DEFAULT_INTRO_TEXT)

        button_frame = ttk.Frame(self.root)
        button_frame.grid(row=4, column=1, sticky="ew", **pad)

        self.generate_button = Button(button_frame, text="Generate, Save, and Play", command=self.generate_clicked)
        self.generate_button.pack(side="left")
        Button(button_frame, text="Choose Output Folder", command=self.choose_output_folder).pack(side="left", padx=8)

        Label(self.root, textvariable=self.status_var, anchor="w").grid(row=5, column=0, columnspan=2, sticky="ew", **pad)

        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(3, weight=1)

    def choose_output_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=str(self.output_dir))
        if selected:
            self.output_dir = Path(selected)
            self.status_var.set(f"Output folder: {self.output_dir}")

    def generate_clicked(self) -> None:
        if not self.api_key:
            messagebox.showerror("Missing API key", f"No OPENAI_API_KEY found in {ENV_PATH}")
            return

        text = self.text_box.get("1.0", END).strip()
        if not text:
            messagebox.showerror("Missing text", "Enter text to synthesize.")
            return

        if self.generate_button:
            self.generate_button.config(state="disabled")
        self.status_var.set("Generating audio...")
        thread = threading.Thread(target=self.generate_audio, args=(text,), daemon=True)
        thread.start()

    def generate_audio(self, text: str) -> None:
        try:
            output_path = self.write_audio_file(text)
        except Exception as exc:
            self.root.after(0, self.finish_with_error, str(exc))
            return
        self.root.after(0, self.finish_success, output_path)

    def write_audio_file(self, text: str) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / f"{safe_file_stem(self.file_var.get())}.mp3"

        payload = {
            "model": self.model,
            "voice": self.voice_var.get(),
            "input": text,
            "response_format": "mp3",
        }
        instructions = self.instructions_var.get().strip()
        if instructions:
            payload["instructions"] = instructions

        request = urllib.request.Request(
            f"{self.base_url}/audio/speech",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                output_path.write_bytes(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI request failed: HTTP {exc.code}\n{detail}") from exc

        return output_path

    def finish_success(self, output_path: Path) -> None:
        if self.generate_button:
            self.generate_button.config(state="normal")
        self.status_var.set(f"Saved: {output_path}")
        os.startfile(output_path)

    def finish_with_error(self, message: str) -> None:
        if self.generate_button:
            self.generate_button.config(state="normal")
        self.status_var.set("Generation failed.")
        messagebox.showerror("Generation failed", message)

    def run(self) -> None:
        self.root.mainloop()


def write_audio_file(
    text: str,
    output_path: Path,
    voice: str = "alloy",
    instructions: str = "Speak as a dark fantasy narrator. Calm, clear, ominous, and inviting.",
) -> Path:
    env = load_env(ENV_PATH)
    api_key = env.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(f"No OPENAI_API_KEY found in {ENV_PATH}")
    base_url = env.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = env.get("LLM_MODEL_TTS", "gpt-4o-mini-tts")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": model,
        "voice": voice,
        "input": text,
        "response_format": "mp3",
    }
    if instructions.strip():
        payload["instructions"] = instructions.strip()
    request = urllib.request.Request(
        f"{base_url}/audio/speech",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            output_path.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI request failed: HTTP {exc.code}\n{detail}") from exc
    return output_path


def run_cli() -> bool:
    parser = argparse.ArgumentParser(description="Generate an MP3 using the Story Engine TTS settings.")
    parser.add_argument("--text", help="Text to synthesize.")
    parser.add_argument("--text-file", type=Path, help="UTF-8 text file to synthesize.")
    parser.add_argument("--voice", default="alloy", choices=VOICES)
    parser.add_argument("--instructions", default="Speak as a dark fantasy narrator. Calm, clear, ominous, and inviting.")
    parser.add_argument("--output", type=Path, help="Output MP3 path.")
    args = parser.parse_args()
    if not any([args.text, args.text_file, args.output]):
        return False
    if not args.output:
        parser.error("--output is required in CLI mode")
    if args.text_file:
        text = args.text_file.read_text(encoding="utf-8").strip()
    else:
        text = (args.text or "").strip()
    if not text:
        parser.error("--text or --text-file must contain text")
    output_path = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    saved = write_audio_file(text, output_path, voice=args.voice, instructions=args.instructions)
    print(saved)
    return True


if __name__ == "__main__":
    if not run_cli():
        TtsStudio().run()
