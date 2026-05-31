"""Tkinter GUI for Kimodo BVH → Mixamo retarget."""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Kimodo BVH → Mixamo Retarget")
        self.resizable(True, True)
        self.minsize(560, 480)
        self._build_ui()
        self._center()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # ── Input file ──────────────────────────────────────────────
        frm_in = ttk.LabelFrame(self, text="Input", padding=6)
        frm_in.pack(fill="x", **pad)

        ttk.Label(frm_in, text="BVH file:").grid(row=0, column=0, sticky="w")
        self._input_var = tk.StringVar()
        ttk.Entry(frm_in, textvariable=self._input_var, width=52).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )
        ttk.Button(frm_in, text="Browse…", command=self._browse_input).grid(
            row=0, column=2, padx=(4, 0)
        )
        frm_in.columnconfigure(1, weight=1)

        # ── Output file ──────────────────────────────────────────────
        frm_out = ttk.LabelFrame(self, text="Output", padding=6)
        frm_out.pack(fill="x", **pad)

        ttk.Label(frm_out, text="BVH file:").grid(row=0, column=0, sticky="w")
        self._output_var = tk.StringVar()
        ttk.Entry(frm_out, textvariable=self._output_var, width=52).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )
        ttk.Button(frm_out, text="Browse…", command=self._browse_output).grid(
            row=0, column=2, padx=(4, 0)
        )
        frm_out.columnconfigure(1, weight=1)

        # ── Options ──────────────────────────────────────────────────
        frm_opt = ttk.LabelFrame(self, text="Options", padding=6)
        frm_opt.pack(fill="x", **pad)

        # Scale
        ttk.Label(frm_opt, text="Scale:").grid(row=0, column=0, sticky="w")
        self._scale_var = tk.StringVar(value="1.0")
        ttk.Entry(frm_opt, textvariable=self._scale_var, width=8).grid(
            row=0, column=1, sticky="w", padx=(4, 0)
        )
        ttk.Label(
            frm_opt,
            text="  (1.0 = keep units,  100 = m → cm,  0.01 = cm → m)",
            foreground="#555",
        ).grid(row=0, column=2, sticky="w", padx=(6, 0))

        # Yaw
        ttk.Label(frm_opt, text="Yaw offset (°):").grid(row=1, column=0, sticky="w")
        self._yaw_var = tk.StringVar(value="0")
        ttk.Entry(frm_opt, textvariable=self._yaw_var, width=8).grid(
            row=1, column=1, sticky="w", padx=(4, 0)
        )
        ttk.Label(
            frm_opt,
            text="  rotate character around Y axis",
            foreground="#555",
        ).grid(row=1, column=2, sticky="w", padx=(6, 0))

        # Strip namespace
        self._strip_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frm_opt,
            text='Remove "mixamorig:" prefix from joint names',
            variable=self._strip_var,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # ── Run button ───────────────────────────────────────────────
        self._run_btn = ttk.Button(
            self, text="▶  Retarget", command=self._on_run, width=20
        )
        self._run_btn.pack(pady=(4, 2))

        # ── Progress bar ─────────────────────────────────────────────
        self._progress = ttk.Progressbar(self, mode="indeterminate", length=400)
        self._progress.pack(fill="x", padx=8)

        # ── Log ──────────────────────────────────────────────────────
        frm_log = ttk.LabelFrame(self, text="Log", padding=4)
        frm_log.pack(fill="both", expand=True, **pad)

        self._log_text = tk.Text(
            frm_log, height=10, state="disabled", wrap="word",
            font=("Courier", 9), bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white",
        )
        scroll = ttk.Scrollbar(frm_log, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._log_text.pack(side="left", fill="both", expand=True)

    # ------------------------------------------------------------------
    # File dialogs
    # ------------------------------------------------------------------

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Kimodo BVH file",
            filetypes=[("BVH animation", "*.bvh"), ("All files", "*.*")],
        )
        if not path:
            return
        self._input_var.set(path)
        base, _ = os.path.splitext(path)
        if not self._output_var.get():
            self._output_var.set(base + "_mixamo.bvh")

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save retargeted BVH",
            defaultextension=".bvh",
            filetypes=[("BVH animation", "*.bvh"), ("All files", "*.*")],
        )
        if path:
            self._output_var.set(path)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _on_run(self) -> None:
        src_path = self._input_var.get().strip()
        dst_path = self._output_var.get().strip()

        if not src_path:
            messagebox.showwarning("Missing input", "Please select an input BVH file.")
            return
        if not os.path.isfile(src_path):
            messagebox.showerror("File not found", f"Cannot find:\n{src_path}")
            return
        if not dst_path:
            messagebox.showwarning("Missing output", "Please specify an output path.")
            return

        try:
            scale = float(self._scale_var.get())
            yaw = float(self._yaw_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Scale and Yaw must be numbers.")
            return

        self._run_btn.configure(state="disabled")
        self._progress.start(12)
        self._log_clear()

        args = (src_path, dst_path, scale, yaw, self._strip_var.get())
        thread = threading.Thread(target=self._run_worker, args=args, daemon=True)
        thread.start()

    def _run_worker(
        self,
        src: str,
        dst: str,
        scale: float,
        yaw: float,
        strip: bool,
    ) -> None:
        try:
            # Imports here so GUI starts fast even if numpy is slow to load
            from bvh_reader import read_bvh
            from bvh_writer import write_bvh
            from retarget import retarget as do_retarget

            self._log(f"Reading  {src}")
            bvh = read_bvh(src)
            self._log(f"  Joints : {len(bvh.joints)}")
            self._log(f"  Frames : {bvh.num_frames}  @  {bvh.fps:.2f} fps")

            self._log("Retargeting…")
            result, stats = do_retarget(
                bvh,
                scale=scale,
                yaw_deg=yaw,
                strip_namespace=strip,
                log=self._log,
            )

            self._log(f"Writing  {dst}")
            write_bvh(result, dst)

            size_kb = os.path.getsize(dst) / 1024
            self._log(f"Done ✓  →  {dst}  ({size_kb:.1f} KB)")
            self.after(0, lambda: messagebox.showinfo(
                "Done",
                f"Retargeted {stats['matched']}/{stats['total']} joints.\n"
                f"Saved to:\n{dst}",
            ))
        except Exception as exc:
            import traceback
            self._log(f"ERROR: {exc}")
            self._log(traceback.format_exc())
            self.after(0, lambda: messagebox.showerror("Error", str(exc)))
        finally:
            self.after(0, self._run_done)

    def _run_done(self) -> None:
        self._progress.stop()
        self._run_btn.configure(state="normal")

    # ------------------------------------------------------------------
    # Log helpers (thread-safe via after())
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        self.after(0, lambda m=msg: self._log_append(m))

    def _log_append(self, msg: str) -> None:
        self._log_text.configure(state="normal")
        self._log_text.insert("end", msg + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _log_clear(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def _center(self) -> None:
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
