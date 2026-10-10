"""
Moteur de modélisation d'une suite numérique par série de Fourier.

Modèle ajusté :

    u(n) = c0 + c1*n + c2*n^2                       (tendance, degré 0 à 2)
         + somme_k  R_k * cos(2*pi*n / T_k + phi_k)  (termes de Fourier)

Méthode :
  1. on retire la tendance polynomiale (moindres carrés) ;
  2. on calcule la FFT du résidu (avec zéro-padding pour affiner les fréquences)
     et on retient les K pics les plus forts ;
  3. on réajuste tous les coefficients ensemble par moindres carrés
     (A_k cos + B_k sin, puis conversion en amplitude R_k et phase phi_k).
"""

import csv
import io
import math
from dataclasses import dataclass, field

import numpy as np


# --------------------------------------------------------------------------- #
#  Lecture du CSV (colonne A)
# --------------------------------------------------------------------------- #

def _parse_number(text):
    t = text.strip().replace(" ", "").replace(" ", "")
    if not t:
        return None
    # virgule décimale française
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    elif "," in t and "." in t:
        # 1.234,56 -> 1234.56  ou  1,234.56 -> 1234.56
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def load_column_a(path):
    """Lit la colonne A d'un fichier CSV et renvoie un tableau de valeurs.

    Gère : séparateurs ; , tabulation, virgule décimale, ligne d'en-tête,
    lignes vides ou non numériques (ignorées), encodages UTF-8 / Latin-1.
    """
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    sample = "\n".join(text.splitlines()[:50])
    if ";" in sample:
        delim = ";"
    elif "\t" in sample:
        delim = "\t"
    else:
        delim = ","

    values, skipped = [], 0
    for row in csv.reader(io.StringIO(text), delimiter=delim):
        if not row:
            continue
        v = _parse_number(row[0])
        if v is None:
            skipped += 1
        else:
            values.append(v)
    if len(values) < 4:
        raise ValueError(
            "La colonne A doit contenir au moins 4 nombres "
            f"(trouvé {len(values)})."
        )
    return np.asarray(values, dtype=float), skipped


# --------------------------------------------------------------------------- #
#  Modèle
# --------------------------------------------------------------------------- #

@dataclass
class FourierTerm:
    period: float          # période T_k (en nombre de termes)
    amplitude: float       # R_k
    phase: float           # phi_k (radians)
    active: bool = True

    @property
    def frequency(self):
        return 1.0 / self.period


@dataclass
class FourierModel:
    trend: list = field(default_factory=lambda: [0.0])   # [c0, c1, c2]
    terms: list = field(default_factory=list)            # FourierTerm
    n0: int = 1                                           # indice du 1er terme

    def evaluate(self, n):
        n = np.asarray(n, dtype=float)
        y = np.zeros_like(n)
        for p, c in enumerate(self.trend):
            y += c * n ** p
        for t in self.terms:
            if t.active and t.period != 0:
                y += t.amplitude * np.cos(2 * np.pi * n / t.period + t.phase)
        return y

    def equation(self, digits=4):
        def f(x):
            return f"{x:.{digits}g}"

        parts = []
        names = ["", "·n", "·n²"]
        for p, c in enumerate(self.trend):
            if p == 0:
                parts.append(f(c))
            else:
                sign = "-" if c < 0 else "+"
                parts.append(f" {sign} {f(abs(c))}{names[p]}")
        for t in self.terms:
            if not t.active:
                continue
            sign = "-" if t.amplitude < 0 else "+"
            ph = t.phase
            ph_txt = f" {'-' if ph < 0 else '+'} {f(abs(ph))}" if abs(ph) > 1e-12 else ""
            parts.append(
                f" {sign} {f(abs(t.amplitude))}·cos(2π·n/{f(t.period)}{ph_txt})"
            )
        return "u(n) = " + "".join(parts)


def _design_matrix(n, degree, freqs):
    cols = [n ** p for p in range(degree + 1)]
    for fr in freqs:
        cols.append(np.cos(2 * np.pi * fr * n))
        cols.append(np.sin(2 * np.pi * fr * n))
    return np.column_stack(cols)


