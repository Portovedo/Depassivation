import tkinter as tk
from tkinter import scrolledtext
import serial
import threading
import time
import csv
from datetime import datetime

# --- Configuration ---
# IMPORTANT: Change this to the correct COM port for your ESP32
ESP32_PORT = 'COM3' 
BAUD_RATE = 115200

class DepassivationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Estação de Despassivação de Baterias")
        self.root.geometry("600x450")

        self.serial_connection = None
        self.is_running = False
        self.log_file_writer = None
        self.log_file = None

        # --- UI Elements ---
        self.main_frame = tk.Frame(root, padx=10, pady=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Control Frame
        control_frame = tk.LabelFrame(self.main_frame, text="Controlo", padx=10, pady=10)
        control_frame.pack(fill=tk.X, pady=5)

        self.start_button = tk.Button(control_frame, text="Iniciar Processo", command=self.start_process, font=("Helvetica", 12), bg="#4CAF50", fg="white")
        self.start_button.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        self.abort_button = tk.Button(control_frame, text="Abortar Processo", command=self.abort_process, font=("Helvetica", 12), bg="#f44336", fg="white", state=tk.DISABLED)
        self.abort_button.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # Log Frame
        log_frame = tk.LabelFrame(self.main_frame, text="Registo de Dados (Tempo (ms), Tensão (V), Corrente (mA))", padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 10))
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        # Status Bar
        self.status_var = tk.StringVar()
        self.status_var.set(f"A conectar a {ESP32_PORT}...")
        self.status_bar = tk.Label(root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.connect_to_esp32()

    def connect_to_esp32(self):
        try:
            self.serial_connection = serial.Serial(ESP32_PORT, BAUD_RATE, timeout=1)
            self.status_var.set(f"Conectado a {ESP32_PORT}. Pronto.")
            self.log_message(f"INFO: Conexão com ESP32 em {ESP32_PORT} estabelecida.")
            # Start a thread to read from serial
            self.read_thread = threading.Thread(target=self.read_from_serial, daemon=True)
            self.read_thread.start()
        except serial.SerialException as e:
            self.status_var.set(f"Erro: Não foi possível abrir a porta {ESP32_PORT}.")
            self.log_message(f"ERROR: {e}")
            self.start_button.config(state=tk.DISABLED)

    def log_message(self, message):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)

    def start_process(self):
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.write(b'START\n')
            self.start_button.config(state=tk.DISABLED)
            self.abort_button.config(state=tk.NORMAL)
            self.is_running = True
            
            # Create a new log file for this session
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"depassivation_log_{timestamp}.csv"
            try:
                self.log_file = open(filename, 'w', newline='')
                self.log_file_writer = csv.writer(self.log_file)
                self.log_file_writer.writerow(['Timestamp_ms', 'Voltage_V', 'Current_mA'])
                self.log_message(f"INFO: A guardar dados em {filename}")
            except IOError as e:
                self.log_message(f"ERROR: Não foi possível criar o ficheiro de log: {e}")


    def abort_process(self):
        if self.serial_connection and self.serial_connection.is_open and self.is_running:
            self.serial_connection.write(b'ABORT\n')
            # The rest of the state change will be handled by the response from the ESP32

    def read_from_serial(self):
        while True:
            try:
                if self.serial_connection and self.serial_connection.is_open:
                    line = self.serial_connection.readline().decode('utf-8').strip()
                    if line:
                        self.root.after(0, self.handle_serial_data, line)
                else:
                    time.sleep(0.1)
            except (serial.SerialException, TypeError):
                self.status_var.set("Erro de comunicação. A reconectar...")
                self.log_message("ERROR: Ligação perdida. Tente reiniciar a aplicação.")
                self.serial_connection.close()
                self.start_button.config(state=tk.DISABLED)
                self.abort_button.config(state=tk.DISABLED)
                break # Exit thread on error

    def handle_serial_data(self, data):
        self.log_message(f"ESP32: {data}")
        
        if data.startswith("PROCESS_END"):
            self.is_running = False
            self.start_button.config(state=tk.NORMAL)
            self.abort_button.config(state=tk.DISABLED)
            if self.log_file:
                self.log_file.close()
                self.log_file = None
                self.log_file_writer = None
                self.log_message("INFO: Ficheiro de log fechado.")

        elif data.startswith("DATA,"):
            parts = data.split(',')
            if len(parts) == 4 and self.log_file_writer:
                try:
                    # parts[0] is "DATA"
                    log_data = [parts[1], parts[2], parts[3]]
                    self.log_file_writer.writerow(log_data)
                except Exception as e:
                    self.log_message(f"ERROR: Falha ao escrever no CSV: {e}")


    def on_closing(self):
        if self.is_running:
            self.abort_process()
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = DepassivationApp(root)
    root.mainloop()
