from __future__ import annotations

import sys
import tkinter as tk


def apply_windows_dpi_awareness() -> None:
    """Call *before* creating the Tk root on Windows to enable crisp DPI rendering.

    On Windows 10/11 with display scaling > 100 %, without this the OS upscales the
    application bitmap and everything looks blurry.  The call is a no-op on
    non-Windows platforms.
    """
    if sys.platform != "win32":
        return
    try:
        from ctypes import windll
        try:
            # Per-monitor DPI awareness (Windows 8.1+)
            windll.shcore.SetProcessDpiAwareness(1)
        except AttributeError:
            # Fallback for Windows Vista/7
            windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def get_dpi_scale(root: tk.Tk) -> float:
    """Return the display DPI scale factor derived from *root*.

    A standard 96 DPI display returns 1.0.  A 125 % scaled display returns ≈ 1.25,
    a 150 % scaled display returns ≈ 1.5, etc.
    """
    try:
        pixels_per_inch = root.winfo_fpixels("1i")
        return max(1.0, pixels_per_inch / 96.0)
    except Exception:
        return 1.0


def scaled_size(base: int, scale: float) -> int:
    """Return *base* scaled by *scale*, clamped to a minimum of 1."""
    return max(1, int(base * scale))
