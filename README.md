# MoeLingo

**Real-time overlay translator for Japanese visual novels / galgames.**
Reads the game's text straight off the window with OCR and translates it with a
**local** LLM — nothing leaves your machine. Pick *what language to translate into*
and *what language the UI is in* independently.

> 用本地大模型实时翻译日文 galgame / 视觉小说的悬浮翻译工具。截取游戏窗口 → OCR → 本地模型翻译 → 悬浮显示。译文语言与界面语言可分别选择，全程本地，不上传任何内容。

---

## How it works

```
game window ──PrintWindow──▶ crop text region ──PaddleOCR(JP)──▶ local LLM (Ollama) ──▶ overlay
```

- **OBS-style window capture** (`PrintWindow`) — follows the window when moved and
  is immune to anything drawn on top (including the overlay itself). The window is
  matched by its **process exe**, not its title.
- **PaddleOCR (Japanese)** for detection + recognition — robust on long, stylized
  lines over textured dialogue boxes.
- **Local LLM via [Ollama](https://ollama.com)** (default `qwen2.5:7b-instruct`).
  Optional **game background info** is fed as context to unify names and improve
  accuracy. Same line is never re-translated (dedup), and the model is stopped from
  parroting the background or leaving the source language untranslated.

## Requirements

- **Windows 10/11** (uses the Win32 `PrintWindow` API).
- **Python 3.9–3.11**.
- **[Ollama](https://ollama.com)** running locally with a model pulled:
  ```bash
  ollama pull qwen2.5:7b-instruct
  ```
- A GPU is optional — OCR runs on CPU; the LLM uses whatever Ollama is configured for.

## Install

```bash
git clone https://github.com/AlvinXu0311/MoeLingo.git
cd MoeLingo
pip install -r requirements.txt
```

> Note: installing `paddlepaddle` may conflict with an existing PyTorch install in
> the same environment (a known Windows DLL clash). Use a dedicated virtualenv if
> you also need torch.

## Run

```bash
python -m moelingo        # or:  python run.py   (or double-click run.bat)
```

Then, in the control bar:

1. **Window** — pick the game window (shown with its `exe` name).
2. **Region** — drag a box over the dialogue text on the captured frame. The box is
   stored *relative to the window*, so it survives moving/resizing.
3. **Game Info** *(optional)* — paste plot/character background; it's used as context.
4. **To** — choose the translation target language (中文 / English).
5. **UI** — choose the interface language (中文 / English).
6. **▶ Start**. Drag the dark overlay anywhere; toggle **Source** to see the OCR text.

Settings (window, region, game info, languages) are saved to `config.json` at the
repo root.

## Configuration (env vars)

| Variable | Default | Meaning |
|---|---|---|
| `MOELINGO_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `MOELINGO_MODEL` | `qwen2.5:7b-instruct` | translation model (any Ollama model) |
| `MOELINGO_OCR_LANG` | `japan` | PaddleOCR source language |

## Tips

- Box **only the dialogue text** — exclude the speaker-name box, text-speed bars, and
  the bottom menu strip, or they pollute the OCR.
- If a line is mistranslated, fill in **Game Info** (character names, setting, tone).
- Closing the small control window quits the app; **minimize** it instead of closing.

## Limitations

- Windows-only; Japanese source by default.
- OCR accuracy depends on the game's font/rendering; very small or heavily stylized
  text may still misread.

## License

[Apache-2.0](LICENSE)
