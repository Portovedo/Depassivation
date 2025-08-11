# Depassivation GUI

A Python-based graphical user interface (GUI) for controlling and monitoring a battery depassivation process. This application communicates with an ESP32 microcontroller to perform tests, visualize data in real-time, and log the results.

## Features

*   **Real-time Data Visualization**: Plots battery voltage against time during the depassivation process.
*   **Hardware Integration**: Connects to an ESP32 device over a USB serial port to send commands and receive data.
*   **Test Configuration**: Allows users to set the test duration and the pass/fail voltage threshold.
*   **Profile Management**: Save, load, and delete testing profiles (duration and voltage settings) for different types of batteries.
*   **Data Logging**: Automatically saves raw data (timestamp, voltage, current) to a CSV file for each test run.
*   **Data Export**: Export the generated graph as a PNG image and the test data as a CSV file.
*   **Status and Logging**: Provides a log area for system messages and a status bar for real-time updates.

## Prerequisites

*   Python 3.x
*   An ESP32 microcontroller flashed with the appropriate firmware to communicate with this GUI.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create a virtual environment (optional but recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Connect the ESP32 device** to your computer via USB. The application will attempt to automatically detect the correct serial port.
2.  **Run the application:**
    ```bash
    python Depassivation_GUI.py
    ```
3.  **Configure the test:**
    *   Set the **Duração (s)** (Duration in seconds).
    *   Set the **Tensão Passa/Falha (V)** (Pass/Fail Voltage in Volts).
    *   Alternatively, load a saved profile.
4.  **Start the process:**
    *   Click the **Iniciar Processo** (Start Process) button.
5.  **Monitor the process:**
    *   Observe the real-time graph and the metrics panel.
6.  **After the process is complete:**
    *   You can export the graph and data using the **Exportar Gráfico** (Export Graph) and **Exportar Dados** (Export Data) buttons.

## Profile Management

You can save your current test configuration as a profile for easy reuse.

*   **To save a profile:** Enter a name in the "Guardar Perfil Como" field and click **Guardar** (Save).
*   **To load a profile:** Select a profile from the dropdown menu and click **Carregar** (Load).
*   **To delete a profile:** Select a profile from the dropdown menu and click **Apagar** (Delete).

Profiles are saved in a `profiles.json` file in the same directory as the application.

## Dependencies

*   [pyserial](https://pyserial.readthedocs.io/): For serial communication with the ESP32.
*   [matplotlib](https://matplotlib.org/): For plotting the data.
