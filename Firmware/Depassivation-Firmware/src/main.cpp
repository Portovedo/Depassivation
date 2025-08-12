/**
 * @file main.cpp
 * @brief Firmware for a battery depassivation station controlled via Serial.
 *
 * This firmware communicates with a Python GUI to run a timed test on a battery.
 * It uses a non-blocking architecture and controls the onboard LED for status.
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
const int LED_PIN = 2;          // Onboard LED on most ESP32 DevKits

// --- Global Objects ---
Adafruit_INA219 ina219;

// --- State and Timing Variables ---
bool isProcessRunning = false;
unsigned long processStartTime = 0;
unsigned long depassivationDurationMs = 0;
unsigned long lastMeasurementTime = 0;
const long measurementIntervalMs = 1000;

// --- Forward Declarations ---
void handleSerialCommands();
void startDepassivationProcess(unsigned long duration);
void stopDepassivationProcess(String message);
void measureAndLogData();

// =================================================================
//  SETUP: Runs once on boot or reset.
// =================================================================
void setup() {
  Serial.begin(115200);
  Serial.println("ESP32 Depassivation Station Initialized.");

  // Initialize the MOSFET pin as an output and ensure it's off.
  pinMode(MOSFET_GATE_PIN, OUTPUT);
  digitalWrite(MOSFET_GATE_PIN, LOW);

  // --- NEW: Initialize the onboard LED pin and ensure it's off. ---
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Initialize the INA219 current sensor.
  if (!ina219.begin()) {
    Serial.println("FATAL: Failed to find INA219 chip. Check wiring.");
    while (1) {
      digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Blink LED to indicate fatal error
      delay(250);
    }
  }
  Serial.println("INA219 sensor found. Ready for commands.");
}

// =================================================================
//  LOOP: Runs continuously after setup.
// =================================================================
void loop() {
  handleSerialCommands();

  if (isProcessRunning) {
    if (millis() - processStartTime >= depassivationDurationMs) {
      stopDepassivationProcess("Process completed successfully.");
    }

    if (millis() - lastMeasurementTime >= measurementIntervalMs) {
      lastMeasurementTime = millis();
      measureAndLogData();
    }
  }
}

// =================================================================
//  Core Functions
// =================================================================

void handleSerialCommands() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command.startsWith("START") && !isProcessRunning) {
      int firstComma = command.indexOf(',');
      if (firstComma > 0) {
        int secondComma = command.indexOf(',', firstComma + 1);
        if (secondComma > 0) {
          String durationStr = command.substring(firstComma + 1, secondComma);
          unsigned long durationSec = durationStr.toInt();
          startDepassivationProcess(durationSec * 1000);
        }
      }
    } else if (command.equalsIgnoreCase("ABORT") && isProcessRunning) {
      stopDepassivationProcess("Process aborted by user.");
    }
  }
}

void startDepassivationProcess(unsigned long duration) {
  Serial.println("PROCESS_START");
  isProcessRunning = true;
  processStartTime = millis();
  lastMeasurementTime = millis();
  depassivationDurationMs = duration;

  // --- NEW: Turn the onboard LED ON to indicate a test is running. ---
  digitalWrite(LED_PIN, HIGH);

  digitalWrite(MOSFET_GATE_PIN, HIGH);
  Serial.println("Load connected. Starting measurements...");
  measureAndLogData();
}

void stopDepassivationProcess(String message) {
  // --- NEW: Turn the onboard LED OFF as the test is over. ---
  digitalWrite(LED_PIN, LOW);

  digitalWrite(MOSFET_GATE_PIN, LOW);
  isProcessRunning = false;
  Serial.println("Load disconnected.");
  Serial.println("PROCESS_END: " + message);
}

void measureAndLogData() {
  float shuntVoltage_mV = ina219.getShuntVoltage_mV();
  float busVoltage_V = ina219.getBusVoltage_V();
  float current_mA = ina219.getCurrent_mA();
  float loadVoltage_V = busVoltage_V + (shuntVoltage_mV / 1000.0);

  Serial.print("DATA,");
  Serial.print(millis() - processStartTime);
  Serial.print(",");
  Serial.print(loadVoltage_V, 3);
  Serial.print(",");
  Serial.println(current_mA, 2);
}
