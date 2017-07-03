import logging
import numpy as np
import struct
logger = logging.get_logger('blocks')


class SnapFengine(object):
    def __init__(self):
        self.blocks = [
            Sync('sync'),
            NoiseGen('noise', nstreams=6),
            Input('input', nstreams=12),
            Delay('delay', nstreams=6),
            Pfb('pfb'),
            Eq('eq', nstreams=6),
            EqTvg('eq_tvg', nstreams=6, nchans=2**11),
            ChanReorder('chan_reorder', nchans=2**11),
            Packetizer('packetizer'),
        ]

# Block Classes
class Block(object):
    def __init__(self, host, name):
        self.host = host
        self.name = name
        self.prefix = name + '_'
    
    def print_status(self):
        """
        Individual blocks should override this
        method to print some useful information.
        """
        pass

    def initialize(self):
        """
        Individual blocks should override this
        method to configure themselves appropriately
        """

    def listdev(self):
        """
        return a list of all register names within
        the block.
        """
        devs = host.listdev()
        return [x.lstrip(self.prefix) in devs if x.startswith(self.prefix)]

    def read_int(self, reg, offset=0, **kwargs):
        return host.read_int(self.prefix + reg, 4, offset=offset, **kwargs)

    def write_int(self, reg, val, offset=0, **kwargs):
        host.write_int(self.prefix + reg, val, offset=offset, **kwargs))

    def read_uint(self, reg, offset=0, **kwargs):
        return host.read_uint(self.prefix + reg, 4, offset=offset, **kwargs)

    def write_uint(self, reg, val, offset=0, **kwargs):
        host.write_int(self.prefix + reg, val, offset=offset, **kwargs))

    def read(self, reg, nbytes, **kwargs):
        return host.read(self.prefix + reg, nbytes, **kwargs)

    def write(self, reg, val, **kwargs):
        host.write(self.prefix + reg, val, **kwargs)

    def blindwrite(self, reg, val, **kwargs):
        host.blindwrite(self.prefix + reg, val, **kwargs)

    def change_reg_bits(self, reg, val, start, width=1):
        orig_val = self.read_uint(reg)
        mask = (2**32 - 1) - ((2**width - 1) << start)
        new_val = (orig_val & mask) + (val << start)
        self.write_int(reg, new_val)


def Sync(Block):
    def __init__(self, host, name):
        super(Sync, self).__init__(host, name)
        self.ARM_SYNC  = 1<<0
        self.ARM_NOISE = 1<<1
        self.SW_SYNC   = 1<<4
    
    def uptime(self):
        """
        Returns uptime in seconds, assumes 250 MHz FPGA clock
        """
        return self.read_uint('uptime')

    def period(self):
        """
        Returns period of sync in pulses, in FPGA clock ticks
        """
        return self.read_uint('period')

    def count(self):
        """
        Returns Number of external sync pulses received.
        """
        return self.read_uint('count')

    def arm_sync(self):
        """
        Arm sync pulse generator.
        """
        curr = self.read_int('arm')
        self.write_int('arm', (curr & (self.SW_SYNC | self.ARM_NOISE)))
        self.write_int('arm', (curr & (self.SW_SYNC | self.ARM_NOISE)) | self.ARM_SYNC)
        self.write_int('arm', (curr & (self.SW_SYNC | self.ARM_NOISE)))

    def arm_noise(self):
        """
        Arm noise generator resets
        """
        curr = self.read_int('arm')
        self.write_int('arm', (curr & (self.SW_SYNC | self.ARM_SYNC)))
        self.write_int('arm', (curr & (self.SW_SYNC | self.ARM_SYNC)) | self.ARM_NOISE)
        self.write_int('arm', (curr & (self.SW_SYNC | self.ARM_SYNC)))

    def sw_sync(self):
        """
        Issue a software sync pulse
        """
        curr = self.read_int('arm')
        self.write_int('arm', (curr & (self.ARM_NOISE | self.ARM_SYNC)))
        self.write_int('arm', (curr & (self.ARM_NOISE | self.ARM_SYNC)) | self.SW_SYNC)
        self.write_int('arm', (curr & (self.ARM_NOISE | self.ARM_SYNC)))

    def print_status(self):
        print 'Sync block: %s: Uptime: %d seconds' % (self.name, self.uptime())
        print 'Sync block: %s: Period: %d FPGA clocks' % (self.name, self.period())
        print 'Sync block: %s: Count : %d' % (self.name, self.count())

    def initialize(self):
        self.write_int('arm', 0)

