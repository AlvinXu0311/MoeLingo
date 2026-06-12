# MoeLingo

Real-time overlay translator for Japanese visual novels / galgames, powered by a
**local** LLM. 面向日文视觉小说 / galgame 的**本地**实时悬浮翻译工具。

<p align="center">
  <img alt="platform" src="https://img.shields.io/badge/platform-Windows-0078D6?style=for-the-badge">
  <img alt="python" src="https://img.shields.io/badge/python-3.9–3.11-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="LLM" src="https://img.shields.io/badge/LLM-Ollama-4B8BBE?style=for-the-badge">
  <img alt="OCR" src="https://img.shields.io/badge/OCR-PaddleOCR-FF6F00?style=for-the-badge">
  <img alt="license" src="https://img.shields.io/badge/license-Apache--2.0-2EA44F?style=for-the-badge">
</p>

<p align="center">
  <img alt="overlay translating in-game" src="https://github.com/user-attachments/assets/89b99b34-eb17-4f74-8942-ae1b9bc389fc" height="320">
  <img alt="overlay with source text" src="https://github.com/user-attachments/assets/a081eae3-1b2e-4ece-9c2b-f2c30b369fd7" height="320">
</p>

<details>
<summary><h3>English &nbsp;&nbsp;·&nbsp;&nbsp; click to expand </h3></summary>

<br>

MoeLingo reads the on-screen text directly from the game window with OCR and
translates it with a **local** large language model, then shows the result in a
floating overlay. Nothing is sent to the cloud.

It is not tied to any single game: point it at any window, box the text area, and
pick your languages. The OCR language and the translation model are configurable, so
you can adapt it to other games and models.

You choose two things independently:

- **Target language** — what the game text is translated **into** (Chinese or English).
- **UI language** — the language of MoeLingo's own interface (Chinese or English).

### Features

- Local and private: OCR runs on your machine; translation runs on your local LLM.
- Works with any window; not specific to one game.
- Independent target-language and UI-language selection (Chinese / English).
- In-app Settings for the model, Ollama URL, and OCR language (no code editing).
- Optional game-background context for consistent names and better accuracy.
- Window-relative capture region; stable de-duplicated output.

### Requirements

**Operating system** — Windows 10 or 11 (uses the Win32 `PrintWindow` API; Windows only).

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

### Install

```
git clone https://github.com/AlvinXu0311/MoeLingo.git
cd MoeLingo
pip install -r requirements.txt
```

Note: installing `paddlepaddle` can conflict with an existing PyTorch installation in
the same Python environment (a known Windows DLL clash). If you also use PyTorch, put
MoeLingo in its own virtual environment.

### Run

```
python -m moelingo
```

Equivalently, `python run.py`, or double-click `run.bat` on Windows.

### Usage

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

### Configuration

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

### Tips

- Box **only the dialogue text**. Exclude the speaker-name box, text-speed bars and
  the bottom menu strip, or they will pollute the OCR.
- If a line reads oddly, fill in **Game Info** with character names, setting and tone.
- Closing the small control window quits the app. **Minimize** it instead of closing.

### How it works (design)

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
   misread. Only lines containing real Japanese (kana/kanji) are kept.
4. **Translation (local LLM via Ollama).** Each new line is translated by a local
   model. The same line is never re-translated (de-duplicated). Optional **Game Info**
   is supplied as read-only context to keep names consistent; the model is prevented
   from parroting it, and output that still contains untranslated source characters is
   retried automatically.
5. **Overlay.** A draggable, always-on-top window shows the translation in a normal
   system font — no in-game font hacks required.

### License

[Apache-2.0](LICENSE)

</details>

<details>
<summary><h3>中文 &nbsp;&nbsp;·&nbsp;&nbsp; 点击展开 </h3></summary>

<br>

MoeLingo 直接从游戏窗口用 OCR 读取画面上的文字，再交给**本地**大模型翻译，并显示在一个
悬浮窗里。全程在本机完成，不上传任何内容。

它不绑定某一个游戏：把它对准任意窗口、框出文字区域、选好语言即可。OCR 语言和翻译模型都可
配置，因此也能适配其他游戏和模型。

两个设置相互独立：

- **译文语言** —— 把游戏文字翻译**成**什么语言（中文 / 英文）。
- **界面语言** —— MoeLingo 自身界面的语言（中文 / 英文）。

### 功能特性

- 本地、隐私：OCR 在本机运行，翻译用你本地的大模型。
- 适用于任意窗口，不针对特定游戏。
- 译文语言与界面语言可分别选择（中文 / 英文）。
- 内置「设置」可改模型、Ollama 地址、OCR 语言（无需改代码）。
- 可选填游戏背景信息，统一译名、提升准确度。
- 截取区域相对窗口存储；输出去重、稳定不闪。

