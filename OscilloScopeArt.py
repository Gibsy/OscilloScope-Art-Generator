import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import numpy as np
import wave
import os
from PIL import Image, ImageTk, ImageFilter
from scipy.ndimage import uniform_filter1d
from skimage import measure

def nearest_neighbor_order(contours_pts):
    if len(contours_pts) <= 1:
        return contours_pts
    ordered = [contours_pts[0]]
    remaining = list(contours_pts[1:])
    while remaining:
        last = ordered[-1][-1]
        best_i, best_d, best_flip = 0, np.inf, False
        for i, c in enumerate(remaining):
            d0 = np.hypot(c[0, 0] - last[0], c[0, 1] - last[1])
            d1 = np.hypot(c[-1, 0] - last[0], c[-1, 1] - last[1])
            if d0 < best_d:
                best_d, best_i, best_flip = d0, i, False
            if d1 < best_d:
                best_d, best_i, best_flip = d1, i, True
        c = remaining.pop(best_i)
        ordered.append(c[::-1] if best_flip else c)
    return ordered

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Oscilloscope Art Generator")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")
        self.image_path = None
        self.preview_img = None
        self._build_ui()

    def _build_ui(self):
        pad = dict(padx=12, pady=6)

        # header
        tk.Label(self, text="Oscilloscope Art Generator", font=("Helvetica", 16, "bold"),
                 bg="#1e1e2e", fg="#cdd6f4").grid(row=0, column=0, columnspan=2, pady=(15, 5))

        # preview
        self.canvas = tk.Canvas(self, width=300, height=300, bg="#11111b",
                                highlightthickness=1, highlightbackground="#313244")
        self.canvas.grid(row=1, column=0, columnspan=2, padx=20, pady=5)
        self.canvas.create_text(150, 150, text="No image selected", fill="#45475a", font=("Helvetica", 10))

        # set
        ctrl = tk.Frame(self, bg="#1e1e2e")
        ctrl.grid(row=2, column=0, columnspan=2, padx=20, pady=10, sticky="ew")

        # controls
        tk.Label(ctrl, text="Sample rate:", bg="#1e1e2e", fg="#cdd6f4").grid(row=0, column=0, sticky="w", pady=2)
        self.sr_var = tk.StringVar(value="44100")
        ttk.Combobox(ctrl, textvariable=self.sr_var, values=["44100", "48000", "96000"], width=12).grid(row=0, column=1,
                                                                                                        sticky="e")

        tk.Label(ctrl, text="Duration (s):", bg="#1e1e2e", fg="#cdd6f4").grid(row=1, column=0, sticky="w", pady=2)
        self.dur_var = tk.DoubleVar(value=10.0)
        tk.Spinbox(ctrl, textvariable=self.dur_var, from_=1, to=60, width=12).grid(row=1, column=1, sticky="e")

        tk.Label(ctrl, text="Point density:", bg="#1e1e2e", fg="#cdd6f4").grid(row=2, column=0, sticky="w", pady=2)
        self.density_var = tk.IntVar(value=1)
        tk.Spinbox(ctrl, textvariable=self.density_var, from_=1, to=10, width=12).grid(row=2, column=1, sticky="e")

        tk.Label(ctrl, text="Min points:", bg="#1e1e2e", fg="#cdd6f4").grid(row=3, column=0, sticky="w", pady=2)
        self.min_pts_var = tk.IntVar(value=50)
        tk.Spinbox(ctrl, textvariable=self.min_pts_var, from_=2, to=1000, width=12).grid(row=3, column=1, sticky="e")

        # progressbar
        self.progress = ttk.Progressbar(self, mode="determinate", length=280)
        self.progress.grid(row=3, column=0, columnspan=2, padx=20, pady=(5, 0))

        # status
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_var, bg="#1e1e2e", fg="#6c7086", font=("Helvetica", 8)).grid(row=4,
                                                                                                             column=0,
                                                                                                             columnspan=2,
                                                                                                             pady=5)

        # buttons
        btn_frame = tk.Frame(self, bg="#1e1e2e")
        btn_frame.grid(row=5, column=0, columnspan=2, pady=(0, 20))

        tk.Button(btn_frame, text="📂 Open Image", command=self._open_image,
                  bg="#89b4fa", fg="#1e1e2e", font=("Helvetica", 9, "bold"), relief="flat", padx=10).pack(side="left",
                                                                                                          padx=5)

        tk.Button(btn_frame, text="▶ Generate WAV", command=self._generate,
                  bg="#a6e3a1", fg="#1e1e2e", font=("Helvetica", 9, "bold"), relief="flat", padx=10).pack(side="left",
                                                                                                          padx=5)

    def _open_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif")])
        if path:
            self.image_path = path
            img = Image.open(path).convert("RGB")
            img.thumbnail((300, 300))
            self.preview_img = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(150, 150, image=self.preview_img)
            self.status_var.set(f"Loaded: {os.path.basename(path)}")

    def _generate(self):
        if not self.image_path:
            messagebox.showwarning("Warning", "Please open an image first!")
            return

        out_path = filedialog.asksaveasfilename(
            defaultextension=".wav",
            initialfile="OscilloscopeArt.wav",
            filetypes=[("WAV audio", "*.wav")]
        )

        if not out_path: return

        try:
            self.status_var.set("Processing...")
            self.progress["value"] = 10
            self.update()

            img = Image.open(self.image_path).convert("L")

            img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
            arr = np.array(img)
            h, w = arr.shape

            raw_contours = measure.find_contours(arr, level=128)

            self.progress["value"] = 40
            self.update()

            processed_contours = []
            min_pts = self.min_pts_var.get()
            density = self.density_var.get()

            for c in raw_contours:
                if len(c) < min_pts: continue
                pts = c[::density]
                y_norm = 1.0 - (pts[:, 0] / h) * 2.0
                x_norm = (pts[:, 1] / w) * 2.0 - 1.0
                processed_contours.append(np.column_stack([x_norm, y_norm]))

            ordered = nearest_neighbor_order(processed_contours)

            all_pts = []
            for c in ordered:
                for p in c: all_pts.append(p)
                all_pts.append(c[0])

            points = np.array(all_pts)
            sr = int(self.sr_var.get())
            total_samples = int(sr * self.dur_var.get())

            reps = int(np.ceil(total_samples / len(points)))
            signal = np.tile(points, (reps, 1))[:total_samples]

            left = uniform_filter1d(signal[:, 0].astype(np.float32), size=3)
            right = uniform_filter1d(signal[:, 1].astype(np.float32), size=3)

            left_i16 = (left * 32767).astype(np.int16)
            right_i16 = (right * 32767).astype(np.int16)

            self.progress["value"] = 80
            self.update()

            with wave.open(out_path, "w") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                stereo = np.empty(total_samples * 2, dtype=np.int16)
                stereo[0::2] = left_i16
                stereo[1::2] = right_i16
                wf.writeframes(stereo.tobytes())

            self.progress["value"] = 100
            self.status_var.set("Success!")
            messagebox.showinfo("Done", f"Saved to:\n{os.path.basename(out_path)}\n"
                                        "test here: https://gibsy.site/OscilloScope-XY\n"
                                        "author: Gibsy")


        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status_var.set("Error")
        finally:
            self.after(2000, lambda: self.progress.configure(value=0))
            self.after(2000, lambda: self.status_var.set("Ready"))


if __name__ == "__main__":
    App().mainloop()