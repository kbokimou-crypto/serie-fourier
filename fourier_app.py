"""
Série de Fourier – modélisation et prédiction d'une suite de nombres.

Charge un fichier CSV (valeurs dans la colonne A), trouve l'équation
    u(n) = tendance(n) + somme_k R_k cos(2πn/T_k + φ_k)
affiche les données, le modèle et la prédiction, et permet d'ajuster
les coefficients à la main.
"""

import csv
import math
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib
import matplotlib.ticker

matplotlib.use("TkAgg")
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

import fourier_model as fm

APP_TITLE = "Série de Fourier – modélisation de suites"
TREND_LABELS = ["Constante (degré 0)", "Linéaire (degré 1)", "Quadratique (degré 2)"]


def fmt(x, digits=6):
    return f"{x:.{digits}g}"


class ScrollFrame(ttk.Frame):
    """Cadre avec barre de défilement verticale."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width)
        )
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1280x800")
        self.minsize(1000, 640)

        self.y = None
        self.model = None
        self.path = None

        self.var_harm = tk.IntVar(value=3)
        self.var_trend = tk.StringVar(value=TREND_LABELS[1])
        self.var_n0 = tk.IntVar(value=1)
        self.var_minper = tk.DoubleVar(value=2.0)
        self.var_horizon = tk.IntVar(value=20)
        self.var_test = tk.IntVar(value=0)
        self.var_trend_coefs = [tk.StringVar() for _ in range(3)]
        self.term_rows = []

        self._build_ui()
        self._redraw()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, padding=8)
        right = ttk.Frame(paned)
        paned.add(left, weight=0)
        paned.add(right, weight=1)

        # --- fichier ---
        f_file = ttk.LabelFrame(left, text="Données", padding=6)
        f_file.pack(fill="x")
        ttk.Button(f_file, text="Ouvrir un fichier CSV…", command=self.open_csv).pack(fill="x")
        self.lbl_file = ttk.Label(f_file, text="Aucun fichier chargé", wraplength=330)
        self.lbl_file.pack(fill="x", pady=(4, 0))

        # --- paramètres ---
        f_par = ttk.LabelFrame(left, text="Paramètres du modèle", padding=6)
        f_par.pack(fill="x", pady=6)
        rows = [
            ("Nombre de termes de Fourier", ttk.Spinbox(f_par, from_=0, to=30, width=8, textvariable=self.var_harm)),
            ("Tendance", ttk.Combobox(f_par, values=TREND_LABELS, textvariable=self.var_trend, state="readonly", width=20)),
            ("Indice du 1er terme (n₀)", ttk.Spinbox(f_par, from_=0, to=10**6, width=8, textvariable=self.var_n0)),
            ("Période minimale", ttk.Spinbox(f_par, from_=2, to=10**6, increment=0.5, width=8, textvariable=self.var_minper)),
            ("Nombre de termes à prédire", ttk.Spinbox(f_par, from_=0, to=10**6, width=8, textvariable=self.var_horizon)),
            ("Termes gardés pour tester", ttk.Spinbox(f_par, from_=0, to=10**6, width=8, textvariable=self.var_test)),
        ]
        for r, (txt, w) in enumerate(rows):
            ttk.Label(f_par, text=txt).grid(row=r, column=0, sticky="w", pady=1)
            w.grid(row=r, column=1, sticky="ew", padx=(6, 0), pady=1)
        f_par.columnconfigure(1, weight=1)
        ttk.Button(f_par, text="Calculer le modèle (FFT + moindres carrés)", command=self.compute).grid(
            row=len(rows), column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )
        self.var_horizon.trace_add("write", lambda *a: self._safe_redraw())

        # --- résultat ---
        f_res = ttk.LabelFrame(left, text="Équation et qualité", padding=6)
        f_res.pack(side="bottom", fill="x", pady=(6, 0))
        self.txt_eq = tk.Text(f_res, height=4, wrap="word", font=("Consolas", 9))
        self.txt_eq.pack(fill="x")
        self.lbl_metrics = ttk.Label(f_res, text="", justify="left", wraplength=330)
        self.lbl_metrics.pack(fill="x", pady=(4, 0))
        f_b2 = ttk.Frame(f_res)
        f_b2.pack(fill="x", pady=(4, 0))
        ttk.Button(f_b2, text="Copier l'équation", command=self.copy_equation).pack(side="left", fill="x", expand=True)
        ttk.Button(f_b2, text="Exporter en CSV…", command=self.export_csv).pack(
            side="left", fill="x", expand=True, padx=(4, 0)
        )

        # --- coefficients ---
        f_coef = ttk.LabelFrame(left, text="Coefficients (modifiables, Entrée pour appliquer)", padding=6)
        f_coef.pack(fill="both", expand=True)

        f_tr = ttk.Frame(f_coef)
        f_tr.pack(fill="x")
        for i, lab in enumerate(["c₀", "c₁ (×n)", "c₂ (×n²)"]):
            ttk.Label(f_tr, text=lab).grid(row=0, column=i, sticky="w")
            e = ttk.Entry(f_tr, textvariable=self.var_trend_coefs[i], width=12)
            e.grid(row=1, column=i, sticky="ew", padx=2)
            e.bind("<Return>", lambda ev: self.apply_edits())
            e.bind("<FocusOut>", lambda ev: self.apply_edits())
            f_tr.columnconfigure(i, weight=1)

        hdr = ttk.Frame(f_coef)
        hdr.pack(fill="x", pady=(8, 0))
        for i, (lab, w) in enumerate([("Actif", 5), ("Période T", 11), ("Amplitude R", 11), ("Phase φ (rad)", 11), ("", 2)]):
            ttk.Label(hdr, text=lab, width=w).grid(row=0, column=i, sticky="w")

        self.terms_frame = ScrollFrame(f_coef)
        self.terms_frame.pack(fill="both", expand=True)

        f_btn = ttk.Frame(f_coef)
        f_btn.pack(fill="x", pady=(4, 0))
        ttk.Button(f_btn, text="+ Ajouter un terme", command=self.add_term).pack(side="left", fill="x", expand=True)
        ttk.Button(f_btn, text="Réajuster R et φ (garder les T)", command=self.refit).pack(
            side="left", fill="x", expand=True, padx=(4, 0)
        )

        # --- graphique ---
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(211)
        self.ax_spec = self.fig.add_subplot(212)
        self.fig.subplots_adjust(left=0.10, right=0.98, top=0.95, bottom=0.08, hspace=0.35)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        NavigationToolbar2Tk(self.canvas, right).update()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # ------------------------------------------------------------ helpers --
    def _degree(self):
        return TREND_LABELS.index(self.var_trend.get())

    def _int(self, var, default):
        try:
            return int(float(var.get()))
        except (tk.TclError, ValueError):
            return default

    def _train(self):
        """Partie de la suite utilisée pour l'ajustement."""
        test = max(0, self._int(self.var_test, 0))
        if test >= len(self.y) - 3:
            test = 0
        return self.y[: len(self.y) - test] if test else self.y, test

    def _n(self, start_idx, count):
        n0 = self.model.n0 if self.model else self._int(self.var_n0, 1)
        return np.arange(n0 + start_idx, n0 + start_idx + count, dtype=float)

    # ------------------------------------------------------------ actions --
    def open_csv(self):
        path = filedialog.askopenfilename(
            title="Choisir un fichier CSV",
            filetypes=[("Fichiers CSV", "*.csv *.txt"), ("Tous les fichiers", "*.*")],
        )
        if path:
            self.load(path)

    def load(self, path):
        try:
            y, skipped = fm.load_column_a(path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(APP_TITLE, f"Impossible de lire le fichier :\n{exc}")
            return
        self.y, self.path = y, path
        msg = f"{os.path.basename(path)} : {len(y)} valeurs"
        if skipped:
            msg += f" ({skipped} ligne(s) non numérique(s) ignorée(s))"
        self.lbl_file.config(text=msg)
        self.compute()

    def compute(self):
        if self.y is None:
            messagebox.showinfo(APP_TITLE, "Chargez d'abord un fichier CSV.")
            return
        train, _ = self._train()
        try:
            minper = max(2.0, float(self.var_minper.get()))
        except (tk.TclError, ValueError):
            minper = 2.0
        self.model = fm.fit(
            train,
            n_harmonics=self._int(self.var_harm, 3),
            degree=self._degree(),
            n0=self._int(self.var_n0, 1),
            min_period=minper,
        )
        self._model_to_widgets()
        self._redraw()

    def refit(self):
        if self.model is None or self.y is None:
            return
        if not self.apply_edits(redraw=False):
            return
        train, _ = self._train()
        self.model = fm.refit_coefficients(self.model, train, degree=self._degree())
        self._model_to_widgets()
        self._redraw()

    def add_term(self):
        if self.model is None:
            self.model = fm.FourierModel(trend=[0.0], terms=[], n0=self._int(self.var_n0, 1))
        else:
            self.apply_edits(redraw=False)
        default_T = float(len(self.y)) / 2 if self.y is not None else 10.0
        self.model.terms.append(fm.FourierTerm(period=default_T, amplitude=0.0, phase=0.0))
        self._model_to_widgets()
        self._redraw()

    def remove_term(self, idx):
        self.apply_edits(redraw=False)
        if self.model and 0 <= idx < len(self.model.terms):
            del self.model.terms[idx]
            self._model_to_widgets()
            self._redraw()

    def apply_edits(self, redraw=True):
        """Lit les champs de coefficients et met à jour le modèle."""
        if self.model is None:
            return False
        try:
            deg = self._degree()
            trend = []
            for i in range(deg + 1):
                s = self.var_trend_coefs[i].get().strip().replace(",", ".")
                trend.append(float(s) if s else 0.0)
            terms = []
            for row in self.term_rows:
                T = float(row["T"].get().replace(",", "."))
                if T == 0:
                    raise ValueError("une période ne peut pas être nulle")
                terms.append(
                    fm.FourierTerm(
                        period=T,
                        amplitude=float(row["R"].get().replace(",", ".")),
                        phase=float(row["phi"].get().replace(",", ".")),
                        active=bool(row["on"].get()),
                    )
                )
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, f"Coefficient invalide : {exc}")
            return False
        self.model.trend = trend
        self.model.terms = terms
        if redraw:
            self._update_equation()
            self._redraw()
        return True

    def copy_equation(self):
        if self.model:
            self.clipboard_clear()
            self.clipboard_append(self.model.equation(digits=8))

    def export_csv(self):
        if self.model is None or self.y is None:
            return
        path = filedialog.asksaveasfilename(
            title="Exporter les résultats",
            defaultextension=".csv",
            filetypes=[("Fichiers CSV", "*.csv")],
            initialfile="prediction_fourier.csv",
        )
        if not path:
            return
        horizon = max(0, self._int(self.var_horizon, 0))
        total = len(self.y) + horizon
        n = self._n(0, total)
        yhat = self.model.evaluate(n)
        num = lambda v: f"{v:.10g}".replace(".", ",")  # format Excel français
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["n", "valeur observée", "valeur du modèle", "type"])
            for i in range(total):
                obs = num(self.y[i]) if i < len(self.y) else ""
                kind = "donnée" if i < len(self.y) else "prédiction"
                w.writerow([int(n[i]), obs, num(yhat[i]), kind])
            w.writerow([])
            w.writerow([self.model.equation(digits=10)])
        messagebox.showinfo(APP_TITLE, f"Résultats exportés dans :\n{path}")

    # ----------------------------------------------------- model <-> widgets --
    def _model_to_widgets(self):
        m = self.model
        deg = len(m.trend) - 1
        self.var_trend.set(TREND_LABELS[deg])
        for i in range(3):
            self.var_trend_coefs[i].set(fmt(m.trend[i], 10) if i <= deg else "")

        for child in self.terms_frame.inner.winfo_children():
            child.destroy()
        self.term_rows = []
        for idx, t in enumerate(m.terms):
            row = {
                "on": tk.BooleanVar(value=t.active),
                "T": tk.StringVar(value=fmt(t.period, 8)),
                "R": tk.StringVar(value=fmt(t.amplitude, 8)),
                "phi": tk.StringVar(value=fmt(t.phase, 8)),
            }
            fr = self.terms_frame.inner
            ttk.Checkbutton(fr, variable=row["on"], command=self.apply_edits).grid(row=idx, column=0, padx=(8, 8))
            for c, key in enumerate(["T", "R", "phi"], start=1):
                e = ttk.Entry(fr, textvariable=row[key], width=11)
                e.grid(row=idx, column=c, padx=1, pady=1, sticky="ew")
                e.bind("<Return>", lambda ev: self.apply_edits())
                e.bind("<FocusOut>", lambda ev: self.apply_edits())
                e.bind("<Up>", lambda ev, k=key, r=row: self._nudge(r, k, +1))
                e.bind("<Down>", lambda ev, k=key, r=row: self._nudge(r, k, -1))
            ttk.Button(fr, text="✕", width=2, command=lambda i=idx: self.remove_term(i)).grid(row=idx, column=4)
            self.term_rows.append(row)
        self._update_equation()

    def _nudge(self, row, key, direction):
        """Flèches haut/bas : variation de ±1 % (ou ±0,05 rad pour la phase)."""
        try:
            v = float(row[key].get().replace(",", "."))
        except ValueError:
            return "break"
        if key == "phi":
            v += 0.05 * direction
        else:
            step = abs(v) * 0.01 or 0.01
            v += step * direction
        row[key].set(fmt(v, 8))
        self.apply_edits()
        return "break"

    def _update_equation(self):
        self.txt_eq.delete("1.0", "end")
        if self.model:
            self.txt_eq.insert("1.0", self.model.equation())

    # -------------------------------------------------------------- drawing --
    def _safe_redraw(self):
        try:
            self._redraw()
        except Exception:  # noqa: BLE001  (saisie en cours dans un champ)
            pass

    def _redraw(self):
        ax, axs = self.ax, self.ax_spec
        ax.clear()
        axs.clear()
        if self.y is None:
            ax.set_title("Ouvrez un fichier CSV (valeurs en colonne A)")
            axs.set_title("Spectre de Fourier")
            self.canvas.draw_idle()
            return

        N = len(self.y)
        train, test = self._train()
        ntr = len(train)
        n_all = self._n(0, N)
        ax.plot(n_all[:ntr], train, "o", ms=3, color="#1f77b4", label="Données")
        if test:
            ax.plot(n_all[ntr:], self.y[ntr:], "o", ms=3, color="#ff7f0e", label="Données de test")

        info = []
        if self.model is not None:
            horizon = max(0, self._int(self.var_horizon, 0))
            dense = np.linspace(n_all[0], n_all[-1], max(400, 8 * N))
            ax.plot(dense, self.model.evaluate(dense), "-", color="#2ca02c", lw=1.6, label="Modèle")
            if horizon:
                n_pred = self._n(N, horizon)
                dense_p = np.linspace(n_all[-1], n_pred[-1], max(200, 8 * horizon))
                ax.plot(dense_p, self.model.evaluate(dense_p), "--", color="#d62728", lw=1.6, label="Prédiction")
                ax.plot(n_pred, self.model.evaluate(n_pred), ".", color="#d62728", ms=4)
                ax.axvline(n_all[-1] + 0.5, color="gray", lw=0.8, ls=":")

            rmse, r2 = fm.metrics(train, self.model.evaluate(n_all[:ntr]))
            info.append(f"Ajustement : R² = {r2:.4f}   écart-type (RMSE) = {fmt(rmse, 4)}")
            if test:
                rmse_t, r2_t = fm.metrics(self.y[ntr:], self.model.evaluate(n_all[ntr:]))
                info.append(
                    f"Test sur les {test} derniers termes : RMSE = {fmt(rmse_t, 4)}"
                    f"   R² = {r2_t:.4f}"
                )
            if r2 == r2 and r2 < 0.5:
                info.append("⚠ Le modèle explique mal les données : la prédiction est peu fiable.")
        ax.set_xlabel("n")
        ax.set_ylabel("u(n)")
        ax.set_title("Suite, modèle de Fourier et prédiction")
        ax.grid(alpha=0.3)
        ax.legend(loc="best", fontsize=8)

        # spectre du résidu après tendance
        n_tr = n_all[:ntr]
        deg = self._degree()
        X = np.column_stack([n_tr ** p for p in range(deg + 1)])
        c, *_ = np.linalg.lstsq(X, train, rcond=None)
        res = train - X @ c
        nfft = int(2 ** math.ceil(math.log2(max(ntr, 2) * 16)))
        spec = np.abs(np.fft.rfft((res - res.mean()) * np.hanning(ntr), nfft))
        spec *= 2.0 / max(np.hanning(ntr).sum(), 1e-12)
        freqs = np.fft.rfftfreq(nfft)
        mask = freqs >= 1.0 / ntr
        axs.plot(1.0 / freqs[mask], spec[mask], color="#555")
        axs.set_xscale("log")
        axs.xaxis.set_major_locator(matplotlib.ticker.LogLocator(subs=(1.0, 2.0, 5.0)))
        axs.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"{v:g}"))
        axs.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        if self.model is not None:
            for t in self.model.terms:
                if t.active and t.period > 0:
                    axs.axvline(t.period, color="#d62728", lw=1, alpha=0.7)
        axs.set_xlabel("Période T (en nombre de termes, échelle log)")
        axs.set_ylabel("Amplitude")
        axs.set_title("Spectre du signal sans tendance (traits rouges : périodes du modèle)")
        axs.grid(alpha=0.3, which="both")

        self.lbl_metrics.config(text="\n".join(info))
        self.canvas.draw_idle()


def main():
    app = App()
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        app.after(100, lambda: app.load(sys.argv[1]))
    app.mainloop()


if __name__ == "__main__":
    main()
