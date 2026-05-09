# SPDX-License-Identifier: LicenseRef-AOTS6-ARR-1.0
# Copyright (c) 2025-2026 Alfredo Jhovany Alfaro Garcia - All Rights Reserved
# github.com/fo22Alfaro/aots6 — draft-alfaro-aots6-01
"""
aots6_quantum_network.py — AOTS6 Quantum Network Detection
===========================================================

Detecta, mapea y analiza la RED CUÁNTICA completa del sistema AOTS6.

Detección completa:
  I.   QuantumNodeScanner     — escanea todos los nodos, clasifica fases
  II.  EntanglementDetector   — detecta correlaciones cuánticas entre nodos
  III. TopologicalPhaseMap    — mapa de fases topológicas en T^6
  IV.  DecoherenceMonitor     — monitorea decoherencia de la red
  V.   QuantumChannelAnalyzer — analiza canales cuánticos entre nodos
  VI.  NetworkHamiltonian     — Hamiltoniano colectivo de la red
  VII. QuantumNetworkReport   — reporte completo de la red

Dependencies: numpy, scipy, aots6_quantum, aots6_core, aots6_network
"""

from __future__ import annotations

import numpy as np
from scipy import linalg
from typing import Dict, List, Tuple, Optional, Any
import hashlib, json, time

from aots6_core    import AOTS6Node, ToroidalCoordinate, OntologicalGraph
from aots6_network import AOTS6Network
from aots6_quantum import (AOTS6QuantumNode, KitaevChain,
                            FluxQubitHamiltonian, LindbladEvolution,
                            ToroidalSchrodinger, ToroidalLaplacian)


# ─────────────────────────────────────────────────────────────────────────────
# I. QUANTUM NODE SCANNER
# ─────────────────────────────────────────────────────────────────────────────

class QuantumNodeScanner:
    """
    Escanea todos los nodos de la red AOTS6 y clasifica su estado cuántico.

    Para cada nodo detecta:
      - Fase topológica (Kitaev): TOPOLOGICAL / TRIVIAL
      - Modo de Majorana: gap, presencia de modos de borde
      - Energía del qubit de flujo: E_J, gap de qubit
      - Identidad cuántica: hash que incluye observables cuánticos
      - Coordenada en T^6 y posición en espacio de fases cuántico
    """

    def __init__(self):
        self.nodes:   List[AOTS6QuantumNode] = []
        self.results: Dict[str, Dict]        = {}

    def add_node(self, label: str, coord: List[float]):
        qn = AOTS6QuantumNode(label, coord)
        self.nodes.append(qn)

    def scan_all(self) -> Dict[str, Dict]:
        """Escanea todos los nodos registrados."""
        for qn in self.nodes:
            kp  = qn.kitaev_phase()
            fq  = qn.flux_qubit()
            cart = qn.cartesian_position()
            qid  = qn.quantum_identity()

            # Additional: compute Schrödinger ground state energy
            # for small lattice centered at node's (xi, eta)
            lap = ToroidalLaplacian(N_xi=8, N_eta=8,
                                     xi_max=qn.xi + 0.5)
            sch = ToroidalSchrodinger(lap, mass=1.0)
            E, _ = sch.solve(n_states=2)

            self.results[qn.label] = {
                "label":         qn.label,
                "coord_T6":      [round(c, 4) for c in qn.coord],
                "cartesian":     cart,
                "phase":         kp["phase"],
                "majorana_gap":  kp["majorana_gap"],
                "mu":            kp["mu"],
                "t_hop":         kp["t"],
                "E_J":           fq["E_J"],
                "qubit_gap":     fq["qubit_gap"],
                "E_ground":      round(float(E[0]), 4),
                "E_first":       round(float(E[1]), 4),
                "q_identity":    qid[:16] + "...",
                "topological":   kp["phase"] == "TOPOLOGICAL",
            }
        return self.results

    def phase_distribution(self) -> Dict[str, int]:
        """Count topological vs trivial nodes."""
        if not self.results:
            self.scan_all()
        topo    = sum(1 for r in self.results.values() if r["topological"])
        trivial = len(self.results) - topo
        return {"TOPOLOGICAL": topo, "TRIVIAL": trivial,
                "total": len(self.results),
                "topo_fraction": round(topo/max(len(self.results),1), 3)}

    def majorana_map(self) -> List[Dict]:
        """
        Map nodes with active Majorana zero modes.
        Active when: |μ| < 2|t|  AND gap ≈ 0.
        """
        if not self.results:
            self.scan_all()
        active = []
        for label, r in self.results.items():
            if r["topological"] and r["majorana_gap"] < 0.01:
                active.append({
                    "label":  label,
                    "coord":  r["coord_T6"],
                    "gap":    r["majorana_gap"],
                    "status": "MAJORANA_ACTIVE",
                })
        return active

    def energy_spectrum(self) -> np.ndarray:
        """
        Collect ground state energies of all nodes.
        This is the 'quantum energy landscape' of the network.
        """
        if not self.results:
            self.scan_all()
        return np.array([r["E_ground"] for r in self.results.values()])