class NoiseGen(Block):
    def __init__(self, host, name, nstreams=6):
        super(NoiseGen, self).__init__(host, name)
        self.nstreams = nstreams

    def set_seed(self, seed, stream):
        """
        Set the seed of the noise generator for a given stream.
        """
        if stream > self.nstreams:
            logger.error('Tried to set noise generator seed for stream %d > nstreams (%d)' % (stream, self.nstreams))
            return
        reg_name = 'seed%d' % (stream // 4)
        val = self.read_uint(regname)
        masked_val = val & (0xffffffff - (0xff << stream))
        self.write_int(regname, masked_val + (seed << stream))

    def get_seed(self, stream):
        """
        Get the seed of the noise generator for a given stream.
        """
        if stream > self.nstreams:
            logger.error('Tried to get noise generator seed for stream %d > nstreams (%d)' % (stream, self.nstreams))
            return
        reg_name = 'seed%d' % (stream // 4)
        return self.read_uint(regname) & (0xff << stream)


    def initialize(self):
        for stream in self.nstreams:
            self.set_seed(0, stream)

    def print_status(self):
        for stream in self.nstreams:
            print 'NoiseGen block: %s: stream %d seed: %d' % (self.name, stream, self.get_seed(stream))
       

class Input(Block):
    def __init__(self, host, name, nstreams=6):
        super(Input, self).__init__(host, name)
        self.nstreams = nstreams
        self.USE_NOISE = 0
        self.USE_ADC   = 1
        self.USE_ZERO  = 2

    def use_noise(self, stream=None):
        if stream is None:
            v = 0
            for stream in range(self.nstreams):
                v += self.USE_NOISE*(2<<stream)
            self.write_int('source_sel', v)
        else:
            raise NotImplementedError('Different input selects not supported yet!')

    def use_adc(self, stream=None):
        if stream is None:
            v = 0
            for stream in range(self.nstreams):
                v += self.USE_ADC*(2<<stream)
            self.write_int('source_sel', v)
        else:
            raise NotImplementedError('Different input selects not supported yet!')

    def use_zero(self, stream=None):
        if stream is None:
            v = 0
            for stream in range(self.nstreams):
                v += self.USE_ZERO*(2<<stream)
            self.write_int('source_sel', v)
        else:
            raise NotImplementedError('Different input selects not supported yet!')

    def get_stats(self):
        self.write_int('rms_enable', 1)
        time.sleep(0.01)
        self.write_int('rms_enable', 0)
        x = np.array(struct.unpack('>%dl' % (2*self.nstreams), self.read('rms_levels', self.nstreams * 8)))
        self.write_int('rms_enable', 1)
        means = x[0::2]
        sds   = x[1::2]
        return {'means':means, 'sds':sds}

    def initialize(self):
        self.use_adc()
        self.write_int('rms_enable', 1)

    def print_status(self):
        print self.get_stats()

class Delay(Block):
    def __init__(self, host, name, nstreams=6):
        super(Delay, self).__init__(host, name)
        self.nstreams = nstreams

    def set_delay(self, stream, delay):
        if stream > self.nstreams:
            logger.error('Tried to set delay for stream %d > nstreams (%d)' % (stream, self.nstreams))
        self.write_int(change_reg_bits(self.host.read_uint('delays'), delay, 4*stream, 4)

    def initialize(self):
        self.write_int('delays', 0)

class Pfb(Block):
    def __init__(self, host, name):
        super(Delay, self).__init__(host, name)
        self.SHIFT_OFFSET = 0
        self.SHIFT_WIDTH  = 12
        self.PRESHIFT_OFFSET = 12
        self.PRESHIFT_WIDTH  = 2
        self.STAT_RST_BIT = 14

    def set_fft_shift(self, shift):
        self.change_reg_bits('ctrl', shift, self.SHIFT_OFFSET, self.SHIFT_WIDTH)

    def set_fft_preshift(self, shift):
        self.change_reg_bits('ctrl', shift, self.PRESHIFT_OFFSET, self.PRESHIFT_WIDTH)

    def rst_stats(self):
        self.change_reg_bits('ctrl', 1, self.RST_BIT)
        self.change_reg_bits('ctrl', 0, self.RST_BIT)

    def is_overflowing(self):
        return self.read_uint('status') != 0
        
    def initialize(self):
        self.host.write_int('ctrl', 0)
        self.rst_stats()

class Eq(Block):
    def __init__(self, host, name, nstreams=6, ncoeffs=2**11):
        super(Eq, self).__init__(host, name)
        self.nstreams = nstreams
        self.ncoeffs = ncoeffs
        self.width = 18
        self.bp = 7
        self.format = 'Q'

    def set_coeffs(self, stream, coeffs):
        coeffs = coeffs << self.bp
        if np.any(self.coeffs > (2**width - 1)):
            logger.warning("Some coefficients out of range")
        # saturate coefficients
        coeffs[coeffs>(2**width - 1)] = 2**width - 1
        coeffs = list(coeffs)
        coeffs_str = struct.pack('>%d%s' % (len(coeffs), self.format), *coeffs)
        self.write('%d_coeffs' % stream, coeffs_str)

    def get_coeffs(self, stream):
        coeffs_str = self.read('%d_coeffs' % stream, self.ncoeffs*struct.calcsize(self.format))
        coeffs = np.array(struct.unpack('>%d%s' % (self.ncoeffs, self.format), coeffs_str))
        return coeffs / (2.**bp)

    def initialize(self):
        for stream in self.nstreams:
            self.set_coeffs(self, stream, np.ones(self.ncoeffs))

class EqTvg(Block):
    def __init__(self, host, name, nstreams=6, nchans=2**11):
        super(EqTvg, self).__init__(host, name)
        self.nstreams = nstreams
        self.nchans = nchans
        self.format = 'Q'

    def tvg_en(self):
        self.write_int('tvg_en', 1)

    def tvg_disable(self):
        self.write_int('tvg_en', 0)

    def write_freq_ramp(self):
        ramp = np.arange(self.nchans)
        ramp = ramp % 256 # tvg values are only 8 bits
        tv = np.zeros(self.nchans, dtype='>%s'%self.format) 
        for stream in range(self.nstreams):
            tv += (ramp << (8*stream))
        self.write('tv', tv.tostring())

    def initialize(self):
        self.tvg_disable()
        self.write_freq_ramp()

class ChanReorder(Block):
    def __init__(self, host, name, nchans):
        super(ChanReorder, self).__init__(host, name)
        self.nchans = nchans

    def set_channel_order(self, order):
        order = list(order)
        if len(order) != self.nchans:
            logger.Error("Tried to reorder channels, but map was the wrong length")
            return
        order_str = struct.pack('>%dH' % self.nchans, *order)
        self.write('reorder1_map1', order_str)

class Packetizer(Block):
    def __init__(self, host, name):
        super(ChanReorder, self).__init__(host, name)

    def set_nants(self, nants):
        self.write_int('n_ants', nants)

    def use_gpu_packing(self):
        self.write_int('stupid_gpu_packing', 1)

    def use_fpga_packing(self):
        self.write_int('stupid_gpu_packing', 0)

    def set_dest_ips(self, ips):
        self.write('ips', struct.pack('>%dL' % len(ips), *ips))

    def set_ant_headers(self, ants):
        self.write('ants', struct.pack('>%dL' % len(ants), *ants))
        
    def set_chan_headers(self, chans):
        self.write('chans', struct.pack('>%dL' % len(chans), *chans))

    def initialize(self):
        self.set_dest_ips(np.zeros(1024))
        
class Eth(Block):
    def __init__(self, host, name, port=10000):
        super(ChanReorder, self).__init__(host, name)
        self.port = port

    def get_status(self):
        stat = self.read_uint('sw_status')
        rv = {}
        rv['rx_overrun'  : (stat >> 0) & 1]
        rv['rx_bad_frame': (stat >> 1) & 1]
        rv['tx_of'       : (stat >> 2) & 1]
        rv['tx_afull'    : (stat >> 3) & 1]
        rv['tx_led'      : (stat >> 4) & 1]
        rv['rx_led'      : (stat >> 5) & 1]
        rv['up'          : (stat >> 6) & 1]
        rv['eof_cnt'     : (stat >> 7) & (2**25-1)]
        return rv

    def status_reset(self):
        self.change_reg_bits('ctrl', 0, 18)
        self.change_reg_bits('ctrl', 1, 18)
        self.change_reg_bits('ctrl', 0, 18)

    def set_port(self, port):
        self.change_reg_bits('ctrl', port, 2, 16)

    def reset(self):
        # disable core
        self.change_reg_bits('ctrl', 0, 1)
        # toggle reset
        self.change_reg_bits('ctrl', 0, 0)
        self.change_reg_bits('ctrl', 1, 0)
        self.change_reg_bits('ctrl', 0, 0)

    def enable_tx(self):
        self.change_reg_bits('ctrl', 1, 1)


