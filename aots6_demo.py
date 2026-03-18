# SPDX-License-Identifier: LicenseRef-AOTS6-ARR-1.0
# Copyright (c) 2025-2026 Alfredo Jhovany Alfaro Garcia - All Rights Reserved
from aots6_core import ToroidalCoordinate
from aots6_network import AOTS6Network
from aots6_validation import AOTS6Validator

print(AOTS6Validator().run_all().summary())

net=AOTS6Network()
alpha=net.add_peer("Alpha",  ToroidalCoordinate([0.00,0.20,0.40,0.60,0.80,0.99]))
beta =net.add_peer("Beta",   ToroidalCoordinate([0.17,0.34,0.51,0.68,0.85,0.02]))
gamma=net.add_peer("Gamma",  ToroidalCoordinate([0.33,0.50,0.67,0.84,0.01,0.18]))
delta=net.add_peer("Delta",  ToroidalCoordinate([0.50,0.67,0.84,0.01,0.18,0.35]))
eps  =net.add_peer("Epsilon",ToroidalCoordinate([0.67,0.84,0.01,0.18,0.35,0.52]))
ids=net.peer_ids()
alpha.link(ids[1],"feeds"); beta.link(ids[2],"delegates_to")
alpha.evolve({"load":0.25}); beta.evolve({"jobs":14})
print("\nPeer verification:")
for p in [alpha,beta,gamma,delta,eps]:
    ok=all(p.verify().values())
    print(f"  {'OK' if ok else 'FAIL'}  {p.local_node.label}")
s=net.network_status()
print(f"\npeers:{s['peers']}  messages:{s['messages']}")
print("\nT^6 distances:")
peers=[alpha,beta,gamma,delta,eps]
names=[p.local_node.label[:5] for p in peers]
print("  "+(" "*7)+"".join(f"{n:>7}" for n in names))
for i,pi in enumerate(peers):
    row=f"  {names[i]:<7}"
    for pj in peers: row+=f"  {pi.local_node.coordinate.distance(pj.local_node.coordinate):4.3f}"
    print(row)
print("\nAOTS6 demo complete.")
