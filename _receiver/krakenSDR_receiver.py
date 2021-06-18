# KrakenSDR Receiver

# Copyright (C) 2018-2020  Carl Laufer, Tamás Pető
#
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

# -*- coding: utf-8 -*-

# Import built-in modules
import sys
import time
from struct import pack, unpack
from scipy import signal
import socket
import _thread
from threading import Lock
import queue 
import logging

# Import third party modules
import numpy as np
from iq_header import IQHeader
from shmemIface import inShmemIface
class ReceiverRTLSDR():
    
    def __init__(self, data_que, data_interface = "eth"):     
        """
        Parameter:
        ----------        
            :param: data_que: Que to communicate with the UI (web iface/Qt GUI)        
            :param: data_interface: This field is configured by the GUI during instantiation. 
                                    Valid values are the followings:
                                    "eth"  : The module will receiver IQ frames through an Ethernet connection
                                    "shmem": The module will receiver IQ frames through a shared memory interface
            :type : data_interface: string
        """       
        self.logger = logging.getLogger(__name__)
        # DAQ parameters
        # These values are used by default to configure the DAQ through the configuration interface
        # Values are configured externally upon configuration request
        self.daq_center_freq   = 100 # MHz
        self.daq_rx_gain       = 0   # [dB]
        self.daq_squelch_th_dB = 0

        # UI interface
        self.data_que = data_que

        # IQ data interface 
        self.data_interface = data_interface
        
        # -> Ethernet
        self.receiver_connection_status = False
        self.port = 5000
        self.rec_ip_addr = "127.0.0.1" # Configured by the GUI prior to connection request
        self.socket_inst = socket.socket()
        self.receiverBufferSize = 2 ** 18  # Size of the Ethernet receiver buffer measured in bytes     
            
        # -> Shared memory
        self.init_data_iface()

        # Control interface
        self.ctr_iface_socket = socket.socket()
        self.ctr_iface_port = 5001
        self.ctr_iface_thread_lock = Lock() # Used to synchronize the operation of the ctr_iface thread
        
        self.iq_frame_bytes = None
        self.iq_samples = None
        self.iq_header = IQHeader()
        self.M = 0 # Number of receiver channels, updated after establishing connection
    
    def init_data_iface(self):
        if self.data_interface == "shmem":
            # Open shared memory interface to capture the DAQ firmware output
            self.in_shmem_iface = inShmemIface("delay_sync_iq", "../heimdall_daq_fw/Firmware/_data_control/")
            if not self.in_shmem_iface.init_ok:
                self.logger.critical("Shared memory initialization failed")
                self.in_shmem_iface.destory_sm_buffer()
                return -1
        return 0

            
    def eth_connect(self):        
        """
            Compatible only with DAQ firmwares that has the IQ streaming mode. 
            HeIMDALL DAQ Firmware version: 1.0 or later
        """
        try:
            if not self.receiver_connection_status:
                if self.data_interface == "eth":
                    # Establlish IQ data interface connection
                    self.socket_inst.connect((self.rec_ip_addr, self.port))            
                    self.socket_inst.sendall(str.encode('streaming'))                                
                    test_iq = self.receive_iq_frame()
                    
                    self.M = self.iq_header.active_ant_chs

                # Establish control interface connection
                self.ctr_iface_socket.connect((self.rec_ip_addr, self.ctr_iface_port))
                self.receiver_connection_status = True
                self.ctr_iface_init()
                self.set_center_freq(self.daq_center_freq)
                self.set_if_gain(self.daq_rx_gain)
                self.set_squelch_threshold(self.daq_squelch_th_dB)
        except:
            errorMsg = sys.exc_info()[0]
            self.logger.error("Error message: "+str(errorMsg))            
            self.receiver_connection_status = False
            self.logger.error("Unexpected error: {0}".format(sys.exc_info()[0]))
            
            # Re-instantiating sockets
            self.socket_inst = socket.socket()
            self.ctr_iface_socket = socket.socket()
            return -1            

        self.logger.info("Connection established")
        que_data_packet = []
        que_data_packet.append(['conn-ok',])
        self.data_que.put(que_data_packet)
        
    def eth_close(self):    
        """
            Close Ethernet conenctions including the IQ data and the control interfaces
        """                
        try:            
            if self.receiver_connection_status:
                if self.data_interface == "eth":
                    self.socket_inst.sendall(str.encode('q')) # Send exit message
                    self.socket_inst.close()                
                    self.socket_inst = socket.socket() # Re-instantiating socket

                # Close control interface connection
                exit_message_bytes=("EXIT".encode()+bytearray(124))
                self.ctr_iface_socket.send(exit_message_bytes)  
                self.ctr_iface_socket.close()
                self.ctr_iface_socket = socket.socket()

            self.receiver_connection_status = False
            que_data_packet = []
            que_data_packet.append(['disconn-ok',])
            self.data_que.put(que_data_packet)
        except:
            errorMsg = sys.exc_info()[0]
            self.logger.error("Error message: {0}".format(errorMsg))
            return -1
        
        if self.data_interface == "shmem":
            self.in_shmem_iface.destory_sm_buffer()     
        
        return 0

    def get_iq_online(self):   
        """
            This function obtains a new IQ data frame through the Ethernet IQ data or the shared memory interface
        """     
        # Check connection
        if not self.receiver_connection_status:
            fail = self.eth_connect()
            if fail:
                return -1
        
        if self.data_interface == "eth":
            self.socket_inst.sendall(str.encode("IQDownload")) # Send iq request command
            self.iq_samples = self.receive_iq_frame()      
                
        elif self.data_interface == "shmem":
            active_buff_index = self.in_shmem_iface.wait_buff_free()            
            if active_buff_index < 0 or active_buff_index > 1:
                self.logger.info("Terminating.., signal: {:d}".format(active_buff_index))                
                return -1       
            buffer = self.in_shmem_iface.buffers[active_buff_index]
            iq_header_bytes = buffer[0:1024].tobytes()
            self.iq_header.decode_header(iq_header_bytes)

            # Inititalization from header - Set channel numbers    
            if self.M == 0:
                self.M = self.iq_header.active_ant_chs
            
            incoming_payload_size = self.iq_header.cpi_length*self.iq_header.active_ant_chs*2*int(self.iq_header.sample_bit_depth/8)
            if incoming_payload_size > 0:
                iq_samples_in = (buffer[1024:1024 + incoming_payload_size].view(dtype=np.complex64))\
                                .reshape(self.iq_header.active_ant_chs, self.iq_header.cpi_length)
                self.iq_samples = iq_samples_in.copy()
            self.in_shmem_iface.send_ctr_buff_ready(active_buff_index)
            
    def receive_iq_frame(self):
        """
            Called by the get_iq_online function. Receives IQ samples over the establed Ethernet connection
        """
        total_received_bytes = 0
        recv_bytes_count = 0
        iq_header_bytes = bytearray(self.iq_header.header_size)  # allocate array
        view = memoryview(iq_header_bytes)  # Get buffer
        
        self.logger.debug("Starting IQ header reception")
        
        while total_received_bytes < self.iq_header.header_size:
            # Receive into buffer
            recv_bytes_count = self.socket_inst.recv_into(view, self.iq_header.header_size-total_received_bytes)            
            view = view[recv_bytes_count:]  # reset memory region
            total_received_bytes += recv_bytes_count
        
        self.iq_header.decode_header(iq_header_bytes)
        # Uncomment to check the content of the IQ header
        #self.iq_header.dump_header()
        
        incoming_payload_size = self.iq_header.cpi_length*self.iq_header.active_ant_chs*2*int(self.iq_header.sample_bit_depth/8)
        if incoming_payload_size > 0:
            # Calculate total bytes to receive from the iq header data        
            total_bytes_to_receive = incoming_payload_size
            receiver_buffer_size = 2**18
            
            self.logger.debug("Total bytes to receive: {:d}".format(total_bytes_to_receive))
            
            total_received_bytes = 0
            recv_bytes_count = 0
            iq_data_bytes = bytearray(total_bytes_to_receive + receiver_buffer_size)  # allocate array
            view = memoryview(iq_data_bytes)  # Get buffer
            
            while total_received_bytes < total_bytes_to_receive:
                # Receive into buffer
                recv_bytes_count = self.socket_inst.recv_into(view, receiver_buffer_size)
                view = view[recv_bytes_count:]  # reset memory region
                total_received_bytes += recv_bytes_count
            
            self.logger.debug(" IQ data succesfully received")
            
            # Convert raw bytes to Complex float64 IQ samples
            self.iq_samples = np.frombuffer(iq_data_bytes[0:total_bytes_to_receive], dtype=np.complex64).reshape(self.iq_header.active_ant_chs, self.iq_header.cpi_length)
            
            self.iq_frame_bytes =  bytearray()+iq_header_bytes+iq_data_bytes
            return self.iq_samples
        else:
             return 0

    def set_squelch_threshold(self, threshold_dB):
        """
            Configures the threshold level of the squelch module in the DAQ FW through the control interface
        """
        if self.receiver_connection_status: # Check connection                        
            self.daq_squelch_th_dB      = threshold_dB
            if threshold_dB == -80: threshold = 0
            else: threshold = 10**(threshold_dB/20)
                
            # Assembling message            
            cmd="STHU"
            th_bytes=pack("f",threshold)
            msg_bytes=(cmd.encode()+th_bytes+bytearray(120))           
            try:                
                _thread.start_new_thread(self.ctr_iface_communication, (msg_bytes,))            
            except:                
                errorMsg = sys.exc_info()[0]        
                self.logger.error("Unable to start communication thread")
                self.logger.error("Error message: {:s}".format(errorMsg))

    def ctr_iface_init(self):
        """
            Initialize connection with the DAQ FW through the control interface
        """
        if self.receiver_connection_status: # Check connection
            # Assembling message            
            cmd="INIT"            
            msg_bytes=(cmd.encode()+bytearray(124))           
            try:                
                _thread.start_new_thread(self.ctr_iface_communication, (msg_bytes,))            
            except:                
                errorMsg = sys.exc_info()[0]        
                self.logger.error("Unable to start communication thread")
                self.logger.error("Error message: {:s}".format(errorMsg))

    def ctr_iface_communication(self, msg_bytes):
        """
            Handles communication on the control interface with the DAQ FW

            Parameters:
            -----------

                :param: msg: Message bytes, that will be sent ont the control interface
                :type:  msg: Byte array                
        """ 
        self.ctr_iface_thread_lock.acquire()
        self.logger.debug("Sending control message")        
        self.ctr_iface_socket.send(msg_bytes)
        
        # Waiting for the command to take effect
        reply_msg_bytes = self.ctr_iface_socket.recv(128)    

        self.logger.debug("Control interface communication finished")                
        self.ctr_iface_thread_lock.release()
        
        status = reply_msg_bytes[0:4].decode()
        if status == "FNSD":
            self.logger.info("Reconfiguration succesfully finished")
            que_data_packet = []
            que_data_packet.append(['config-ok',])
            self.data_que.put(que_data_packet)
            
        else:
            self.logger.error("Failed to set the requested parameter, reply: {0}".format(status))
        
    def set_center_freq(self, center_freq):
        """
            Configures the RF center frequency of the receiver through the control interface
        
            Paramters:
            ----------
                :param: center_freq: Required center frequency to set [Hz]
                :type:  center_freq: int
        """
        if self.receiver_connection_status: # Check connection
            self.daq_center_freq = center_freq
            # Set center frequency
            cmd="FREQ"
            freq_bytes=pack("Q",center_freq)
            msg_bytes=(cmd.encode()+freq_bytes+bytearray(116))           
            try:                
                _thread.start_new_thread(self.ctr_iface_communication, (msg_bytes,))            
            except:                
                errorMsg = sys.exc_info()[0]        
                self.logger.error("Unable to start communication thread")
                self.logger.error("Error message: {:s}".format(errorMsg))
    
    def set_if_gain(self, gain):
        """
            Configures the IF gain of the receiver through the control interface
        
            Paramters:
            ----------
                :param: gain: IF gain value [dB]
                :type:  gain: int
        """
        if self.receiver_connection_status: # Check connection
            self.daq_rx_gain     = gain

            # Set center frequency
            cmd="GAIN"
            gain_list=[int(gain*10)]*self.M
            gain_bytes=pack("I"*self.M, *gain_list)
            msg_bytes=(cmd.encode()+gain_bytes+bytearray(128-(self.M+1)*4))
            try:                
                _thread.start_new_thread(self.ctr_iface_communication, (msg_bytes,))            
            except:                
                errorMsg = sys.exc_info()[0]        
                self.logger.error("Unable to start communication thread")
                self.logger.error("Error message: {:s}".format(errorMsg))

    def close(self):
        """
            Disconnet the receiver module and the DAQ FW
        """
        self.eth_close()
        