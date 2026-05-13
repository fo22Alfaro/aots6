import torch
import torch.nn as nn
import torch.optim as optim
import pennylane as qml
from torchdiffeq import odeint
import numpy as np

class SpectralConv6D(nn.Module):
    def __init__(self, in_channels, out_channels, modes):
        super().__init__()
        self.modes = modes
        self.scale = 1 / (in_channels * out_channels)
        self.weights = nn.Parameter(self.scale * torch.rand(in_channels, out_channels, modes, dtype=torch.cfloat))

    def forward(self, x):
        x_ft = torch.fft.rfft(x)
        out_ft = torch.zeros_like(x_ft)
        out_ft[:, :, :self.modes] = torch.einsum("bix, iox -> box", x_ft[:, :, :self.modes], self.weights)
        return torch.fft.irfft(out_ft, n=x.size(-1))

class DatacenterDynamics(nn.Module):
    def __init__(self, channels=6):
        super().__init__()
        self.local_coupling = nn.Conv1d(channels, channels, kernel_size=3, padding=1)
        self.activation = nn.Tanh()

    def forward(self, t, u):
        return self.activation(self.local_coupling(u))

n_qubits = 6 
dev = qml.device("default.qubit", wires=n_qubits)

@qml.qnode(dev, interface="torch", diff_method="backprop")
def quantum_entanglement_circuit(inputs, weights):
    capas_cuanticas = weights.shape[0]
    for i in range(n_qubits):
        qml.RY(inputs[i] * np.pi, wires=i)
    for layer in range(capas_cuanticas):
        for i in range(n_qubits):
            qml.CRX(weights[layer, i], wires=[i, (i + 1) % n_qubits])
        for i in range(n_qubits):
            qml.RZ(weights[layer, i], wires=i)
    return [qml.expval(qml.PauliZ(i)) for i in range(n_qubits)]

class QuantumActorCritic(nn.Module):
    def __init__(self, channels=6, modes=16, q_layers=3):
        super().__init__()
        self.dynamics = DatacenterDynamics(channels)
        self.global_mixing = SpectralConv6D(channels, channels, modes)
        self.spatial_pool = nn.AdaptiveAvgPool1d(1)
        
        weight_shapes_actor = {"weights": (q_layers, channels)}
        self.actor_quantum = qml.qnn.TorchLayer(quantum_entanglement_circuit, weight_shapes_actor)
        self.actor_head = nn.Linear(channels, 3) 
        
        weight_shapes_critic = {"weights": (q_layers, channels)}
        self.critic_quantum = qml.qnn.TorchLayer(quantum_entanglement_circuit, weight_shapes_critic)
        self.critic_head = nn.Linear(channels, 1) 

    def forward(self, u0, t_span):
        u_local = odeint(self.dynamics, u0, t_span)[-1]
        u_global = self.global_mixing(u_local)
        
        u_pooled = self.spatial_pool(u_global).squeeze(-1)
        u_norm = torch.tanh(u_pooled)
        
        estado_cuantico_actor = self.actor_quantum(u_norm)
        politica_acciones = torch.sigmoid(self.actor_head(estado_cuantico_actor))
        
        estado_cuantico_critico = self.critic_quantum(u_norm)
        valor_estado = self.critic_head(estado_cuantico_critico)
        
        return politica_acciones, valor_estado

def evaluar_recompensa_termodinamica(estado, acciones):
    temp_global = estado[:, 0, :].mean().item()
    cpu_global = estado[:, 2, :].mean().item()
    energia_gastada = acciones[:, 0].mean().item()
    refrigeracion_gastada = acciones[:, 1].mean().item()
    
    penalizacion_termica = 0.0
    if temp_global > 0.8: 
        if refrigeracion_gastada < 0.7:
             penalizacion_termica = -5.0 
    
    penalizacion_energia = -(energia_gastada + refrigeracion_gastada) * 0.5
    recompensa_rendimiento = cpu_global * 2.0 
    
    recompensa_total = recompensa_rendimiento + penalizacion_energia + penalizacion_termica
    return recompensa_total

if __name__ == "__main__":
    print("Iniciando Secuencia de Activación Compleja AOTS-6...")
    print("Módulo: Actor-Crítico Híbrido Cuántico (Q-PPO)")
    
    agente = QuantumActorCritic()
    optimizador = optim.Adam(agente.parameters(), lr=0.005)
    
    t_span = torch.linspace(0, 1, 3)
    batch_size = 4
    pasos_entrenamiento = 10
    
    print("-" * 50)
    for paso in range(pasos_entrenamiento):
        optimizador.zero_grad()
        
        estado_dc = torch.randn(batch_size, 6, 1024)
        acciones_predichas, valor_predicho = agente(estado_dc, t_span)
        
        recompensa = evaluar_recompensa_termodinamica(estado_dc, acciones_predichas)
        recompensa_tensor = torch.tensor([recompensa] * batch_size).view(-1, 1).float()
        
        ventaja = recompensa_tensor - valor_predicho.detach()
        
        perdida_actor = -(torch.log(acciones_predichas + 1e-8) * ventaja).mean()
        perdida_critico = nn.MSELoss()(valor_predicho, recompensa_tensor)
        
        perdida_total = perdida_actor + perdida_critico
        
        perdida_total.backward()
        optimizador.step()
        
        print(f"Paso de Convergencia [{paso+1:02d}] | Recompensa Obtenida: {recompensa:.2f} | Error Crítico: {perdida_critico.item():.4f}")

    print("-" * 50)
    print("Activación Compleja lograda. El organismo AOTS-6 ahora aprende y se adapta autónomamente.")