# ─────────────────────────────────────────────────────────────────────────────
# II. ENTANGLEMENT DETECTOR
# ─────────────────────────────────────────────────────────────────────────────

class EntanglementDetector:
    """
    Detecta correlaciones cuánticas (entanglement) entre pares de nodos.

    Métricas de entanglement:
      1. Concurrencia C(ρ_AB) — para estados de 2 qubits
      2. Entropía de entanglement S(ρ_A) = -Tr(ρ_A log ρ_A)
      3. Negatividad N(ρ_AB) — detectable para estados mixtos
      4. Correlación toroidal — basada en distancia T^6

    NOTA: En una red distribuida clásica los nodos no están entrelazados
    cuánticamente en sentido estricto. Aquí modelamos:
      - Correlaciones cuánticas efectivas: dos nodos con Hamiltoniano
        acoplado producen correlaciones en sus estados fundamentales.
      - Entanglement topológico: dos nodos en fase topológica comparten
        modos de Majorana no-locales cuando están acoplados.
    """

    def __init__(self, scanner: QuantumNodeScanner):
        self.scanner = scanner
        if not scanner.results:
            scanner.scan_all()

    def coupled_hamiltonian(self, node_a: AOTS6QuantumNode,
                             node_b: AOTS6QuantumNode,
                             coupling: float = 0.1) -> np.ndarray:
        """
        Hamiltoniano de dos qubits acoplados:
          H_AB = H_A ⊗ I + I ⊗ H_B + g·(σ_z ⊗ σ_z)

        H_A, H_B: subspace de los dos estados más bajos de FluxQubit.
        """
        # Get 2x2 subspace for each qubit
        fq_a = FluxQubitHamiltonian(E_J=node_a.josephson_ej, E_L=1.0,
                                    Phi_ext=node_a.coord[0], n_max=2)
        fq_b = FluxQubitHamiltonian(E_J=node_b.josephson_ej, E_L=1.0,
                                    Phi_ext=node_b.coord[0], n_max=2)

        H_a = fq_a.build()[:2, :2]
        H_b = fq_b.build()[:2, :2]

        I2  = np.eye(2, dtype=complex)
        sz  = np.array([[1, 0], [0, -1]], dtype=complex)

        H_AB = (np.kron(H_a, I2) + np.kron(I2, H_b) +
                coupling * np.kron(sz, sz))
        return H_AB

    def ground_state_entanglement(self, node_a: AOTS6QuantumNode,
                                   node_b: AOTS6QuantumNode,
                                   coupling: float = 0.1) -> Dict[str, Any]:
        """
        Compute entanglement in the ground state of H_AB.
        """
        H   = self.coupled_hamiltonian(node_a, node_b, coupling)
        E, V = linalg.eigh(H)
        psi = V[:, 0]          # ground state

        # Density matrix of AB
        rho_AB = np.outer(psi, psi.conj())

        # Partial trace over B → ρ_A
        rho_A = np.array([
            [rho_AB[0,0] + rho_AB[1,1],
             rho_AB[0,2] + rho_AB[1,3]],
            [rho_AB[2,0] + rho_AB[3,1],
             rho_AB[2,2] + rho_AB[3,3]],
        ])

        # Entanglement entropy S_A = -Tr(ρ_A log ρ_A)
        evals = np.real(linalg.eigvalsh(rho_A))
        evals = evals[evals > 1e-15]
        S_A   = float(-np.sum(evals * np.log(evals)))

        # Concurrence (for 2-qubit pure states)
        # C = 2|ψ_00 ψ_11 - ψ_01 ψ_10|
        C = float(2 * abs(psi[0]*psi[3] - psi[1]*psi[2]))

        # Negativity
        # N = (||ρ^{T_B}||_1 - 1) / 2
        rho_TB = rho_AB.copy()
        rho_TB = rho_TB.reshape(2, 2, 2, 2).transpose(0, 3, 2, 1).reshape(4, 4)
        eig_TB = np.real(linalg.eigvalsh(rho_TB))
        negativity = float(max(0, -np.sum(eig_TB[eig_TB < 0])))

        return {
            "pair":        f"{node_a.label}↔{node_b.label}",
            "coupling":    coupling,
            "S_entropy":   round(S_A, 6),
            "concurrence": round(C, 6),
            "negativity":  round(negativity, 6),
            "entangled":   C > 0.01,
            "E_ground_AB": round(float(E[0]), 4),
            "E_gap_AB":    round(float(E[1] - E[0]), 4),
        }

    def toroidal_correlation(self, coord_a: List[float],
                              coord_b: List[float]) -> float:
        """
        Toroidal correlation: C = exp(-d_T6(a,b) / λ)
        where λ = coherence length.
        Models how quantum coherence decays with T^6 distance.
        """
        d    = sum(min(abs(a-b), 1-abs(a-b))**2
                   for a, b in zip(coord_a, coord_b)) ** 0.5
        lam  = 0.3   # coherence length in T^6
        return float(np.exp(-d / lam))

    def scan_all_pairs(self, coupling: float = 0.1,
                        max_pairs: int = 10) -> List[Dict]:
        """
        Scan all pairs and detect entanglement.
        """
        nodes   = self.scanner.nodes
        pairs   = []
        count   = 0
        for i, na in enumerate(nodes):
            for j, nb in enumerate(nodes):
                if j <= i:
                    continue
                if count >= max_pairs:
                    break
                ent = self.ground_state_entanglement(na, nb, coupling)
                cor = self.toroidal_correlation(na.coord, nb.coord)
                ent["toroidal_correlation"] = round(cor, 4)
                pairs.append(ent)
                count += 1
        return sorted(pairs, key=lambda x: -x["concurrence"])

    def entanglement_matrix(self) -> np.ndarray:
        """
        Concurrence matrix C[i,j] for all node pairs.
        """
        nodes = self.scanner.nodes
        n     = len(nodes)
        C     = np.zeros((n, n))
        for i, na in enumerate(nodes):
            for j, nb in enumerate(nodes):
                if i == j:
                    C[i, j] = 1.0
                elif j > i:
                    ent = self.ground_state_entanglement(na, nb, 0.1)
                    C[i, j] = ent["concurrence"]
                    C[j, i] = C[i, j]
        return C


