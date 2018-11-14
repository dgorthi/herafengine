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

# Set sync
snap.write_int('sync_period', 8192*32)
snap.write_int('corr_0_acc_len', 8192)

for ant1 in range(6):
    for ant2 in range(ant1,6,1):
        snap.write_int('corr_0_input_sel',((ant1<<8)+ant2))
        time.sleep(0.1)

        pol1 = tv[ant1*nchans:(ant1+1)*nchans]
        pol1_i = np.asarray([signed_int(x) for x in (pol1&(0x0f))])
        pol1_r = 1j*np.asarray([signed_int(x) for x in (pol1>>4)])
        pol1 = pol1_r + pol1_i
        
        pol2 = tv[ant2*nchans:(ant2+1)*nchans]
        pol2_r = np.asarray([signed_int(x) for x in (pol2&(0x0f))])
        pol2_i = 1j*np.asarray([signed_int(x) for x in (pol2>>4)])
        pol2 = pol2_r + pol2_i
        
        corr_test = pol1*np.conj(pol2)
        corr_test = np.sum(corr_test.reshape(-1,8), axis=1)
        
        corr_bram = np.asarray(struct.unpack('>2048l',snap.read('corr_0_dout',8*1024)))
        
        if (ant1 == ant2):
            corr = (corr_bram[::2] + 1j*corr_bram[1::2])
            print ant1, ant2, np.all(corr_test.real == corr.real/8), np.all(corr_test.real == corr.imag)
        else:
            corr = (corr_bram[::2] + 1j*corr_bram[1::2])/8
            print ant1, ant2, np.all(corr_test.real == corr.real), np.all(corr_test.imag == corr.imag)

plt.figure()
plt.plot(np.real(corr_test), 'o', label='Test real', alpha=0.3, lw=2)
plt.plot(np.imag(corr_test), 'o', label='Test imag', alpha=0.3, lw=2)

plt.plot(np.real(corr),label='Snap corr real')
plt.plot(np.imag(corr),label='Snap corr imag')

plt.legend()
plt.show()
