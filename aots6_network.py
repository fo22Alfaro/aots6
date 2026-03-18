# SPDX-License-Identifier: LicenseRef-AOTS6-ARR-1.0
# Copyright (c) 2025-2026 Alfredo Jhovany Alfaro Garcia - All Rights Reserved
from __future__ import annotations
import hashlib,json,time,uuid,threading
from dataclasses import dataclass,field
from enum import Enum
from typing import Any,Callable,Dict,List,Optional
from aots6_core import AOTS6Edge,AOTS6Node,OntologicalGraph,ToroidalCoordinate,identity_hash

class MsgType(str,Enum):
    INIT="INIT"; LINK="LINK"; VERIFY="VERIFY"; EVOLVE="EVOLVE"; HEARTBEAT="HEARTBEAT"

@dataclass
class AOTS6Message:
    msg_type:MsgType; sender_id:str
    payload:Dict[str,Any]=field(default_factory=dict)
    msg_id:str=field(default_factory=lambda:str(uuid.uuid4()))
    timestamp:float=field(default_factory=time.time)
    signature:str=field(init=False,default="")
    def __post_init__(self): self.signature=self._sign()
    def _sign(self):
        b=json.dumps({"msg_id":self.msg_id,"sender":self.sender_id,"type":self.msg_type,
                      "payload":self.payload,"ts":self.timestamp},sort_keys=True).encode()
        return hashlib.sha256(b).hexdigest()[:32]
    def verify_signature(self): return self.signature==self._sign()
    def to_dict(self): return {"msg_id":self.msg_id,"type":self.msg_type,
                               "sender_id":self.sender_id,"payload":self.payload,
                               "timestamp":self.timestamp,"signature":self.signature}

class MessageBus:
    def __init__(self): self._subscribers={}; self._log=[]; self._lock=threading.Lock()
    def subscribe(self,pid,h):
        with self._lock: self._subscribers[pid]=h
    def publish(self,msg,target_id=None):
        with self._lock:
            self._log.append(msg.to_dict())
            if target_id:
                h=self._subscribers.get(target_id)
                if h: h(msg)
            else:
                for pid,h in self._subscribers.items():
                    if pid!=msg.sender_id: h(msg)
    def message_log(self): return list(self._log)

class AOTS6Peer:
    def __init__(self,label,coordinate,bus,context=None):
        self._bus=bus; self._log=[]
        self.local_node=AOTS6Node(label=label,coordinate=coordinate,context=context or{"peer":label})
        self.peer_id=self.local_node.node_id
        self.graph=OntologicalGraph(); self.graph.add_node(self.local_node)
        self._known={}
        bus.subscribe(self.peer_id,self._on_message)
        self._emit(MsgType.INIT,{"label":label,"identity":self.local_node.identity,
                                  "coordinate":self.local_node.coordinate.to_dict()})
    def _emit(self,t,p,target=None):
        self._bus.publish(AOTS6Message(msg_type=t,sender_id=self.peer_id,payload=p),target_id=target)
    def link(self,tid,label,weight=1.0):
        if tid not in self._known: return False
        e=AOTS6Edge(self.peer_id,tid,label,weight)
        ok=self.graph.add_edge(e)
        if ok: self._emit(MsgType.LINK,{"target":tid,"label":label,"sig":e.signature()})
        return ok
    def verify(self):
        r=self.graph.verify_all()
        self._emit(MsgType.VERIFY,{"hash":self.graph.graph_hash()[:16],"ok":all(r.values())})
        return r
    def evolve(self,delta):
        m=self.local_node.evolve(delta)
        self._emit(MsgType.EVOLVE,{"new_identity":self.local_node.identity,"keys":list(delta.keys())})
        return m
    def heartbeat(self): self._emit(MsgType.HEARTBEAT,{"identity":self.local_node.identity})
    def _on_message(self,msg):
        if not msg.verify_signature(): return
        if msg.msg_type==MsgType.INIT:
            comp=list(msg.payload.get("coordinate",{}).values())
            if len(comp)!=6: comp=[0.0]*6
            rn=AOTS6Node(label=msg.payload.get("label","?"),coordinate=ToroidalCoordinate(comp),
                         context={"remote":True},node_id=msg.sender_id,is_remote=True)
            self._known[msg.sender_id]=rn; self.graph.add_node(rn)
            self._log.append(f"INIT <- {msg.payload.get('label')}")
    def status(self):
        return {"peer":self.local_node.label,"identity":self.local_node.identity[:16]+"...",
                "graph":self.graph.stats(),"known":len(self._known),"log":self._log[-3:]}

class AOTS6Network:
    def __init__(self): self.bus=MessageBus(); self.peers={}
    def add_peer(self,label,coordinate=None,context=None):
        import random
        if coordinate is None: coordinate=ToroidalCoordinate([random.random() for _ in range(6)])
        p=AOTS6Peer(label,coordinate,self.bus,context); self.peers[p.peer_id]=p; return p
    def peer_ids(self): return list(self.peers.keys())
    def network_status(self):
        return {"peers":len(self.peers),"messages":len(self.bus.message_log()),
                "statuses":[p.status() for p in self.peers.values()]}
