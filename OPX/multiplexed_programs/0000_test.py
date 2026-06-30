from qualang_tools.plot.fitting import Fit
import numpy as np

tau_min = 16 # // 4
tau_max = 12_000 # // 4
d_tau = 128 // 4
# taus = np.arange(tau_min, tau_max + 0.1, d_tau)  # Linear sweep
taus = np.logspace(np.log10(tau_min), np.log10(tau_max), 200, endpoint=True)  # Log sweep
taus = np.array(np.unique(taus//4), dtype=int)
print(taus)

fit = Fit()
decay_fit = fit.T1(4 * taus, Q, plot=False)

print(decay_fit.keys())
print(decay_fit)