import tkinter as tk
from tkinter import ttk, messagebox
import json, re
import subprocess
import os, subprocess, shutil
import webbrowser
from pynput import keyboard as pynput_keyboard


VERSION = "0.2.0"
MAINTAINERS = ["Animosity"]

CONFIG_FILE = "gg_presets.json"
_deps = {}
_hotkey_listener = None
_hotkey_map = {}

DEFAULT_PRESETS = {
    "1": {"display": 1, "gamma": 128, "vibrance": 0, "vibrance_mode": "nvidia", "hotkey": "alt+1"},
    "2": {"display": 1, "gamma": 144, "vibrance": 512, "vibrance_mode": "nvidia", "hotkey": "alt+2"},
    "3": {"display": 1, "gamma": 255, "vibrance": 1023, "vibrance_mode": "nvidia", "hotkey": "alt+3"},
}


# ----------------------------
# Utility functions
# ----------------------------

def detect_monitors():
    try:
        out = subprocess.check_output(["ddcutil", "detect"], text=True)
    except Exception:
        return []

    monitors = []
    current_index = None

    for line in out.splitlines():
        line = line.strip()
        m = re.match(r"Display\s+(\d+)", line)
        if m:
            current_index = int(m.group(1))
        if "Model:" in line and current_index is not None:
            name = line.split("Model:", 1)[1].strip()
            monitors.append((current_index, name))
            current_index = None

    return monitors


def load_presets():
    if not os.path.exists(CONFIG_FILE):
        save_presets(DEFAULT_PRESETS)

    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)

    # Backfill missing keys
    for pid, defaults in DEFAULT_PRESETS.items():
        data.setdefault(pid, {})
        for k, v in defaults.items():
            data[pid].setdefault(k, v)

    return data


