# SPDX-License-Identifier: LicenseRef-AOTS6-ARR-1.0
# Copyright (c) 2025-2026 Alfredo Jhovany Alfaro Garcia - All Rights Reserved
from __future__ import annotations
import hashlib, json, time, uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class Dimension(Enum):
    D0_TEMPORAL=0; D1_SPATIAL=1; D2_LOGICAL=2
    D3_MEMORY=3;   D4_NETWORK=4; D5_INFERENCE=5

@dataclass
class ToroidalCoordinate:
    components: List[float] = field(default_factory=lambda:[0.0]*6)
    def __post_init__(self):
        if len(self.components)!=6: raise ValueError("T^6 needs 6 components")
        self.components=[c%1.0 for c in self.components]
    def distance(self,other):
        return sum(min(abs(a-b),1-abs(a-b))**2 for a,b in zip(self.components,other.components))**0.5
    def to_dict(self):
        return {d.name:round(v,6) for d,v in zip(Dimension,self.components)}

def identity_hash(node_id,context,timestamp=None):
    t=timestamp if timestamp is not None else 0
    p=json.dumps({"node_id":node_id,"context":context,"t":t},sort_keys=True).encode()
    return hashlib.sha256(p).hexdigest()

@dataclass
class AOTS6Node:
    label:str; coordinate:ToroidalCoordinate
    context:Dict[str,Any]=field(default_factory=dict)
    node_id:str=field(default_factory=lambda:str(uuid.uuid4()))
    is_remote:bool=False
    _created_at:float=field(default_factory=time.time,init=False)
    _identity:str=field(init=False,default="")
    _state_history:List[Dict]=field(default_factory=list,init=False)
    def __post_init__(self):
        self._identity=identity_hash(self.node_id,self.context); self._snapshot()
    @property
    def identity(self): return self._identity
    def verify_identity(self): return self._identity==identity_hash(self.node_id,self.context)
    def evolve(self,delta):
        old=self._identity; self.context={**self.context,**delta}
        self._identity=identity_hash(self.node_id,self.context); self._snapshot(delta)
        return old!=self._identity
    def _snapshot(self,delta=None):
        self._state_history.append({"t":time.time(),"identity":self._identity,"delta":delta})

@dataclass
class AOTS6Edge:
    source_id:str; target_id:str; label:str; weight:float=1.0
    edge_id:str=field(default_factory=lambda:str(uuid.uuid4()))
    metadata:Dict[str,Any]=field(default_factory=dict)
    created_at:float=field(default_factory=time.time)
    def signature(self):
        return hashlib.sha256(f"{self.source_id}|{self.target_id}|{self.label}|{self.weight}".encode()).hexdigest()[:16]

class OntologicalGraph:
    def __init__(self): self._nodes={}; self._edges=[]; self._adj={}
    def add_node(self,node): self._nodes[node.node_id]=node; self._adj.setdefault(node.node_id,[])
    def add_edge(self,edge):
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes: return False
        self._edges.append(edge); self._adj[edge.source_id].append(edge.edge_id); return True
    def verify_all(self,local_only=True):
        return {nid:n.verify_identity() for nid,n in self._nodes.items() if not(local_only and n.is_remote)}
    def graph_hash(self):
        s={"nodes":sorted(n.identity for n in self._nodes.values()),
           "edges":sorted(e.signature() for e in self._edges)}
        return hashlib.sha256(json.dumps(s,sort_keys=True).encode()).hexdigest()
    def stats(self): return {"nodes":len(self._nodes),"edges":len(self._edges),"hash":self.graph_hash()[:16]}
