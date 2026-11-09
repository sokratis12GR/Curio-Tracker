import math

import customtkinter as ctk
from PIL import Image, ImageTk

import config as c
import platform_compat
from fonts import make_font
from img_utils import get_local_image
from logger import log_message
from settings import get_setting, set_setting
from win_utils import center_window_on_parent, get_poe_bbox


class OCRRegionEditor:
    PREVIEW_MAX_WIDTH = 900
    PREVIEW_MAX_HEIGHT = 600

    def __init__(self, parent, owner):
        self.parent = parent
        self.owner = owner

        self.window = None

        self.drag_start_x = None
        self.drag_start_y = None

        self.rect_id = None
        self.rect_coords = None

        self.preview_image = None
        self.tk_image = None

        self.preview_width = 0
        self.preview_height = 0

        self.using_example_image = False

        self._capture_preview()

        self.window = ctk.CTkToplevel(parent)
        self.window.title("Configure OCR Region")
        self.window.resizable(False, False)

        self.window.transient(parent)

        self.window.protocol(
            "WM_DELETE_WINDOW",
            self._close
        )

        self._build_ui()
        self._draw_saved_region()

        self.window.update_idletasks()

        center_window_on_parent(
            self.window,
            parent
        )

        self.window.lift()
        self.window.grab_set()
        self.window.focus_force()

    def _close(self):
        try:
            if self.window:
                self.window.grab_release()
        except Exception:
            pass

        try:
            if self.window:
                self.window.destroy()
        except Exception:
            pass

        try:
            if self.parent and self.parent.winfo_exists():
                self.parent.deiconify()
                self.parent.lift()
                self.parent.grab_set()
                self.parent.focus_force()
        except Exception:
            pass

    def _capture_preview(self):
        bbox = get_poe_bbox()

        if c.DEBUGGING:
            log_message(
                "OCR Region",
                f"PoE bbox returned: {bbox!r}"
            )

        if not bbox:
            log_message(
                "OCR Region",
                "Path of Exile window not found. Using example image."
            )

            screenshot = get_local_image(
                "assets/ocr_example.jpeg"
            )

            if screenshot is None:
                raise RuntimeError(
                    "Could not locate Path of Exile window and "
                    "the example OCR image could not be loaded."
                )

            self.using_example_image = True

        else:
            self.using_example_image = False

            left, top, right, bottom = bbox

            screenshot = platform_compat.grab_screen(
                bbox=(
                    int(left),
                    int(top),
                    int(right),
                    int(bottom)
                )
            )

        original_width, original_height = screenshot.size

        scale = min(
            self.PREVIEW_MAX_WIDTH / original_width,
            self.PREVIEW_MAX_HEIGHT / original_height,
            1.0
        )

        self.preview_width = int(
            original_width * scale
        )

        self.preview_height = int(
            original_height * scale
        )

        self.preview_image = screenshot.resize(
            (
                self.preview_width,
                self.preview_height
            ),
            Image.Resampling.LANCZOS
        )

        if c.DEBUGGING:
            log_message(
                "OCR Region",
                (
                    f"Using {'example' if self.using_example_image else 'live'} image | "
                    f"preview={self.preview_width}x{self.preview_height}"
                )
            )

    def _build_ui(self):
        self.tk_image = ImageTk.PhotoImage(
            self.preview_image,
            master=self.window
        )

        container = ctk.CTkFrame(
            self.window,
            fg_color="transparent"
        )
        container.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )

        instruction_text = (
            "Drag over the area that should be processed by OCR."
        )

        if self.using_example_image:
            instruction_text += (
                "\nPath of Exile was not detected, so an example image is being used."
            )

        ctk.CTkLabel(
            container,
            text=instruction_text,
            justify="left"
        ).pack(
            anchor="w",
            pady=(0, 8)
        )

        self.canvas = ctk.CTkCanvas(
            container,
            width=self.preview_width,
            height=self.preview_height,
            highlightthickness=0,
            cursor="cross"
        )
        self.canvas.pack()

        self.canvas.create_image(
            0,
            0,
            anchor="nw",
            image=self.tk_image
        )

        self.canvas.bind(
            "<Button-1>",
            self._on_mouse_down
        )

        self.canvas.bind(
            "<B1-Motion>",
            self._on_mouse_drag
        )

        self.canvas.bind(
            "<ButtonRelease-1>",
            self._on_mouse_up
        )

        self.info_label = ctk.CTkLabel(
            container,
            text=""
        )
        self.info_label.pack(
            anchor="w",
            pady=(8, 5)
        )

        buttons = ctk.CTkFrame(
            container,
            fg_color="transparent"
        )
        buttons.pack(fill="x", pady=(5, 0))

        ctk.CTkButton(
            buttons,
            text="Reset",
            width=100,
            command=self._reset
        ).pack(side="left")

        ctk.CTkButton(
            buttons,
            text="Cancel",
            width=100,
            command=self._close
        ).pack(side="right")

        ctk.CTkButton(
            buttons,
            text="Save",
            width=100,
            command=self._save
        ).pack(side="right", padx=(0, 8))

    def _draw_saved_region(self):
        left = self.owner.ocr_region_left_var.get()
        top = self.owner.ocr_region_top_var.get()
        right = self.owner.ocr_region_right_var.get()
        bottom = self.owner.ocr_region_bottom_var.get()

        x1 = left * self.preview_width
        y1 = top * self.preview_height
        x2 = right * self.preview_width
        y2 = bottom * self.preview_height

        self._set_rectangle(x1, y1, x2, y2)

    def _on_mouse_down(self, event):
        self.drag_start_x = self._clamp(
            event.x,
            0,
            self.preview_width
        )

        self.drag_start_y = self._clamp(
            event.y,
            0,
            self.preview_height
        )

        self._set_rectangle(
            self.drag_start_x,
            self.drag_start_y,
            self.drag_start_x,
            self.drag_start_y
        )

    def _on_mouse_drag(self, event):
        if self.drag_start_x is None:
            return

        x = self._clamp(
            event.x,
            0,
            self.preview_width
        )

        y = self._clamp(
            event.y,
            0,
            self.preview_height
        )

        self._set_rectangle(
            self.drag_start_x,
            self.drag_start_y,
            x,
            y
        )

    def _on_mouse_up(self, event):
        if self.drag_start_x is None:
            return

        x = self._clamp(
            event.x,
            0,
            self.preview_width
        )

        y = self._clamp(
            event.y,
            0,
            self.preview_height
        )

        self._set_rectangle(
            self.drag_start_x,
            self.drag_start_y,
            x,
            y
        )

        self.drag_start_x = None
        self.drag_start_y = None

    def _set_rectangle(self, x1, y1, x2, y2):
        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))

        x1 = self._clamp(x1, 0, self.preview_width)
        x2 = self._clamp(x2, 0, self.preview_width)
        y1 = self._clamp(y1, 0, self.preview_height)
        y2 = self._clamp(y2, 0, self.preview_height)

        # Keep our own authoritative copy.
        self.rect_coords = (x1, y1, x2, y2)

        if self.rect_id is None:
            self.rect_id = self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline="red",
                width=3
            )
        else:
            self.canvas.coords(
                self.rect_id,
                x1,
                y1,
                x2,
                y2
            )

        self._update_info()

    def _update_info(self):
        if self.rect_coords is None:
            return

        x1, y1, x2, y2 = self.rect_coords

        width = max(0, x2 - x1)
        height = max(0, y2 - y1)

        total_area = self.preview_width * self.preview_height
        selected_area = width * height

        if total_area <= 0:
            percent = 0.0
        else:
            percent = (selected_area / total_area) * 100

        excluded = 100 - percent

        region_width_pct = (
            (width / self.preview_width) * 100
            if self.preview_width > 0
            else 0.0
        )

        region_height_pct = (
            (height / self.preview_height) * 100
            if self.preview_height > 0
            else 0.0
        )

        self.info_label.configure(
            text=(
                f"OCR area: {percent:.1f}%   |   "
                f"Width: {region_width_pct:.1f}%   |   "
                f"Height: {region_height_pct:.1f}%   |   "
                f"Excluded: {excluded:.1f}%"
            )
        )

    def _reset(self):
        left, top, right, bottom = c.OCR_REGION_PRESETS["Recommended"]

        self._set_rectangle(
            left * self.preview_width,
            top * self.preview_height,
            right * self.preview_width,
            bottom * self.preview_height
        )

    def _save(self):
        if self.rect_coords is None:
            return

        x1, y1, x2, y2 = self.rect_coords

        # Prevent accidentally saving an unusably tiny region.
        if x2 - x1 < 20 or y2 - y1 < 20:
            self.parent.bell()
            return

        if self.preview_width <= 0 or self.preview_height <= 0:
            return

        left = x1 / self.preview_width
        top = y1 / self.preview_height
        right = x2 / self.preview_width
        bottom = y2 / self.preview_height

        left = self._clamp(left, 0.0, 1.0)
        top = self._clamp(top, 0.0, 1.0)
        right = self._clamp(right, 0.0, 1.0)
        bottom = self._clamp(bottom, 0.0, 1.0)

        set_setting("Application", "ocr_region_left", left)
        set_setting("Application", "ocr_region_top", top)
        set_setting("Application", "ocr_region_right", right)
        set_setting("Application", "ocr_region_bottom", bottom)

        self.owner.ocr_region_left_var.set(left)
        self.owner.ocr_region_top_var.set(top)
        self.owner.ocr_region_right_var.set(right)
        self.owner.ocr_region_bottom_var.set(bottom)

        set_setting(
            "Application",
            "ocr_region_preset",
            "Custom"
        )

        self.owner.ocr_region_preset_var.set("Custom")

        if self.owner.ocr_region_label:
            self.owner.ocr_region_label.configure(
                text=self.owner._get_ocr_region_description()
            )

        log_message(
            "OCR Region",
            (
                f"{left:.4f}, {top:.4f}, "
                f"{right:.4f}, {bottom:.4f}"
            )
        )

        self._close()

    @staticmethod
    def _clamp(value, minimum, maximum):
        return max(
            minimum,
            min(maximum, value)
        )