def save_presets(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

def check_linux_dependencies():
    """
    Checks for required Linux dependencies: ddcutil and nvibrant.

    Returns:
        dict: {
            "ddcutil": {"installed": bool, "path": str | None, "version": str | None},
            "nvibrant": {"installed": bool, "path": str | None, "version": str | None},
        }
    """
    deps = ["ddcutil", "nvibrant"]
    results = {}

    for dep in deps:
        path = shutil.which(dep)
        installed = path is not None
        version = None

        if installed:
            try:
                # Most CLI tools support --version; suppress stderr just in case
                version = subprocess.check_output(
                    [dep, "--version"],
                    stderr=subprocess.DEVNULL,
                    text=True
                ).strip()
            except Exception:
                # Tool exists but doesn't support --version or failed
                version = None

        results[dep] = {
            "installed": installed,
            "path": path,
            "version": version,
        }

    return results




def apply_preset(display, gamma, vibrance):
    """ README/FOLDME
    This function is vital and is where compatibilty will absolutely break.
    EXTERNAL DEPENDENCIES: ddcutil, nvibrant

    This function only supports monitors implementing MCCS (Monitor Control
    Command Set) over I2C, and therefore can be controlled via ddcutil.

    The purpose of this function (and application) is to dynamically adjust the
    hardware gamma configuration (only using command 0x72 - Gamma) of the
    primary gaming monitor. Additionally, it is to adjust the digital vibrance
    dynamically for the color-challenged users.

    Problems:
    * Destructive settings - Does not store original monitor configuration
    * nvibrant parameters are structured for the formatted output of (`nvibrant`)
    using a singular GPU RTX30XX-series presence with one HDMI and 3 DP outputs.
    * ddcutil 0x72 value packing is tailored to Dell S2716DG (see Notes)
    * *FIXED 24DEC2025* -- NVIBRANT call doesn't use Monitor index (always #2)
    * NVIDIA-only support for vibrance control

    Notes:
    (1) Dell S2716DG only uses the MSByte of the gamma value. Writing LSByte != 0x00
    can cause CRC Verify errors.
    (2) The scheme of only writing MSByte has not been
    tested on other monitors.

    (3) Development reference:
            Output of nvibrant:
                ❯ nvibrant
                    Driver version: (580.105.08)

                    Display 0:
                    • (0, HDMI) • Set vibrance (    0) • None
                    • (1, DP  ) • Set vibrance (    0) • Success
                    • (2, DP  ) • Set vibrance (    0) • None
                    • (3, DP  ) • Set vibrance (    0) • Success
                    • (4, DP  ) • Set vibrance (    0) • None
                    • (5, DP  ) • Set vibrance (    0) • Success
                    • (6, DP  ) • Set vibrance (    0) • None

            Therefore:
                the command structure is: `nvibrant 0 <vibrance_monitor1> 0
                <vibrance_monitor2> 0 <vibrance_monitor3>`. Monitor-relative
                parameter position is (2*display)-1
                By discovery, vibrance value range is [-1023, 1023]


    """
    global _deps
    # Apply monitor gamma via ddcutil if installed.
    # See Notes (1-2).
    if _deps.get("nvibrant", {}).get("installed"):
        subprocess.Popen([
            "ddcutil",
            "-d", str(display),
            "setvcp", "0x72", f"0x{gamma:02X}00"
        ])

    # Apply NVIDIA vibrance if nvibrant is installed
    if _deps.get("nvibrant", {}).get("installed"):
        cmd = ["nvibrant"]+["0"] * 7 # See Note (3).
        # The parameter position is 2n-1 but it is already offset by the nvibrant string.
        # Insert vibrance value into monitor-relative parameter position
        cmd[2*display]=str(vibrance)
        subprocess.Popen(cmd)

# ----------------------------
# GUI
# ----------------------------

class PresetPane(ttk.Frame):
    def __init__(self, parent, preset_id, title, presets, get_display):
        super().__init__(parent, padding=10, relief="ridge")
        self.preset_id = str(preset_id)
        self.presets = presets
        self.get_display = get_display

        self.base_title = f"Preset {self.preset_id}"
        self.title_label = ttk.Label(
            self,
            text=f"{self.base_title} ({self.presets[self.preset_id]['hotkey'].upper()})",
            font=("Sans", 12, "bold"),
            cursor="hand2",
            foreground="black"
        )
        self.title_label.pack(pady=(0, 10))
        self.title_label.bind("<Button-1>", self.open_hotkey_config)
        self.title_label.bind("<Enter>", lambda e: self._start_hover_animation())
        self.title_label.bind("<Leave>", lambda e: self._stop_hover_animation())
        self.title_label.configure(foreground="black")
        # ---- Gamma ----
        ttk.Label(self, text="Gamma").pack(anchor="w")
        g_frame = ttk.Frame(self)
        g_frame.pack(fill="x")

        self.gamma = tk.IntVar(value=presets[self.preset_id]["gamma"])

        self.gamma_entry = ttk.Entry(g_frame, width=6, textvariable=self.gamma)
        self.gamma_entry.pack(side="right", padx=5)
        self.gamma_entry.bind("<Return>", self._sync_gamma_entry)

        self.gamma_slider = ttk.Scale(
            g_frame, from_=0, to=255,
            orient="horizontal",
            command=self._sync_gamma_slider
        )
        self.gamma_slider.set(self.gamma.get())
        self.gamma_slider.pack(side="left", expand=True, fill="x")

       # ---- Vibrance Mode ----
        ttk.Label(self, text="Vibrance Source").pack(anchor="w", pady=(10, 0))

        self.vibrance_mode = tk.StringVar(
            value=presets[self.preset_id].get("vibrance_mode", "NVIDIA")
        )

        mode_frame = ttk.Frame(self)
        mode_frame.pack(anchor="w", pady=(0, 5))

        ttk.Radiobutton(
            mode_frame, text="NVIDIA Digital Vibrance",
            variable=self.vibrance_mode, value="nvidia",
            command=self._update_vibrance_ui
        ).pack(side="left")

        ttk.Radiobutton(
            mode_frame, text="Monitor Color Vibrance (DDC)",
            variable=self.vibrance_mode, value="ddc",
            command=self._update_vibrance_ui
        ).pack(side="left", padx=(10, 0))


    # ---- Sync helpers ----

    def _sync_gamma_slider(self, val):
        self.gamma.set(int(float(val)))

    def _sync_gamma_entry(self, _):
        try:
            v = int(self.gamma.get())
            if 0 <= v <= 255:
                self.gamma_slider.set(v)
        except Exception:
            pass

    def _sync_vib_slider(self, val):
        self.vibrance.set(int(float(val)))

    def _sync_vib_entry(self, _):
        try:
            v = int(self.vibrance.get())
            if -1023 <= v <= 1023:
                self.vib_slider.set(v)
        except Exception:
            pass

    def _start_hover_animation(self):
        self._hover_active = True
        self._hover_index = 0
        self._animate_hover()

    def _stop_hover_animation(self):
        self._hover_active = False
        if hasattr(self, "_hover_after_id"):
            self.after_cancel(self._hover_after_id)
        self.title_label.configure(foreground="black")

    def _animate_hover(self):
        if not self._hover_active:
            return

        colors = ["#000000", "#555555", "#FFFFFF", "#555555"]
        self.title_label.configure(foreground=colors[self._hover_index])

        self._hover_index = (self._hover_index + 1) % len(colors)
        self._hover_after_id = self.after(120, self._animate_hover)

    def refresh_title(self):
        hotkey = self.presets[self.preset_id]["hotkey"]
        self.title_label.configure(
            text=f"{self.base_title} ({hotkey.upper()})"
    )

    # ---- Preset actions ----

    def save(self):
        p = self.presets[self.preset_id]
        p["gamma"] = self.gamma.get()
        p["vibrance"] = self.vibrance.get()
        p["display"] = self.get_display()
        save_presets(self.presets)

    def apply(self):
        apply_preset(
            self.get_display(),
            self.gamma.get(),
            self.vibrance.get()
        )

    # ---- Hotkey config ----

    def open_hotkey_config(self, _=None):
        win = tk.Toplevel(self)
        win.title(f"Configure Hotkey – Preset {self.preset_id}")
        win.transient(self)

        win.resizable(False, False)

        ttk.Label(win, text="Current Hotkey:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        ttk.Label(
            win,
            text=self.presets[self.preset_id]["hotkey"],
            font=("Sans", 10, "bold")
        ).grid(row=0, column=1, padx=10, pady=5, sticky="w")

        ttk.Label(win, text="New Hotkey:").grid(row=1, column=0, padx=10, pady=5, sticky="w")

        hotkey_var = tk.StringVar()
        entry = ttk.Entry(win, textvariable=hotkey_var, width=25)
        entry.grid(row=1, column=1, padx=10, pady=5)
        entry.focus_set()

        pressed = set()
        win.wait_visibility()
        win.grab_set()

        def key_to_name(key):
            if isinstance(key, pynput_keyboard.Key):
                return key.name
            return key.char

        def on_press(key):
            name = key_to_name(key)
            if name:
                pressed.add(name)
                hotkey_var.set("+".join(pressed))

        def on_release(key):
            name = key_to_name(key)
            pressed.discard(name)

        listener = pynput_keyboard.Listener(
            on_press=on_press,
            on_release=on_release
        )
        listener.start()


        def clear():
            pressed.clear()
            hotkey_var.set("")

        def save_hotkey():
            new = hotkey_var.get().strip()
            if not new:
                messagebox.showerror("Error", "Hotkey cannot be empty.")
                return

            self.presets[self.preset_id]["hotkey"] = new
            save_presets(self.presets)

            self.refresh_title()
            listener.stop()
            setup_hotkeys(self.master)
            win.destroy()

        ttk.Button(win, text="Clear", command=clear).grid(row=2, column=0, padx=10, pady=10)
        ttk.Button(win, text="Save Hotkey", command=save_hotkey).grid(row=2, column=1, padx=10, pady=10)

        win.protocol("WM_DELETE_WINDOW", lambda: (listener.stop(), win.destroy()))

# ----------------------------
# Hotkeys + Menu
# ----------------------------

def setup_hotkeys_old(container):
    #try: keyboard.unhook_all_hotkeys()
    #except Exception:
    #    pass
    for child in container.winfo_children():
        if isinstance(child, PresetPane):
            hk = child.presets[child.preset_id]["hotkey"]
            keyboard.add_hotkey(hk, child.apply)

def setup_hotkeys(container):
    global _hotkey_listener, _hotkey_map

    _hotkey_map = {}

    for child in container.winfo_children():
        if isinstance(child, PresetPane):
            hk = child.presets[child.preset_id]["hotkey"]

            # pynput needs all hotkey strings which aren't single characters to be <wrapped>'
            # Look at this ugly piece of work right here.
            pynput_hk = "+".join(
                f"<{k}>" if len(k) >= 2 else k
                for k in hk.lower().split("+")
            )

            _hotkey_map[pynput_hk] = child.apply

    if _hotkey_listener:
        _hotkey_listener.stop()
    _hotkey_listener = pynput_keyboard.GlobalHotKeys(_hotkey_map)
    _hotkey_listener.start()

def show_about():
    def open_url(url):
        webbrowser.open_new(url)

    win = tk.Toplevel()
    win.title(f"About gamergamma v{VERSION}")
    win.resizable(False, False)
    win.transient()
    win.grab_set()

    frame = ttk.Frame(win, padding=12)
    frame.pack(fill="both", expand=True)

    # Author (clickable)
    author_label = ttk.Label(
        frame,
        text="Author: github.com/Animosity",
        foreground="blue",
        cursor="hand2"
    )
    author_label.pack(anchor="w")
    author_label.bind(
        "<Button-1>",
        lambda e: open_url("https://github.com/Animosity/gamergamma")
    )

    # Body text (pre-requirements)
    body_text = (
        "By and for colorblind gamers (and allies).\nHow to use: Click the Preset # (<keybind>) title to configure the hotkey for the preset.\n\n"
        "Adjust and save the gamma and vibrance settings for each preset you want to use.\n\n"
        "Switch between the presets in any game/app of your choice, using your hotkeys.\n\n"
        "Settings saved in gg_presets.json in your $pwd when you execute gamergamma.\n\n"
        "Requirements:"
    )
    ttk.Label(frame, text=body_text, justify="left", wraplength=420).pack(anchor="w")

    # Requirements links
    req_frame = ttk.Frame(frame)
    req_frame.pack(anchor="w", padx=12, pady=(4, 0))

    ddc_label = ttk.Label(
        req_frame,
        text="• ddcutil (https://github.com/rockowitz/ddcutil)",
        foreground="blue",
        cursor="hand2"
    )
    ddc_label.pack(anchor="w")
    ddc_label.bind(
        "<Button-1>",
        lambda e: open_url("https://github.com/rockowitz/ddcutil")
    )

    nvibrant_label = ttk.Label(
        req_frame,
        text="• nvibrant (NVIDIA-only; https://github.com/Tremeschin/nvibrant)",
        foreground="blue",
        cursor="hand2"
    )
    nvibrant_label.pack(anchor="w")
    nvibrant_label.bind(
        "<Button-1>",
        lambda e: open_url("https://github.com/Tremeschin/nvibrant")
    )

    # Footer
    ttk.Label(
        frame,
        text="\nCreated: December 2025",
        justify="left"
    ).pack(anchor="w")

    # OK button
    ttk.Button(frame, text="OK", command=win.destroy).pack(pady=(10, 0))


def add_dependency_status_bar(root):
    """
    Adds a subtle status bar to the bottom-right of the main window.
    Shows warnings if dependencies are missing.
    """
    # Persist the result here, lazily as global because only want to make calls
    # to the dependencies which exist, without failing hard.
    global _deps
    _deps = check_linux_dependencies()

    status_parts = []
    if not _deps.get("ddcutil", {}).get("installed", False):
        msg = "Gamma disabled: ddcutil not found."
        print(msg)
        status_parts.append(msg)
    if not _deps.get("nvibrant", {}).get("installed", False):
        msg = "Vibrance disabled: nvibrant not found."
        print(msg)
        status_parts.append(msg)

    status_text = " | ".join(status_parts) if status_parts else ""

    # Status bar frame
    status_frame = ttk.Frame(root)
    status_frame.pack(side="bottom", fill="x", padx=5, pady=2)

    # Right-aligned label
    status_label = ttk.Label(
        status_frame,
        text=status_text,
        font=("Sans", 9),
        foreground="#AA0000" if status_parts else "#000000",
        anchor="e"
    )
    status_label.pack(side="right", anchor="e")

    return status_label

# ----------------------------
# Main App
# ----------------------------

def main():
    print(f"gamergamma v{VERSION}\n  created by: github.com/Animosity")
    presets = load_presets()
    monitors = detect_monitors()

    root = tk.Tk()
    root.title(f"gamergamma v{VERSION}")

    menubar = tk.Menu(root)
    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(label="About", command=show_about)
    menubar.add_cascade(label="Help", menu=help_menu)
    root.config(menu=menubar)

    top = ttk.Frame(root, padding=10)
    top.pack(fill="x")

    ttk.Label(top, text="Monitor:").pack(side="left")

    monitor_var = tk.StringVar()
    monitor_map = {}
    display_values = []

    for idx, name in monitors:
        label = f"{idx} – {name}"
        monitor_map[label] = idx
        display_values.append(label)

    preset_display = presets["1"]["display"]

    for label, idx in monitor_map.items():
        if idx == preset_display:
            monitor_var.set(label)
            break

    combo = ttk.Combobox(
        top,
        textvariable=monitor_var,
        values=display_values,
        state="readonly",
        width=40
    )
    combo.pack(side="left", padx=10)

    def get_selected_display():
        return monitor_map.get(monitor_var.get(), preset_display)

    container = ttk.Frame(root, padding=10)
    container.pack(fill="both", expand=True)

    for i in ("1", "2", "3"):
        PresetPane(
            container,
            i,
            f"Preset ({presets[i]['hotkey'].upper()})",
            presets,
            get_selected_display
        ).pack(side="left", expand=True, fill="both", padx=5)


    status_label = add_dependency_status_bar(root)
    setup_hotkeys(container)
    root.mainloop()


if __name__ == "__main__":
    main()
