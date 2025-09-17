import threading
import time
import random

class SimulationHandler:
    """
    Simulates the ESP32 hardware for testing the GUI without a physical device.
    It runs in a separate thread and sends data back to the main app via a callback.
    """
    def __init__(self, app):
        self.app = app
        self.is_running = False
        self.simulation_thread = None

    def start(self, duration_sec, pass_fail_voltage):
        """Starts the simulation in a new thread."""
        if self.is_running:
            return

        self.is_running = True
        # The 'daemon=True' ensures the thread will close when the main app closes.
        self.simulation_thread = threading.Thread(
            target=self._run_simulation,
            args=(duration_sec, pass_fail_voltage),
            daemon=True
        )
        self.simulation_thread.start()

    def abort(self):
        """Stops the currently running simulation."""
        self.is_running = False
        self.app.log_message("INFO: Simulation aborted by user.")

    def _run_simulation(self, duration_sec, pass_fail_voltage):
        """The main logic of the simulation, executed in a thread."""
        self.app.log_message("INFO: Starting hardware simulation...")
        
        # Notify the GUI that the process has started
        self.app.root.after(0, self.app.handle_serial_data, "PROCESS_START")

        start_time = time.time()
        time_elapsed_ms = 0
        
        # Simulate initial battery state
        voltage = 3.85
        current = 150.0

        while self.is_running and time_elapsed_ms < (duration_sec * 1000):
            # Simulate a realistic voltage drop and some noise
            voltage -= random.uniform(0.005, 0.02) # Voltage drops over time
            current = 150.0 + random.uniform(-5.0, 5.0) # Current fluctuates slightly
            
            # Ensure voltage doesn't go below a realistic floor
            if voltage < 2.5:
                voltage = 2.5
            
            time_elapsed_ms = int((time.time() - start_time) * 1000)

            # Format the data exactly like the ESP32 does
            data_string = f"DATA,{time_elapsed_ms},{voltage:.3f},{current:.1f}"
            
            # Use root.after() to safely send the data back to the main GUI thread
            self.app.root.after(0, self.app.handle_serial_data, data_string)

            time.sleep(1) # Wait 1 second between measurements, just like the firmware

        # Notify the GUI that the process has ended
        if self.is_running:
            end_message = "PROCESS_END: Simulation completed successfully."
        else:
            end_message = "PROCESS_END: Simulation aborted by user."
            
        self.app.root.after(0, self.app.handle_serial_data, end_message)
        self.is_running = False
