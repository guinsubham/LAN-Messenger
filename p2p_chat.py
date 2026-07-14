import json
import hashlib
import ctypes
import os
import queue
import re
import socket
import struct
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
from tkinter import (
    BOTH,
    Canvas,
    END,
    LEFT,
    PhotoImage,
    RIGHT,
    TOP,
    TclError,
    X,
    Y,
    Button,
    Entry,
    Frame,
    Label,
    Menu,
    Scrollbar,
    Text,
    Tk,
    Toplevel,
    filedialog,
    messagebox,
    simpledialog,
)

try:
    if sys.platform == "darwin":
        raise ImportError("menu-bar tray is disabled on macOS builds")
    import pystray
    from PIL import Image, ImageDraw

    TRAY_AVAILABLE = True
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None
    TRAY_AVAILABLE = False

try:
    if sys.platform == "darwin":
        raise ImportError("drag-and-drop extension is disabled on macOS builds")
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DND_AVAILABLE = True
except ImportError:
    DND_FILES = None
    TkinterDnD = None
    DND_AVAILABLE = False

try:
    from PIL import Image as PILImage, ImageSequence, ImageTk

    TYPING_IMAGE_AVAILABLE = True
except ImportError:
    PILImage = None
    ImageSequence = None
    ImageTk = None
    TYPING_IMAGE_AVAILABLE = False


APP_NAME = "LAN Messenger"
APP_VERSION = "1.0.61"
APP_MUTEX_HANDLE = None
STARTUP_ARG = "--startup"
UPDATED_CHILD_ARG = "--updated-child"
SETTLED_ARG = "--settled-child"
TYPING_TIMEOUT_MS = 3000
TYPING_SEND_INTERVAL = 1.0
AUTO_AFK_SECONDS = 5 * 60
AUTO_OFFLINE_SECONDS = 10 * 60
IDLE_CHECK_INTERVAL_MS = 10_000
SOUND_FILES = {
    "incoming_message": "Incoming_msg.wav",
    "file_received": "File_received.wav",
    "new_user_online": "New_User_Online.wav",
}
FONT_FAMILY = "Consolas" if os.name == "nt" else "Menlo"
FONT_NORMAL = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_TITLE = (FONT_FAMILY, 13, "bold")
FONT_BOLD = (FONT_FAMILY, 10, "bold")
CHAT_FONT_NORMAL = (FONT_FAMILY, 12)
CHAT_FONT_BOLD = (FONT_FAMILY, 12, "bold")
BUTTON_RADIUS = 10
STATUS_VALUES = ["Available", "AFK", "Offline"]
STATUS_COLORS = {
    "Available": "#2ecc71",
    "AFK": "#f39c12",
    "Offline": "#e74c3c",
}
DISCOVERY_GROUP = "224.7.7.7"
DISCOVERY_PORT = 45777
DISCOVERY_BROADCAST_HOST = "255.255.255.255"
TCP_PORT = 45778
BUFFER_SIZE = 64 * 1024
MAX_HEADER_SIZE = 10 * 1024 * 1024
EMOJIS = [
    "\U0001f600",
    "\U0001f601",
    "\U0001f602",
    "\U0001f60a",
    "\U0001f60d",
    "\U0001f60e",
    "\U0001f44d",
    "\U0001f64f",
    "\U0001f44f",
    "\U0001f389",
    "\u2764\ufe0f",
    "\U0001f525",
    "\u2705",
    "\u274c",
    "\u26a0\ufe0f",
    "\U0001f4ce",
    "\U0001f4c1",
    "\U0001f4ac",
]
LIGHT_THEME = {
    "window": "#f6f7f9",
    "panel": "#ffffff",
    "header": "#f6f7f9",
    "header_text": "#111827",
    "text_bg": "#ffffff",
    "text_fg": "#111827",
    "entry_bg": "#ffffff",
    "entry_fg": "#111827",
    "button_bg": "#e8edf3",
    "button_fg": "#111827",
    "select_bg": "#2563eb",
    "select_fg": "#ffffff",
    "border": "#d6dde6",
}
DARK_THEME = {
    "window": "#0f1115",
    "panel": "#171a21",
    "header": "#090b10",
    "header_text": "#f9fafb",
    "text_bg": "#111318",
    "text_fg": "#e5e7eb",
    "entry_bg": "#0b0d12",
    "entry_fg": "#f9fafb",
    "button_bg": "#262b36",
    "button_fg": "#f9fafb",
    "select_bg": "#3b82f6",
    "select_fg": "#ffffff",
    "border": "#2f3541",
}


def _colorref(hex_color):
    value = hex_color.lstrip("#")
    red = int(value[0:2], 16)
    green = int(value[2:4], 16)
    blue = int(value[4:6], 16)
    return red | (green << 8) | (blue << 16)


def apply_title_bar_theme(window, dark_mode):
    if os.name != "nt":
        return
    try:
        import ctypes

        window.update_idletasks()
        user32 = ctypes.windll.user32
        handles = []
        for raw_handle in (
            window.winfo_id(),
            window.tk.call("wm", "frame", window._w),
        ):
            try:
                handle = int(raw_handle, 0) if isinstance(raw_handle, str) else int(raw_handle)
            except Exception:
                continue
            handles.append(handle)
            for related in (
                user32.GetParent(handle),
                user32.GetAncestor(handle, 2),
            ):
                if related:
                    handles.append(int(related))

        enabled = ctypes.c_int(1 if dark_mode else 0)
        theme = DARK_THEME if dark_mode else LIGHT_THEME
        color_values = {
            34: theme["border"],
            35: theme["header"] if dark_mode else theme["window"],
            36: theme["text_fg"],
        }
        for handle in dict.fromkeys(handles):
            hwnd = ctypes.c_void_p(handle)
            for attribute in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attribute,
                    ctypes.byref(enabled),
                    ctypes.sizeof(enabled),
                )
            for attribute, hex_color in color_values.items():
                color = ctypes.c_int(_colorref(hex_color))
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attribute,
                    ctypes.byref(color),
                    ctypes.sizeof(color),
                )
            user32.RedrawWindow(hwnd, None, None, 0x0400 | 0x0100 | 0x0001)
    except Exception:
        pass


def schedule_title_bar_theme(window, dark_mode):
    apply_title_bar_theme(window, dark_mode)
    for delay in (80, 250, 600):
        try:
            window.after(delay, lambda target=window, dark=dark_mode: apply_title_bar_theme(target, dark))
        except Exception:
            break


def show_themed_info(parent, title, message, dark_mode):
    theme = DARK_THEME if dark_mode else LIGHT_THEME
    dialog = Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.resizable(False, False)
    dialog.configure(bg=theme["window"])
    schedule_title_bar_theme(dialog, dark_mode)

    panel = Frame(dialog, padx=24, pady=22, bg=theme["window"])
    panel.pack(fill=BOTH, expand=True)

    message_label = Label(
        panel,
        text=message,
        font=FONT_NORMAL,
        bg=theme["window"],
        fg=theme["text_fg"],
        justify=LEFT,
        wraplength=310,
    )
    message_label.pack(anchor="w", pady=(0, 18))

    ok_button = Button(
        panel,
        text="OK",
        width=10,
        command=dialog.destroy,
        bg=theme["button_bg"],
        fg=theme["button_fg"],
        activebackground=theme["select_bg"],
        activeforeground=theme["select_fg"],
    )
    ok_button.pack(anchor="e")

    dialog.update_idletasks()
    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_w = parent.winfo_width()
    parent_h = parent.winfo_height()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = parent_x + max(0, (parent_w - width) // 2)
    y = parent_y + max(0, (parent_h - height) // 2)
    dialog.geometry(f"+{x}+{y}")
    dialog.grab_set()
    ok_button.focus_set()
    dialog.wait_window()


class RoundedButton(Canvas):
    def __init__(self, master=None, text="", command=None, width=None, **kwargs):
        self.command = command
        self.text = text
        self.bg_color = kwargs.pop("bg", LIGHT_THEME["button_bg"])
        self.fg_color = kwargs.pop("fg", LIGHT_THEME["button_fg"])
        self.active_bg = kwargs.pop("activebackground", LIGHT_THEME["select_bg"])
        self.active_fg = kwargs.pop("activeforeground", LIGHT_THEME["select_fg"])
        self.font = kwargs.pop("font", FONT_NORMAL)
        self.radius = kwargs.pop("radius", BUTTON_RADIUS)
        char_width = max(width or len(text), 4)
        pixel_width = kwargs.pop("pixel_width", max(72, char_width * 10 + 24))
        pixel_height = kwargs.pop("pixel_height", 32)
        super().__init__(
            master,
            width=pixel_width,
            height=pixel_height,
            highlightthickness=0,
            bd=0,
            bg=master.cget("bg") if master else LIGHT_THEME["panel"],
        )
        self.pixel_width = pixel_width
        self.pixel_height = pixel_height
        self._hover = False
        self._draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def configure(self, cnf=None, **kwargs):
        options = {}
        if cnf:
            options.update(cnf)
        options.update(kwargs)

        if "text" in options:
            self.text = options.pop("text")
        if "command" in options:
            self.command = options.pop("command")
        if "bg" in options:
            self.bg_color = options.pop("bg")
        if "fg" in options:
            self.fg_color = options.pop("fg")
        if "activebackground" in options:
            self.active_bg = options.pop("activebackground")
        if "activeforeground" in options:
            self.active_fg = options.pop("activeforeground")
        if "font" in options:
            self.font = options.pop("font")
        if "width" in options:
            char_width = options.pop("width")
            self.pixel_width = max(72, int(char_width) * 10 + 24)
            super().configure(width=self.pixel_width)
        if "background" in options:
            self.bg_color = options.pop("background")
        super().configure(**options)
        self._draw()

    config = configure

    def _draw(self):
        try:
            super().configure(bg=self.master.cget("bg"))
        except Exception:
            pass
        self.delete("all")
        fill = self.active_bg if self._hover else self.bg_color
        text_fill = self.active_fg if self._hover else self.fg_color
        self._rounded_rect(1, 1, self.pixel_width - 1, self.pixel_height - 1, self.radius, fill)
        self.create_text(
            self.pixel_width // 2,
            self.pixel_height // 2,
            text=self.text,
            fill=text_fill,
            font=self.font,
        )

    def _rounded_rect(self, x1, y1, x2, y2, radius, fill):
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        self.create_polygon(points, smooth=True, fill=fill, outline="")

    def _on_enter(self, _event):
        self._hover = True
        self.configure(cursor="hand2")
        self._draw()

    def _on_leave(self, _event):
        self._hover = False
        self.configure(cursor="")
        self._draw()

    def _on_click(self, _event):
        if self.command:
            self.command()


Button = RoundedButton


class ThemeToggle(Canvas):
    def __init__(self, master=None, command=None, dark=False):
        self.command = command
        self.dark = dark
        self.pixel_width = 45
        self.pixel_height = 22
        self.knob_position = 1.0 if dark else 0.0
        self._animating = False
        super().__init__(
            master,
            width=self.pixel_width,
            height=self.pixel_height,
            highlightthickness=0,
            bd=0,
            bg=master.cget("bg") if master else LIGHT_THEME["header"],
        )
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda _event: self.configure(cursor="hand2"))
        self.bind("<Leave>", lambda _event: self.configure(cursor=""))
        self._draw()

    def set_dark(self, dark):
        if self.dark == dark and not self._animating:
            self._draw()
            return
        self.dark = dark
        self._animate_to(1.0 if dark else 0.0)

    def configure(self, cnf=None, **kwargs):
        if "bg" in kwargs:
            super().configure(bg=kwargs.pop("bg"))
        if "background" in kwargs:
            super().configure(bg=kwargs.pop("background"))
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        super().configure(**kwargs)
        self._draw()

    config = configure

    def _on_click(self, _event):
        if self.command:
            self.command()

    def _animate_to(self, target):
        if self._animating:
            self.knob_position = target
            self._draw()
            return
        start = self.knob_position
        distance = target - start
        steps = 10
        self._animating = True

        def tick(step=1):
            t = step / steps
            eased = t * t * (3 - 2 * t)
            self.knob_position = start + distance * eased
            self._draw()
            if step < steps:
                self.after(14, lambda: tick(step + 1))
            else:
                self.knob_position = target
                self._animating = False
                self._draw()

        tick()

    def _draw(self):
        self.delete("all")
        try:
            super().configure(bg=self.master.cget("bg"))
        except Exception:
            pass

        border = "#153242"
        yellow = "#ffd91f"
        light_track = "#ffffff"
        dark_track = border
        position = max(0.0, min(1.0, self.knob_position))
        track = self._mix_color(light_track, dark_track, position)
        self._pill(1, 1, self.pixel_width - 1, self.pixel_height - 1, fill=border)
        self._pill(3, 3, self.pixel_width - 3, self.pixel_height - 3, fill=track)

        if position < 0.72:
            self._draw_sun(13, 11, yellow, scale=0.72)
        if position > 0.28:
            self._draw_moon(32, 11, yellow, track, scale=0.62)

        knob_start = 34
        knob_end = 11
        knob_x = knob_start + (knob_end - knob_start) * position
        knob_color = self._mix_color(border, "#ffffff", position)
        self.create_oval(knob_x - 8, 3, knob_x + 8, 19, fill=knob_color, outline="")

    def _pill(self, x1, y1, x2, y2, fill):
        radius = (y2 - y1) / 2
        self.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline="")
        self.create_oval(x1, y1, x1 + radius * 2, y2, fill=fill, outline="")
        self.create_oval(x2 - radius * 2, y1, x2, y2, fill=fill, outline="")

    def _rounded_rect(self, x1, y1, x2, y2, radius, fill, outline, width):
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        self.create_polygon(points, smooth=True, fill=fill, outline=outline, width=width)

    def _draw_sun(self, cx, cy, color, scale=1.0):
        r = 4.4 * scale
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")

    def _draw_moon(self, cx, cy, color, mask, scale=1.0):
        r = 7 * scale
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")
        self.create_oval(cx + 1.8 * scale, cy - 7 * scale, cx + 10 * scale, cy + 7 * scale, fill=mask, outline="")

    def _mix_color(self, left, right, amount):
        amount = max(0.0, min(1.0, amount))
        l = tuple(int(left[index:index + 2], 16) for index in (1, 3, 5))
        r = tuple(int(right[index:index + 2], 16) for index in (1, 3, 5))
        mixed = tuple(int(lc + (rc - lc) * amount) for lc, rc in zip(l, r))
        return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"