### 环境要求

**操作系统** —— Windows 10 或 11（使用 Win32 `PrintWindow` 接口，仅支持 Windows）。

**软件**

- Python 3.9 - 3.11。
- 安装并运行 [Ollama](https://ollama.com)，并拉取一个模型：
  ```
  ollama pull qwen2.5:7b-instruct
  ```

**硬件（建议）**

- OCR（PaddleOCR）跑在 **CPU** 上，无需显卡。现代多核 CPU 处理一行对白约 1 秒。
- 大模型由 Ollama 提供，可使用显卡。默认的 `qwen2.5:7b-instruct` 舒适运行约需
  **5-6 GB 空闲显存**，显存不足也可跑 CPU（较慢），或在「设置」里换更小的模型。
- 系统内存 16 GB 较舒适；8 GB 配小模型也可用。

### 安装

```
git clone https://github.com/AlvinXu0311/MoeLingo.git
cd MoeLingo
pip install -r requirements.txt
```

注意：安装 `paddlepaddle` 可能与同一 Python 环境里已有的 PyTorch 冲突（Windows 上已知的
DLL 冲突）。如果你也用 PyTorch，请把 MoeLingo 装在独立的虚拟环境里。

### 运行

```
python -m moelingo
```

等价地，也可以 `python run.py`，或在 Windows 上双击 `run.bat`。

### 使用方法

在控制栏里：

1. **选择窗口** —— 选游戏窗口（列表会显示其可执行文件名）。
2. **选择区域** —— 在截取到的画面上拖框圈住对白文字。
3. **游戏信息**（可选）—— 粘贴剧情 / 人物背景以提升准确度。
4. **设置**（可选）—— 设置模型、Ollama 地址、OCR 语言。
5. **译文** —— 选择译文语言（中文 / 英文）。
6. **界面** —— 选择界面语言（中文 / 英文）。
7. **开始** —— 开始翻译。深色悬浮窗可随意拖动；勾选**原文**可同时看到识别出的日文。

所有设置保存在仓库根目录的 `config.json`。

### 配置

推荐用**设置**对话框，可在运行时修改：

- **模型** —— 你 Ollama 里的任意模型（如 `qwen2.5:7b-instruct`、`qwen2.5:14b-instruct`、
  `llama3.1:8b`）。即时生效。
- **Ollama 地址** —— 默认 `http://localhost:11434`。即时生效。
- **OCR 语言** —— PaddleOCR 语言代码（`japan`、`ch`、`en`、`korean` …）。改动需重启生效。

这三项也可用环境变量设置（在未保存时作为默认值）：

| 变量 | 默认值 | 含义 |
|---|---|---|
| `MOELINGO_OLLAMA_URL` | `http://localhost:11434` | Ollama 服务地址 |
| `MOELINGO_MODEL` | `qwen2.5:7b-instruct` | 翻译模型 |
| `MOELINGO_OCR_LANG` | `japan` | PaddleOCR 源语言 |

### 小贴士

- **只框对白文字**。把人名框、文字速度条、底部菜单栏排除在外，否则会污染 OCR。
- 某句翻得别扭时，在**游戏信息**里补上人物名、设定与语气。
- 关闭那个小控制窗会退出程序，想收起请**最小化**而不是关闭。

### 工作原理（设计）

```
游戏窗口 --[PrintWindow]--> 裁剪文字区域 --[PaddleOCR]--> 本地大模型 (Ollama) --> 悬浮窗
```

1. **窗口捕捉（Win32 `PrintWindow`）。** 像 OBS 的"窗口捕捉"一样直接抓取所选游戏窗口：
   窗口移动 / 缩放都跟得上，且不受任何盖在上面的东西影响（包括 MoeLingo 自己的悬浮窗）。
   窗口按**进程可执行文件名**匹配，而非标题，因此不会误抓到恰好同名的浏览器或编辑器。
2. **文字区域。** 只需在对白区域拖一次框。它按窗口的相对位置保存，所以窗口移动 / 缩放后仍然有效。
3. **OCR（PaddleOCR）。** 检测 + 识别一体，能应对花纹对白框上又长又花的文字——这正是单行
   OCR 模型容易读错的地方。只保留含真正日文（假名 / 汉字）的行。
4. **翻译（本地大模型，经 Ollama）。** 每出现新的一行就交给本地模型翻译。同一行不会重复翻译
   （去重）。可选的**游戏信息**作为只读上下文喂给模型以统一译名；并防止模型把它原样背出来，
   若输出里仍残留未翻译的源语言文字会自动重翻一次。
5. **悬浮窗。** 一个可拖动、置顶的窗口用普通系统字体显示译文——无需对游戏做任何字库 hack。

### 许可证

[Apache-2.0](LICENSE)

</details>
