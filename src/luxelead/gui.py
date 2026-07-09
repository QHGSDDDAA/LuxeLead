import os
import sys
import json
import threading
import time
import platform
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, ttk, messagebox

from .datetime_picker import DateTimePickerPopup, DISPLAY_FMT, format_datetime, parse_datetime_text
from .generator import (
    count_images_recursive,
    generate_ppt,
    group_images_by_prefix,
    list_folders_with_images,
    plan_folder_image_pages,
)
from .layout import check_yolov8_available
from .version import DISPLAY_VERSION
from .version_dialog import CheckUpdateDialog, VersionInfoDialog

DEFAULT_PREFIX_SEPARATOR = "_"

def get_config_path():
    return os.path.join(os.path.expanduser("~"), ".luxelead", "config.json")

def load_config():
    config_path = get_config_path()
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(config):
    config_path = get_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except:
        pass

def get_desktop_path():
    return os.path.join(os.path.expanduser("~"), "Desktop")

class LuxeLeadApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"LuxeLead PPT Generator {DISPLAY_VERSION}")
        self.root.geometry("820x780")
        self.root.resizable(True, True)

        config = load_config()
        self.config = config
        desktop = get_desktop_path()
        self.output_dir = config.get("output_dir", desktop)
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)

        self.main_folder = ""
        self.is_running = False
        self.stop_event = threading.Event()
        self.mode_var = tk.StringVar(value=config.get("mode", "folder"))
        self.prefix_separator_var = tk.StringVar(value=DEFAULT_PREFIX_SEPARATOR)
        self.prefix_cutoff_time_var = tk.StringVar(
            value=config.get("prefix_cutoff_time", "")
        )
        self.folder_images_per_page_var = tk.StringVar(value="")
        self.folder_sort_order_var = tk.StringVar(
            value=config.get("folder_sort_order", "asc")
        )
        self.crop_var = tk.BooleanVar(value=False)
        self.crop_output_dir = ""
        self._preview_job = None
        self._folder_hint_job = None

        self.create_menu_bar()
        self.create_widgets()
        self._bind_live_preview()
        self.update_mode_options_state()

    def create_menu_bar(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="查看版本", command=self.show_version_info)
        help_menu.add_command(label="检查更新", command=self.check_for_updates)

    def show_version_info(self):
        VersionInfoDialog(self.root, self.config)

    def check_for_updates(self):
        CheckUpdateDialog(self.root, self.config)

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(1, weight=1)

        row = 0

        title_label = ttk.Label(main_frame, text="LuxeLead PPT Generator", 
                               font=("Microsoft YaHei", 14, "bold"))
        title_label.grid(row=row, column=0, columnspan=3, pady=(0, 10))

        row += 1

        ttk.Label(main_frame, text="来源文件夹：").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.folder_path_entry = ttk.Entry(main_frame, width=55)
        self.folder_path_entry.grid(row=row, column=1, sticky=tk.W+tk.E, pady=5)
        self.folder_path_entry.bind("<FocusOut>", self.on_main_folder_path_changed)
        ttk.Button(main_frame, text="浏览...", command=self.browse_main_folder).grid(row=row, column=2, padx=5, pady=5)

        row += 1

        ttk.Label(main_frame, text="PPT保存路径：").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.output_path_entry = ttk.Entry(main_frame, width=55)
        self.output_path_entry.insert(0, self.output_dir)
        self.output_path_entry.grid(row=row, column=1, sticky=tk.W+tk.E, pady=5)
        self.output_path_entry.bind("<FocusOut>", self.on_output_path_changed)
        ttk.Button(main_frame, text="浏览...", command=self.browse_output_folder).grid(row=row, column=2, padx=5, pady=5)

        row += 1

        ttk.Label(main_frame, text="生成模式：").grid(row=row, column=0, sticky=tk.W, pady=5)
        mode_frame = ttk.Frame(main_frame)
        mode_frame.grid(row=row, column=1, columnspan=2, sticky=tk.W+tk.E, pady=5)
        
        ttk.Radiobutton(mode_frame, text="按文件夹", variable=self.mode_var,
                        value="folder", command=self.on_mode_changed).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="按文件前缀", variable=self.mode_var,
                        value="prefix", command=self.on_mode_changed).pack(side=tk.LEFT, padx=10)

        row += 1

        self.prefix_options_label = ttk.Label(main_frame, text="前缀规则：")
        self.prefix_options_label.grid(row=row, column=0, sticky=tk.W, pady=5)

        self.prefix_options_frame = ttk.Frame(main_frame)
        self.prefix_options_frame.grid(row=row, column=1, columnspan=2, sticky=tk.W+tk.E, pady=5)

        prefix_sep_row = ttk.Frame(self.prefix_options_frame)
        prefix_sep_row.pack(fill=tk.X, anchor=tk.W)

        ttk.Label(prefix_sep_row, text="分隔符").pack(side=tk.LEFT)
        self.prefix_separator_entry = ttk.Entry(
            prefix_sep_row,
            textvariable=self.prefix_separator_var,
            width=8,
        )
        self.prefix_separator_entry.pack(side=tk.LEFT, padx=(5, 10))
        self.prefix_separator_entry.bind("<FocusOut>", self.on_prefix_separator_changed)
        self.prefix_separator_entry.bind("<Return>", self.on_prefix_separator_changed)
        self.prefix_separator_entry.bind("<KeyRelease>", self.on_prefix_separator_live_changed)

        self.prefix_rule_hint = ttk.Label(
            prefix_sep_row,
            text="取文件名（不含扩展名）左起分隔符前的部分作为前缀，分隔符支持中文等任意字符",
            foreground="gray",
        )
        self.prefix_rule_hint.pack(side=tk.LEFT)

        prefix_time_row = ttk.Frame(self.prefix_options_frame)
        prefix_time_row.pack(fill=tk.X, anchor=tk.W, pady=(6, 0))

        ttk.Label(prefix_time_row, text="数据截至时间").pack(side=tk.LEFT)
        self.prefix_cutoff_picker_frame = ttk.Frame(prefix_time_row)
        self.prefix_cutoff_picker_frame.pack(side=tk.LEFT, padx=(5, 5))

        self.prefix_cutoff_entry = ttk.Entry(
            self.prefix_cutoff_picker_frame,
            textvariable=self.prefix_cutoff_time_var,
            width=22,
            state="readonly",
        )
        self.prefix_cutoff_entry.pack(side=tk.LEFT)
        ttk.Button(
            self.prefix_cutoff_picker_frame,
            text="📅",
            width=3,
            command=self.open_prefix_cutoff_picker,
        ).pack(side=tk.LEFT)
        self.prefix_cutoff_entry.bind("<Button-1>", lambda e: self.open_prefix_cutoff_picker())
        ttk.Button(
            prefix_time_row,
            text="清空",
            command=self.clear_prefix_cutoff_datetime,
        ).pack(side=tk.LEFT, padx=(0, 10))
        self.prefix_cutoff_hint = ttk.Label(
            prefix_time_row,
            text="仅使用创建时间≥该时间的图片；留空表示不过滤",
            foreground="gray",
        )
        self.prefix_cutoff_hint.pack(side=tk.LEFT)
        self._prefix_cutoff_popup = None

        row += 1

        self.folder_options_label = ttk.Label(main_frame, text="文件夹规则：")
        self.folder_options_label.grid(row=row, column=0, sticky=tk.W, pady=5)

        self.folder_options_frame = ttk.Frame(main_frame)
        self.folder_options_frame.grid(row=row, column=1, columnspan=2, sticky=tk.W+tk.E, pady=5)

        folder_top_row = ttk.Frame(self.folder_options_frame)
        folder_top_row.pack(fill=tk.X, anchor=tk.W)

        ttk.Label(folder_top_row, text="每页图片数 N").pack(side=tk.LEFT)
        self.folder_images_per_page_entry = ttk.Entry(
            folder_top_row,
            textvariable=self.folder_images_per_page_var,
            width=8,
        )
        self.folder_images_per_page_entry.pack(side=tk.LEFT, padx=(5, 10))
        self.folder_images_per_page_entry.bind("<FocusOut>", self.on_folder_options_changed)
        self.folder_images_per_page_entry.bind("<Return>", self.on_folder_options_changed)
        self.folder_images_per_page_entry.bind("<KeyRelease>", self.on_folder_options_live_changed)

        self.folder_per_page_hint = ttk.Label(
            folder_top_row,
            text="默认等于当前文件夹图片总数，切换文件夹后自动更新",
            foreground="gray",
        )
        self.folder_per_page_hint.pack(side=tk.LEFT)

        folder_sort_row = ttk.Frame(self.folder_options_frame)
        folder_sort_row.pack(fill=tk.X, anchor=tk.W, pady=(6, 0))

        ttk.Label(folder_sort_row, text="排序").pack(side=tk.LEFT)
        ttk.Radiobutton(
            folder_sort_row,
            text="图片生成时间正序",
            variable=self.folder_sort_order_var,
            value="asc",
            command=self.on_folder_options_changed,
        ).pack(side=tk.LEFT, padx=(10, 10))
        ttk.Radiobutton(
            folder_sort_row,
            text="图片生成时间倒序",
            variable=self.folder_sort_order_var,
            value="desc",
            command=self.on_folder_options_changed,
        ).pack(side=tk.LEFT)

        row += 1

        ttk.Label(main_frame, text="是否裁剪：").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.crop_checkbutton = ttk.Checkbutton(main_frame, text="使用YOLOv8人物检测进行裁剪", 
                                                variable=self.crop_var, command=self.on_crop_toggle)
        self.crop_checkbutton.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=5)

        row += 1

        ttk.Label(main_frame, text="裁剪后存储地址：").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.crop_output_entry = ttk.Entry(main_frame, width=55, state=tk.DISABLED)
        self.crop_output_entry.grid(row=row, column=1, sticky=tk.W+tk.E, pady=5)
        self.crop_output_button = ttk.Button(main_frame, text="浏览...", command=self.browse_crop_output_folder, state=tk.DISABLED)
        self.crop_output_button.grid(row=row, column=2, padx=5, pady=5)

        row += 1

        ttk.Label(main_frame, text="内容预览：").grid(row=row, column=0, sticky=tk.W, pady=5)

        row += 1

        content_frame = ttk.Frame(main_frame)
        content_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)

        self.content_listbox = tk.Listbox(content_frame, height=8)
        self.content_listbox.grid(row=0, column=0, sticky=tk.W+tk.E+tk.N+tk.S)
        
        content_scrollbar = ttk.Scrollbar(content_frame, orient=tk.VERTICAL, command=self.content_listbox.yview)
        content_scrollbar.grid(row=0, column=1, sticky=tk.N+tk.S)
        self.content_listbox.config(yscrollcommand=content_scrollbar.set)

        row += 1

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=10)
        
        self.execute_button = ttk.Button(button_frame, text="执行", command=self.start_execution)
        self.execute_button.pack(side=tk.LEFT, padx=10)
        
        self.stop_button = ttk.Button(button_frame, text="停止", command=self.stop_execution, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=10)

        row += 1

        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E)
        status_frame.columnconfigure(0, weight=1)

        ttk.Label(status_frame, text="执行状态：").grid(row=0, column=0, sticky=tk.W)
        self.status_label = ttk.Label(status_frame, text="未开始", foreground="blue")
        self.status_label.grid(row=0, column=1, sticky=tk.W)

        row += 1

        self.progress_bar = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, length=400, mode='indeterminate')
        self.progress_bar.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)

        row += 1

        ttk.Label(main_frame, text="日志：").grid(row=row, column=0, sticky=tk.W, pady=5)

        row += 1

        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E+tk.N+tk.S)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=tk.W+tk.E+tk.N+tk.S)
        
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scrollbar.grid(row=0, column=1, sticky=tk.N+tk.S)
        self.log_text.config(yscrollcommand=log_scrollbar.set)

        main_frame.rowconfigure(row, weight=1)

    def browse_main_folder(self):
        initial = self.folder_path_entry.get().strip() or self.main_folder or os.path.expanduser("~")
        if not os.path.isdir(initial):
            initial = os.path.expanduser("~")

        folder = filedialog.askdirectory(
            parent=self.root,
            title="选择图片文件夹",
            initialdir=initial,
        )
        if not folder:
            return

        self.main_folder = folder
        self.folder_path_entry.delete(0, tk.END)
        self.folder_path_entry.insert(0, folder)
        self.apply_folder_defaults(folder)
        self.update_content_preview()

    def on_main_folder_path_changed(self, event=None):
        folder = self.folder_path_entry.get().strip()
        if not folder:
            return
        if not os.path.isdir(folder):
            return
        if folder != self.main_folder:
            self.main_folder = folder
            self.apply_folder_defaults(folder)
            self.update_content_preview()

    def count_main_folder_images(self, folder=None):
        folder = folder or self.main_folder
        if not folder or not os.path.isdir(folder):
            return 0
        return count_images_recursive(folder)

    def apply_folder_defaults(self, folder=None):
        folder = folder or self.main_folder
        if not folder or not os.path.isdir(folder):
            return
        total = self.count_main_folder_images(folder)
        self.folder_images_per_page_var.set(str(total) if total > 0 else "")
        self.update_folder_per_page_hint()

    def browse_output_folder(self):
        initial = self.output_path_entry.get().strip() or self.output_dir or os.path.expanduser("~")
        if not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        folder = filedialog.askdirectory(
            parent=self.root,
            title="选择PPT保存路径",
            initialdir=initial,
        )
        if folder:
            self.output_dir = folder
            self.output_path_entry.delete(0, tk.END)
            self.output_path_entry.insert(0, folder)
            self.save_app_config()

    def on_crop_toggle(self):
        if self.crop_var.get():
            try:
                self.root.config(cursor="wait")
                self.root.update_idletasks()
                available, error_msg = check_yolov8_available()
            except Exception as e:
                available, error_msg = False, str(e)
            finally:
                self.root.config(cursor="")

            if not available:
                messagebox.showerror("裁剪功能不可用", f"无法启用 YOLOv8 裁剪：\n{error_msg}")
                self.crop_var.set(False)
                return

            self.crop_output_entry.config(state=tk.NORMAL)
            self.crop_output_button.config(state=tk.NORMAL)
            if not self.crop_output_entry.get().strip():
                self.crop_output_dir = self.crop_output_dir or os.path.join(
                    self.output_dir, "cropped_images"
                )
                self.crop_output_entry.delete(0, tk.END)
                self.crop_output_entry.insert(0, self.crop_output_dir)
        else:
            self.crop_output_entry.config(state=tk.DISABLED)
            self.crop_output_button.config(state=tk.DISABLED)



    def browse_crop_output_folder(self):
        initial = self.crop_output_entry.get().strip() or self.crop_output_dir or self.output_dir or os.path.expanduser("~")
        if not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        folder = filedialog.askdirectory(
            parent=self.root,
            title="选择裁剪图片保存路径",
            initialdir=initial,
        )
        if folder:
            self.crop_output_dir = folder
            self.crop_output_entry.delete(0, tk.END)
            self.crop_output_entry.insert(0, folder)

    def on_output_path_changed(self, event=None):
        path = self.output_path_entry.get().strip()
        if path and os.path.exists(path):
            self.output_dir = path
            self.save_app_config()

    def on_mode_changed(self):
        self.update_mode_options_state()
        self.update_content_preview()
        self.save_app_config()

    def _bind_live_preview(self):
        self.prefix_separator_var.trace_add("write", self._on_prefix_separator_var_changed)
        self.prefix_cutoff_time_var.trace_add("write", self._on_prefix_cutoff_time_var_changed)
        self.folder_images_per_page_var.trace_add("write", self._on_folder_images_per_page_var_changed)

    def _on_prefix_cutoff_time_var_changed(self, *args):
        self.schedule_live_preview_update()

    def _on_prefix_separator_var_changed(self, *args):
        self.schedule_live_preview_update()

    def _on_folder_images_per_page_var_changed(self, *args):
        self.schedule_live_preview_update()
        self.schedule_folder_hint_update()

    def schedule_live_preview_update(self, save_config=False):
        if self._preview_job is not None:
            self.root.after_cancel(self._preview_job)
        self._preview_job = self.root.after(
            120,
            lambda: self._apply_live_preview_update(save_config),
        )

    def schedule_folder_hint_update(self):
        if hasattr(self, "_folder_hint_job") and self._folder_hint_job is not None:
            self.root.after_cancel(self._folder_hint_job)
        self._folder_hint_job = self.root.after(120, self.update_folder_per_page_hint)

    def _apply_live_preview_update(self, save_config):
        self._preview_job = None
        self.update_content_preview(show_input_errors=False)
        if save_config:
            self.save_app_config()

    def on_prefix_separator_live_changed(self, event=None):
        self.schedule_live_preview_update()

    def on_prefix_separator_changed(self, event=None):
        self.update_content_preview()
        self.save_app_config()

    def get_prefix_cutoff_time(self):
        return self.prefix_cutoff_time_var.get().strip()

    def get_prefix_cutoff_timestamp(self, strict=True):
        value = self.get_prefix_cutoff_time()
        if not value:
            return None
        try:
            return parse_datetime_text(value).timestamp()
        except ValueError:
            if strict:
                raise ValueError(f"数据截至时间格式应为 {DISPLAY_FMT}")
            return None

    def clear_prefix_cutoff_datetime(self):
        self.prefix_cutoff_time_var.set("")
        if self._prefix_cutoff_popup:
            self._prefix_cutoff_popup.close()
        self.save_app_config()
        self.update_content_preview()

    def open_prefix_cutoff_picker(self):
        current = self.get_prefix_cutoff_time()
        initial = datetime.now()
        if current:
            try:
                initial = parse_datetime_text(current)
            except ValueError:
                messagebox.showerror("格式错误", f"当前时间格式无效，请使用 {DISPLAY_FMT}")
                return

        if self._prefix_cutoff_popup:
            self._prefix_cutoff_popup.close()

        def on_commit(selected_dt):
            self.prefix_cutoff_time_var.set(format_datetime(selected_dt))
            self.save_app_config()
            self.update_content_preview()

        def on_clear():
            self.prefix_cutoff_time_var.set("")
            self.save_app_config()
            self.update_content_preview()

        self._prefix_cutoff_popup = DateTimePickerPopup(
            self.root,
            self.prefix_cutoff_picker_frame,
            initial,
            on_commit,
            on_clear=on_clear,
        )
        self._prefix_cutoff_popup.show()

    def on_folder_options_live_changed(self, event=None):
        self.schedule_live_preview_update()

    def on_folder_options_changed(self, event=None):
        self.update_content_preview()
        self.save_app_config()

    def save_app_config(self):
        config = load_config()
        config.update({
            "output_dir": self.output_dir,
            "mode": self.mode_var.get(),
            "prefix_separator": self.get_prefix_separator() or DEFAULT_PREFIX_SEPARATOR,
            "prefix_cutoff_time": self.get_prefix_cutoff_time(),
            "folder_sort_order": self.folder_sort_order_var.get(),
        })
        save_config(config)

    def get_prefix_separator(self):
        separator = self.prefix_separator_var.get()
        return separator if separator else DEFAULT_PREFIX_SEPARATOR

    def parse_images_per_page(self, strict=True):
        value = self.folder_images_per_page_var.get().strip()
        if not value:
            total = self.count_main_folder_images()
            return total if total > 0 else 0
        try:
            parsed = int(value)
        except ValueError:
            if strict:
                raise ValueError("每页图片数 N 必须是正整数")
            return None
        if parsed <= 0:
            if strict:
                raise ValueError("每页图片数 N 必须是正整数")
            return None
        return parsed

    def get_images_per_page(self):
        return self.parse_images_per_page(strict=True)

    def get_sort_order(self):
        return self.folder_sort_order_var.get()

    def update_mode_options_state(self):
        is_prefix = self.mode_var.get() == "prefix"
        if is_prefix:
            self.prefix_options_label.grid()
            self.prefix_options_frame.grid()
            self.folder_options_label.grid_remove()
            self.folder_options_frame.grid_remove()
        else:
            self.prefix_options_label.grid_remove()
            self.prefix_options_frame.grid_remove()
            self.folder_options_label.grid()
            self.folder_options_frame.grid()
            self.update_folder_per_page_hint()

    def update_folder_per_page_hint(self):
        if not self.main_folder or not os.path.isdir(self.main_folder):
            self.folder_per_page_hint.config(text="默认等于当前文件夹图片总数，切换文件夹后自动更新")
            return

        total_images = self.count_main_folder_images()
        if total_images:
            self.folder_per_page_hint.config(
                text=f"默认 N={total_images}（递归统计当前文件夹及子文件夹图片总数）"
            )
        else:
            self.folder_per_page_hint.config(text="当前文件夹及子文件夹没有图片")

    def sync_main_folder(self):
        folder = self.folder_path_entry.get().strip()
        if folder:
            self.main_folder = folder
        return self.main_folder

    def update_content_preview(self, show_input_errors=True):
        self.content_listbox.delete(0, tk.END)
        self.sync_main_folder()

        if not self.main_folder:
            return

        try:
            mode = self.mode_var.get()
            folder_display_name = os.path.basename(self.main_folder)

            if mode == "prefix":
                prefix_separator = self.get_prefix_separator()
                cutoff_timestamp = self.get_prefix_cutoff_timestamp(strict=False)
                cutoff_display = self.get_prefix_cutoff_time() or "未设置"
                all_groups = []
                def collect_groups(folder):
                    rel_path = os.path.relpath(folder, self.main_folder) if folder != self.main_folder else ""
                    prefix_groups = group_images_by_prefix(
                        folder, prefix_separator, cutoff_timestamp
                    )
                    for prefix, images in prefix_groups.items():
                        if images:
                            all_groups.append((rel_path, prefix, folder, images))
                    for item in os.listdir(folder):
                        item_path = os.path.join(folder, item)
                        if os.path.isdir(item_path):
                            collect_groups(item_path)
                collect_groups(self.main_folder)
                all_groups.sort(key=lambda x: (x[0], x[1]))
                page_num = 1
                separator_display = prefix_separator if prefix_separator else "（无）"
                self.content_listbox.insert(
                    tk.END,
                    f"数据截至时间: {cutoff_display}（仅包含创建时间≥该时间的图片）",
                )
                for rel_path, prefix, folder, images in all_groups:
                    path_display = f"[{rel_path}]" if rel_path else ""
                    self.content_listbox.insert(
                        tk.END,
                        f"【第{page_num}页】{path_display}前缀「{prefix}」- {len(images)}张图片（分隔符: {separator_display}）",
                    )
                    page_num += 1
                if not all_groups:
                    self.content_listbox.insert(tk.END, "该文件夹下没有图片")
            else:
                images_per_page = self.parse_images_per_page(strict=False)
                if images_per_page is None:
                    self.content_listbox.insert(
                        tk.END,
                        "每页图片数 N 必须是正整数，请输入有效数字后预览将自动更新",
                    )
                    return
                sort_order = self.get_sort_order()
                sort_label = "时间正序" if sort_order == "asc" else "时间倒序"
                page_num = 1

                for ctime, path, images, rel_path, name in list_folders_with_images(
                    self.main_folder
                ):
                    folder_pages = plan_folder_image_pages(
                        path,
                        images,
                        images_per_page,
                        sort_order,
                    )
                    effective_n = images_per_page if images_per_page > 0 else len(images)
                    ctime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ctime))
                    if rel_path:
                        display_name = rel_path
                    else:
                        display_name = folder_display_name
                    for chunk in folder_pages:
                        self.content_listbox.insert(
                            tk.END,
                            f"【第{page_num}页】{display_name} - {len(chunk)}张图片（N={effective_n}，{sort_label}，文件夹创建: {ctime_str}）",
                        )
                        page_num += 1

                if page_num == 1:
                    self.content_listbox.insert(tk.END, "该文件夹下没有图片")

        except ValueError as e:
            if show_input_errors:
                messagebox.showerror("错误", str(e))
            else:
                self.content_listbox.insert(tk.END, str(e))
        except Exception as e:
            if show_input_errors:
                messagebox.showerror("错误", f"读取文件夹失败：{str(e)}")
            else:
                self.content_listbox.insert(tk.END, f"读取文件夹失败：{str(e)}")

    def start_execution(self):
        folder = self.sync_main_folder()
        if not folder:
            messagebox.showwarning("警告", "请先选择来源文件夹")
            return
        if not os.path.isdir(folder):
            messagebox.showerror("错误", f"来源路径不是有效的文件夹：\n{folder}")
            return

        output_path = self.output_path_entry.get().strip()
        if not output_path:
            messagebox.showwarning("警告", "请先选择保存路径")
            return

        if self.mode_var.get() == "folder":
            try:
                self.get_images_per_page()
            except ValueError as e:
                messagebox.showerror("错误", str(e))
                return
        elif self.mode_var.get() == "prefix":
            try:
                self.get_prefix_cutoff_timestamp(strict=True)
            except ValueError as e:
                messagebox.showerror("错误", str(e))
                return

        if not os.path.exists(output_path):
            confirm = messagebox.askyesno("确认", f"保存路径不存在：\n{output_path}\n\n是否创建该目录？")
            if confirm:
                try:
                    os.makedirs(output_path)
                    self.log(f"已创建保存目录: {output_path}")
                except Exception as e:
                    messagebox.showerror("错误", f"创建目录失败：{str(e)}")
                    return
            else:
                return

        self.is_running = True
        self.stop_event.clear()
        self.execute_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_label.config(text="执行中", foreground="green")
        self.progress_bar.start()

        thread = threading.Thread(target=self.execute_generate, args=(output_path,))
        thread.daemon = True
        thread.start()

    def stop_execution(self):
        self.is_running = False
        self.stop_event.set()
        self.status_label.config(text="已停止", foreground="orange")

    def execute_generate(self, output_path):
        output_file = None
        try:
            self.log("开始执行...")
            mode = self.mode_var.get()
            main_folder = self.sync_main_folder()

            crop = self.crop_var.get()
            crop_output_dir = None
            if crop:
                crop_output_dir = self.crop_output_entry.get().strip() or self.crop_output_dir or None

            self.log("参数信息:")
            self.log(f"  - 来源文件夹: {main_folder}")
            self.log(f"  - 保存路径: {output_path}")
            self.log(f"  - 生成模式: {mode}")
            if mode == "prefix":
                self.log(f"  - 前缀分隔符: {self.get_prefix_separator()!r}")
                cutoff_time = self.get_prefix_cutoff_time()
                self.log(
                    f"  - 数据截至时间: {cutoff_time if cutoff_time else '未设置（不过滤）'}"
                )
            else:
                images_per_page = self.get_images_per_page()
                sort_order = self.get_sort_order()
                self.log(f"  - 每页图片数 N: {images_per_page if images_per_page > 0 else '全部'}")
                self.log(f"  - 图片排序: {'时间正序' if sort_order == 'asc' else '时间倒序'}")
            self.log(f"  - 是否裁剪: {crop}")
            self.log(f"  - 裁剪保存路径: {crop_output_dir}")

            if crop:
                self.log("已启用图片裁剪（YOLOv8人物检测）")
                if not crop_output_dir:
                    self.log("警告: 裁剪保存路径为空，将不会保存裁剪后的图片")

            generate_kwargs = {
                "prefix_separator": self.get_prefix_separator(),
                "prefix_cutoff_time": self.get_prefix_cutoff_time() or None,
            }
            if mode == "folder":
                generate_kwargs["images_per_page"] = self.get_images_per_page()
                generate_kwargs["sort_order"] = self.get_sort_order()

            output_file, slide_count = generate_ppt(
                main_folder,
                output_path,
                mode,
                crop,
                crop_output_dir,
                self.log,
                **generate_kwargs,
            )
            self.log(f"成功生成 PPT: {output_file}")
            self.log(f"共生成 {slide_count} 页")
            self.set_status("运行完成", "green")
        except Exception as e:
            self.log(f"生成失败: {str(e)}")
            self.set_status("执行失败", "red")
        else:
            try:
                if platform.system() == "Darwin":
                    os.system(f"open '{output_file}'")
                else:
                    os.startfile(output_file)
            except Exception as e:
                self.log(f"PPT 已生成，但自动打开失败: {str(e)}")
        finally:
            self.finish_execution()

    def set_status(self, text, color):
        self.root.after(0, lambda: self.status_label.config(text=text, foreground=color))

    def finish_execution(self):
        def reset_ui():
            self.is_running = False
            self.progress_bar.stop()
            self.execute_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

        self.root.after(0, reset_ui)

    def log(self, message):
        self.root.after(0, lambda: self._append_log(message))

    def _append_log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

def main():
    update_dir = os.environ.get("LUXELEAD_UPDATE_PROGRESS", "").strip()
    if not update_dir and len(sys.argv) >= 3 and sys.argv[1] == "--luxelead-update-progress":
        update_dir = sys.argv[2].strip()
    if update_dir:
        from .update_progress import run_update_progress_monitor

        run_update_progress_monitor(update_dir)
        return

    root = tk.Tk()
    app = LuxeLeadApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()