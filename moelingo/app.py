"""MoeLingo — real-time overlay translator for Japanese visual novels / galgames.

Pipeline:  capture the game WINDOW (PrintWindow; follows moves, immune to overlays
on top) -> crop the text region (stored relative to the window) -> PaddleOCR
(Japanese) -> live translation via a local LLM (Ollama), seeded with optional game
background info -> show the translation in an always-on-top overlay.

Translate-to language (中文/English) and UI language are chosen independently from
the control bar. Configure the model/host/source-OCR-language via env vars:
  MOELINGO_OLLAMA_URL  (default http://localhost:11434)
  MOELINGO_MODEL       (default qwen2.5:7b-instruct)
  MOELINGO_OCR_LANG    (PaddleOCR lang, default 'japan')

Run:  python -m moelingo   (or  python run.py)
"""
import os, sys, json, time, threading, queue, hashlib
import tkinter as tk
from tkinter import font as tkfont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
# user config lives at the repo root (gitignored), not inside the package
CONFIG = os.path.join(ROOT, 'config.json')

# A dedicated var (NOT the conventional OLLAMA_HOST, which is often '0.0.0.0' for serving).
_OLLAMA = os.environ.get('MOELINGO_OLLAMA_URL', 'http://localhost:11434').rstrip('/')
if '://' not in _OLLAMA:
    _OLLAMA = 'http://' + _OLLAMA
OLLAMA_HOST = _OLLAMA
OLLAMA_MODEL = os.environ.get('MOELINGO_MODEL', 'qwen2.5:7b-instruct')
OCR_LANG = os.environ.get('MOELINGO_OCR_LANG', 'japan')
CAP_INTERVAL = 0.12 # seconds between captures
STABLE_FRAMES = 2   # identical frames required before OCR (skip typewriter anim)
DEFAULT_FRAC = {'x': 0.04, 'y': 0.72, 'w': 0.92, 'h': 0.26}  # typical ADV textbox strip

# target translation languages (code -> native display name)
TARGETS = [('zh', '中文'), ('en', 'English')]
UI_LANGS = [('zh', '中文'), ('en', 'English')]
TGT_NAME = {'zh': '简体中文', 'en': 'English'}

# UI strings per interface language
STRINGS = {
 'zh': {
   'app_title': '实时翻译', 'btn_window': '选择窗口', 'btn_region': '选择区域',
   'btn_gameinfo': '游戏信息', 'btn_start': '▶ 开始', 'btn_pause': '⏸ 暂停',
   'chk_src': '原文', 'ui_lang': '界面', 'tgt_lang': '译文',
   'st_init': '初始化…', 'st_loadocr': '加载OCR模型（PaddleOCR 日文）…', 'st_ready': '就绪',
   'st_nowin': '找不到窗口「{title}」', 'st_ocrerr': 'OCR错误:{e}', 'st_pickwin': '请先选择窗口',
   'st_winsel': '已选窗口：{t} ({e})', 'st_region': '区域已保存', 'st_gisaved': '游戏信息已保存',
   'st_grabfail': '截取窗口失败', 'st_nofind': '找不到窗口',
   'winlabel': '目标窗口: {title}  |  译文: {tgt} {info}', 'unselected': '（未选）',
   'have_info': '· 已填游戏信息',
   'picker_title': '选择游戏窗口', 'picker_prompt': '双击选择游戏窗口：', 'ok': '确定',
   'region_title': '框选文本区域（拖动）',
   'gi_title': '游戏信息 / 背景设定',
   'gi_help': '填入剧情梗概、人物名与关系、世界观、语气风格等。\n这些会作为上下文喂给本地模型，帮助统一译名、提升翻译准确度。',
   'gi_save': '保存', 'gi_saveclose': '保存并关闭', 'gi_saved': '✓ 已保存',
   'ov_waiting': '（等待文本…）', 'translating': '翻译中…',
   'src_live': '实时翻译', 'src_live_ocr': '实时翻译…（OCR {t:.1f}s）',
 },
 'en': {
   'app_title': 'Live Translate', 'btn_window': 'Window', 'btn_region': 'Region',
   'btn_gameinfo': 'Game Info', 'btn_start': '▶ Start', 'btn_pause': '⏸ Pause',
   'chk_src': 'Source', 'ui_lang': 'UI', 'tgt_lang': 'To',
   'st_init': 'Initializing…', 'st_loadocr': 'Loading OCR (PaddleOCR Japanese)…', 'st_ready': 'Ready',
   'st_nowin': 'Window not found: {title}', 'st_ocrerr': 'OCR error: {e}', 'st_pickwin': 'Pick a window first',
   'st_winsel': 'Window: {t} ({e})', 'st_region': 'Region saved', 'st_gisaved': 'Game info saved',
   'st_grabfail': 'Window capture failed', 'st_nofind': 'Window not found',
   'winlabel': 'Target: {title}  |  to {tgt} {info}', 'unselected': '(none)',
   'have_info': '· game info set',
   'picker_title': 'Pick game window', 'picker_prompt': 'Double-click the game window:', 'ok': 'OK',
   'region_title': 'Drag to box the text region',
   'gi_title': 'Game Info / Background',
   'gi_help': 'Enter plot summary, character names & relations, setting, tone, etc.\n'
              'This is fed to the local model as context to unify names and improve accuracy.',
   'gi_save': 'Save', 'gi_saveclose': 'Save & Close', 'gi_saved': '✓ saved',
   'ov_waiting': '(waiting for text…)', 'translating': 'translating…',
   'src_live': 'live', 'src_live_ocr': 'translating… (OCR {t:.1f}s)',
 },
}

