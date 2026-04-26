import math
import pytest
from aots6_core import ToroidalCoordinate, AOTS6Node, AOTS6Edge, OntologicalGraph, identity_hash

def make_coord():
    return ToroidalCoordinate([0.1,0.2,0.3,0.4,0.5,0.6])

def make_node(label="test"):
    return AOTS6Node(label=label, coordinate=make_coord())

def test_distancia_cero():
    c = make_coord()
    assert c.distance(c) == pytest.approx(0.0)

def test_distancia_simetrica():
    p = ToroidalCoordinate([0.1,0.2,0.3,0.4,0.5,0.6])
    q = ToroidalCoordinate([0.9,0.8,0.7,0.6,0.5,0.4])
    assert p.distance(q) == pytest.approx(q.distance(p))

def test_distancia_toroidal_wrapping():
    p = ToroidalCoordinate([0.0,0.5,0.5,0.5,0.5,0.5])
    q = ToroidalCoordinate([0.9,0.5,0.5,0.5,0.5,0.5])
    assert p.distance(q) == pytest.approx(0.1, abs=1e-9)

def test_identity_hash_determinista():
    h1 = identity_hash("n1", {"x":1})
    h2 = identity_hash("n1", {"x":1})
    assert h1 == h2

def test_nodo_tiene_identity():
    n = make_node()
    assert len(n.identity) == 64

def test_nodo_verifica_integridad():
    n = make_node()
    assert n.verify_identity() is True

def test_nodo_evoluciona():
    n = make_node()
    antes = n.identity
    n.evolve({"estado": "nuevo"})
    assert n.identity != antes

def test_grafo_agrega_nodo():
    g = OntologicalGraph()
    n = make_node("alpha")
    g.add_node(n)
    assert n.node_id in g._nodes

def test_grafo_agrega_arista():
    g = OntologicalGraph()
    a = make_node("a")
    b = make_node("b")
    g.add_node(a)
    g.add_node(b)
    e = AOTS6Edge(source_id=a.node_id, target_id=b.node_id, label="link")
    assert g.add_edge(e) is True

def test_grafo_hash_cambia():
    g = OntologicalGraph()
    h1 = g.graph_hash()
    g.add_node(make_node("nuevo"))
    assert g.graph_hash() != h1
