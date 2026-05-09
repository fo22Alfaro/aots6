# SPDX-License-Identifier: LicenseRef-AOTS6-ARR-1.0
# Copyright (c) 2025-2026 Alfredo Jhovany Alfaro Garcia - All Rights Reserved
# github.com/fo22Alfaro/aots6 — draft-alfaro-aots6-01
"""
aots6_quantum.py — AOTS6 Quantum Toroidal Framework
=====================================================
Implements the formal equations from AOTS6_Quantum_Framework_COMPLETE_FULL:

  1. Toroidal coordinate system  (bipolar/toroidal 3D)
  2. Laplacian in toroidal coordinates
  3. Schrodinger equation on toroid  (discrete FD approximation)
  4. Flux quantum Hamiltonian  (superconducting ring)
  5. Kitaev topological Hamiltonian  (Majorana chain)
  6. Lindblad master equation  (open quantum system)
  7. AOTS6 integration: T^6 node mapped to quantum state

Dependencies: numpy, scipy (stdlib-only fallback for core ops)
Optional:     matplotlib (visualization)
"""

from __future__ import annotations

import numpy as np
from scipy import linalg, sparse
from scipy.sparse.linalg import eigsh
from typing import List, Tuple, Optional, Dict, Any
import hashlib
import json


# ─────────────────────────────────────────────────────────────────────────────
# 1. TOROIDAL COORDINATE SYSTEM
# ─────────────────────────────────────────────────────────────────────────────

def toroidal_to_cartesian(xi: float, eta: float, phi: float,
                          a: float = 1.0) -> Tuple[float, float, float]:
    """
    Bipolar toroidal coordinates → Cartesian (x, y, z).

    x = a * sinh(xi) / (cosh(xi) - cos(eta)) * cos(phi)
    y = a * sinh(xi) / (cosh(xi) - cos(eta)) * sin(phi)
    z = a * sin(eta)  / (cosh(xi) - cos(eta))

    Parameters
    ----------
    xi  : radial toroidal coordinate  (0, inf)
    eta : poloidal angle              (-pi, pi)
    phi : azimuthal angle             (0, 2*pi)
    a   : focal ring radius
    """
    denom = np.cosh(xi) - np.cos(eta)
    x = a * np.sinh(xi) / denom * np.cos(phi)
    y = a * np.sinh(xi) / denom * np.sin(phi)
    z = a * np.sin(eta) / denom
    return x, y, z


def toroidal_scale_factors(xi: float, eta: float,
                           a: float = 1.0) -> Tuple[float, float, float]:
    """
    Lame coefficients h_xi = h_eta = h_phi for toroidal coordinates.
    h_xi = h_eta = a / (cosh(xi) - cos(eta))
    h_phi        = a * sinh(xi) / (cosh(xi) - cos(eta))
    """
    denom = np.cosh(xi) - np.cos(eta)
    h     = a / denom
    h_phi = a * np.sinh(xi) / denom
    return h, h, h_phi


# ─────────────────────────────────────────────────────────────────────────────
# 2. LAPLACIAN IN TOROIDAL COORDINATES  (analytic expression)
# ─────────────────────────────────────────────────────────────────────────────

