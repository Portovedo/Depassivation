/**
 * @file main.cpp
 * @brief Firmware for a battery depassivation station controlled via Serial.
 *
 * This firmware communicates with a Python GUI to run a timed test on a battery.
 * It uses a non-blocking architecture to ensure it is always responsive to
 * commands like 'ABORT'.
 *
 * Communication Protocol:
 * - GUI to ESP32:
 * - "START,<duration_sec>,<pass_fail_voltage>" -> Begins the test.
 * - "ABORT" -> Immediately stops the test.
 * - ESP32 to GUI:
 * - "DATA,<time_ms>,<voltage_V>,<current_mA>" -> Sends a data point.
 * - "PROCESS_START" -> Acknowledges the start of the test.
 * - "PROCESS_END: [message]" -> Signals the end of the test.
 * - Other text is for logging/debugging.
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA219.h>

// --- Pin Definitions ---
const int MOSFET_GATE_PIN = 23; // GPIO that controls the power MOSFET Gate

// --- Global Objects ---
Adafruit_INA219 ina219;

// --- State and Timing Variables ---
bool isProcessRunning = false;
unsigned long processStartTime = 0;        // When the current process started
unsigned long depassivationDurationMs = 0; // Total duration for the current test
unsigned long lastMeasurementTime = 0;     // When the last measurement was taken
const long measurementIntervalMs = 1000;   // How often to measure (1 second)

// --- Forward Declarations ---
// Declaring functions before they are used is good practice.
void handleSerialCommands();
void startDepassivationProcess(unsigned long duration);
void stopDepassivationProcess(String message);
void measureAndLogData();

// =================================================================
//  SETUP: Runs once on boot or reset.
// =================================================================
void setup() {
  // Start Serial communication at 115200 baud
  Serial.begin(115200);
  Serial.println("ESP32 Depassivation Station Initialized.");

  // Initialize the MOSFET pin as an output and ensure it's off by default.
  pinMode(MOSFET_GATE_PIN, OUTPUT);
  digitalWrite(MOSFET_GATE_PIN, LOW);

  // Initialize the INA219 current sensor.
  // If it's not found, print an error and halt execution.
  if (!ina219.begin()) {
    Serial.println("FATAL: Failed to find INA219 chip. Check wiring.");
    while (1) {
      delay(10); // Halt indefinitely
    }
  }
  Serial.println("INA219 sensor found. Ready for commands.");
}

// =================================================================
//  LOOP: Runs continuously after setup.
// =================================================================
void loop() {
  // Always check for new commands from the GUI.
  handleSerialCommands();

  // The following code only runs if a test is in progress.
  if (isProcessRunning) {
    // Check 1: Has the total test duration elapsed?
    if (millis() - processStartTime >= depassivationDurationMs) {
      stopDepassivationProcess("Process completed successfully.");
    }

    // Check 2: Is it time to take another measurement?
    // This is a NON-BLOCKING delay. The loop continues to run while waiting.
    if (millis() - lastMeasurementTime >= measurementIntervalMs) {
      lastMeasurementTime = millis(); // Reset the timer for the next interval
      measureAndLogData();
    }
  }
}

// =================================================================
//  Core Functions
// =================================================================

/**
 * @brief Checks for and processes incoming commands from the serial port.
 */
void handleSerialCommands() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim(); // Remove any leading/trailing whitespace

    // Command: START,<duration>,<voltage>
    if (command.startsWith("START") && !isProcessRunning) {
      // Find the comma separating START from the duration
      int firstComma = command.indexOf(',');
      if (firstComma > 0) {
        // Find the second comma to isolate the duration string
        int secondComma = command.indexOf(',', firstComma + 1);
        if (secondComma > 0) {
          String durationStr = command.substring(firstComma + 1, secondComma);
          // Convert duration from seconds (sent by GUI) to milliseconds
          unsigned long durationSec = durationStr.toInt();
          startDepassivationProcess(durationSec * 1000);
        }
      }
    }
    // Command: ABORT
    else if (command.equalsIgnoreCase("ABORT") && isProcessRunning) {
      stopDepassivationProcess("Process aborted by user.");
    }
  }
}

/**
 * @brief Begins the depassivation test.
 * @param duration The total duration of the test in milliseconds.
 */
void startDepassivationProcess(unsigned long duration) {
  Serial.println("PROCESS_START");
  isProcessRunning = true;
  processStartTime = millis();
  lastMeasurementTime = millis(); // Take the first measurement immediately
  depassivationDurationMs = duration;

  // Turn on the MOSFET to connect the load resistor to the battery
  digitalWrite(MOSFET_GATE_PIN, HIGH);
  Serial.println("Load connected. Starting measurements...");

  // Perform the first measurement right away
  measureAndLogData();
}

/**
 * @brief Stops the depassivation test and resets the state.
 * @param message The reason for stopping, to be sent to the GUI.
 */
void stopDepassivationProcess(String message) {
  // Disconnect the load resistor to stop draining the battery
  digitalWrite(MOSFET_GATE_PIN, LOW);
  isProcessRunning = false;
  Serial.println("Load disconnected.");

  // Notify the GUI that the process has ended
  Serial.println("PROCESS_END: " + message);
}

/**
 * @brief Reads data from the INA219 and sends it to the GUI.
 */
void measureAndLogData() {
  // The INA219 measures voltage on the high side of the shunt resistor.
  float shuntVoltage_mV = ina219.getShuntVoltage_mV();
  float busVoltage_V = ina219.getBusVoltage_V(); // Voltage after the shunt
  float current_mA = ina219.getCurrent_mA();

  // To get the true battery voltage, add the small voltage drop across the shunt.
  float loadVoltage_V = busVoltage_V + (shuntVoltage_mV / 1000.0);

  // Send data to the GUI in a clean CSV format.
  // This method avoids creating large String objects, which is more memory-efficient.
  Serial.print("DATA,");
  Serial.print(millis() - processStartTime);
  Serial.print(",");
  Serial.print(loadVoltage_V, 3); // Print voltage with 3 decimal places
  Serial.print(",");
  Serial.println(current_mA, 2); // Print current with 2 decimal places and a newline
}
