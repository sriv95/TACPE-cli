"""Native file picker: tkinter first, OS-provided command as fallback."""

import shutil
import subprocess
import sys


def browse_file() -> str | None:
    """Open native file picker (tkinter, else OS-provided command).
    Output: (str | None) chosen file path, or None if cancelled.
    Raises: FileNotFoundError if no picker is available on this OS.
    """
    try:
        return _browse_file_tkinter()
    except Exception:
        return _browse_file_os()


def _browse_file_tkinter() -> str | None:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="Select CSV file", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    root.destroy()
    return path or None


def _browse_file_os() -> str | None:
    """Raises: FileNotFoundError if no native picker is available on this OS."""
    if sys.platform == "darwin":
        script = 'POSIX path of (choose file with prompt "Select CSV file" of type {"csv"})'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    if sys.platform == "win32":
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms | Out-Null;"
            "$f = New-Object System.Windows.Forms.OpenFileDialog;"
            "$f.Filter = 'CSV files (*.csv)|*.csv|All files (*.*)|*.*';"
            "if ($f.ShowDialog() -eq 'OK') { Write-Output $f.FileName }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True
        )
        path = result.stdout.strip()
        return path or None

    for picker in (["zenity", "--file-selection", "--file-filter=*.csv"], ["kdialog", "--getopenfilename", "."]):
        if shutil.which(picker[0]):
            result = subprocess.run(picker, capture_output=True, text=True)
            path = result.stdout.strip()
            return path or None

    raise FileNotFoundError("no native file picker available")
