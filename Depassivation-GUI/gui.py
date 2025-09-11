import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, ttk, simpledialog
from tkinter.ttk import Style
import threading
import time
import csv
from datetime import datetime

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from data_handler import DataHandler

class BatteryManagerWindow(tk.Toplevel):
    def __init__(self, parent_app):
        super().__init__(parent_app.root)
        self.parent_app = parent_app
        self.data_handler = self.parent_app.data_handler
        self.title("Manage Batteries")
        self.geometry("400x350")
        self.transient(parent_app.root)
        self.grab_set()
        self._create_widgets()
        self.load_batteries()

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        list_frame = ttk.LabelFrame(main_frame, text="Registered Batteries")
        list_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.battery_listbox = tk.Listbox(list_frame)
        self.battery_listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.battery_listbox.yview)
        self.battery_listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
        delete_button = ttk.Button(list_frame, text="Delete Selected", command=self.delete_battery, style="danger.TButton")
        delete_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5,0))
        add_frame = ttk.LabelFrame(main_frame, text="Register New Battery")
        add_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        add_frame.columnconfigure(0, weight=1)
        self.new_battery_name_var = tk.StringVar()
        ttk.Label(add_frame, text="Battery Name:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        entry = ttk.Entry(add_frame, textvariable=self.new_battery_name_var)
        entry.grid(row=1, column=0, sticky="ew", padx=5)
        add_button = ttk.Button(add_frame, text="Register", command=self.add_battery)
        add_button.grid(row=1, column=1, padx=5, pady=5)

    def load_batteries(self):
        self.battery_listbox.delete(0, tk.END)
        self.batteries = self.data_handler.get_all_batteries()
        for battery in self.batteries:
            self.battery_listbox.insert(tk.END, battery['name'])

    def add_battery(self):
        name = self.new_battery_name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Battery name cannot be empty.", parent=self)
            return
        new_id = self.data_handler.create_battery(name)
        if new_id:
            self.new_battery_name_var.set("")
            self.load_batteries()
            self.parent_app.refresh_battery_dropdown()
        else:
            messagebox.showerror("Error", f"Battery '{name}' already exists.", parent=self)

    def delete_battery(self):
        selection_index = self.battery_listbox.curselection()
        if not selection_index:
            messagebox.showwarning("Warning", "Please select a battery to delete.", parent=self)
            return
        selected_battery = self.batteries[selection_index[0]]
        if messagebox.askyesno("Confirm", f"Are you sure you want to delete '{selected_battery['name']}'?\nAssociated tests will become uncategorized.", parent=self):
            if self.data_handler.delete_battery(selected_battery['id']):
                self.load_batteries()
                self.parent_app.refresh_battery_dropdown()
            else:
                messagebox.showerror("Error", "Could not delete the battery.", parent=self)

class DepassivationApp:
    def __init__(self, root, simulate=False):
        self.root = root
        self.simulation_mode = simulate
        self.is_running = False
        self.current_mode = "main"
        self.current_test_id = None
        self.last_completed_test_id = None
        self.selected_battery_id = None
        self.selected_history_test_id = None
        self.data_points = []
        self.min_voltage = 0.0

        if self.simulation_mode:
            from simulation_handler import SimulationHandler
            self.connection_handler = SimulationHandler(self)
            self.root.title("Battery Analyzer (SIMULATION MODE)")
        else:
            from serial_handler import SerialHandler
            self.connection_handler = SerialHandler(self)
            self.root.title("Battery Analyzer")

        self.data_handler = DataHandler(self)
        config = self.data_handler.load_config()
        self.root.geometry(config.get("geometry", "950x850"))
        self.duration_var = tk.StringVar(value=config.get("duration", "10"))
        self.pass_fail_voltage_var = tk.StringVar(value=config.get("pass_fail_voltage", "3.2"))
        self.selected_port_var = tk.StringVar(value=config.get("last_port", ""))
        self.selected_battery_var = tk.StringVar()
        self.duration_var.trace_add("write", self.update_graph_xaxis)

        self._setup_styles()
        self._create_widgets()

        self.data_handler._init_database()

        self.clear_graph_and_stats()
        self.refresh_battery_dropdown()
        self.populate_battery_history_list()

        if not self.simulation_mode:
            self._refresh_port_list()
        else:
            self.status_var.set("Simulation Mode: Ready.")

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('TButton', font=('Helvetica', 10))
        style.configure('success.TButton', background='#4CAF50', foreground='white', font=('Helvetica', 10, 'bold'))
        style.map('success.TButton', background=[('active', '#45a049')])
        style.configure('danger.TButton', background='#f44336', foreground='white', font=('Helvetica', 10, 'bold'))
        style.map('danger.TButton', background=[('active', '#e53935')])
        style.configure('pass.TLabel', background='green', foreground='white', font=('Helvetica', 16, 'bold'))
        style.configure('fail.TLabel', background='red', foreground='white', font=('Helvetica', 16, 'bold'))

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        self.main_tab = ttk.Frame(self.notebook, padding="10")
        self.history_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.main_tab, text="Test Control")
        self.notebook.add(self.history_tab, text="History")
        self._create_main_tab_widgets(self.main_tab)
        self._create_history_tab_widgets(self.history_tab)
        self._create_status_bar()

    def _create_main_tab_widgets(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=2) # Graph
        parent.grid_rowconfigure(4, weight=1) # Log
        top_frame = ttk.Frame(parent)
        top_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        top_frame.columnconfigure(0, weight=1)
        top_frame.columnconfigure(1, weight=1)
        if not self.simulation_mode:
            self._create_connection_frame(top_frame).grid(row=0, column=0, sticky="nsew", padx=(0, 5))
            self._create_battery_control_frame(top_frame).grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        else:
            self._create_battery_control_frame(top_frame).grid(row=0, column=0, columnspan=2, sticky="nsew")

        # Progress bar for tests
        progress_frame = ttk.LabelFrame(parent, text="Test Progress", padding="10")
        progress_frame.grid(row=1, column=0, sticky="ew", pady=(5,0))
        progress_frame.columnconfigure(0, weight=1)
        self.test_progress_bar = ttk.Progressbar(progress_frame, orient='horizontal', mode='determinate')
        self.test_progress_bar.grid(row=0, column=0, sticky="ew")
        self.cycle_label = ttk.Label(progress_frame, text="Current Cycle: --")
        self.cycle_label.grid(row=1, column=0, sticky="w", pady=(5,0))

        view_container = ttk.Frame(parent)
        view_container.grid(row=2, column=0, sticky="nsew", pady=(5,5))
        view_container.grid_columnconfigure(0, weight=1)
        view_container.grid_rowconfigure(0, weight=1)
        self.main_view_frame = self._create_main_view_widgets(view_container)
        self.main_view_frame.grid(row=0, column=0, sticky="nsew")
        self.live_view_frame = self._create_live_view_widgets(view_container)
        self.live_view_frame.grid(row=0, column=0, sticky="nsew")
        self.show_frame("main")
        bottom_frame = ttk.Frame(parent)
        bottom_frame.grid(row=3, column=0, sticky="ew", pady=(5,0))
        bottom_frame.columnconfigure(0, weight=1)
        bottom_frame.columnconfigure(1, weight=2)
        self._create_settings_frame(bottom_frame).grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self._create_control_frame(bottom_frame).grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self._create_log_frame(parent).grid(row=4, column=0, sticky="nsew", pady=(5,0))

    def _create_history_tab_widgets(self, parent):
        parent.grid_columnconfigure(1, weight=3)
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        list_frame = ttk.Frame(parent)
        list_frame.grid(row=0, column=0, sticky="nswe", padx=(0, 5))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        battery_list_frame = ttk.LabelFrame(list_frame, text="Select Battery", padding="10")
        battery_list_frame.pack(fill="both", expand=True, side="top")
        battery_list_frame.rowconfigure(0, weight=1)
        battery_list_frame.columnconfigure(0, weight=1)
        self.history_battery_list = tk.Listbox(battery_list_frame)
        self.history_battery_list.grid(row=0, column=0, sticky="nswe")
        self.history_battery_list.bind("<<ListboxSelect>>", self.on_history_battery_selected)
        test_list_frame = ttk.LabelFrame(list_frame, text="Test History", padding="10")
        test_list_frame.pack(fill="both", expand=True, side="bottom", pady=(10,0))
        test_list_frame.rowconfigure(0, weight=1)
        test_list_frame.columnconfigure(0, weight=1)
        self.history_tree = ttk.Treeview(test_list_frame, columns=("ID", "Timestamp", "Result"), show="headings")
        self.history_tree.heading("ID", text="ID")
        self.history_tree.heading("Timestamp", text="Date/Time")
        self.history_tree.heading("Result", text="Result")
        self.history_tree.column("ID", width=40, anchor='center')
        self.history_tree.bind("<<TreeviewSelect>>", self.show_history_details)
        self.history_tree.grid(row=0, column=0, sticky="nswe")
        details_frame = ttk.LabelFrame(parent, text="Test Details", padding="10")
        details_frame.grid(row=0, column=1, rowspan=2, sticky="nswe", padx=(5, 0))
        details_frame.grid_columnconfigure(0, weight=1)
        details_frame.grid_rowconfigure(0, weight=1)
        history_graph_frame = ttk.LabelFrame(details_frame, text="Test Graph", padding="10")
        history_graph_frame.grid(row=0, column=0, sticky="ew")
        self.history_fig = Figure(figsize=(5, 3), dpi=100)
        self.history_ax = self.history_fig.add_subplot(111)
        self.history_canvas = FigureCanvasTkAgg(self.history_fig, master=history_graph_frame)
        self.history_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        history_stats_frame = ttk.LabelFrame(details_frame, text="Test Metrics & Actions", padding="10")
        history_stats_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        self.history_id_label = ttk.Label(history_stats_frame, text="Test ID: --")
        self.history_id_label.pack(anchor="w", pady=2)
        self.history_timestamp_label = ttk.Label(history_stats_frame, text="Timestamp: --")
        self.history_timestamp_label.pack(anchor="w", pady=2)
        self.history_duration_label = ttk.Label(history_stats_frame, text="Duration: -- s")
        self.history_duration_label.pack(anchor="w", pady=2)
        self.history_pass_fail_voltage_label = ttk.Label(history_stats_frame, text="Target Voltage: -- V")
        self.history_pass_fail_voltage_label.pack(anchor="w", pady=2)
        self.history_min_voltage_label = ttk.Label(history_stats_frame, text="Min Voltage: -- V")
        self.history_min_voltage_label.pack(anchor="w", pady=8)
        self.history_result_label = ttk.Label(history_stats_frame, text="Result: --", font=("Helvetica", 14, "bold"))
        self.history_result_label.pack(anchor="w", pady=8)
        self.delete_history_button = ttk.Button(history_stats_frame, text="Delete This Test", command=self.delete_selected_history_test, style="danger.TButton", state=tk.DISABLED)
        self.delete_history_button.pack(pady=(10,0))
        export_frame = ttk.Frame(details_frame, padding=(0, 10))
        export_frame.grid(row=2, column=0, sticky="ew", pady=5)
        export_frame.columnconfigure(0, weight=1)
        export_frame.columnconfigure(1, weight=1)
        self.export_history_graph_button = ttk.Button(export_frame, text="Export Graph (.png)", command=self.export_history_graph, state=tk.DISABLED)
        self.export_history_graph_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.export_history_data_button = ttk.Button(export_frame, text="Export Data (.csv)", command=self.export_history_data, state=tk.DISABLED)
        self.export_history_data_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _create_main_view_widgets(self, parent):
        frame = ttk.Frame(parent)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        self._create_graph_and_stats_frame(frame).grid(row=0, column=0, sticky="nsew")
        return frame

    def _create_live_view_widgets(self, parent):
        frame = ttk.Frame(parent, padding=10)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        live_frame = ttk.LabelFrame(frame, text="Live Measurement Mode", padding=20)
        live_frame.grid(sticky="nsew")
        live_frame.columnconfigure(0, weight=1)
        self.live_voltage_label = ttk.Label(live_frame, text="Voltage: -- V", font=("Helvetica", 20))
        self.live_voltage_label.pack(pady=10)
        self.live_current_label = ttk.Label(live_frame, text="Current: -- mA", font=("Helvetica", 20))
        self.live_current_label.pack(pady=10)
        self.live_power_label = ttk.Label(live_frame, text="Power: -- mW", font=("Helvetica", 20))
        self.live_power_label.pack(pady=10)
        self.live_resistance_label = ttk.Label(live_frame, text="Resistance: -- Ω", font=("Helvetica", 20))
        self.live_resistance_label.pack(pady=10)
        self.mosfet_button = ttk.Button(live_frame, text="Activate Load", command=self.toggle_mosfet)
        self.mosfet_button.pack(pady=20, ipadx=10, ipady=5)
        self.mosfet_on = False
        return frame

    def show_frame(self, mode):
        self.current_mode = mode
        if mode == "live":
            self.live_view_frame.tkraise()
            if self.connection_handler.is_connected():
                self.connection_handler.send("SET_MODE,LIVE\n")
        else:
            self.main_view_frame.tkraise()
            if self.connection_handler.is_connected():
                self.connection_handler.send("SET_MODE,IDLE\n")

    def _create_connection_frame(self, parent):
        conn_frame = ttk.LabelFrame(parent, text="Serial Connection", padding="10")
        conn_frame.grid_columnconfigure(0, weight=1)
        self.port_combobox = ttk.Combobox(conn_frame, textvariable=self.selected_port_var, state='readonly')
        self.port_combobox.grid(row=0, column=0, sticky="ew", padx=(0,5))
        self.refresh_ports_button = ttk.Button(conn_frame, text="Refresh", command=self._refresh_port_list)
        self.refresh_ports_button.grid(row=0, column=1, padx=5)
        self.connect_button = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.connect_button.grid(row=0, column=2, padx=5)
        return conn_frame

    def _create_battery_control_frame(self, parent):
        battery_frame = ttk.LabelFrame(parent, text="Battery Selection", padding="10")
        battery_frame.columnconfigure(0, weight=1)
        self.battery_combobox = ttk.Combobox(battery_frame, textvariable=self.selected_battery_var, state='readonly')
        self.battery_combobox.grid(row=0, column=0, sticky="ew", padx=(0,5))
        self.battery_combobox.bind("<<ComboboxSelected>>", self.on_battery_selected)
        manage_button = ttk.Button(battery_frame, text="Manage...", command=self.open_battery_manager)
        manage_button.grid(row=0, column=1, padx=5)
        return battery_frame

    def _create_graph_and_stats_frame(self, parent):
        frame = ttk.Frame(parent)
        frame.grid_columnconfigure(0, weight=3)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        graph_frame = ttk.LabelFrame(frame, text="Graph: Voltage (V) vs. Time (s)", padding="10")
        graph_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        stats_frame = ttk.LabelFrame(frame, text="Metrics", padding="10")
        stats_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.voltage_label = ttk.Label(stats_frame, text="Current Voltage: -- V", font=("Helvetica", 12))
        self.voltage_label.pack(anchor="w", pady=5)
        self.current_label = ttk.Label(stats_frame, text="Current: -- mA", font=("Helvetica", 12))
        self.current_label.pack(anchor="w", pady=5)
        self.min_voltage_label = ttk.Label(stats_frame, text="Min Voltage: -- V", font=("Helvetica", 12, "bold"))
        self.min_voltage_label.pack(anchor="w", pady=10)
        ttk.Separator(stats_frame, orient='horizontal').pack(fill='x', pady=10, padx=5)
        self.pass_fail_label = ttk.Label(stats_frame, text="---", font=("Helvetica", 16, "bold"), anchor="center")
        self.pass_fail_label.pack(fill='x', expand=True, pady=5)
        return frame

    def _create_control_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Controls", padding="10")
        button_frame = ttk.Frame(frame)
        button_frame.pack(side="left", fill="y", padx=(0,10))
        self.start_button = ttk.Button(button_frame, text="Start Test", command=self.start_process, style='success.TButton', state=tk.DISABLED)
        self.start_button.pack(pady=2, fill='x')
        self.abort_button = ttk.Button(button_frame, text="Abort Test", command=self.abort_process, state=tk.DISABLED, style='danger.TButton')
        self.abort_button.pack(pady=2, fill='x')
        self.toggle_live_button = ttk.Button(button_frame, text="Live View", command=lambda: self.show_frame("live" if self.current_mode == "main" else "main"))
        self.toggle_live_button.pack(pady=(10, 2), fill='x')
        export_frame = ttk.LabelFrame(frame, text="Export Last Test", padding=10)
        export_frame.pack(side="left", fill="both", expand=True)
        self.export_live_graph_button = ttk.Button(export_frame, text="Export Graph (.png)", command=self.export_live_graph, state=tk.DISABLED)
        self.export_live_graph_button.pack(pady=2, fill='x')
        self.export_live_data_button = ttk.Button(export_frame, text="Export Data (.csv)", command=self.export_live_data, state=tk.DISABLED)
        self.export_live_data_button.pack(pady=2, fill='x')
        return frame

    def _create_settings_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Test Configuration", padding="10")
        ttk.Label(frame, text="Duration (s):").pack(anchor="w")
        self.duration_entry = ttk.Entry(frame, textvariable=self.duration_var)
        self.duration_entry.pack(fill="x", expand=True, pady=(0,5))
        ttk.Label(frame, text="Pass/Fail Voltage (V):").pack(anchor="w")
        self.pass_fail_entry = ttk.Entry(frame, textvariable=self.pass_fail_voltage_var)
        self.pass_fail_entry.pack(fill="x", expand=True)
        return frame

    def _create_log_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Data Log", padding="10")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.log_area = scrolledtext.ScrolledText(frame, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 10), height=8)
        self.log_area.grid(row=0, column=0, sticky="nsew")
        return frame

    def _create_status_bar(self):
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def open_battery_manager(self):
        BatteryManagerWindow(self)

    def log_message(self, msg):
        if hasattr(self, 'log_area'):
            self.log_area.config(state=tk.NORMAL)
            self.log_area.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
            self.log_area.see(tk.END)
            self.log_area.config(state=tk.DISABLED)

    def refresh_battery_dropdown(self):
        self.batteries = self.data_handler.get_all_batteries()
        battery_names = [b['name'] for b in self.batteries]
        self.battery_combobox['values'] = battery_names
        if battery_names:
            self.battery_combobox.set(battery_names[0])
        else:
            self.battery_combobox.set('')
        self.on_battery_selected(None)
        self.populate_battery_history_list()

    def on_battery_selected(self, event):
        selected_name = self.selected_battery_var.get()
        battery = next((b for b in self.batteries if b['name'] == selected_name), None)
        if battery:
            self.selected_battery_id = battery['id']
            if self.connection_handler.is_connected() or self.simulation_mode:
                self.start_button.config(state=tk.NORMAL)
        else:
            self.selected_battery_id = None
            self.start_button.config(state=tk.DISABLED)

    def start_process(self):
        if self.selected_battery_id is None:
            messagebox.showerror("Error", "Please select a battery before starting a test.")
            return
        try:
            duration = int(self.duration_var.get())
        except ValueError:
            messagebox.showerror("Error", "Duration must be a valid number.")
            return
        self.clear_graph_and_stats()
        self.current_test_id = self.data_handler.create_new_test(self.selected_battery_id, duration, float(self.pass_fail_voltage_var.get()))
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.abort_button.config(state=tk.NORMAL)
        self.connection_handler.send(f"START,{duration}\n")

    def abort_process(self):
        if not self.is_running: return
        self.is_running = False
        self.abort_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.NORMAL if self.selected_battery_id else tk.DISABLED)
        if self.connection_handler.is_connected():
            self.connection_handler.send('ABORT\n')

    def toggle_mosfet(self):
        self.mosfet_on = not self.mosfet_on
        self.connection_handler.send(f"SET_MOSFET,{1 if self.mosfet_on else 0}\n")
        self.mosfet_button.config(text="Deactivate Load" if self.mosfet_on else "Activate Load")

    def _refresh_port_list(self):
        ports = self.connection_handler.get_ports()
        port_names = [p.device for p in ports]
        self.port_combobox['values'] = port_names
        if port_names: self.port_combobox.set(port_names[0])

    def toggle_connection(self):
        if self.connection_handler.is_connected():
            self.connection_handler.disconnect()
            self.connect_button.config(text="Connect")
            self.start_button.config(state=tk.DISABLED)
        else:
            if self.connection_handler.connect(self.selected_port_var.get()):
                self.connect_button.config(text="Disconnect")
                if self.selected_battery_id:
                    self.start_button.config(state=tk.NORMAL)

    def populate_battery_history_list(self):
        self.history_battery_list.delete(0, tk.END)
        self.history_battery_list.insert(tk.END, "[Uncategorized Tests]")
        for battery in self.batteries:
            self.history_battery_list.insert(tk.END, battery['name'])

    def on_history_battery_selected(self, event=None):
        selection_idx = self.history_battery_list.curselection()
        if not selection_idx:
            if self.history_battery_list.size() > 0:
                self.history_battery_list.selection_set(0)
                selection_idx = (0,)
            else: return
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        selected_name = self.history_battery_list.get(selection_idx[0])
        if selected_name == "[Uncategorized Tests]":
            tests = self.data_handler.get_uncategorized_tests()
        else:
            battery = next((b for b in self.batteries if b['name'] == selected_name), None)
            tests = self.data_handler.get_tests_for_battery(battery['id']) if battery else []
        for test in tests:
            self.history_tree.insert("", tk.END, values=(test[0], test[1], test[2] or "Incomplete"))

    def update_graph_xaxis(self, *args):
        try:
            duration = int(self.duration_var.get())
            if duration > 0:
                self.ax.set_xlim(0, duration)
                self.canvas.draw()
        except (ValueError, tk.TclError): pass

    def clear_graph_and_stats(self):
        self.data_points = []
        self.min_voltage = 0.0
        self.last_completed_test_id = None
        self.voltage_label.config(text="Current Voltage: -- V")
        self.current_label.config(text="Current: -- mA")
        self.min_voltage_label.config(text="Min Voltage: -- V")
        self.pass_fail_label.config(text="---", style="TLabel")
        if hasattr(self, 'export_live_graph_button'):
            self.export_live_graph_button.config(state=tk.DISABLED)
            self.export_live_data_button.config(state=tk.DISABLED)
        self.ax.cla()
        self.ax.grid(True)
        self.update_graph_xaxis()
        self.canvas.draw()

    def update_graph(self):
        self.ax.cla()
        if self.data_points:
            times, voltages, _ = zip(*self.data_points)
            self.ax.plot(times, voltages, marker='o', linestyle='-')
        self.ax.grid(True)
        self.update_graph_xaxis()
        self.canvas.draw()

    def handle_serial_data(self, data):
        self.log_message(f"RECV: {data}")
        if data.startswith("BTN_PRESS"):
            _, button = data.split(',')
            if button == "START": self.start_process()
            elif button == "ABORT": self.abort_process()
            elif button == "MEASURE": self.show_frame("live" if self.current_mode == "main" else "main")
        elif data.startswith("LIVE_DATA"):
            try:
                _, v, c, p, r = data.split(',')
                self.live_voltage_label.config(text=f"Voltage: {float(v):.3f} V")
                self.live_current_label.config(text=f"Current: {float(c):.1f} mA")
                self.live_power_label.config(text=f"Power: {float(p):.1f} mW")
                self.live_resistance_label.config(text=f"Resistance: {float(r):.2f} Ω")
            except (ValueError, IndexError): pass
        elif data.startswith("PROCESS_END"):
            self.is_running = False
            self.start_button.config(state=tk.NORMAL if self.selected_battery_id else tk.DISABLED)
            self.abort_button.config(state=tk.DISABLED)
            if self.current_test_id:
                self.export_live_graph_button.config(state=tk.NORMAL)
                self.export_live_data_button.config(state=tk.NORMAL)
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
                    self.pass_fail_label.config(text="ERROR", style="fail.TLabel")
                self.data_handler.update_test_result(self.min_voltage, result)
                self.last_completed_test_id = self.current_test_id
                self.current_test_id = None
            self.on_history_battery_selected(None)
        elif data.startswith("DATA,"):
            try:
                _, time_ms, voltage_v, current_ma = data.split(',')
                voltage = float(voltage_v)
                self.data_points.append((float(time_ms) / 1000.0, voltage, float(current_ma)))
                self.voltage_label.config(text=f"Current Voltage: {voltage:.3f} V")
                self.current_label.config(text=f"Current: {float(current_ma):.1f} mA")
                if self.min_voltage == 0.0 or voltage < self.min_voltage:
                    self.min_voltage = voltage
                    self.min_voltage_label.config(text=f"Min Voltage: {self.min_voltage:.3f} V")
                self.update_graph()
            except (ValueError, IndexError): pass

    def on_closing(self):
        if self.is_running: self.abort_process()
        self.data_handler.save_config()
        if self.connection_handler:
            self.connection_handler.disconnect()
        self.root.destroy()

    def show_history_details(self, event):
        selection = self.history_tree.selection()
        if not selection:
            self.selected_history_test_id = None
            self.delete_history_button.config(state=tk.DISABLED)
            self.export_history_graph_button.config(state=tk.DISABLED)
            self.export_history_data_button.config(state=tk.DISABLED)
            return
        self.delete_history_button.config(state=tk.NORMAL)
        selected_item = selection[0]
        test_id = self.history_tree.item(selected_item, "values")[0]
        self.selected_history_test_id = test_id
        summary = self.data_handler.get_test_summary(test_id)
        data_points = self.data_handler.get_test_data(test_id)
        if not summary:
            self.log_message(f"WARN: No details found for test ID {test_id}.")
            return
        self.history_id_label.config(text=f"Test ID: {summary['id']}")
        self.history_timestamp_label.config(text=f"Timestamp: {summary['timestamp']}")
        self.history_duration_label.config(text=f"Duration: {summary['duration']} s")
        self.history_pass_fail_voltage_label.config(text=f"Target Voltage: {summary['pass_fail_voltage']} V")
        min_v = summary['min_voltage']
        self.history_min_voltage_label.config(text=f"Min Voltage: {min_v:.3f} V" if min_v is not None else "N/A")
        result = summary['result']
        self.history_result_label.config(text=f"Result: {result if result else 'N/A'}")
        self.history_ax.cla()
        if data_points:
            self.export_history_graph_button.config(state=tk.NORMAL)
            self.export_history_data_button.config(state=tk.NORMAL)
            times, voltages, _ = zip(*data_points)
            self.history_ax.plot(times, voltages, marker='o', linestyle='-')
        else:
            self.export_history_graph_button.config(state=tk.DISABLED)
            self.export_history_data_button.config(state=tk.DISABLED)
        self.history_ax.set_title(f"Test Data (ID: {test_id})")
        self.history_ax.set_xlabel("Time (s)")
        self.history_ax.set_ylabel("Voltage (V)")
        self.history_ax.set_ylim(0, 5)
        self.history_ax.set_xlim(0, summary['duration'])
        self.history_ax.grid(True)
        self.history_fig.tight_layout()
        self.history_canvas.draw()

    def delete_selected_history_test(self):
        if self.selected_history_test_id is None:
            messagebox.showwarning("Warning", "No test selected to delete.")
            return
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently delete test ID {self.selected_history_test_id}?"):
            if self.data_handler.delete_test(self.selected_history_test_id):
                self.log_message(f"INFO: Deleted test {self.selected_history_test_id}.")
                self.selected_history_test_id = None
                self.history_id_label.config(text="Test ID: --")
                self.history_timestamp_label.config(text="Timestamp: --")
                self.history_result_label.config(text="Result: --")
                self.history_ax.cla()
                self.history_canvas.draw()
                self.on_history_battery_selected()
            else:
                messagebox.showerror("Error", "Failed to delete the test.")

    def export_history_graph(self):
        if self.selected_history_test_id is None:
            messagebox.showwarning("Warning", "Please select a test from the history list first.")
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")], title="Save History Graph As...", initialfile=f"test_graph_{self.selected_history_test_id}.png")
        if not filepath: return
        try:
            self.history_fig.savefig(filepath, dpi=300)
            self.log_message(f"INFO: Saved history graph to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save graph: {e}")

    def export_history_data(self):
        if self.selected_history_test_id is None:
            messagebox.showwarning("Warning", "Please select a test from the history list first.")
            return
        test_data = self.data_handler.get_test_data(self.selected_history_test_id)
        if not test_data:
            messagebox.showwarning("Warning", "No data points found for the selected test.")
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title="Save History Data As...", initialfile=f"test_data_{self.selected_history_test_id}.csv")
        if not filepath: return
        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp_s', 'Voltage_V', 'Current_mA'])
                writer.writerows(test_data)
            self.log_message(f"INFO: Saved history data to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save data: {e}")

    def export_live_graph(self):
        if self.last_completed_test_id is None:
            messagebox.showwarning("Warning", "Please complete a test before exporting.")
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")], title="Save Live Test Graph As...", initialfile=f"test_graph_{self.last_completed_test_id}.png")
        if not filepath: return
        try:
            self.fig.savefig(filepath, dpi=300)
            self.log_message(f"INFO: Saved live test graph to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save graph: {e}")

    def export_live_data(self):
        if self.last_completed_test_id is None:
            messagebox.showwarning("Warning", "Please complete a test before exporting.")
            return
        test_data = self.data_handler.get_test_data(self.last_completed_test_id)
        if not test_data:
            messagebox.showwarning("Warning", "No data points found for the last test.")
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title="Save Live Test Data As...", initialfile=f"test_data_{self.last_completed_test_id}.csv")
        if not filepath: return
        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp_s', 'Voltage_V', 'Current_mA'])
                writer.writerows(test_data)
            self.log_message(f"INFO: Saved live test data to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save data: {e}")
