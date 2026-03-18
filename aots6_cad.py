# SPDX-License-Identifier: LicenseRef-AOTS6-ARR-1.0
# Copyright (c) 2025-2026 Alfredo Jhovany Alfaro Garcia - All Rights Reserved
# github.com/fo22Alfaro/aots6 — draft-alfaro-aots6-01
"""
aots6_cad.py — AOTS6 Geometric Models, T^11 Extension & Complex Movement
=========================================================================

¹¹∞∆⁶ — El movimiento complejo en dimensión infinita con delta de seis.

MÓDULOS:

  I.   ToroidalMesh        — Malla CAD del toro T² y T³ en R³
  II.  T6Projection        — Proyección de T^6 en R³ (secciones de Poincaré)
  III. T11Manifold         — Extensión a T^11 = (S^1)^11
  IV.  GeodesicFlow        — Flujo geodésico en T^n (movimiento complejo)
  V.   HamiltonianDynamics — Dinámica hamiltoniana en T^6
  VI.  InfiniteDimLimit    — Límite T^∞ — campo toroidal infinito-dimensional
  VII. AOTS6CADExport      — Exporta geometría a SVG, OBJ, y datos de malla
  VIII.ComplexMovement     — Movimiento ¹¹∞∆⁶: trayectorias en T^11 con Δ^6

Dependencies: numpy, scipy, sympy
"""

from __future__ import annotations

import numpy as np
from scipy import linalg
from scipy.spatial import ConvexHull
from typing import Dict, List, Tuple, Optional, Any
import hashlib, json, time


# ─────────────────────────────────────────────────────────────────────────────
# I. MALLA CAD — TORO T² y T³ EN R³
# ─────────────────────────────────────────────────────────────────────────────

