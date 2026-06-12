"""OBS-style per-window capture (Windows). Captures a specific HWND's client
area via PrintWindow (works when the window is occluded / moved), with a
screen-grab fallback for D3D windows that return black."""
import os
import numpy as np
import win32gui, win32ui
import ctypes
from ctypes import windll, wintypes

PW_RENDERFULLCONTENT = 2

def window_exe(hwnd):
    """Basename of the exe that owns hwnd, e.g. 'lingeries.exe' (or None)."""
    pid = wintypes.DWORD()
    windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = windll.kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(512)
        size = wintypes.DWORD(512)
        if windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
    finally:
        windll.kernel32.CloseHandle(h)
    return None

def list_windows():
    """[(hwnd, title, exe)] for visible, titled top-level windows."""
    out = []
    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            t = win32gui.GetWindowText(h)
            if t.strip():
                out.append((h, t, window_exe(h) or ''))
    win32gui.EnumWindows(cb, None)
    return out

def find_window(title=None, exe=None):
    """Locate the target window. Prefer exe match (unique & stable), then exact
    title, then title substring -- so 'Lingeries' won't grab 'Lingeries - VS Code'."""
    wins = list_windows()
    if exe:
        exe = exe.lower()
        for h, t, e in wins:
            if e == exe:
                return h
    if title:
        for h, t, e in wins:          # exact title
            if t == title:
                return h
        for h, t, e in wins:          # substring fallback
            if title.lower() in t.lower():
                return h
    return None

def client_size(hwnd):
    l, t, r, b = win32gui.GetClientRect(hwnd)
    return r - l, b - t

def _printwindow(hwnd):
    w, h = client_size(hwnd)
    if w <= 0 or h <= 0:
        return None
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(bmp)
    ok = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)
    bits = bmp.GetBitmapBits(True)
    arr = np.frombuffer(bits, dtype=np.uint8).reshape(h, w, 4).copy()  # BGRA
    win32gui.DeleteObject(bmp.GetHandle())
    saveDC.DeleteDC(); mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    if not ok:
        return None
    return arr[:, :, :3]  # BGR

def _screengrab(hwnd):
    """Fallback: grab the window's screen rectangle (requires it be on top)."""
    import mss
    l, t, r, b = win32gui.GetClientRect(hwnd)
    # client (0,0) -> screen coords
    sx, sy = win32gui.ClientToScreen(hwnd, (0, 0))
    with mss.mss() as sct:
        raw = sct.grab({'left': sx, 'top': sy, 'width': r - l, 'height': b - t})
    return np.asarray(raw)[:, :, :3]

def grab_window(hwnd, force_screen=False):
    """Return BGR ndarray of the window client area, or None."""
    if not force_screen:
        arr = _printwindow(hwnd)
        if arr is not None and arr.size and arr.std() > 3:  # not all-black/uniform
            return arr
    try:
        return _screengrab(hwnd)
    except Exception:
        return None

if __name__ == '__main__':
    import sys
    from PIL import Image
    h = find_window('Lingeries')
    print('hwnd', hex(h) if h else None, 'client', client_size(h) if h else None)
    pw = _printwindow(h)
    print('PrintWindow:', None if pw is None else f'{pw.shape} std={pw.std():.1f}')
    if pw is not None:
        Image.fromarray(pw[:, :, ::-1]).save('overlay/_cap_printwindow.png')
    try:
        sg = _screengrab(h)
        print('ScreenGrab :', f'{sg.shape} std={sg.std():.1f}')
        Image.fromarray(sg[:, :, ::-1]).save('overlay/_cap_screengrab.png')
    except Exception as e:
        print('ScreenGrab : fail', e)
