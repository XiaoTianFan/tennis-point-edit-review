"""Run the OS folder chooser on its own main thread; called only by Browse."""
import json
import sys


def choose(initial):
    if sys.platform == 'win32':
        # Set DPI awareness before Tk creates any HWND. This affects only this
        # short-lived picker process, not the user's OS or browser settings.
        import ctypes
        try:
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
            if not user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                raise OSError('Per-monitor v2 context unavailable')
        except (AttributeError, OSError):
            try:
                ctypes.WinDLL('shcore').SetProcessDpiAwareness(2)
            except (AttributeError, OSError):
                ctypes.windll.user32.SetProcessDPIAware()
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    try:
        return filedialog.askdirectory(parent=root, initialdir=initial, mustexist=True)
    finally:
        root.destroy()


if __name__ == '__main__':
    print(json.dumps({'directory': choose(sys.argv[1])}, ensure_ascii=True))