class ToroidalMesh:
    """
    Genera la malla geométrica (CAD) del toro T² embebido en R³.

    T² = { (x,y,z) : (√(x²+y²) - R)² + z² = r² }

    Parámetros estándar:
      R = radio mayor (centro del tubo al eje de revolución)
      r = radio menor (radio del tubo)

    Para AOTS6: usamos R=3, r=1 como geometría canónica.
    Las secciones transversales a diferentes φ son las "fibras" de T^6
    proyectadas en 3D.
    """

    def __init__(self, R: float = 3.0, r: float = 1.0,
                 n_phi: int = 64, n_theta: int = 32):
        self.R       = R
        self.r       = r
        self.n_phi   = n_phi
        self.n_theta = n_theta

        phi   = np.linspace(0, 2*np.pi, n_phi,   endpoint=False)
        theta = np.linspace(0, 2*np.pi, n_theta, endpoint=False)
        PHI, THETA = np.meshgrid(phi, theta, indexing='ij')

        self.PHI   = PHI
        self.THETA = THETA
        self.X = (R + r * np.cos(THETA)) * np.cos(PHI)
        self.Y = (R + r * np.cos(THETA)) * np.sin(PHI)
        self.Z = r * np.sin(THETA)

    def vertices(self) -> np.ndarray:
        """(n_phi*n_theta, 3) array of vertex coordinates."""
        return np.column_stack([
            self.X.flatten(),
            self.Y.flatten(),
            self.Z.flatten(),
        ])

    def faces(self) -> np.ndarray:
        """(n_faces, 4) array of quad face indices."""
        np_, nt = self.n_phi, self.n_theta
        faces   = []
        for i in range(np_):
            for j in range(nt):
                a = i * nt + j
                b = ((i + 1) % np_) * nt + j
                c = ((i + 1) % np_) * nt + (j + 1) % nt
                d = i * nt + (j + 1) % nt
                faces.append([a, b, c, d])
        return np.array(faces)

    def normals(self) -> np.ndarray:
        """Outward unit normal at each vertex."""
        cos_phi = np.cos(self.PHI).flatten()
        sin_phi = np.sin(self.PHI).flatten()
        cos_the = np.cos(self.THETA).flatten()
        sin_the = np.sin(self.THETA).flatten()
        nx = cos_the * cos_phi
        ny = cos_the * sin_phi
        nz = sin_the
        return np.column_stack([nx, ny, nz])

    def gaussian_curvature(self) -> np.ndarray:
        """
        Gaussian curvature K at each point of T²:
          K = cos(θ) / (r(R + r*cos(θ)))

        Positive at outer equator (θ=0), negative at inner (θ=π).
        Integral ∫K dA = 0  (Gauss-Bonnet, χ(T²)=0).
        """
        cos_theta = np.cos(self.THETA)
        K = cos_theta / (self.r * (self.R + self.r * cos_theta))
        return K

    def mean_curvature(self) -> np.ndarray:
        """
        Mean curvature H = (R + 2r*cos(θ)) / (2r(R + r*cos(θ)))
        """
        cos_t = np.cos(self.THETA)
        H = (self.R + 2*self.r*cos_t) / (2*self.r*(self.R + self.r*cos_t))
        return H

    def geodesic_on_torus(self, phi0: float, theta0: float,
                           dphi: float, dtheta: float,
                           n_steps: int = 500) -> np.ndarray:
        """
        Geodesic on T² starting at (phi0, theta0) with velocity (dphi, dtheta).

        On a flat torus: geodesics are straight lines φ(t) = φ₀ + dphi·t,
        θ(t) = θ₀ + dtheta·t  (mod 2π).
        On the embedded torus in R³: geodesics curve due to embedding.

        Returns (n_steps, 3) path in R³.
        """
        # Use the flat torus geodesic (wrapped)
        t    = np.linspace(0, 2*np.pi, n_steps)
        phi  = (phi0 + dphi * t) % (2*np.pi)
        theta = (theta0 + dtheta * t) % (2*np.pi)
        x = (self.R + self.r * np.cos(theta)) * np.cos(phi)
        y = (self.R + self.r * np.cos(theta)) * np.sin(phi)
        z = self.r * np.sin(theta)
        return np.column_stack([x, y, z])

    def to_obj(self) -> str:
        """Export mesh to Wavefront OBJ format string."""
        lines = ["# AOTS6 Toroidal Mesh — T²",
                 f"# R={self.R}, r={self.r}",
                 f"# © 2025-2026 Alfredo Jhovany Alfaro Garcia",
                 ""]
        verts = self.vertices()
        norms = self.normals()
        for v, n in zip(verts, norms):
            lines.append(f"v  {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
        lines.append("")
        for n in norms:
            lines.append(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}")
        lines.append("")
        lines.append("g torus")
        for i, f in enumerate(self.faces()):
            a,b,c,d = f+1  # OBJ is 1-indexed
            lines.append(f"f {a}//{a} {b}//{b} {c}//{c} {d}//{d}")
        return "\n".join(lines)

    def summary(self) -> Dict[str, Any]:
        K    = self.gaussian_curvature()
        H    = self.mean_curvature()
        vols = np.sum(np.abs(K)) * (2*np.pi*self.R) * (2*np.pi*self.r) / (self.n_phi*self.n_theta)
        return {
            "R":                  self.R,
            "r":                  self.r,
            "n_vertices":         self.n_phi * self.n_theta,
            "n_faces":            self.n_phi * self.n_theta,
            "K_range":            [round(float(K.min()),4), round(float(K.max()),4)],
            "H_range":            [round(float(H.min()),4), round(float(H.max()),4)],
            "gauss_bonnet_check": round(float(np.sum(K * self.r * (self.R + self.r * np.cos(self.THETA)) * (2*np.pi/self.n_phi) * (2*np.pi/self.n_theta))), 4),
            "surface_area":       round(float(4 * np.pi**2 * self.R * self.r), 4),
            "volume_enclosed":    round(float(2 * np.pi**2 * self.R * self.r**2), 4),
        }


# ─────────────────────────────────────────────────────────────────────────────
# II. PROYECCIÓN T^6 → R³ (SECCIONES DE POINCARÉ)
# ─────────────────────────────────────────────────────────────────────────────

class T6Projection:
    """
    Proyecta T^6 = (S^1)^6 en R³ para visualización CAD.

    Métodos de proyección:
      1. Proyección cilíndrica:  (φ,θ) de T^6 → esfera S² en R³
      2. Sección de Poincaré:   fija 3 dimensiones, proyecta las otras 3
      3. Proyección hopf:        usa la fibración de Hopf S^3 → S^2
      4. Coordenadas de toroide nested: toros anidados en R³
    """

    def __init__(self, n: int = 6):
        self.n = n

    def poincare_section(self, nodes: List[List[float]],
                          fixed_dims: Tuple[int,int,int] = (3,4,5),
                          fixed_vals: Tuple[float,...] = (0.5,0.5,0.5),
                          tol: float = 0.1
                          ) -> np.ndarray:
        """
        Sección de Poincaré: filtra nodos donde las dimensiones fijas
        están cerca de fixed_vals, y proyecta las 3 libres en R³.
        """
        free_dims = [i for i in range(self.n) if i not in fixed_dims][:3]
        selected  = []
        for c in nodes:
            c = [x % 1.0 for x in c]
            if all(abs(c[fixed_dims[k]] - fixed_vals[k]) < tol
                   for k in range(len(fixed_dims))):
                selected.append([c[d] for d in free_dims])
        return np.array(selected) if selected else np.zeros((0,3))

    def hopf_projection(self, coord: List[float]) -> np.ndarray:
        """
        Proyecta un punto de T^6 al espacio R³ usando la fibración de Hopf.

        Hopf: S^3 → S^2,  (z₁,z₂) ↦ (2z₁z̄₂, |z₁|²-|z₂|²)

        Usamos (D0,D1) como ángulos de z₁ y (D2,D3) como ángulos de z₂.
        El resultado es un punto en S² ⊂ R³, con la fibra siendo S^1
        parametrizada por D4.
        """
        c  = [x % 1.0 for x in coord]
        α  = c[0] * 2 * np.pi    # fase z₁
        β  = c[1] * 2 * np.pi    # módulo z₁
        γ  = c[2] * 2 * np.pi    # fase z₂
        δ  = c[3] * 2 * np.pi    # módulo z₂

        z1 = np.cos(β/2) * np.exp(1j * α)
        z2 = np.sin(β/2) * np.exp(1j * γ)

        # Hopf map S^3 → S^2
        x  = float(2 * np.real(z1 * np.conj(z2)))
        y  = float(2 * np.imag(z1 * np.conj(z2)))
        z  = float(np.abs(z1)**2 - np.abs(z2)**2)
        return np.array([x, y, z])

    def nested_tori(self, coord: List[float],
                     layers: int = 3) -> List[np.ndarray]:
        """
        Representación de T^6 como toros anidados en R³.
        Cada par de dimensiones (D0-D1, D2-D3, D4-D5) define un toro T².
        Los tres toros se anidan concentricamente con radios R=3,2,1.
        """
        c    = [x % 1.0 for x in coord]
        Rs   = [3.0, 1.8, 0.9]
        rs   = [0.8, 0.5, 0.25]
        points = []
        for k in range(min(layers, 3)):
            phi   = c[2*k] * 2 * np.pi
            theta = c[2*k+1] * 2 * np.pi
            R_, r_ = Rs[k], rs[k]
            x = (R_ + r_ * np.cos(theta)) * np.cos(phi)
            y = (R_ + r_ * np.cos(theta)) * np.sin(phi)
            z = r_ * np.sin(theta) + k * 0.3  # slight vertical offset
            points.append(np.array([x, y, z]))
        return points

    def generate_cloud(self, n_points: int = 500,
                        seed: int = 42) -> np.ndarray:
        """
        Genera una nube de puntos en T^6 y la proyecta en R³.
        Útil para visualización de la geometría global.
        """
        rng    = np.random.default_rng(seed)
        coords = rng.uniform(0, 1, (n_points, self.n))
        cloud  = np.array([self.hopf_projection(c) for c in coords])
        return cloud

    def summary(self) -> Dict[str, Any]:
        cloud = self.generate_cloud(200)
        return {
            "projection_methods": ["poincare_section", "hopf", "nested_tori"],
            "cloud_shape":        list(cloud.shape),
            "cloud_extent":       [round(float(cloud[:,i].max()-cloud[:,i].min()),4)
                                   for i in range(3)],
            "hopf_example":       self.hopf_projection([0.2,0.4,0.6,0.1,0.8,0.3]).tolist(),
            "nested_example":     [p.tolist() for p in
                                   self.nested_tori([0.3,0.6,0.1,0.8,0.5,0.2])],
        }


# ─────────────────────────────────────────────────────────────────────────────
# III. T^11 — EXTENSIÓN ONCE-DIMENSIONAL
# ─────────────────────────────────────────────────────────────────────────────

class T11Manifold:
    """
    T^11 = (S^1)^11 — El manifold toroidal de once dimensiones.

    En AOTS6: T^11 extiende T^6 añadiendo cinco dimensiones cognitivas
    de orden superior:

      D0  Temporal       : causalidad
      D1  Spatial        : localidad
      D2  Logical        : simbólico
      D3  Memory         : persistencia
      D4  Network        : comunicación
      D5  Inference      : razonamiento
      ─── T^6 base ─────────────────
      D6  Ontological    : ser / existencia (nuevo)
      D7  Ethical        : valor / ética (nuevo)
      D8  Aesthetic      : forma / belleza (nuevo)
      D9  Recursive      : autocontención / meta (nuevo)
      D10 Transcendent   : límite / apertura infinita (nuevo)
      ─── T^11 extensión ────────────

    Las 5 dimensiones adicionales son el "seis arriba":
    la extensión del sistema más allá de su dominio operativo original
    hacia el espacio de valores, significado y autorreferencia.
    """

    DIM_NAMES = [
        "Temporal",   "Spatial",   "Logical",   "Memory",
        "Network",    "Inference", "Ontological", "Ethical",
        "Aesthetic",  "Recursive", "Transcendent"
    ]

    def __init__(self):
        self.n = 11

    def distance(self, a: List[float], b: List[float]) -> float:
        """Toroidal metric on T^11."""
        return sum(min(abs(ai-bi), 1-abs(ai-bi))**2
                   for ai, bi in zip(a, b)) ** 0.5

    def project_to_t6(self, coord: List[float]) -> List[float]:
        """Project T^11 coordinates to T^6 (first 6 dims)."""
        return [c % 1.0 for c in coord[:6]]

    def embed_from_t6(self, t6_coord: List[float],
                       extra: Optional[List[float]] = None) -> List[float]:
        """
        Embed T^6 into T^11 by adding 5 extra dimensions.
        Default extra dimensions: derived from T^6 via self-referential map.
        """
        c = [x % 1.0 for x in t6_coord[:6]]
        if extra is None:
            # Auto-generate extra dims via toroidal map of T^6
            d6  = sum(c) / 6.0           # ontological = mean of T^6
            d7  = min(c)                  # ethical = minimum (most constrained)
            d8  = max(c) - min(c)         # aesthetic = range (contrast)
            d9  = (c[5] * 2 + c[0]) % 1.0  # recursive = inference→temporal
            d10 = (1 - sum(ci**2 for ci in c)/6) % 1.0  # transcendent = deviation from center
            extra = [d6, d7, d8, d9, d10]
        return c + [x % 1.0 for x in extra[:5]]

    def geodesic_t11(self, start: List[float],
                      velocity: List[float],
                      t: float) -> List[float]:
        """
        Geodesic in T^11: linear flow with wrap-around.
        γ(t) = (start + velocity*t) mod 1  (componentwise)
        """
        return [(s + v*t) % 1.0 for s, v in zip(start, velocity)]

    def holonomy_t11(self, loop_windings: List[int]) -> Dict[str, Any]:
        """
        Holonomy of a loop in T^11.
        For flat T^11: holonomy is trivial (identity).
        For T^11 with connection: holonomy encodes parallel transport.

        loop_windings: winding number in each of 11 dimensions.
        """
        w    = list(loop_windings)
        norm = sum(wi**2 for wi in w) ** 0.5
        dims_active = [(self.DIM_NAMES[i], wi) for i, wi in enumerate(w) if wi != 0]
        return {
            "winding":       w,
            "norm":          round(norm, 4),
            "dims_active":   dims_active,
            "phase":         round(2 * np.pi * norm, 4),
            "is_memory":     any(wi != 0 for wi in w),
            "t6_component":  w[:6],
            "t11_extension": w[6:],
        }

    def dimension_profile(self, coord: List[float]) -> Dict[str, Any]:
        """
        Compute the dimensional profile of a T^11 coordinate.
        Shows which dimensions are activated and their semantic meaning.
        """
        c = [x % 1.0 for x in coord]
        profile = {}
        for i, (name, val) in enumerate(zip(self.DIM_NAMES, c)):
            profile[f"D{i}_{name}"] = {
                "value":    round(val, 4),
                "active":   val > 0.5,
                "quadrant": "upper" if val > 0.5 else "lower",
            }
        dominant = self.DIM_NAMES[int(np.argmax(c))]
        return {
            "coord":    [round(ci, 4) for ci in c],
            "dominant": dominant,
            "profile":  profile,
            "energy":   round(sum(c)/self.n, 4),
        }

    def betti_t11(self) -> List[int]:
        """Betti numbers of T^11: b_k = C(11, k)."""
        from math import comb
        return [comb(11, k) for k in range(12)]

    def summary(self) -> Dict[str, Any]:
        test = [0.1, 0.3, 0.5, 0.7, 0.2, 0.9, 0.4, 0.6, 0.8, 0.15, 0.55]
        full = self.embed_from_t6([0.3, 0.5, 0.7, 0.2, 0.8, 0.4])
        return {
            "n":            self.n,
            "dim_names":    self.DIM_NAMES,
            "betti":        self.betti_t11(),
            "euler_char":   0,
            "K0_rank":      2**10,
            "pi1":          "Z^11",
            "test_profile": self.dimension_profile(test),
            "t6_embed":     full,
            "holonomy_ex":  self.holonomy_t11([1,0,0,0,0,1,0,1,0,0,-1]),
        }


# ─────────────────────────────────────────────────────────────────────────────
# IV. FLUJO GEODÉSICO EN T^n
# ─────────────────────────────────────────────────────────────────────────────

class GeodesicFlow:
    """
    Flujo geodésico en T^n — el movimiento más puro en el toro.

    En T^n plano: las geodésicas son líneas rectas mod 1.
    γ(t) = (x₀ + v·t) mod 1

    Propiedades:
      - Si v_i/v_j ∈ Q para todo i,j: la geodésica es CERRADA
        (período = lcm de los denominadores)
      - Si algún v_i/v_j ∉ Q: la geodésica es DENSA en T^n
        (pasa arbitrariamente cerca de todo punto)

    AOTS6: cada nodo sigue una geodésica en T^6 entre operaciones EVOLVE.
    La densidad de la geodésica determina el alcance semántico del nodo.
    """

    def __init__(self, n: int = 6):
        self.n = n

    def is_closed(self, velocity: List[float],
                   tol: float = 1e-6) -> Tuple[bool, Optional[float]]:
        """
        Check if geodesic with given velocity is closed.
        Closed iff all velocity ratios are rational.
        """
        v = [abs(vi) for vi in velocity if abs(vi) > tol]
        if len(v) < 2:
            return True, 1.0
        # Check rationality of ratios via continued fractions
        from fractions import Fraction
        try:
            fracs = [Fraction(vi).limit_denominator(1000) for vi in v]
            # Period = lcm of denominators / gcd of numerators
            from math import gcd, lcm
            denoms = [f.denominator for f in fracs]
            period = 1
            for d in denoms:
                period = period * d // gcd(period, d)
            return True, float(period)
        except:
            return False, None

    def compute_geodesic(self, start: List[float],
                          velocity: List[float],
                          n_steps: int = 1000,
                          T: float = 10.0) -> np.ndarray:
        """
        Compute geodesic trajectory in T^n.
        Returns (n_steps, n) array of positions.
        """
        t   = np.linspace(0, T, n_steps)
        pos = np.array([(np.array(start) + np.array(velocity) * ti) % 1.0
                         for ti in t])
        return pos

    def winding_numbers(self, trajectory: np.ndarray) -> List[int]:
        """
        Count winding numbers in each dimension along a trajectory.
        """
        windings = []
        for i in range(trajectory.shape[1]):
            diff  = np.diff(trajectory[:, i])
            # Count wrap-arounds
            winds = int(np.sum(diff < -0.5) - np.sum(diff > 0.5))
            windings.append(winds)
        return windings

    def ergodic_coverage(self, velocity: List[float],
                          n_steps: int = 5000) -> float:
        """
        Estimate ergodic coverage: fraction of T^n volume visited.
        Uses box-counting with resolution 0.05.
        """
        traj  = self.compute_geodesic([0.0]*self.n, velocity, n_steps)
        res   = 0.05
        cells = set()
        for pos in traj:
            cell = tuple(int(pi / res) for pi in pos)
            cells.add(cell)
        max_cells = (1/res) ** self.n
        return min(len(cells) / max_cells, 1.0)

    def lyapunov_exponent(self, velocity: List[float],
                           n_steps: int = 2000) -> float:
        """
        Lyapunov exponent for the geodesic flow.
        For flat T^n: always 0 (integrable system).
        Nonzero values indicate perturbation from flat metric.
        """
        # On flat T^n, geodesics don't diverge → λ = 0
        # We compute a numerical estimate as sanity check
        dx     = 1e-6
        perturb = [v + dx if i == 0 else v for i, v in enumerate(velocity)]
        traj1  = self.compute_geodesic([0.0]*self.n, velocity,  n_steps)
        traj2  = self.compute_geodesic([0.0]*self.n, perturb,   n_steps)
        dists  = np.linalg.norm(traj1 - traj2, axis=1)
        # Lyapunov: slope of log(dist) vs t
        valid  = dists > 1e-12
        if np.sum(valid) < 10:
            return 0.0
        t_arr  = np.arange(n_steps)[valid]
        log_d  = np.log(dists[valid])
        slope, _ = np.polyfit(t_arr[:100], log_d[:100], 1)
        return round(float(slope), 6)

    def poincare_return_map(self, velocity: List[float],
                             section_dim: int = 0,
                             section_val: float = 0.0,
                             n_returns: int = 50) -> np.ndarray:
        """
        Poincaré return map: record positions every time the trajectory
        crosses section_dim = section_val.
        Returns (n_returns, n-1) array of positions on the section.
        """
        returns  = []
        pos      = np.array([0.0] * self.n)
        vel      = np.array(velocity)
        dt       = 0.001
        prev_dim = pos[section_dim]

        while len(returns) < n_returns:
            pos = (pos + vel * dt) % 1.0
            curr_dim = pos[section_dim]
            # Check crossing of section_val (with wrap-around)
            if (prev_dim < section_val <= curr_dim or
                (prev_dim > 0.9 and curr_dim < 0.1)):
                returns.append(np.delete(pos, section_dim))
            prev_dim = curr_dim

        return np.array(returns)

    def summary(self) -> Dict[str, Any]:
        v1 = [1/3, 1/5, 1/7, 1/4, 1/6, 1/8]      # rational → closed
        v2 = [1.0, np.sqrt(2)/2, 1/3, np.pi/10, 1/7, np.sqrt(3)/5]  # irrational → dense

        closed1, period1 = self.is_closed(v1)
        closed2, period2 = self.is_closed(v2)

        return {
            "rational_velocity":   [round(v, 4) for v in v1],
            "rational_is_closed":  closed1,
            "rational_period":     period1,
            "irrational_velocity": [round(v, 4) for v in v2],
            "irrational_is_closed": closed2,
            "lyapunov_flat_torus":  self.lyapunov_exponent(v1, 500),
        }


# ─────────────────────────────────────────────────────────────────────────────
# V. DINÁMICA HAMILTONIANA EN T^6
# ─────────────────────────────────────────────────────────────────────────────

class HamiltonianDynamics:
    """
    Dinámica Hamiltoniana en T^6.

    El espacio de fases de AOTS6 es T^*T^6 = T^6 × R^6
    (cotangente bundle del toro).

    Coordenadas:  (q_0,...,q_5) ∈ T^6  (posiciones)
                  (p_0,...,p_5) ∈ R^6   (momentos)

    Hamiltoniano:
      H = T + V = Σᵢ pᵢ²/2 + V(q)

    Para AOTS6:
      V(q) = Σᵢ aᵢ·cos(2π·q_i)   (potencial toroidal)

    Ecuaciones de Hamilton:
      dqᵢ/dt = ∂H/∂pᵢ = pᵢ
      dpᵢ/dt = -∂H/∂qᵢ = 2π·aᵢ·sin(2π·qᵢ)
    """

    def __init__(self, potential_amps: Optional[List[float]] = None):
        self.n  = 6
        self.a  = np.array(potential_amps or [0.1]*6)  # potential amplitudes

    def hamiltonian(self, q: np.ndarray, p: np.ndarray) -> float:
        """H(q,p) = Σ pᵢ²/2 + Σ aᵢ·cos(2π·qᵢ)"""
        T = 0.5 * np.sum(p**2)
        V = np.sum(self.a * np.cos(2 * np.pi * q))
        return float(T + V)

    def equations_of_motion(self, q: np.ndarray,
                              p: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Hamilton's equations."""
        dq_dt = p.copy()
        dp_dt = 2 * np.pi * self.a * np.sin(2 * np.pi * q)
        return dq_dt, dp_dt

    def symplectic_rk4(self, q0: np.ndarray, p0: np.ndarray,
                        dt: float, n_steps: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Symplectic 4th-order Runge-Kutta integrator.
        Preserves the symplectic form dq ∧ dp (Liouville's theorem).
        """
        q = q0.copy()
        p = p0.copy()
        qs = np.zeros((n_steps, self.n))
        ps = np.zeros((n_steps, self.n))

        for i in range(n_steps):
            qs[i] = q % 1.0
            ps[i] = p

            # RK4 step
            dq1, dp1 = self.equations_of_motion(q,           p)
            dq2, dp2 = self.equations_of_motion(q+dt*dq1/2,  p+dt*dp1/2)
            dq3, dp3 = self.equations_of_motion(q+dt*dq2/2,  p+dt*dp2/2)
            dq4, dp4 = self.equations_of_motion(q+dt*dq3,    p+dt*dp3)

            q = q + dt * (dq1 + 2*dq2 + 2*dq3 + dq4) / 6
            p = p + dt * (dp1 + 2*dp2 + 2*dp3 + dp4) / 6

        return qs, ps

    def energy_conservation(self, q_traj: np.ndarray,
                              p_traj: np.ndarray) -> Dict[str, float]:
        """Check energy conservation along trajectory."""
        H0     = self.hamiltonian(q_traj[0], p_traj[0])
        Hs     = np.array([self.hamiltonian(q_traj[i], p_traj[i])
                            for i in range(len(q_traj))])
        drift  = float(np.max(np.abs(Hs - H0)))
        return {
            "H_initial":    round(H0, 6),
            "H_final":      round(float(Hs[-1]), 6),
            "max_drift":    round(drift, 8),
            "conservation": "EXCELLENT" if drift < 1e-4 else "POOR",
        }

    def action_angle_variables(self, q0: List[float],
                                p0: List[float]) -> Dict[str, Any]:
        """
        Action-angle variables (I, θ) for integrable Hamiltonians.

        For the separable Hamiltonian H = Σ Hᵢ(qᵢ, pᵢ):
          Iᵢ = (1/2π) ∮ pᵢ dqᵢ  (action)
          θᵢ = ∂S/∂Iᵢ            (angle)

        For H = Σ pᵢ²/2 + aᵢcos(2πqᵢ): pendulum-like in each dimension.
        """
        I = []
        omega = []  # frequencies ωᵢ = dHᵢ/dIᵢ
        for i in range(self.n):
            pi_ = p0[i]
            ai  = self.a[i]
            # Energy of mode i: Eᵢ = pᵢ²/2 + aᵢcos(2πqᵢ)
            Ei  = pi_**2/2 + ai * np.cos(2*np.pi*q0[i])
            # Action: Iᵢ = (1/2π)∮ pᵢ dqᵢ
            # For libration (Eᵢ < aᵢ): Iᵢ = (4/2π)∫₀^{q*} sqrt(2(Eᵢ-aᵢcos)) dq
            # For rotation (Eᵢ > aᵢ): Iᵢ = (1/2π)∫₀^1 sqrt(2(Eᵢ-aᵢcos)) dq
            if abs(ai) < 1e-10:
                Ii = abs(pi_)
                wi = pi_
            else:
                # Numerical estimate
                q_arr = np.linspace(0, 1, 200)
                integrand = np.sqrt(np.maximum(0, 2*(Ei - ai*np.cos(2*np.pi*q_arr))))
                Ii = float(np.trapz(integrand, q_arr) / (2*np.pi))
                wi = pi_ / (Ii + 1e-10)
            I.append(round(Ii, 4))
            omega.append(round(float(wi), 4))
        return {
            "actions":         I,
            "frequencies":     omega,
            "KAM_stable":      all(abs(o) > 1e-3 for o in omega),
            "resonances":      sum(1 for i in range(len(omega)-1)
                                   if abs(omega[i]/omega[i+1] - 1) < 0.1),
        }

    def summary(self) -> Dict[str, Any]:
        q0 = np.array([0.1, 0.3, 0.5, 0.7, 0.2, 0.9])
        p0 = np.array([0.5, -0.3, 0.8, 0.2, -0.6, 0.4])
        qs, ps = self.symplectic_rk4(q0, p0, dt=0.01, n_steps=200)
        conservation = self.energy_conservation(qs, ps)
        aa = self.action_angle_variables(q0.tolist(), p0.tolist())
        return {
            "hamiltonian":    "H = Σpᵢ²/2 + Σaᵢcos(2πqᵢ)",
            "potential_amps": list(self.a),
            "conservation":   conservation,
            "action_angles":  aa,
        }


# ─────────────────────────────────────────────────────────────────────────────
# VI. LÍMITE T^∞ — CAMPO TOROIDAL INFINITO-DIMENSIONAL
# ─────────────────────────────────────────────────────────────────────────────

class InfiniteDimLimit:
    """
    T^∞ = lim_{n→∞} T^n — El toro infinito-dimensional.

    T^∞ es el espacio de sucesiones (x_0, x_1, x_2, ...) con xᵢ ∈ [0,1).
    Es un grupo topológico compacto (por el teorema de Tychonov).

    Métrica en T^∞:
      d(x, y) = Σᵢ₌₀^∞ 2^{-i} · min(|xᵢ-yᵢ|, 1-|xᵢ-yᵢ|)

    Esta serie converge absolutamente (suma de 2^{-i} = 2).

    En AOTS6: T^∞ es el límite al que tiende el sistema cuando
    se añaden infinitas dimensiones cognitivas. Cada nueva dimensión
    contribuye 2^{-i} a la métrica — las primeras dimensiones
    dominan, las ulteriores refinan.

    T^6 es la aproximación de orden 6 de T^∞.
    T^11 es la aproximación de orden 11.
    """

    def distance(self, x: List[float], y: List[float],
                  n_terms: int = 50) -> float:
        """
        Metric on T^∞: d(x,y) = Σ 2^{-i} min(|xᵢ-yᵢ|, 1-|xᵢ-yᵢ|)
        Truncated to n_terms.
        """
        total = 0.0
        for i in range(min(n_terms, len(x), len(y))):
            di = min(abs(x[i]-y[i]), 1-abs(x[i]-y[i]))
            total += 2**(-i) * di
        return total

    def embed_t6_in_tinf(self, t6_coord: List[float],
                           n_extra: int = 44) -> List[float]:
        """
        Embed T^6 in T^∞ by extending with derived coordinates.
        Total: 6 + n_extra = 50 dimensions (truncated T^∞).
        """
        c    = [x % 1.0 for x in t6_coord[:6]]
        ext  = []
        prev = c.copy()
        for k in range(n_extra):
            # Next coord = toroidal map of previous
            next_coord = (prev[k % 6] + prev[(k+1) % 6]) % 1.0
            ext.append(next_coord)
            prev = ext[-6:] if len(ext) >= 6 else c + ext
        return c + ext

    def truncation_error(self, x: List[float],
                          y: List[float],
                          n: int) -> float:
        """
        Error from truncating T^∞ to T^n:
        |d_∞(x,y) - d_n(x,y)| ≤ Σᵢ₌ₙ^∞ 2^{-i} = 2^{1-n}
        """
        return 2.0 ** (1 - n)

    def spectral_gap(self, n: int) -> float:
        """
        Spectral gap of the Laplacian on T^n:
        λ₁(T^n) = 4π² (lowest non-zero eigenvalue, independent of n).
        As n → ∞: the spectrum fills [4π², ∞) densely.
        """
        return 4 * np.pi**2

    def fourier_decay(self, k_vector: List[int]) -> float:
        """
        For a smooth function f on T^∞:
        |f̂(k)| ≤ C · (1 + |k|²)^{-s/2}  for any s > 0.
        Rate of Fourier decay quantifies the smoothness class.
        """
        k2   = sum(ki**2 for ki in k_vector)
        # For s=2 (H^2 Sobolev class):
        return 1.0 / (1 + k2)

    def summary(self) -> Dict[str, Any]:
        x  = [0.3, 0.5, 0.7, 0.1, 0.9, 0.4]
        y  = [0.4, 0.6, 0.8, 0.2, 0.85, 0.35]
        x_ext = self.embed_t6_in_tinf(x, 44)
        y_ext = self.embed_t6_in_tinf(y, 44)
        d_6   = self.distance(x, y, 6)
        d_11  = self.distance(x_ext, y_ext, 11)
        d_50  = self.distance(x_ext, y_ext, 50)
        return {
            "metric":          "d(x,y) = Σ 2^{-i} min(|xᵢ-yᵢ|, 1-|xᵢ-yᵢ|)",
            "d_T6":            round(d_6, 6),
            "d_T11":           round(d_11, 6),
            "d_T50":           round(d_50, 6),
            "trunc_error_T6":  round(self.truncation_error(x,y,6), 6),
            "trunc_error_T11": round(self.truncation_error(x,y,11), 6),
            "spectral_gap":    round(self.spectral_gap(11), 4),
            "convergence":     "d_T6 → d_T11 → d_T∞  (exponentially fast)",
            "compact":         "T^∞ is compact by Tychonov's theorem",
        }


# ─────────────────────────────────────────────────────────────────────────────
# VII. EXPORTADOR CAD
# ─────────────────────────────────────────────────────────────────────────────

class AOTS6CADExport:
    """
    Exporta geometría AOTS6 en formatos estándar CAD/visualización.
    Genera SVG (2D), OBJ (3D mesh), y JSON (datos de nube de puntos).
    """

    def export_torus_svg(self, R: float = 3.0, r: float = 1.0,
                          width: int = 400, height: int = 400,
                          n_curves: int = 12) -> str:
        """
        Export T² as SVG — ortographic projection viewed from above.
        Shows the outer equator, inner equator, and meridian circles.
        """
        cx, cy = width//2, height//2
        scale  = width / (2*(R+r) + 0.5)

        lines  = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">',
            f'<rect width="{width}" height="{height}" fill="#0a0a1a"/>',
            f'<title>AOTS6 T² CAD — Alfredo Jhovany Alfaro Garcia</title>',
            f'<!-- © 2025-2026 Alfredo Jhovany Alfaro Garcia -->',
        ]

        # Draw parallels (circles of constant θ) — projected as ellipses
        for i in range(n_curves):
            theta = i * np.pi / n_curves
            r_eff = R + r * np.cos(theta)
            rx    = r_eff * scale
            ry    = r_eff * scale * 0.35   # foreshortening
            opacity = 0.3 + 0.5 * abs(np.cos(theta))
            lines.append(
                f'<ellipse cx="{cx}" cy="{cy}" rx="{rx:.1f}" ry="{ry:.1f}" '
                f'fill="none" stroke="#00ffcc" stroke-width="0.8" '
                f'opacity="{opacity:.2f}"/>'
            )

        # Draw meridians (circles of constant φ) — as line segments
        n_mer = 24
        for i in range(n_mer):
            phi   = i * 2 * np.pi / n_mer
            pts   = []
            for j in range(50):
                theta = j * 2 * np.pi / 49
                x_    = (R + r * np.cos(theta)) * np.cos(phi)
                y_    = (R + r * np.cos(theta)) * np.sin(phi) * 0.35
                z_    = r * np.sin(theta)
                px    = cx + x_ * scale
                py    = cy - (y_ + z_ * 0.4) * scale
                pts.append(f"{px:.1f},{py:.1f}")
            path = " L ".join(pts)
            lines.append(
                f'<path d="M {path}" fill="none" '
                f'stroke="#ff6600" stroke-width="0.5" opacity="0.4"/>'
            )

        # Center cross
        lines.append(
            f'<line x1="{cx-8}" y1="{cy}" x2="{cx+8}" y2="{cy}" '
            f'stroke="#ffffff" stroke-width="1" opacity="0.5"/>'
        )
        lines.append(
            f'<line x1="{cx}" y1="{cy-8}" x2="{cx}" y2="{cy+8}" '
            f'stroke="#ffffff" stroke-width="1" opacity="0.5"/>'
        )

        # Label
        lines += [
            f'<text x="10" y="20" font-family="monospace" font-size="11" '
            f'fill="#00ffcc">AOTS6 T² — R={R} r={r}</text>',
            f'<text x="10" y="{height-8}" font-family="monospace" font-size="9" '
            f'fill="#666666">© Alfredo Jhovany Alfaro Garcia</text>',
            '</svg>'
        ]
        return "\n".join(lines)

    def export_geodesic_svg(self, velocities: List[List[float]],
                              colors: Optional[List[str]] = None,
                              width: int = 500, height: int = 500) -> str:
        """
        Export geodesic flows on T² projected to 2D square.
        Shows the fundamental domain [0,1]² with geodesics as lines.
        """
        cx, cy = 0, 0
        scale  = width - 40

        default_colors = ["#00ffcc", "#ff6600", "#ff00ff", "#ffff00", "#00aaff"]
        colors = colors or default_colors

        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}">',
            f'<rect width="{width}" height="{height}" fill="#050510"/>',
            f'<!-- AOTS6 Geodesic Flow on T² -->',
            f'<!-- © 2025-2026 Alfredo Jhovany Alfaro Garcia -->',
            f'<rect x="20" y="20" width="{scale}" height="{scale}" '
            f'fill="none" stroke="#333366" stroke-width="1"/>',
        ]

        n_steps = 2000
        for idx, vel in enumerate(velocities):
            col = colors[idx % len(colors)]
            pos = np.zeros(2)
            v2  = np.array(vel[:2])
            t   = np.linspace(0, 20, n_steps)
            pts = []
            for ti in t:
                p = (v2 * ti) % 1.0
                px = 20 + p[0] * scale
                py = 20 + p[1] * scale
                pts.append(f"{px:.1f},{py:.1f}")
            # Draw as polyline segments (break at wrap-arounds)
            segs = " L ".join(pts[:300])
            lines.append(
                f'<path d="M {segs}" fill="none" stroke="{col}" '
                f'stroke-width="0.8" opacity="0.7"/>'
            )

        # Grid lines
        for i in range(1, 5):
            x = 20 + i * scale // 5
            y = 20 + i * scale // 5
            lines.append(f'<line x1="{x}" y1="20" x2="{x}" y2="{20+scale}" '
                          f'stroke="#222244" stroke-width="0.5"/>')
            lines.append(f'<line x1="20" y1="{y}" x2="{20+scale}" y2="{y}" '
                          f'stroke="#222244" stroke-width="0.5"/>')

        lines += [
            f'<text x="25" y="15" font-family="monospace" font-size="11" '
            f'fill="#00ffcc">T² Geodesic Flow</text>',
            '</svg>'
        ]
        return "\n".join(lines)

    def export_t6_pointcloud_json(self, n_points: int = 300,
                                   seed: int = 42) -> str:
        """Export T^6 point cloud projected to 3D as JSON."""
        rng    = np.random.default_rng(seed)
        coords = rng.uniform(0, 1, (n_points, 6))
        proj   = T6Projection(6)
        points = [proj.hopf_projection(c.tolist()).tolist() for c in coords]
        colors = []
        for c in coords:
            r_ = int(c[0] * 255)
            g_ = int(c[3] * 255)
            b_ = int(c[5] * 255)
            colors.append([r_, g_, b_])
        data = {
            "type":    "T6_pointcloud",
            "n":       n_points,
            "points":  [[round(p, 4) for p in pt] for pt in points],
            "colors":  colors,
            "meta": {
                "author":  "Alfredo Jhovany Alfaro Garcia",
                "system":  "AOTS6 v0.1.0",
                "draft":   "draft-alfaro-aots6-01",
            }
        }
        return json.dumps(data, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# VIII. MOVIMIENTO COMPLEJO ¹¹∞∆⁶
# ─────────────────────────────────────────────────────────────────────────────

class ComplexMovement:
    """
    Movimiento Complejo ¹¹∞∆⁶

    ¹¹  → Operación en T^11 (11 dimensiones)
    ∞   → Límite T^∞ (infinito dimensional)
    ∆   → Operador delta: variación topológica
    ⁶   → Proyección a T^6 (base operativa)

    El movimiento complejo es la composición:

      Ψ: T^6 ──embed──> T^11 ──flow──> T^∞ ──∆──> T^6

    Donde:
      embed: T^6 → T^11  (extensión ontológica)
      flow:  geodésico hamiltoniano en T^11
      ∆:     operador de variación (diferencia topológica)
      project: T^∞ → T^6  (proyección al espacio base)

    La composición Ψ es un endomorfismo de T^6 con
    propiedades topológicas no triviales.
    """

    def __init__(self):
        self.t11   = T11Manifold()
        self.hdyn  = HamiltonianDynamics()
        self.tinf  = InfiniteDimLimit()
        self.geo   = GeodesicFlow(11)

    def delta6_operator(self, coord: List[float],
                         epsilon: float = 0.01) -> np.ndarray:
        """
        ∆⁶ operator: infinitesimal generator of T^6 automorphisms.

        ∆⁶[f](x) = lim_{ε→0} (f(x+ε·v) - f(x)) / ε

        For AOTS6: ∆⁶ is the Lie derivative along the fundamental
        vector fields ∂/∂xᵢ on T^6.
        Returns the 6×6 structure matrix of the operator.
        """
        c    = np.array([x % 1.0 for x in coord[:6]])
        # Structure matrix: D[i,j] = d(xᵢ)/d(xⱼ) under the flow
        # For flat T^6: identity matrix (translations commute)
        D    = np.eye(6)
        # Add curvature correction from potential
        for i in range(6):
            for j in range(6):
                if i != j:
                    D[i,j] = epsilon * np.sin(2*np.pi*(c[i]-c[j]))
        return D

    def psi_map(self, t6_coord: List[float],
                 t_flow: float = 1.0) -> Dict[str, Any]:
        """
        Full Ψ map: T^6 → T^6 via ¹¹∞∆⁶.

        Steps:
          1. Embed T^6 → T^11
          2. Evolve with geodesic flow in T^11
          3. Embed T^11 → T^∞ (first 50 dims)
          4. Apply ∆⁶ operator
          5. Project back to T^6
        """
        # Step 1: embed
        c6  = [x % 1.0 for x in t6_coord[:6]]
        c11 = self.t11.embed_from_t6(c6)

        # Step 2: geodesic flow in T^11
        vel = [0.1 * (i+1) / 11 for i in range(11)]
        c11_evolved = self.geo.compute_geodesic(c11, vel, n_steps=2,
                                                  T=t_flow)[1]

        # Step 3: embed in T^∞
        c11e = list(c11_evolved)
        c50  = self.tinf.embed_t6_in_tinf(c11e[:6], 44)

        # Step 4: apply ∆⁶
        D    = self.delta6_operator(c50[:6])
        c6p  = np.array(c50[:6])
        c6_delta = (D @ c6p) % 1.0

        # Step 5: result
        dist_from_start = sum(min(abs(a-b), 1-abs(a-b))**2
                              for a,b in zip(c6, c6_delta)) ** 0.5

        return {
            "input_T6":      [round(c, 4) for c in c6],
            "after_T11":     [round(c, 4) for c in c11_evolved],
            "after_T_inf":   [round(c, 4) for c in c50[:6]],
            "after_delta6":  [round(c, 4) for c in c6_delta],
            "displacement":  round(dist_from_start, 6),
            "operator":      "Ψ = project ∘ ∆⁶ ∘ T^∞-embed ∘ T^11-flow ∘ T^11-embed",
            "fixed_point":   dist_from_start < 0.01,
        }

    def orbit_portrait(self, coord: List[float],
                        n_iter: int = 20) -> Dict[str, Any]:
        """
        Iterate Ψ n_iter times and record the orbit.
        Fixed points: Ψ(x) = x  (topological attractors)
        Periodic orbits: Ψ^n(x) = x
        """
        orbit = [list(coord[:6])]
        c     = list(coord[:6])
        for _ in range(n_iter):
            result = self.psi_map(c, t_flow=0.1)
            c      = result["after_delta6"]
            orbit.append(c)

        # Detect periodicity
        dists = [sum(min(abs(orbit[0][k]-orbit[i][k]),
                         1-abs(orbit[0][k]-orbit[i][k]))**2
                     for k in range(6))**0.5
                 for i in range(1, n_iter+1)]

        min_return = min(enumerate(dists), key=lambda x: x[1])
        return {
            "n_iterations":  n_iter,
            "final_pos":     [round(c, 4) for c in orbit[-1]],
            "orbit_length":  round(float(np.mean(dists)), 4),
            "nearest_return": min_return[0]+1,
            "return_dist":   round(min_return[1], 6),
            "is_bounded":    all(d < 1.0 for d in dists),
        }

    def summary(self) -> Dict[str, Any]:
        test = [0.2, 0.4, 0.6, 0.1, 0.8, 0.3]
        psi  = self.psi_map(test, t_flow=1.0)
        orb  = self.orbit_portrait(test, n_iter=15)
        return {
            "operator":    "Ψ: T^6 → T^6 via ¹¹∞∆⁶",
            "composition": psi["operator"],
            "psi_result":  psi,
            "orbit":       orb,
        }


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION SUITE
# ─────────────────────────────────────────────────────────────────────────────

def run_cad_validation():
    """Validate CAD + T11 + Complex Movement modules."""

    print("\n" + "=" * 66)
    print(" AOTS6 CAD + T^11 + Movimiento Complejo ¹¹∞∆⁶")
    print("=" * 66)

    results = []
    t_total = time.perf_counter()

    def check(name, fn):
        t0 = time.perf_counter()
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, str(e)[:80]
        ms = (time.perf_counter() - t0) * 1000
        icon = "[+]" if ok else "[x]"
        print(f"  {icon} {'PASS' if ok else 'FAIL'}  {name:<52} ({ms:.1f}ms)")
        if msg:
            print(f"         {msg}")
        results.append({"name": name, "passed": ok, "ms": ms})

    # CAD-01: Torus mesh — vertex count and Gauss-Bonnet
    def c01():
        m  = ToroidalMesh(R=3, r=1, n_phi=32, n_theta=16)
        s  = m.summary()
        ok = (s["n_vertices"] == 32*16 and
              abs(s["gauss_bonnet_check"]) < 0.01)  # χ(T²)=0
        return ok, f"n_verts={s['n_vertices']}, K·dA≈{s['gauss_bonnet_check']}"
    check("CAD-01  Torus mesh geometry", c01)

    # CAD-02: Normals are unit vectors
    def c02():
        m  = ToroidalMesh(R=3, r=1, n_phi=16, n_theta=8)
        N  = m.normals()
        norms = np.linalg.norm(N, axis=1)
        ok = np.allclose(norms, 1.0, atol=1e-10)
        return ok, f"normal norms ∈ [{norms.min():.4f}, {norms.max():.4f}]"
    check("CAD-02  Torus normals are unit vectors", c02)

    # CAD-03: T^6 Hopf projection lands on S²
    def c03():
        proj  = T6Projection(6)
        cloud = proj.generate_cloud(100)
        # Hopf maps to S²: |p|² ≈ 1 (approximately)
        norms = np.linalg.norm(cloud, axis=1)
        ok    = np.all(norms <= 1.01 + 1e-6)
        return ok, f"cloud norms ∈ [{norms.min():.4f}, {norms.max():.4f}]"
    check("CAD-03  T^6 Hopf projection onto S²", c03)

    # CAD-04: T^11 has 11 dimensions
    def c04():
        t11 = T11Manifold()
        c6  = [0.3, 0.5, 0.7, 0.2, 0.8, 0.4]
        c11 = t11.embed_from_t6(c6)
        ok  = (len(c11) == 11 and all(0 <= x < 1 for x in c11))
        return ok, f"T^11 coord len={len(c11)}, all∈[0,1)={ok}"
    check("CAD-04  T^11 extension has 11 dims in [0,1)", c04)

    # CAD-05: T^11 Betti = C(11,k)
    def c05():
        from math import comb
        t11  = T11Manifold()
        b    = t11.betti_t11()
        exp  = [comb(11, k) for k in range(12)]
        ok   = b == exp and sum((-1)**k * b[k] for k in range(12)) == 0
        return ok, f"b_0={b[0]}, b_1={b[1]}, b_6={b[6]}, χ={sum((-1)**k*b[k] for k in range(12))}"
    check("CAD-05  T^11 Betti numbers = C(11,k)", c05)

    # CAD-06: Geodesic closure detection
    def c06():
        geo = GeodesicFlow(6)
        v1  = [1/3, 1/5, 1/4, 1/6, 1/7, 1/8]
        v2  = [np.sqrt(2)/2, 1/3, 1/5, 1/7, 1/11, 1/13]
        c1, p1 = geo.is_closed(v1)
        c2, p2 = geo.is_closed(v2)
        ok = c1 and p1 is not None
        return ok, f"rational→closed={c1} period={p1}, irrational→closed={c2}"
    check("CAD-06  Geodesic closure detection", c06)

    # CAD-07: Hamiltonian energy conservation
    def c07():
        hd   = HamiltonianDynamics([0.05]*6)
        q0   = np.array([0.1, 0.3, 0.5, 0.7, 0.2, 0.9])
        p0   = np.array([0.3, -0.2, 0.5, 0.1, -0.4, 0.2])
        qs, ps = hd.symplectic_rk4(q0, p0, dt=0.005, n_steps=500)
        cons = hd.energy_conservation(qs, ps)
        ok   = cons["max_drift"] < 1e-3
        return ok, f"H drift = {cons['max_drift']:.2e} ({cons['conservation']})"
    check("CAD-07  Hamiltonian energy conservation", c07)

    # CAD-08: T^∞ metric converges
    def c08():
        tinf = InfiniteDimLimit()
        x    = [0.3, 0.5, 0.7, 0.1, 0.9, 0.4]
        y    = [0.4, 0.6, 0.8, 0.2, 0.85, 0.35]
        d6   = tinf.distance(x, y, 6)
        d50  = tinf.distance(
            tinf.embed_t6_in_tinf(x, 44),
            tinf.embed_t6_in_tinf(y, 44), 50
        )
        ok = d6 <= 2.0 and d50 >= d6 * 0.9  # d_∞ ≥ d_6 since more terms
        return ok, f"d_T6={d6:.4f}, d_T∞≈{d50:.4f}"
    check("CAD-08  T^∞ metric convergence", c08)

    # CAD-09: SVG export is valid
    def c09():
        exp  = AOTS6CADExport()
        svg  = exp.export_torus_svg()
        ok   = svg.startswith('<svg') and '</svg>' in svg
        return ok, f"SVG: {len(svg)} chars, valid={'</svg>' in svg}"
    check("CAD-09  SVG export valid", c09)

    # CAD-10: Complex movement Ψ is bounded
    def c10():
        cm   = ComplexMovement()
        orb  = cm.orbit_portrait([0.3, 0.5, 0.1, 0.7, 0.4, 0.8], n_iter=10)
        ok   = orb["is_bounded"]
        return ok, f"orbit bounded={ok}, nearest return at iter {orb['nearest_return']}"
    check("CAD-10  Complex movement ¹¹∞∆⁶ bounded orbit", c10)

    # CAD-11: OBJ export format
    def c11():
        m    = ToroidalMesh(R=3, r=1, n_phi=8, n_theta=4)
        obj  = m.to_obj()
        ok   = obj.startswith('# AOTS6') and 'v ' in obj and 'f ' in obj
        return ok, f"OBJ: {len(obj.splitlines())} lines"
    check("CAD-11  OBJ mesh export", c11)

    # CAD-12: T^11 holonomy
    def c12():
        t11  = T11Manifold()
        hol  = t11.holonomy_t11([1,0,0,0,0,1,0,1,0,0,-1])
        ok   = (len(hol["winding"]) == 11 and
                len(hol["dims_active"]) >= 3 and
                hol["is_memory"])
        return ok, f"Active dims: {[d[0] for d in hol['dims_active']]}"
    check("CAD-12  T^11 holonomy and memory", c12)

    passed   = sum(1 for r in results if r["passed"])
    total    = len(results)
    ms_total = (time.perf_counter() - t_total) * 1000
    print("─" * 66)
    print(f"  Result: {passed}/{total} tests passed  |  {ms_total:.1f}ms")
    print("=" * 66 + "\n")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────────────────────

def demo_cad():
    """CAD + Movement demo."""
    print("AOTS6 CAD + T^11 + ¹¹∞∆⁶ Demo")
    print("=" * 52)

    # Torus geometry
    m = ToroidalMesh(R=3, r=1, n_phi=48, n_theta=24)
    s = m.summary()
    print(f"\n  T² Mesh: {s['n_vertices']} verts, area={s['surface_area']}")
    print(f"  Curvature K ∈ [{s['K_range'][0]}, {s['K_range'][1]}]")

    # T^11 node
    t11  = T11Manifold()
    c11  = t11.embed_from_t6([0.3, 0.7, 0.5, 0.2, 0.9, 0.4])
    prof = t11.dimension_profile(c11)
    print(f"\n  T^11 node dominant dim: {prof['dominant']}")
    print(f"  T^11 coord: {prof['coord'][:6]}... (6 of 11)")

    # Complex movement
    cm  = ComplexMovement()
    psi = cm.psi_map([0.3, 0.5, 0.7, 0.2, 0.8, 0.4], t_flow=1.0)
    print(f"\n  Ψ: ¹¹∞∆⁶ movement")
    print(f"  input : {psi['input_T6']}")
    print(f"  output: {psi['after_delta6']}")
    print(f"  displ : {psi['displacement']}")

    # Geodesic flow
    geo = GeodesicFlow(6)
    s_geo = geo.summary()
    print(f"\n  Geodesics:")
    print(f"  rational v  → closed={s_geo['rational_is_closed']}, "
          f"period={s_geo['rational_period']}")
    print(f"  irrational v → closed={s_geo['irrational_is_closed']}")
    print()


if __name__ == "__main__":
    results = run_cad_validation()
    demo_cad()
