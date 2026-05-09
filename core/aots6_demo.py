# SPDX-License-Identifier: LicenseRef-AOTS6-ARR-1.0
# Copyright (c) 2025-2026 Alfredo Jhovany Alfaro Garcia - All Rights Reserved
"""aots6_demo.py — AOTS6 Complete End-to-End Demonstration"""

from aots6_core       import AOTS6Node, ToroidalCoordinate, OntologicalGraph, AOTS6Edge
from aots6_network    import AOTS6Network
from aots6_validation import AOTS6Validator
from aots6_quantum    import (AOTS6QuantumNode, run_quantum_validation,
                               FluxQubitHamiltonian, LindbladEvolution)
import numpy as np

print("\nAOTS6 v0.1.0 — Complete System Demo")
print("=" * 62)

# 1. Core validation
print(AOTS6Validator().run_all().summary())

# 2. Quantum validation
q_results = run_quantum_validation()

# 3. Integrated network + quantum
print("Integrated Network + Quantum")
print("-" * 48)
net   = AOTS6Network()
coords = [
    [0.00, 0.20, 0.40, 0.60, 0.80, 0.99],
    [0.17, 0.34, 0.51, 0.68, 0.85, 0.02],
    [0.33, 0.50, 0.67, 0.84, 0.01, 0.18],
    [0.50, 0.67, 0.84, 0.01, 0.18, 0.35],
    [0.67, 0.84, 0.01, 0.18, 0.35, 0.52],
]
labels = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
peers  = [net.add_peer(l, ToroidalCoordinate(c)) for l, c in zip(labels, coords)]
ids    = net.peer_ids()
peers[0].link(ids[1], "feeds");   peers[1].link(ids[2], "delegates_to")
peers[0].evolve({"load": 0.25});  peers[1].evolve({"jobs": 14})

q_nodes = [AOTS6QuantumNode(p.local_node.label, p.local_node.coordinate.components)
           for p in peers]

print(f"\n  {'Peer':8s}  {'Verify':6s}  {'Phase':12s}  {'MajGap':7s}  {'QGap':7s}")
for peer, qn in zip(peers, q_nodes):
    ok  = all(peer.verify().values())
    kp  = qn.kitaev_phase()
    fq  = qn.flux_qubit()
    print(f"  {peer.local_node.label:8s}  "
          f"{'OK' if ok else '!!':6s}  "
          f"{kp['phase']:12s}  "
          f"{kp['majorana_gap']:.4f}  "
          f"{fq['qubit_gap']:.4f}")

# 4. T^6 distance matrix
print("\n  T^6 pairwise distances:")
names = [p.local_node.label[:5] for p in peers]
print("  " + " "*8 + "".join(f"{n:>7}" for n in names))
for i, pi in enumerate(peers):
    row = f"  {names[i]:<8}"
    for pj in peers:
        d = pi.local_node.coordinate.distance(pj.local_node.coordinate)
        row += f"  {d:4.3f}"
    print(row)

# 5. Lindblad decoherence
print("\n  Lindblad decoherence (Alpha qubit):")
fq2   = FluxQubitHamiltonian(E_J=q_nodes[0].josephson_ej, E_L=1.0,
                               Phi_ext=q_nodes[0].coord[0], n_max=2)
H4    = fq2.build()[:4, :4]
Lk    = np.zeros((4,4), dtype=complex); Lk[0,1] = 0.1
lind  = LindbladEvolution(H4, [Lk])
rho0  = np.diag([0.6, 0.3, 0.08, 0.02]).astype(complex)
for t, rho in zip([0,1,2,3,4,5], lind.evolve(rho0, np.linspace(0,5,6))):
    p = lind.purity(rho)
    S = lind.von_neumann_entropy(rho)
    print(f"    t={t}  purity={p:.4f}  S={S:.4f}")

# 6. Summary
s = net.network_status()
core_p = sum(1 for r in AOTS6Validator().run_all().results if r.passed)
q_p    = sum(1 for r in q_results if r["passed"])
print("\n" + "=" * 62)
print(" AOTS6 v0.1.0 — System Summary")
print("=" * 62)
print(f"  Core protocol tests   : {core_p}/7  PASS")
print(f"  Quantum framework     : {q_p}/8  PASS")
print(f"  Network peers         : {s['peers']}")
print(f"  Messages exchanged    : {s['messages_sent']}")
print(f"  Total PASS            : {core_p + q_p}/15")
print("=" * 62 + "\n")
