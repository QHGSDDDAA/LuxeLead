"""日历 + 时分秒列选择器（参考 Element UI 日期时间控件）。"""
import calendar
import tkinter as tk
from datetime import datetime
from tkinter import ttk

DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
DISPLAY_FMT = "%Y/%m/%d %H:%M:%S"
WEEKDAYS_CN = ("一", "二", "三", "四", "五", "六", "日")
CALENDAR_ROWS = 6

SELECT_BG = "#409EFF"
SELECT_FG = "#FFFFFF"
NORMAL_FG = "#606266"
TODAY_BORDER = "#409EFF"


def parse_datetime_text(value):
    text = (value or "").strip()
    if not text:
        return None
    for fmt in (DATETIME_FMT, DISPLAY_FMT):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"时间格式应为 {DISPLAY_FMT}")


def format_datetime(dt):
    return dt.strftime(DISPLAY_FMT)


class DateTimePickerPopup:
    """在锚点控件下方弹出的日期时间选择面板。"""

    def __init__(self, parent, anchor_widget, initial_dt, on_commit, on_clear=None):
        self.parent = parent
        self.anchor_widget = anchor_widget
        self.selected = initial_dt or datetime.now()
        self.view_year = self.selected.year
        self.view_month = self.selected.month
        self.on_commit = on_commit
        self.on_clear = on_clear
        self.popup = None
        self.days_frame = None
        self._updating_lists = False
        self._popup_width = 360
        self._popup_height = 268

    def show(self):
        if self.popup and self.popup.winfo_exists():
            self.close()

        self.popup = tk.Toplevel(self.parent)
        self.popup.withdraw()
        self.popup.title("选择时间")
        self.popup.transient(self.parent)
        self.popup.resizable(False, False)
        self.popup.configure(bg="#FFFFFF")
        self.popup.protocol("WM_DELETE_WINDOW", self.close)

        outer = tk.Frame(self.popup, bg="#FFFFFF", highlightbackground="#E4E7ED", highlightthickness=1)
        outer.pack(fill=tk.BOTH, expand=True)

        content = tk.Frame(outer, bg="#FFFFFF", padx=8, pady=8)
        content.pack(fill=tk.BOTH, expand=True)

        self.preview_var = tk.StringVar(value=format_datetime(self.selected))
        preview_label = tk.Label(
            content,
            textvariable=self.preview_var,
            bg="#FFFFFF",
            fg="#303133",
            font=("Consolas", 10),
            anchor=tk.W,
        )
        preview_label.pack(fill=tk.X, pady=(0, 6))

        body = tk.Frame(content, bg="#FFFFFF")
        body.pack(fill=tk.BOTH, expand=True)

        calendar_frame = tk.Frame(body, bg="#FFFFFF", width=210, height=190)
        calendar_frame.pack(side=tk.LEFT, padx=(0, 8))
        calendar_frame.pack_propagate(False)

        self._build_calendar_header(calendar_frame)
        self._build_weekday_header(calendar_frame)
        self.days_frame = tk.Frame(calendar_frame, bg="#FFFFFF", height=150)
        self.days_frame.pack(fill=tk.X)
        self.days_frame.pack_propagate(False)

        time_frame = tk.Frame(body, bg="#FFFFFF", highlightbackground="#E4E7ED", highlightthickness=1, width=120, height=168)
        time_frame.pack(side=tk.LEFT, fill=tk.Y)
        time_frame.pack_propagate(False)

        time_inner = tk.Frame(time_frame, bg="#FFFFFF")
        time_inner.pack(padx=4, pady=4)

        self.hour_list = self._create_time_list(time_inner, 24)
        self.minute_list = self._create_time_list(time_inner, 60)
        self.second_list = self._create_time_list(time_inner, 60)

        footer = tk.Frame(content, bg="#FFFFFF")
        footer.pack(fill=tk.X, pady=(8, 0))

        clear_btn = tk.Label(
            footer,
            text="清除",
            fg="#409EFF",
            bg="#FFFFFF",
            cursor="hand2",
            font=("Microsoft YaHei", 9),
        )
        clear_btn.pack(side=tk.LEFT)
        clear_btn.bind("<Button-1>", lambda e: self._handle_clear())

        right_footer = tk.Frame(footer, bg="#FFFFFF")
        right_footer.pack(side=tk.RIGHT)

        reset_time_btn = tk.Label(
            right_footer,
            text="时分秒归零",
            fg="#409EFF",
            bg="#FFFFFF",
            cursor="hand2",
            font=("Microsoft YaHei", 9),
        )
        reset_time_btn.pack(side=tk.LEFT, padx=(0, 12))
        reset_time_btn.bind("<Button-1>", lambda e: self._handle_reset_time())

        today_btn = tk.Label(
            right_footer,
            text="今天",
            fg="#409EFF",
            bg="#FFFFFF",
            cursor="hand2",
            font=("Microsoft YaHei", 9),
        )
        today_btn.pack(side=tk.LEFT, padx=(0, 12))
        today_btn.bind("<Button-1>", lambda e: self._handle_today())

        ok_btn = ttk.Button(right_footer, text="确定", width=8, command=self._handle_confirm)
        ok_btn.pack(side=tk.LEFT)

        self._render_calendar()
        self._sync_time_lists()
        self._refresh_preview()

        self.popup.bind("<Escape>", lambda e: self.close())

        self.popup.update_idletasks()
        self._lock_popup_size()
        self._position_below_anchor()
        self.popup.deiconify()
        self.popup.lift()

    def close(self):
        if self.popup and self.popup.winfo_exists():
            self.popup.destroy()

    def _lock_popup_size(self):
        self.popup.geometry(f"{self._popup_width}x{self._popup_height}")
        self.popup.minsize(self._popup_width, self._popup_height)
        self.popup.maxsize(self._popup_width, self._popup_height)

    def _position_below_anchor(self):
        ax = self.anchor_widget.winfo_rootx()
        ay = self.anchor_widget.winfo_rooty() + self.anchor_widget.winfo_height() + 2
        self.popup.geometry(f"{self._popup_width}x{self._popup_height}+{ax}+{ay}")

    def _build_calendar_header(self, parent):
        header = tk.Frame(parent, bg="#FFFFFF")
        header.pack(fill=tk.X, pady=(0, 4))

        self.month_label = tk.Label(
            header,
            text="",
            bg="#FFFFFF",
            fg="#303133",
            font=("Microsoft YaHei", 10, "bold"),
        )
        self.month_label.pack(side=tk.LEFT)

        nav = tk.Frame(header, bg="#FFFFFF")
        nav.pack(side=tk.RIGHT)

        prev_btn = tk.Label(nav, text="▲", bg="#FFFFFF", fg="#606266", cursor="hand2", width=2)
        prev_btn.pack(side=tk.LEFT)
        prev_btn.bind("<Button-1>", lambda e: self._change_month(-1))

        next_btn = tk.Label(nav, text="▼", bg="#FFFFFF", fg="#606266", cursor="hand2", width=2)
        next_btn.pack(side=tk.LEFT)
        next_btn.bind("<Button-1>", lambda e: self._change_month(1))

    def _build_weekday_header(self, parent):
        row = tk.Frame(parent, bg="#FFFFFF")
        row.pack(pady=(0, 2))
        for day_name in WEEKDAYS_CN:
            lbl = tk.Label(
                row,
                text=day_name,
                width=3,
                bg="#FFFFFF",
                fg="#909399",
                font=("Microsoft YaHei", 9),
            )
            lbl.pack(side=tk.LEFT, padx=1)

    def _create_time_list(self, parent, count):
        frame = tk.Frame(parent, bg="#FFFFFF")
        frame.pack(side=tk.LEFT, padx=1)

        listbox = tk.Listbox(
            frame,
            width=3,
            height=7,
            exportselection=False,
            activestyle="none",
            selectmode=tk.SINGLE,
            bg="#FFFFFF",
            fg=NORMAL_FG,
            selectbackground=SELECT_BG,
            selectforeground=SELECT_FG,
            highlightthickness=0,
            borderwidth=0,
            font=("Consolas", 10),
        )
        listbox.pack()
        for i in range(count):
            listbox.insert(tk.END, f"{i:02d}")
        listbox.bind("<<ListboxSelect>>", self._on_time_select)
        return listbox

    def _clear_days_grid(self):
        if not self.days_frame:
            return
        for child in self.days_frame.winfo_children():
            child.destroy()

    def _change_month(self, delta):
        month = self.view_month + delta
        year = self.view_year
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        self.view_year = year
        self.view_month = month
        self._render_calendar()

    def _render_calendar(self):
        self.month_label.config(text=f"{self.view_year}年{self.view_month:02d}月")
        self._clear_days_grid()

        cal = calendar.Calendar(firstweekday=0)
        weeks = cal.monthdayscalendar(self.view_year, self.view_month)
        while len(weeks) < CALENDAR_ROWS:
            weeks.append([0] * 7)

        today = datetime.now().date()

        for week in weeks[:CALENDAR_ROWS]:
            row = tk.Frame(self.days_frame, bg="#FFFFFF")
            row.pack(anchor=tk.NW)
            for day in week:
                if day == 0:
                    tk.Label(row, text="", width=3, bg="#FFFFFF").pack(side=tk.LEFT, padx=1, pady=1)
                    continue

                is_selected = (
                    self.selected.year == self.view_year
                    and self.selected.month == self.view_month
                    and self.selected.day == day
                )
                is_today = (
                    today.year == self.view_year
                    and today.month == self.view_month
                    and today.day == day
                )

                bg = SELECT_BG if is_selected else "#FFFFFF"
                text_fg = SELECT_FG if is_selected else NORMAL_FG

                btn = tk.Label(
                    row,
                    text=str(day),
                    width=3,
                    bg=bg,
                    fg=text_fg,
                    cursor="hand2",
                    font=("Microsoft YaHei", 9),
                    highlightbackground=TODAY_BORDER if is_today and not is_selected else bg,
                    highlightthickness=1 if is_today and not is_selected else 0,
                )
                btn.pack(side=tk.LEFT, padx=1, pady=1)
                btn.bind("<Button-1>", lambda e, d=day: self._select_day(d))

    def _select_day(self, day):
        self.selected = self.selected.replace(
            year=self.view_year,
            month=self.view_month,
            day=day,
        )
        self._render_calendar()
        self._refresh_preview()

    def _read_time_from_lists(self):
        try:
            hour = int(self.hour_list.get(self.hour_list.curselection()[0]))
            minute = int(self.minute_list.get(self.minute_list.curselection()[0]))
            second = int(self.second_list.get(self.second_list.curselection()[0]))
        except (IndexError, ValueError, tk.TclError):
            return
        self.selected = self.selected.replace(hour=hour, minute=minute, second=second)

    def _on_time_select(self, event=None):
        if self._updating_lists:
            return
        self._read_time_from_lists()
        self._refresh_preview()

    def _sync_time_lists(self):
        self._updating_lists = True
        try:
            for listbox, value in (
                (self.hour_list, self.selected.hour),
                (self.minute_list, self.selected.minute),
                (self.second_list, self.selected.second),
            ):
                listbox.selection_clear(0, tk.END)
                listbox.selection_set(value)
                listbox.see(value)
        finally:
            self._updating_lists = False

    def _refresh_preview(self):
        self.preview_var.set(format_datetime(self.selected))

    def _handle_confirm(self):
        self._read_time_from_lists()
        if self.on_commit:
            self.on_commit(self.selected)
        self.close()

    def _handle_today(self):
        self.selected = datetime.now()
        self.view_year = self.selected.year
        self.view_month = self.selected.month
        self._render_calendar()
        self._sync_time_lists()
        self._refresh_preview()

    def _handle_reset_time(self):
        self.selected = self.selected.replace(hour=0, minute=0, second=0)
        self._sync_time_lists()
        self._refresh_preview()

    def _handle_clear(self):
        if self.on_clear:
            self.on_clear()
        self.close()
