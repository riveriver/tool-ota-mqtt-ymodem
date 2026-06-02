"""
YMODEM Fault Injector for testing error handling in OTA transfers.
Simulates various real-world network and protocol errors.
"""
import os
import time
import random
from typing import Optional, Callable, Dict, Any


class FaultConfig:
    """Configuration for fault injection scenarios"""
    
    def __init__(self):
        # Packet-specific faults (packet_num -> fault_type)
        self.packet_faults: Dict[int, str] = {}
        
        # Probability-based faults (apply to all packets)
        self.ack_loss_probability = 0.0        # Randomly drop ACKs
        self.ack_delay_ms = 0                   # Add delay before ACK
        self.ack_corrupted_probability = 0.0   # Send wrong response
        self.data_corruption_probability = 0.0  # Corrupt received data
        self.duplicate_ack_probability = 0.0    # Send duplicate ACK
        self.ack_timeout_extension = 0          # Extend timeout artificially
        
        # Specific packet faults
        self.packet_delay_map: Dict[int, int] = {}  # packet_num -> delay_ms
        self.packet_loss_map: Dict[int, bool] = {}   # packet_num -> is_lost
        self.packet_corruption_map: Dict[int, bytes] = {}  # packet_num -> corrupt_bytes
        
        # Scenario presets
        self.scenario = None  # 'high_latency', 'packet_loss', 'corrupted_data', etc.


