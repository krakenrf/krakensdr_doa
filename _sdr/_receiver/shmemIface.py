"""
    HeIMDALL DAQ Firmware
    Python based shared memory interface implementations

    Author: Tamás Pető
    License: GNU GPL V3

   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import logging
import os
from multiprocessing import shared_memory
from struct import pack, unpack

import numpy as np

A_BUFF_READY = 1
B_BUFF_READY = 2
INIT_READY = 10
TERMINATE = 255


class outShmemIface:
    def __init__(self, shmem_name, shmem_size, drop_mode=False):
        self.init_ok = True
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.drop_mode = drop_mode
        self.dropped_frame_cntr = 0

        self.shmem_name = shmem_name
        self.buffer_free = [True, True]

        self.memories = []
        self.buffers = []

        # Try to remove shared memories if already exist
        try:
            shmem_A = shared_memory.SharedMemory(name=shmem_name + "_A", create=False, size=shmem_size)
            shmem_A.close()
            shmem_A.unlink()
            # shmem_A.unkink()
        except FileNotFoundError as err:
            self.logger.warning(f"Shared memory not exist: {err}")
        try:
            shmem_B = shared_memory.SharedMemory(name=shmem_name + "_B", create=False, size=shmem_size)
            shmem_B.close()
            shmem_B.unlink()
            # shmem_B.unkink()
        except FileNotFoundError as err:
            self.logger.warning(f"Shared memory not exist: {err}")

        # Create the shared memories
        self.memories.append(shared_memory.SharedMemory(name=shmem_name + "_A", create=True, size=shmem_size))
        self.memories.append(shared_memory.SharedMemory(name=shmem_name + "_B", create=True, size=shmem_size))
        self.buffers.append(np.ndarray((shmem_size,), dtype=np.uint8, buffer=self.memories[0].buf))
        self.buffers.append(np.ndarray((shmem_size,), dtype=np.uint8, buffer=self.memories[1].buf))

        # Opening control FIFOs
        if self.drop_mode:
            bw_fifo_flags = os.O_RDONLY | os.O_NONBLOCK
        else:
            bw_fifo_flags = os.O_RDONLY
        try:
            self.fw_ctr_fifo = os.open("_data_control/" + "fw_" + shmem_name, os.O_WRONLY)
            self.bw_ctr_fifo = os.open("_data_control/" + "bw_" + shmem_name, bw_fifo_flags)
        except OSError as err:
            self.logger.critical(f"OS error: {err}")
            self.logger.critical("Failed to open control fifos")
            self.bw_ctr_fifo = None
            self.fw_ctr_fifo = None
            self.init_ok = False

        # Send init ready signal
        if self.init_ok:
            os.write(self.fw_ctr_fifo, pack("B", INIT_READY))

    def send_ctr_buff_ready(self, active_buffer_index):
        # Send buffer ready signal on the forward FIFO
        if active_buffer_index == 0:
            os.write(self.fw_ctr_fifo, pack("B", A_BUFF_READY))
        elif active_buffer_index == 1:
            os.write(self.fw_ctr_fifo, pack("B", B_BUFF_READY))

        # Deassert buffer free flag
        self.buffer_free[active_buffer_index] = False

    def send_ctr_terminate(self):
        os.write(self.fw_ctr_fifo, pack("B", TERMINATE))
        self.logger.info("Terminate signal sent")

    def destory_sm_buffer(self):
        for memory in self.memories:
            memory.close()
            memory.unlink()

        if self.fw_ctr_fifo is not None:
            os.close(self.fw_ctr_fifo)

        if self.bw_ctr_fifo is not None:
            os.close(self.bw_ctr_fifo)

    def wait_buff_free(self):
        if self.buffer_free[0]:
            return 0
        elif self.buffer_free[1]:
            return 1
        else:
            try:
                buffer = os.read(self.bw_ctr_fifo, 1)
                signal = unpack("B", buffer)[0]

                if signal == A_BUFF_READY:
                    self.buffer_free[0] = True
                    return 0
                if signal == B_BUFF_READY:
                    self.buffer_free[1] = True
                    return 1
            except BlockingIOError as err:
                self.dropped_frame_cntr += 1
                self.logger.warning(f"Dropping frame.. Total: [{self.dropped_frame_cntr}] ")
                self.logger.warning(f"Due to: {err}")
        return -1


class inShmemIface:
    def __init__(self, shmem_name, ctr_fifo_path="_data_control/"):
        self.init_ok = True
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.drop_mode = False

        self.shmem_name = shmem_name

        self.memories = []
        self.buffers = []
        try:
            self.fw_ctr_fifo = os.open(ctr_fifo_path + "fw_" + shmem_name, os.O_RDONLY)
            self.bw_ctr_fifo = os.open(ctr_fifo_path + "bw_" + shmem_name, os.O_WRONLY)
        except OSError as err:
            self.logger.critical("OS error: {0}".format(err))
            self.logger.critical("Failed to open control fifos")
            self.bw_ctr_fifo = None
            self.fw_ctr_fifo = None
            self.init_ok = False

        if self.fw_ctr_fifo is not None:
            if unpack("B", os.read(self.fw_ctr_fifo, 1))[0] == INIT_READY:
                self.memories.append(shared_memory.SharedMemory(name=shmem_name + "_A"))
                self.memories.append(shared_memory.SharedMemory(name=shmem_name + "_B"))
                self.buffers.append(
                    np.ndarray(
                        (self.memories[0].size,),
                        dtype=np.uint8,
                        buffer=self.memories[0].buf,
                    )
                )
                self.buffers.append(
                    np.ndarray(
                        (self.memories[1].size,),
                        dtype=np.uint8,
                        buffer=self.memories[1].buf,
                    )
                )
            else:
                self.init_ok = False

    def send_ctr_buff_ready(self, active_buffer_index):
        if active_buffer_index == 0:
            os.write(self.bw_ctr_fifo, pack("B", A_BUFF_READY))
        elif active_buffer_index == 1:
            os.write(self.bw_ctr_fifo, pack("B", B_BUFF_READY))

    def destory_sm_buffer(self):
        for memory in self.memories:
            memory.close()

        if self.fw_ctr_fifo is not None:
            os.close(self.fw_ctr_fifo)

        if self.bw_ctr_fifo is not None:
            os.close(self.bw_ctr_fifo)

    def wait_buff_free(self):
        signal = unpack("B", os.read(self.fw_ctr_fifo, 1))[0]
        if signal == A_BUFF_READY:
            return 0
        elif signal == B_BUFF_READY:
            return 1
        elif signal == TERMINATE:
            return TERMINATE
        return -1
