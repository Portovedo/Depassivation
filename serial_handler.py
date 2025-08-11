import serial
from serial.tools import list_ports
import threading
import time
from tkinter import messagebox

class SerialHandler:
    def __init__(self, app):
        self.app = app
        self.serial_connection = None
        self.read_thread = None

    def get_ports(self):
        return list_ports.comports()

    def connect(self, port):
        try:
            self.serial_connection = serial.Serial(port, 115200, timeout=1)
            self.app.log_message(f"INFO: Conexão com ESP32 em {port} estabelecida.")

            self.read_thread = threading.Thread(target=self.read_from_serial, daemon=True)
            self.read_thread.start()
            return True
        except serial.SerialException as e:
            messagebox.showerror("Erro de Conexão", f"Não foi possível abrir a porta {port}.\n{e}")
            self.app.log_message(f"ERROR: {e}")
            return False

    def disconnect(self):
        if self.serial_connection:
            self.serial_connection.close()
            self.serial_connection = None
            self.app.log_message("INFO: Conexão terminada.")

    def read_from_serial(self):
        while self.serial_connection and self.serial_connection.is_open:
            try:
                line = self.serial_connection.readline().decode('utf-8').strip()
                if line:
                    self.app.root.after(0, self.app.handle_serial_data, line)
            except (serial.SerialException, TypeError):
                self.app.log_message("ERROR: Ligação perdida. Por favor, reinicie a aplicação.")
                self.app.root.after(0, self.app.handle_disconnect)
                break

    def send(self, data):
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.write(data.encode('utf-8'))
            return True
        return False
