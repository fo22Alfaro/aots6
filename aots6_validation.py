# SPDX-License-Identifier: LicenseRef-AOTS6-ARR-1.0
# Copyright (c) 2025-2026 Alfredo Jhovany Alfaro Garcia - All Rights Reserved
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List
from aots6_core import AOTS6Edge, AOTS6Node, OntologicalGraph, ToroidalCoordinate, identity_hash
from aots6_network import AOTS6Message, AOTS6Network, MsgType

@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    def __str__(self):
        s = "PASS" if self.passed else "FAIL"
        i = "+" if self.passed else "x"
        line1 = "  [" + i + "] [" + s + "] " + self.name.ljust(40) + " (" + str(round(self.duration_ms,1)) + "ms)"
        return line1 + "\n       " + self.message

class AOTS6Validator:
    def __init__(self): self.results = []
    def _run(self, name, fn):
        t0 = time.perf_counter()
        try:
            info = fn()
            passed = info.pop("passed", True)
            msg = info.pop("message", "OK")
        except Exception as e:
            passed = False; msg = str(e); info = {}
        r = TestResult(name, passed, msg, (time.perf_counter()-t0)*1000, info)
        self.results.append(r)
        return r
    def tc01_identity_stability(self):
        def run():
            ctx = {"v": 1}
            h1 = identity_hash("A", ctx)
            h2 = identity_hash("A", ctx)
            ok = h1 == h2 and h1 != identity_hash("B", ctx) and h1 != identity_hash("A", {"v": 2})
            return {"passed": ok, "message": "Identical inputs same hash; different inputs diverge"}
        return self._run("TC-01 Identity Stability", run)
    def tc02_graph_consistency(self):
        def run():
            g = OntologicalGraph()
            n1 = AOTS6Node("a", ToroidalCoordinate([0.1]*6))
            n2 = AOTS6Node("b", ToroidalCoordinate([0.5]*6))
            g.add_node(n1); g.add_node(n2); hb = g.graph_hash()
            ok = (g.add_edge(AOTS6Edge(n1.node_id, n2.node_id, "rel")) and
                  hb != g.graph_hash() and
                  not g.add_edge(AOTS6Edge(n1.node_id, "ghost", "bad")) and
                  all(g.verify_all().values()))
            return {"passed": ok, "message": "Hash updates on mutation; invalid edges rejected"}
        return self._run("TC-02 Graph Consistency", run)
    def tc03_evolution_integrity(self):
        def run():
            n = AOTS6Node("g", ToroidalCoordinate([0.0]*6), context={"s": "init"})
            id0 = n.identity; n.evolve({}); id1 = n.identity
            n.evolve({"s": "v2"}); id2 = n.identity
            return {"passed": id0 == id1 and id1 != id2, "message": "Null delta preserves; non-null mutates"}
        return self._run("TC-03 Evolution Integrity", run)
    def tc04_toroidal_symmetry(self):
        def run():
            c1 = ToroidalCoordinate([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
            c2 = ToroidalCoordinate([0.9, 0.8, 0.7, 0.6, 0.5, 0.4])
            ok = abs(c1.distance(c2) - c2.distance(c1)) < 1e-10 and c1.distance(c1) < 1e-10
            return {"passed": ok, "message": "d(a,b)=d(b,a), d(a,a)=0"}
        return self._run("TC-04 Toroidal Distance Symmetry", run)
    def tc05_message_signatures(self):
        def run():
            m = AOTS6Message(msg_type=MsgType.INIT, sender_id="x", payload={"l": "t"})
            v1 = m.verify_signature(); m.payload["evil"] = "x"; v2 = m.verify_signature()
            return {"passed": v1 and not v2, "message": "Valid before tamper; invalid after"}
        return self._run("TC-05 Message Signature Validity", run)
    def tc06_network_convergence(self):
        def run():
            net = AOTS6Network()
            p1 = net.add_peer("A", ToroidalCoordinate([0.1]*6))
            p2 = net.add_peer("B", ToroidalCoordinate([0.5]*6))
            net.add_peer("C", ToroidalCoordinate([0.9]*6))
            ids = net.peer_ids(); linked = p1.link(ids[1], "comm")
            p2.evolve({"state": "active"})
            return {"passed": linked and all(p1.verify().values()), "message": "INIT+LINK+EVOLVE+VERIFY OK"}
        return self._run("TC-06 Network Convergence", run)
    def tc07_consistency_constraint(self):
        def run():
            n = AOTS6Node("d", ToroidalCoordinate([0.3]*6), context={"k": "v"})
            snaps = [n.identity]
            for i in range(5):
                n.evolve({"step": i}); snaps.append(n.identity)
            return {"passed": len(set(snaps)) == 6 and len(n._state_history) == 6,
                    "message": "Each distinct delta produces unique snapshot"}
        return self._run("TC-07 Consistency Constraint", run)
    def run_all(self):
        for tc in [self.tc01_identity_stability, self.tc02_graph_consistency,
                   self.tc03_evolution_integrity, self.tc04_toroidal_symmetry,
                   self.tc05_message_signatures, self.tc06_network_convergence,
                   self.tc07_consistency_constraint]:
            tc()
        return self
    def summary(self):
        p = sum(1 for r in self.results if r.passed)
        t = len(self.results)
        ms = sum(r.duration_ms for r in self.results)
        lines = ["", "="*56, " AOTS6 Validation -- draft-alfaro-aots6-01", "="*56]
        for r in self.results: lines.append(str(r))
        lines += ["─"*56, "  Result: " + str(p) + "/" + str(t) + " passed  |  " + str(round(ms,1)) + "ms", "="*56]
        return "\n".join(lines)
