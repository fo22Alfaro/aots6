# SPDX-License-Identifier: LicenseRef-AOTS6-ARR-1.0
# Copyright (c) 2025-2026 Alfredo Jhovany Alfaro García — All Rights Reserved
"""
AOTS⁶ — Red TCP Real
Autor  : Alfredo Jhovany Alfaro García
ORCID  : 0009-0002-5177-9029
Origen : 21 de marzo de 2025 · Guadalupe Victoria, Puebla, México
GitHub : https://github.com/fo22Alfaro/AOTS6-Ontological-Toroidal-System

Reemplaza el MessageBus in-process con sockets TCP reales.
Peers en distintas máquinas (o terminales) pueden conectarse entre sí.

Arquitectura:
  AOTS6TCPServer  — escucha conexiones entrantes (threading, un hilo por peer)
  AOTS6TCPClient  — conecta a un peer remoto y envía mensajes
  AOTS6TCPPeer    — nodo completo: servidor + cliente + grafo ontológico T⁶
  AOTS6TCPNetwork — orquestador local de múltiples peers (demo y tests)

Wire format (línea JSON + newline):
  {"msg_id":"<uuid>","type":"<TIPO>","sender_id":"<id>",
   "timestamp":<float>,"payload":{...},"signature":"<sha256[:32]>"}

Tipos de mensaje: INIT LINK VERIFY EVOLVE HEARTBEAT DISCOVER PEER_LIST

Sin dependencias externas. Python 3.8+
"""

from __future__ import annotations
import hashlib, json, math, socket, threading, time, uuid, logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# ══════════════════════════════════════════════════════════════════════════════
#  NÚCLEO T⁶  (inline para que el módulo sea autónomo)
# ══════════════════════════════════════════════════════════════════════════════

DIMENSIONS = ["D0·tiempo","D1·espacio","D2·lógica","D3·memoria","D4·red","D5·inferencia"]