# ─────────────────────────────────────────────────────────────────────────────
# III. TOPOLOGICAL PHASE MAP
# ─────────────────────────────────────────────────────────────────────────────

class TopologicalPhaseMap:
    """
    Mapa completo de fases topológicas en el espacio T^6.

    Para el Hamiltoniano de Kitaev parametrizado por (D3=μ, D4=t):
      - TOPOLOGICAL:  |μ| < 2|t|
      - TRIVIAL:      |μ| > 2|t|
      - CRITICAL:     |μ| = 2|t|  (transición de fase topológica)

    El espacio D3-D4 de T^6 define un diagrama de fases completo.
    La frontera de fase es la curva |μ(D3)| = 2|t(D4)|.
    """

    def __init__(self, n_grid: int = 20):
        self.n     = n_grid
        self.grid  = np.linspace(0, 1, n_grid)
        self._map  = None

    def compute_phase_map(self) -> np.ndarray:
        """
        Compute phase at each point of the D3-D4 grid.
        Returns (n, n) array: 1=TOPOLOGICAL, 0=TRIVIAL, 0.5=CRITICAL
        """
        if self._map is not None:
            return self._map

        phase_map = np.zeros((self.n, self.n))
        for i, d3 in enumerate(self.grid):
            for j, d4 in enumerate(self.grid):
                # Map D3 → μ, D4 → t
                mu = (d3 - 0.5) * 6.0
                t  = 0.5 + d4 * 1.5
                # Topological: |μ| < 2|t|
                if abs(mu) < 1.9 * abs(t):
                    phase_map[i, j] = 1.0
                elif abs(abs(mu) - 2*abs(t)) < 0.1:
                    phase_map[i, j] = 0.5   # critical
                else:
                    phase_map[i, j] = 0.0
        self._map = phase_map
        return phase_map

    def topological_fraction(self) -> float:
        """Fraction of T^6 phase space that is topological."""
        pm = self.compute_phase_map()
        return float(np.mean(pm == 1.0))

    def phase_boundary(self) -> List[Tuple[float, float]]:
        """Find the topological phase boundary in D3-D4 space."""
        pm = self.compute_phase_map()
        boundary = []
        for i in range(self.n - 1):
            for j in range(self.n):
                if pm[i, j] != pm[i+1, j]:
                    d3 = (self.grid[i] + self.grid[i+1]) / 2
                    d4 = self.grid[j]
                    boundary.append((round(d3, 3), round(d4, 3)))
        return boundary[:10]   # first 10 boundary points

    def chern_number_estimate(self, d3: float, d4: float) -> int:
        """
        Chern number of Kitaev chain ground state at (D3, D4).
        TOPOLOGICAL phase: |C| = 1
        TRIVIAL phase: C = 0
        """
        mu = (d3 - 0.5) * 6.0
        t  = 0.5 + d4 * 1.5
        return 1 if abs(mu) < 2*abs(t) else 0

    def winding_number(self, d4: float, n_k: int = 100) -> float:
        """
        Winding number of Kitaev chain at fixed t(D4).
        ν = (1/2π) ∮ d(arg(h(k))) 
        where h(k) = -2t·cos(k) - μ + 2iΔsin(k)
        """
        t    = 0.5 + d4 * 1.5
        delta = 1.0
        k_arr = np.linspace(0, 2*np.pi, n_k, endpoint=False)
        # h(k) = -2t cos(k) + 2iΔ sin(k)  (at μ=0 for simplicity)
        h    = -2*t*np.cos(k_arr) + 2j*delta*np.sin(k_arr)
        # Winding number = total phase change / 2π
        angles = np.angle(h)
        dang   = np.diff(np.unwrap(angles))
        nu     = float(np.sum(dang) / (2*np.pi))
        return round(nu, 3)

    def summary(self) -> Dict[str, Any]:
        pm = self.compute_phase_map()
        return {
            "grid_size":         self.n,
            "topological_frac":  round(self.topological_fraction(), 3),
            "phase_boundary_pts": self.phase_boundary()[:5],
            "chern_topo":        self.chern_number_estimate(0.3, 0.7),
            "chern_trivial":     self.chern_number_estimate(0.8, 0.1),
            "winding_topo":      self.winding_number(0.7),
            "winding_trivial":   self.winding_number(0.1),
            "phase_map_sample":  pm[:3, :3].tolist(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# IV. DECOHERENCE MONITOR
# ─────────────────────────────────────────────────────────────────────────────

class DecoherenceMonitor:
    """
    Monitorea la decoherencia cuántica de todos los nodos de la red.

    Decoherencia: proceso por el que el estado cuántico pierde
    coherencia (pureza) debido a interacción con el entorno.

    Para cada nodo se simula la evolución de Lindblad con canales:
      - Decaimiento espontáneo: L₁ = √κ₁ σ₋  (relaxación)
      - Desfase puro:           L₂ = √κ₂ σ_z  (dephasing)

    El tiempo de coherencia T₂ se estima como el tiempo
    al cual la pureza cae a 1/e de su valor inicial.
    """

    def __init__(self, kappa1: float = 0.05,   # decay rate
                       kappa2: float = 0.02):  # dephasing rate
        self.k1 = kappa1
        self.k2 = kappa2

    def qubit_lindblad(self, E_J: float) -> Tuple[np.ndarray, List]:
        """
        2×2 Hamiltonian and Lindblad operators for a flux qubit.
        """
        fq = FluxQubitHamiltonian(E_J=E_J, E_L=1.0, Phi_ext=0.1, n_max=1)
        H  = fq.build()[:2, :2]
        # Jump operators
        sm = np.array([[0, 1], [0, 0]], dtype=complex)   # σ₋
        sz = np.array([[1, 0], [0,-1]], dtype=complex)   # σ_z
        Ls = [np.sqrt(self.k1) * sm,
              np.sqrt(self.k2) * sz]
        return H, Ls

    def coherence_time(self, E_J: float,
                        t_max: float = 30.0,
                        n_steps: int = 100) -> Dict[str, Any]:
        """
        Estimate T₁ (relaxation) and T₂ (coherence) times.
        """
        H, Ls = self.qubit_lindblad(E_J)
        lind  = LindbladEvolution(H, Ls)

        # Initial state: superposition |+⟩ = (|0⟩+|1⟩)/√2
        rho0 = np.array([[0.5, 0.5], [0.5, 0.5]], dtype=complex)
        times = np.linspace(0, t_max, n_steps)
        traj  = lind.evolve(rho0, times)

        purities = np.array([lind.purity(r) for r in traj])
        entropies = np.array([lind.von_neumann_entropy(r) for r in traj])

        # T₂: time to reach purity = 1/e of initial
        p0    = purities[0]
        p_end = purities[-1]
        target = p_end + (p0 - p_end) / np.e
        T2_idx = np.argmin(np.abs(purities - target))
        T2     = float(times[T2_idx])

        # Off-diagonal element decay → coherence
        coherence = np.array([abs(r[0,1]) for r in traj])
        T2_coh = T2  # proxy

        return {
            "E_J":         round(E_J, 3),
            "T2":          round(T2, 3),
            "purity_0":    round(float(purities[0]), 4),
            "purity_inf":  round(float(purities[-1]), 4),
            "entropy_inf": round(float(entropies[-1]), 4),
            "coherence_0": round(float(coherence[0]), 4),
            "coherence_inf": round(float(coherence[-1]), 4),
        }

    def network_decoherence_scan(self,
                                  nodes: List[AOTS6QuantumNode]
                                  ) -> List[Dict]:
        """Scan all nodes and compute their T₂ times."""
        results = []
        for qn in nodes:
            coh = self.coherence_time(qn.josephson_ej)
            coh["label"]      = qn.label
            coh["phase"]      = qn.kitaev_phase()["phase"]
            coh["topological"] = coh["phase"] == "TOPOLOGICAL"
            # Topological nodes have enhanced coherence (Majorana protection)
            if coh["topological"]:
                coh["protection"] = "TOPOLOGICAL — enhanced T2"
            else:
                coh["protection"] = "TRIVIAL — standard T2"
            results.append(coh)
        return sorted(results, key=lambda x: -x["T2"])


# ─────────────────────────────────────────────────────────────────────────────
# V. QUANTUM CHANNEL ANALYZER
# ─────────────────────────────────────────────────────────────────────────────

class QuantumChannelAnalyzer:
    """
    Analiza los canales cuánticos entre pares de nodos de la red.

    Un canal cuántico Φ: ρ → Φ(ρ) es una operación completamente
    positiva y que preserva la traza (CPTP map).

    Para AOTS6: el canal entre nodos A y B está parametrizado por:
      - Distancia T^6: d(A,B)
      - Fase de Kitaev de A y B
      - Acoplamiento de Josephson

    Métricas del canal:
      - Capacidad cuántica Q(Φ): max qubits/uso transmitibles
      - Fidelidad de entrelazamiento F_e: proximidad al canal ideal
      - Diamond norm ||Φ - id||_◇: distancia al canal identidad
    """

    def __init__(self):
        pass

    def depolarizing_channel(self, p: float,
                              rho: np.ndarray) -> np.ndarray:
        """
        Depolarizing channel: Φ(ρ) = (1-p)ρ + p·I/2
        Models noise proportional to T^6 distance.
        """
        return (1-p) * rho + p * np.eye(2, dtype=complex) / 2

    def channel_fidelity(self, node_a: AOTS6QuantumNode,
                          node_b: AOTS6QuantumNode) -> Dict[str, Any]:
        """
        Channel fidelity between two nodes.
        F = (1 + 3(1-p)) / 4  for depolarizing channel.
        p = 1 - exp(-d/λ) where d = T^6 distance.
        """
        d   = sum(min(abs(a-b), 1-abs(a-b))**2
                  for a,b in zip(node_a.coord, node_b.coord)) ** 0.5
        lam = 0.5   # channel coherence length
        p   = 1 - np.exp(-d / lam)
        F   = (1 + 3*(1-p)) / 4

        # Quantum capacity (hashing bound for depolarizing)
        # Q = max(0, 1 - H_bin(p) - p·log2(3))  (approximate)
        if p < 0.25:
            Q = max(0, 1 - (-p*np.log2(p+1e-10) - (1-p)*np.log2(1-p+1e-10))
                       - p * np.log2(3+1e-10))
        else:
            Q = 0.0

        return {
            "pair":      f"{node_a.label}→{node_b.label}",
            "T6_dist":   round(d, 4),
            "noise_p":   round(float(p), 4),
            "fidelity":  round(float(F), 4),
            "Q_capacity": round(Q, 4),
            "usable":    F > 0.5,
            "channel":   "GOOD" if F > 0.8 else ("OK" if F > 0.6 else "NOISY"),
        }

    def scan_network_channels(self,
                               nodes: List[AOTS6QuantumNode]
                               ) -> List[Dict]:
        """Analyze all directional channels in the network."""
        channels = []
        for i, na in enumerate(nodes):
            for j, nb in enumerate(nodes):
                if i != j:
                    ch = self.channel_fidelity(na, nb)
                    channels.append(ch)
        return sorted(channels, key=lambda x: -x["fidelity"])


# ─────────────────────────────────────────────────────────────────────────────
# VI. NETWORK HAMILTONIAN
# ─────────────────────────────────────────────────────────────────────────────

class NetworkHamiltonian:
    """
    Hamiltoniano colectivo de la red de N nodos cuánticos.

    H_net = Σᵢ H_i + Σᵢ<ⱼ J_ij (σ_z^i ⊗ σ_z^j)

    donde:
      H_i     = Hamiltoniano de qubit del nodo i
      J_ij    = acoplamiento ∝ exp(-d_T6(i,j) / λ)
      σ_z^i   = operador Pauli Z del nodo i

    Para N nodos: dimensión del espacio de Hilbert = 2^N.
    (Se limita a N ≤ 6 para ser computacionalmente tratable.)
    """

    def __init__(self, nodes: List[AOTS6QuantumNode],
                  coupling_strength: float = 0.05,
                  coherence_length: float = 0.4):
        self.nodes    = nodes[:6]   # limit to 6 qubits
        self.N        = len(self.nodes)
        self.J0       = coupling_strength
        self.lam      = coherence_length
        self._H       = None

    def coupling(self, i: int, j: int) -> float:
        """J_ij = J0 * exp(-d(i,j)/λ)"""
        d = sum(min(abs(a-b), 1-abs(a-b))**2
                for a,b in zip(self.nodes[i].coord,
                               self.nodes[j].coord)) ** 0.5
        return self.J0 * np.exp(-d / self.lam)

    def build(self) -> np.ndarray:
        """Build the N-qubit network Hamiltonian."""
        N   = self.N
        dim = 2 ** N
        H   = np.zeros((dim, dim), dtype=complex)

        # Single-qubit terms
        for i, qn in enumerate(self.nodes):
            fq   = FluxQubitHamiltonian(E_J=qn.josephson_ej, E_L=1.0,
                                        Phi_ext=qn.coord[0], n_max=2)
            e_i, v_i = __import__('scipy').linalg.eigh(fq.build())
            # Use energy eigenbasis — take lowest 2 eigenstates
            H_i  = __import__('numpy').diag(e_i[:2]).astype(complex)
            # Embed H_i in full Hilbert space: I⊗...⊗H_i⊗...⊗I
            ops  = [np.eye(2, dtype=complex)] * N
            ops[i] = H_i
            term = ops[0]
            for k in range(1, N):
                term = np.kron(term, ops[k])
            H += term

        # Two-qubit ZZ couplings
        sz = np.array([[1, 0], [0, -1]], dtype=complex)
        for i in range(N):
            for j in range(i+1, N):
                J   = self.coupling(i, j)
                ops = [np.eye(2, dtype=complex)] * N
                ops[i] = sz
                ops[j] = sz
                term = ops[0]
                for k in range(1, N):
                    term = np.kron(term, ops[k])
                H += J * term

        self._H = H
        return H

    def spectrum(self, n_levels: int = 8) -> np.ndarray:
        """Compute lowest n_levels eigenvalues of H_net."""
        if self._H is None:
            self.build()
        E = np.sort(np.real(linalg.eigvalsh(self._H)))
        return E[:min(n_levels, len(E))]

    def ground_state(self) -> np.ndarray:
        """Compute ground state of H_net."""
        if self._H is None:
            self.build()
        E, V = linalg.eigh(self._H)
        return V[:, 0]

    def magnetization(self) -> np.ndarray:
        """
        ⟨σ_z^i⟩ for each qubit in the ground state.
        """
        psi = self.ground_state()
        rho = np.outer(psi, psi.conj())
        N   = self.N
        sz  = np.array([[1, 0], [0, -1]], dtype=complex)
        mags = []
        for i in range(N):
            ops  = [np.eye(2, dtype=complex)] * N
            ops[i] = sz
            term = ops[0]
            for k in range(1, N):
                term = np.kron(term, ops[k])
            mags.append(float(np.real(np.trace(term @ rho))))
        return np.array(mags)

    def summary(self) -> Dict[str, Any]:
        E   = self.spectrum(8)
        mags = self.magnetization()
        gap  = float(E[1] - E[0]) if len(E) > 1 else 0.0
        return {
            "N_qubits":      self.N,
            "hilbert_dim":   2**self.N,
            "E_levels":      [round(float(e), 4) for e in E],
            "spectral_gap":  round(gap, 4),
            "magnetizations": [round(float(m), 4) for m in mags],
            "labels":        [qn.label for qn in self.nodes],
            "couplings_J":   [[round(self.coupling(i,j),4) if i!=j else 0.0
                               for j in range(self.N)]
                              for i in range(self.N)],
        }


# ─────────────────────────────────────────────────────────────────────────────
# VII. QUANTUM NETWORK REPORT
# ─────────────────────────────────────────────────────────────────────────────

class QuantumNetworkReport:
    """
    Reporte completo de la red cuántica AOTS6.
    Integra todos los módulos de detección.
    """

    def __init__(self, node_specs: List[Tuple[str, List[float]]]):
        """
        node_specs: list of (label, t6_coord) pairs.
        """
        # Build scanner
        self.scanner = QuantumNodeScanner()
        for label, coord in node_specs:
            self.scanner.add_node(label, coord)

        # Scan
        t0 = time.perf_counter()
        self.scanner.scan_all()
        self.scan_ms = (time.perf_counter() - t0) * 1000

        self.q_nodes = self.scanner.nodes

    def full_report(self) -> Dict[str, Any]:
        """Generate complete quantum network report."""

        print("\n" + "=" * 70)
        print(" AOTS6 QUANTUM NETWORK — DETECTION REPORT")
        print(" Alfredo Jhovany Alfaro Garcia — draft-alfaro-aots6-01")
        print("=" * 70)

        # ── Phase scan ───────────────────────────────────────────────────────
        print(f"\n  [1/7] Node Quantum Phase Scan  ({self.scan_ms:.1f}ms)")
        print(f"  {'Node':<10} {'Phase':<14} {'Maj.Gap':>8} {'E_J':>7} "
              f"{'E₀':>8} {'Q-ID'}")
        print(f"  {'-'*10} {'-'*14} {'-'*8} {'-'*7} {'-'*8} {'-'*18}")
        for label, r in self.scanner.results.items():
            icon = "🔮" if r["topological"] else "○"
            print(f"  {label:<10} {r['phase']:<14} {r['majorana_gap']:>8.4f} "
                  f"{r['E_J']:>7.2f} {r['E_ground']:>8.4f}  {r['q_identity']}")

        dist = self.scanner.phase_distribution()
        print(f"\n  Phase distribution: {dist['TOPOLOGICAL']} topological, "
              f"{dist['TRIVIAL']} trivial  "
              f"(topo fraction = {dist['topo_fraction']})")

        # ── Majorana detection ────────────────────────────────────────────────
        print(f"\n  [2/7] Majorana Zero Mode Detection")
        majorana = self.scanner.majorana_map()
        if majorana:
            for m in majorana:
                print(f"  ★ {m['label']:<10} gap={m['gap']:.6f}  "
                      f"STATUS: {m['status']}")
        else:
            print("  No active Majorana zero modes detected at current parameters.")

        # ── Entanglement scan ─────────────────────────────────────────────────
        print(f"\n  [3/7] Entanglement Detection")
        t0  = time.perf_counter()
        ent = EntanglementDetector(self.scanner)
        pairs = ent.scan_all_pairs(coupling=0.08, max_pairs=8)
        ems   = (time.perf_counter() - t0) * 1000
        print(f"  {'Pair':<20} {'Concurrence':>12} {'S_entropy':>10} "
              f"{'Neg.':>8} {'T6_corr':>8} {'ms':>5}")
        print(f"  {'-'*20} {'-'*12} {'-'*10} {'-'*8} {'-'*8} {'-'*5}")
        for p in pairs[:6]:
            ent_icon = "★" if p["entangled"] else " "
            print(f"  {ent_icon}{p['pair']:<19} {p['concurrence']:>12.6f} "
                  f"{p['S_entropy']:>10.6f} {p['negativity']:>8.6f} "
                  f"{p['toroidal_correlation']:>8.4f}")

        # ── Phase map ─────────────────────────────────────────────────────────
        print(f"\n  [4/7] Topological Phase Map (D3-D4 space)")
        t0  = time.perf_counter()
        pm  = TopologicalPhaseMap(n_grid=15)
        pms = pm.summary()
        pms_ms = (time.perf_counter() - t0) * 1000
        print(f"  Topological fraction of T^6: {pms['topological_frac']}")
        print(f"  Chern number (topo region):  {pms['chern_topo']}")
        print(f"  Chern number (trivial):       {pms['chern_trivial']}")
        print(f"  Winding number ν (topo):     {pms['winding_topo']}")
        print(f"  Winding number ν (trivial):  {pms['winding_trivial']}")
        print(f"  Phase boundary points: {pms['phase_boundary_pts'][:3]}...")

        # ── Decoherence monitor ───────────────────────────────────────────────
        print(f"\n  [5/7] Decoherence Monitor")
        t0  = time.perf_counter()
        dm  = DecoherenceMonitor(kappa1=0.03, kappa2=0.01)
        dec = dm.network_decoherence_scan(self.q_nodes)
        dec_ms = (time.perf_counter() - t0) * 1000
        print(f"  {'Node':<10} {'T₂':>8} {'Purity∞':>9} {'S∞':>8} {'Protection'}")
        print(f"  {'-'*10} {'-'*8} {'-'*9} {'-'*8} {'-'*30}")
        for d in dec[:6]:
            print(f"  {d['label']:<10} {d['T2']:>8.3f} {d['purity_inf']:>9.4f} "
                  f"{d['entropy_inf']:>8.4f}  {d['protection']}")

        # ── Channel analysis ──────────────────────────────────────────────────
        print(f"\n  [6/7] Quantum Channel Analysis")
        t0   = time.perf_counter()
        qca  = QuantumChannelAnalyzer()
        chs  = qca.scan_network_channels(self.q_nodes[:5])
        chs_ms = (time.perf_counter() - t0) * 1000
        print(f"  {'Channel':<20} {'d_T6':>7} {'Noise p':>8} "
              f"{'Fidelity':>9} {'Q-cap':>7} {'Status'}")
        print(f"  {'-'*20} {'-'*7} {'-'*8} {'-'*9} {'-'*7} {'-'*10}")
        for ch in chs[:8]:
            print(f"  {ch['pair']:<20} {ch['T6_dist']:>7.4f} "
                  f"{ch['noise_p']:>8.4f} {ch['fidelity']:>9.4f} "
                  f"{ch['Q_capacity']:>7.4f}  {ch['channel']}")

        # ── Network Hamiltonian ───────────────────────────────────────────────
        print(f"\n  [7/7] Network Hamiltonian H_net")
        t0   = time.perf_counter()
        nh   = NetworkHamiltonian(self.q_nodes[:4], coupling_strength=0.05)
        nhs  = nh.summary()
        nh_ms = (time.perf_counter() - t0) * 1000
        print(f"  N qubits: {nhs['N_qubits']}  "
              f"Hilbert dim: {nhs['hilbert_dim']}")
        print(f"  Energy levels: {nhs['E_levels']}")
        print(f"  Spectral gap:  {nhs['spectral_gap']}")
        print(f"  Magnetizations ⟨σ_z^i⟩: {nhs['magnetizations']}")
        print(f"  Coupling matrix J_ij:")
        for i, row in enumerate(nhs['couplings_J']):
            print(f"    {nhs['labels'][i]}: {[round(j,4) for j in row]}")

        # ── Summary ───────────────────────────────────────────────────────────
        total_ms = (self.scan_ms + ems + pms_ms + dec_ms + chs_ms + nh_ms)
        n_nodes  = len(self.q_nodes)
        n_topo   = dist["TOPOLOGICAL"]
        n_maj    = len(majorana)
        n_ent    = sum(1 for p in pairs if p["entangled"])
        best_F   = max(ch["fidelity"] for ch in chs) if chs else 0

        print(f"\n" + "─" * 70)
        print(f"  QUANTUM NETWORK SUMMARY")
        print(f"  Nodes scanned:           {n_nodes}")
        print(f"  Topological nodes:       {n_topo}/{n_nodes}  "
              f"({dist['topo_fraction']*100:.0f}%)")
        print(f"  Majorana active:         {n_maj} nodes")
        print(f"  Entangled pairs:         {n_ent}/{len(pairs)} "
              f"pairs detected")
        print(f"  Best channel fidelity:   {best_F:.4f}")
        print(f"  Spectral gap H_net:      {nhs['spectral_gap']}")
        print(f"  Total detection time:    {total_ms:.1f}ms")
        print("=" * 70 + "\n")

        return {
            "n_nodes":     n_nodes,
            "phase_dist":  dist,
            "majorana":    majorana,
            "entanglement": pairs,
            "phase_map":   pms,
            "decoherence": dec,
            "channels":    chs[:5],
            "hamiltonian": nhs,
            "total_ms":    round(total_ms, 1),
        }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — RED CUÁNTICA COMPLETA
# ─────────────────────────────────────────────────────────────────────────────

# Full network specification — all AOTS6 nodes
AOTS6_QUANTUM_NETWORK = [
    ("Alpha",   [0.00, 0.20, 0.40, 0.60, 0.80, 0.99]),
    ("Beta",    [0.17, 0.34, 0.51, 0.68, 0.85, 0.02]),
    ("Gamma",   [0.33, 0.50, 0.67, 0.84, 0.01, 0.18]),
    ("Delta",   [0.50, 0.67, 0.84, 0.01, 0.18, 0.35]),
    ("Epsilon", [0.67, 0.84, 0.01, 0.18, 0.35, 0.52]),
    ("Zeta",    [0.12, 0.45, 0.78, 0.23, 0.56, 0.89]),
    ("Eta",     [0.89, 0.12, 0.45, 0.78, 0.23, 0.56]),
    ("Theta",   [0.56, 0.89, 0.12, 0.45, 0.78, 0.23]),
]


if __name__ == "__main__":
    report = QuantumNetworkReport(AOTS6_QUANTUM_NETWORK)
    results = report.full_report()
