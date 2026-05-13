import torch
import torch.nn as nn
import torch.fft
from torchdiffeq import odeint

class SpectralConv6D(nn.Module):
    def __init__(self, in_channels, out_channels, modes):
        super(SpectralConv6D, self).__init__()
        self.modes = modes
        self.scale = 1 / (in_channels * out_channels)
        self.weights = nn.Parameter(self.scale * torch.rand(in_channels, out_channels, modes, dtype=torch.cfloat))

    def forward(self, x):
        batch_size = x.shape[0]
        x_ft = torch.fft.rfft(x)
        out_ft = torch.zeros_like(x_ft)
        out_ft[:, :, :self.modes] = torch.einsum("bix, iox -> box", x_ft[:, :, :self.modes], self.weights)
        x = torch.fft.irfft(out_ft, n=x.size(-1))
        return x

class DatacenterDynamics(nn.Module):
    def __init__(self, channels=6):
        super(DatacenterDynamics, self).__init__()
        self.local_coupling = nn.Conv1d(channels, channels, kernel_size=3, padding=1)
        self.activation = nn.Tanh()

    def forward(self, t, u):
        du = self.local_coupling(u)
        return self.activation(du)

class HybridSquidOperator(nn.Module):
    def __init__(self, channels=6, modes=16):
        super(HybridSquidOperator, self).__init__()
        self.dynamics = DatacenterDynamics(channels)
        self.global_mixing = SpectralConv6D(channels, channels, modes)
        self.projection = nn.Linear(channels, channels)

    def forward(self, u0, t_span):
        u_local = odeint(self.dynamics, u0, t_span)[-1]
        u_global = self.global_mixing(u_local)
        return self.projection(u_global.transpose(1, 2)).transpose(1, 2)

u_init = torch.randn(1, 6, 1024)
t = torch.linspace(0, 1, 10)
model = HybridSquidOperator()
output = model(u_init, t)
print("System evolved successfully. Final output shape:", output.shape)