class Ymodem:
    def __init__(self, chunk_size=1024, fault_config: Optional[FaultConfig] = None):
        self.chunk_size = chunk_size
        self.fault_config = fault_config or FaultConfig()
        self.stats = {
            'acks_dropped': 0,
            'packets_delayed': 0,
            'packets_corrupted': 0,
            'duplicate_acks_sent': 0,
            'total_retries': 0,
        }

    def _apply_scenario(self):
        """Apply preset fault scenarios"""
        if not self.fault_config.scenario:
            return
            
        scenario = self.fault_config.scenario.lower()
        
        if scenario == 'high_latency':
            self.fault_config.ack_delay_ms = random.randint(500, 2000)
            print(f"[FAULT] Scenario: High Latency - ACK delays {self.fault_config.ack_delay_ms}ms", flush=True)
            
        elif scenario == 'packet_loss':
            self.fault_config.ack_loss_probability = 0.15  # 15% ACK loss
            print(f"[FAULT] Scenario: Packet Loss - 15% ACK drop rate", flush=True)
            
        elif scenario == 'intermittent':
            self.fault_config.ack_loss_probability = 0.05
            self.fault_config.ack_delay_ms = random.randint(100, 500)
            print(f"[FAULT] Scenario: Intermittent Issues - 5% loss + {self.fault_config.ack_delay_ms}ms delay", flush=True)
            
        elif scenario == 'corrupted_data':
            self.fault_config.data_corruption_probability = 0.1
            print(f"[FAULT] Scenario: Data Corruption - 10% corruption rate", flush=True)
            
        elif scenario == 'duplicate_acks':
            self.fault_config.duplicate_ack_probability = 0.2
            print(f"[FAULT] Scenario: Duplicate ACKs - 20% duplication rate", flush=True)

    def _should_drop_ack(self, packet_num: int) -> bool:
        """Decide if ACK should be dropped"""
        if packet_num in self.fault_config.packet_loss_map:
            lost = self.fault_config.packet_loss_map[packet_num]
            if lost:
                print(f"[FAULT] Packet {packet_num}: ACK dropped (configured)", flush=True)
                self.stats['acks_dropped'] += 1
            return lost
            
        if random.random() < self.fault_config.ack_loss_probability:
            print(f"[FAULT] Packet {packet_num}: ACK dropped (random)", flush=True)
            self.stats['acks_dropped'] += 1
            return True
        return False

    def _get_ack_delay(self, packet_num: int) -> int:
        """Get ACK delay for a packet"""
        if packet_num in self.fault_config.packet_delay_map:
            delay = self.fault_config.packet_delay_map[packet_num]
            if delay > 0:
                print(f"[FAULT] Packet {packet_num}: Delaying ACK by {delay}ms", flush=True)
                self.stats['packets_delayed'] += 1
            return delay
            
        if self.fault_config.ack_delay_ms > 0:
            jitter = random.randint(-50, 50)
            actual_delay = max(0, self.fault_config.ack_delay_ms + jitter)
            return actual_delay
        return 0

    def _should_corrupt_data(self, packet_num: int) -> Optional[bytes]:
        """Decide if data should be corrupted and return corruption"""
        if packet_num in self.fault_config.packet_corruption_map:
            corrupt_data = self.fault_config.packet_corruption_map[packet_num]
            print(f"[FAULT] Packet {packet_num}: Data corrupted (configured)", flush=True)
            self.stats['packets_corrupted'] += 1
            return corrupt_data
            
        if random.random() < self.fault_config.data_corruption_probability:
            # Flip a few random bits
            num_bits = random.randint(1, 3)
            print(f"[FAULT] Packet {packet_num}: Data corrupted - {num_bits} bits flipped (random)", flush=True)
            self.stats['packets_corrupted'] += 1
            return None  # Signal to caller to flip bits
            
        return None

    def _should_duplicate_ack(self, packet_num: int) -> bool:
        """Decide if ACK should be duplicated"""
        if random.random() < self.fault_config.duplicate_ack_probability:
            print(f"[FAULT] Packet {packet_num}: Duplicate ACK will be sent", flush=True)
            self.stats['duplicate_acks_sent'] += 1
            return True
        return False

    def send(self, file_obj, publish_fn=None, topic=None, recv_queue=None, timeout=30, 
             should_stop=None, wait_for_initial_crc=True, initial_crc_timeout=180, block0_timeout=180):
        """Enhanced send with fault injection capability"""
        
        self._apply_scenario()
        
        def crc16_ccitt(data: bytes, poly=0x1021, init=0x0000):
            crc = init
            for b in data:
                crc ^= (b << 8)
                for _ in range(8):
                    if crc & 0x8000:
                        crc = ((crc << 1) & 0xFFFF) ^ poly
                    else:
                        crc = (crc << 1) & 0xFFFF
            return crc & 0xFFFF

        SOH = 0x01
        STX = 0x02
        EOT = 0x04
        ACK = 0x06
        NAK = 0x15
        CAN = 0x18
        CRCCHR = ord('C')

        if isinstance(file_obj, str):
            f = open(file_obj, 'rb')
            close_after = True
        else:
            f = file_obj
            close_after = False

        if recv_queue is None:
            recv_queue = getattr(self, 'recv_queue', None)

        try:
            if publish_fn is None or topic is None or recv_queue is None:
                while True:
                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break
                    publish_fn(topic, chunk)
                return True

            def publish_packet(data: bytes):
                try:
                    publish_fn(topic, data)
                except Exception:
                    pass

            def wait_for(expected_set, timeout_sec, not_before=None):
                """Wait for one of expected bytes, with fault injection"""
                end = time.time() + timeout_sec
                while time.time() < end:
                    if callable(should_stop) and should_stop():
                        return None
                    try:
                        item = recv_queue.get(timeout=0.5)
                    except Exception:
                        continue
                    if item is None:
                        continue
                        
                    tpc = None
                    payload = item
                    item_ts = None
                    if isinstance(item, tuple) and len(item) >= 2:
                        tpc, payload = item[0], item[1]
                        if len(item) >= 3:
                            item_ts = item[2]

                    if not_before is not None and item_ts is not None and item_ts < not_before:
                        continue

                    if isinstance(payload, str):
                        payload_bytes = payload.encode(errors='ignore')
                    else:
                        payload_bytes = payload

                    # Log received response
                    if tpc is not None:
                        print(f"[RECV] Received from {tpc}: {repr(payload_bytes)}", flush=True)
                    else:
                        print(f"[RECV] Received: {repr(payload_bytes)}", flush=True)

                    for b in payload_bytes:
                        if b in expected_set:
                            return b
                    try:
                        s = None
                        if isinstance(payload_bytes, (bytes, bytearray)):
                            try:
                                s = payload_bytes.decode('ascii').strip()
                            except Exception:
                                s = None
                        if s:
                            s2 = ''.join(s.split())
                            if len(s2) % 2 == 0:
                                import string
                                if all(c in string.hexdigits for c in s2):
                                    try:
                                        hb = bytes.fromhex(s2)
                                        for b in hb:
                                            if b in expected_set:
                                                return b
                                    except Exception:
                                        pass
                    except Exception:
                        pass
                return None

            def confirm_ack_stable(settle_sec=0.25):
                """After ACK, briefly detect late NAK/CAN before moving on."""
                end = time.monotonic() + settle_sec
                while time.monotonic() < end:
                    if callable(should_stop) and should_stop():
                        return None
                    remaining = end - time.monotonic()
                    if remaining <= 0:
                        break
                    try:
                        item = recv_queue.get(timeout=min(0.05, remaining))
                    except Exception:
                        continue
                    if item is None:
                        continue
                    tpc = None
                    payload = item
                    item_ts = None
                    if isinstance(item, tuple) and len(item) >= 2:
                        tpc, payload = item[0], item[1]
                        if len(item) >= 3:
                            item_ts = item[2]
                    if item_ts is not None and item_ts < time.monotonic() - settle_sec:
                        continue
                    if isinstance(payload, str):
                        payload_bytes = payload.encode(errors='ignore')
                    else:
                        payload_bytes = payload
                    for b in payload_bytes:
                        if b == NAK or b == CAN:
                            try:
                                if tpc is not None:
                                    print(f"Late response after ACK from {tpc}: {b:02x}", flush=True)
                                else:
                                    print(f"Late response after ACK: {b:02x}", flush=True)
                            except Exception:
                                pass
                            return b
                return ACK

            if wait_for_initial_crc:
                print(f"Waiting for 'C' from receiver (timeout {initial_crc_timeout}s)...", flush=True)
                b = wait_for({CRCCHR}, initial_crc_timeout)
                if b is None:
                    return False

            filepath = getattr(f, 'name', None)
            filename = os.path.basename(filepath) if filepath else ''
            try:
                size = os.path.getsize(filepath) if filepath and isinstance(filepath, str) else None
            except Exception:
                size = None
            meta = (filename or '').encode() + b'\0' + (str(size).encode() if size is not None else b'') + b'\0'
            block0_data = meta.ljust(128, b'\0')

            try:
                total_packets = (size + 1023) // 1024 if size is not None else 0
            except Exception:
                total_packets = 0
            print(f"Total data packets to send: {total_packets}")

            def make_packet(pktno, data, use_stx=False):
                if use_stx:
                    header = bytes([STX, pktno & 0xFF, (~pktno) & 0xFF])
                    length = 1024
                else:
                    header = bytes([SOH, pktno & 0xFF, (~pktno) & 0xFF])
                    length = 128
                if len(data) < length:
                    pad_byte = 0x1A if use_stx else 0x00
                    data = data + bytes([pad_byte]) * (length - len(data))
                crc = crc16_ccitt(data)
                crc_bytes = bytes([(crc >> 8) & 0xFF, crc & 0xFF])
                return header + data + crc_bytes

            retries = 10
            def fmt_expected(eset):
                return ",".join(f"{b:02x}" for b in sorted(eset))

            # Send block 0
            for attempt in range(retries):
                if callable(should_stop) and should_stop():
                    return False
                pkt = make_packet(0, block0_data, use_stx=False)
                print(f"Sending block 0 (attempt {attempt+1}/{retries})...", flush=True)
                publish_packet(pkt)
                print(f"Waiting for ACK/NAK for block 0 (timeout {block0_timeout}s)... expected: {fmt_expected({ACK,NAK,CAN})}", flush=True)
                
                # Check if we should drop this ACK
                if self._should_drop_ack(0):
                    continue
                
                # Apply delay
                delay_ms = self._get_ack_delay(0)
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
                
                r = wait_for({ACK, NAK, CAN}, block0_timeout, not_before=time.monotonic())
                if r == ACK:
                    stable = confirm_ack_stable()
                    if stable == NAK:
                        continue
                    if stable == CAN:
                        return False
                    break
                if r == NAK:
                    continue
                if r == CAN:
                    return False
                if r is None:
                    print(f"Timeout waiting for ACK/NAK for block 0, retrying...", flush=True)
                    self.stats['total_retries'] += 1
                    continue
            else:
                return False

            print(f"Waiting for 'C' or ACK before data blocks... expected: {fmt_expected({CRCCHR,ACK})}", flush=True)
            b = wait_for({CRCCHR, ACK}, timeout)

            # Send data blocks
            seq = 1
            while True:
                if callable(should_stop) and should_stop():
                    return False
                data = f.read(1024)
                if not data:
                    break
                pkt = make_packet(seq % 256, data, use_stx=True)
                for attempt in range(retries):
                    if callable(should_stop) and should_stop():
                        return False
                    print(f"Sending data packet {seq} (attempt {attempt+1}/{retries})...", flush=True)
                    publish_packet(pkt)
                    print(f"Waiting for ACK/NAK for packet {seq}... expected: {fmt_expected({ACK,NAK,CAN})}", flush=True)
                    
                    # Check if we should drop this ACK
                    if self._should_drop_ack(seq):
                        continue
                    
                    # Apply delay
                    delay_ms = self._get_ack_delay(seq)
                    if delay_ms > 0:
                        time.sleep(delay_ms / 1000.0)
                    
                    r = wait_for({ACK, NAK, CAN}, timeout, not_before=time.monotonic())
                    
                    # Check for duplicate ACK
                    if r == ACK and self._should_duplicate_ack(seq):
                        print(f"[FAULT] Sending duplicate ACK for packet {seq}", flush=True)
                        # This would be received in the next wait_for call
                    
                    if r == ACK:
                        stable = confirm_ack_stable()
                        if stable == NAK:
                            continue
                        if stable == CAN:
                            return False
                        break
                    if r == NAK:
                        continue
                    if r == CAN:
                        return False
                    if r is None:
                        print(f"Timeout waiting for ACK/NAK for packet {seq}, retrying...", flush=True)
                        self.stats['total_retries'] += 1
                        continue
                else:
                    return False
                seq += 1

            # Send EOT
            for attempt in range(retries):
                if callable(should_stop) and should_stop():
                    return False
                print(f"Sending EOT (attempt {attempt+1}/{retries})...", flush=True)
                publish_packet(bytes([EOT]))
                print(f"Waiting for ACK for EOT... expected: {fmt_expected({ACK,NAK,CAN})}", flush=True)
                
                if self._should_drop_ack(-1):  # EOT has special packet num
                    continue
                
                delay_ms = self._get_ack_delay(-1)
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
                
                r = wait_for({ACK, NAK, CAN}, timeout, not_before=time.monotonic())
                if r == ACK:
                    stable = confirm_ack_stable()
                    if stable == NAK:
                        continue
                    if stable == CAN:
                        return False
                    break
                if r == NAK:
                    continue
                if r == CAN:
                    return False
                if r is None:
                    print("Timeout waiting for ACK for EOT, retrying...", flush=True)
                    self.stats['total_retries'] += 1
                    continue
            else:
                return False

            print(f"Waiting for 'C' before final block (timeout {timeout}s)... expected: {fmt_expected({CRCCHR})}", flush=True)
            b = wait_for({CRCCHR}, timeout)
            
            final_block = make_packet(0, b'', use_stx=False)
            for attempt in range(retries):
                if callable(should_stop) and should_stop():
                    return False
                print(f"Sending final block 0 (attempt {attempt+1}/{retries})...", flush=True)
                publish_packet(final_block)
                print(f"Waiting for ACK/NAK for final block... expected: {fmt_expected({ACK,NAK,CAN})}", flush=True)
                
                if self._should_drop_ack(0):  # Reuse block 0 fault config
                    continue
                
                delay_ms = self._get_ack_delay(0)
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
                
                r = wait_for({ACK, NAK, CAN}, timeout, not_before=time.monotonic())
                if r == ACK:
                    stable = confirm_ack_stable()
                    if stable == NAK:
                        continue
                    if stable == CAN:
                        return False
                    return True
                if r == NAK:
                    continue
                if r == CAN:
                    return False
                if r is None:
                    print("Timeout waiting for ACK/NAK for final block, retrying...", flush=True)
                    self.stats['total_retries'] += 1
                    continue
            return False
        finally:
            if close_after:
                f.close()
            
            # Print fault injection statistics
            print("\n[FAULT INJECTION STATS]", flush=True)
            for key, value in self.stats.items():
                print(f"  {key}: {value}", flush=True)

    def receive(self):
        raise NotImplementedError()
