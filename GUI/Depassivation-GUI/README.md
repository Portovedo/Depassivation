# Depassivation Station GUI

## Overview

This application provides a graphical user interface (GUI) for controlling and monitoring a battery depassivation station. It is designed to communicate with an ESP32-based hardware setup over a serial connection, allowing users to run configurable tests and visualize the results in real-time. All test data is saved to a local SQLite database for later review and analysis.

## Features

- **Live Test Monitoring**:
  - Real-time plotting of Voltage vs. Time during a test.
  - Live display of key metrics like current voltage, current, and minimum voltage reached.
  - Automatic detection of serial ports with a manual override option.
- **Configurable Tests**:
  - Set custom test durations and pass/fail voltage thresholds.
  - Save and load different test configurations as named profiles.
- **Persistent Test History**:
  - A "History" tab allows browsing of all previously run tests.
  - Select any past test to view its detailed metrics and its full voltage/time graph.
  - Delete old or unwanted test records from the database.
- **Data Export**:
  - Export the graph of a completed test as a PNG image.
  - Export the raw, time-series data of a completed test to a CSV file.

## Dependencies

The application requires the following Python libraries:

- `pyserial`
- `matplotlib`

## Setup and Usage

1.  **Install Dependencies**:
    Before running the application, ensure you have the required libraries installed. You can install them using pip and the provided `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the Application**:
    To start the GUI, run the `main.py` script:
    ```bash
    python3 main.py
    ```

## Hardware Communication Protocol

The GUI communicates with the hardware (e.g., an ESP32) over a serial connection. The expected commands and data formats are as follows:

- **Commands sent from GUI to Hardware**:
  - `START,<duration_seconds>,<pass_fail_voltage>`: Initiates a new test.
    - Example: `START,10,3.2`
  - `ABORT`: Immediately stops the currently running test.

- **Data sent from Hardware to GUI**:
  - `DATA,<time_milliseconds>,<voltage>,<current_milliamps>`: A single data point reading from the test.
    - Example: `DATA,100,3.65,50.2`
  - `PROCESS_END`: A message indicating that the test has finished normally.
  - Any other line sent from the hardware will be displayed in the "Registo de Dados" (Data Log) text area.