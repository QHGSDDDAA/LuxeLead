"""Version info and online update dialogs."""

import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .updater import (
    apply_windows_update,
    check_for_update,
    download_file,
    get_download_headers,
    get_executable_path,
    get_manifest_url,
    is_update_available,
    is_newer_version,
    load_local_release_notes,
    prepare_download_path,
    resolve_update_package,
    verify_sha256,
)
from .version import DISPLAY_VERSION, RELEASE_DATE, VERSION


class VersionInfoDialog:
    def __init__(self, parent, config=None):
        self.parent = parent
        self.config = config or {}
        self.manifest = None
        self.error_message = None

        self.window = tk.Toplevel(parent)
        self.window.title("版本信息")
        self.window.geometry("560x420")
        self.window.resizable(True, True)
        self.window.transient(parent)
        self.window.grab_set()

        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        ttk.Label(
            frame,
            text=f"当前版本：{DISPLAY_VERSION}（{VERSION}）",
            font=("Microsoft YaHei", 11, "bold"),
        ).grid(row=0, column=0, sticky=tk.W, pady=(0, 4))

        ttk.Label(
            frame,
            text=f"发布日期：{RELEASE_DATE}",
        ).grid(row=1, column=0, sticky=tk.W, pady=(0, 8))

        ttk.Label(frame, text="版本说明：").grid(row=2, column=0, sticky=tk.NW)

        notes_frame = ttk.Frame(frame)
        notes_frame.grid(row=3, column=0, sticky=tk.NSEW, pady=(4, 8))
        notes_frame.columnconfigure(0, weight=1)
        notes_frame.rowconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)

        self.notes_text = tk.Text(
            notes_frame,
            wrap=tk.WORD,
            height=12,
            font=("Microsoft YaHei", 10),
        )
        scrollbar = ttk.Scrollbar(notes_frame, orient=tk.VERTICAL, command=self.notes_text.yview)
        self.notes_text.configure(yscrollcommand=scrollbar.set)
        self.notes_text.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.notes_text.insert(tk.END, load_local_release_notes())
        self.notes_text.config(state=tk.DISABLED)

        self.remote_status = ttk.Label(frame, text="正在检查服务器最新版本...", foreground="#666666")
        self.remote_status.grid(row=4, column=0, sticky=tk.W, pady=(0, 8))

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=5, column=0, sticky=tk.E)

        self.update_button = ttk.Button(
            button_frame,
            text="检查更新",
            command=self.on_check_update_clicked,
            state=tk.DISABLED,
        )
        self.update_button.pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(button_frame, text="关闭", command=self.window.destroy).pack(side=tk.RIGHT)

        self.window.after(100, self._fetch_remote_version)

    def _fetch_remote_version(self):
        def worker():
            manifest, error = check_for_update(get_manifest_url(self.config), config=self.config)
            update_available = is_update_available(manifest) if manifest else False
            self.parent.after(
                0, lambda: self._show_remote_status(manifest, error, update_available)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _show_remote_status(self, manifest, error, update_available=False):
        self.manifest = manifest
        self.error_message = error
        self.update_button.config(state=tk.NORMAL)

        if error:
            self.remote_status.config(text=f"服务器：{error}", foreground="#aa6600")
            return

        remote_display = manifest.get("display_version", manifest.get("version", ""))
        remote_version = manifest.get("version", "")
        if update_available:
            if is_newer_version(remote_version):
                self.remote_status.config(
                    text=f"发现新版本：{remote_display}（{remote_version}）",
                    foreground="#cc3300",
                )
            else:
                self.remote_status.config(
                    text=f"发现新版本安装包（{remote_display}，内容已更新）",
                    foreground="#cc3300",
                )
        else:
            self.remote_status.config(
                text=f"已是最新版本（服务器：{remote_display}）",
                foreground="#008800",
            )

    def on_check_update_clicked(self):
        self.window.destroy()
        CheckUpdateDialog(self.parent, self.config, manifest=self.manifest)


class CheckUpdateDialog:
    def __init__(self, parent, config=None, manifest=None):
        self.parent = parent
        self.config = config or {}
        self.manifest = manifest
        self.update_package = None
        self.download_path = None

        self.window = tk.Toplevel(parent)
        self.window.title("检查更新")
        self.window.geometry("520x360")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(frame, text="正在检查更新...", wraplength=480)
        self.status_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 8))

        self.notes_text = tk.Text(frame, wrap=tk.WORD, height=10, font=("Microsoft YaHei", 10))
        self.notes_text.grid(row=1, column=0, sticky=tk.NSEW, pady=(0, 8))
        frame.rowconfigure(1, weight=1)

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky=tk.EW, pady=(0, 8))

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=3, column=0, sticky=tk.E)

        self.action_button = ttk.Button(button_frame, text="立即更新", command=self.on_update_clicked)
        self.action_button.pack(side=tk.RIGHT, padx=(8, 0))
        self.action_button.config(state=tk.DISABLED)

        ttk.Button(button_frame, text="关闭", command=self.window.destroy).pack(side=tk.RIGHT)

        if manifest is None:
            self.progress.start(10)
            self.window.after(100, self._check_update)
        else:
            self.window.after(100, lambda: self._start_apply_manifest(manifest))

    def _start_apply_manifest(self, manifest):
        def worker():
            update_available = is_update_available(manifest) if manifest else False
            self.parent.after(
                0, lambda: self._apply_manifest(manifest, None, update_available)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _check_update(self):
        def worker():
            manifest, error = check_for_update(get_manifest_url(self.config), config=self.config)
            update_available = is_update_available(manifest) if manifest else False
            self.parent.after(
                0, lambda: self._apply_manifest(manifest, error, update_available)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _apply_manifest(self, manifest, error, update_available=False):
        self.progress.stop()
        self.progress.config(mode="determinate", value=0)

        if error:
            self.status_label.config(text=error)
            return

        self.manifest = manifest
        remote_display = manifest.get("display_version", manifest.get("version", ""))
        remote_version = manifest.get("version", "")

        self.notes_text.delete("1.0", tk.END)
        self.notes_text.insert(tk.END, manifest.get("release_notes", "").strip())

        if update_available:
            patch_hint = ""
            pkg = resolve_update_package(manifest, VERSION)
            if pkg.get("_update_mode") == "patch":
                size_mb = (pkg.get("file_size") or 0) // (1024 * 1024)
                patch_hint = f"，增量包约 {size_mb} MB" if size_mb else "，将使用增量更新包"
            if is_newer_version(remote_version):
                self.status_label.config(
                    text=(
                        f"发现新版本 {remote_display}（{remote_version}），"
                        f"当前版本 {DISPLAY_VERSION}（{VERSION}）{patch_hint}"
                    )
                )
            else:
                self.status_label.config(
                    text=(
                        f"发现新版本安装包（{remote_display}），"
                        f"当前版本 {DISPLAY_VERSION}（{VERSION}）{patch_hint}"
                    )
                )
            self.action_button.config(state=tk.NORMAL)
        else:
            self.status_label.config(text=f"当前已是最新版本 {DISPLAY_VERSION}（{VERSION}）")

    def on_update_clicked(self):
        if not self.manifest:
            return

        if os.name != "nt":
            # macOS: open browser to GitHub Releases
            import webbrowser
            url = self.manifest.get("download_url") or self.manifest.get("github_html_url", "")
            if url:
                webbrowser.open(url)
                messagebox.showinfo(
                    "打开下载页面",
                    f"请在浏览器中下载新版本。\n\n如果浏览器未自动打开，请访问：\n{url}",
                    parent=self.window,
                )
            else:
                messagebox.showwarning("无法更新", "未找到下载地址。", parent=self.window)
            return

        self.update_package = resolve_update_package(self.manifest, VERSION)
        download_url = self.update_package.get("download_url", "").strip()
        if not download_url:
            messagebox.showerror("更新失败", "更新清单未提供下载地址。", parent=self.window)
            return

        filename = (
            self.update_package.get("filename")
            or os.path.basename(download_url)
            or "LuxeLead_update.zip"
        )
        self.download_path = prepare_download_path(filename)

        mode_label = "增量更新包" if self.update_package.get("_update_mode") == "patch" else "完整更新包"
        self.action_button.config(state=tk.DISABLED)
        self.progress.config(mode="determinate", maximum=100, value=0)
        self.status_label.config(text=f"正在下载{mode_label}，请稍候...")

        def worker():
            try:
                def on_progress(downloaded, total):
                    if total:
                        percent = min(100, int(downloaded * 100 / total))
                        self.parent.after(
                            0,
                            lambda p=percent: self.progress.config(value=p),
                        )

                download_file(
                    download_url,
                    self.download_path,
                    progress_callback=on_progress,
                    extra_headers=get_download_headers(self.manifest, self.config),
                )
                expected_hash = self.update_package.get("sha256", "")
                if not verify_sha256(self.download_path, expected_hash):
                    raise ValueError("下载文件校验失败，请稍后重试或联系管理员")

                self.parent.after(0, self._finish_download)
            except Exception as exc:
                self.parent.after(0, lambda: self._download_failed(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _download_failed(self, message):
        self.status_label.config(text=f"下载失败：{message}")
        self.action_button.config(state=tk.NORMAL)

    def _finish_download(self):
        self.progress.config(value=100)
        self.status_label.config(text="下载完成，请确认是否安装更新。")
        if not messagebox.askyesno(
            "确认更新",
            "更新包已下载完成。\n\n点击“是”将关闭当前程序并安装新版本。\n安装过程中会显示更新进度。",
            parent=self.window,
        ):
            self.status_label.config(text="更新包已保存，可稍后手动安装。")
            self.action_button.config(state=tk.NORMAL)
            return

        try:
            apply_windows_update(
                self.download_path,
                get_executable_path(),
                manifest=self.update_package,
            )
        except Exception as exc:
            messagebox.showerror("更新失败", str(exc), parent=self.window)
            self.action_button.config(state=tk.NORMAL)
            return

        self.window.destroy()
        self.parent.destroy()
