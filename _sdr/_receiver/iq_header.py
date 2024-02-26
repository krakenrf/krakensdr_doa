import logging
from struct import pack, unpack

"""
    Desctiption: IQ Frame header definition
    For header field description check the corresponding documentation
    Total length: 1024 byte
    Project: HeIMDALL RTL
    Author: Tamás Pető
    Status: Finished
    Version history:
            1 : Initial version (2019 04 23)
            2 : Fixed 1024 byte length (2019 07 25)
            3 : Noise source state (2019 10 01)
            4 : IQ sync flag (2019 10 21)
            5 : Sync state (2019 11 10)
            6 : Unix Epoch timestamp (2019 12 17)
            6a: Frame type defines (2020 03 19)
            7 : Sync word (2020 05 03)
"""


class IQHeader:
    FRAME_TYPE_DATA = 0
    FRAME_TYPE_DUMMY = 1
    FRAME_TYPE_RAMP = 2
    FRAME_TYPE_CAL = 3
    FRAME_TYPE_TRIGW = 4
    FRAME_TYPE_EMPTY = 5

    SYNC_WORD = 0x2BF7B95A

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.header_size = 1024  # size in bytes
        self.reserved_bytes = 192

        self.sync_word = 0  # uint32_t
        self.frame_type = self.FRAME_TYPE_EMPTY  # uint32_t
        self.hardware_id = ""  # char [16]
        self.unit_id = 0  # uint32_t
        self.active_ant_chs = 0  # uint32_t
        self.ioo_type = 0  # uint32_t
        self.rf_center_freq = 0  # uint64_t
        self.adc_sampling_freq = 0  # uint64_t
        self.sampling_freq = 0  # uint64_t
        self.cpi_length = 0  # uint32_t
        self.time_stamp = 0  # uint64_t
        self.daq_block_index = 0  # uint32_t
        self.cpi_index = 0  # uint32_t
        self.ext_integration_cntr = 0  # uint64_t
        self.data_type = 0  # uint32_t
        self.sample_bit_depth = 0  # uint32_t
        self.adc_overdrive_flags = 0  # uint32_t
        self.if_gains = [0] * 32  # uint32_t x 32
        self.delay_sync_flag = 0  # uint32_t
        self.iq_sync_flag = 0  # uint32_t
        self.sync_state = 0  # uint32_t
        self.noise_source_state = 0  # uint32_t
        self.reserved = [0] * self.reserved_bytes  # uint32_t x reserverd_bytes
        self.header_version = 0  # uint32_t

    def decode_header(self, iq_header_byte_array):
        """
        Unpack,decode and store the content of the iq header
        """
        iq_header_list = unpack(
            "II16sIIIQQQIQIIQIII" + "I" * 32 + "IIII" + "I" * self.reserved_bytes + "I",
            iq_header_byte_array,
        )

        self.sync_word = iq_header_list[0]
        self.frame_type = iq_header_list[1]
        self.hardware_id = iq_header_list[2].decode()
        self.unit_id = iq_header_list[3]
        self.active_ant_chs = iq_header_list[4]
        self.ioo_type = iq_header_list[5]
        self.rf_center_freq = iq_header_list[6]
        self.adc_sampling_freq = iq_header_list[7]
        self.sampling_freq = iq_header_list[8]
        self.cpi_length = iq_header_list[9]
        self.time_stamp = iq_header_list[10]
        self.daq_block_index = iq_header_list[11]
        self.cpi_index = iq_header_list[12]
        self.ext_integration_cntr = iq_header_list[13]
        self.data_type = iq_header_list[14]
        self.sample_bit_depth = iq_header_list[15]
        self.adc_overdrive_flags = iq_header_list[16]
        self.if_gains = iq_header_list[17:49]
        self.delay_sync_flag = iq_header_list[49]
        self.iq_sync_flag = iq_header_list[50]
        self.sync_state = iq_header_list[51]
        self.noise_source_state = iq_header_list[52]
        self.header_version = iq_header_list[52 + self.reserved_bytes + 1]

    def encode_header(self):
        """
        Pack the iq header information into a byte array
        """
        iq_header_byte_array = pack("II", self.sync_word, self.frame_type)
        iq_header_byte_array += self.hardware_id.encode() + bytearray(16 - len(self.hardware_id.encode()))
        iq_header_byte_array += pack(
            "IIIQQQIQIIQIII",
            self.unit_id,
            self.active_ant_chs,
            self.ioo_type,
            self.rf_center_freq,
            self.adc_sampling_freq,
            self.sampling_freq,
            self.cpi_length,
            self.time_stamp,
            self.daq_block_index,
            self.cpi_index,
            self.ext_integration_cntr,
            self.data_type,
            self.sample_bit_depth,
            self.adc_overdrive_flags,
        )
        for m in range(32):
            iq_header_byte_array += pack("I", self.if_gains[m])

        iq_header_byte_array += pack("I", self.delay_sync_flag)
        iq_header_byte_array += pack("I", self.iq_sync_flag)
        iq_header_byte_array += pack("I", self.sync_state)
        iq_header_byte_array += pack("I", self.noise_source_state)

        for _ in range(self.reserved_bytes):
            iq_header_byte_array += pack("I", 0)

        iq_header_byte_array += pack("I", self.header_version)
        return iq_header_byte_array

    def dump_header(self):
        """
        Prints out the content of the header in human readable format
        """
        self.logger.info("Sync word: {:d}".format(self.sync_word))
        self.logger.info("Header version: {:d}".format(self.header_version))
        self.logger.info("Frame type: {:d}".format(self.frame_type))
        self.logger.info("Hardware ID: {:16}".format(self.hardware_id))
        self.logger.info("Unit ID: {:d}".format(self.unit_id))
        self.logger.info("Active antenna channels: {:d}".format(self.active_ant_chs))
        self.logger.info("Illuminator type: {:d}".format(self.ioo_type))
        self.logger.info("RF center frequency: {:.2f} MHz".format(self.rf_center_freq / 10**6))
        self.logger.info("ADC sampling frequency: {:.2f} MHz".format(self.adc_sampling_freq / 10**6))
        self.logger.info("IQ sampling frequency {:.2f} MHz".format(self.sampling_freq / 10**6))
        self.logger.info("CPI length: {:d}".format(self.cpi_length))
        self.logger.info("Unix Epoch timestamp: {:d}".format(self.time_stamp))
        self.logger.info("DAQ block index: {:d}".format(self.daq_block_index))
        self.logger.info("CPI index: {:d}".format(self.cpi_index))
        self.logger.info("Extended integration counter {:d}".format(self.ext_integration_cntr))
        self.logger.info("Data type: {:d}".format(self.data_type))
        self.logger.info("Sample bit depth: {:d}".format(self.sample_bit_depth))
        self.logger.info("ADC overdrive flags: {:d}".format(self.adc_overdrive_flags))
        for m in range(32):
            self.logger.info("Ch: {:d} IF gain: {:.1f} dB".format(m, self.if_gains[m] / 10))
        self.logger.info("Delay sync  flag: {:d}".format(self.delay_sync_flag))
        self.logger.info("IQ sync  flag: {:d}".format(self.iq_sync_flag))
        self.logger.info("Sync state: {:d}".format(self.sync_state))
        self.logger.info("Noise source state: {:d}".format(self.noise_source_state))

    def check_sync_word(self):
        """
        Check the sync word of the header
        """
        if self.sync_word != self.SYNC_WORD:
            return -1
        else:
            return 0
