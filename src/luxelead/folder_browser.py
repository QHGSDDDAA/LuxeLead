"""可同时浏览文件夹与文件的目录选择对话框。"""
import os
import time
import tkinter as tk
from tkinter import messagebox, ttk


def _format_mtime(path):
    try:
        return time.strftime("%Y/%m/%d %H:%M", time.localtime(os.path.getmtime(path)))
    except OSError:
        return ""


def browse_folder(parent, title="选择文件夹", initial_dir=None):
    initial_dir = initial_dir or os.path.expanduser("~")
    if not os.path.isdir(initial_dir):
        initial_dir = os.path.expanduser("~")

    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(True, True)
    dialog.geometry("760x480")
    dialog.minsize(600, 400)

    current_path = {"value": initial_dir}
    selected_path = {"value": None}
    entry_map = {}

    header = ttk.Frame(dialog, padding=(10, 10, 10, 0))
    header.pack(fill=tk.X)

    ttk.Label(header, text="当前路径：").pack(side=tk.LEFT)
    path_var = tk.StringVar(value=initial_dir)
    path_entry = ttk.Entry(header, textvariable=path_var)
    path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))

    body = ttk.Frame(dialog, padding=10)
    body.pack(fill=tk.BOTH, expand=True)

    list_frame = ttk.Frame(body)
    list_frame.pack(fill=tk.BOTH, expand=True)

    tree = ttk.Treeview(
        list_frame,
        columns=("name", "mtime", "kind"),
        show="headings",
        selectmode="browse",
    )
    tree.heading("name", text="名称")
    tree.heading("mtime", text="修改日期")
    tree.heading("kind", text="类型")
    tree.column("name", width=360, anchor=tk.W)
    tree.column("mtime", width=150, anchor=tk.W)
    tree.column("kind", width=80, anchor=tk.W)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree.config(yscrollcommand=scrollbar.set)

    hint = ttk.Label(
        body,
        text="双击文件夹进入；浏览至目标位置后点「打开」，确认上方地址栏路径（无需选中文件）",
        foreground="gray",
    )
    hint.pack(anchor=tk.W, pady=(6, 0))

    footer = ttk.Frame(dialog, padding=(10, 0, 10, 10))
    footer.pack(fill=tk.X)

    def refresh_list():
        path = current_path["value"]
        path_var.set(path)
        tree.delete(*tree.get_children())
        entry_map.clear()

        entries = []
        parent_dir = os.path.dirname(path.rstrip("\\/"))
        if parent_dir and os.path.normcase(parent_dir) != os.path.normcase(path):
            entries.append(("dir", "..", parent_dir))

        try:
            names = os.listdir(path)
        except OSError as exc:
            messagebox.showerror("错误", f"无法读取目录：\n{exc}", parent=dialog)
            return

        dirs = sorted(name for name in names if os.path.isdir(os.path.join(path, name)))
        files = sorted(name for name in names if os.path.isfile(os.path.join(path, name)))

        for name in dirs:
            entries.append(("dir", name, os.path.join(path, name)))
        for name in files:
            entries.append(("file", name, os.path.join(path, name)))

        for kind, name, full_path in entries:
            if name == "..":
                display_name = ".."
                mtime = ""
                kind_text = "上级"
            elif kind == "dir":
                display_name = name
                mtime = _format_mtime(full_path)
                kind_text = "文件夹"
            else:
                display_name = name
                mtime = _format_mtime(full_path)
                kind_text = "文件"

            iid = tree.insert("", tk.END, values=(display_name, mtime, kind_text))
            entry_map[iid] = (kind, name, full_path)

    def enter_directory(target_path):
        if os.path.isdir(target_path):
            current_path["value"] = target_path
            refresh_list()

    def on_go_path(event=None):
        target = path_var.get().strip()
        if os.path.isdir(target):
            enter_directory(target)
        else:
            messagebox.showwarning("提示", "路径不存在或不是文件夹", parent=dialog)

    def on_double_click(event=None):
        selection = tree.selection()
        if not selection:
            return
        kind, _name, full_path = entry_map[selection[0]]
        if kind == "dir":
            enter_directory(full_path)

    def on_select_folder():
        selected_path["value"] = current_path["value"]
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    def go_parent():
        path = current_path["value"]
        parent_dir = os.path.dirname(path.rstrip("\\/"))
        if parent_dir and os.path.normcase(parent_dir) != os.path.normcase(path):
            enter_directory(parent_dir)

    path_entry.bind("<Return>", on_go_path)
    tree.bind("<Double-Button-1>", on_double_click)

    ttk.Button(footer, text="上级目录", command=go_parent).pack(side=tk.LEFT)
    ttk.Button(footer, text="打开", command=on_select_folder).pack(side=tk.RIGHT, padx=(6, 0))
    ttk.Button(footer, text="取消", command=on_cancel).pack(side=tk.RIGHT)

    dialog.bind("<Escape>", lambda e: on_cancel())
    dialog.bind("<Return>", lambda e: on_select_folder())
    refresh_list()

    dialog.update_idletasks()
    x = parent.winfo_rootx() + max(0, (parent.winfo_width() - dialog.winfo_width()) // 2)
    y = parent.winfo_rooty() + max(0, (parent.winfo_height() - dialog.winfo_height()) // 2)
    dialog.geometry(f"+{x}+{y}")

    parent.wait_window(dialog)
    return selected_path["value"]