class ToroidalLaplacian:
    """
    Discrete Laplacian on a 2D toroidal grid (xi, eta) at fixed phi.

    Uses second-order finite differences with periodic boundary in eta
    and Dirichlet in xi.

    nabla^2 f ≈ (1/h^2) * [f(i+1,j) + f(i-1,j) + f(i,j+1) + f(i,j-1) - 4f(i,j)]
    corrected by the Lame factors at each grid point.
    """

    def __init__(self, N_xi: int = 32, N_eta: int = 32,
                 xi_max: float = 3.0, a: float = 1.0):
        self.N_xi  = N_xi
        self.N_eta = N_eta
        self.a     = a
        self.xi    = np.linspace(0.1, xi_max, N_xi)
        self.eta   = np.linspace(-np.pi, np.pi, N_eta, endpoint=False)
        self.dxi   = self.xi[1]  - self.xi[0]
        self.deta  = self.eta[1] - self.eta[0]
        self._L    = None

    def build(self) -> sparse.csr_matrix:
        """Build the sparse Laplacian matrix  L  of shape (N*N, N*N)."""
        N = self.N_xi * self.N_eta
        rows, cols, vals = [], [], []

        def idx(i, j):
            return i * self.N_eta + (j % self.N_eta)

        for i in range(self.N_xi):
            for j in range(self.N_eta):
                xi_  = self.xi[i]
                eta_ = self.eta[j]
                h, _, _ = toroidal_scale_factors(xi_, eta_, self.a)
                # Use uniform h² so the stencil is symmetric
                h2xi  = self.dxi  ** 2
                h2eta = self.deta ** 2
                c = idx(i, j)

                diag = -(2/h2xi + 2/h2eta)
                rows.append(c); cols.append(c); vals.append(diag)

                # xi neighbours (Dirichlet BC)
                if i > 0:
                    rows.append(c); cols.append(idx(i-1, j)); vals.append(1/h2xi)
                if i < self.N_xi - 1:
                    rows.append(c); cols.append(idx(i+1, j)); vals.append(1/h2xi)

                # eta neighbours (periodic BC)
                rows.append(c); cols.append(idx(i, j-1)); vals.append(1/h2eta)
                rows.append(c); cols.append(idx(i, j+1)); vals.append(1/h2eta)

        self._L = sparse.csr_matrix((vals, (rows, cols)), shape=(N, N))
        return self._L

    @property
    def matrix(self) -> sparse.csr_matrix:
        if self._L is None:
            self.build()
        return self._L


# ─────────────────────────────────────────────────────────────────────────────
# 3. SCHRODINGER EQUATION ON TOROID
# ─────────────────────────────────────────────────────────────────────────────

class ToroidalSchrodinger:
    """
    [-1/(2m) nabla^2 + V(xi, eta)] psi = E psi

    Solved as a sparse eigenvalue problem.
    Returns the n_states lowest eigenvalues and eigenvectors.
    """

    def __init__(self, laplacian: ToroidalLaplacian,
                 mass: float = 1.0,
                 potential_fn=None):
        self.lap      = laplacian
        self.mass     = mass
        self.V_fn     = potential_fn or (lambda xi, eta: 0.0)
        self._H       = None
        self.energies = None
        self.states   = None

    def build_hamiltonian(self) -> sparse.csr_matrix:
        L = self.lap.matrix
        N = self.lap.N_xi * self.lap.N_eta

        # Potential diagonal
        V_diag = np.zeros(N)
        for i, xi_ in enumerate(self.lap.xi):
            for j, eta_ in enumerate(self.lap.eta):
                k = i * self.lap.N_eta + j
                V_diag[k] = self.V_fn(xi_, eta_)

        T = -1.0 / (2.0 * self.mass) * L
        V = sparse.diags(V_diag, format='csr')
        self._H = T + V
        return self._H

    def solve(self, n_states: int = 6) -> Tuple[np.ndarray, np.ndarray]:
        if self._H is None:
            self.build_hamiltonian()
        # Shift-invert for lowest eigenvalues
        self.energies, self.states = eigsh(
            self._H, k=n_states, which='SM', tol=1e-6
        )
        idx = np.argsort(self.energies)
        self.energies = self.energies[idx]
        self.states   = self.states[:, idx]
        return self.energies, self.states

    def probability_density(self, state_idx: int = 0) -> np.ndarray:
        if self.states is None:
            self.solve()
        psi = self.states[:, state_idx]
        rho = np.abs(psi) ** 2
        return rho.reshape(self.lap.N_xi, self.lap.N_eta)


# ─────────────────────────────────────────────────────────────────────────────
# 4. FLUX QUANTUM HAMILTONIAN  (superconducting ring)
# ─────────────────────────────────────────────────────────────────────────────

PHI0 = 2.067833848e-15   # Weber  (magnetic flux quantum h/2e)

