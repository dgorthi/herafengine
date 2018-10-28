import casperfpga
import numpy as np
import matplotlib.pyplot as plt
import time
import struct

def signed_int(x):
    if (x&0x8):
        return (x - 16)
    else:
        return x

nchans = 2**13
nstreams = 8

snap = casperfpga.CasperFpga('snap109')

# Ramp
ramp = np.arange(nchans, dtype='>B')
tv = np.zeros(nchans*nstreams, dtype='>B')

for stream in range(nstreams):
    tv[stream*nchans:(stream+1)*nchans] = ramp + stream #stream+1+(stream<<5) 
snap.write('tv',tv.tostring())

ant1 = 5
ant2 = 6

# Generate test correlation
pol1 = tv[ant1*nchans:(ant1+1)*nchans]
pol1_r = np.asarray([signed_int(x) for x in (pol1&(0x0f))])
pol1_i = 1j*np.asarray([signed_int(x) for x in (pol1>>4)])
pol1 = pol1_r + pol1_i

pol2 = tv[ant2*nchans:(ant2+1)*nchans]
pol2_r = np.asarray([signed_int(x) for x in (pol2&(0x0f))])
pol2_i = 1j*np.asarray([signed_int(x) for x in (pol2>>4)])
pol2 = pol2_r + pol2_i

corr_test = pol1*np.conj(pol2)
corr_test = np.mean(corr_test.reshape(-1,8), axis=1)

plt.figure()
plt.plot(np.real(corr_test), label='Test real', alpha=0.3, lw=2)
plt.plot(np.imag(corr_test), label='Test imag', alpha=0.3, lw=2)

# Set sync
snap.write_int('sync_period', 8192*32)

snap.write_int('corr_0_input_sel',((ant1<<8)+ant2))
snap.write_int('corr_0_acc_len', 8192)
time.sleep(2)

corr = np.asarray(struct.unpack('>2048l',snap.read('corr_0_dout',8*1024)))
corr = (corr[::2] + 1j*corr[1::2])/8

plt.plot(np.real(corr),label='Snap corr real')
plt.plot(np.imag(corr),label='Snap corr imag')

plt.legend()
plt.show()
