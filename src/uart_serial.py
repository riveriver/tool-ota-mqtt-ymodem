class UARTSerial:
    def __init__(self, port, baudrate=115200):
        import serial
        self.serial = serial.Serial(port, baudrate)

    def send_data(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        self.serial.write(data)

    def receive_data(self, size=1024):
        return self.serial.read(size)