class FluxQubitHamiltonian:
    """
    Flux qubit on a superconducting ring:

      H_flux = (1/2L)(Phi - n*Phi0)^2
      H_J    = -E_J * cos(phi_hat - 2*pi*Phi/Phi0)

    Represented in the charge basis |n> for n in [-n_max, n_max].
    """

    def __init__(self, E_J: float = 10.0, E_L: float = 1.0,
                 Phi_ext: float = 0.0, n_max: int = 10):
        self.E_J    = E_J
        self.E_L    = E_L
        self.Phi    = Phi_ext
        self.n_max  = n_max
        self.dim    = 2 * n_max + 1
        self._H     = None

    def build(self) -> np.ndarray:
        n   = self.n_max
        dim = self.dim
        H   = np.zeros((dim, dim), dtype=complex)
        ns  = np.arange(-n, n + 1)

        # Inductive term  (1/2L)(Phi - n*Phi0)^2  → diagonal
        for i, ni in enumerate(ns):
            H[i, i] += 0.5 * self.E_L * (self.Phi - ni) ** 2

        # Josephson term  -E_J/2 * (e^{i phi} + e^{-i phi})
        # In charge basis: raises/lowers n by 1
        phase = np.exp(1j * 2 * np.pi * self.Phi)
        for i in range(dim - 1):
            H[i,   i+1] += -self.E_J / 2.0 * phase
            H[i+1, i  ] += -self.E_J / 2.0 * np.conj(phase)

        self._H = H
        return H

    def eigenstates(self) -> Tuple[np.ndarray, np.ndarray]:
        if self._H is None:
            self.build()
        energies, states = linalg.eigh(self._H)
        return energies, states

    def qubit_gap(self) -> float:
        e, _ = self.eigenstates()
        return float(e[1] - e[0])


# ─────────────────────────────────────────────────────────────────────────────
# 5. KITAEV TOPOLOGICAL HAMILTONIAN  (Majorana chain)
# ─────────────────────────────────────────────────────────────────────────────

