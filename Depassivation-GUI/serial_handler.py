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
        self.is_running = False

    def get_ports(self):
        return list_ports.comports()

    def connect(self, port):
        try:
            self.serial_connection = serial.Serial(port, 115200, timeout=1)
            self.app.log_message(f"INFO: Conexão com ESP32 em {port} estabelecida.")

            self.is_running = True
            self.read_thread = threading.Thread(target=self.read_from_serial, daemon=True)
            self.read_thread.start()
            return True
        except serial.SerialException as e:
            messagebox.showerror("Erro de Conexão", f"Não foi possível abrir a porta {port}.\n{e}")
            self.app.log_message(f"ERROR: {e}")
            return False

    def disconnect(self):
        self.is_running = False # Signal the thread to stop
        if self.serial_connection:
            # Wait a moment for the thread to exit its loop
            if self.read_thread and self.read_thread.is_alive():
                self.read_thread.join(timeout=1.0)
            self.serial_connection.close()
            self.serial_connection = None
            self.app.log_message("INFO: Conexão terminada.")

    def read_from_serial(self):
        """
        Reads data from the serial port in a separate thread.
        Handles potential decoding errors by ignoring invalid bytes.
        """
        while self.is_running and self.serial_connection and self.serial_connection.is_open:
            try:
                # Wait until there is data waiting in the serial buffer
                if self.serial_connection.in_waiting > 0:
                    # Use errors='ignore' to prevent crashes on invalid byte sequences
                    line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        # Schedule the data handling in the main GUI thread
                        self.app.root.after(0, self.app.handle_serial_data, line)
            except serial.SerialException:
                # This can happen if the device is unplugged
                self.app.log_message("ERROR: Ligação perdida. Por favor, reinicie a aplicação.")
                self.app.root.after(0, self.app.handle_disconnect)
                break
            except Exception as e:
                # Catch any other unexpected errors
                self.app.log_message(f"ERROR: Erro inesperado na leitura serial: {e}")

            time.sleep(0.01) # Small delay to prevent high CPU usage

    def send(self, data):
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.write(data.encode('utf-8'))
                return True
            except serial.SerialException as e:
                self.app.log_message(f"ERROR: Falha ao enviar dados: {e}")
                return False
        return False

    def is_connected(self):
        return self.serial_connection is not None and self.serial_connection.is_open