# ----------------------------------------------------------------------------- DB
def jp_norm(s):
    """Keep only kana/kanji/fullwidth so OCR noise, brackets, \\n, spaces drop out."""
    out = []
    for c in s:
        o = ord(c)
        if (0x3040 <= o <= 0x30ff) or (0x4e00 <= o <= 0x9fff) or (0xff10 <= o <= 0xff5a):
            out.append(c)
    return ''.join(out)

def kana_kanji_count(s):
    """Count real Japanese chars (kana + kanji) — excludes fullwidth digits/latin,
    so stylized logos / numbers ('１９．６１６Ｓ') don't get treated as dialogue."""
    n = 0
    for c in s:
        o = ord(c)
        if (0x3040 <= o <= 0x30ff) or (0x4e00 <= o <= 0x9fff):
            n += 1
    return n

# ------------------------------------------------------------------------- Ollama
OLLAMA_CHAT = OLLAMA_HOST + '/api/chat'
RULES = {
 'zh': ("你是galgame翻译。只把【用户消息里给的那一句日文】翻译成自然口语的简体中文。"
        "只输出这一句的译文本身，不要解释、不要拼音、不要附日文原文。"
        "拟声词/语气词也要译成中文（如「ふぅ」→「呼…」「あんっ」→「啊嗯…」），"
        "输出中绝对不能出现任何日文假名。"),
 'en': ("You are a galgame translator. Translate ONLY the single Japanese line in the "
        "user's message into natural, colloquial English. Output just that translation — "
        "no explanation, no romaji, no Japanese. Render onomatopoeia/interjections in "
        "English too. The output must contain no Japanese kana or kanji."),
}
INFO_NOTE = {
 'zh': ("\n\n以下是游戏背景资料，仅供你理解上下文与统一译名。这只是参考，"
        "绝对不要翻译、复述、引用或输出其中的任何句子；无论用户那句多短，你都只翻译用户那一句：\n"),
 'en': ("\n\nThe following is game background, for context and consistent names only. "
        "It is reference — never translate, repeat, quote or output any of it; no matter how "
        "short the user's line is, translate only the user's line:\n"),
}
USER_MSG = {'zh': '把这句日文翻成简体中文（只输出译文）：\n{jp}',
            'en': 'Translate this Japanese line into English (output only the translation):\n{jp}'}

def has_kana(s):
    return any(0x3040 <= ord(c) <= 0x30ff for c in s)

