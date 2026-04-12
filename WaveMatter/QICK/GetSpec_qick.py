###########################################################################
########################     What and hOw?      ##########################
###########################################################################
# Resonator Readout
# version 1.0
# Created in April 2026 by Gun Suer
#
###########################################################################
######################     IMPORTS AND CONFIG     #########################
###########################################################################

import numpy as np
import subprocess
from datetime import datetime
from scipy.io import savemat
from qick import QickSoc
from qick.averager_program import AveragerProgramV2

###########################################################################
#######################     REMOTE SAVE CONFIG     ########################
###########################################################################

REMOTE_USER = "your_username"
REMOTE_HOST = "172.31.255.33"
REMOTE_DIR  = "/path/to/save/dir"

###########################################################################
#####################     EXPERIMENT PARAMETERS     ######################
###########################################################################

GEN_CH = 0
RO_CH  = 0

RES_FREQ_MHZ  = 5500.0
FREQ_SPAN_MHZ = 10.0
N_FREQS       = 201
GAIN          = 0.3
PULSE_LEN_US  = 10.0
N_REPS        = 1000
RELAX_US      = 100.0
ADC_OFFSET_US = 0.5

###########################################################################
#########################     QICK PROGRAM     ############################
###########################################################################

class GetSpec(AveragerProgramV2):

    def initialize(self):
        cfg = self.cfg
        self.declare_gen(ch=GEN_CH, nqz=2, mixer_freq=cfg["freq"], ro_ch=RO_CH)
        self.declare_readout(
            ch=RO_CH,
            freq=cfg["freq"],
            length=self.us2cycles(cfg["pulse_len_us"], ro_ch=RO_CH),
            gen_ch=GEN_CH,
        )
        self.add_pulse(
            ch=GEN_CH,
            name="ro_pulse",
            style="const",
            length=self.us2cycles(cfg["pulse_len_us"], gen_ch=GEN_CH),
            gain=cfg["gain"],
        )
        self.synci(200)

    def body(self):
        cfg = self.cfg
        self.measure(
            pulse_ch=GEN_CH,
            adcs=[RO_CH],
            adc_trig_offset=cfg["adc_trig_offset_us"],
            wait=True,
            syncdelay=self.us2cycles(cfg["relax_us"]),
        )

###########################################################################
#######################     INITIALIZE HARDWARE     ######################
###########################################################################

soc = QickSoc()

###########################################################################
#########################     RUN SWEEP     ###############################
###########################################################################

freqs  = np.linspace(RES_FREQ_MHZ - FREQ_SPAN_MHZ,
                     RES_FREQ_MHZ + FREQ_SPAN_MHZ, N_FREQS)
I_data = np.zeros(N_FREQS)
Q_data = np.zeros(N_FREQS)

for idx, f in enumerate(freqs):
    cfg = {
        "freq": f, "pulse_len_us": PULSE_LEN_US, "gain": GAIN,
        "reps": N_REPS, "relax_us": RELAX_US,
        "adc_trig_offset_us": ADC_OFFSET_US,
    }
    prog = GetSpec(soc, cfg)
    iq = prog.acquire(soc, load_pulses=True, progress=False)
    I_data[idx] = iq[RO_CH][0, 0]
    Q_data[idx] = iq[RO_CH][0, 1]

###########################################################################
#####################     SAVE AND TRANSFER     ###########################
###########################################################################

timestamp  = datetime.now().strftime("%Y%m%d%H%M")
filename   = f"K001_{timestamp}_KIv4_res.mat"
local_path = f"/tmp/{filename}"

savemat(local_path, {
    "freqs_MHz":    freqs,
    "I":            I_data,
    "Q":            Q_data,
    "gain":         GAIN,
    "pulse_len_us": PULSE_LEN_US,
    "nreps":        N_REPS,
})

subprocess.run([
    "scp", local_path,
    f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}/{filename}"
], check=True)

print(f"Saved {filename} to {REMOTE_HOST}:{REMOTE_DIR}")