def detect_frequencies(residual, k, pad_factor=16, min_period=2.0, max_period=None):
    """Renvoie les k fréquences (cycles par terme) les plus fortes du résidu."""
    N = len(residual)
    if max_period is None:
        max_period = N  # pas de période plus longue que la série observée
    nfft = int(2 ** math.ceil(math.log2(N * pad_factor)))
    window = np.hanning(N)
    spec = np.abs(np.fft.rfft((residual - residual.mean()) * window, nfft))
    freqs = np.fft.rfftfreq(nfft, d=1.0)

    valid = (freqs >= 1.0 / max_period) & (freqs <= 1.0 / min_period)
    # maxima locaux uniquement
    peaks = []
    for i in range(1, len(spec) - 1):
        if valid[i] and spec[i] >= spec[i - 1] and spec[i] >= spec[i + 1]:
            peaks.append((spec[i], freqs[i]))
    peaks.sort(reverse=True)

    chosen = []
    min_sep = 1.0 / N  # résolution fréquentielle réelle
    for _, fr in peaks:
        if all(abs(fr - c) >= min_sep for c in chosen):
            chosen.append(fr)
        if len(chosen) == k:
            break
    return chosen


def fit_least_squares(n, y, degree, freqs):
    """Moindres carrés pour la tendance + cos/sin aux fréquences données."""
    X = _design_matrix(n, degree, freqs)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    trend = list(coef[: degree + 1])
    terms = []
    for i, fr in enumerate(freqs):
        a = coef[degree + 1 + 2 * i]
        b = coef[degree + 2 + 2 * i]
        # a cos(x) + b sin(x) = R cos(x + phi), R = sqrt(a²+b²), phi = atan2(-b, a)
        R = math.hypot(a, b)
        phi = math.atan2(-b, a)
        terms.append(FourierTerm(period=1.0 / fr, amplitude=R, phase=phi))
    terms.sort(key=lambda t: -t.amplitude)
    return trend, terms


def _sse(n, y, degree, freqs):
    X = _design_matrix(n, degree, freqs)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ coef
    return float(r @ r)


def refine_frequencies(n, y, degree, freqs, passes=3, min_period=2.0):
    """Affine chaque fréquence (recherche par section dorée) pour minimiser
    l'erreur quadratique du modèle complet. Améliore nettement l'extrapolation."""
    freqs = list(freqs)
    N = len(y)
    g = (math.sqrt(5) - 1) / 2
    fmax = 1.0 / min_period
    for _ in range(passes):
        for i in range(len(freqs)):
            def cost(f):
                trial = freqs[:i] + [f] + freqs[i + 1:]
                return _sse(n, y, degree, trial)

            a = max(1e-9, freqs[i] - 0.5 / N)
            b = min(fmax, freqs[i] + 0.5 / N)
            c, d = b - g * (b - a), a + g * (b - a)
            fc, fd = cost(c), cost(d)
            for _ in range(30):
                if fc < fd:
                    b, d, fd = d, c, fc
                    c = b - g * (b - a)
                    fc = cost(c)
                else:
                    a, c, fc = c, d, fd
                    d = a + g * (b - a)
                    fd = cost(d)
            best = (a + b) / 2
            if cost(best) < cost(freqs[i]):
                freqs[i] = best
    return freqs


def fit(y, n_harmonics=3, degree=1, n0=1, min_period=2.0):
    """Ajuste le modèle complet sur la suite y (indices n0, n0+1, ...)."""
    y = np.asarray(y, dtype=float)
    N = len(y)
    n = np.arange(n0, n0 + N, dtype=float)
    degree = max(0, min(int(degree), 2, N - 1))

    # nombre maximal de paramètres raisonnable
    max_h = max(0, (N - (degree + 1) - 1) // 2)
    n_harmonics = max(0, min(int(n_harmonics), max_h))

    Xt = _design_matrix(n, degree, [])
    ct, *_ = np.linalg.lstsq(Xt, y, rcond=None)
    residual = y - Xt @ ct

    freqs = detect_frequencies(residual, n_harmonics, min_period=min_period) if n_harmonics else []
    if freqs:
        freqs = refine_frequencies(n, y, degree, freqs, min_period=min_period)
    trend, terms = fit_least_squares(n, y, degree, freqs)
    return FourierModel(trend=trend, terms=terms, n0=n0)


def refit_coefficients(model, y, degree=None):
    """Garde les périodes (éventuellement modifiées à la main) et recalcule
    au mieux tendance, amplitudes et phases."""
    y = np.asarray(y, dtype=float)
    n = np.arange(model.n0, model.n0 + len(y), dtype=float)
    if degree is None:
        degree = len(model.trend) - 1
    active = [t for t in model.terms if t.active and t.period != 0]
    inactive = [t for t in model.terms if not (t.active and t.period != 0)]
    trend, terms = fit_least_squares(n, y, degree, [t.frequency for t in active])
    return FourierModel(trend=trend, terms=terms + inactive, n0=model.n0)


def metrics(y, yhat):
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    err = y - yhat
    rmse = float(np.sqrt(np.mean(err ** 2)))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - float(np.sum(err ** 2)) / ss_tot if ss_tot > 0 else float("nan")
    return rmse, r2
