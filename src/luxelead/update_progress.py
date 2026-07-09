"""Update installation progress monitor (separate process)."""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk


def progress_file_path(update_dir: str) -> str:
    return os.path.join(update_dir, "progress.txt")


def init_update_progress(update_dir: str, percent: int, message: str) -> None:
    os.makedirs(update_dir, exist_ok=True)
    write_update_progress(update_dir, percent, message)


def write_update_progress(update_dir: str, percent: int, message: str) -> None:
    path = progress_file_path(update_dir)
    with open(path, "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(f"{percent}\n{message}\n")


def read_update_progress(update_dir: str) -> tuple[int, str]:
    path = progress_file_path(update_dir)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle.read().splitlines() if line.strip()]
        if not lines:
            return 0, "准备安装更新..."
        percent = int(lines[0])
        message = lines[1] if len(lines) > 1 else ""
        return percent, message
    except (OSError, ValueError):
        return 0, "准备安装更新..."


def ensure_powershell_progress_monitor(update_dir: str) -> str:
    """Write a standalone PowerShell progress UI that does not lock app files."""
    update_dir = os.path.abspath(update_dir)
    os.makedirs(update_dir, exist_ok=True)
    ps1_path = os.path.join(update_dir, "progress_monitor.ps1")
    script = r'''param(
    [Parameter(Mandatory = $true)]
    [string]$ProgressFile
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = "正在安装更新"
$form.Size = New-Object System.Drawing.Size(480, 190)
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$form.TopMost = $true

$title = New-Object System.Windows.Forms.Label
$title.AutoSize = $true
$title.Font = New-Object System.Drawing.Font("Microsoft YaHei", 11, [System.Drawing.FontStyle]::Bold)
$title.Location = New-Object System.Drawing.Point(20, 16)
$title.Text = "正在安装更新，请勿关闭此窗口"
$form.Controls.Add($title)

$status = New-Object System.Windows.Forms.Label
$status.AutoSize = $false
$status.Size = New-Object System.Drawing.Size(430, 40)
$status.Location = New-Object System.Drawing.Point(20, 48)
$status.Text = "准备安装更新..."
$form.Controls.Add($status)

$bar = New-Object System.Windows.Forms.ProgressBar
$bar.Location = New-Object System.Drawing.Point(20, 92)
$bar.Size = New-Object System.Drawing.Size(430, 24)
$bar.Minimum = 0
$bar.Maximum = 100
$form.Controls.Add($bar)

$pct = New-Object System.Windows.Forms.Label
$pct.AutoSize = $true
$pct.Location = New-Object System.Drawing.Point(20, 124)
$pct.Text = "0%"
$form.Controls.Add($pct)

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 200
$timer.Add_Tick({
    if (-not (Test-Path -LiteralPath $ProgressFile)) { return }
    try {
        $lines = Get-Content -LiteralPath $ProgressFile -Encoding UTF8 | Where-Object { $_ -ne "" }
        if (-not $lines) { return }
        $value = [int]$lines[0]
        $msg = if ($lines.Count -gt 1) { [string]$lines[1] } else { "" }
        if ($value -ge 0) {
            $bar.Value = [Math]::Min(100, [Math]::Max(0, $value))
            $pct.Text = "$value%"
        }
        if ($msg) { $status.Text = $msg }
        if ($value -lt 0) {
            $timer.Stop()
            $form.Hide()
            [System.Windows.Forms.MessageBox]::Show($msg, "更新失败", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
            $form.Close()
        }
        elseif ($value -ge 100) {
            $timer.Stop()
            $form.Hide()
            [System.Windows.Forms.MessageBox]::Show("新版本已安装完成，程序已自动重启。`n`n如未看到主窗口，请进入 LuxeLead 文件夹手动双击 exe 启动。", "更新完成", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
            $form.Close()
        }
    } catch {}
})
$form.Add_FormClosing({
    param($sender, $e)
    if ($bar.Value -gt 0 -and $bar.Value -lt 100) {
        $e.Cancel = $true
        [System.Windows.Forms.MessageBox]::Show("更新安装进行中，请等待完成后再关闭。", "正在更新", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
    }
})
$timer.Start()
[void]$form.ShowDialog()
'''
    with open(ps1_path, "w", encoding="utf-8-sig", newline="\r\n") as handle:
        handle.write(script)
    return ps1_path


def launch_powershell_progress_monitor(update_dir: str) -> None:
    update_dir = os.path.abspath(update_dir)
    ps1_path = ensure_powershell_progress_monitor(update_dir)
    progress_file = progress_file_path(update_dir)
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ps1_path,
            "-ProgressFile",
            progress_file,
        ],
        close_fds=True,
        cwd=update_dir,
    )


class UpdateProgressMonitor:
    def __init__(self, update_dir: str):
        self.update_dir = os.path.abspath(update_dir)
        self.root = tk.Tk()
        self.root.title("正在安装更新")
        self.root.geometry("460x180")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_attempt)

        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            text="正在安装更新，请勿关闭此窗口",
            font=("Microsoft YaHei", 11, "bold"),
        ).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        self.status_label = ttk.Label(frame, text="准备安装更新...", wraplength=420)
        self.status_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 10))

        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progress.grid(row=2, column=0, sticky=tk.EW, pady=(0, 6))

        self.percent_label = ttk.Label(frame, text="0%")
        self.percent_label.grid(row=3, column=0, sticky=tk.E)

        self.root.attributes("-topmost", True)
        self.root.update_idletasks()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.after(200, self._poll_progress)

    def _on_close_attempt(self):
        messagebox.showwarning(
            "正在更新",
            "更新安装进行中，请等待完成后再关闭。",
            parent=self.root,
        )

    def _poll_progress(self):
        percent, message = read_update_progress(self.update_dir)
        self.progress.config(value=max(0, min(100, percent)))
        self.percent_label.config(text=f"{percent}%")
        if message:
            self.status_label.config(text=message)

        if percent < 0:
            self.root.withdraw()
            messagebox.showerror("更新失败", message or "安装更新时发生错误，请稍后重试。")
            self.root.destroy()
            return

        if percent >= 100:
            self.root.withdraw()
            messagebox.showinfo(
                "更新完成",
                "新版本已安装完成，程序已自动重启。\n\n如未看到主窗口，请进入 LuxeLead 文件夹手动双击 exe 启动。",
            )
            self.root.destroy()
            return

        self.root.after(200, self._poll_progress)

    def run(self):
        self.root.mainloop()


def run_update_progress_monitor(update_dir: str) -> None:
    UpdateProgressMonitor(update_dir).run()
