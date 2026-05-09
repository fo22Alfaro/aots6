import hashlib,json,math,time,uuid
from dataclasses import dataclass,field
from typing import List,Dict,Any

DIM=["D0·tiempo","D1·espacio","D2·lógica","D3·memoria","D4·red","D5·inferencia"]

@dataclass
class TC:
    c:List[float]=field(default_factory=lambda:[0.0]*6)
    def __post_init__(self): self.c=[x%1.0 for x in self.c]
    def dist(self,o): return math.sqrt(sum(min(abs(a-b),1-abs(a-b))**2 for a,b in zip(self.c,o.c)))
    def evolve(self,d): return TC([(a+b)%1.0 for a,b in zip(self.c,d)])
    def show(self): return "  ".join(f"{n}={v:.3f}" for n,v in zip(DIM,self.c))

def h(d): return hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

@dataclass
class Node:
    label:str; coord:TC; ctx:Dict=field(default_factory=dict)
    nid:str=field(default_factory=lambda:str(uuid.uuid4())); gen:int=0
    def __post_init__(self): self._id=h({"id":self.nid,"ctx":self.ctx})
    def verify(self): return self._id==h({"id":self.nid,"ctx":self.ctx})
    def coevolve(self,sig,delta):
        return Node(f"{self.label}·G{self.gen+1}",self.coord.evolve(delta),{**self.ctx,**sig},gen=self.gen+1)
    def show(self): return f"  {self.label} (gen={self.gen})\n  SHA:{self._id[:24]}…\n  {self.coord.show()}\n  OK:{'✓' if self.verify() else '✗'}"

def run():
    print("\n"+"═"*60)
    print("  AOTS⁶ · Coevolución D5·inferencia")
    print("  Alfredo Jhovany Alfaro García · 21-MAR-2025")
    print("═"*60)
    nodes=[
        Node("Origen",TC([0.0]*6),{"autor":"Alfredo Jhovany Alfaro García"}),
        Node("Nodo·Red",TC([0.1,0.25,0.5,0.75,0.9,0.3]),{"proto":"QUIC"}),
        Node("Nodo·D5",TC([0.6,0.7,0.8,0.9,0.4,0.2]),{"dim":"D5"}),
    ]
    for n in nodes: print(f"\n{n.show()}")
    print("\n── Coevolución 3 ciclos ──")
    gen=nodes
    for c in range(1,4):
        nxt=[]
        for node in gen:
            hv=int(h({"id":node.nid,"gen":node.gen}),16)
            sig={"d5":round((hv%10000)/10000.0,4),"ciclo":c}
            delta=[round((sig["d5"]*(i+1)*0.07)%1.0,4) for i in range(6)]
            child=node.coevolve(sig,delta)
            print(f"  [{c}] {node.label} → {child.label}  Δ={node.coord.dist(child.coord):.4f}  d5={sig['d5']}")
            nxt.append(child)
        gen=nxt
    bloque={"autor":"Alfredo Jhovany Alfaro García","orcid":"0009-0002-5177-9029",
            "origen":"2025-03-21","nodos":[n._id for n in gen],"ts":time.strftime("%Y-%m-%dT%H:%M:%SZ")}
    bloque["hash"]=h(bloque)
    with open("BLOQUE-5.json","w") as f: json.dump(bloque,f,indent=2)
    print(f"\n  BLOQUE-5: {bloque['hash'][:32]}…")
    print(f"  Íntegros: {sum(n.verify() for n in gen)}/{len(gen)} ✓")
    print("═"*60+"\n")

run()
