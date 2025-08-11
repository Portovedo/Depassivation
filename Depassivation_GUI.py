import tkinter as tk
from tkinter import scrolledtext
import serial
from serial.tools import list_ports
import threading
import time
import csv
from datetime import datetime

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class DepassivationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Estação de Despassivação de Baterias")
        self.root.geometry("800x600")

        self.serial_connection = None
        self.is_running = False
        self.log_file_writer = None
        self.log_file = None

        self.data_points = []
        self.min_voltage = 0.0

        self.main_frame = tk.Frame(root, padx=10, pady=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.main_frame.grid_rowconfigure(0, weight=3)
        self.main_frame.grid_rowconfigure(2, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        top_frame = tk.Frame(self.main_frame)
        top_frame.grid(row=0, column=0, sticky="nsew", pady=5)
        top_frame.grid_columnconfigure(0, weight=3)
        top_frame.grid_columnconfigure(1, weight=1)
        top_frame.grid_rowconfigure(0, weight=1)

        graph_frame = tk.LabelFrame(top_frame, text="Gráfico: Tensão (V) vs. Tempo (s)", padx=10, pady=10)
        graph_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        stats_frame = tk.LabelFrame(top_frame, text="Métricas", padx=10, pady=10)
        stats_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self.voltage_label = tk.Label(stats_frame, text="Tensão Atual: -- V", font=("Helvetica", 12))
        self.voltage_label.pack(anchor="w", pady=5)

        self.current_label = tk.Label(stats_frame, text="Corrente Atual: -- mA", font=("Helvetica", 12))
        self.current_label.pack(anchor="w", pady=5)

        self.min_voltage_label = tk.Label(stats_frame, text="Tensão Mínima: -- V", font=("Helvetica", 12, "bold"))
        self.min_voltage_label.pack(anchor="w", pady=10)

        control_frame = tk.LabelFrame(self.main_frame, text="Controlo", padx=10, pady=10)
        control_frame.grid(row=1, column=0, sticky="ew", pady=5)

        self.start_button = tk.Button(control_frame, text="Iniciar Processo", command=self.start_process, font=("Helvetica", 12), bg="#4CAF50", fg="white")
        self.start_button.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        self.abort_button = tk.Button(control_frame, text="Abortar Processo", command=self.abort_process, font=("Helvetica", 12), bg="#f44336", fg="white", state=tk.DISABLED)
        self.abort_button.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        log_frame = tk.LabelFrame(self.main_frame, text="Registo de Dados", padx=10, pady=10)
        log_frame.grid(row=2, column=0, sticky="nsew")

        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 10), height=8)
        self.log_area.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar()
        self.status_bar = tk.Label(root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.clear_graph_and_stats()
        self.connect_to_esp32()

    def find_esp32_port(self):
        ports = list_ports.comports()
        for port in ports:
            # A simple check for ports that might be an ESP32.
            # This could be improved with a more specific check if needed.
            if "USB" in port.description or "CP210x" in port.description or "CH340" in port.description:
                return port.device
        return None

    def connect_to_esp32(self):
        esp32_port = self.find_esp32_port()
        if esp32_port is None:
            self.status_var.set("Erro: Nenhuma porta ESP32 detetada. Verifique a ligação.")
            self.log_message("ERROR: Could not find any potential ESP32 serial ports.")
            self.start_button.config(state=tk.DISABLED)
            return

        self.status_var.set(f"A conectar a {esp32_port}...")
        try:
            self.serial_connection = serial.Serial(esp32_port, 115200, timeout=1)
            self.status_var.set(f"Conectado a {esp32_port}. Pronto.")
            self.log_message(f"INFO: Conexão com ESP32 em {esp32_port} estabelecida.")
            self.read_thread = threading.Thread(target=self.read_from_serial, daemon=True)
            self.read_thread.start()
        except serial.SerialException as e:
            self.status_var.set(f"Erro: Não foi possível abrir a porta {esp32_port}.")
            self.log_message(f"ERROR: {e}")
            self.start_button.config(state=tk.DISABLED)

    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)

    def start_process(self):
        if self.serial_connection and self.serial_connection.is_open:
            self.clear_graph_and_stats()
            self.serial_connection.write(b'START\n')
            self.start_button.config(state=tk.DISABLED)
            self.abort_button.config(state=tk.NORMAL)
            self.is_running = True

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"depassivation_log_{timestamp}.csv"
            try:
                self.log_file = open(filename, 'w', newline='')
                self.log_file_writer = csv.writer(self.log_file)
                self.log_file_writer.writerow(['Timestamp_ms', 'Voltage_V', 'Current_mA'])
                self.log_message(f"INFO: A guardar dados em {filename}")
            except IOError as e:
                self.log_message(f"ERROR: Não foi possível criar o ficheiro de log: {e}")

    def clear_graph_and_stats(self):
        self.data_points.clear()
        self.min_voltage = 0.0

        self.voltage_label.config(text="Tensão Atual: -- V")
        self.current_label.config(text="Corrente Atual: -- mA")
        self.min_voltage_label.config(text="Tensão Mínima: -- V")

        self.ax.cla()
        self.ax.set_xlabel("Tempo (s)")
        self.ax.set_ylabel("Tensão (V)")
        self.ax.grid(True)
        self.fig.tight_layout()
        self.canvas.draw()

    def update_graph(self):
        self.ax.cla()
        if len(self.data_points) > 0:
            times, voltages, _ = zip(*self.data_points)
            self.ax.plot(times, voltages, marker='o', linestyle='-')

            # Dynamic Y-axis scaling for better visualization
            min_v, max_v = min(voltages), max(voltages)
            v_range = max_v - min_v
            if v_range < 0.4: # If range is small, center it with a fixed range
                center = v_range / 2 + min_v
                self.ax.set_ylim(center - 0.2, center + 0.2)
            else: # Otherwise, use a small buffer
                self.ax.set_ylim(min_v - 0.1, max_v + 0.1)

        self.ax.set_xlabel("Tempo (s)")
        self.ax.set_ylabel("Tensão (V)")
        self.ax.grid(True)
        self.fig.tight_layout()
        self.canvas.draw()

    def abort_process(self):
        if self.serial_connection and self.serial_connection.is_open and self.is_running:
            self.serial_connection.write(b'ABORT\n')
            self.log_message("INFO: Processo abortado pelo utilizador.")

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
                self.log_message("ERROR: Ligação perdida. Por favor, reinicie a aplicação.")
                self.root.after(0, self.handle_disconnect)
                break

    def handle_disconnect(self):
        self.status_var.set("Desconectado. Tente reiniciar a aplicação.")
        if self.serial_connection:
            self.serial_connection.close()
        self.start_button.config(state=tk.DISABLED)
        self.abort_button.config(state=tk.DISABLED)
        self.is_running = False

    def handle_serial_data(self, data):
        if not data.startswith("DATA,"):
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
            try:
                _, time_ms, voltage_v, current_ma = data.split(',')
                time_s = float(time_ms) / 1000.0
                voltage = float(voltage_v)
                current = float(current_ma)

                self.data_points.append((time_s, voltage, current))

                self.voltage_label.config(text=f"Tensão Atual: {voltage:.3f} V")
                self.current_label.config(text=f"Corrente Atual: {current:.1f} mA")

                if self.min_voltage == 0.0 or voltage < self.min_voltage:
                    self.min_voltage = voltage
                    self.min_voltage_label.config(text=f"Tensão Mínima: {self.min_voltage:.3f} V")

                self.update_graph()

                if self.log_file_writer:
                    self.log_file_writer.writerow([time_ms, voltage_v, current_ma])

            except (ValueError, IndexError) as e:
                self.log_message(f"ERROR: Falha ao processar dados: {data} ({e})")
            except Exception as e:
                self.log_message(f"ERROR: Erro inesperado em handle_serial_data: {e}")

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