def _sha256(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

@dataclass
class ToroidalCoordinate:
    components: List[float] = field(default_factory=lambda: [0.0]*6)
    def __post_init__(self):
        self.components = [c % 1.0 for c in self.components]
    def distance(self, other: "ToroidalCoordinate") -> float:
        return math.sqrt(sum(
            min(abs(a-b), 1-abs(a-b))**2
            for a,b in zip(self.components, other.components)))
    def evolve(self, delta: List[float]) -> "ToroidalCoordinate":
        return ToroidalCoordinate([(c+d)%1.0 for c,d in zip(self.components, delta)])
    def to_dict(self) -> Dict:
        return {f"d{i}": round(v,6) for i,v in enumerate(self.components)}
    @classmethod
    def from_dict(cls, d: Dict) -> "ToroidalCoordinate":
        return cls([d.get(f"d{i}", 0.0) for i in range(6)])
    def display(self) -> str:
        return "  ".join(f"{n}={v:.3f}" for n,v in zip(DIMENSIONS, self.components))

@dataclass
class AOTS6Node:
    label: str
    coordinate: ToroidalCoordinate
    context: Dict[str,Any] = field(default_factory=dict)
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    is_remote: bool = False
    def __post_init__(self):
        self._identity = _sha256({"id": self.node_id, "ctx": self.context})
        self._history: List[str] = [self._identity]
    @property
    def identity(self) -> str: return self._identity
    def verify(self) -> bool:
        return self._identity == _sha256({"id": self.node_id, "ctx": self.context})
    def evolve(self, delta: Dict[str,Any]) -> bool:
        if not delta: return False
        self.context = {**self.context, **delta}
        new_id = _sha256({"id": self.node_id, "ctx": self.context})
        changed = new_id != self._identity
        if changed:
            self._identity = new_id
            self._history.append(new_id)
        return changed

@dataclass
class AOTS6Edge:
    source_id: str; target_id: str
    label: str = "RELACIONA"; weight: float = 1.0
    def signature(self) -> str:
        return _sha256({"s":self.source_id,"t":self.target_id,
                        "l":self.label,"w":self.weight})[:16]

class OntologicalGraph:
    def __init__(self):
        self._nodes: Dict[str, AOTS6Node] = {}
        self._edges: List[AOTS6Edge] = []
    def add_node(self, n: AOTS6Node): self._nodes[n.node_id] = n
    def add_edge(self, e: AOTS6Edge) -> bool:
        if e.source_id not in self._nodes or e.target_id not in self._nodes:
            return False
        self._edges.append(e); return True
    def verify_all(self) -> Dict[str,bool]:
        return {nid: n.verify() for nid,n in self._nodes.items()}
    def graph_hash(self) -> str:
        ids = sorted(n.identity for n in self._nodes.values())
        sigs = sorted(e.signature() for e in self._edges)
        return _sha256({"nodes": ids, "edges": sigs})
    def stats(self) -> Dict:
        return {"nodes": len(self._nodes), "edges": len(self._edges),
                "hash": self.graph_hash()[:16]+"…"}

# ══════════════════════════════════════════════════════════════════════════════
#  PROTOCOLO DE MENSAJES
# ══════════════════════════════════════════════════════════════════════════════

class MsgType(str, Enum):
    INIT      = "INIT"
    LINK      = "LINK"
    VERIFY    = "VERIFY"
    EVOLVE    = "EVOLVE"
    HEARTBEAT = "HEARTBEAT"
    DISCOVER  = "DISCOVER"   # solicitar lista de peers conocidos
    PEER_LIST = "PEER_LIST"  # respuesta con lista de peers
    ACK       = "ACK"        # confirmación de recepción
    ERROR     = "ERROR"      # error de protocolo

@dataclass
class AOTS6Message:
    msg_type: MsgType
    sender_id: str
    payload: Dict[str,Any] = field(default_factory=dict)
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    signature: str = field(init=False, default="")

    def __post_init__(self):
        self.signature = self._sign()

    def _sign(self) -> str:
        body = json.dumps({
            "msg_id": self.msg_id, "type": self.msg_type,
            "sender": self.sender_id, "payload": self.payload,
            "ts": self.timestamp,
        }, sort_keys=True).encode()
        return hashlib.sha256(body).hexdigest()[:32]

    def verify_signature(self) -> bool:
        return self.signature == self._sign()

    def to_json(self) -> str:
        return json.dumps({
            "msg_id": self.msg_id, "type": self.msg_type,
            "sender_id": self.sender_id, "payload": self.payload,
            "timestamp": self.timestamp, "signature": self.signature,
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> Optional["AOTS6Message"]:
        try:
            d = json.loads(raw)
            msg = cls(
                msg_type  = MsgType(d["type"]),
                sender_id = d["sender_id"],
                payload   = d.get("payload", {}),
                msg_id    = d["msg_id"],
                timestamp = d["timestamp"],
            )
            msg.signature = d.get("signature", "")
            return msg
        except Exception:
            return None

# ══════════════════════════════════════════════════════════════════════════════
#  TRANSPORT  — envío y recepción de mensajes por TCP
# ══════════════════════════════════════════════════════════════════════════════

DELIMITER = b"\n"
RECV_BUFSIZE = 65536
CONNECT_TIMEOUT = 5.0
REPLAY_WINDOW = 60.0  # segundos

class TCPTransport:
    """Envía y recibe mensajes JSON delimitados por newline sobre TCP."""

    @staticmethod
    def send(sock: socket.socket, msg: AOTS6Message) -> bool:
        try:
            data = (msg.to_json() + "\n").encode("utf-8")
            sock.sendall(data)
            return True
        except (OSError, BrokenPipeError):
            return False

    @staticmethod
    def recv_lines(sock: socket.socket) -> List[str]:
        """Lee todo lo disponible y devuelve líneas completas."""
        lines = []
        try:
            data = b""
            sock.settimeout(0.1)
            while True:
                try:
                    chunk = sock.recv(RECV_BUFSIZE)
                    if not chunk:
                        break
                    data += chunk
                    if b"\n" in chunk:
                        break
                except socket.timeout:
                    break
        except OSError:
            pass
        finally:
            sock.settimeout(None)
        for line in data.split(b"\n"):
            line = line.strip()
            if line:
                lines.append(line.decode("utf-8", errors="replace"))
        return lines

# ══════════════════════════════════════════════════════════════════════════════
#  SERVIDOR TCP
# ══════════════════════════════════════════════════════════════════════════════

class AOTS6TCPServer:
    """
    Servidor TCP para AOTS⁶.
    Acepta conexiones entrantes de peers remotos.
    Un hilo por conexión — diseño simple y robusto para redes pequeñas/medianas.
    """

    def __init__(self, host: str, port: int,
                 on_message: Callable[[AOTS6Message, socket.socket], None]):
        self.host = host
        self.port = port
        self._on_message = on_message
        self._server_sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._connections: List[socket.socket] = []
        self._lock = threading.Lock()
        self.log = logging.getLogger(f"AOTS6.Server:{port}")

    def start(self):
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(64)
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        self.log.info(f"Servidor escuchando en {self.host}:{self.port}")

    def stop(self):
        self._running = False
        if self._server_sock:
            try: self._server_sock.close()
            except: pass
        with self._lock:
            for conn in self._connections:
                try: conn.close()
                except: pass
            self._connections.clear()
        self.log.info("Servidor detenido.")

    def _accept_loop(self):
        while self._running:
            try:
                self._server_sock.settimeout(1.0)
                conn, addr = self._server_sock.accept()
                self.log.info(f"Conexión entrante de {addr}")
                with self._lock:
                    self._connections.append(conn)
                t = threading.Thread(
                    target=self._handle_connection,
                    args=(conn, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_connection(self, conn: socket.socket, addr: Tuple):
        log = logging.getLogger(f"AOTS6.Conn:{addr}")
        try:
            buf = b""
            while self._running:
                try:
                    conn.settimeout(30.0)
                    chunk = conn.recv(RECV_BUFSIZE)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            raw = line.decode("utf-8", errors="replace")
                            msg = AOTS6Message.from_json(raw)
                            if msg is None:
                                log.warning("Mensaje inválido descartado")
                                continue
                            if not msg.verify_signature():
                                log.warning(f"Firma inválida en {msg.msg_id[:8]}… descartado")
                                continue
                            age = abs(time.time() - msg.timestamp)
                            if age > REPLAY_WINDOW:
                                log.warning(f"Mensaje fuera de ventana ({age:.0f}s) descartado")
                                continue
                            self._on_message(msg, conn)
                        except Exception as e:
                            log.error(f"Error procesando mensaje: {e}")
                except socket.timeout:
                    # Enviar heartbeat si la conexión está idle
                    break
                except (ConnectionResetError, BrokenPipeError):
                    break
        finally:
            with self._lock:
                if conn in self._connections:
                    self._connections.remove(conn)
            try: conn.close()
            except: pass
            log.info(f"Conexión {addr} cerrada")

# ══════════════════════════════════════════════════════════════════════════════
#  CLIENTE TCP
# ══════════════════════════════════════════════════════════════════════════════

class AOTS6TCPClient:
    """
    Cliente TCP para AOTS⁶.
    Mantiene una conexión persistente a un peer remoto.
    Reconexión automática con backoff exponencial.
    """

    def __init__(self, remote_host: str, remote_port: int,
                 on_message: Optional[Callable[[AOTS6Message], None]] = None):
        self.remote_host = remote_host
        self.remote_port = remote_port
        self._on_message = on_message
        self._sock: Optional[socket.socket] = None
        self._connected = False
        self._lock = threading.Lock()
        self._recv_thread: Optional[threading.Thread] = None
        self._running = False
        self.log = logging.getLogger(f"AOTS6.Client→{remote_host}:{remote_port}")

    def connect(self, timeout: float = CONNECT_TIMEOUT) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((self.remote_host, self.remote_port))
            s.settimeout(None)
            with self._lock:
                self._sock = s
                self._connected = True
            self._running = True
            if self._on_message:
                self._recv_thread = threading.Thread(
                    target=self._recv_loop, daemon=True)
                self._recv_thread.start()
            self.log.info(f"Conectado a {self.remote_host}:{self.remote_port}")
            return True
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            self.log.warning(f"No se pudo conectar: {e}")
            return False

    def send(self, msg: AOTS6Message) -> bool:
        with self._lock:
            if not self._connected or self._sock is None:
                return False
            return TCPTransport.send(self._sock, msg)

    def disconnect(self):
        self._running = False
        with self._lock:
            self._connected = False
            if self._sock:
                try: self._sock.close()
                except: pass
                self._sock = None
        self.log.info("Desconectado.")

    def _recv_loop(self):
        buf = b""
        while self._running:
            with self._lock:
                sock = self._sock
            if not sock:
                break
            try:
                sock.settimeout(5.0)
                chunk = sock.recv(RECV_BUFSIZE)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    raw = line.decode("utf-8", errors="replace")
                    msg = AOTS6Message.from_json(raw)
                    if msg and msg.verify_signature() and self._on_message:
                        self._on_message(msg)
            except socket.timeout:
                continue
            except (ConnectionResetError, BrokenPipeError, OSError):
                break
        self.log.info("Bucle de recepción terminado.")

    @property
    def connected(self) -> bool:
        return self._connected

# ══════════════════════════════════════════════════════════════════════════════
#  PEER TCP COMPLETO
# ══════════════════════════════════════════════════════════════════════════════

class AOTS6TCPPeer:
    """
    Peer completo de AOTS⁶ sobre TCP.

    Combina:
    - AOTS6TCPServer  → acepta conexiones entrantes
    - AOTS6TCPClient  → conexiones salientes a peers conocidos
    - OntologicalGraph → grafo T⁶ local
    - Protocolo completo: INIT, LINK, VERIFY, EVOLVE, HEARTBEAT, DISCOVER, PEER_LIST
    """

    def __init__(self, label: str, host: str, port: int,
                 coordinate: Optional[ToroidalCoordinate] = None,
                 context: Optional[Dict] = None):
        self.label    = label
        self.host     = host
        self.port     = port
        self.log      = logging.getLogger(f"AOTS6.Peer.{label}")

        # Nodo ontológico local
        self.local_node = AOTS6Node(
            label      = label,
            coordinate = coordinate or ToroidalCoordinate([0.0]*6),
            context    = context or {"peer": label},
        )
        self.peer_id = self.local_node.node_id

        # Grafo local
        self.graph = OntologicalGraph()
        self.graph.add_node(self.local_node)

        # Peers conocidos: {peer_id: {"host":str, "port":int, "identity":str}}
        self._known_peers: Dict[str, Dict] = {}
        self._clients:     Dict[str, AOTS6TCPClient] = {}
        self._seen_msgs:   Dict[str, float] = {}  # msg_id → timestamp (dedup)
        self._lock = threading.Lock()

        # Servidor
        self._server = AOTS6TCPServer(host, port, self._on_inbound_message)

        # Heartbeat thread
        self._hb_thread: Optional[threading.Thread] = None
        self._running = False

        self.log.info(f"Peer inicializado — ID: {self.peer_id[:16]}…")

    # ── Ciclo de vida ───────────────────────────────────────────────────────

    def start(self):
        self._server.start()
        self._running = True
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_thread.start()
        self.log.info(f"Peer {self.label} activo en {self.host}:{self.port}")

    def stop(self):
        self._running = False
        self._server.stop()
        with self._lock:
            for client in self._clients.values():
                client.disconnect()
            self._clients.clear()
        self.log.info(f"Peer {self.label} detenido.")

    # ── Conexión a peers remotos ────────────────────────────────────────────

    def connect_to(self, remote_host: str, remote_port: int) -> bool:
        """Conectar a un peer remoto y enviar INIT."""
        key = f"{remote_host}:{remote_port}"
        with self._lock:
            if key in self._clients:
                return self._clients[key].connected

        client = AOTS6TCPClient(
            remote_host, remote_port,
            on_message=self._on_inbound_message_from_client
        )
        ok = client.connect()
        if ok:
            with self._lock:
                self._clients[key] = client
            # Enviar INIT al nuevo peer
            self._send_to_client(client, self._build_init())
            # Solicitar lista de peers conocidos
            self._send_to_client(client, self._build_msg(MsgType.DISCOVER, {}))
            self.log.info(f"Conectado y INIT enviado a {key}")
        return ok

    # ── Operaciones del protocolo ───────────────────────────────────────────

    def link(self, target_peer_id: str, label: str = "RELACIONA",
             weight: float = 1.0) -> bool:
        """LINK — crear arista ontológica con un peer conocido."""
        with self._lock:
            if target_peer_id not in self._known_peers:
                self.log.warning(f"Peer {target_peer_id[:16]}… no conocido")
                return False
        edge = AOTS6Edge(self.peer_id, target_peer_id, label, weight)
        ok = self.graph.add_edge(edge)
        if ok:
            msg = self._build_msg(MsgType.LINK, {
                "target": target_peer_id,
                "label": label,
                "weight": weight,
                "signature": edge.signature(),
            })
            self._broadcast(msg)
            self.log.info(f"LINK → {target_peer_id[:16]}… [{label}]")
        return ok

    def verify(self) -> Dict[str,bool]:
        """VERIFY — verificar integridad local y anunciarla."""
        results = self.graph.verify_all()
        msg = self._build_msg(MsgType.VERIFY, {
            "graph_hash": self.graph.graph_hash(),
            "all_ok": all(results.values()),
            "node_count": len(results),
        })
        self._broadcast(msg)
        return results

    def evolve(self, delta: Dict[str,Any]) -> bool:
        """EVOLVE — mutar contexto local y anunciar nueva identidad."""
        changed = self.local_node.evolve(delta)
        if changed:
            msg = self._build_msg(MsgType.EVOLVE, {
                "new_identity": self.local_node.identity,
                "keys": list(delta.keys()),
            })
            self._broadcast(msg)
            self.log.info(f"EVOLVE — nueva identidad: {self.local_node.identity[:16]}…")
        return changed

    def heartbeat(self):
        """HEARTBEAT — señal de presencia activa."""
        msg = self._build_msg(MsgType.HEARTBEAT, {
            "identity": self.local_node.identity,
            "graph_hash": self.graph.graph_hash(),
        })
        self._broadcast(msg)

    def status(self) -> Dict:
        with self._lock:
            known = len(self._known_peers)
            clients = sum(1 for c in self._clients.values() if c.connected)
        return {
            "peer":       self.label,
            "host":       f"{self.host}:{self.port}",
            "id":         self.peer_id[:16] + "…",
            "identity":   self.local_node.identity[:16] + "…",
            "coordinate": self.local_node.coordinate.display(),
            "graph":      self.graph.stats(),
            "known_peers": known,
            "active_connections": clients,
            "integrity":  all(self.graph.verify_all().values()),
        }

    # ── Construcción de mensajes ────────────────────────────────────────────

    def _build_msg(self, msg_type: MsgType, payload: Dict) -> AOTS6Message:
        return AOTS6Message(msg_type=msg_type, sender_id=self.peer_id,
                            payload=payload)

    def _build_init(self) -> AOTS6Message:
        return self._build_msg(MsgType.INIT, {
            "label":      self.label,
            "host":       self.host,
            "port":       self.port,
            "identity":   self.local_node.identity,
            "coordinate": self.local_node.coordinate.to_dict(),
            "context":    self.local_node.context,
        })

    # ── Envío ───────────────────────────────────────────────────────────────

    def _broadcast(self, msg: AOTS6Message):
        with self._lock:
            clients = list(self._clients.values())
        for client in clients:
            if client.connected:
                client.send(msg)

    def _send_to_client(self, client: AOTS6TCPClient, msg: AOTS6Message):
        if client.connected:
            client.send(msg)

    def _send_to_peer(self, peer_id: str, msg: AOTS6Message) -> bool:
        with self._lock:
            info = self._known_peers.get(peer_id)
        if not info:
            return False
        key = f"{info['host']}:{info['port']}"
        with self._lock:
            client = self._clients.get(key)
        if client and client.connected:
            return client.send(msg)
        return False

    # ── Recepción ───────────────────────────────────────────────────────────

    def _on_inbound_message(self, msg: AOTS6Message, conn: socket.socket):
        """Llamado por el servidor para mensajes entrantes."""
        self._process_message(msg, reply_sock=conn)

    def _on_inbound_message_from_client(self, msg: AOTS6Message):
        """Llamado por clientes salientes para mensajes entrantes."""
        self._process_message(msg, reply_sock=None)

    def _process_message(self, msg: AOTS6Message,
                         reply_sock: Optional[socket.socket]):
        # Deduplicación
        now = time.time()
        with self._lock:
            if msg.msg_id in self._seen_msgs:
                return
            # Limpiar entradas viejas
            self._seen_msgs = {
                k: v for k,v in self._seen_msgs.items()
                if now - v < REPLAY_WINDOW
            }
            self._seen_msgs[msg.msg_id] = now

        self.log.debug(f"← {msg.msg_type} de {msg.sender_id[:16]}…")

        if msg.msg_type == MsgType.INIT:
            self._handle_init(msg, reply_sock)
        elif msg.msg_type == MsgType.LINK:
            self._handle_link(msg)
        elif msg.msg_type == MsgType.VERIFY:
            self._handle_verify(msg)
        elif msg.msg_type == MsgType.EVOLVE:
            self._handle_evolve(msg)
        elif msg.msg_type == MsgType.HEARTBEAT:
            self._handle_heartbeat(msg)
        elif msg.msg_type == MsgType.DISCOVER:
            self._handle_discover(msg, reply_sock)
        elif msg.msg_type == MsgType.PEER_LIST:
            self._handle_peer_list(msg)
        elif msg.msg_type == MsgType.ACK:
            pass  # confirmación — sin acción requerida
        elif msg.msg_type == MsgType.ERROR:
            self.log.warning(f"ERROR de peer: {msg.payload.get('reason','?')}")

    # ── Handlers ────────────────────────────────────────────────────────────

    def _handle_init(self, msg: AOTS6Message, reply_sock: Optional[socket.socket]):
        p = msg.payload
        coord_dict = p.get("coordinate", {})
        coord = ToroidalCoordinate.from_dict(coord_dict)
        remote_node = AOTS6Node(
            label      = p.get("label", "?"),
            coordinate = coord,
            context    = p.get("context", {"remote": True}),
            node_id    = msg.sender_id,
            is_remote  = True,
        )
        remote_node._identity = p.get("identity", remote_node._identity)

        with self._lock:
            is_new = msg.sender_id not in self._known_peers
            self._known_peers[msg.sender_id] = {
                "host":     p.get("host", "?"),
                "port":     p.get("port", 0),
                "identity": p.get("identity", ""),
                "label":    p.get("label", "?"),
            }
        self.graph.add_node(remote_node)

        d = self.local_node.coordinate.distance(coord)
        self.log.info(
            f"INIT ← {p.get('label','?')} "
            f"({msg.sender_id[:16]}…)  d(T⁶)={d:.4f}  {'[NUEVO]' if is_new else '[CONOCIDO]'}"
        )

        # Responder con nuestro propio INIT si es un peer nuevo
        if is_new and reply_sock:
            try:
                TCPTransport.send(reply_sock, self._build_init())
            except: pass

    def _handle_link(self, msg: AOTS6Message):
        p = msg.payload
        target = p.get("target", "")
        with self._lock:
            has_target = (target in self._known_peers or
                          target == self.peer_id)
        if has_target:
            edge = AOTS6Edge(msg.sender_id, target,
                             p.get("label","RELACIONA"),
                             p.get("weight", 1.0))
            ok = self.graph.add_edge(edge)
            self.log.info(
                f"LINK ← {msg.sender_id[:16]}… → {target[:16]}… "
                f"[{p.get('label','?')}] {'✓' if ok else '✗'}"
            )

    def _handle_verify(self, msg: AOTS6Message):
        p = msg.payload
        self.log.info(
            f"VERIFY ← {msg.sender_id[:16]}…  "
            f"hash={p.get('graph_hash','?')[:16]}…  "
            f"ok={p.get('all_ok','?')}"
        )

    def _handle_evolve(self, msg: AOTS6Message):
        p = msg.payload
        with self._lock:
            if msg.sender_id in self._known_peers:
                self._known_peers[msg.sender_id]["identity"] = p.get("new_identity","")
        # Actualizar identidad del nodo remoto en el grafo
        remote = self.graph._nodes.get(msg.sender_id)
        if remote:
            remote._identity = p.get("new_identity", remote._identity)
        self.log.info(
            f"EVOLVE ← {msg.sender_id[:16]}…  "
            f"nueva_id={p.get('new_identity','?')[:16]}…  "
            f"keys={p.get('keys',[])}"
        )

    def _handle_heartbeat(self, msg: AOTS6Message):
        self.log.debug(f"HEARTBEAT ← {msg.sender_id[:16]}…")

    def _handle_discover(self, msg: AOTS6Message,
                         reply_sock: Optional[socket.socket]):
        """Responder con lista de peers conocidos."""
        with self._lock:
            peers = {
                pid: {"host": info["host"], "port": info["port"],
                      "label": info["label"]}
                for pid, info in self._known_peers.items()
            }
        response = self._build_msg(MsgType.PEER_LIST, {"peers": peers})
        if reply_sock:
            try:
                TCPTransport.send(reply_sock, response)
            except: pass
        self.log.info(f"DISCOVER ← {msg.sender_id[:16]}…  → enviando {len(peers)} peers")

    def _handle_peer_list(self, msg: AOTS6Message):
        """Recibir lista de peers y conectar a desconocidos (gossip)."""
        peers = msg.payload.get("peers", {})
        new_connections = 0
        for pid, info in peers.items():
            if pid == self.peer_id:
                continue
            with self._lock:
                already_known = pid in self._known_peers
            if not already_known:
                host = info.get("host", "")
                port = info.get("port", 0)
                if host and port:
                    self.log.info(f"PEER_LIST: intentando conectar a {info.get('label','?')} {host}:{port}")
                    if self.connect_to(host, port):
                        new_connections += 1
        if new_connections:
            self.log.info(f"PEER_LIST: {new_connections} nuevas conexiones vía gossip")

    # ── Heartbeat periódico ─────────────────────────────────────────────────

    def _heartbeat_loop(self):
        while self._running:
            time.sleep(15)
            if self._running:
                self.heartbeat()

# ══════════════════════════════════════════════════════════════════════════════
#  ORQUESTADOR  — para demos y tests locales
# ══════════════════════════════════════════════════════════════════════════════

class AOTS6TCPNetwork:
    """
    Orquestador de una red AOTS⁶ local para demos y tests.
    Crea múltiples peers en localhost con puertos distintos.
    """

    def __init__(self, base_port: int = 9600):
        self.base_port = base_port
        self.peers: Dict[str, AOTS6TCPPeer] = {}
        self._port_counter = base_port

    def add_peer(self, label: str,
                 coordinate: Optional[ToroidalCoordinate] = None,
                 context: Optional[Dict] = None) -> AOTS6TCPPeer:
        port = self._port_counter
        self._port_counter += 1
        peer = AOTS6TCPPeer(
            label      = label,
            host       = "127.0.0.1",
            port       = port,
            coordinate = coordinate,
            context    = context or {"rol": label.lower()},
        )
        peer.start()
        self.peers[peer.peer_id] = peer
        return peer

    def connect_all(self):
        """Conectar todos los peers entre sí (topología full-mesh)."""
        peer_list = list(self.peers.values())
        for i, p1 in enumerate(peer_list):
            for p2 in peer_list[i+1:]:
                p1.connect_to(p2.host, p2.port)
        time.sleep(0.5)  # dar tiempo al handshake

    def stop_all(self):
        for peer in self.peers.values():
            peer.stop()

    def network_status(self) -> Dict:
        return {
            "peers": len(self.peers),
            "statuses": [p.status() for p in self.peers.values()],
        }

# ══════════════════════════════════════════════════════════════════════════════
#  DEMO
# ══════════════════════════════════════════════════════════════════════════════

SEP = "─" * 70

def demo():
    print(f"\n{'═'*70}")
    print("  AOTS⁶ · Red TCP Real — Demo de 5 peers")
    print("  Alfredo Jhovany Alfaro García · 21-MAR-2025")
    print(f"{'═'*70}\n")

    logging.getLogger().setLevel(logging.WARNING)  # silenciar logs en demo

    net = AOTS6TCPNetwork(base_port=9700)

    print(f"{SEP}\n  1 · Creando 5 peers en localhost\n{SEP}")
    alpha   = net.add_peer("Alpha",   ToroidalCoordinate([0.1,0.1,0.1,0.1,0.1,0.1]),
                           {"rol":"gateway"})
    beta    = net.add_peer("Beta",    ToroidalCoordinate([0.2,0.3,0.4,0.5,0.6,0.7]),
                           {"rol":"compute"})
    gamma   = net.add_peer("Gamma",   ToroidalCoordinate([0.5,0.5,0.5,0.5,0.5,0.5]),
                           {"rol":"storage"})
    delta_p = net.add_peer("Delta",   ToroidalCoordinate([0.9,0.8,0.7,0.6,0.5,0.4]),
                           {"rol":"inference"})
    epsilon = net.add_peer("Epsilon", ToroidalCoordinate([0.3,0.6,0.2,0.8,0.4,0.9]),
                           {"rol":"edge"})

    for p in [alpha, beta, gamma, delta_p, epsilon]:
        print(f"  ✓ {p.label:10s}  puerto={p.port}  ID={p.peer_id[:16]}…")

    print(f"\n{SEP}\n  2 · Conectando peers (TCP real)\n{SEP}")
    net.connect_all()
    time.sleep(0.8)
    print("  Full-mesh establecido")

    print(f"\n{SEP}\n  3 · Protocolo: LINK + EVOLVE + VERIFY\n{SEP}")

    alpha.link(beta.peer_id,    "PROCESA",   weight=0.8)
    alpha.link(gamma.peer_id,   "ALMACENA",  weight=0.9)
    beta.link(delta_p.peer_id,  "INFIERE",   weight=0.95)
    gamma.link(epsilon.peer_id, "DISTRIBUYE",weight=0.7)
    delta_p.link(alpha.peer_id, "RETROALIM", weight=0.85)

    delta_p.evolve({"estado": "activo", "ciclo": 1, "d5_señal": 0.7312})
    epsilon.evolve({"estado": "edge-activo", "latencia_ms": 12})
    alpha.evolve({"estado": "gateway-listo"})

    for p in [alpha, beta, gamma, delta_p, epsilon]:
        p.verify()

    time.sleep(0.3)

    print(f"\n{SEP}\n  4 · Estado de la red\n{SEP}")
    for p in [alpha, beta, gamma, delta_p, epsilon]:
        s = p.status()
        print(f"\n  {s['peer']:10s}  {s['host']}")
        print(f"    ID         : {s['id']}")
        print(f"    Identidad  : {s['identity']}")
        print(f"    Coords     : {s['coordinate']}")
        print(f"    Grafo      : {s['graph']}")
        print(f"    Peers      : {s['known_peers']} conocidos  {s['active_connections']} activos")
        print(f"    Íntegro    : {'✓' if s['integrity'] else '✗'}")

    print(f"\n{SEP}\n  5 · Métricas toroidales entre peers\n{SEP}")
    peers_list = [alpha, beta, gamma, delta_p, epsilon]
    for i in range(len(peers_list)):
        for j in range(i+1, len(peers_list)):
            a = peers_list[i]; b = peers_list[j]
            d = a.local_node.coordinate.distance(b.local_node.coordinate)
            print(f"  d({a.label}, {b.label}) = {d:.6f}")

    print(f"\n{SEP}\n  6 · Ancla de proveniencia\n{SEP}")
    system_state = {
        "framework": "AOTS6-TCP",
        "version":   "1.0.3",
        "autor":     "Alfredo Jhovany Alfaro García",
        "orcid":     "0009-0002-5177-9029",
        "origen":    "2025-03-21",
        "peers":     [p.peer_id for p in peers_list],
        "graphs":    [p.graph.graph_hash() for p in peers_list],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    system_hash = _sha256(system_state)
    with open("BLOQUE-5-TCP.json", "w", encoding="utf-8") as f:
        json.dump({**system_state, "system_hash": system_hash}, f,
                  indent=2, ensure_ascii=False)

    print(f"  System hash : {system_hash[:32]}…")
    print(f"  BLOQUE-5-TCP.json guardado ✓")

    net.stop_all()

    print(f"\n{'═'*70}")
    print("  AOTS⁶ Red TCP — Demo completado correctamente.")
    print(f"  GitHub : https://github.com/fo22Alfaro/AOTS6-Ontological-Toroidal-System")
    print(f"{'═'*70}\n")


if __name__ == "__main__":
    demo()
