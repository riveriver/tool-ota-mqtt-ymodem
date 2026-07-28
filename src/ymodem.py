import os
import time


class Ymodem:
    def __init__(self, chunk_size=1024):
        # chunk_size: bytes per data packet when publishing over MQTT
        self.chunk_size = chunk_size

    def send(self, file_obj, publish_fn=None, topic=None, recv_queue=None, timeout=30, should_stop=None, wait_for_initial_crc=True):
        """Send a file-like object using a YMODEM-like protocol over MQTT.

        This implements a simplified YMODEM sender with CRC handshake:
        - Waits for receiver to send 'C' (0x43) to request CRC-transfer
        - Sends block 0 (filename/size) as 128-byte SOH packet
        - Sends data blocks as 1024-byte STX packets, waiting for ACK after each
        - Sends EOT and final empty block0

        Parameters:
        - file_obj: file-like object opened in 'rb' mode OR a filepath string
        - publish_fn: callable(topic, payload) used to publish each packet
        - topic: MQTT topic to publish to
        - recv_queue: Queue that receives raw payload bytes from the receiver
        - timeout: seconds to wait for expected responses

        Returns True on success, False on failure.
        """
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

        # support passing path string
        if isinstance(file_obj, str):
            f = open(file_obj, 'rb')
            close_after = True
        else:
            f = file_obj
            close_after = False
        # recv_queue and timeout are provided as parameters; if not provided, try
        # to read a recv_queue attribute on self as a fallback
        if recv_queue is None:
            recv_queue = getattr(self, 'recv_queue', None)

        try:
            if publish_fn is None or topic is None or recv_queue is None:
                # fallback to simple chunked send without handshake
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
                    # swallow publish errors; caller may detect failures separately
                    pass

            pending_response = bytearray()

            def wait_for(expected_set, timeout_sec):
                """Wait for one of expected bytes (set of ints) from recv_queue within timeout."""
                end = time.time() + timeout_sec

                def take_expected(payload_bytes):
                    for idx, b in enumerate(payload_bytes):
                        if b in expected_set:
                            pending_response.extend(payload_bytes[idx + 1:])
                            return b
                    return None

                while time.time() < end:
                    if callable(should_stop) and should_stop():
                        return None

                    if pending_response:
                        payload_bytes = bytes(pending_response)
                        pending_response.clear()
                        b = take_expected(payload_bytes)
                        if b is not None:
                            print(
                                f"Received buffered response: {repr(payload_bytes)}",
                                flush=True,
                            )
                            return b

                    try:
                        item = recv_queue.get(timeout=0.5)
                    except Exception:
                        continue
                    if item is None:
                        continue
                    # support (topic, payload) tuples pushed by CLI
                    tpc = None
                    payload = item
                    if isinstance(item, tuple) and len(item) >= 2:
                        tpc, payload = item[0], item[1]
                    # ensure bytes
                    if isinstance(payload, str):
                        payload_bytes = payload.encode(errors='ignore')
                    else:
                        payload_bytes = payload
                    try:
                        if tpc is not None:
                            print(f"Received response from {tpc}: {repr(payload_bytes)}", flush=True)
                        else:
                            print(f"Received response: {repr(payload_bytes)}", flush=True)
                    except Exception:
                        pass
                    # First, inspect raw bytes
                    b = take_expected(payload_bytes)
                    if b is not None:
                        return b
                    # If not found, try interpreting payload as ASCII hex string (e.g. '06322c43')
                    try:
                        s = None
                        if isinstance(payload_bytes, (bytes, bytearray)):
                            try:
                                s = payload_bytes.decode('ascii').strip()
                            except Exception:
                                s = None
                        if s:
                            # remove spaces
                            s2 = ''.join(s.split())
                            if len(s2) % 2 == 0:
                                import string
                                if all(c in string.hexdigits for c in s2):
                                    try:
                                        hb = bytes.fromhex(s2)
                                        b = take_expected(hb)
                                        if b is not None:
                                            return b
                                    except Exception:
                                        pass
                    except Exception:
                        pass
                return None

            # Optionally wait for initial 'C' (CRC request). Some workflows skip this.
            if wait_for_initial_crc:
                # allow long timeout for remote module to start (e.g., 3 minutes)
                print(f"Waiting for 'C' from receiver (timeout {timeout}s)...", flush=True)
                b = wait_for({CRCCHR}, timeout)
                if b is None:
                    return False

            # prepare block 0 (SOH, 128 bytes) with filename and size
            filepath = getattr(f, 'name', None)
            filename = os.path.basename(filepath) if filepath else ''
            try:
                size = os.path.getsize(filepath) if filepath and isinstance(filepath, str) else None
            except Exception:
                size = None
            meta = (filename or '').encode() + b'\0' + (str(size).encode() if size is not None else b'') + b'\0'
            block0_data = meta.ljust(128, b'\0')

            # compute total data packets (1K blocks)
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
                    # pad with 0x1A for data packets, 0x00 for block0
                    pad_byte = 0x1A if use_stx else 0x00
                    data = data + bytes([pad_byte]) * (length - len(data))
                crc = crc16_ccitt(data)
                crc_bytes = bytes([(crc >> 8) & 0xFF, crc & 0xFF])
                return header + data + crc_bytes

            # send block0, wait for ACK
            retries = 10
            def fmt_expected(eset):
                return ",".join(f"{b:02x}" for b in sorted(eset))

            for attempt in range(retries):
                if callable(should_stop) and should_stop():
                    return False
                pkt = make_packet(0, block0_data, use_stx=False)
                print(f"Sending block 0 (attempt {attempt+1}/{retries})...", flush=True)
                publish_packet(pkt)
                print(f"Waiting for ACK/NAK for block 0... expected: {fmt_expected({ACK,NAK,CAN})}", flush=True)
                r = wait_for({ACK, NAK, CAN}, timeout)
                if r == ACK:
                    break
                if r == NAK:
                    continue
                if r == CAN:
                    return False
                if r is None:
                    print(f"Timeout waiting for ACK/NAK for block 0, retrying...", flush=True)
                    continue
            else:
                return False

            # after ACK, wait for 'C' before data blocks (some receivers send 'C')
            print(f"Waiting for 'C' or ACK before data blocks... expected: {fmt_expected({CRCCHR,ACK})}", flush=True)
            b = wait_for({CRCCHR, ACK}, timeout)
            # proceed when 'C' or ACK seen; if ACK seen, still proceed

            # send data blocks
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
                    r = wait_for({ACK, NAK, CAN}, timeout)
                    if r == ACK:
                        break
                    if r == NAK:
                        continue
                    if r == CAN:
                        return False
                    if r is None:
                        print(f"Timeout waiting for ACK/NAK for packet {seq}, retrying...", flush=True)
                        continue
                else:
                    return False
                seq += 1

            # send EOT until ACK
            for attempt in range(retries):
                if callable(should_stop) and should_stop():
                    return False
                print(f"Sending EOT (attempt {attempt+1}/{retries})...", flush=True)
                publish_packet(bytes([EOT]))
                print(f"Waiting for ACK for EOT... expected: {fmt_expected({ACK,NAK,CAN})}", flush=True)
                r = wait_for({ACK, NAK, CAN}, timeout)
                if r == ACK:
                    break
                if r == NAK:
                    continue
                if r == CAN:
                    return False
                if r is None:
                    print("Timeout waiting for ACK for EOT, retrying...", flush=True)
                    continue
            else:
                return False

            # wait for 'C' before final block
            print(f"Waiting for 'C' before final block (timeout {timeout}s)... expected: {fmt_expected({CRCCHR})}", flush=True)
            b = wait_for({CRCCHR}, timeout)
            # send final empty block0
            final_block = make_packet(0, b'', use_stx=False)
            for attempt in range(retries):
                if callable(should_stop) and should_stop():
                    return False
                print(f"Sending final block 0 (attempt {attempt+1}/{retries})...", flush=True)
                publish_packet(final_block)
                print(f"Waiting for ACK/NAK for final block... expected: {fmt_expected({ACK,NAK,CAN})}", flush=True)
                r = wait_for({ACK, NAK, CAN}, timeout)
                if r == ACK:
                    return True
                if r == NAK:
                    continue
                if r == CAN:
                    return False
                if r is None:
                    print("Timeout waiting for ACK/NAK for final block, retrying...", flush=True)
                    continue
            return False
        finally:
            if close_after:
                f.close()

    def receive(self):
        # Full Ymodem receive implementation is not provided in this project.
        raise NotImplementedError()