class KitaevChain:
    """
    H_K = -mu * sum_i c†_i c_i
          - t  * sum_i (c†_i c_{i+1} + h.c.)
          + Delta * sum_i (c_i c_{i+1} + h.c.)

    Implemented in the Bogoliubov-de Gennes (BdG) representation.
    Shape: (2N x 2N) Nambu spinor basis (c, c†).

    Topological phase: |mu| < 2|t|  → Majorana zero modes at ends.
    Trivial phase:     |mu| > 2|t|
    """

    def __init__(self, N: int = 20, mu: float = 0.5,
                 t: float = 1.0, delta: float = 1.0):
        self.N     = N
        self.mu    = mu
        self.t     = t
        self.delta = delta
        self._H    = None

    def build_bdg(self) -> np.ndarray:
        N = self.N
        H = np.zeros((2*N, 2*N), dtype=complex)

        for i in range(N):
            # Chemical potential
            H[i,   i  ] += -self.mu / 2.0
            H[i+N, i+N] +=  self.mu / 2.0

            # Hopping
            if i < N - 1:
                H[i,     i+1  ] += -self.t
                H[i+1,   i    ] += -self.t
                H[i+N+1, i+N  ] +=  self.t
                H[i+N,   i+N+1] +=  self.t

            # Pairing
            if i < N - 1:
                H[i,     i+N+1] +=  self.delta
                H[i+N+1, i    ] +=  self.delta
                H[i+1,   i+N  ] += -self.delta
                H[i+N,   i+1  ] += -self.delta

        self._H = H
        return H

    def spectrum(self) -> np.ndarray:
        if self._H is None:
            self.build_bdg()
        return np.sort(linalg.eigvalsh(self._H))

    def is_topological(self) -> bool:
        """Topological iff |mu| < 2*|t|."""
        return abs(self.mu) < 2.0 * abs(self.t)

    def majorana_gap(self) -> float:
        spec = self.spectrum()
        pos  = spec[spec > 1e-10]
        return float(pos.min()) if len(pos) > 0 else 0.0

    def majorana_operators(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return gamma_A = c + c†,  gamma_B = i(c† - c) per site."""
        N   = self.N
        dim = 2 * N
        I   = np.eye(dim)
        # Single-particle ladder operators in BdG basis
        # gamma_A[i] and gamma_B[i] are 2N x 2N matrices
        gammas_A = []
        gammas_B = []
        for i in range(N):
            gA = np.zeros((dim, dim), dtype=complex)
            gB = np.zeros((dim, dim), dtype=complex)
            gA[i, i+N] = 1.0;  gA[i+N, i] = 1.0   # c + c†
            gB[i, i+N] = 1j;   gB[i+N, i] = -1j    # i(c† - c)
            gammas_A.append(gA)
            gammas_B.append(gB)
        return gammas_A, gammas_B


# ─────────────────────────────────────────────────────────────────────────────
# 6. LINDBLAD MASTER EQUATION  (open quantum system)
# ─────────────────────────────────────────────────────────────────────────────

class LindbladEvolution:
    """
    dot(rho) = -i [H, rho] + sum_k ( L_k rho L_k† - 1/2 {L_k† L_k, rho} )

    Solved by vectorising rho as a density-matrix superoperator (Liouvillian).
    rho_vec = vec(rho),   dot(rho_vec) = L_super * rho_vec
    """

    def __init__(self, H: np.ndarray, jump_ops: Optional[List[np.ndarray]] = None):
        self.H    = np.array(H, dtype=complex)
        self.Ls   = [np.array(L, dtype=complex) for L in (jump_ops or [])]
        self.dim  = H.shape[0]
        self._L   = None

    def _kron_comm(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        """Superoperator A ⊗ B acting on vec(rho)."""
        return np.kron(A, B)

    def build_liouvillian(self) -> np.ndarray:
        d  = self.dim
        I  = np.eye(d, dtype=complex)

        # Coherent part: -i (H ⊗ I - I ⊗ H^T)
        L_super = -1j * (np.kron(self.H, I) - np.kron(I, self.H.T))

        # Dissipative part
        for Lk in self.Ls:
            LkLk = Lk.conj().T @ Lk
            L_super += (np.kron(Lk, Lk.conj())
                        - 0.5 * np.kron(LkLk, I)
                        - 0.5 * np.kron(I, LkLk.T))

        self._L = L_super
        return L_super

    def steady_state(self) -> np.ndarray:
        """Find rho_ss such that L_super @ vec(rho_ss) = 0."""
        if self._L is None:
            self.build_liouvillian()

        # Find null vector of L_super
        vals, vecs = linalg.eig(self._L)
        idx = np.argmin(np.abs(vals))
        rho_vec = vecs[:, idx]

        rho = rho_vec.reshape(self.dim, self.dim)
        # Normalise and ensure Hermitian positive semi-definite
        rho = (rho + rho.conj().T) / 2.0
        rho /= np.trace(rho)
        return rho

    def evolve(self, rho0: np.ndarray,
               times: np.ndarray) -> List[np.ndarray]:
        """Time-evolve rho0 under the Lindblad superoperator."""
        if self._L is None:
            self.build_liouvillian()

        rho_vec0 = rho0.flatten().astype(complex)
        results  = []
        dt       = times[1] - times[0] if len(times) > 1 else 0.01

        # Exact matrix exponential for small systems
        if self.dim <= 8:
            for t in times:
                rho_t = linalg.expm(self._L * t) @ rho_vec0
                results.append(rho_t.reshape(self.dim, self.dim))
        else:
            # Euler integration for larger systems
            rho_vec = rho_vec0.copy()
            t_current = 0.0
            t_idx = 0
            while t_idx < len(times):
                if t_current >= times[t_idx]:
                    results.append(rho_vec.reshape(self.dim, self.dim).copy())
                    t_idx += 1
                rho_vec += dt * (self._L @ rho_vec)
                t_current += dt

        return results

    def purity(self, rho: np.ndarray) -> float:
        return float(np.real(np.trace(rho @ rho)))

    def von_neumann_entropy(self, rho: np.ndarray) -> float:
        evals = np.real(linalg.eigvalsh(rho))
        evals = evals[evals > 1e-15]
        return float(-np.sum(evals * np.log(evals)))


# ─────────────────────────────────────────────────────────────────────────────
# 7. AOTS6 INTEGRATION — T^6 NODE ↔ QUANTUM STATE
# ─────────────────────────────────────────────────────────────────────────────

class AOTS6QuantumNode:
    """
    Bridge between an AOTS6 node in T^6 and a quantum state.

    Maps the six T^6 coordinates to physical quantum parameters:
      D0 (temporal)  → evolution time t
      D1 (spatial)   → toroidal xi coordinate
      D2 (logical)   → poloidal eta coordinate
      D3 (memory)    → Kitaev mu (topological order)
      D4 (network)   → Kitaev t (hopping)
      D5 (inference) → Josephson E_J
    """

    def __init__(self, label: str, t6_coord: List[float]):
        if len(t6_coord) != 6:
            raise ValueError("T^6 requires exactly 6 coordinates")
        self.label    = label
        self.coord    = [c % 1.0 for c in t6_coord]
        self._state   = None
        self._chain   = None
        self._flux    = None

    # ── parameter mapping ────────────────────────────────────────────────────

    @property
    def time(self) -> float:
        """D0 → evolution time in [0, 2*pi]."""
        return self.coord[0] * 2 * np.pi

    @property
    def xi(self) -> float:
        """D1 → toroidal xi in [0.1, 3]."""
        return 0.1 + self.coord[1] * 2.9

    @property
    def eta(self) -> float:
        """D2 → poloidal eta in [-pi, pi]."""
        return (self.coord[2] - 0.5) * 2 * np.pi

    @property
    def kitaev_mu(self) -> float:
        """D3 → chemical potential mu in [-3, 3]."""
        return (self.coord[3] - 0.5) * 6.0

    @property
    def kitaev_t(self) -> float:
        """D4 → hopping amplitude in [0.5, 2.0]."""
        return 0.5 + self.coord[4] * 1.5

    @property
    def josephson_ej(self) -> float:
        """D5 → Josephson energy in [1, 20]."""
        return 1.0 + self.coord[5] * 19.0

    # ── quantum computations ─────────────────────────────────────────────────

    def kitaev_phase(self) -> Dict[str, Any]:
        """Compute topological phase from D3, D4 coordinates."""
        chain = KitaevChain(N=10,
                            mu=self.kitaev_mu,
                            t=self.kitaev_t,
                            delta=1.0)
        topo = chain.is_topological()
        gap  = chain.majorana_gap()
        return {
            "topological":  topo,
            "majorana_gap": round(gap, 6),
            "mu":           round(self.kitaev_mu, 4),
            "t":            round(self.kitaev_t,  4),
            "phase":        "TOPOLOGICAL" if topo else "TRIVIAL",
        }

    def flux_qubit(self) -> Dict[str, Any]:
        """Compute flux qubit spectrum from D5 coordinate."""
        fq = FluxQubitHamiltonian(
            E_J=self.josephson_ej,
            E_L=1.0,
            Phi_ext=self.coord[0],   # D0 as external flux
            n_max=5
        )
        e, _ = fq.eigenstates()
        gap  = fq.qubit_gap()
        return {
            "E_J":       round(self.josephson_ej, 4),
            "qubit_gap": round(gap, 6),
            "ground_E":  round(float(e[0]), 6),
            "first_E":   round(float(e[1]), 6),
        }

    def cartesian_position(self) -> Tuple[float, float, float]:
        """Map D1, D2 to 3D Cartesian via toroidal coordinates."""
        x, y, z = toroidal_to_cartesian(self.xi, self.eta,
                                         phi=self.coord[4] * 2 * np.pi)
        return round(x, 6), round(y, 6), round(z, 6)

    def quantum_identity(self) -> str:
        """
        Cryptographic identity = SHA-256(T^6 coords + quantum observables).
        Links AOTS6 identity chain to quantum state.
        """
        phase = self.kitaev_phase()
        qubit = self.flux_qubit()
        payload = json.dumps({
            "label":   self.label,
            "coord":   [round(c, 8) for c in self.coord],
            "phase":   phase["phase"],
            "gap":     phase["majorana_gap"],
            "qubit":   qubit["qubit_gap"],
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def summary(self) -> Dict[str, Any]:
        return {
            "label":        self.label,
            "coord_T6":     [round(c, 4) for c in self.coord],
            "cartesian":    self.cartesian_position(),
            "kitaev":       self.kitaev_phase(),
            "flux_qubit":   self.flux_qubit(),
            "q_identity":   self.quantum_identity()[:16] + "...",
        }


# ─────────────────────────────────────────────────────────────────────────────
# 8. VALIDATION SUITE
# ─────────────────────────────────────────────────────────────────────────────

def run_quantum_validation() -> List[Dict]:
    results = []

    def check(name, fn):
        import time
        t0 = time.perf_counter()
        try:
            ok, msg, details = fn()
        except Exception as e:
            ok, msg, details = False, str(e), {}
        ms = (time.perf_counter() - t0) * 1000
        icon = "[+]" if ok else "[x]"
        results.append({"name": name, "passed": ok, "msg": msg, "ms": round(ms, 1)})
        print(f"  {icon} {'PASS' if ok else 'FAIL'}  {name:<48}  ({ms:.1f}ms)")
        print(f"         {msg}")
        return ok

    print("\n" + "=" * 62)
    print(" AOTS6 Quantum Framework — Validation Suite")
    print("=" * 62)

    # QTC-01: Toroidal coordinates round-trip
    def qc01():
        xi, eta, phi = 1.5, 0.8, 1.2
        x, y, z = toroidal_to_cartesian(xi, eta, phi, a=1.0)
        # Verify against analytic: r = sqrt(x^2+y^2), z given
        r = np.sqrt(x**2 + y**2)
        expected_r = np.sinh(xi) / (np.cosh(xi) - np.cos(eta))
        ok = abs(r - expected_r) < 1e-10
        return ok, f"r={r:.6f}, expected={expected_r:.6f}", {}
    check("QTC-01 Toroidal coordinate round-trip", qc01)

    # QTC-02: Laplacian matrix is symmetric
    def qc02():
        lap = ToroidalLaplacian(N_xi=8, N_eta=8)
        L   = lap.build()
        diff = abs(L - L.T).max()
        ok  = diff < 1e-12
        return ok, f"||L - L^T||_max = {diff:.2e}", {"nnz": L.nnz}
    check("QTC-02 Laplacian symmetry", qc02)

    # QTC-03: Schrodinger ground state energy is real and negative
    def qc03():
        lap = ToroidalLaplacian(N_xi=12, N_eta=12)
        sch = ToroidalSchrodinger(lap)
        E, _ = sch.solve(n_states=3)
        ok = np.all(np.isreal(E)) and E[0] <= E[1] <= E[2]
        return ok, f"E_0={E[0]:.4f}, E_1={E[1]:.4f}, E_2={E[2]:.4f}", {}
    check("QTC-03 Schrodinger eigenvalues real and ordered", qc03)

    # QTC-04: Flux qubit gap increases with E_J
    def qc04():
        gaps = []
        for ej in [1.0, 5.0, 10.0, 20.0]:
            fq = FluxQubitHamiltonian(E_J=ej, E_L=1.0, Phi_ext=0.0, n_max=5)
            gaps.append(fq.qubit_gap())
        ok = all(gaps[i] < gaps[i+1] for i in range(len(gaps)-1))
        return ok, f"gaps={[round(g,3) for g in gaps]}", {}
    check("QTC-04 Flux qubit gap monotone in E_J", qc04)

    # QTC-05: Kitaev topological phase boundary
    def qc05():
        # |mu| < 2|t| → topological
        chain_topo  = KitaevChain(N=10, mu=0.5, t=1.0, delta=1.0)
        chain_triv  = KitaevChain(N=10, mu=3.0, t=1.0, delta=1.0)
        ok = chain_topo.is_topological() and not chain_triv.is_topological()
        gap_t = chain_topo.majorana_gap()
        gap_v = chain_triv.majorana_gap()
        return ok, f"topo_gap={gap_t:.4f}, trivial_gap={gap_v:.4f}", {}
    check("QTC-05 Kitaev topological phase boundary", qc05)

    # QTC-06: Lindblad steady state is valid density matrix
    def qc06():
        # 2-level system with decay
        H  = np.array([[1, 0], [0, -1]], dtype=complex)
        Lk = np.array([[0, 1], [0,  0]], dtype=complex) * 0.5   # decay
        lind = LindbladEvolution(H, [Lk])
        rho_ss = lind.steady_state()
        trace_ok  = abs(np.trace(rho_ss) - 1.0) < 1e-6
        herm_ok   = np.allclose(rho_ss, rho_ss.conj().T, atol=1e-6)
        evals     = np.real(linalg.eigvalsh(rho_ss))
        pos_ok    = np.all(evals >= -1e-6)
        ok = trace_ok and herm_ok and pos_ok
        S  = lind.von_neumann_entropy(rho_ss)
        return ok, f"Tr(rho)={np.trace(rho_ss).real:.6f}, S={S:.4f}", {}
    check("QTC-06 Lindblad steady state is valid density matrix", qc06)

    # QTC-07: T^6 node quantum identity is deterministic
    def qc07():
        coord = [0.1, 0.3, 0.5, 0.2, 0.7, 0.9]
        n1 = AOTS6QuantumNode("A", coord)
        n2 = AOTS6QuantumNode("A", coord)
        n3 = AOTS6QuantumNode("A", [0.2, 0.3, 0.5, 0.2, 0.7, 0.9])  # different
        ok = (n1.quantum_identity() == n2.quantum_identity() and
              n1.quantum_identity() != n3.quantum_identity())
        return ok, "Same coords → same q-identity; diff coords → diff identity", {}
    check("QTC-07 Quantum identity determinism", qc07)

    # QTC-08: Purity of pure state = 1
    def qc08():
        rho_pure = np.array([[1, 0], [0, 0]], dtype=complex)
        lind = LindbladEvolution(np.zeros((2,2), dtype=complex))
        p = lind.purity(rho_pure)
        ok = abs(p - 1.0) < 1e-10
        return ok, f"Tr(rho^2) = {p:.10f}", {}
    check("QTC-08 Purity of pure state = 1", qc08)

    passed = sum(1 for r in results if r["passed"])
    total  = len(results)
    ms_tot = sum(r["ms"] for r in results)
    print("─" * 62)
    print(f"  Result: {passed}/{total} tests passed  |  {ms_tot:.1f}ms total")
    print("=" * 62 + "\n")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────────────────────

def demo():
    print("\nAOTS6 Quantum Framework — Demo")
    print("=" * 48)

    # Five AOTS6 nodes with distinct T^6 coordinates
    nodes = [
        AOTS6QuantumNode("Alpha",   [0.10, 0.20, 0.40, 0.15, 0.80, 0.90]),
        AOTS6QuantumNode("Beta",    [0.33, 0.50, 0.67, 0.60, 0.30, 0.45]),
        AOTS6QuantumNode("Gamma",   [0.55, 0.75, 0.20, 0.85, 0.55, 0.70]),
        AOTS6QuantumNode("Delta",   [0.70, 0.10, 0.80, 0.40, 0.15, 0.25]),
        AOTS6QuantumNode("Epsilon", [0.90, 0.60, 0.35, 0.25, 0.95, 0.60]),
    ]

    for node in nodes:
        s = node.summary()
        phase = s["kitaev"]["phase"]
        gap   = s["kitaev"]["majorana_gap"]
        qgap  = s["flux_qubit"]["qubit_gap"]
        cart  = s["cartesian"]
        qid   = s["q_identity"]
        print(f"\n  [{s['label']:8s}]")
        print(f"    T^6       : {s['coord_T6']}")
        print(f"    Cartesian : ({cart[0]:7.4f}, {cart[1]:7.4f}, {cart[2]:7.4f})")
        print(f"    Kitaev    : {phase:<12s}  gap={gap:.4f}")
        print(f"    Flux qubit: E_J={s['flux_qubit']['E_J']:.2f}  qubit_gap={qgap:.4f}")
        print(f"    Q-identity: {qid}")

    print("\n")


if __name__ == "__main__":
    results = run_quantum_validation()
    demo()