class StatusSelector(Canvas):
    def __init__(self, master=None, value="Available", command=None):
        self.value = value if value in STATUS_VALUES else "Available"
        self.command = command
        self.pixel_width = 118
        self.pixel_height = 24
        self.theme = LIGHT_THEME
        super().__init__(
            master,
            width=self.pixel_width,
            height=self.pixel_height,
            highlightthickness=0,
            bd=0,
            bg=master.cget("bg") if master else LIGHT_THEME["header"],
        )
        self.menu = Menu(self, tearoff=0)
        self.bind("<Button-1>", self._show_menu)
        self.bind("<Enter>", lambda _event: self.configure(cursor="hand2"))
        self.bind("<Leave>", lambda _event: self.configure(cursor=""))
        self._rebuild_menu()
        self._draw()

    def set_value(self, value):
        self.value = value if value in STATUS_VALUES else "Available"
        self._draw()

    def configure_theme(self, theme, header_bg):
        self.theme = theme
        super().configure(bg=header_bg)
        self.menu.configure(
            bg=theme["panel"],
            fg=theme["text_fg"],
            activebackground=theme["select_bg"],
            activeforeground=theme["select_fg"],
            font=FONT_NORMAL,
        )
        self._draw()

    def _rebuild_menu(self):
        self.menu.delete(0, END)
        for status in STATUS_VALUES:
            self.menu.add_command(label=status, command=lambda selected=status: self._select(selected))
            index = self.menu.index(END)
            self.menu.entryconfigure(index, foreground=STATUS_COLORS[status])

    def _select(self, status):
        self.set_value(status)
        if self.command:
            self.command(status)

    def _show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def _draw(self):
        self.delete("all")
        theme = self.theme
        self._pill(0, 0, self.pixel_width, self.pixel_height, theme["button_bg"])
        self.create_oval(10, 8, 18, 16, fill=STATUS_COLORS[self.value], outline="")
        self.create_text(25, 12, text=self.value, anchor="w", fill=theme["button_fg"], font=FONT_NORMAL)
        self.create_line(101, 10, 106, 15, 111, 10, fill=theme["button_fg"], width=1)

    def _pill(self, x1, y1, x2, y2, fill):
        radius = (y2 - y1) / 2
        self.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline="")
        self.create_oval(x1, y1, x1 + radius * 2, y2, fill=fill, outline="")
        self.create_oval(x2 - radius * 2, y1, x2, y2, fill=fill, outline="")


class PeerList(Canvas):
    def __init__(self, master=None, open_command=None):
        super().__init__(
            master,
            highlightthickness=1,
            bd=0,
            takefocus=True,
            bg=LIGHT_THEME["text_bg"],
        )
        self.open_command = open_command
        self.theme = LIGHT_THEME
        self.rows = []
        self.unread_counts = {}
        self.selected_index = None
        self.row_height = 25
        self.bind("<Button-1>", self._on_click)
        self.bind("<Double-Button-1>", self._on_double_click)
        self.bind("<Return>", self._on_return)
        self.bind("<Configure>", lambda _event: self._draw())

    def configure_theme(self, theme):
        self.theme = theme
        self.configure(
            bg=theme["text_bg"],
            highlightbackground=theme["border"],
            highlightcolor=theme["select_bg"],
        )
        self._draw()

    def set_rows(self, rows, unread_counts, selected_id=None):
        self.rows = list(rows)
        self.unread_counts = dict(unread_counts)
        self.selected_index = None
        if selected_id:
            for index, peer in enumerate(self.rows):
                if peer.get("id") == selected_id:
                    self.selected_index = index
                    break
        self._draw()

    def curselection(self):
        if self.selected_index is None:
            return ()
        return (self.selected_index,)

    def selection_set(self, index):
        if 0 <= index < len(self.rows):
            self.selected_index = index
            self._draw()

    def _on_click(self, event):
        self.focus_set()
        index = event.y // self.row_height
        if 0 <= index < len(self.rows):
            self.selected_index = int(index)
            self._draw()

    def _on_double_click(self, _event):
        if self.open_command:
            self.open_command()

    def _on_return(self, _event):
        if self.open_command:
            self.open_command()
        return "break"

    def _draw(self):
        self.delete("all")
        width = max(1, self.winfo_width())
        for index, peer in enumerate(self.rows):
            y1 = index * self.row_height
            y2 = y1 + self.row_height
            selected = index == self.selected_index
            if selected:
                self.create_rectangle(0, y1, width, y2, fill=self.theme["select_bg"], outline="")
                text_color = self.theme["select_fg"]
            else:
                text_color = self.theme["text_fg"]

            center_y = y1 + self.row_height // 2
            status = peer.get("status", "Available")
            dot_color = STATUS_COLORS.get(status, STATUS_COLORS["Available"])
            self.create_oval(9, center_y - 4, 17, center_y + 4, fill=dot_color, outline="")

            unread = self.unread_counts.get(peer.get("id"), 0)
            badge = f" ({unread})" if unread else ""
            self.create_text(
                30,
                center_y,
                text=f"{peer.get('name', 'Unknown')}{badge}",
                anchor="w",
                fill=text_color,
                font=FONT_NORMAL,
            )

        self.configure(scrollregion=(0, 0, width, max(self.winfo_height(), len(self.rows) * self.row_height)))


class TrayController:
    def __init__(self, app):
        self.app = app
        self.icon = None

    def start(self):
        if not TRAY_AVAILABLE or self.icon:
            return False
        menu = pystray.Menu(
            pystray.MenuItem("Show LAN Messenger", self._show, default=True),
            pystray.MenuItem("Quit", self._quit),
        )
        self.icon = pystray.Icon(APP_NAME, self._image(), APP_NAME, menu)
        if hasattr(self.icon, "run_detached"):
            self.icon.run_detached()
        else:
            threading.Thread(target=self.icon.run, daemon=True).start()
        return True

    def stop(self):
        if self.icon:
            icon = self.icon
            self.icon = None
            icon.stop()

    def _show(self, _icon=None, _item=None):
        self.app.root.after(0, self.app.show_window)

    def _quit(self, _icon=None, _item=None):
        self.app.root.after(0, self.app.quit_app)

    def _image(self):
        icon_path = resource_path("assets", "app_icon.png")
        if icon_path.exists():
            return Image.open(icon_path).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((10, 12, 54, 50), radius=12, fill="#111827")
        draw.ellipse((17, 19, 31, 33), fill="#2ecc71")
        draw.rounded_rectangle((28, 24, 48, 38), radius=5, fill="#ffffff")
        return image


def get_app_data_dir():
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
        candidates = [base / "LANMessenger", Path.home() / "Documents" / "LANMessenger"]
    elif os.uname().sysname == "Darwin":
        candidates = [Path.home() / "Library" / "Application Support" / "LANMessenger", Path.home() / "Documents" / "LANMessenger"]
    else:
        candidates = [Path.home() / ".lan_messenger", Path.home() / "Documents" / "LANMessenger"]

    candidates.append(Path.cwd() / "LANMessengerData")
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except OSError:
            continue
    return Path.cwd()


def get_identity_path():
    return get_app_data_dir() / "identity.json"


def load_identity():
    identity_path = get_identity_path()
    try:
        with open(identity_path, "r", encoding="utf-8") as source:
            data = json.load(source)
            if isinstance(data, dict):
                return data
    except (OSError, ValueError):
        pass
    return {}


def save_identity(identity):
    existing = load_identity()
    existing.update(identity)
    if not existing.get("peer_id"):
        existing["peer_id"] = str(uuid.uuid4())
    try:
        with open(get_identity_path(), "w", encoding="utf-8") as output:
            json.dump(existing, output, indent=2)
    except OSError:
        pass
    return existing


def load_or_create_peer_id():
    identity = load_identity()
    peer_id = identity.get("peer_id")
    if peer_id:
        return peer_id
    return save_identity({"peer_id": str(uuid.uuid4())})["peer_id"]


def load_saved_display_name():
    name = load_identity().get("display_name")
    if isinstance(name, str):
        name = name.strip()
        if name:
            return name
    return None


