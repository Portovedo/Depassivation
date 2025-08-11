import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, ttk
from tkinter.ttk import Style
import serial
from serial.tools import list_ports
import threading
import time
import csv
import json
import os
from datetime import datetime

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

PROFILES_FILE = "profiles.json"

class DepassivationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Estação de Despassivação de Baterias")
        self.root.geometry("800x750")

        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TButton', font=('Helvetica', 10))
        style.configure('success.TButton', background='#4CAF50', foreground='white', font=('Helvetica', 12, 'bold'))
        style.map('success.TButton', background=[('active', '#45a049')])
        style.configure('danger.TButton', background='#f44336', foreground='white', font=('Helvetica', 12, 'bold'))
        style.map('danger.TButton', background=[('active', '#e53935')])
        style.configure('pass.TLabel', background='green', foreground='white', font=('Helvetica', 16, 'bold'))
        style.configure('fail.TLabel', background='red', foreground='white', font=('Helvetica', 16, 'bold'))

        self.serial_connection = None
        self.is_running = False
        self.log_file_writer = None
        self.log_file = None

        self.data_points = []
        self.min_voltage = 0.0
        self.profiles = {}

        self.duration_var = tk.StringVar(value="10")
        self.pass_fail_voltage_var = tk.StringVar(value="3.2")
        self.profile_name_var = tk.StringVar()
        self.selected_profile_var = tk.StringVar()
        self.selected_port_var = tk.StringVar()

        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.main_frame.grid_rowconfigure(1, weight=4)
        self.main_frame.grid_rowconfigure(4, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        conn_frame = ttk.LabelFrame(self.main_frame, text="Conexão Serial", padding="10")
        conn_frame.grid(row=0, column=0, sticky="ew", pady=5)
        conn_frame.grid_columnconfigure(0, weight=1)

        self.port_combobox = ttk.Combobox(conn_frame, textvariable=self.selected_port_var, state='readonly')
        self.port_combobox.grid(row=0, column=0, sticky="ew", padx=(0,5))

        self.refresh_ports_button = ttk.Button(conn_frame, text="Atualizar Portas", command=self._refresh_port_list)
        self.refresh_ports_button.grid(row=0, column=1, padx=5)

        self.connect_button = ttk.Button(conn_frame, text="Conectar", command=self.toggle_connection)
        self.connect_button.grid(row=0, column=2, padx=5)

        top_frame = ttk.Frame(self.main_frame)
        top_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        top_frame.grid_columnconfigure(0, weight=3)
        top_frame.grid_columnconfigure(1, weight=1)
        top_frame.grid_rowconfigure(0, weight=1)

        graph_frame = ttk.LabelFrame(top_frame, text="Gráfico: Tensão (V) vs. Tempo (s)", padding="10")
        graph_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        stats_frame = ttk.LabelFrame(top_frame, text="Métricas", padding="10")
        stats_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self.voltage_label = ttk.Label(stats_frame, text="Tensão Atual: -- V", font=("Helvetica", 12))
        self.voltage_label.pack(anchor="w", pady=5)

        self.current_label = ttk.Label(stats_frame, text="Corrente Atual: -- mA", font=("Helvetica", 12))
        self.current_label.pack(anchor="w", pady=5)

        self.min_voltage_label = ttk.Label(stats_frame, text="Tensão Mínima: -- V", font=("Helvetica", 12, "bold"))
        self.min_voltage_label.pack(anchor="w", pady=10)

        ttk.Separator(stats_frame, orient='horizontal').pack(fill='x', pady=10, padx=5)

        self.pass_fail_label = ttk.Label(stats_frame, text="---", font=("Helvetica", 16, "bold"), anchor="center")
        self.pass_fail_label.pack(fill='x', expand=True, pady=5)


        control_frame = ttk.LabelFrame(self.main_frame, text="Controlo e Exportação", padding="10")
        control_frame.grid(row=2, column=0, sticky="ew", pady=5)
        control_frame.column_configure(0, weight=1)

        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=0, column=0, sticky="ew")
        button_frame.column_configure(0, weight=1)
        button_frame.column_configure(1, weight=1)

        self.start_button = ttk.Button(button_frame, text="Iniciar Processo", command=self.start_process, style='success.TButton', state=tk.DISABLED)
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0,5))

        self.abort_button = ttk.Button(button_frame, text="Abortar Processo", command=self.abort_process, state=tk.DISABLED, style='danger.TButton')
        self.abort_button.grid(row=0, column=1, sticky="ew", padx=(5,0))

        self.progressbar = ttk.Progressbar(control_frame, orient='horizontal', mode='determinate')
        self.progressbar.grid(row=1, column=0, sticky="ew", pady=(10,0))

        settings_area_frame = ttk.Frame(self.main_frame)
        settings_area_frame.grid(row=3, column=0, sticky="ew", pady=5)
        settings_area_frame.grid_columnconfigure(0, weight=1)
        settings_area_frame.grid_columnconfigure(1, weight=1)

        config_frame = ttk.LabelFrame(settings_area_frame, text="Configuração do Teste", padding="10")
        config_frame.grid(row=0, column=0, sticky="nsew", padx=(0,5))

        ttk.Label(config_frame, text="Duração (s):").pack(anchor="w")
        self.duration_entry = ttk.Entry(config_frame, textvariable=self.duration_var)
        self.duration_entry.pack(fill="x", expand=True, pady=(0,5))

        ttk.Label(config_frame, text="Tensão Passa/Falha (V):").pack(anchor="w")
        self.pass_fail_entry = ttk.Entry(config_frame, textvariable=self.pass_fail_voltage_var)
        self.pass_fail_entry.pack(fill="x", expand=True)

        profiles_frame = ttk.LabelFrame(settings_area_frame, text="Perfis de Bateria", padding="10")
        profiles_frame.grid(row=0, column=1, sticky="nsew", padx=(5,0))
        profiles_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(profiles_frame, text="Carregar Perfil:").grid(row=0, column=0, sticky="w")
        self.profile_menu = ttk.OptionMenu(profiles_frame, self.selected_profile_var, "Nenhum")
        self.profile_menu.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0,5))

        ttk.Button(profiles_frame, text="Carregar", command=self.load_profile).grid(row=1, column=2, padx=(5,0))
        ttk.Button(profiles_frame, text="Apagar", command=self.delete_profile).grid(row=1, column=3, padx=(5,0))

        ttk.Label(profiles_frame, text="Guardar Perfil Como:").grid(row=2, column=0, sticky="w", pady=(5,0))
        ttk.Entry(profiles_frame, textvariable=self.profile_name_var).grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Button(profiles_frame, text="Guardar", command=self.save_profile).grid(row=3, column=2, columnspan=2, padx=(5,0))

        log_frame = ttk.LabelFrame(self.main_frame, text="Registo de Dados", padding="10")
        log_frame.grid(row=4, column=0, sticky="nsew")

        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 10), height=8)
        self.log_area.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.clear_graph_and_stats()
        self._load_profiles_from_file()
        self._update_profile_dropdown()
        self._refresh_port_list()

    # --- Connection Methods ---
    def _refresh_port_list(self):
        ports = list_ports.comports()
        port_names = [port.device for port in ports]
        self.port_combobox['values'] = port_names

        esp32_port = None
        for port in ports:
            if "USB" in port.description or "CP210x" in port.description or "CH340" in port.description:
                esp32_port = port.device
                break

        if esp32_port:
            self.selected_port_var.set(esp32_port)
        elif port_names:
            self.selected_port_var.set(port_names[0])
        else:
            self.selected_port_var.set("")
        self.status_var.set("Pronto para conectar. Selecione uma porta e clique em Conectar.")

    def toggle_connection(self):
        if self.serial_connection and self.serial_connection.is_open:
            self._disconnect_from_esp32()
        else:
            self._connect_to_esp32()

    def _connect_to_esp32(self):
        port = self.selected_port_var.get()
        if not port:
            messagebox.showerror("Erro de Conexão", "Nenhuma porta serial selecionada.")
            return

        try:
            self.serial_connection = serial.Serial(port, 115200, timeout=1)
            self.status_var.set(f"Conectado a {port}. Pronto.")
            self.log_message(f"INFO: Conexão com ESP32 em {port} estabelecida.")

            self.read_thread = threading.Thread(target=self.read_from_serial, daemon=True)
            self.read_thread.start()

            self.connect_button.config(text="Desconectar")
            self.start_button.config(state=tk.NORMAL)
            self.port_combobox.config(state=tk.DISABLED)
            self.refresh_ports_button.config(state=tk.DISABLED)

        except serial.SerialException as e:
            messagebox.showerror("Erro de Conexão", f"Não foi possível abrir a porta {port}.\n{e}")
            self.log_message(f"ERROR: {e}")

    def _disconnect_from_esp32(self):
        if self.serial_connection:
            self.serial_connection.close()
            self.serial_connection = None
            self.status_var.set("Desconectado. Selecione uma porta para conectar.")
            self.log_message("INFO: Conexão terminada.")

            self.connect_button.config(text="Conectar")
            self.start_button.config(state=tk.DISABLED)
            self.port_combobox.config(state='readonly')
            self.refresh_ports_button.config(state=tk.NORMAL)

    def _update_progressbar(self, duration):
        self.progressbar['maximum'] = duration * 10
        self.progressbar['value'] = 0

        start_time = time.time()
        while self.is_running:
            elapsed = time.time() - start_time
            if elapsed > duration:
                break

            self.progressbar['value'] = elapsed * 10
            time.sleep(0.1)

        self.progressbar['value'] = 0


    # --- Profile Methods ---
    def _load_profiles_from_file(self):
        if os.path.exists(PROFILES_FILE):
            try:
                with open(PROFILES_FILE, 'r') as f:
                    self.profiles = json.load(f)
                    self.log_message(f"INFO: Loaded {len(self.profiles)} profiles from {PROFILES_FILE}")
            except (json.JSONDecodeError, IOError) as e:
                self.log_message(f"ERROR: Could not load profiles file: {e}")
                self.profiles = {}
        else:
            self.profiles = {}
            self.log_message(f"INFO: No profiles file found. Starting with empty profiles.")

    def _save_profiles_to_file(self):
        try:
            with open(PROFILES_FILE, 'w') as f:
                json.dump(self.profiles, f, indent=4)
            self.log_message("INFO: Profiles saved successfully.")
        except IOError as e:
            self.log_message(f"ERROR: Could not save profiles file: {e}")

    def _update_profile_dropdown(self):
        menu = self.profile_menu["menu"]
        menu.delete(0, "end")

        profile_names = list(self.profiles.keys())
        if not profile_names:
            menu.add_command(label="Nenhum", state="disabled")
            self.selected_profile_var.set("Nenhum")
        else:
            for name in profile_names:
                menu.add_command(label=name, command=lambda value=name: self.selected_profile_var.set(value))
            if profile_names:
                self.selected_profile_var.set(profile_names[0])

    def save_profile(self):
        profile_name = self.profile_name_var.get().strip()
        if not profile_name:
            messagebox.showerror("Erro", "O nome do perfil não pode estar em branco.")
            return

        try:
            duration = int(self.duration_var.get())
            voltage = float(self.pass_fail_voltage_var.get())
        except ValueError:
            messagebox.showerror("Erro", "Os valores de duração e tensão devem ser números válidos.")
            return

        self.profiles[profile_name] = {"duration": duration, "voltage": voltage}
        self._save_profiles_to_file()
        self._update_profile_dropdown()
        self.profile_name_var.set("")
        messagebox.showinfo("Sucesso", f"Perfil '{profile_name}' guardado.")

    def load_profile(self):
        profile_name = self.selected_profile_var.get()
        if profile_name in self.profiles:
            profile = self.profiles[profile_name]
            self.duration_var.set(str(profile["duration"]))
            self.pass_fail_voltage_var.set(str(profile["voltage"]))
            self.status_var.set(f"Perfil '{profile_name}' carregado.")
            self.log_message(f"INFO: Loaded profile '{profile_name}'.")
        else:
            messagebox.showwarning("Aviso", "Por favor, selecione um perfil válido para carregar.")

    def delete_profile(self):
        profile_name = self.selected_profile_var.get()
        if profile_name in self.profiles and profile_name != "Nenhum":
            if messagebox.askyesno("Confirmar", f"Tem a certeza que quer apagar o perfil '{profile_name}'?"):
                del self.profiles[profile_name]
                self._save_profiles_to_file()
                self._update_profile_dropdown()
                self.status_var.set(f"Perfil '{profile_name}' apagado.")
                self.log_message(f"INFO: Deleted profile '{profile_name}'.")
        else:
            messagebox.showwarning("Aviso", "Por favor, selecione um perfil válido para apagar.")


    # --- Core Methods ---
    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)

    def start_process(self):
        if not (self.serial_connection and self.serial_connection.is_open):
            self.log_message("ERROR: Not connected to ESP32. Cannot start process.")
            self.status_var.set("Erro: Não conectado ao dispositivo.")
            return

        try:
            duration = int(self.duration_var.get())
            if duration <= 0:
                raise ValueError("Duration must be positive.")
        except ValueError:
            self.status_var.set("Erro: Duração do teste inválida. Insira um número inteiro positivo.")
            return

        try:
            pass_fail_voltage = float(self.pass_fail_voltage_var.get())
            if pass_fail_voltage <= 0:
                raise ValueError("Voltage must be positive.")
        except ValueError:
            self.status_var.set("Erro: Tensão de Passa/Falha inválida. Insira um número positivo.")
            return

        self.clear_graph_and_stats()

        command = f"START,{duration},{pass_fail_voltage}\n"
        self.serial_connection.write(command.encode('utf-8'))
        self.log_message(f"INFO: Sent command to ESP32: {command.strip()}")

        self.start_button.config(state=tk.DISABLED)
        self.abort_button.config(state=tk.NORMAL)
        self.is_running = True

        progress_thread = threading.Thread(target=self._update_progressbar, args=(duration,), daemon=True)
        progress_thread.start()

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

        self.export_graph_button.config(state=tk.DISABLED)
        self.export_data_button.config(state=tk.DISABLED)
        self.pass_fail_label.config(text="---", style="TLabel")

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

            min_v, max_v = min(voltages), max(voltages)
            v_range = max_v - min_v
            if v_range < 0.4:
                center = v_range / 2 + min_v
                self.ax.set_ylim(center - 0.2, center + 0.2)
            else:
                self.ax.set_ylim(min_v - 0.1, max_v + 0.1)

        self.ax.set_xlabel("Tempo (s)")
        self.ax.set_ylabel("Tensão (V)")
        self.ax.grid(True)
        self.fig.tight_layout()
        self.canvas.draw()

    def export_graph(self):
        if not self.data_points:
            self.status_var.set("Nada para exportar. Execute um teste primeiro.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            title="Guardar Gráfico Como..."
        )
        if not filepath:
            self.status_var.set("Exportação do gráfico cancelada.")
            return

        try:
            self.fig.savefig(filepath, dpi=300)
            self.status_var.set(f"Gráfico guardado em {filepath}")
            self.log_message(f"INFO: Graph saved to {filepath}")
        except Exception as e:
            self.status_var.set(f"Erro ao guardar o gráfico: {e}")
            self.log_message(f"ERROR: Failed to save graph: {e}")

    def export_data(self):
        if not self.data_points:
            self.status_var.set("Nada para exportar. Execute um teste primeiro.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Guardar Dados Como..."
        )
        if not filepath:
            self.status_var.set("Exportação dos dados cancelada.")
            return

        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp_s', 'Voltage_V', 'Current_mA'])
                writer.writerows(self.data_points)
            self.status_var.set(f"Dados guardados em {filepath}")
            self.log_message(f"INFO: Data saved to {filepath}")
        except Exception as e:
            self.status_var.set(f"Erro ao guardar os dados: {e}")
            self.log_message(f"ERROR: Failed to save data: {e}")

    def abort_process(self):
        if self.serial_connection and self.serial_connection.is_open and self.is_running:
            self.serial_connection.write(b'ABORT\n')
            self.is_running = False # Stop the progress bar thread
            self.log_message("INFO: Processo abortado pelo utilizador.")
            self.abort_button.config(state=tk.DISABLED)
            self.start_button.config(state=tk.NORMAL)

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

            if self.data_points:
                self.export_graph_button.config(state=tk.NORMAL)
                self.export_data_button.config(state=tk.NORMAL)

                # Check pass/fail status
                try:
                    pass_voltage = float(self.pass_fail_voltage_var.get())
                    if self.min_voltage >= pass_voltage:
                        self.pass_fail_label.config(text="PASS", style="pass.TLabel")
                    else:
                        self.pass_fail_label.config(text="FAIL", style="fail.TLabel")
                except ValueError:
                    self.pass_fail_label.config(text="N/A", style="")


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
