# Battery Depassivation Station

## Overview

This project provides a complete hardware and software solution for testing and analyzing the depassivation process of batteries. It consists of two main parts:

1.  **Python GUI**: A user-friendly desktop application built with Tkinter for controlling tests, viewing live data, and managing a history of test results.
2.  **ESP32 Firmware**: Code for an ESP32 microcontroller that controls the hardware (MOSFET, INA219 sensor) to perform the actual test on the battery.

The two components communicate over a serial (USB) connection, creating a robust and easy-to-use testing station.

---

## Features

- **Live Test Monitoring**:
  - Real-time plotting of Voltage vs. Time during a test.
  - Live display of key metrics like current voltage, current, and minimum voltage reached.
- **Persistent Test History**:
  - All test results are automatically saved to a local SQLite database.
  - A "History" tab allows browsing of all previously run tests.
  - Select any past test to view its detailed metrics and its full voltage/time graph.
  - Delete old or unwanted test records.
- **Configurable Tests**:
  - Set custom test durations and pass/fail voltage thresholds.
  - Save and load different test configurations as named profiles.
- **Data Export**:
  - Export the graph of any completed test as a PNG image.
  - Export the raw, time-series data of any completed test to a CSV file.
- **Hardware Simulation Mode**:
  - Run the GUI without any physical hardware connected.
  - Ideal for testing UI changes, demonstrating the software, or developing new features.
- **Visual Status Indicator**:
  - The onboard red LED on the ESP32 lights up during a test, providing a clear visual status.

---

## Project Structure

The workspace is organized into two main folders:

-   `GUI/`: Contains the Python source code for the desktop application.
-   `Firmware/`: Contains the C++/Arduino source code for the ESP32, managed by PlatformIO.

---

## Part 1: GUI Setup and Usage

### Dependencies

The application requires the following Python libraries:

-   `pyserial`
-   `matplotlib`

### Installation

1.  Navigate to the `GUI/` directory.
2.  Install the required libraries using the `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```

### Running the Application

You can run the GUI in two modes from the `GUI/` directory:

1.  **Normal Mode (with Hardware)**:
    ```bash
    python main.py
    ```
2.  **Simulation Mode (No Hardware Needed)**:
    ```bash
    python main.py --simulate
    ```

---

## Part 2: Firmware Setup and Usage

The firmware is managed using the **PlatformIO IDE** extension in Visual Studio Code.

### Dependencies

-   Visual Studio Code
-   The official [PlatformIO IDE extension](https://platformio.org/install/ide?install=vscode) from the VS Code Marketplace.
-   The hardware libraries (`Adafruit INA219`) are managed automatically by PlatformIO via the `platformio.ini` file.

### Setup and Upload

1.  Open the entire project workspace in VS Code.
2.  Open the `Firmware/platformio.ini` file.
3.  Change the `upload_port` and `monitor_port` to match the COM port of your ESP32.
4.  Use the PlatformIO toolbar icons at the bottom of the VS Code window:
    -   Click the **Build (✓)** icon to compile the code.
    -   Click the **Upload (→)** icon to flash the firmware to your ESP32. You may need to use the manual boot sequence (hold BOOT, press EN, release BOOT) while PlatformIO is trying to connect.

---

## Communication Protocol

The GUI and ESP32 communicate using a simple text-based protocol over serial.

-   **Commands sent from GUI to Hardware**:
    -   `START,<duration_seconds>,<pass_fail_voltage>`: Initiates a new test. (e.g., `START,10,3.2`)
    -   `ABORT`: Immediately stops the currently running test.

-   **Data sent from Hardware to GUI**:
    -   `DATA,<time_ms>,<voltage_V>,<current_mA>`: A single data point reading from the test. (e.g., `DATA,1000,3.650,150.20`)
    -   `PROCESS_START`: Acknowledges that the test has begun.
    -   `PROCESS_END: [message]`: Signals that the test has finished, with a reason.
    -   Any other line is treated as a general log message.