def save_display_name(name):
    name = name.strip() if isinstance(name, str) else ""
    if name:
        save_identity({"display_name": name})


def version_tuple(version):
    numbers = []
    for part in str(version).split("."):
        match = re.match(r"(\d+)", part)
        numbers.append(int(match.group(1)) if match else 0)
    while len(numbers) < 4:
        numbers.append(0)
    return tuple(numbers[:4])


def is_newer_version(candidate, current=APP_VERSION):
    return version_tuple(candidate) > version_tuple(current)


def current_update_platform():
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "source"


def current_update_package():
    if getattr(sys, "frozen", False):
        package = Path(sys.executable)
    else:
        package = Path(__file__).resolve()
    return package if package.exists() else None


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while True:
            chunk = source.read(BUFFER_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def get_app_install_dir():
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "LAN Messenger"
    if sys.platform == "darwin":
        return Path.home() / "Applications" / "LAN Messenger"
    return Path.home() / ".local" / "share" / "LAN Messenger"


def get_app_install_path():
    suffix = ".exe" if os.name == "nt" else ""
    return get_app_install_dir() / f"LANMessenger{suffix}"


def acquire_single_instance_lock():
    global APP_MUTEX_HANDLE
    if os.name != "nt":
        return True
    kernel32 = ctypes.windll.kernel32
    APP_MUTEX_HANDLE = kernel32.CreateMutexW(None, False, "Local\\LANMessengerSingleInstance")
    if not APP_MUTEX_HANDLE:
        return True
    return kernel32.GetLastError() != 183


def ensure_installed_location():
    if not getattr(sys, "frozen", False):
        return False
    if SETTLED_ARG in sys.argv[1:] or UPDATED_CHILD_ARG in sys.argv[1:]:
        return False
    current_path = Path(sys.executable).resolve()
    target_path = get_app_install_path()
    try:
        if current_path == target_path.resolve():
            return False
    except OSError:
        pass
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if not target_path.exists() or current_path.stat().st_mtime > target_path.stat().st_mtime:
            import shutil

            shutil.copy2(current_path, target_path)
        args = [arg for arg in sys.argv[1:] if arg != SETTLED_ARG]
        subprocess.Popen([str(target_path)] + args + [SETTLED_ARG], cwd=str(target_path.parent))
        return True
    except OSError:
        return False


def get_updates_dir():
    path = get_app_data_dir() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_pending_update(version, path, platform, size=None, sha256=None):
    save_identity(
        {
            "pending_update": {
                "version": version,
                "path": str(path),
                "platform": platform,
                "size": size,
                "sha256": sha256,
            }
        }
    )


def clear_pending_update():
    save_identity({"pending_update": None})


def _windows_update_launcher(downloaded_path, current_path, expected_size=None):
    script_path = get_updates_dir() / "apply_update.bat"
    size_check = ""
    if expected_size:
        size_check = f"""for %%A in ("%SOURCE%") do set "SOURCE_SIZE=%%~zA"
if not "%SOURCE_SIZE%"=="{int(expected_size)}" (
  start "" /D "%TARGET_DIR%" "%SOURCE%" {UPDATED_CHILD_ARG}
  exit /b 2
)
"""
    script = f"""@echo off
setlocal
set "PID={os.getpid()}"
set "SOURCE={downloaded_path}"
set "TARGET={current_path}"
for %%A in ("%TARGET%") do set "TARGET_DIR=%%~dpA"
:wait_app
tasklist /FI "PID eq %PID%" | find "%PID%" >nul
if not errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto wait_app
)
{size_check}
copy /Y "%SOURCE%" "%TARGET%" >nul
if errorlevel 1 (
  start "" /D "%TARGET_DIR%" "%SOURCE%" {UPDATED_CHILD_ARG}
  exit /b 1
)
start "" /D "%TARGET_DIR%" "%TARGET%" {UPDATED_CHILD_ARG}
"""
    script_path.write_text(script, encoding="utf-8")
    return script_path


def maybe_launch_pending_update():
    if UPDATED_CHILD_ARG in sys.argv[1:]:
        clear_pending_update()
        return False
    pending = load_identity().get("pending_update")
    if not isinstance(pending, dict):
        return False
    if pending.get("platform") != current_update_platform():
        return False
    if not is_newer_version(pending.get("version", "0.0.0")):
        return False
    path = Path(pending.get("path", ""))
    if not path.exists():
        return False
    expected_size = pending.get("size")
    if expected_size and path.stat().st_size != int(expected_size):
        return False
    expected_hash = pending.get("sha256")
    if expected_hash and file_sha256(path).lower() != str(expected_hash).lower():
        return False
    current_exe = Path(sys.executable).resolve()
    if getattr(sys, "frozen", False):
        if path.resolve() == current_exe:
            return False
        if sys.platform.startswith("win"):
            launcher = _windows_update_launcher(path.resolve(), current_exe, expected_size)
            subprocess.Popen([str(launcher)], cwd=str(launcher.parent), creationflags=subprocess.CREATE_NO_WINDOW)
            return True
        command = [str(path)]
    else:
        command = [sys.executable, str(path)]
    args = [arg for arg in sys.argv[1:] if arg != UPDATED_CHILD_ARG]
    subprocess.Popen(command + args + [UPDATED_CHILD_ARG], cwd=str(path.parent))
    return True


def should_prompt_startup():
    return not bool(load_identity().get("startup_prompted"))


def mark_startup_prompted():
    save_identity({"startup_prompted": True})


def app_launch_command():
    if getattr(sys, "frozen", False):
        installed_path = get_app_install_path()
        return [str(installed_path if installed_path.exists() else Path(sys.executable))]
    return [sys.executable, str(Path(__file__).resolve())]


def enable_startup():
    command = app_launch_command() + [STARTUP_ARG]
    if os.name == "nt":
        startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        startup_dir.mkdir(parents=True, exist_ok=True)
        shortcut_path = startup_dir / f"{APP_NAME}.lnk"
        ps_command = (
            "$shell = New-Object -ComObject WScript.Shell; "
            f"$shortcut = $shell.CreateShortcut('{str(shortcut_path)}'); "
            f"$shortcut.TargetPath = '{command[0]}'; "
            f"$shortcut.Arguments = '{' '.join(command[1:])}'; "
            f"$shortcut.WorkingDirectory = '{str(Path(command[0]).parent)}'; "
            "$shortcut.Save()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True

    if sys.platform == "darwin":
        launch_agents = Path.home() / "Library" / "LaunchAgents"
        launch_agents.mkdir(parents=True, exist_ok=True)
        plist_path = launch_agents / "com.lanmessenger.startup.plist"
        args = "\n".join(f"        <string>{arg}</string>" for arg in command)
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.lanmessenger.startup</string>
    <key>ProgramArguments</key>
    <array>
{args}
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
        plist_path.write_text(plist, encoding="utf-8")
        subprocess.run(["launchctl", "unload", str(plist_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["launchctl", "load", str(plist_path)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    return False


def refresh_startup_shortcut_if_present():
    if os.name != "nt":
        return
    startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    shortcut_path = startup_dir / f"{APP_NAME}.lnk"
    if not shortcut_path.exists():
        return
    try:
        enable_startup()
    except Exception:
        pass


def get_download_dir():
    candidates = [
        Path.home() / "Documents" / "LAN Messenger",
        Path.home() / "Downloads" / "LAN Messenger",
        get_app_data_dir() / "Received Files",
    ]
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except OSError:
            continue
    return get_app_data_dir()


def get_received_file_dir(sender):
    sender_name = safe_filename(sender).replace(" ", "_")
    date_label = time.strftime("%d_%m_%Y")
    target_dir = get_download_dir() / f"{sender_name}_{date_label}"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def resource_path(*parts):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def load_window_icon():
    icon_path = resource_path("assets", "app_icon.png")
    if not icon_path.exists():
        return None
    try:
        return PhotoImage(file=str(icon_path))
    except TclError:
        return None


def play_sound(sound_key):
    filename = SOUND_FILES.get(sound_key)
    if not filename:
        return
    sound_path = resource_path("assets", filename)
    if not sound_path.exists():
        return

    def worker():
        try:
            if os.name == "nt":
                import winsound

                winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif sys.platform == "darwin":
                subprocess.Popen(["afplay", str(sound_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                for player in ("paplay", "aplay", "ffplay"):
                    try:
                        args = [player, "-nodisp", "-autoexit", str(sound_path)] if player == "ffplay" else [player, str(sound_path)]
                        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        break
                    except OSError:
                        continue
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()


def local_ip():
    return local_ipv4_addresses()[0]


def is_usable_lan_ip(value):
    parts = value.split(".")
    if len(parts) != 4 or not all(part.isdigit() for part in parts):
        return False
    octets = [int(part) for part in parts]
    if octets[0] in {0, 127}:
        return False
    if octets[0] == 169 and octets[1] == 254:
        return False
    if octets[0] == 10:
        return True
    if octets[0] == 192 and octets[1] == 168:
        return True
    if octets[0] == 172 and 16 <= octets[1] <= 31:
        return True
    if octets[0] == 100 and 64 <= octets[1] <= 127:
        return True
    return False


def local_ipv4_addresses():
    addresses = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            addresses.append(sock.getsockname()[0])
        finally:
            sock.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.append(info[4][0])
    except OSError:
        pass
    usable = []
    for address in addresses:
        if is_usable_lan_ip(address) and address not in usable:
            usable.append(address)
    return usable or ["127.0.0.1"]


def discovery_targets(host_ip):
    targets = {(DISCOVERY_GROUP, DISCOVERY_PORT), (DISCOVERY_BROADCAST_HOST, DISCOVERY_PORT)}
    parts = host_ip.split(".")
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        targets.add((".".join(parts[:3] + ["255"]), DISCOVERY_PORT))
    return sorted(targets)


def safe_filename(name):
    cleaned = "".join(ch if ch not in '<>:"/\\|?*' else "_" for ch in name)
    return cleaned.strip() or "received_file"


def now_label():
    return time.strftime("%H:%M")


def today_label():
    return time.strftime("%Y-%m-%d")


def system_idle_seconds(fallback_last_activity):
    if os.name != "nt":
        return max(0, time.time() - fallback_last_activity)
    try:
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return max(0, time.time() - fallback_last_activity)
        tick_count = ctypes.windll.kernel32.GetTickCount()
        return max(0, (tick_count - info.dwTime) / 1000.0)
    except Exception:
        return max(0, time.time() - fallback_last_activity)


URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>'\"]+")
FILE_URL_RE = re.compile(r"(?i)\bfile://[^\s<>'\"]+")
WINDOWS_PATH_RE = re.compile(r"(?<!\w)(?:[A-Za-z]:[\\/][^\n<>:\"|?*]+|\\\\[^\s\\/:*?\"<>|]+\\[^\n:*?\"<>|]+|//[^\s/:*?\"<>|]+/[^\n:*?\"<>|]+)")
UNIX_PATH_RE = re.compile(r"(?<!\w)/(?:Users|Volumes|Applications|tmp|var|private|home)/[^\s<>'\"]+")
QUOTED_PATH_RE = re.compile(r"(['\"])(?P<path>(?:file://|[A-Za-z]:[\\/]|\\\\|//|/(?:Users|Volumes|Applications|tmp|var|private|home)/)[^'\"]+)\1")
TRAILING_LINK_CHARS = ".,;:!?)]}"
COMMON_FILE_EXTENSIONS = {
    "7z", "csv", "doc", "docx", "dwg", "gif", "heic", "jpeg", "jpg", "mov", "mp3", "mp4",
    "pdf", "png", "ppt", "pptx", "rar", "rtf", "txt", "wav", "xls", "xlsm", "xlsx", "zip",
}


def _trim_target(text, start, end):
    while end > start and text[end - 1] in TRAILING_LINK_CHARS:
        end -= 1
    return start, end, text[start:end]


def normalize_file_target(value):
    value = value.strip().strip("\"'").rstrip(TRAILING_LINK_CHARS + " ")
    if value.lower().startswith("file://"):
        parsed = urlparse(value)
        path = unquote(parsed.path or "")
        if sys.platform.startswith("win"):
            if parsed.netloc:
                return "\\\\" + parsed.netloc + path.replace("/", "\\")
            if path.startswith("/") and re.match(r"^/[A-Za-z]:/", path):
                path = path[1:]
            return path.replace("/", "\\")
        if parsed.netloc:
            return f"//{parsed.netloc}{path}"
        return path
    if sys.platform.startswith("win") and value.startswith("//"):
        return "\\\\" + unquote(value[2:]).replace("/", "\\")
    return value


def _best_existing_path_span(text, start, end):
    start, end, value = _trim_target(text, start, end)
    extension_match = re.search(r"\.([A-Za-z0-9]{1,8})(?=$|[\s,;:!?)\]}])", value)
    if extension_match and extension_match.group(1).lower() in COMMON_FILE_EXTENSIONS:
        guessed = value[:extension_match.end()].rstrip(TRAILING_LINK_CHARS + " ")
        return start, start + len(guessed), guessed

    if sys.platform.startswith("win"):
        existing, exact_match = _nearest_existing_windows_path(value)
        if existing and not exact_match:
            existing_text = str(existing)
            normalized_value = normalize_file_target(value)
            if normalized_value.lower().startswith(existing_text.lower()):
                return start, start + len(existing_text), value[: len(existing_text)]

    return start, end, value


def _nearest_existing_windows_path(value):
    cleaned = normalize_file_target(value)
    cleaned = cleaned.replace("/", "\\") if re.match(r"^(?:[A-Za-z]:|\\\\)", cleaned) else cleaned
    candidate = Path(cleaned)
    try:
        if candidate.exists():
            return candidate, True
    except OSError:
        pass

    trimmed = cleaned.rstrip(TRAILING_LINK_CHARS + " ")
    while " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0].rstrip(TRAILING_LINK_CHARS + " ")
        if not trimmed:
            break
        try:
            trimmed_path = Path(trimmed)
            if trimmed_path.exists():
                return trimmed_path, False
        except OSError:
            continue

    for separator in ("\\", "/"):
        if separator not in cleaned:
            continue
        pieces = cleaned.split(separator)
        minimum = 4 if cleaned.startswith("\\\\") else 2
        for count in range(len(pieces), minimum - 1, -1):
            partial = separator.join(pieces[:count]).rstrip(TRAILING_LINK_CHARS + " ")
            if cleaned.startswith("\\\\") and not partial.startswith("\\\\"):
                partial = "\\\\" + partial.lstrip("\\")
            try:
                partial_path = Path(partial)
                if partial_path.exists():
                    return partial_path, False
            except OSError:
                continue

    parts = re.split(r"[\\/]+", cleaned)
    if cleaned.startswith("\\\\"):
        for count in range(len(parts), 3, -1):
            partial = "\\\\" + "\\".join(part for part in parts[2:count] if part)
            try:
                partial_path = Path(partial)
                if partial_path.exists():
                    return partial_path, False
            except OSError:
                continue
    elif re.match(r"^[A-Za-z]:[\\/]", cleaned):
        for count in range(len(parts), 1, -1):
            partial = "\\".join(parts[:count])
            try:
                partial_path = Path(partial)
                if partial_path.exists():
                    return partial_path, False
            except OSError:
                continue

    return candidate, False


def _displayable_windows_path(value):
    cleaned = normalize_file_target(value)
    return cleaned.replace("/", "\\") if re.match(r"^(?:[A-Za-z]:|\\\\)", cleaned) else cleaned


def find_click_targets(text):
    targets = []

    for match in QUOTED_PATH_RE.finditer(text):
        start, end = match.span("path")
        start, end, value = _trim_target(text, start, end)
        targets.append((start, end, "file", normalize_file_target(value)))

    for pattern in [FILE_URL_RE, URL_RE, WINDOWS_PATH_RE, UNIX_PATH_RE]:
        kind = "url" if pattern is URL_RE else "file"
        for match in pattern.finditer(text):
            if pattern is WINDOWS_PATH_RE:
                start, end, value = _best_existing_path_span(text, match.start(), match.end())
            else:
                start, end, value = _trim_target(text, match.start(), match.end())
            if not value:
                continue
            if any(start < existing_end and end > existing_start for existing_start, existing_end, _kind, _value in targets):
                continue
            if kind == "file":
                value = normalize_file_target(value)
            targets.append((start, end, kind, value))

    return sorted(targets, key=lambda item: item[0])


def open_url(value):
    url = value if value.lower().startswith(("http://", "https://")) else f"https://{value}"
    webbrowser.open(url)


def open_file_location(value):
    if sys.platform.startswith("win"):
        target, exact_match = _nearest_existing_windows_path(value)
        try:
            exists = target.exists()
        except OSError:
            exists = False
        if not exists:
            messagebox.showwarning(APP_NAME, f"File path was not found on this computer:\n{_displayable_windows_path(value)}")
            return
        try:
            if target.is_file():
                subprocess.Popen(["explorer.exe", "/select,", str(target)])
            else:
                os.startfile(str(target))
        except OSError:
            folder = target.parent if target.is_file() else target
            subprocess.Popen(["explorer.exe", str(folder)])
        return

    target = Path(normalize_file_target(value)).expanduser()
    if not target.exists():
        messagebox.showwarning(APP_NAME, f"File path was not found:\n{value}")
        return

    if sys.platform == "darwin":
        if target.is_file():
            subprocess.Popen(["open", "-R", str(target)])
        else:
            subprocess.Popen(["open", str(target)])
    else:
        folder = target if target.is_dir() else target.parent
        subprocess.Popen(["xdg-open", str(folder)])


class ChatHistory:
    def __init__(self):
        self.path = get_app_data_dir() / "history.json"
        self._lock = threading.Lock()
        self._history = self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as source:
                data = json.load(source)
                return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _record_date(self, record):
        try:
            return datetime.strptime(record.get("date", ""), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as output:
                json.dump(self._history, output, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def add(self, peer_id, sender, text, kind="message", extra=None):
        record = {
            "date": today_label(),
            "time": now_label(),
            "sender": sender,
            "text": text,
            "kind": kind,
        }
        if extra:
            record.update(extra)
        with self._lock:
            self._history.setdefault(peer_id, []).append(record)
            self._save()

    def list_for(self, peer_id, today_only=False):
        with self._lock:
            records = [record for record in self._history.get(peer_id, []) if isinstance(record, dict)]
        if today_only:
            today = today_label()
            records = [record for record in records if record.get("date") == today]
        return records


class PeerDirectory:
    def __init__(self):
        self._lock = threading.Lock()
        self._peers = {}

    def upsert(self, peer_id, name, host, port, status="Available", version="0.0.0", platform="source"):
        with self._lock:
            self._peers[peer_id] = {
                "id": peer_id,
                "name": name,
                "host": host,
                "port": int(port),
                "status": status if status in STATUS_VALUES else "Available",
                "version": version,
                "platform": platform,
                "last_seen": time.time(),
            }

    def remove_stale(self, max_age=12):
        cutoff = time.time() - max_age
        with self._lock:
            stale = [peer_id for peer_id, peer in self._peers.items() if peer["last_seen"] < cutoff]
            for peer_id in stale:
                del self._peers[peer_id]

    def list(self):
        with self._lock:
            return sorted(self._peers.values(), key=lambda peer: peer["name"].lower())

    def get(self, peer_id):
        with self._lock:
            return self._peers.get(peer_id)

    def contains(self, peer_id):
        with self._lock:
            return peer_id in self._peers


class ChatNetwork:
    def __init__(self, display_name, event_queue, peer_id=None, status="Available"):
        self.peer_id = peer_id or str(uuid.uuid4())
        self.display_name = display_name
        self.status = status
        self.event_queue = event_queue
        self.peers = PeerDirectory()
        self.host_ips = local_ipv4_addresses()
        self.host_ip = self.host_ips[0]
        self.running = threading.Event()
        self.running.set()

    def start(self):
        threading.Thread(target=self._discovery_sender, daemon=True).start()
        threading.Thread(target=self._discovery_receiver, daemon=True).start()
        threading.Thread(target=self._tcp_server, daemon=True).start()
        threading.Thread(target=self._stale_peer_cleaner, daemon=True).start()

    def stop(self):
        self.running.clear()

    def set_status(self, status):
        if status in STATUS_VALUES:
            self.status = status

    def set_display_name(self, display_name):
        self.display_name = display_name

    def send_message(self, peer, text):
        payload = {
            "type": "message",
            "from_id": self.peer_id,
            "from_name": self.display_name,
            "from_port": TCP_PORT,
            "from_status": self.status,
            "from_version": APP_VERSION,
            "from_platform": current_update_platform(),
            "text": text,
            "sent_at": time.time(),
        }
        return self._send_payload(peer, payload)

    def send_typing(self, peer, is_typing=True):
        payload = {
            "type": "typing",
            "from_id": self.peer_id,
            "from_name": self.display_name,
            "from_port": TCP_PORT,
            "from_status": self.status,
            "from_version": APP_VERSION,
            "from_platform": current_update_platform(),
            "is_typing": bool(is_typing),
            "sent_at": time.time(),
        }
        return self._send_payload(peer, payload)

    def broadcast_message(self, peers, text):
        sent = 0
        for peer in peers:
            if self.send_message(peer, text):
                sent += 1
        return sent

    def send_file(self, peer, path):
        file_path = Path(path)
        payload = {
            "type": "file",
            "from_id": self.peer_id,
            "from_name": self.display_name,
            "from_port": TCP_PORT,
            "from_status": self.status,
            "from_version": APP_VERSION,
            "from_platform": current_update_platform(),
            "filename": file_path.name,
            "size": file_path.stat().st_size,
            "sent_at": time.time(),
        }
        return self._send_payload(peer, payload, file_path)

    def request_update(self, peer):
        payload = {
            "type": "update_request",
            "from_id": self.peer_id,
            "from_name": self.display_name,
            "from_port": TCP_PORT,
            "from_status": self.status,
            "from_version": APP_VERSION,
            "from_platform": current_update_platform(),
        }
        try:
            with socket.create_connection((peer["host"], peer["port"]), timeout=12) as sock:
                header = json.dumps(payload).encode("utf-8")
                sock.sendall(struct.pack("!Q", len(header)))
                sock.sendall(header)

                response_len_raw = self._read_exact(sock, 8)
                response_len = struct.unpack("!Q", response_len_raw)[0]
                if response_len > MAX_HEADER_SIZE:
                    raise ValueError("update header is too large")
                response = json.loads(self._read_exact(sock, response_len).decode("utf-8"))
                if response.get("type") != "update_response":
                    raise ValueError(response.get("error", "unexpected update response"))
                version = response.get("version", "0.0.0")
                platform = response.get("platform", "source")
                if platform != current_update_platform():
                    raise ValueError("update is for a different platform")
                if not is_newer_version(version):
                    raise ValueError("peer does not have a newer version")

                size = int(response.get("size", 0))
                expected_hash = str(response.get("sha256", "")).lower()
                filename = safe_filename(response.get("filename", "LANMessenger_update"))
                target_dir = get_updates_dir() / version
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / filename
                remaining = size
                downloaded = 0
                self.event_queue.put(("update_progress", 0, size))
                with open(target, "wb") as output:
                    while remaining > 0:
                        chunk = sock.recv(min(BUFFER_SIZE, remaining))
                        if not chunk:
                            raise OSError("connection closed before update finished")
                        output.write(chunk)
                        downloaded += len(chunk)
                        remaining -= len(chunk)
                        self.event_queue.put(("update_progress", downloaded, size))
                if target.stat().st_size != size:
                    raise OSError("downloaded update size did not match")
                if expected_hash and file_sha256(target).lower() != expected_hash:
                    target.unlink(missing_ok=True)
                    raise OSError("downloaded update checksum did not match")
                if not sys.platform.startswith("win"):
                    target.chmod(target.stat().st_mode | 0o111)
                save_pending_update(version, target, platform, size, expected_hash)
                self.event_queue.put(("update_downloaded", version, str(target)))
                return True
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.event_queue.put(("error", f"Could not download update from {peer['name']}: {exc}"))
            return False

    def _send_payload(self, peer, payload, file_path=None):
        try:
            with socket.create_connection((peer["host"], peer["port"]), timeout=8) as sock:
                header = json.dumps(payload).encode("utf-8")
                sock.sendall(struct.pack("!Q", len(header)))
                sock.sendall(header)

                if file_path:
                    with open(file_path, "rb") as source:
                        while True:
                            chunk = source.read(BUFFER_SIZE)
                            if not chunk:
                                break
                            sock.sendall(chunk)
            return True
        except OSError as exc:
            self.event_queue.put(("error", f"Could not send to {peer['name']}: {exc}"))
            return False

    def _discovery_sender(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while self.running.is_set():
            try:
                self.host_ips = local_ipv4_addresses()
                self.host_ip = self.host_ips[0]
                for host_ip in self.host_ips:
                    announcement = {
                        "app": APP_NAME,
                        "peer_id": self.peer_id,
                        "name": self.display_name,
                        "status": self.status,
                        "version": APP_VERSION,
                        "platform": current_update_platform(),
                        "host": host_ip,
                        "port": TCP_PORT,
                    }
                    data = json.dumps(announcement).encode("utf-8")
                    for target in discovery_targets(host_ip):
                        try:
                            sock.sendto(data, target)
                        except OSError:
                            continue
            except OSError as exc:
                self.event_queue.put(("error", f"Discovery send failed: {exc}"))
            time.sleep(2)

        sock.close()

    def _discovery_receiver(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass

        try:
            sock.bind(("", DISCOVERY_PORT))
            joined_multicast = False
            for host_ip in ["0.0.0.0"] + local_ipv4_addresses():
                try:
                    membership = socket.inet_aton(DISCOVERY_GROUP) + socket.inet_aton(host_ip)
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
                    joined_multicast = True
                except OSError:
                    continue
            if not joined_multicast:
                self.event_queue.put(("error", "Discovery multicast join failed; broadcast fallback is still active."))
            sock.settimeout(1)
        except OSError as exc:
            self.event_queue.put(("error", f"Discovery receive failed: {exc}"))
            sock.close()
            return

        while self.running.is_set():
            try:
                data, address = sock.recvfrom(4096)
                message = json.loads(data.decode("utf-8"))
                if message.get("app") != APP_NAME or message.get("peer_id") == self.peer_id:
                    continue

                peer_id = message["peer_id"]
                is_new_peer = not self.peers.contains(peer_id)
                host = address[0] or message.get("host") or ""
                self.peers.upsert(
                    peer_id,
                    message.get("name", "Unknown"),
                    host,
                    message["port"],
                    message.get("status", "Available"),
                    message.get("version", "0.0.0"),
                    message.get("platform", "source"),
                )
                if is_new_peer:
                    self.event_queue.put(("new_peer", peer_id, message.get("name", "Unknown")))
                self.event_queue.put(("peers", self.peers.list()))
            except socket.timeout:
                continue
            except (OSError, ValueError, KeyError) as exc:
                self.event_queue.put(("error", f"Discovery receive error: {exc}"))

        sock.close()

    def _tcp_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server.bind(("", TCP_PORT))
            server.listen()
            server.settimeout(1)
        except OSError as exc:
            self.event_queue.put(("error", f"Could not start receiving port {TCP_PORT}: {exc}"))
            server.close()
            return

        while self.running.is_set():
            try:
                conn, address = server.accept()
                threading.Thread(target=self._handle_connection, args=(conn, address), daemon=True).start()
            except socket.timeout:
                continue
            except OSError as exc:
                self.event_queue.put(("error", f"Receiving error: {exc}"))

        server.close()

    def _handle_connection(self, conn, address):
        with conn:
            try:
                header_len_raw = self._read_exact(conn, 8)
                if not header_len_raw:
                    return

                header_len = struct.unpack("!Q", header_len_raw)[0]
                if header_len > MAX_HEADER_SIZE:
                    raise ValueError("incoming header is too large")

                header = json.loads(self._read_exact(conn, header_len).decode("utf-8"))
                sender_id = header.get("from_id", address[0])
                sender = header.get("from_name", address[0])
                sender_port = header.get("from_port", TCP_PORT)
                is_new_peer = not self.peers.contains(sender_id)
                self.peers.upsert(
                    sender_id,
                    sender,
                    address[0],
                    sender_port,
                    header.get("from_status", "Available"),
                    header.get("from_version", "0.0.0"),
                    header.get("from_platform", "source"),
                )
                if is_new_peer:
                    self.event_queue.put(("new_peer", sender_id, sender))
                self.event_queue.put(("peers", self.peers.list()))

                if header.get("type") == "message":
                    self.event_queue.put(("message", sender_id, sender, header.get("text", "")))
                    return

                if header.get("type") == "typing":
                    self.event_queue.put(("typing", sender_id, sender, bool(header.get("is_typing", True))))
                    return

                if header.get("type") == "file":
                    self._receive_file(conn, sender_id, sender, header)
                    return

                if header.get("type") == "update_request":
                    self._send_update_response(conn)
                    return
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self.event_queue.put(("error", f"Incoming transfer failed: {exc}"))

    def _send_update_response(self, conn):
        package = current_update_package()
        if not package:
            payload = {"type": "update_response", "error": "no update package available"}
            header = json.dumps(payload).encode("utf-8")
            conn.sendall(struct.pack("!Q", len(header)))
            conn.sendall(header)
            return
        payload = {
            "type": "update_response",
            "version": APP_VERSION,
            "platform": current_update_platform(),
            "filename": package.name,
            "size": package.stat().st_size,
            "sha256": file_sha256(package),
        }
        header = json.dumps(payload).encode("utf-8")
        conn.sendall(struct.pack("!Q", len(header)))
        conn.sendall(header)
        with open(package, "rb") as source:
            while True:
                chunk = source.read(BUFFER_SIZE)
                if not chunk:
                    break
                conn.sendall(chunk)

    def _receive_file(self, conn, sender_id, sender, header):
        size = int(header.get("size", 0))
        filename = safe_filename(header.get("filename", "received_file"))
        target = get_received_file_dir(sender) / filename

        if target.exists():
            stem = target.stem
            suffix = target.suffix
            target = target.with_name(f"{stem}_{int(time.time())}{suffix}")

        remaining = size
        with open(target, "wb") as output:
            while remaining > 0:
                chunk = conn.recv(min(BUFFER_SIZE, remaining))
                if not chunk:
                    raise OSError("connection closed before file finished")
                output.write(chunk)
                remaining -= len(chunk)

        self.event_queue.put(("file", sender_id, sender, str(target), size))

    def _read_exact(self, conn, size):
        data = bytearray()
        while len(data) < size:
            chunk = conn.recv(size - len(data))
            if not chunk:
                raise OSError("connection closed unexpectedly")
            data.extend(chunk)
        return bytes(data)

    def _stale_peer_cleaner(self):
        while self.running.is_set():
            self.peers.remove_stale()
            self.event_queue.put(("peers", self.peers.list()))
            time.sleep(4)


class ConversationWindow:
    def __init__(self, app, peer):
        self.app = app
        self.peer = peer
        self.emoji_popup = None
        self.link_count = 0
        self.link_tags = []
        self.inline_buttons = []
        self.history_loaded = False
        self.today_history_loaded = False
        self.typing_visible = False
        self.typing_after_id = None
        self.typing_anim_after_id = None
        self.typing_step = 0
        self.typing_frames = []
        self.last_typing_sent = 0
        self.typing_state_sent = False
        self.window = Toplevel(app.root)
        self.window.title(f"{peer['name']} - Conversation")
        if self.app.window_icon:
            self.window.iconphoto(False, self.app.window_icon)
        self.window.geometry("520x450")
        self.window.minsize(460, 380)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self._build_ui()
        self.apply_theme()
        self.show_today_history()

    def _build_ui(self):
        self.root_frame = Frame(self.window, padx=8, pady=8)
        self.root_frame.pack(fill=BOTH, expand=True)

        top = Frame(self.root_frame)
        top.pack(fill=X)
        self.frames = [self.root_frame, top]

        self.conversation_label = Label(top, text="Conversation:", font=FONT_BOLD)
        self.conversation_label.pack(side=LEFT)

        self.file_button = Button(top, text="Send File(s)", command=self.send_file)
        self.file_button.pack(side=RIGHT, padx=4)
        self.history_button = Button(top, text="History", command=self.show_history)
        self.history_button.pack(side=RIGHT, padx=4)
        self.emoji_button = None

        history_frame = Frame(self.root_frame)
        history_frame.pack(fill=BOTH, expand=True, pady=6)
        self.frames.append(history_frame)

        self.history = Text(history_frame, state="disabled", wrap="word", height=12, font=CHAT_FONT_NORMAL, bd=0, highlightthickness=1)
        history_scroll = Scrollbar(history_frame, command=self.history.yview)
        self.history.configure(yscrollcommand=history_scroll.set)
        self.history.pack(side=LEFT, fill=BOTH, expand=True)
        history_scroll.pack(side=RIGHT, fill=Y)

        self.typing_frames = self._load_typing_frames()
        self.typing_widget = Frame(self.history, bd=0)
        self.typing_image = Label(self.typing_widget, bd=0)
        self.typing_image.pack(side=LEFT)
        self.typing_text = Label(self.typing_widget, text="Typing...", font=CHAT_FONT_NORMAL, bd=0)
        self.typing_text.pack(side=LEFT, padx=(6, 0))

        self.message_label = Label(self.root_frame, text="Message text:", font=FONT_BOLD)
        self.message_label.pack(anchor="w")

        input_frame = Frame(self.root_frame)
        input_frame.pack(fill=X, pady=6)
        self.frames.append(input_frame)

        self.message_input = Text(input_frame, height=4, wrap="word", font=CHAT_FONT_NORMAL, bd=0, highlightthickness=1)
        input_scroll = Scrollbar(input_frame, command=self.message_input.yview)
        self.message_input.configure(yscrollcommand=input_scroll.set)
        self.message_input.pack(side=LEFT, fill=X, expand=True)
        input_scroll.pack(side=RIGHT, fill=Y)
        self.message_input.bind("<Return>", self._send_on_enter)
        self.message_input.bind("<Shift-Return>", self._insert_newline)
        self.message_input.bind("<Control-Return>", lambda _event: self.send_message())
        self.message_input.bind("<KeyRelease>", self._handle_typing_key_release)

        buttons = Frame(self.root_frame)
        buttons.pack(fill=X)
        self.frames.append(buttons)

        self.close_button = Button(buttons, text="Close", width=10, command=self.close)
        self.close_button.pack(side=RIGHT)
        self.send_button = Button(buttons, text="Send", width=10, command=self.send_message)
        self.send_button.pack(side=RIGHT, padx=8)
        self.emoji_button = Button(buttons, text="Emoji", width=10, command=self.toggle_emoji_picker)
        self.emoji_button.pack(side=RIGHT)

        self.labels = [self.conversation_label, self.message_label]
        self.buttons = [self.file_button, self.history_button, self.emoji_button, self.close_button, self.send_button]
        self._enable_file_drop()

    def _enable_file_drop(self):
        if not DND_AVAILABLE:
            return
        drop_widgets = [
            self.window,
            self.root_frame,
            self.history,
            self.message_input,
            self.file_button,
            self.history.master,
            self.message_input.master,
        ]
        for widget in drop_widgets:
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._handle_file_drop)
            except Exception:
                continue

    def _handle_file_drop(self, event):
        paths = []
        for raw_path in self.window.tk.splitlist(event.data):
            path = Path(raw_path.strip("{}"))
            if path.is_file():
                paths.append(str(path))
        if paths:
            self.send_files(paths)
        else:
            messagebox.showwarning(APP_NAME, "No valid file was dropped.")
        return "break"

    def update_peer(self, peer):
        self.peer = peer
        self.window.title(f"{peer['name']} - Conversation")

    def is_focused(self):
        try:
            focused = self.window.focus_get()
            return focused is not None and str(focused).startswith(str(self.window))
        except Exception:
            return False

    def bring_to_front(self):
        try:
            self.app.tray_hidden_conversations.discard(self.peer["id"])
            self.window.deiconify()
            self.window.lift()
            self.window.attributes("-topmost", True)
            self.window.after(1200, lambda: self.window.attributes("-topmost", False))
            self.window.focus_force()
        except Exception:
            pass

    def apply_theme(self):
        theme = self.app.theme
        schedule_title_bar_theme(self.window, self.app.dark_mode)
        self.window.configure(bg=theme["window"])
        for frame in self.frames:
            frame.configure(bg=theme["panel"])
        for label in self.labels:
            label.configure(bg=theme["panel"], fg=theme["text_fg"])
        for button in self.buttons + self.inline_buttons:
            button.configure(
                bg=theme["button_bg"],
                fg=theme["button_fg"],
                activebackground=theme["select_bg"],
                activeforeground=theme["select_fg"],
            )
        self.history.configure(bg=theme["text_bg"], fg=theme["text_fg"], insertbackground=theme["text_fg"])
        self.history.configure(highlightbackground=theme["border"], highlightcolor=theme["select_bg"])
        self.typing_widget.configure(bg=theme["text_bg"])
        self.typing_image.configure(bg=theme["text_bg"])
        self.typing_text.configure(bg=theme["text_bg"], fg="#9ca3af" if self.app.dark_mode else "#6b7280")
        self.message_input.configure(bg=theme["entry_bg"], fg=theme["entry_fg"], insertbackground=theme["entry_fg"])
        self.message_input.configure(highlightbackground=theme["border"], highlightcolor=theme["select_bg"])
        if self.typing_visible:
            self._show_typing_frame()
        self._style_chat_tags()
        self._style_link_tags()
        if self.emoji_popup and self.emoji_popup.winfo_exists():
            self._style_emoji_popup()

    def _handle_typing_key_release(self, event):
        if event.keysym in {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"}:
            return
        text = self.message_input.get("1.0", END).strip()
        self._send_typing_status(bool(text))

    def _send_typing_status(self, is_typing):
        now = time.time()
        if is_typing and self.typing_state_sent and now - self.last_typing_sent < TYPING_SEND_INTERVAL:
            return
        if not is_typing:
            if not self.typing_state_sent:
                return
            self.typing_state_sent = False
            self.last_typing_sent = now
            threading.Thread(target=self.app.network.send_typing, args=(self.peer, False), daemon=True).start()
            return
        self.typing_state_sent = is_typing
        self.last_typing_sent = now
        threading.Thread(target=self.app.network.send_typing, args=(self.peer, is_typing), daemon=True).start()

    def show_typing(self, sender, is_typing=True):
        if not is_typing:
            self.hide_typing()
            return
        if not self.typing_visible:
            self.typing_visible = True
            self._show_typing_frame()
            self._insert_typing_indicator()
            self._animate_typing()
        if self.typing_after_id:
            self.window.after_cancel(self.typing_after_id)
        self.typing_after_id = self.window.after(TYPING_TIMEOUT_MS, self.hide_typing)

    def hide_typing(self):
        self.typing_visible = False
        if self.typing_after_id:
            self.window.after_cancel(self.typing_after_id)
            self.typing_after_id = None
        if self.typing_anim_after_id:
            self.window.after_cancel(self.typing_anim_after_id)
            self.typing_anim_after_id = None
        self.typing_image.configure(image="")
        self._remove_typing_indicator()

    def _animate_typing(self):
        if not self.typing_visible:
            return
        self._show_typing_frame()
        frame_count = len(self.typing_frames) or 3
        self.typing_step = (self.typing_step + 1) % frame_count
        self.typing_anim_after_id = self.window.after(220, self._animate_typing)

    def _show_typing_frame(self):
        if self.typing_frames:
            self.typing_image.configure(image=self.typing_frames[self.typing_step % len(self.typing_frames)])

    def _insert_typing_indicator(self):
        self.typing_widget.place(relx=0, rely=1, x=8, y=-8, anchor="sw")
        self.history.see(END)

    def _remove_typing_indicator(self):
        self.typing_widget.place_forget()

    def _load_typing_frames(self):
        path = resource_path("assets", "typing_indicator_preview.gif")
        if not path.exists():
            return []
        if TYPING_IMAGE_AVAILABLE:
            try:
                with PILImage.open(path) as image:
                    target_height = max(26, int(CHAT_FONT_NORMAL[1] * 3.32))
                    frames = []
                    for frame in ImageSequence.Iterator(image):
                        rgba = frame.convert("RGBA")
                        ratio = target_height / max(1, rgba.height)
                        target_width = max(1, int(rgba.width * ratio))
                        resized = rgba.resize((target_width, target_height), PILImage.Resampling.LANCZOS)
                        frames.append(ImageTk.PhotoImage(resized))
                    return frames
            except Exception:
                pass
        frames = []
        index = 0
        while True:
            try:
                frame = PhotoImage(file=str(path), format=f"gif -index {index}")
                frames.append(frame.subsample(24, 24))
                index += 1
            except TclError:
                break
        return frames

    def send_message(self):
        text = self.message_input.get("1.0", END).strip()
        if not text:
            return "break"
        self.message_input.delete("1.0", END)
        self._send_typing_status(False)
        self.append_chat("You", text)
        self.app.history.add(self.peer["id"], "You", text)
        threading.Thread(target=self.app.network.send_message, args=(self.peer, text), daemon=True).start()
        return "break"

    def _send_on_enter(self, _event):
        return self.send_message()

    def _insert_newline(self, _event):
        self.message_input.insert("insert", "\n")
        return "break"

    def send_file(self):
        paths = filedialog.askopenfilenames(title="Choose file(s) to send")
        if not paths:
            return
        self.send_files(paths)

    def send_files(self, paths):
        for path in paths:
            self.append_system(f"Sending {Path(path).name}...")
        threading.Thread(target=self._send_files_worker, args=(list(paths),), daemon=True).start()

    def _send_files_worker(self, paths):
        sent = 0
        for path in paths:
            if self.app.network.send_file(self.peer, path):
                sent += 1
                self.app.events.put(("conversation_system", self.peer["id"], f"Sent file: {Path(path).name}", True))
        if len(paths) > 1:
            self.app.events.put(("conversation_system", self.peer["id"], f"Finished sending {sent} of {len(paths)} file(s).", False))

    def toggle_emoji_picker(self):
        if self.emoji_popup and self.emoji_popup.winfo_exists():
            self.emoji_popup.destroy()
            self.emoji_popup = None
            return

        self.emoji_popup = Toplevel(self.window)
        self.emoji_popup.title("Emoji")
        self.emoji_popup.resizable(False, False)
        self.emoji_popup.transient(self.window)
        self.emoji_popup.geometry(f"+{self.window.winfo_rootx() + 160}+{self.window.winfo_rooty() + 70}")
        schedule_title_bar_theme(self.emoji_popup, self.app.dark_mode)

        self.emoji_panel = Frame(self.emoji_popup, padx=8, pady=8)
        self.emoji_panel.pack()
        self.emoji_buttons = []
        for index, emoji in enumerate(EMOJIS):
            button = Button(
                self.emoji_panel,
                text=emoji,
                width=4,
                command=lambda value=emoji: self.insert_emoji(value),
            )
            button.grid(row=index // 8, column=index % 8, padx=3, pady=3)
            self.emoji_buttons.append(button)
        self._style_emoji_popup()

    def _style_emoji_popup(self):
        theme = self.app.theme
        schedule_title_bar_theme(self.emoji_popup, self.app.dark_mode)
        self.emoji_popup.configure(bg=theme["panel"])
        self.emoji_panel.configure(bg=theme["panel"])
        for button in self.emoji_buttons:
            button.configure(
                bg=theme["button_bg"],
                fg=theme["button_fg"],
                activebackground=theme["select_bg"],
                activeforeground=theme["select_fg"],
            )

    def insert_emoji(self, emoji):
        self.message_input.insert("insert", emoji)
        self.message_input.focus_set()

    def append_chat(self, sender, text):
        self.append_chat_line(now_label(), sender, text)

    def append_system(self, text):
        self.append_line(f"{now_label()}  [{text}]")

    def append_saved_chat(self, record):
        self.append_chat_line(record.get("time", ""), record.get("sender", "Unknown"), record.get("text", ""))

    def append_saved_system(self, record):
        self.append_line(f"{record.get('time', '')}  [{record.get('text', '')}]")

    def append_received_file(self, sender, target, size):
        self.append_system(f"{sender} sent a file: {Path(target).name} ({size:,} bytes)")
        self.append_system(f"Saved to {target}")
        self.append_open_location_button(target)

    def append_saved_received_file(self, record):
        self.append_line(f"{record.get('time', '')}  [{record.get('text', '')}]")
        target = record.get("target")
        if target:
            self.append_open_location_button(target)

    def show_today_history(self):
        if self.today_history_loaded:
            return
        records = self.app.history.list_for(self.peer["id"], today_only=True)
        self.today_history_loaded = True
        if not records:
            return
        self.append_line("---- Today's chat history ----")
        for record in records:
            self.append_history_record(record)

    def show_history(self):
        if self.history_loaded:
            self.append_system("Full history is already shown.")
            return
        records = self.app.history.list_for(self.peer["id"])
        records = [record for record in records if record.get("date") != today_label()]
        if not records:
            self.append_system("No older chat history.")
            return
        self.history_loaded = True
        self.append_line("---- Older chat history ----")
        for record in records:
            self.append_history_record(record)
        self.append_line("---- End of history ----")

    def append_history_record(self, record):
        if record.get("kind") == "received_file":
            self.append_saved_received_file(record)
        elif record.get("kind") == "file":
            self.append_saved_system(record)
        else:
            self.append_saved_chat(record)

    def append_line(self, text):
        self.history.configure(state="normal")
        self._insert_clickable_line(text)
        self.history.see(END)
        self.history.configure(state="disabled")

    def append_chat_line(self, timestamp, sender, text):
        self.history.configure(state="normal")
        self.history.insert(END, f"{timestamp}  {sender}: ", ("chat_meta",))
        self._insert_clickable_line(text, ("chat_message",))
        self.history.see(END)
        self.history.configure(state="disabled")

    def _insert_clickable_line(self, text, base_tags=()):
        targets = find_click_targets(text)
        cursor = 0
        for start, end, kind, value in targets:
            if start > cursor:
                self.history.insert(END, text[cursor:start], base_tags)
            tag = self._make_link_tag(kind, value)
            self.history.insert(END, text[start:end], tuple(base_tags) + (tag,))
            cursor = end
        if cursor < len(text):
            self.history.insert(END, text[cursor:], base_tags)
        self.history.insert(END, "\n")

    def _make_link_tag(self, kind, value):
        tag = f"link_{self.link_count}"
        self.link_count += 1
        self.link_tags.append(tag)
        self.history.tag_configure(tag, foreground=self._link_color(), underline=True)
        self.history.tag_bind(tag, "<Enter>", lambda _event: self.history.configure(cursor="hand2"))
        self.history.tag_bind(tag, "<Leave>", lambda _event: self.history.configure(cursor=""))
        if kind == "url":
            self.history.tag_bind(tag, "<Button-1>", lambda _event, target=value: open_url(target))
        else:
            self.history.tag_bind(tag, "<Button-1>", lambda _event, target=value: open_file_location(target))
        return tag

    def _link_color(self):
        return "#93c5fd" if self.app.dark_mode else "#1d4ed8"

    def _style_chat_tags(self):
        meta_color = "#9ca3af" if self.app.dark_mode else "#6b7280"
        self.history.tag_configure("chat_meta", foreground=meta_color, font=CHAT_FONT_NORMAL)
        self.history.tag_configure("chat_message", foreground=self.app.theme["text_fg"], font=CHAT_FONT_BOLD)

    def _style_link_tags(self):
        color = self._link_color()
        for tag in self.link_tags:
            self.history.tag_configure(tag, foreground=color, underline=True)

    def append_open_location_button(self, target):
        self.history.configure(state="normal")
        button = Button(self.history, text="Open Location", command=lambda path=target: open_file_location(path))
        self.inline_buttons.append(button)
        self._style_inline_button(button)
        self.history.insert(END, "  ")
        self.history.window_create(END, window=button)
        self.history.insert(END, "\n")
        self.history.see(END)
        self.history.configure(state="disabled")

    def _style_inline_button(self, button):
        theme = self.app.theme
        button.configure(
            bg=theme["button_bg"],
            fg=theme["button_fg"],
            activebackground=theme["select_bg"],
            activeforeground=theme["select_fg"],
        )

    def close(self):
        self.hide_typing()
        if self.emoji_popup and self.emoji_popup.winfo_exists():
            self.emoji_popup.destroy()
        self.app.tray_hidden_conversations.add(self.peer["id"])
        self.window.withdraw()


class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("360x520")
        self.root.minsize(300, 420)
        self.window_icon = load_window_icon()
        if self.window_icon:
            self.root.iconphoto(True, self.window_icon)
        self.events = queue.Queue()
        self.peer_rows = []
        self.unread_counts = {}
        self.conversations = {}
        self.hidden_to_tray = False
        self.tray_hidden_conversations = set()
        self.dark_mode = True
        self.theme = DARK_THEME
        self.history = ChatHistory()
        self.manual_status = "Available"
        self.my_status = "Available"
        self.last_activity_at = time.time()
        self.started_from_startup = STARTUP_ARG in sys.argv[1:]
        self.tray = TrayController(self)

        saved_name = load_saved_display_name()
        default_name = saved_name or os.environ.get("USERNAME") or os.environ.get("USER") or "Me"
        self.display_name = saved_name
        if not self.display_name:
            entered_name = simpledialog.askstring(APP_NAME, "Your display name:", initialvalue=default_name)
            self.display_name = (entered_name or default_name).strip() or "Me"
            save_display_name(self.display_name)

        self.network = ChatNetwork(self.display_name, self.events, load_or_create_peer_id(), self.my_status)
        self._build_ui()
        refresh_startup_shortcut_if_present()
        self.tray.start()
        self.network.start()
        self._bind_activity_tracking()
        self._poll_events()
        self._poll_idle_status()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(300, self._maybe_prompt_startup)
        if self.started_from_startup:
            self.root.after(500, self.hide_to_tray)

    def _build_ui(self):
        self.header = Frame(self.root, padx=10, pady=8)
        self.header.pack(side=TOP, fill=X)

        self.header_controls = Frame(self.header)
        self.header_controls.pack(anchor="center")

        self.status_selector = StatusSelector(self.header_controls, value=self.my_status, command=self._set_my_status)
        self.status_selector.pack(side=LEFT, padx=8)

        self.theme_toggle = ThemeToggle(self.header_controls, command=self._toggle_dark_mode, dark=self.dark_mode)
        self.theme_toggle.pack(side=LEFT, padx=8)

        self.update_button_wrap = Frame(self.header_controls, width=90, height=30)
        self.update_button_wrap.pack(side=LEFT, padx=8)
        self.update_button_wrap.pack_propagate(False)
        self.update_button = Button(self.update_button_wrap, text="Update", command=self.check_for_update)
        self.update_button.pack(fill=BOTH, expand=True)
        self.update_badge = Canvas(self.update_button_wrap, width=15, height=15, bd=0, highlightthickness=0)
        self.update_progress = Canvas(self.update_button_wrap, height=5, bd=0, highlightthickness=0)

        self.main = Frame(self.root, padx=10, pady=10)
        self.main.pack(fill=BOTH, expand=True)

        self.status_label = Label(self.main, text="0 online", font=FONT_BOLD)
        self.status_label.pack(anchor="w")

        self.peer_list = PeerList(self.main, open_command=self.open_selected_conversation)
        self.peer_list.pack(fill=BOTH, expand=True, pady=8)

        self.action_row = Frame(self.main)
        self.action_row.pack(fill=X, pady=3)

        self.open_button = Button(self.action_row, text="Open Conversation", command=self.open_selected_conversation)
        self.open_button.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))

        self.refresh_button = Button(self.action_row, text="Refresh", command=self._refresh_peers)
        self.refresh_button.pack(side=LEFT, fill=X, expand=True, padx=(4, 0))

        self.secondary_action_row = Frame(self.main)
        self.secondary_action_row.pack(fill=X, pady=3)

        self.broadcast_button = Button(self.secondary_action_row, text="Broadcast Message", command=self.broadcast_message)
        self.broadcast_button.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))

        self.my_info_button = Button(self.secondary_action_row, text="My info", command=self.edit_my_info)
        self.my_info_button.pack(side=LEFT, fill=X, expand=True, padx=(4, 0))

        self.hint_label = Label(self.main, text="Double-click a user to start chatting.", font=FONT_SMALL)
        self.hint_label.pack(anchor="w", pady=6)
        self._apply_theme()

    def _toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self._apply_theme()

    def _maybe_prompt_startup(self):
        if not should_prompt_startup():
            return
        mark_startup_prompted()
        if messagebox.askyesno(APP_NAME, "Start LAN Messenger automatically when this computer starts?"):
            try:
                enable_startup()
                messagebox.showinfo(APP_NAME, "Startup enabled. The app will open minimized to the tray at startup.")
            except Exception as exc:
                messagebox.showwarning(APP_NAME, f"Could not enable startup automatically:\n{exc}")

    def _set_my_status(self, status):
        self.manual_status = status
        self.last_activity_at = time.time()
        self._set_effective_status(status)

    def _set_effective_status(self, status):
        if status not in STATUS_VALUES or status == self.my_status:
            return
        self.my_status = status
        self.network.set_status(status)
        self.status_selector.set_value(status)
        self.status_label.configure(text=f"{len(self.peer_rows)} online | You: {status}")

    def _bind_activity_tracking(self):
        for sequence in ("<Any-KeyPress>", "<Any-Button>", "<Motion>", "<MouseWheel>"):
            self.root.bind_all(sequence, self._record_activity, add="+")

    def _record_activity(self, _event=None):
        self.last_activity_at = time.time()

    def _poll_idle_status(self):
        idle_seconds = system_idle_seconds(self.last_activity_at)
        if self.manual_status == "Offline":
            desired_status = "Offline"
        elif idle_seconds >= AUTO_OFFLINE_SECONDS:
            desired_status = "Offline"
        elif idle_seconds >= AUTO_AFK_SECONDS:
            desired_status = "AFK"
        else:
            desired_status = self.manual_status
        self._set_effective_status(desired_status)
        self.root.after(IDLE_CHECK_INTERVAL_MS, self._poll_idle_status)

    def edit_my_info(self):
        updated_name = simpledialog.askstring(APP_NAME, "Your username:", initialvalue=self.display_name)
        updated_name = updated_name.strip() if updated_name else ""
        if not updated_name:
            return
        self.display_name = updated_name
        save_display_name(updated_name)
        self.network.set_display_name(updated_name)
        messagebox.showinfo(APP_NAME, "Your username was updated.")

    def _apply_theme(self):
        self.theme = DARK_THEME if self.dark_mode else LIGHT_THEME
        theme = self.theme
        schedule_title_bar_theme(self.root, self.dark_mode)
        self.root.configure(bg=theme["window"])
        self.header.configure(bg=theme["header"])
        self.header_controls.configure(bg=theme["header"])
        self.update_button_wrap.configure(bg=theme["header"])
        self.main.configure(bg=theme["panel"])
        self.action_row.configure(bg=theme["panel"])
        self.secondary_action_row.configure(bg=theme["panel"])
        self.status_label.configure(bg=theme["panel"], fg=theme["text_fg"])
        self.hint_label.configure(bg=theme["panel"], fg=theme["text_fg"])
        self.update_button.configure(
            bg=theme["button_bg"],
            fg=theme["button_fg"],
            activebackground=theme["select_bg"],
            activeforeground=theme["select_fg"],
        )
        self._draw_update_badge()
        self._draw_update_progress()
        self.status_selector.configure_theme(theme, theme["header"])
        self.theme_toggle.configure(bg=theme["header"])
        self.theme_toggle.set_dark(self.dark_mode)
        for button in [self.open_button, self.broadcast_button, self.refresh_button, self.my_info_button]:
            button.configure(
                bg=theme["button_bg"],
                fg=theme["button_fg"],
                activebackground=theme["select_bg"],
                activeforeground=theme["select_fg"],
            )
        self.peer_list.configure_theme(theme)
        for conversation in list(self.conversations.values()):
            conversation.apply_theme()

    def _poll_events(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break

            kind = event[0]
            if kind == "peers":
                self._set_peers(event[1])
            elif kind == "new_peer":
                play_sound("new_user_online")
            elif kind == "message":
                sender_id, sender, text = event[1], event[2], event[3]
                play_sound("incoming_message")
                conversation_was_open = self._has_open_conversation(sender_id)
                self.history.add(sender_id, sender, text)
                conversation = self._conversation_for(sender_id, sender)
                if not conversation.is_focused():
                    self.unread_counts[sender_id] = self.unread_counts.get(sender_id, 0) + 1
                    self._refresh_peer_list()
                conversation.hide_typing()
                if conversation_was_open:
                    conversation.append_chat(sender, text)
                conversation.bring_to_front()
            elif kind == "typing":
                sender_id, sender, is_typing = event[1], event[2], event[3]
                conversation = self.conversations.get(sender_id)
                if conversation:
                    conversation.show_typing(sender, is_typing)
            elif kind == "file":
                sender_id, sender, target, size = event[1], event[2], event[3], event[4]
                play_sound("file_received")
                conversation_was_open = self._has_open_conversation(sender_id)
                self.history.add(
                    sender_id,
                    sender,
                    f"{sender} sent a file: {Path(target).name} ({size:,} bytes). Saved to {target}",
                    "received_file",
                    {"target": target, "size": size},
                )
                conversation = self._conversation_for(sender_id, sender)
                if conversation_was_open:
                    conversation.append_received_file(sender, target, size)
                conversation.bring_to_front()
            elif kind == "conversation_system":
                peer_id, text = event[1], event[2]
                should_save = len(event) < 4 or event[3]
                if should_save:
                    self.history.add(peer_id, "You", text, "file")
                conversation = self.conversations.get(peer_id)
                if conversation:
                    conversation.append_system(text)
            elif kind == "broadcast_done":
                sent, total = event[1], event[2]
                messagebox.showinfo(APP_NAME, f"Broadcast sent to {sent} of {total} online user(s).")
            elif kind == "update_downloaded":
                version, target = event[1], event[2]
                self._hide_update_progress()
                should_restart = messagebox.askyesno(
                    APP_NAME,
                    f"Version {version} was downloaded.\n\nRestart into the updated app now?",
                )
                if should_restart:
                    self._launch_downloaded_update(target)
            elif kind == "update_button_ready":
                self.update_button.configure(state="normal")
                self._hide_update_progress()
            elif kind == "update_progress":
                downloaded, total = event[1], max(1, event[2])
                percent = min(100, int(downloaded * 100 / total))
                self._show_update_progress(percent)
            elif kind == "error":
                messagebox.showwarning(APP_NAME, event[1])

        self.root.after(200, self._poll_events)

    def _show_update_progress(self, percent):
        self.update_progress_percent = percent
        self.update_button.configure(text=f"{percent}%")
        if not self.update_progress.winfo_ismapped():
            self.update_progress.place(x=8, rely=1, y=-7, width=74, height=4)
        self._draw_update_progress()

    def _hide_update_progress(self):
        self.update_progress_percent = 0
        self.update_progress.place_forget()
        self.update_button.configure(text="Update")

    def _draw_update_progress(self):
        percent = getattr(self, "update_progress_percent", 0)
        theme = self.theme
        self.update_progress.configure(bg=theme["button_bg"])
        self.update_progress.delete("all")
        width = max(1, self.update_progress.winfo_width() or 74)
        height = max(1, self.update_progress.winfo_height() or 4)
        self.update_progress.create_rectangle(0, 0, width, height, fill=theme["border"], outline=theme["border"])
        fill_width = max(1, int(width * min(100, max(0, percent)) / 100))
        self.update_progress.create_rectangle(0, 0, fill_width, height, fill=theme["select_bg"], outline=theme["select_bg"])

    def _conversation_for(self, peer_id, fallback_name=None):
        peer = self.network.peers.get(peer_id)
        if not peer:
            peer = {"id": peer_id, "name": fallback_name or "Unknown", "host": "", "port": TCP_PORT, "status": "Available"}
        conversation = self.conversations.get(peer_id)
        if conversation and conversation.window.winfo_exists():
            conversation.update_peer(peer)
            return conversation
        if conversation:
            self.conversations.pop(peer_id, None)

        peer_name = peer.get("name") or fallback_name
        if peer_name:
            for existing_id, existing in list(self.conversations.items()):
                if not existing.window.winfo_exists():
                    self.conversations.pop(existing_id, None)
                    continue
                if existing.peer.get("name") == peer_name:
                    existing.update_peer(peer)
                    self.conversations.pop(existing_id, None)
                    self.conversations[peer_id] = existing
                    return existing
        conversation = ConversationWindow(self, peer)
        self.conversations[peer_id] = conversation
        return conversation

    def _has_open_conversation(self, peer_id):
        conversation = self.conversations.get(peer_id)
        return bool(conversation and conversation.window.winfo_exists())

    def open_selected_conversation(self):
        selection = self.peer_list.curselection()
        if not selection:
            messagebox.showinfo(APP_NAME, "Choose an online user first.")
            return
        peer = self.peer_rows[selection[0]]
        self.clear_unread(peer["id"])
        conversation = self._conversation_for(peer["id"], peer["name"])
        conversation.bring_to_front()

    def broadcast_message(self):
        peers = list(self.peer_rows)
        if not peers:
            messagebox.showinfo(APP_NAME, "No online users to broadcast to.")
            return
        text = simpledialog.askstring(APP_NAME, f"Broadcast message to {len(peers)} online user(s):")
        text = text.strip() if text else ""
        if not text:
            return
        for peer in peers:
            self.history.add(peer["id"], "You", text)
            conversation = self.conversations.get(peer["id"])
            if conversation and conversation.window.winfo_exists():
                conversation.append_chat("You", text)
        threading.Thread(target=self._broadcast_worker, args=(peers, text), daemon=True).start()

    def _broadcast_worker(self, peers, text):
        sent = self.network.broadcast_message(peers, text)
        self.events.put(("broadcast_done", sent, len(peers)))

    def check_for_update(self):
        same_platform_peers = [
            peer
            for peer in self.peer_rows
            if peer.get("platform") == current_update_platform()
        ]
        candidates = [peer for peer in same_platform_peers if is_newer_version(peer.get("version", "0.0.0"))]
        if not candidates:
            if same_platform_peers:
                show_themed_info(self.root, APP_NAME, f"Already on latest version {APP_VERSION}", self.dark_mode)
            else:
                show_themed_info(
                    self.root,
                    APP_NAME,
                    f"No same-platform online users found.\n\nCurrent version: {APP_VERSION}",
                    self.dark_mode,
                )
            return
        peer = sorted(candidates, key=lambda item: version_tuple(item.get("version", "0.0.0")), reverse=True)[0]
        if not messagebox.askyesno(APP_NAME, f"Version {peer.get('version')} is available from {peer['name']}.\n\nDownload it now?"):
            return
        self.update_button.configure(state="disabled")
        threading.Thread(target=self._update_worker, args=(peer,), daemon=True).start()

    def _has_available_update(self):
        return any(
            peer.get("platform") == current_update_platform()
            and is_newer_version(peer.get("version", "0.0.0"))
            for peer in self.peer_rows
        )

    def _refresh_update_badge(self):
        if self._has_available_update():
            self.update_badge.place(relx=1, rely=0, x=-2, y=2, anchor="ne")
        else:
            self.update_badge.place_forget()

    def _draw_update_badge(self):
        self.update_badge.configure(bg=self.theme["header"])
        self.update_badge.delete("all")
        self.update_badge.create_oval(1, 1, 14, 14, fill="#dc2626", outline="#dc2626")
        self.update_badge.create_text(7.5, 7, text="!", fill="#ffffff", font=FONT_SMALL)

    def _update_worker(self, peer):
        try:
            self.network.request_update(peer)
        finally:
            self.events.put(("update_button_ready",))

    def _launch_downloaded_update(self, target):
        path = Path(target)
        if not path.exists():
            messagebox.showwarning(APP_NAME, f"Downloaded update was not found:\n{target}")
            return
        try:
            if getattr(sys, "frozen", False):
                if sys.platform.startswith("win"):
                    launcher = _windows_update_launcher(path.resolve(), Path(sys.executable).resolve(), path.stat().st_size)
                    subprocess.Popen([str(launcher)], cwd=str(launcher.parent), creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    subprocess.Popen([str(path), UPDATED_CHILD_ARG], cwd=str(path.parent))
            else:
                subprocess.Popen([sys.executable, str(path), UPDATED_CHILD_ARG], cwd=str(path.parent))
            self.quit_app()
        except OSError as exc:
            messagebox.showwarning(APP_NAME, f"Could not start downloaded update:\n{exc}")

    def clear_unread(self, peer_id):
        if self.unread_counts.pop(peer_id, None) is not None:
            self._refresh_peer_list()

    def _refresh_peer_list(self):
        selected_id = None
        selection = self.peer_list.curselection()
        if selection and selection[0] < len(self.peer_rows):
            selected_id = self.peer_rows[selection[0]]["id"]

        self.peer_list.set_rows(self.peer_rows, self.unread_counts, selected_id)
        self._refresh_update_badge()

    def _set_peers(self, peers):
        selected_id = None
        selection = self.peer_list.curselection()
        if selection and selection[0] < len(self.peer_rows):
            selected_id = self.peer_rows[selection[0]]["id"]

        self.peer_rows = peers
        self.status_label.configure(text=f"{len(peers)} online | You: {self.my_status}")

        active_ids = {peer["id"] for peer in peers}
        for peer_id in list(self.unread_counts):
            if peer_id not in active_ids:
                del self.unread_counts[peer_id]

        for peer in peers:
            if peer["id"] in self.conversations:
                self.conversations[peer["id"]].update_peer(peer)
        self._refresh_peer_list()

    def _refresh_peers(self):
        self._set_peers(self.network.peers.list())

    def _on_close(self):
        if self.tray.icon:
            self.hide_to_tray()
            return
        self.quit_app()

    def hide_to_tray(self):
        if not self.tray.icon and not self.tray.start():
            return
        self.hidden_to_tray = True
        self.root.withdraw()

    def show_window(self):
        self.hidden_to_tray = False
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def quit_app(self):
        for conversation in list(self.conversations.values()):
            if conversation.window.winfo_exists():
                conversation.window.destroy()
        self.tray.stop()
        self.network.stop()
        self.root.destroy()


def main():
    if maybe_launch_pending_update():
        return
    if ensure_installed_location():
        return
    if not acquire_single_instance_lock():
        return
    root = TkinterDnD.Tk() if DND_AVAILABLE else Tk()
    ChatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