def _residual_jp(s, target):
    """Untranslated leftovers: kana always; for English target, any CJK at all."""
    if has_kana(s):
        return True
    if target == 'en':
        return any(0x4e00 <= ord(c) <= 0x9fff for c in s)
    return False

def _echoes_info(out, game_info):
    """True if the output verbatim-copies a long chunk of the background info."""
    if not game_info:
        return False
    g = game_info.replace('\n', '').replace(' ', '')
    o = out.replace('\n', '').replace(' ', '')
    W = 16
    return any(o[i:i + W] in g for i in range(0, max(0, len(o) - W + 1)))

def _ollama_chat(system, user, temp):
    import requests
    r = requests.post(OLLAMA_CHAT, json={
        'model': OLLAMA_MODEL, 'stream': False,
        'messages': [{'role': 'system', 'content': system},
                     {'role': 'user', 'content': user}],
        'options': {'temperature': temp, 'num_predict': 200},
    }, timeout=60)
    return r.json().get('message', {}).get('content', '').strip()

def ollama_translate(jp, game_info=None, target='zh'):
    target = target if target in RULES else 'zh'
    def system(with_info):
        s = RULES[target]
        if with_info and game_info and game_info.strip():
            s += INFO_NOTE[target] + game_info.strip()
        return s
    user = USER_MSG[target].format(jp=jp)
    try:
        out = _ollama_chat(system(True), user, 0.0)
        # if it parroted the background, or left source-language text, redo without info
        if _echoes_info(out, game_info) or _residual_jp(out, target):
            out2 = _ollama_chat(system(False), user, 0.2)
            if out2:
                out = out2
        return out
    except Exception as e:
        return f"[translate failed: {e}]"

# ----------------------------------------------------------------------------- OCR
class PaddleJaOCR:
    """PaddleOCR Japanese (detection + recognition in one). Handles long lines and
    textured backgrounds far better than manga-ocr (which hallucinated on 30+ char
    lines). Self-contained — no torch. Keeps only lines with >=2 kana/kanji."""
    def __init__(self):
        import numpy as np
        from paddleocr import PaddleOCR
        self.np = np
        self.po = PaddleOCR(use_angle_cls=False, lang=OCR_LANG, show_log=False)

    def read(self, crop_bgr):
        """Return recognized Japanese text lines in reading order."""
        bgr = self.np.ascontiguousarray(crop_bgr)
        try:
            r = self.po.ocr(bgr, cls=False)
        except Exception:
            return []
        if not r or not r[0]:
            return []
        items = []
        for box, (text, score) in r[0]:
            ys = [p[1] for p in box]; xs = [p[0] for p in box]
            items.append((min(ys), min(xs), text))
        items.sort(key=lambda b: (round(b[0] / 12), b[1]))   # top-to-bottom, then x
        return [t for _, _, t in items if kana_kanji_count(t) >= 2]