class CaptureSettingsMixin:
    # -------------------------------
    # Capture / OCR
    # -------------------------------
    def _build_capture(self, frame):
        row = 0

        def section_title(text, pady=(0, 5)):
            nonlocal row

            ctk.CTkLabel(
                frame,
                text=text,
                font=make_font(12, "bold")
            ).grid(
                row=row,
                column=0,
                columnspan=2,
                sticky="w",
                pady=pady
            )

            row += 1

        def field_label(text, pady=(0, 0)):
            ctk.CTkLabel(
                frame,
                text=text
            ).grid(
                row=row,
                column=0,
                sticky="w",
                pady=pady
            )

        # --------------------------------------------------
        # OCR region
        # --------------------------------------------------
        section_title("OCR Capture Region")

        field_label("Capture Area:")

        self.ocr_region_label = ctk.CTkLabel(
            frame,
            text=self._get_ocr_region_description()
        )

        self.ocr_region_label.grid(
            row=row,
            column=1,
            sticky="w"
        )

        row += 1

        field_label(
            "Preset:",
            pady=(6, 0)
        )

        self.ocr_region_preset_var = ctk.StringVar(
            value=get_setting(
                "Application",
                "ocr_region_preset",
                c.DEFAULT_OCR_REGION_PRESET
            )
        )

        ctk.CTkComboBox(
            frame,
            variable=self.ocr_region_preset_var,
            values=list(c.OCR_REGION_PRESETS.keys()),
            width=self.width,
            state="readonly",
            command=self._apply_ocr_region_preset
        ).grid(
            row=row,
            column=1,
            sticky="w",
            pady=(6, 0)
        )

        row += 1

        ctk.CTkButton(
            frame,
            text="Configure OCR Region",
            width=self.long_width,
            command=self._open_ocr_region_editor
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 0)
        )

        row += 1

        # --------------------------------------------------
        # Layout capture
        # --------------------------------------------------
        section_title(
            "Blueprint Layout Capture",
            pady=(14, 5)
        )

        field_label("Top Right Area %:")

        ctk.CTkEntry(
            frame,
            textvariable=self.top_right_target_area_percent_var,
            width=self.width
        ).grid(
            row=row,
            column=1,
            sticky="w"
        )

        self.top_right_target_area_percent_var.trace_add(
            "write",
            self._update_top_right_target_area_percent
        )

        row += 1

        ctk.CTkButton(
            frame,
            text="Visualise Capture Area",
            width=self.long_width,
            command=self._visualise_top_right_capture_area
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 0)
        )

    # -------------------------------
    # Capture
    # -------------------------------
    def _update_top_right_target_area_percent(self, *_):
        val = self.top_right_target_area_percent_var.get()

        if val in ("", ".", "-", "+"):
            return

        try:
            percent = float(val)
        except ValueError:
            return

        percent = max(0.01, min(1.00, percent))

        if str(percent) != val:
            self.top_right_target_area_percent_var.set(str(percent))
            return

        log_message("Top Right Target Area Percent", percent)
        set_setting("Application", "top_right_target_area_percent", percent)

    def _get_ocr_region_description(self):
        left = self.ocr_region_left_var.get()
        top = self.ocr_region_top_var.get()
        right = self.ocr_region_right_var.get()
        bottom = self.ocr_region_bottom_var.get()

        area = (right - left) * (bottom - top)
        area = max(0.0, min(1.0, area))

        return f"{area * 100:.1f}% of game window"

    def _open_ocr_region_editor(self):
        settings_window = self.settings_window

        if not settings_window:
            return

        try:
            if not settings_window.winfo_exists():
                return
        except Exception:
            return

        try:
            settings_window.grab_release()
        except Exception:
            pass

        try:
            OCRRegionEditor(
                parent=settings_window,
                owner=self
            )

        except Exception as error:
            import traceback

            log_message(
                "OCR Region",
                (
                    f"Failed to open OCR region editor: {error}\n"
                    f"{traceback.format_exc()}"
                )
            )

            try:
                settings_window.grab_set()
                settings_window.lift()
                settings_window.focus_force()
            except Exception:
                pass

    def _apply_ocr_region_preset(self, preset_name):
        region = c.OCR_REGION_PRESETS.get(preset_name)

        if region is None:
            return

        left, top, right, bottom = region

        self.ocr_region_left_var.set(left)
        self.ocr_region_top_var.set(top)
        self.ocr_region_right_var.set(right)
        self.ocr_region_bottom_var.set(bottom)

        set_setting("Application", "ocr_region_preset", preset_name)
        set_setting("Application", "ocr_region_left", left)
        set_setting("Application", "ocr_region_top", top)
        set_setting("Application", "ocr_region_right", right)
        set_setting("Application", "ocr_region_bottom", bottom)

        if self.ocr_region_label:
            self.ocr_region_label.configure(
                text=self._get_ocr_region_description()
            )

        log_message(
            "OCR Region Preset",
            f"{preset_name}: {left:.3f}, {top:.3f}, "
            f"{right:.3f}, {bottom:.3f}"
        )

    def _visualise_top_right_capture_area(self):
        # Toggle existing preview off.
        if self.top_right_target_capture_preview_window:
            self._hide_top_right_capture_area()
            return

        try:
            percent = float(
                self.top_right_target_area_percent_var.get()
            )
        except (TypeError, ValueError):
            percent = c.DEFAULT_TOP_RIGHT_CAPTURE_PERCENT

        percent = max(
            0.01,
            min(1.0, percent)
        )

        screen_width = self.parent.winfo_screenwidth()
        screen_height = self.parent.winfo_screenheight()

        aspect_ratio = (c.TOP_RIGHT_CUT_WIDTH / c.TOP_RIGHT_CUT_HEIGHT)

        total_area = (screen_width * screen_height)

        target_area = (total_area * percent)

        capture_height = math.sqrt(target_area / aspect_ratio)

        capture_width = (capture_height * aspect_ratio)

        capture_width = int(capture_width)
        capture_height = int(capture_height)

        capture_width = min(screen_width, capture_width)

        capture_height = min(screen_height, capture_height)

        x = screen_width - capture_width
        y = 0

        try:
            if self.settings_window and self.settings_window.winfo_exists():
                self.settings_window.grab_release()
        except Exception:
            pass

        preview = ctk.CTkToplevel(
            self.parent
        )

        self.top_right_target_capture_preview_window = preview

        preview.overrideredirect(True)

        preview.attributes("-topmost", True)

        try:
            preview.attributes("-alpha", 0.72)
        except Exception:
            pass

        preview.geometry(
            f"{capture_width}x{capture_height}+{x}+{y}"
        )

        # One consistent background color.
        capture_bg = "#300000"

        preview.configure(fg_color=capture_bg)

        border = ctk.CTkFrame(
            preview,
            fg_color=capture_bg,
            border_width=3,
            border_color="#FF4040",
            corner_radius=0
        )

        border.pack(fill="both", expand=True)

        title_label = ctk.CTkLabel(
            border,
            text="Layout Capture Area",
            font=make_font(
                12,
                "bold"
            ),
            text_color="#FFFFFF",
            fg_color=capture_bg
        )

        title_label.place(relx=0.5, rely=0.27, anchor="center")

        size_label = ctk.CTkLabel(
            border,
            text=(
                f"{percent * 100:.1f}%"
                f"  •  "
                f"{capture_width}×{capture_height}px"
            ),
            font=make_font(
                10,
                "bold"
            ),
            text_color="#FFFFFF",
            fg_color=capture_bg
        )

        size_label.place(relx=0.5, rely=0.52, anchor="center")

        close_label = ctk.CTkLabel(border, text="Click here to close", font=make_font(9), text_color="#D0D0D0",
                                   fg_color=capture_bg, cursor="hand2")

        close_label.place(relx=0.5, rely=0.75, anchor="center")

        def close_preview(_event=None):
            self._hide_top_right_capture_area()

        preview.bind("<Button-1>", close_preview)

        border.bind("<Button-1>", close_preview)

        title_label.bind("<Button-1>", close_preview)

        size_label.bind("<Button-1>", close_preview)

        close_label.bind("<Button-1>", close_preview)

        preview.lift()

        try:
            preview.focus_force()
        except Exception:
            pass

    def _hide_top_right_capture_area(self):
        preview = self.top_right_target_capture_preview_window

        self.top_right_target_capture_preview_window = None

        if preview:
            try:
                if preview.winfo_exists():
                    preview.destroy()
            except Exception:
                pass

        try:
            if self.settings_window and self.settings_window.winfo_exists():
                self.settings_window.lift()
                self.settings_window.grab_set()
                self.settings_window.focus_force()
        except Exception:
            pass
