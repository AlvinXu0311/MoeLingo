# MoeLingo

Real-time overlay translator for Japanese visual novels and galgames. MoeLingo
reads the on-screen text directly from the game window with OCR and translates it
with a **local** large language model, then shows the result in a floating overlay.
Nothing is sent to the cloud.

It is not tied to any single game: point it at any window, box the text area, and
pick your languages. The OCR language and the translation model are configurable, so
you can adapt it to other games and models.

You choose two things independently:

- **Target language** — what the game text is translated **into** (Chinese or English).
- **UI language** — the language of MoeLingo's own interface (Chinese or English).

---

## How it works (design)

```
game window --[PrintWindow]--> crop text region --[PaddleOCR]--> local LLM (Ollama) --> overlay
```

1. **Window capture (Win32 `PrintWindow`).** MoeLingo captures the chosen game
   window directly, the same way OBS "Window Capture" does. This follows the window
   when it is moved or resized and is immune to anything drawn on top (including
   MoeLingo's own overlay). The window is matched by its **process executable name**,
   not its title, so it will not accidentally grab a browser or editor that happens
   to share a title.
2. **Text region.** You drag a box over the dialogue area once. It is stored relative
   to the window, so it keeps working after the window moves or resizes.
3. **OCR (PaddleOCR).** Detection plus recognition in one pass. This handles long,
   stylized lines over textured dialogue boxes, which single-line OCR models tend to
   misread. Only lines containing real Japanese (kana/kanji) are kept, so logos,
   numbers and English captions are ignored.
4. **Translation (local LLM via Ollama).** Each new line is translated by a local
   model. Quality safeguards:
   - The same line is never re-translated (de-duplicated), so background animation
     and the blinking cursor do not cause flicker.
   - Optional **Game Info** (plot, character names, setting, tone) is supplied to the
     model as read-only context to keep names consistent and improve accuracy.
   - The model is prevented from parroting that background text, and any output that
     still contains untranslated source-language characters is automatically retried.
5. **Overlay.** A draggable, always-on-top window shows the translation. Because it is
   MoeLingo's own window, it renders Chinese/English with a normal system font — no
   in-game font hacks required.

## Features

- Local and private: OCR runs on your machine; translation runs on your local LLM.
- Works with any window; not specific to one game.
- Independent target-language and UI-language selection (Chinese / English).
- In-app Settings for the model, Ollama URL, and OCR language (no code editing).
- Optional game-background context for consistent names and better accuracy.
- Window-relative capture region; stable de-duplicated output.

## Requirements

**Operating system**

- Windows 10 or 11 (uses the Win32 `PrintWindow` API; Windows only).

**Software**

- Python 3.9 - 3.11.
- [Ollama](https://ollama.com) installed and running, with a model pulled:
  ```
  ollama pull qwen2.5:7b-instruct
  ```

**Hardware (guidance)**

- OCR (PaddleOCR) runs on the **CPU** and needs no GPU. A modern multi-core CPU
  handles a dialogue line in roughly one second.
- The LLM is served by Ollama and can use your GPU if available. The default
  `qwen2.5:7b-instruct` needs about **5-6 GB of free VRAM** for comfortable speed, or
  it can run on CPU more slowly. Pick a smaller model in Settings if you have less.
- 16 GB system RAM is comfortable; 8 GB works with a small model.

## Install

```
git clone https://github.com/AlvinXu0311/MoeLingo.git
cd MoeLingo
pip install -r requirements.txt
```

Note: installing `paddlepaddle` can conflict with an existing PyTorch installation in
the same Python environment (a known Windows DLL clash). If you also use PyTorch, put
MoeLingo in its own virtual environment.

## Run

```
python -m moelingo
```

Equivalently, `python run.py`, or double-click `run.bat` on Windows.

## Usage

In the control bar:

1. **Window** — pick the game window (listed with its executable name).
2. **Region** — drag a box over the dialogue text on the captured frame.
3. **Game Info** (optional) — paste plot/character background to improve accuracy.
4. **Settings** (optional) — set the model, Ollama URL, and OCR language.
5. **To** — choose the target language (Chinese / English).
6. **UI** — choose the interface language (Chinese / English).
7. **Start** — begin translating. Drag the dark overlay anywhere; toggle **Source**
   to also see the recognized Japanese.

All settings are saved to `config.json` at the repository root.

## Configuration

The **Settings** dialog (recommended) lets you change, at runtime:

- **Model** — any model available to your Ollama (e.g. `qwen2.5:7b-instruct`,
  `qwen2.5:14b-instruct`, `llama3.1:8b`). Applies immediately.
- **Ollama URL** — defaults to `http://localhost:11434`. Applies immediately.
- **OCR language** — a PaddleOCR language code (`japan`, `ch`, `en`, `korean`, ...).
  Changing it takes effect after a restart.

The same three values can also be set with environment variables (used as defaults if
no value is saved):

| Variable | Default | Meaning |
|---|---|---|
| `MOELINGO_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `MOELINGO_MODEL` | `qwen2.5:7b-instruct` | translation model |
| `MOELINGO_OCR_LANG` | `japan` | PaddleOCR source language |

## Tips

- Box **only the dialogue text**. Exclude the speaker-name box, text-speed bars and
  the bottom menu strip, or they will pollute the OCR.
- If a line reads oddly, fill in **Game Info** with character names, setting and tone.
- Closing the small control window quits the app. **Minimize** it instead of closing.

## Limitations

- Windows only; Japanese source text by default (other OCR languages are selectable
  but the translation prompts are tuned for Japanese).
- OCR accuracy depends on the game's font and rendering; very small or heavily
  stylized text can still misread.

## License

[Apache-2.0](LICENSE)