# -------------------------------------------------------------------------- Worker
class Worker(threading.Thread):
    def __init__(self, get_state, out_q):
        super().__init__(daemon=True)
        self.get_state = get_state   # -> dict(title, exe, frac, game_info)
        self.out = out_q
        self.paused = True
        self.stop_flag = False
        self._last_src = ''     # last resolved source line (dedup at the line level)

    def run(self):
        import wincap
        from PIL import Image
        import numpy as np
        ui0 = self.get_state().get('ui', 'zh')
        self.out.put({'status': STRINGS[ui0]['st_loadocr']})
        ocr = PaddleJaOCR()
        self.out.put({'status': STRINGS[self.get_state().get('ui', 'zh')]['st_ready']})
        from rapidfuzz import fuzz
        last_hash = ocr_hash = None
        last_norm = ''
        stable = 0
        while not self.stop_flag:
            state = self.get_state()
            title, exe, frac = state['title'], state['exe'], state['frac']
            if self.paused or not (title or exe):
                time.sleep(0.15); continue
            hwnd = wincap.find_window(title, exe)
            if not hwnd:
                self.out.put({'status': STRINGS[state.get('ui', 'zh')]['st_nowin'].format(title=title)})
                time.sleep(0.5); continue
            arr = wincap.grab_window(hwnd)
            if arr is None:
                time.sleep(0.3); continue
            H, W = arr.shape[:2]
            x, y = int(frac['x'] * W), int(frac['y'] * H)
            w, h = int(frac['w'] * W), int(frac['h'] * H)
            crop = arr[max(0, y):y + h, max(0, x):x + w]
            if crop.size == 0:
                time.sleep(0.2); continue
            small = crop[::max(1, crop.shape[0]//16), ::max(1, crop.shape[1]//48)]
            hsh = hashlib.md5((small // 24).tobytes()).hexdigest()
            if hsh == last_hash:
                stable += 1
            else:
                stable = 0; last_hash = hsh
            if stable == STABLE_FRAMES and hsh != ocr_hash:
                ocr_hash = hsh
                t0 = time.time()
                try:
                    lines = ocr.read(crop)
                except Exception as e:
                    self.out.put({'status': STRINGS[state.get('ui', 'zh')]['st_ocrerr'].format(e=e)})
                    time.sleep(CAP_INTERVAL); continue
                n = jp_norm(''.join(lines))
                # Text-level dedup: the same line re-OCR'd (background animation / cursor
                # blink / OCR jitter) must NOT re-translate. Only act when text changes.
                if len(n) < 2 or (last_norm and fuzz.ratio(n, last_norm) >= 88):
                    time.sleep(CAP_INTERVAL); continue
                last_norm = n
                self._handle(lines, time.time() - t0, state)
            time.sleep(CAP_INTERVAL)

    def _handle(self, lines, ocr_t, state):
        jp = ''.join(lines)
        # need at least 2 real Japanese chars -> skip logos / numbers / UI noise
        if not jp or kana_kanji_count(jp) < 2:
            return
        key = jp_norm(jp)
        if key == self._last_src:     # same line already shown -> no re-translate
            return
        self._last_src = key
        ui, target = state.get('ui', 'zh'), state.get('target', 'zh')
        S = STRINGS[ui]
        self.out.put({'jp': jp, 'zh': S['translating'], 'src': S['src_live_ocr'].format(t=ocr_t)})
        zh = ollama_translate(jp, game_info=state.get('game_info'), target=target)
        self.out.put({'jp': jp, 'zh': zh, 'src': S['src_live']})

NAME2CODE = {'中文': 'zh', 'English': 'en'}
CODE2NAME = {'zh': '中文', 'en': 'English'}

# ----------------------------------------------------------------------------- GUI
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.attributes('-topmost', True)
        self.root.geometry('+20+20')
        cfg = self._cfg()
        self.win_title = cfg.get('window_title')
        self.win_exe = cfg.get('window_exe')
        self.frac = cfg.get('region_frac', dict(DEFAULT_FRAC))
        self.game_info = cfg.get('game_info', '')
        self.ui_lang = cfg.get('ui_lang', 'zh')        # interface language
        self.tgt_lang = cfg.get('target_lang', 'zh')   # translate INTO this
        self.out_q = queue.Queue()
        self.show_src = tk.BooleanVar(value=True)
        self.cur = {'jp': '', 'zh': '', 'src': ''}
        self.w = {}   # localizable widgets, keyed by string-id

        bar = tk.Frame(self.root, padx=6, pady=6); bar.pack()
        self.w['btn_window'] = tk.Button(bar, command=self.select_window); self.w['btn_window'].pack(side='left', padx=2)
        self.w['btn_region'] = tk.Button(bar, command=self.select_region); self.w['btn_region'].pack(side='left', padx=2)
        self.w['btn_gameinfo'] = tk.Button(bar, command=self.edit_game_info); self.w['btn_gameinfo'].pack(side='left', padx=2)
        self.btn_run = tk.Button(bar, command=self.toggle); self.btn_run.pack(side='left', padx=2)
        self.w['chk_src'] = tk.Checkbutton(bar, variable=self.show_src, command=self.refresh)
        self.w['chk_src'].pack(side='left', padx=2)
        # target-language dropdown
        self.w['lbl_tgt'] = tk.Label(bar); self.w['lbl_tgt'].pack(side='left', padx=(10, 1))
        self._tgt_disp = tk.StringVar(value=CODE2NAME[self.tgt_lang])
        tk.OptionMenu(bar, self._tgt_disp, *[n for _, n in TARGETS], command=self._on_tgt).pack(side='left')
        # UI-language dropdown
        self.w['lbl_ui'] = tk.Label(bar); self.w['lbl_ui'].pack(side='left', padx=(10, 1))
        self._ui_disp = tk.StringVar(value=CODE2NAME[self.ui_lang])
        tk.OptionMenu(bar, self._ui_disp, *[n for _, n in UI_LANGS], command=self._on_ui).pack(side='left')

        self.status = tk.Label(self.root, anchor='w', fg='#555')
        self.status.pack(fill='x', padx=8, pady=(0, 6))
        self._win_label = tk.Label(self.root, text='', anchor='w', fg='#888', font=('', 8))
        self._win_label.pack(fill='x', padx=8, pady=(0, 4))

        self._build_overlay()
        self._apply_ui_lang()
        self.status.config(text=self.t('st_init'))
        self.worker = Worker(self._state, self.out_q)
        self.worker.start()
        self.root.after(80, self._poll)

    # ---- i18n ----
    def t(self, key, **kw):
        s = STRINGS[self.ui_lang].get(key, key)
        return s.format(**kw) if kw else s

    def _on_ui(self, disp):
        self.ui_lang = NAME2CODE.get(disp, 'zh')
        self._save_cfg(ui_lang=self.ui_lang); self._apply_ui_lang()

    def _on_tgt(self, disp):
        self.tgt_lang = NAME2CODE.get(disp, 'zh')
        self._save_cfg(target_lang=self.tgt_lang); self._upd_winlabel()

    def _apply_ui_lang(self):
        self.root.title(self.t('app_title'))
        for wkey, skey in (('btn_window', 'btn_window'), ('btn_region', 'btn_region'),
                           ('btn_gameinfo', 'btn_gameinfo'), ('chk_src', 'chk_src'),
                           ('lbl_ui', 'ui_lang'), ('lbl_tgt', 'tgt_lang')):
            self.w[wkey].config(text=self.t(skey))
        self.btn_run.config(text=self.t('btn_start' if self.worker_paused() else 'btn_pause'))
        self._upd_winlabel()
        if not self.cur.get('zh'):
            self.lbl_zh.config(text=self.t('ov_waiting'))

    def worker_paused(self):
        return getattr(self, 'worker', None) is None or self.worker.paused

    def _state(self):
        return {'title': self.win_title, 'exe': self.win_exe, 'frac': self.frac,
                'game_info': self.game_info, 'ui': self.ui_lang, 'target': self.tgt_lang}

    def _upd_winlabel(self):
        info = self.t('have_info') if self.game_info.strip() else ''
        self._win_label.config(text=self.t('winlabel', title=self.win_title or self.t('unselected'),
                                           tgt=TGT_NAME[self.tgt_lang], info=info))

    def edit_game_info(self):
        was = self.worker.paused; self.worker.paused = True
        dlg = tk.Toplevel(self.root); dlg.title(self.t('gi_title')); dlg.attributes('-topmost', True)
        dlg.geometry('560x440+220+180'); dlg.minsize(420, 300)
        tk.Label(dlg, anchor='w', justify='left', fg='#444', wraplength=540,
                 text=self.t('gi_help')).pack(side='top', fill='x', padx=10, pady=(10, 4))
        # button bar anchored to the BOTTOM first, so it's never pushed off-screen
        btnbar = tk.Frame(dlg); btnbar.pack(side='bottom', fill='x', padx=10, pady=8)
        saved_note = tk.Label(btnbar, text='', fg='#1a7f37')
        saved_note.pack(side='left')
        txt = tk.Text(dlg, font=('Microsoft YaHei', 11), wrap='word')
        txt.pack(side='top', fill='both', expand=True, padx=10, pady=4)
        txt.insert('1.0', self.game_info); txt.focus_set()
        def save(close=False):
            self.game_info = txt.get('1.0', 'end').strip()
            self._save_cfg(game_info=self.game_info); self._upd_winlabel()
            self.status.config(text=self.t('st_gisaved'))
            if close:
                dlg.destroy(); self.worker.paused = was
            else:
                saved_note.config(text=self.t('gi_saved')); dlg.after(1500, lambda: saved_note.config(text=''))
        tk.Button(btnbar, text=self.t('gi_saveclose'), command=lambda: save(True),
                  width=14).pack(side='right', padx=4)
        tk.Button(btnbar, text=self.t('gi_save'), command=lambda: save(False),
                  width=8).pack(side='right', padx=4)
        dlg.bind('<Control-s>', lambda e: save(False))
        # closing the window (X) or Esc also saves
        dlg.protocol('WM_DELETE_WINDOW', lambda: save(True))
        dlg.bind('<Escape>', lambda e: save(True))

    # ---- overlay window ----
    def _build_overlay(self):
        ov = tk.Toplevel(self.root)
        ov.overrideredirect(True); ov.attributes('-topmost', True); ov.attributes('-alpha', 0.9)
        ov.configure(bg='#0b0b0b')
        ov.geometry(self._cfg().get('overlay_geom', '820x150+300+650'))
        self.zh_font = tkfont.Font(family='Microsoft YaHei', size=20, weight='bold')
        self.src_font = tkfont.Font(family='Microsoft YaHei', size=10)
        self.lbl_zh = tk.Label(ov, text=self.t('ov_waiting'), font=self.zh_font, fg='#fff',
                               bg='#0b0b0b', wraplength=780, justify='left', anchor='w')
        self.lbl_zh.pack(fill='x', padx=14, pady=(10, 2))
        self.lbl_src = tk.Label(ov, text='', font=self.src_font, fg='#7fd1ff',
                                bg='#0b0b0b', wraplength=780, justify='left', anchor='w')
        self.lbl_src.pack(fill='x', padx=14, pady=(0, 8))
        for w in (ov, self.lbl_zh, self.lbl_src):
            w.bind('<Button-1>', self._drag_start); w.bind('<B1-Motion>', self._drag_move)
        self.overlay = ov

    def _drag_start(self, e):
        self._dx, self._dy = e.x_root - self.overlay.winfo_x(), e.y_root - self.overlay.winfo_y()
    def _drag_move(self, e):
        self.overlay.geometry(f'+{e.x_root - self._dx}+{e.y_root - self._dy}')
        self._save_cfg(overlay_geom=f'{self.overlay.winfo_width()}x{self.overlay.winfo_height()}'
                       f'+{self.overlay.winfo_x()}+{self.overlay.winfo_y()}')

    # ---- window picker ----
    def select_window(self):
        import wincap
        was = self.worker.paused; self.worker.paused = True
        dlg = tk.Toplevel(self.root); dlg.title(self.t('picker_title')); dlg.attributes('-topmost', True)
        dlg.geometry('480x320+200+200')
        tk.Label(dlg, text=self.t('picker_prompt'), anchor='w').pack(fill='x', padx=8, pady=4)
        lb = tk.Listbox(dlg, font=('Microsoft YaHei', 10)); lb.pack(fill='both', expand=True, padx=8, pady=4)
        app_titles = (STRINGS['zh']['app_title'], STRINGS['en']['app_title'])
        wins = [(h, t, e) for h, t, e in wincap.list_windows() if t not in app_titles]
        for h, t, e in wins:
            lb.insert('end', f'{t}    〔{e}〕')
        def pick(_=None):
            i = lb.curselection()
            if i:
                self.win_title = wins[i[0]][1]
                self.win_exe = wins[i[0]][2]
                self._save_cfg(window_title=self.win_title, window_exe=self.win_exe)
                self._upd_winlabel()
                self.status.config(text=self.t('st_winsel', t=self.win_title, e=self.win_exe))
            dlg.destroy(); self.worker.paused = was
        lb.bind('<Double-Button-1>', pick)
        tk.Button(dlg, text=self.t('ok'), command=pick).pack(pady=6)
        dlg.bind('<Escape>', lambda e: (dlg.destroy(), setattr(self.worker, 'paused', was)))

    # ---- region picker (on captured window frame) ----
    def select_region(self):
        import wincap
        from PIL import Image, ImageTk
        if not (self.win_title or self.win_exe):
            self.status.config(text=self.t('st_pickwin')); return
        hwnd = wincap.find_window(self.win_title, self.win_exe)
        if not hwnd:
            self.status.config(text=self.t('st_nofind')); return
        arr = wincap.grab_window(hwnd)
        if arr is None:
            self.status.config(text=self.t('st_grabfail')); return
        H, W = arr.shape[:2]
        scr_w, scr_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        scale = min(1.0, (scr_w - 80) / W, (scr_h - 120) / H)
        disp_w, disp_h = int(W * scale), int(H * scale)
        img = Image.fromarray(arr[:, :, ::-1]).resize((disp_w, disp_h))
        was = self.worker.paused; self.worker.paused = True
        dlg = tk.Toplevel(self.root); dlg.title(self.t('region_title')); dlg.attributes('-topmost', True)
        cv = tk.Canvas(dlg, width=disp_w, height=disp_h, cursor='cross', highlightthickness=0)
        cv.pack()
        photo = ImageTk.PhotoImage(img); cv.create_image(0, 0, anchor='nw', image=photo)
        cv.image = photo
        # show current region
        cv.create_rectangle(self.frac['x']*disp_w, self.frac['y']*disp_h,
                            (self.frac['x']+self.frac['w'])*disp_w,
                            (self.frac['y']+self.frac['h'])*disp_h, outline='#3f3', dash=(4, 2))
        st = {}
        def down(e):
            st['x'], st['y'] = e.x, e.y
            st['r'] = cv.create_rectangle(e.x, e.y, e.x, e.y, outline='#36f', width=2)
        def move(e):
            if 'r' in st: cv.coords(st['r'], st['x'], st['y'], e.x, e.y)
        def up(e):
            if 'x' not in st: return
            x1, y1 = min(st['x'], e.x), min(st['y'], e.y)
            x2, y2 = max(st['x'], e.x), max(st['y'], e.y)
            if x2 - x1 > 6 and y2 - y1 > 6:
                self.frac = {'x': x1/disp_w, 'y': y1/disp_h,
                             'w': (x2-x1)/disp_w, 'h': (y2-y1)/disp_h}
                self._save_cfg(region_frac=self.frac)
                self.status.config(text=self.t('st_region'))
            dlg.destroy(); self.worker.paused = was
        cv.bind('<Button-1>', down); cv.bind('<B1-Motion>', move); cv.bind('<ButtonRelease-1>', up)
        dlg.bind('<Escape>', lambda e: (dlg.destroy(), setattr(self.worker, 'paused', was)))

    def toggle(self):
        if not (self.win_title or self.win_exe):
            self.status.config(text=self.t('st_pickwin')); return
        self.worker.paused = not self.worker.paused
        self.btn_run.config(text=self.t('btn_start' if self.worker.paused else 'btn_pause'))

    def _poll(self):
        try:
            while True:
                msg = self.out_q.get_nowait()
                if 'status' in msg:
                    self.status.config(text=msg['status'])
                else:
                    self.cur = msg; self.refresh()
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def refresh(self):
        self.lbl_zh.config(text=self.cur.get('zh', '').replace('\\n', '\n'))
        if self.show_src.get():
            self.lbl_src.config(text=f"{self.cur.get('jp','')}   〔{self.cur.get('src','')}〕")
        else:
            self.lbl_src.config(text='')

    # ---- config ----
    def _cfg(self):
        try: return json.load(open(CONFIG, encoding='utf-8'))
        except Exception: return {}
    def _save_cfg(self, **kw):
        c = self._cfg(); c.update(kw)
        json.dump(c, open(CONFIG, 'w', encoding='utf-8'), ensure_ascii=False)

    def run(self):
        self.root.mainloop()

if __name__ == '__main__':
    App().run()
