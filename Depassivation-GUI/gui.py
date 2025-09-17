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

        # --- Button Frame ---
        button_frame = ttk.Frame(list_frame)
        button_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5,0))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        delete_button = ttk.Button(button_frame, text="Delete Battery", command=self.delete_battery, style="danger.TButton")
        delete_button.grid(row=0, column=0, sticky="ew", padx=(0, 2))

        delete_tests_button = ttk.Button(button_frame, text="Delete All Tests", command=self.delete_battery_tests, style="danger.TButton")
        delete_tests_button.grid(row=0, column=1, sticky="ew", padx=(2, 0))

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

    def delete_battery_tests(self):
        selection_index = self.battery_listbox.curselection()
        if not selection_index:
            messagebox.showwarning("Warning", "Please select a battery to delete its tests.", parent=self)
            return
        selected_battery = self.batteries[selection_index[0]]

        tests = self.data_handler.get_tests_for_battery(selected_battery['id'])
        test_count = len(tests)

        if test_count == 0:
            messagebox.showinfo("Info", f"Battery '{selected_battery['name']}' has no associated tests to delete.", parent=self)
            return

        if messagebox.askyesno("Confirm", f"Are you sure you want to delete all {test_count} tests for '{selected_battery['name']}'?\nThis action cannot be undone.", parent=self):
            if self.data_handler.delete_all_tests_for_battery(selected_battery['id']):
                self.parent_app.log_message(f"INFO: Deleted all tests for battery '{selected_battery['name']}'.")
                self.parent_app.on_history_battery_selected() # Refresh history view
            else:
                messagebox.showerror("Error", "Could not delete the tests for the selected battery.", parent=self)

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
        self.current_history_sequences = {}
        self.current_sequence_info = None
        self.data_points = []
        self.min_voltage = 0.0
        self.max_current = 0.0
        self.power = 0.0
        self.resistance = 0.0
        self.live_min_voltage = 0.0
        self.live_max_current = 0.0
        self.live_min_resistance = 0.0
        self.live_max_resistance = 0.0

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
        self.pass_fail_voltage_var = tk.StringVar(value=config.get("pass_fail_voltage", "3.2"))
        self.selected_port_var = tk.StringVar(value=config.get("last_port", ""))
        self.selected_battery_var = tk.StringVar()
        self.baseline_duration_var = tk.StringVar(value=config.get("baseline_duration", "10"))
        self.depassivation_duration_var = tk.StringVar(value=config.get("depassivation_duration", "180"))

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
        style.configure('warning.TButton', background='#ff9800', foreground='white', font=('Helvetica', 10, 'bold'))
        style.map('warning.TButton', background=[('active', '#fb8c00')])
        style.configure('pass.TLabel', background='green', foreground='white', font=('Helvetica', 16, 'bold'))
        style.configure('fail.TLabel', background='red', foreground='white', font=('Helvetica', 16, 'bold'))
        style.configure("blue.Horizontal.TProgressbar", background='#007BFF')

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

        progress_frame = ttk.LabelFrame(parent, text="Test Progress", padding="10")
        progress_frame.grid(row=1, column=0, sticky="ew", pady=(5,0))
        progress_frame.columnconfigure(0, weight=1)
        self.test_progress_bar = ttk.Progressbar(progress_frame, orient='horizontal', mode='determinate', style="blue.Horizontal.TProgressbar")
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
        self.history_tree = ttk.Treeview(test_list_frame, columns=("ID", "Type", "Timestamp", "Result"), show="headings", selectmode="extended")
        self.history_tree.heading("ID", text="ID")
        self.history_tree.heading("Type", text="Type")
        self.history_tree.heading("Timestamp", text="Date/Time")
        self.history_tree.heading("Result", text="Result")
        self.history_tree.column("ID", width=40, anchor='center')
        self.history_tree.column("Type", width=100, anchor='center')
        self.history_tree.bind("<<TreeviewSelect>>", self.on_history_selection_change)
        self.history_tree.grid(row=0, column=0, sticky="nswe")
        self.history_tree.tag_configure('baseline', background='lightblue')
        self.history_tree.tag_configure('check', background='lightgreen')
        details_frame = ttk.LabelFrame(parent, text="Test Details", padding="10")
        details_frame.grid(row=0, column=1, rowspan=2, sticky="nswe", padx=(5, 0))
        details_frame.grid_columnconfigure(0, weight=1)
        details_frame.grid_rowconfigure(0, weight=1)
        details_frame.grid_rowconfigure(1, weight=1)

        # Graph 1: Depassivation
        graph1_frame = ttk.LabelFrame(details_frame, text="Depassivation Cycle", padding="10")
        graph1_frame.grid(row=0, column=0, sticky="nsew")
        self.history_fig1 = Figure(figsize=(5, 2.5), dpi=100)
        self.history_ax1 = self.history_fig1.add_subplot(111)
        self.history_canvas1 = FigureCanvasTkAgg(self.history_fig1, master=graph1_frame)
        self.history_canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Graph 2: Baseline vs. Check
        graph2_frame = ttk.LabelFrame(details_frame, text="Baseline vs. Check", padding="10")
        graph2_frame.grid(row=1, column=0, sticky="nsew", pady=(5,0))
        self.history_fig2 = Figure(figsize=(5, 2.5), dpi=100)
        self.history_ax2 = self.history_fig2.add_subplot(111)
        self.history_canvas2 = FigureCanvasTkAgg(self.history_fig2, master=graph2_frame)
        self.history_canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # This container will hold either the single test stats or the comparison stats
        history_stats_container = ttk.Frame(details_frame)
        history_stats_container.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        history_stats_container.grid_columnconfigure(0, weight=1)
        history_stats_container.grid_rowconfigure(0, weight=1)

        # --- Single Test View ---
        self.history_stats_frame = ttk.LabelFrame(history_stats_container, text="Test Metrics & Actions", padding="10")
        self.history_stats_frame.grid(row=0, column=0, sticky="nsew")
        self.history_id_label = ttk.Label(self.history_stats_frame, text="Test ID: --")
        self.history_id_label.pack(anchor="w", pady=2)
        self.history_timestamp_label = ttk.Label(self.history_stats_frame, text="Timestamp: --")
        self.history_timestamp_label.pack(anchor="w", pady=2)
        self.history_duration_label = ttk.Label(self.history_stats_frame, text="Duration: -- s")
        self.history_duration_label.pack(anchor="w", pady=2)
        self.history_pass_fail_voltage_label = ttk.Label(self.history_stats_frame, text="Target Voltage: -- V")
        self.history_pass_fail_voltage_label.pack(anchor="w", pady=2)
        self.history_min_voltage_label = ttk.Label(self.history_stats_frame, text="Min Voltage: -- V")
        self.history_min_voltage_label.pack(anchor="w", pady=2)
        self.history_max_current_label = ttk.Label(self.history_stats_frame, text="Max Current: -- mA")
        self.history_max_current_label.pack(anchor="w", pady=2)
        self.history_power_label = ttk.Label(self.history_stats_frame, text="Power: -- mW")
        self.history_power_label.pack(anchor="w", pady=2)
        self.history_resistance_label = ttk.Label(self.history_stats_frame, text="Resistance: -- Ω")
        self.history_resistance_label.pack(anchor="w", pady=8)
        self.history_result_label = ttk.Label(self.history_stats_frame, text="Result: --", font=("Helvetica", 14, "bold"))
        self.history_result_label.pack(anchor="w", pady=8)
        self.delete_history_button = ttk.Button(self.history_stats_frame, text="Delete This Test", command=self.delete_selected_history_test, style="danger.TButton", state=tk.DISABLED)
        self.delete_history_button.pack(pady=(10,0))

        # --- Sequence Comparison View ---
        self.history_comparison_frame = ttk.LabelFrame(history_stats_container, text="Sequence Metrics", padding="10")
        self.history_comparison_frame.grid(row=0, column=0, sticky="nsew")

        # Define headers
        headers = ["Metric", "Baseline (1)", "Depassivation (2)", "Check (3)"]
        for col, header in enumerate(headers):
            ttk.Label(self.history_comparison_frame, text=header, font=('Helvetica', 10, 'bold')).grid(row=0, column=col, padx=5, pady=2, sticky='w')

        self.comparison_labels = {}
        self.metrics_to_display = ["Test ID", "Timestamp", "Duration", "Max Voltage", "Min Voltage", "Last Voltage"]

        for i, metric_name in enumerate(self.metrics_to_display, 1):
            ttk.Label(self.history_comparison_frame, text=f"{metric_name}:").grid(row=i, column=0, sticky='w', padx=5, pady=2)
            for j, cycle in enumerate(["baseline", "depassivation", "check"], 1):
                label_key = f'{cycle}_{metric_name.lower().replace(" ", "_")}'
                label = ttk.Label(self.history_comparison_frame, text="--")
                label.grid(row=i, column=j, sticky='w', padx=5)
                self.comparison_labels[label_key] = label

        self.history_stats_frame.tkraise()
        export_frame = ttk.Frame(details_frame, padding=(0, 10))
        export_frame.grid(row=3, column=0, sticky="ew", pady=5)
        self.export_history_graph_button = ttk.Button(export_frame, text="Export Graph (.png)", command=self.export_history_graph, state=tk.DISABLED)
        self.export_history_graph_button.pack(side="left", expand=True, fill="x", padx=(0,5))
        self.export_history_data_button = ttk.Button(export_frame, text="Export Data (.csv)", command=self.export_history_data, state=tk.DISABLED)
        self.export_history_data_button.pack(side="left", expand=True, fill="x", padx=(5,0))

    def _create_main_view_widgets(self, parent):
        frame = ttk.Frame(parent)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        self._create_graph_and_stats_frame(frame).grid(row=0, column=0, sticky="nsew")
        return frame

    def _create_live_view_widgets(self, parent):
        frame = ttk.Frame(parent, padding=10)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)

        # --- Live Readings Frame ---
        live_frame = ttk.LabelFrame(frame, text="Live Measurement", padding=20)
        live_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        live_frame.columnconfigure(0, weight=1)

        self.live_voltage_label = ttk.Label(live_frame, text="Voltage: -- V", font=("Helvetica", 20))
        self.live_voltage_label.pack(pady=5)
        self.live_current_label = ttk.Label(live_frame, text="Current: -- mA", font=("Helvetica", 20))
        self.live_current_label.pack(pady=5)
        self.live_power_label = ttk.Label(live_frame, text="Power: -- mW", font=("Helvetica", 20))
        self.live_power_label.pack(pady=5)
        self.live_resistance_label = ttk.Label(live_frame, text="Resistance: -- Ω", font=("Helvetica", 20))
        self.live_resistance_label.pack(pady=5)
        self.mosfet_button = ttk.Button(live_frame, text="Activate Load", command=self.toggle_mosfet)
        self.mosfet_button.pack(pady=20, ipadx=10, ipady=5, side='bottom')
        self.mosfet_on = False

        # --- Live Statistics Frame ---
        stats_frame = ttk.LabelFrame(frame, text="Live Statistics", padding=20)
        stats_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self.live_min_v_label = ttk.Label(stats_frame, text="Min Voltage: -- V", font=("Helvetica", 12))
        self.live_min_v_label.pack(anchor='w', pady=4)
        self.live_max_c_label = ttk.Label(stats_frame, text="Max Current: -- mA", font=("Helvetica", 12))
        self.live_max_c_label.pack(anchor='w', pady=4)
        self.live_min_r_label = ttk.Label(stats_frame, text="Min Resistance: -- Ω", font=("Helvetica", 12))
        self.live_min_r_label.pack(anchor='w', pady=4)
        self.live_max_r_label = ttk.Label(stats_frame, text="Max Resistance: -- Ω", font=("Helvetica", 12))
        self.live_max_r_label.pack(anchor='w', pady=4)

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
        self.max_current_label = ttk.Label(stats_frame, text="Max Current: -- mA", font=("Helvetica", 12))
        self.max_current_label.pack(anchor="w", pady=5)
        self.min_voltage_label = ttk.Label(stats_frame, text="Min Voltage: -- V", font=("Helvetica", 12, "bold"))
        self.min_voltage_label.pack(anchor="w", pady=10)
        self.power_label = ttk.Label(stats_frame, text="Power: -- mW", font=("Helvetica", 12))
        self.power_label.pack(anchor="w", pady=5)
        self.resistance_label = ttk.Label(stats_frame, text="Resistance: -- Ω", font=("Helvetica", 12))
        self.resistance_label.pack(anchor="w", pady=5)
        ttk.Separator(stats_frame, orient='horizontal').pack(fill='x', pady=10, padx=5)
        self.pass_fail_label = ttk.Label(stats_frame, text="---", font=("Helvetica", 16, "bold"), anchor="center")
        self.pass_fail_label.pack(fill='x', expand=True, pady=5)
        return frame

    def _create_control_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Controls", padding="10")
        frame.columnconfigure(0, weight=1)

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=0, column=0, sticky="ew")
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)

        self.baseline_button = ttk.Button(button_frame, text="Run Baseline Test", command=self.start_baseline_test, style='success.TButton', state=tk.DISABLED)
        self.baseline_button.grid(row=0, column=0, sticky="ew", padx=2)
        self.depassivation_button = ttk.Button(button_frame, text="Run Depassivation Cycle", command=self.start_depassivation_test, style='success.TButton', state=tk.DISABLED)
        self.depassivation_button.grid(row=0, column=1, sticky="ew", padx=2)
        self.check_button = ttk.Button(button_frame, text="Run Depassivation Check", command=self.start_check_test, style='success.TButton', state=tk.DISABLED)
        self.check_button.grid(row=0, column=2, sticky="ew", padx=2)

        self.abort_button = ttk.Button(frame, text="Abort Test", command=self.abort_process, state=tk.DISABLED, style='danger.TButton')
        self.abort_button.grid(row=1, column=0, sticky="ew", pady=(5,0))

        self.toggle_live_button = ttk.Button(frame, text="Live View", command=lambda: self.show_frame("live" if self.current_mode == "main" else "main"))
        self.toggle_live_button.grid(row=2, column=0, sticky="ew", pady=(10, 2))

        export_frame = ttk.LabelFrame(frame, text="Export Last Test", padding=10)
        export_frame.grid(row=3, column=0, sticky="ew", pady=(5,0))
        export_frame.columnconfigure(0, weight=1)
        export_frame.columnconfigure(1, weight=1)
        self.export_live_graph_button = ttk.Button(export_frame, text="Export Graph", command=self.export_live_graph, state=tk.DISABLED)
        self.export_live_graph_button.grid(row=0, column=0, sticky="ew", padx=(0,5))
        self.export_live_data_button = ttk.Button(export_frame, text="Export Data", command=self.export_live_data, state=tk.DISABLED)
        self.export_live_data_button.grid(row=0, column=1, sticky="ew", padx=(5,0))
        return frame

    def _create_settings_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Test Configuration", padding="10")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Baseline/Check Duration (s):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(frame, textvariable=self.baseline_duration_var, width=10).grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(frame, text="Depassivation Duration (s):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(frame, textvariable=self.depassivation_duration_var, width=10).grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(frame, text="Pass/Fail Voltage (V):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.pass_fail_entry = ttk.Entry(frame, textvariable=self.pass_fail_voltage_var)
        self.pass_fail_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
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

    def on_battery_selected(self, event=None):
        selected_name = self.selected_battery_var.get()
        battery = next((b for b in self.batteries if b['name'] == selected_name), None)
        is_ready = (self.connection_handler and self.connection_handler.is_connected()) or self.simulation_mode

        # Disable all buttons by default
        if hasattr(self, 'baseline_button'):
            self.baseline_button.config(state=tk.DISABLED)
            self.depassivation_button.config(state=tk.DISABLED)
            self.check_button.config(state=tk.DISABLED)

        if battery and is_ready:
            self.selected_battery_id = battery['id']
            last_test = self.data_handler.get_last_test_for_battery(self.selected_battery_id)

            if not last_test:
                # No tests yet, only baseline is allowed.
                self.baseline_button.config(state=tk.NORMAL)
            else:
                result_text = last_test['result'] or ""
                if "Baseline Test" in result_text:
                    # After baseline, only depassivation is allowed.
                    self.depassivation_button.config(state=tk.NORMAL)
                elif "Depassivation Cycle" in result_text:
                    # After depassivation, only check is allowed.
                    self.check_button.config(state=tk.NORMAL)
                elif "Depassivation Check" in result_text:
                    # After a full sequence, a new baseline can be started.
                    self.baseline_button.config(state=tk.NORMAL)
                else:
                    # For any other case (e.g., incomplete, aborted), start fresh with a baseline.
                    self.baseline_button.config(state=tk.NORMAL)
        else:
            self.selected_battery_id = None

    def start_baseline_test(self):
        duration = int(self.baseline_duration_var.get())
        self._start_test("Baseline Test", duration)

    def start_depassivation_test(self):
        duration = int(self.depassivation_duration_var.get())
        self._start_test("Depassivation Cycle", duration)

    def start_check_test(self):
        duration = int(self.baseline_duration_var.get())
        self._start_test("Depassivation Check", duration)

    def _start_test(self, test_name, duration):
        if self.selected_battery_id is None:
            messagebox.showerror("Error", "Please select a battery before starting a test.")
            return
        if self.is_running:
            messagebox.showwarning("Warning", "A test is already in progress.")
            return

        self.clear_graph_and_stats()
        self.cycle_label.config(text=f"Current Cycle: {test_name}")
        self.test_progress_bar['maximum'] = duration * 1000
        self.test_progress_bar['value'] = 0
        self.update_graph_xaxis(duration)
        self.current_test_id = self.data_handler.create_new_test(self.selected_battery_id, duration, float(self.pass_fail_voltage_var.get()))
        self.is_running = True

        self.baseline_button.config(state=tk.DISABLED)
        self.depassivation_button.config(state=tk.DISABLED)
        self.check_button.config(state=tk.DISABLED)
        self.abort_button.config(state=tk.NORMAL)

        self.connection_handler.send(f"START,{duration}\n")

    def abort_process(self):
        if not self.is_running: return
        self.is_running = False
        self.abort_button.config(state=tk.DISABLED)
        self.baseline_button.config(state=tk.NORMAL if self.selected_battery_id else tk.DISABLED)
        self.depassivation_button.config(state=tk.NORMAL if self.selected_battery_id else tk.DISABLED)
        self.check_button.config(state=tk.NORMAL if self.selected_battery_id else tk.DISABLED)

        if self.current_mode == "live":
            self.live_current_label.config(text="Current: --")
            self.live_power_label.config(text="Power: --")
            self.live_resistance_label.config(text="Resistance: --")

        if self.connection_handler.is_connected():
            self.connection_handler.send('ABORT\n')

    def toggle_mosfet(self):
        self.mosfet_on = not self.mosfet_on
        self.connection_handler.send(f"SET_MOSFET,{1 if self.mosfet_on else 0}\n")

        if self.mosfet_on:
            # Reset stats when activating load
            self.live_min_voltage = 0.0
            self.live_max_current = 0.0
            self.live_min_resistance = 0.0
            self.live_max_resistance = 0.0
            self.live_min_v_label.config(text="Min Voltage: -- V")
            self.live_max_c_label.config(text="Max Current: -- mA")
            self.live_min_r_label.config(text="Min Resistance: -- Ω")
            self.live_max_r_label.config(text="Max Resistance: -- Ω")
            self.mosfet_button.config(text="Deactivate Load", style="warning.TButton")
        else:
            self.mosfet_button.config(text="Activate Load", style="TButton")
            # Clear transient readings
            self.live_current_label.config(text="Current: -- mA")
            self.live_power_label.config(text="Power: -- mW")
            self.live_resistance_label.config(text="Resistance: -- Ω")

    def _refresh_port_list(self):
        ports = self.connection_handler.get_ports()
        port_names = [p.device for p in ports]
        self.port_combobox['values'] = port_names
        if port_names: self.port_combobox.set(port_names[0] if not self.selected_port_var.get() else self.selected_port_var.get())

    def toggle_connection(self):
        if self.connection_handler.is_connected():
            self.connection_handler.disconnect()
            self.connect_button.config(text="Connect")
            self.on_battery_selected(None) # Re-evaluates button states
        else:
            if self.connection_handler.connect(self.selected_port_var.get()):
                self.connect_button.config(text="Disconnect")
                self.on_battery_selected(None) # Re-evaluates button states
                self.connection_handler.send("SET_MODE,IDLE\n")

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
            else:
                return

        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        selected_name = self.history_battery_list.get(selection_idx[0])
        if selected_name == "[Uncategorized Tests]":
            tests = self.data_handler.get_uncategorized_tests()
        else:
            battery = next((b for b in self.batteries if b['name'] == selected_name), None)
            tests = self.data_handler.get_tests_for_battery(battery['id']) if battery else []

        from datetime import datetime, timedelta

        tests_with_type = []
        for test in tests:
            result_text = test['result'] or "Incomplete"
            test_type = "Unknown"
            if "Baseline Test" in result_text: test_type = "Baseline"
            elif "Depassivation Cycle" in result_text: test_type = "Depassivation"
            elif "Depassivation Check" in result_text: test_type = "Check"

            tests_with_type.append({
                'id': test['id'], 'timestamp': test['timestamp'], 'result': result_text,
                'duration': test['duration'], 'type': test_type
            })

        display_items = []
        self.current_history_sequences = {}
        i = 0
        while i < len(tests_with_type):
            is_sequence = False
            if i <= len(tests_with_type) - 3:
                test1 = tests_with_type[i]
                test2 = tests_with_type[i+1]
                test3 = tests_with_type[i+2]

                if test1['type'] == "Baseline" and test2['type'] == "Depassivation" and test3['type'] == "Check":
                    is_sequence = True
                    try:
                        t2_start = datetime.strptime(test2['timestamp'], "%Y-%m-%d %H:%M:%S")
                        t2_end = t2_start + timedelta(seconds=test2['duration'])
                        t3_start = datetime.strptime(test3['timestamp'], "%Y-%m-%d %H:%M:%S")
                        time_diff = t3_start - t2_end

                        total_seconds = max(0, time_diff.total_seconds())
                        hours, remainder = divmod(total_seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        time_diff_str = ""
                        if hours > 0: time_diff_str += f"{int(hours)}h "
                        if minutes > 0: time_diff_str += f"{int(minutes)}m "
                        time_diff_str += f"{int(seconds)}s"

                        original_result = test3['result'].split(' - ')[-1]
                        final_result_text = f"Completed - {original_result} ({time_diff_str} rest)"

                        sequence_info = {'baseline': test1, 'depassivation': test2, 'check': test3, 'rest_time': time_diff_str}

                        master_id = test1['id']
                        self.current_history_sequences[master_id] = sequence_info

                        display_items.append({
                            'id': master_id, 'type': 'Sequence', 'timestamp': test1['timestamp'],
                            'result': final_result_text, 'tags': ('check',)
                        })

                        i += 3
                    except (ValueError, TypeError):
                        is_sequence = False

            if not is_sequence:
                test = tests_with_type[i]
                tags = ('baseline',) if "baseline" in test['type'].lower() else ()
                display_items.append({
                    'id': test['id'], 'type': test['type'], 'timestamp': test['timestamp'],
                    'result': test['result'], 'tags': tags
                })
                i += 1

        for item in display_items:
            self.history_tree.insert("", tk.END, values=(item['id'], item['type'], item['timestamp'], item['result']), tags=item['tags'])

    def update_graph_xaxis(self, duration):
        try:
            if duration > 0:
                self.ax.set_xlim(0, duration)
                self.canvas.draw()
        except (ValueError, tk.TclError): pass

    def clear_graph_and_stats(self):
        self.data_points = []
        self.min_voltage = 0.0
        self.max_current = 0.0
        self.power = 0.0
        self.resistance = 0.0
        self.last_completed_test_id = None
        self.voltage_label.config(text="Current Voltage: -- V")
        self.current_label.config(text="Current: -- mA")
        self.max_current_label.config(text="Max Current: -- mA")
        self.min_voltage_label.config(text="Min Voltage: -- V")
        self.power_label.config(text="Power: -- mW")
        self.resistance_label.config(text="Resistance: -- Ω")
        self.pass_fail_label.config(text="---", style="TLabel")
        if hasattr(self, 'export_live_graph_button'):
            self.export_live_graph_button.config(state=tk.DISABLED)
            self.export_live_data_button.config(state=tk.DISABLED)
        self.ax.cla()
        self.ax.grid(True)
        self.canvas.draw()

    def update_graph(self):
        self.ax.cla()
        if self.data_points:
            times, voltages, _ = zip(*self.data_points)
            self.ax.plot(times, voltages, marker='o', linestyle='-')
        self.ax.grid(True)
        self.update_graph_xaxis(self.test_progress_bar['maximum'] / 1000.0)
        self.canvas.draw()

    def handle_serial_data(self, data):
        self.log_message(f"RECV: {data}")
        if data.startswith("BTN_PRESS"):
            _, button = data.split(',')
            # Physical buttons are not tied to specific tests in this UI version
        elif data.startswith("LIVE_DATA"):
            try:
                _, v_str, c_str, p_str, r_str = data.split(',')
                v = float(v_str)
                self.live_voltage_label.config(text=f"Voltage: {v:.3f} V")

                if self.mosfet_on:
                    c = float(c_str)
                    p = float(p_str)
                    r = float(r_str)
                    self.live_current_label.config(text=f"Current: {c:.1f} mA")
                    self.live_power_label.config(text=f"Power: {p:.1f} mW")
                    self.live_resistance_label.config(text=f"Resistance: {r:.2f} Ω")

                    if self.live_min_voltage == 0.0 or v < self.live_min_voltage:
                        self.live_min_voltage = v
                        self.live_min_v_label.config(text=f"Min Voltage: {v:.3f} V")
                    if c > self.live_max_current:
                        self.live_max_current = c
                        self.live_max_c_label.config(text=f"Max Current: {c:.1f} mA")
                    if r > 0:
                        if self.live_min_resistance == 0.0 or r < self.live_min_resistance:
                            self.live_min_resistance = r
                            self.live_min_r_label.config(text=f"Min Resistance: {r:.2f} Ω")
                        if r > self.live_max_resistance:
                            self.live_max_resistance = r
                            self.live_max_r_label.config(text=f"Max Resistance: {r:.2f} Ω")
            except (ValueError, IndexError): pass
        elif data.startswith("PROCESS_END"):
            self.is_running = False
            self.abort_button.config(state=tk.DISABLED)
            self.baseline_button.config(state=tk.NORMAL if self.selected_battery_id else tk.DISABLED)
            self.depassivation_button.config(state=tk.NORMAL if self.selected_battery_id else tk.DISABLED)
            self.check_button.config(state=tk.NORMAL if self.selected_battery_id else tk.DISABLED)

            if self.current_test_id:
                self.export_live_graph_button.config(state=tk.NORMAL)
                self.export_live_data_button.config(state=tk.NORMAL)
                result_status = "N/A"
                try:
                    pass_voltage = float(self.pass_fail_voltage_var.get())
                    result_status = "PASS" if self.min_voltage >= pass_voltage else "FAIL"
                    self.pass_fail_label.config(text=result_status, style=f"{result_status.lower()}.TLabel")
                except ValueError:
                    result_status = "ERROR"
                    self.pass_fail_label.config(text=result_status, style="fail.TLabel")

                test_name = self.cycle_label.cget("text").replace("Current Cycle: ", "")
                final_result = f"{test_name} - {result_status}"
                self.data_handler.update_test_result(self.min_voltage, self.max_current, self.power, self.resistance, final_result)
                self.last_completed_test_id = self.current_test_id
                self.current_test_id = None

            # --- FIX: Auto-select the battery that was just tested in the history view ---
            if self.last_completed_test_id:
                summary = self.data_handler.get_test_summary(self.last_completed_test_id)
                if summary and summary['battery_id'] is not None:
                    battery_id_to_select = summary['battery_id']
                    all_batteries = self.data_handler.get_all_batteries()
                    battery_to_select = next((b for b in all_batteries if b['id'] == battery_id_to_select), None)
                    if battery_to_select:
                        listbox_items = self.history_battery_list.get(0, tk.END)
                        try:
                            idx = listbox_items.index(battery_to_select['name'])
                            self.history_battery_list.selection_clear(0, tk.END)
                            self.history_battery_list.selection_set(idx)
                            self.history_battery_list.see(idx)
                        except ValueError:
                            pass

            self.on_history_battery_selected(None)
        elif data.startswith("DATA,"):
            try:
                _, time_ms_str, voltage_v, current_ma, power_mw, resistance_ohm = data.split(',')
                time_ms = int(time_ms_str)
                voltage = float(voltage_v)
                current = float(current_ma)
                self.power = float(power_mw)
                self.resistance = float(resistance_ohm)

                self.test_progress_bar['value'] = time_ms
                self.data_points.append((time_ms / 1000.0, voltage, current))
                self.voltage_label.config(text=f"Current Voltage: {voltage:.3f} V")
                self.current_label.config(text=f"Current: {current:.1f} mA")
                self.power_label.config(text=f"Power: {self.power:.1f} mW")
                self.resistance_label.config(text=f"Resistance: {self.resistance:.2f} Ω")

                if current > self.max_current:
                    self.max_current = current
                    self.max_current_label.config(text=f"Max Current: {self.max_current:.1f} mA")
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

    def on_history_selection_change(self, event):
        selection = self.history_tree.selection()
        self.delete_history_button.config(state=tk.NORMAL if selection else tk.DISABLED)

        if len(selection) == 1:
            item_id = self.history_tree.selection()[0]
            test_id = self.history_tree.item(item_id, "values")[0]

            if test_id in self.current_history_sequences:
                self.show_sequence_details(self.current_history_sequences[test_id])
            else:
                self.show_history_details(item_id)
        else:
            self.clear_history_details()

    def clear_history_details(self):
        self.selected_history_test_id = None
        self.current_sequence_info = None
        self.history_stats_frame.tkraise()
        self.history_id_label.config(text="Test ID: --")
        self.history_timestamp_label.config(text="Timestamp: --")
        self.history_duration_label.config(text="Duration: -- s")
        self.history_pass_fail_voltage_label.config(text="Target Voltage: -- V")
        self.history_min_voltage_label.config(text="Min Voltage: -- V")
        self.history_max_current_label.config(text="Max Current: -- mA")
        self.history_power_label.config(text="Power: -- mW")
        self.history_resistance_label.config(text="Resistance: -- Ω")
        self.history_result_label.config(text="Result: --")
        self.history_ax1.cla()
        self.history_ax1.grid(True)
        self.history_canvas1.draw()
        self.history_ax2.cla()
        self.history_ax2.grid(True)
        self.history_canvas2.draw()
        self.export_history_graph_button.config(state=tk.DISABLED)
        self.export_history_data_button.config(state=tk.DISABLED)

    def show_history_details(self, selected_item):
        self.history_stats_frame.tkraise()
        self.current_sequence_info = None

        test_id = self.history_tree.item(selected_item, "values")[0]
        self.selected_history_test_id = test_id
        summary = self.data_handler.get_test_summary(test_id)
        if not summary:
            self.log_message(f"WARN: No details found for test ID {test_id}.")
            return

        data_points = self.data_handler.get_test_data(test_id)
        self.history_id_label.config(text=f"Test ID: {summary['id']}")
        self.history_timestamp_label.config(text=f"Timestamp: {summary['timestamp']}")
        self.history_duration_label.config(text=f"Duration: {summary['duration']} s")
        self.history_pass_fail_voltage_label.config(text=f"Target Voltage: {summary['pass_fail_voltage']} V")
        self.history_min_voltage_label.config(text=f"Min Voltage: {summary['min_voltage']:.3f}" if summary['min_voltage'] is not None else "--")
        self.history_max_current_label.config(text=f"Max Current: {summary['max_current']:.1f} mA" if summary['max_current'] is not None else "--")
        self.history_power_label.config(text=f"Power: {summary['power']:.1f} mW" if summary['power'] is not None else "--")
        self.history_resistance_label.config(text=f"Resistance: {summary['resistance']:.2f} Ω" if summary['resistance'] is not None else "--")
        self.history_result_label.config(text=f"Result: {summary['result'] or 'N/A'}")

        self.history_ax1.cla()
        if data_points:
            self.export_history_graph_button.config(state=tk.NORMAL)
            self.export_history_data_button.config(state=tk.NORMAL)
            times, voltages, _ = zip(*data_points)
            self.history_ax1.plot(times, voltages, marker='o', linestyle='-')
        else:
            self.export_history_graph_button.config(state=tk.DISABLED)
            self.export_history_data_button.config(state=tk.DISABLED)
        self.history_ax1.set_title(f"Test Data (ID: {test_id})")
        self.history_ax1.set_xlabel("Time (s)")
        self.history_ax1.set_ylabel("Voltage (V)")
        self.history_ax1.set_ylim(0, 5)
        self.history_ax1.set_xlim(0, summary['duration'])
        self.history_ax1.grid(True)
        self.history_fig1.tight_layout()
        self.history_canvas1.draw()
        self.history_ax2.cla()
        self.history_ax2.grid(True)
        self.history_canvas2.draw()

    def show_sequence_details(self, sequence_info):
        self.history_comparison_frame.tkraise()
        self.current_sequence_info = sequence_info
        self.selected_history_test_id = None # Not a single test
        self._plot_sequence_graph()

        s1 = self.data_handler.get_test_summary(sequence_info['baseline']['id'])
        s2 = self.data_handler.get_test_summary(sequence_info['depassivation']['id'])
        s3 = self.data_handler.get_test_summary(sequence_info['check']['id'])
        d1 = self.data_handler.get_test_data(s1['id'])
        d3 = self.data_handler.get_test_data(s3['id'])

        last_voltage1 = d1[-1][1] if d1 else None
        last_voltage3 = d3[-1][1] if d3 else None

        summaries = {"baseline": s1, "depassivation": s2, "check": s3}

        for cycle, summary in summaries.items():
            if not summary: continue

            self.comparison_labels[f'{cycle}_test_id'].config(text=summary['id'])
            self.comparison_labels[f'{cycle}_timestamp'].config(text=summary['timestamp'])
            self.comparison_labels[f'{cycle}_duration'].config(text=f"{summary['duration']} s")
            self.comparison_labels[f'{cycle}_max_voltage'].config(text=f"{summary['max_current']:.1f} mA" if summary['max_current'] is not None else "--")
            self.comparison_labels[f'{cycle}_min_voltage'].config(text=f"{summary['min_voltage']:.3f} V" if summary['min_voltage'] is not None else "--")

        self.comparison_labels['baseline_last_voltage'].config(text=f"{last_voltage1:.3f} V" if last_voltage1 is not None else "--")
        self.comparison_labels['check_last_voltage'].config(text=f"{last_voltage3:.3f} V" if last_voltage3 is not None else "--")

        # Result Section
        if last_voltage1 is not None and last_voltage3 is not None:
            diff = last_voltage3 - last_voltage1
            color = "green" if diff > 0 else "red"

            result_text = f"Last Voltage 1st Cycle: {last_voltage1:.3f} V\n"
            result_text += f"Last Voltage 3rd Cycle: {last_voltage3:.3f} V\n"
            result_text += f"Difference: {diff:+.3f} V"

            result_label = ttk.Label(self.history_comparison_frame, text=result_text, foreground=color, font=('Helvetica', 11, 'bold'))
            result_label.grid(row=len(self.metrics_to_display)+2, column=0, columnspan=4, sticky='w', padx=5, pady=10)

    def _plot_sequence_graph(self):
        if not self.current_sequence_info: return
        self.history_ax1.cla()
        self.history_ax2.cla()

        s1 = self.data_handler.get_test_summary(self.current_sequence_info['baseline']['id'])
        d1 = self.data_handler.get_test_data(s1['id'])
        s2 = self.data_handler.get_test_summary(self.current_sequence_info['depassivation']['id'])
        d2 = self.data_handler.get_test_data(s2['id'])
        s3 = self.data_handler.get_test_summary(self.current_sequence_info['check']['id'])
        d3 = self.data_handler.get_test_data(s3['id'])

        # Plot 1: Depassivation cycle
        if d2:
            t, v, _ = zip(*d2)
            self.history_ax1.plot(t, v, marker='.', linestyle='-', label=f"Depassivation (ID: {s2['id']})", color='orange')
            self.history_ax1.set_xlim(0, s2['duration'])

        self.history_ax1.set_title("Depassivation Cycle")
        self.history_ax1.set_xlabel("Time (s)")
        self.history_ax1.set_ylabel("Voltage (V)")
        self.history_ax1.set_ylim(0, 5)
        self.history_ax1.grid(True)
        self.history_ax1.legend()
        self.history_fig1.tight_layout()
        self.history_canvas1.draw()

        # Plot 2: Baseline vs. Check
        max_duration = 0
        if d1:
            t, v, _ = zip(*d1)
            self.history_ax2.plot(t, v, marker='.', linestyle='-', label=f"Baseline (ID: {s1['id']})", color='blue')
            max_duration = max(max_duration, s1['duration'])
        if d3:
            t, v, _ = zip(*d3)
            self.history_ax2.plot(t, v, marker='.', linestyle='-', label=f"Check (ID: {s3['id']})", color='green')
            max_duration = max(max_duration, s3['duration'])

        self.history_ax2.set_title("Baseline vs. Check")
        self.history_ax2.set_xlabel("Time (s)")
        self.history_ax2.set_ylabel("Voltage (V)")
        self.history_ax2.set_ylim(0, 5)
        if max_duration > 0:
            self.history_ax2.set_xlim(0, max_duration)
        self.history_ax2.grid(True)
        self.history_ax2.legend()
        self.history_fig2.tight_layout()
        self.history_canvas2.draw()

    def delete_selected_history_test(self):
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "No test selected to delete.")
            return

        test_ids_to_delete = []
        num_sequences = 0
        num_individual_tests = 0

        for item_id_in_tree in selection:
            test_id_str = self.history_tree.item(item_id_in_tree, "values")[0]
            test_id = int(test_id_str)

            if test_id in self.current_history_sequences:
                num_sequences += 1
                sequence = self.current_history_sequences[test_id]
                test_ids_to_delete.append(int(sequence['baseline']['id']))
                test_ids_to_delete.append(int(sequence['depassivation']['id']))
                test_ids_to_delete.append(int(sequence['check']['id']))
            else:
                num_individual_tests += 1
                test_ids_to_delete.append(test_id)

        test_ids_to_delete = sorted(list(set(test_ids_to_delete)))

        msg_parts = []
        if num_sequences > 0:
            msg_parts.append(f"{num_sequences} sequence(s)")
        if num_individual_tests > 0:
            msg_parts.append(f"{num_individual_tests} individual test(s)")

        if not msg_parts: return

        confirm_msg = f"Are you sure you want to permanently delete {' and '.join(msg_parts)}?\nThis will delete a total of {len(test_ids_to_delete)} test records."

        if messagebox.askyesno("Confirm Delete", confirm_msg, parent=self.root):
            deleted_count = 0
            for test_id in test_ids_to_delete:
                if self.data_handler.delete_test(test_id):
                    deleted_count += 1
            self.log_message(f"INFO: Deleted {deleted_count} test record(s).")
            self.on_history_battery_selected()
            self.clear_history_details()

    def export_history_graph(self):
        if self.current_sequence_info:
            test_ids = f"seq_{self.current_sequence_info['baseline']['id']}_{self.current_sequence_info['check']['id']}"
            initial_file = f"test_graph_{test_ids}.png"
        elif self.selected_history_test_id:
            initial_file = f"test_graph_{self.selected_history_test_id}.png"
        else:
            messagebox.showwarning("Warning", "Please select a test or sequence from the history list first.")
            return

        filepath = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")], title="Save History Graph As...", initialfile=initial_file)
        if not filepath: return
        try:
            self.history_fig.savefig(filepath, dpi=300)
            self.log_message(f"INFO: Saved history graph to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save graph: {e}")

    def export_history_data(self):
        if self.current_sequence_info:
            test_id = self.current_sequence_info[self.history_graph_view if self.history_graph_view == 'depassivation' else 'baseline']['id']
            if self.history_graph_view == 'comparison':
                messagebox.showwarning("Warning", "CSV export for comparison view is not supported. Please select a single test or the depassivation view.")
                return
        elif self.selected_history_test_id:
            test_id = self.selected_history_test_id
        else:
            messagebox.showwarning("Warning", "Please select a test from the history list first.")
            return

        test_data = self.data_handler.get_test_data(test_id)
        if not test_data:
            messagebox.showwarning("Warning", "No data points found for the selected test.")
            return

        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title="Save History Data As...", initialfile=f"test_data_{test_id}.csv")
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
