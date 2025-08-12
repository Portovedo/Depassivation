import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, ttk
from tkinter.ttk import Style
import threading
import time
import csv
from datetime import datetime

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from data_handler import DataHandler
# We will import the correct handler based on the mode
# from serial_handler import SerialHandler
# from simulation_handler import SimulationHandler

class DepassivationApp:
    def __init__(self, root, simulate=False):
        self.root = root
        self.simulation_mode = simulate
        self.is_running = False
        self.current_test_id = None
        self.last_completed_test_id = None

        self.data_points = []
        self.min_voltage = 0.0

        self.data_handler = DataHandler(self)

        # --- MODE SWITCH ---
        # Based on the --simulate flag, we instantiate either the real
        # serial handler or the simulation handler.
        if self.simulation_mode:
            from simulation_handler import SimulationHandler
            self.connection_handler = SimulationHandler(self)
            self.root.title("Estação de Despassivação de Baterias (MODO SIMULAÇÃO)")
        else:
            from serial_handler import SerialHandler
            self.connection_handler = SerialHandler(self)
            self.root.title("Estação de Despassivação de Baterias")


        config = self.data_handler.load_config()
        self.root.geometry(config.get("geometry", "800x750"))

        self.duration_var = tk.StringVar(value=config.get("duration", "10"))
        self.pass_fail_voltage_var = tk.StringVar(value=config.get("pass_fail_voltage", "3.2"))
        self.profile_name_var = tk.StringVar()
        self.selected_profile_var = tk.StringVar()
        self.selected_port_var = tk.StringVar(value=config.get("last_port", ""))

        self._setup_styles()
        self._create_widgets()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.clear_graph_and_stats()

        self.profiles = self.data_handler.load_profiles()
        self._update_profile_dropdown()
        
        if not self.simulation_mode:
            self._refresh_port_list()
        else:
            # In simulation mode, the start button is always ready.
            self.start_button.config(state=tk.NORMAL)
            self.status_var.set("Modo Simulação: Pronto para iniciar o processo.")

        self.populate_history_list()

    def _setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('TButton', font=('Helvetica', 10))
        style.configure('success.TButton', background='#4CAF50', foreground='white', font=('Helvetica', 12, 'bold'))
        style.map('success.TButton', background=[('active', '#45a049')])
        style.configure('danger.TButton', background='#f44336', foreground='white', font=('Helvetica', 12, 'bold'))
        style.map('danger.TButton', background=[('active', '#e53935')])
        style.configure('pass.TLabel', background='green', foreground='white', font=('Helvetica', 16, 'bold'))
        style.configure('fail.TLabel', background='red', foreground='white', font=('Helvetica', 16, 'bold'))

    def _create_widgets(self):
        # Main frame setup
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(0, weight=1)

        # Create tabs
        self.live_test_tab = ttk.Frame(self.notebook, padding="10")
        self.history_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.live_test_tab, text="Live Test")
        self.notebook.add(self.history_tab, text="Histórico")

        # Configure grid for live_test_tab
        self.live_test_tab.grid_rowconfigure(1, weight=4)
        self.live_test_tab.grid_rowconfigure(4, weight=1)
        self.live_test_tab.grid_columnconfigure(0, weight=1)

        # Populate tabs
        self._create_live_test_tab(self.live_test_tab)
        self._create_history_tab(self.history_tab)

        # Status bar at the bottom
        self._create_status_bar()

    def _create_live_test_tab(self, parent):
        # Only create the connection frame if not in simulation mode
        if not self.simulation_mode:
            self._create_connection_frame(parent)
        
        self._create_graph_and_stats_frame(parent)
        self._create_control_frame(parent)
        self._create_settings_frame(parent)
        self._create_log_frame(parent)

    def _create_history_tab(self, parent):
        parent.grid_columnconfigure(1, weight=3) # Details column
        parent.grid_columnconfigure(0, weight=1) # List column
        parent.grid_rowconfigure(0, weight=1)

        # Frame for the list of tests
        list_frame = ttk.LabelFrame(parent, text="Testes Anteriores", padding="10")
        list_frame.grid(row=0, column=0, sticky="nswe", padx=(0, 5))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.history_tree = ttk.Treeview(list_frame, columns=("ID", "Timestamp", "Result"), show="headings")
        self.history_tree.heading("ID", text="ID")
        self.history_tree.heading("Timestamp", text="Data e Hora")
        self.history_tree.heading("Result", text="Resultado")
        self.history_tree.column("ID", width=40, anchor='center')
        self.history_tree.bind("<<TreeviewSelect>>", self.show_history_details)
        self.history_tree.grid(row=0, column=0, sticky="nswe")

        # Scrollbar for the Treeview
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Button frame
        button_frame = ttk.Frame(list_frame)
        button_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10,0))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        refresh_button = ttk.Button(button_frame, text="Atualizar Lista", command=self.populate_history_list)
        refresh_button.grid(row=0, column=0, sticky="ew", padx=(0,2))

        delete_button = ttk.Button(button_frame, text="Apagar Teste", command=self.delete_selected_test, style="danger.TButton")
        delete_button.grid(row=0, column=1, sticky="ew", padx=(2,0))

        # Frame for the details of the selected test
        details_frame = ttk.LabelFrame(parent, text="Detalhes do Teste", padding="10")
        details_frame.grid(row=0, column=1, sticky="nswe", padx=(5, 0))
        details_frame.grid_columnconfigure(0, weight=3) # Graph
        details_frame.grid_columnconfigure(1, weight=1) # Stats
        details_frame.grid_rowconfigure(0, weight=1)

        # History Graph
        history_graph_frame = ttk.LabelFrame(details_frame, text="Gráfico do Teste", padding="10")
        history_graph_frame.grid(row=0, column=0, sticky="nswe", padx=(0, 5))
        self.history_fig = Figure(figsize=(5, 4), dpi=100)
        self.history_ax = self.history_fig.add_subplot(111)
        self.history_canvas = FigureCanvasTkAgg(self.history_fig, master=history_graph_frame)
        self.history_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # History Stats
        history_stats_frame = ttk.LabelFrame(details_frame, text="Métricas do Teste", padding="10")
        history_stats_frame.grid(row=0, column=1, sticky="nswe", padx=(5, 0))

        self.history_id_label = ttk.Label(history_stats_frame, text="ID do Teste: --")
        self.history_id_label.pack(anchor="w", pady=2)
        self.history_timestamp_label = ttk.Label(history_stats_frame, text="Data/Hora: --")
        self.history_timestamp_label.pack(anchor="w", pady=2)
        self.history_duration_label = ttk.Label(history_stats_frame, text="Duração: -- s")
        self.history_duration_label.pack(anchor="w", pady=2)
        self.history_pass_fail_voltage_label = ttk.Label(history_stats_frame, text="Tensão Alvo: -- V")
        self.history_pass_fail_voltage_label.pack(anchor="w", pady=2)
        self.history_min_voltage_label = ttk.Label(history_stats_frame, text="Tensão Mínima: -- V")
        self.history_min_voltage_label.pack(anchor="w", pady=8)
        self.history_result_label = ttk.Label(history_stats_frame, text="Resultado: --", font=("Helvetica", 14, "bold"))
        self.history_result_label.pack(anchor="w", pady=8)


    def _create_connection_frame(self, parent):
        conn_frame = ttk.LabelFrame(parent, text="Conexão Serial", padding="10")
        conn_frame.grid(row=0, column=0, sticky="ew", pady=5)
        conn_frame.grid_columnconfigure(0, weight=1)
        self.port_combobox = ttk.Combobox(conn_frame, textvariable=self.selected_port_var, state='readonly')
        self.port_combobox.grid(row=0, column=0, sticky="ew", padx=(0,5))
        self.refresh_ports_button = ttk.Button(conn_frame, text="Atualizar Portas", command=self._refresh_port_list)
        self.refresh_ports_button.grid(row=0, column=1, padx=5)
        self.connect_button = ttk.Button(conn_frame, text="Conectar", command=self.toggle_connection)
        self.connect_button.grid(row=0, column=2, padx=5)

    def _create_graph_and_stats_frame(self, parent):
        top_frame = ttk.Frame(parent)
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

    def _create_control_frame(self, parent):
        control_frame = ttk.LabelFrame(parent, text="Controlo e Exportação", padding="10")
        control_frame.grid(row=2, column=0, sticky="ew", pady=5)
        control_frame.columnconfigure(0, weight=1)
        
        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=0, column=0, sticky="ew")
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        
        self.start_button = ttk.Button(button_frame, text="Iniciar Processo", command=self.start_process, style='success.TButton', state=tk.DISABLED)
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0,5))
        
        self.abort_button = ttk.Button(button_frame, text="Abortar Processo", command=self.abort_process, state=tk.DISABLED, style='danger.TButton')
        self.abort_button.grid(row=0, column=1, sticky="ew", padx=(5,0))
        
        self.progressbar = ttk.Progressbar(control_frame, orient='horizontal', mode='determinate')
        self.progressbar.grid(row=1, column=0, sticky="ew", pady=(10,5))
        
        export_frame = ttk.Frame(control_frame)
        export_frame.grid(row=2, column=0, sticky="ew", pady=(5,0))
        export_frame.columnconfigure(0, weight=1)
        export_frame.columnconfigure(1, weight=1)

        self.export_graph_button = ttk.Button(export_frame, text="Exportar Gráfico (.png)", command=self.export_graph, state=tk.DISABLED)
        self.export_graph_button.grid(row=0, column=0, sticky="ew", padx=(0,5))
        
        self.export_data_button = ttk.Button(export_frame, text="Exportar Dados (.csv)", command=self.export_data, state=tk.DISABLED)
        self.export_data_button.grid(row=0, column=1, sticky="ew", padx=(5,0))


    def _create_settings_frame(self, parent):
        settings_area_frame = ttk.Frame(parent)
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

    def _create_log_frame(self, parent):
        log_frame = ttk.LabelFrame(parent, text="Registo de Dados", padding="10")
        log_frame.grid(row=4, column=0, sticky="nsew")
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 10), height=8)
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def _create_status_bar(self):
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _refresh_port_list(self):
        ports = self.connection_handler.get_ports()
        port_names = [port.device for port in ports]
        self.port_combobox['values'] = port_names
        last_port = self.selected_port_var.get()
        if last_port and last_port in port_names:
            self.port_combobox.set(last_port)
        else:
            esp32_port = next((p.device for p in ports if "USB" in p.description or "CP210x" in p.description or "CH340" in p.description), None)
            if esp32_port: self.selected_port_var.set(esp32_port)
            elif port_names: self.selected_port_var.set(port_names[0])
            else: self.selected_port_var.set("")
        self.status_var.set("Pronto para conectar. Selecione uma porta e clique em Conectar.")

    def toggle_connection(self):
        if self.connection_handler.serial_connection and self.connection_handler.serial_connection.is_open:
            self.connection_handler.disconnect()
            self.connect_button.config(text="Conectar")
            self.start_button.config(state=tk.DISABLED)
            self.port_combobox.config(state='readonly')
            self.refresh_ports_button.config(state=tk.NORMAL)
        else:
            if self.connection_handler.connect(self.selected_port_var.get()):
                self.connect_button.config(text="Desconectar")
                self.start_button.config(state=tk.NORMAL)
                self.port_combobox.config(state=tk.DISABLED)
                self.refresh_ports_button.config(state=tk.DISABLED)

    def _update_progressbar(self, duration):
        self.progressbar['maximum'] = duration * 10
        self.progressbar['value'] = 0
        start_time = time.time()
        while self.is_running:
            elapsed = time.time() - start_time
            if elapsed > duration: break
            self.progressbar['value'] = elapsed * 10
            time.sleep(0.1)
        self.progressbar['value'] = 0

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
            if profile_names: self.selected_profile_var.set(profile_names[0])

    def save_profile(self):
        profile_name = self.profile_name_var.get().strip()
        if not profile_name: messagebox.showerror("Erro", "O nome do perfil não pode estar em branco."); return
        try:
            duration = int(self.duration_var.get())
            voltage = float(self.pass_fail_voltage_var.get())
        except ValueError: messagebox.showerror("Erro", "Os valores de duração e tensão devem ser números válidos."); return
        self.profiles[profile_name] = {"duration": duration, "voltage": voltage}
        self.data_handler.save_profiles()
        self._update_profile_dropdown()
        self.profile_name_var.set("")
        messagebox.showinfo("Sucesso", f"Perfil '{profile_name}' guardado.")

    def load_profile(self):
        profile_name = self.selected_profile_var.get()
        if profile_name in self.profiles:
            profile = self.profiles[profile_name]
            self.duration_var.set(str(profile["duration"]))
            self.pass_fail_voltage_var.set(str(profile["voltage"]))
            self.profile_name_var.set(profile_name)
            self.status_var.set(f"Perfil '{profile_name}' carregado.")
            self.log_message(f"INFO: Loaded profile '{profile_name}'.")
        else: messagebox.showwarning("Aviso", "Por favor, selecione um perfil válido para carregar.")

    def delete_profile(self):
        profile_name = self.selected_profile_var.get()
        if profile_name in self.profiles and profile_name != "Nenhum":
            if messagebox.askyesno("Confirmar", f"Tem a certeza que quer apagar o perfil '{profile_name}'?"):
                del self.profiles[profile_name]
                self.data_handler.save_profiles()
                self._update_profile_dropdown()
                self.status_var.set(f"Perfil '{profile_name}' apagado.")
                self.log_message(f"INFO: Deleted profile '{profile_name}'.")
        else: messagebox.showwarning("Aviso", "Por favor, selecione um perfil válido para apagar.")

    def delete_selected_test(self):
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showwarning("Nenhuma Seleção", "Por favor, selecione um teste da lista para apagar.")
            return

        selected_item = selection[0]
        test_id = self.history_tree.item(selected_item, "values")[0]

        if messagebox.askyesno("Confirmar Apagar", f"Tem a certeza que quer apagar permanentemente o teste ID {test_id}?"):
            if self.data_handler.delete_test(test_id):
                self.log_message(f"INFO: Teste ID {test_id} apagado com sucesso.")
                self.populate_history_list()
                self.history_ax.cla()
                self.history_canvas.draw()
                self.history_id_label.config(text="ID do Teste: --")
                self.history_timestamp_label.config(text="Data/Hora: --")
                self.history_duration_label.config(text="Duração: -- s")
                self.history_pass_fail_voltage_label.config(text="Tensão Alvo: -- V")
                self.history_min_voltage_label.config(text="Tensão Mínima: -- V")
                self.history_result_label.config(text="Resultado: --")
            else:
                messagebox.showerror("Erro", f"Não foi possível apagar o teste ID {test_id}.")
                self.log_message(f"ERROR: Failed to delete test ID {test_id}.")

    def populate_history_list(self):
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        test_summaries = self.data_handler.get_all_tests_summary()
        for test in test_summaries:
            test_id, timestamp, result = test
            result_text = result if result else "Incompleto"
            self.history_tree.insert("", tk.END, values=(test_id, timestamp, result_text))
        self.log_message(f"INFO: Carregado {len(test_summaries)} testes no histórico.")

    def show_history_details(self, event):
        selection = self.history_tree.selection()
        if not selection: return
        selected_item = selection[0]
        test_id = self.history_tree.item(selected_item, "values")[0]
        summary = self.data_handler.get_test_summary(test_id)
        data_points = self.data_handler.get_test_data(test_id)
        if not summary:
            self.log_message(f"WARN: Não foram encontrados detalhes para o teste ID {test_id}.")
            return
        self.history_id_label.config(text=f"ID do Teste: {summary['id']}")
        self.history_timestamp_label.config(text=f"Data/Hora: {summary['timestamp']}")
        self.history_duration_label.config(text=f"Duração: {summary['duration']} s")
        self.history_pass_fail_voltage_label.config(text=f"Tensão Alvo: {summary['pass_fail_voltage']} V")
        min_v = summary['min_voltage']
        self.history_min_voltage_label.config(text=f"Tensão Mínima: {min_v:.3f} V" if min_v else "N/A")
        result = summary['result']
        self.history_result_label.config(text=f"Resultado: {result if result else 'N/A'}")
        self.history_ax.cla()
        if data_points:
            times, voltages, _ = zip(*data_points)
            self.history_ax.plot(times, voltages, marker='o', linestyle='-')
            self._update_graph_yrange(self.history_ax, voltages)
        self.history_ax.set_title(f"Dados do Teste ID: {test_id}")
        self.history_ax.set_xlabel("Tempo (s)")
        self.history_ax.set_ylabel("Tensão (V)")
        self.history_ax.grid(True)
        self.history_fig.tight_layout()
        self.history_canvas.draw()

    def _update_graph_yrange(self, axis, voltages):
        if not voltages: return
        min_v, max_v = min(voltages), max(voltages)
        v_range = max_v - min_v
        if v_range < 0.4:
            center = v_range / 2 + min_v
            axis.set_ylim(center - 0.2, center + 0.2)
        else:
            axis.set_ylim(min_v - 0.1, max_v + 0.1)

    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)

    def start_process(self):
        try:
            duration = int(self.duration_var.get())
            pass_fail_voltage = float(self.pass_fail_voltage_var.get())
            if duration <= 0 or pass_fail_voltage <= 0: raise ValueError("Values must be positive.")
        except ValueError:
            self.status_var.set("Erro: Duração e Tensão devem ser números positivos."); return

        if not self.simulation_mode:
            if not (self.connection_handler.serial_connection and self.connection_handler.serial_connection.is_open):
                self.log_message("ERROR: Not connected. Cannot start process.")
                self.status_var.set("Erro: Não conectado ao dispositivo.")
                return

        self.clear_graph_and_stats()
        self.current_test_id = self.data_handler.create_new_test(duration, pass_fail_voltage)
        if not self.current_test_id:
            self.log_message("ERROR: Could not start test, database error.")
            return

        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.abort_button.config(state=tk.NORMAL)
        threading.Thread(target=self._update_progressbar, args=(duration,), daemon=True).start()

        if self.simulation_mode:
            self.connection_handler.start(duration, pass_fail_voltage)
        else:
            command = f"START,{duration},{pass_fail_voltage}\n"
            self.connection_handler.send(command)
            self.log_message(f"INFO: Sent command to ESP32: {command.strip()}")

    def clear_graph_and_stats(self):
        self.data_points.clear()
        self.min_voltage = 0.0
        self.last_completed_test_id = None
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
        if self.data_points:
            times, voltages, _ = zip(*self.data_points)
            self.ax.plot(times, voltages, marker='o', linestyle='-')
            self._update_graph_yrange(self.ax, voltages)
        self.ax.set_xlabel("Tempo (s)")
        self.ax.set_ylabel("Tensão (V)")
        self.ax.grid(True)
        self.fig.tight_layout()
        self.canvas.draw()

    def export_graph(self):
        if not self.data_points: self.status_var.set("Nada para exportar."); return
        filepath = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png"), ("All files", "*.*")], title="Guardar Gráfico Como...")
        if not filepath: self.status_var.set("Exportação do gráfico cancelada."); return
        try:
            self.fig.savefig(filepath, dpi=300)
            self.status_var.set(f"Gráfico guardado em {filepath}")
            self.log_message(f"INFO: Graph saved to {filepath}")
        except Exception as e: self.status_var.set(f"Erro ao guardar o gráfico: {e}"); self.log_message(f"ERROR: Failed to save graph: {e}")

    def export_data(self):
        if self.last_completed_test_id is None:
            self.status_var.set("Nenhum teste concluído para exportar.")
            self.log_message("WARN: Export data called with no completed test.")
            return
        test_data = self.data_handler.get_test_data(self.last_completed_test_id)
        if not test_data:
            self.status_var.set("Não foram encontrados dados para o último teste.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Guardar Dados do Teste Como...",
            initialfile=f"test_data_{self.last_completed_test_id}.csv"
        )
        if not filepath: self.status_var.set("Exportação dos dados cancelada."); return
        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp_s', 'Voltage_V', 'Current_mA'])
                writer.writerows(test_data)
            self.status_var.set(f"Dados guardados em {filepath}")
            self.log_message(f"INFO: Data for test {self.last_completed_test_id} saved to {filepath}")
        except Exception as e:
            self.status_var.set(f"Erro ao guardar os dados: {e}")
            self.log_message(f"ERROR: Failed to save data for test {self.last_completed_test_id}: {e}")

    def abort_process(self):
        if not self.is_running: return
        self.is_running = False
        self.abort_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.NORMAL)
        
        if self.simulation_mode:
            self.connection_handler.abort()
        else:
            if self.connection_handler.serial_connection and self.connection_handler.serial_connection.is_open:
                self.connection_handler.send('ABORT\n')
                self.log_message("INFO: Processo abortado pelo utilizador.")

    def handle_disconnect(self):
        self.status_var.set("Desconectado. Tente reiniciar a aplicação.")
        self.connection_handler.disconnect()
        self.start_button.config(state=tk.DISABLED)
        self.abort_button.config(state=tk.DISABLED)
        self.is_running = False

    def handle_serial_data(self, data):
        if not data.startswith("DATA,"): self.log_message(f"ESP32/SIM: {data}")
        if data.startswith("PROCESS_END"):
            self.is_running = False
            self.start_button.config(state=tk.NORMAL)
            self.abort_button.config(state=tk.DISABLED)
            if self.current_test_id:
                self.export_graph_button.config(state=tk.NORMAL)
                self.export_data_button.config(state=tk.NORMAL)
                result = "N/A"
                try:
                    pass_voltage = float(self.pass_fail_voltage_var.get())
                    if self.min_voltage >= pass_voltage:
                        result = "PASS"
                        self.pass_fail_label.config(text="PASS", style="pass.TLabel")
                    else:
                        result = "FAIL"
                        self.pass_fail_label.config(text="FAIL", style="fail.TLabel")
                except ValueError:
                    self.pass_fail_label.config(text="N/A", style="TLabel")
                self.data_handler.update_test_result(self.min_voltage, result)
                self.last_completed_test_id = self.current_test_id
                self.current_test_id = None
                self.populate_history_list()
        elif data.startswith("DATA,"):
            try:
                _, time_ms, voltage_v, current_ma = data.split(',')
                time_s = float(time_ms) / 1000.0
                voltage = float(voltage_v)
                current = float(current_ma)
                self.data_handler.log_data_point(int(time_ms), voltage, current)
                self.data_points.append((time_s, voltage, current))
                self.voltage_label.config(text=f"Tensão Atual: {voltage:.3f} V")
                self.current_label.config(text=f"Corrente Atual: {current:.1f} mA")
                if self.min_voltage == 0.0 or voltage < self.min_voltage:
                    self.min_voltage = voltage
                    self.min_voltage_label.config(text=f"Tensão Mínima: {self.min_voltage:.3f} V")
                self.update_graph()
            except (ValueError, IndexError) as e:
                self.log_message(f"ERROR: Falha ao processar dados: {data} ({e})")
            except Exception as e:
                self.log_message(f"ERROR: Erro inesperado em handle_serial_data: {e}")

    def on_closing(self):
        if self.is_running: self.abort_process()
        self.data_handler.save_config()
        if not self.simulation_mode:
            self.connection_handler.disconnect()
        self.root.destroy()
