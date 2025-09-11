/**
 * @file main.cpp
 * @brief Firmware for a battery depassivation and analysis station.
 *
 * This firmware communicates with a Python GUI to run timed tests and live measurements.
 * It supports an RGB status LED, three physical buttons, and an INA219 sensor.
 *
 * Communication Protocol:
 * - GUI to ESP32:
 *   - "START,<duration_sec>" -> Begins the depassivation test.
 *   - "ABORT" -> Stops the current test.
 *   - "SET_MODE,<IDLE|TEST|LIVE>" -> Sets the device's operational mode.
 *   - "SET_MOSFET,<1|0>" -> Manually controls the MOSFET in LIVE mode.
 * - ESP32 to GUI:
 *   - "DATA,<time_ms>,<voltage_V>,<current_mA>" -> Sends a data point during a test.
 *   - "LIVE_DATA,<voltage_V>,<current_mA>,<power_mW>,<resistance_Ohm>" -> Sends live data points.
 *   - "BTN_PRESS,<START|ABORT|MEASURE>" -> Notifies GUI of a physical button press.
 *   - "PROCESS_START" -> Acknowledges the start of the test.
 *   - "PROCESS_END: [message]" -> Signals the end of the test.
 *   - "FATAL: [message]" -> Reports a critical error.
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA219.h>

// --- Pin Definitions ---
// High-Power Control
const int MOSFET_GATE_PIN = 13;
const int MOSFET_LED_PIN = 14;

// RGB Status LED (Common Cathode)
const int RGB_R_PIN = 25;
const int RGB_G_PIN = 26;
const int RGB_B_PIN = 27;

// Push Buttons (with external 10k pulldown resistors)
const int BTN_START_PIN = 32;
const int BTN_ABORT_PIN = 33;
const int BTN_MEASURE_PIN = 34;

// --- Global Objects ---
Adafruit_INA219 ina219;

// --- State Machine ---
enum State { IDLE, TEST_RUNNING, FINISHING, LIVE_VIEW, SUCCESS, FAILED };
State currentState = IDLE;

// --- Timing and Test Variables ---
unsigned long processStartTime = 0;
unsigned long depassivationDurationMs = 0;
unsigned long lastMeasurementTime = 0;
const long measurementIntervalMs = 100;
unsigned long stateChangeTime = 0; // For timed states like SUCCESS/FAILED

// --- Button Debouncing ---
const int DEBOUNCE_DELAY_MS = 50;
bool lastStartState = LOW, lastAbortState = LOW, lastMeasureState = LOW;
unsigned long lastStartDebounce = 0, lastAbortDebounce = 0, lastMeasureDebounce = 0;

// --- Forward Declarations ---
void handleSerialCommands();
void handleButtons();
void startDepassivationProcess(unsigned long duration);
void stopDepassivationProcess(String message);
void measureAndLogTestData();
void measureAndLogLiveData();
void setRgbColor(int r, int g, int b);
void updateLed();
void setState(State newState);

// =================================================================
//  SETUP
// =================================================================
void setup() {
    Serial.begin(115200);
    Serial.println("ESP32 Battery Analyzer Initialized.");

    // Initialize MOSFET and its indicator LED
    pinMode(MOSFET_GATE_PIN, OUTPUT);
    digitalWrite(MOSFET_GATE_PIN, LOW);
    pinMode(MOSFET_LED_PIN, OUTPUT);
    digitalWrite(MOSFET_LED_PIN, LOW);

    // Initialize RGB LED pins
    pinMode(RGB_R_PIN, OUTPUT);
    pinMode(RGB_G_PIN, OUTPUT);
    pinMode(RGB_B_PIN, OUTPUT);

    // Initialize Button pins
    pinMode(BTN_START_PIN, INPUT);
    pinMode(BTN_ABORT_PIN, INPUT);
    pinMode(BTN_MEASURE_PIN, INPUT);

    // Initialize INA219
    if (!ina219.begin()) {
        Serial.println("FATAL: Failed to find INA219 chip. Check wiring.");
        setState(FAILED); // Enter permanent FAILED state
        while (1) { updateLed(); delay(10); } // Loop forever with error signal
    }

    Serial.println("INA219 sensor found. Ready.");
    setState(IDLE);
}

// =================================================================
//  MAIN LOOP
// =================================================================
void loop() {
    handleSerialCommands();
    handleButtons();
    updateLed();

    switch (currentState) {
        case TEST_RUNNING:
            // If the test duration has passed, move to the FINISHING state
            if (millis() - processStartTime >= depassivationDurationMs) {
                setState(FINISHING);
            }
            // Continue taking measurements during the test
            if (millis() - lastMeasurementTime >= measurementIntervalMs) {
                lastMeasurementTime = millis();
                measureAndLogTestData();
            }
            break;
        case FINISHING:
            // Wait 1 extra second with the load on before stopping
            if (millis() - stateChangeTime > 1000) {
                stopDepassivationProcess("Process completed successfully.");
                setState(SUCCESS);
            }
            break;
        case LIVE_VIEW:
            if (millis() - lastMeasurementTime >= measurementIntervalMs) {
                lastMeasurementTime = millis();
                measureAndLogLiveData();
            }
            break;
        case SUCCESS:
        case FAILED:
            // After 3 seconds in SUCCESS/FAILED state, return to IDLE
            if (millis() - stateChangeTime > 3000) {
                setState(IDLE);
            }
            break;
        case IDLE:
            // Do nothing
            break;
    }
}

// =================================================================
//  State Management
// =================================================================
void setState(State newState) {
    if (currentState == newState) return; // Avoid redundant state changes

    currentState = newState;
    stateChangeTime = millis(); // Record time of state change

    // Set initial LED color and hardware state for the new mode
    switch (newState) {
        case IDLE:
            setRgbColor(0, 255, 0); // Green
            digitalWrite(MOSFET_GATE_PIN, LOW);
            digitalWrite(MOSFET_LED_PIN, LOW);
            break;
        case TEST_RUNNING:
        case FINISHING:
            // Blue will be handled by updateLed for pulsing effect
            break;
        case LIVE_VIEW:
            setRgbColor(255, 255, 255); // White
            break;
        case SUCCESS:
            // Flashing Green will be handled by updateLed
            break;
        case FAILED:
            // Flashing Red will be handled by updateLed
            digitalWrite(MOSFET_GATE_PIN, LOW);
            digitalWrite(MOSFET_LED_PIN, LOW);
            break;
    }
}

// =================================================================
//  Core Functions
// =================================================================
void handleSerialCommands() {
    if (Serial.available() > 0) {
        String command = Serial.readStringUntil('\n');
        command.trim();

        if (command.startsWith("START")) {
            int firstComma = command.indexOf(',');
            String durationStr = command.substring(firstComma + 1);
            startDepassivationProcess(durationStr.toInt() * 1000);
        } else if (command.equalsIgnoreCase("ABORT")) {
            if(currentState == TEST_RUNNING) {
                stopDepassivationProcess("Process aborted by user.");
                setState(FAILED);
            }
        } else if (command.startsWith("SET_MODE")) {
            String modeStr = command.substring(command.indexOf(',') + 1);
            if (modeStr.equalsIgnoreCase("LIVE")) {
                setState(LIVE_VIEW);
            } else if (modeStr.equalsIgnoreCase("IDLE")) {
                setState(IDLE);
            }
        } else if (command.startsWith("SET_MOSFET") && currentState == LIVE_VIEW) {
            String stateStr = command.substring(command.indexOf(',') + 1);
            bool is_on = stateStr.toInt() == 1;
            digitalWrite(MOSFET_GATE_PIN, is_on ? HIGH : LOW);
            digitalWrite(MOSFET_LED_PIN, is_on ? HIGH : LOW);
        }
    }
}

void handleButtons() {
    // --- Button 1: Start Test ---
    bool startReading = digitalRead(BTN_START_PIN);
    if (startReading != lastStartState) {
        lastStartDebounce = millis();
    }
    if ((millis() - lastStartDebounce) > DEBOUNCE_DELAY_MS) {
        if (startReading == HIGH && lastStartState == LOW) { // Fire on press
            Serial.println("BTN_PRESS,START");
        }
    }
    lastStartState = startReading;

    // --- Button 2: Abort Test ---
    bool abortReading = digitalRead(BTN_ABORT_PIN);
    if (abortReading != lastAbortState) {
        lastAbortDebounce = millis();
    }
    if ((millis() - lastAbortDebounce) > DEBOUNCE_DELAY_MS) {
        if (abortReading == HIGH && lastAbortState == LOW) { // Fire on press
             Serial.println("BTN_PRESS,ABORT");
        }
    }
    lastAbortState = abortReading;

    // --- Button 3: Measure Mode ---
    bool measureReading = digitalRead(BTN_MEASURE_PIN);
    if (measureReading != lastMeasureState) {
        lastMeasureDebounce = millis();
    }
    if ((millis() - lastMeasureDebounce) > DEBOUNCE_DELAY_MS) {
        if (measureReading == HIGH && lastMeasureState == LOW) { // Fire on press
            Serial.println("BTN_PRESS,MEASURE");
        }
    }
    lastMeasureState = measureReading;
}

void startDepassivationProcess(unsigned long duration) {
    if (currentState == IDLE) {
        Serial.println("PROCESS_START");
        setState(TEST_RUNNING);
        processStartTime = millis();
        lastMeasurementTime = 0; // Ensure first measurement happens immediately
        depassivationDurationMs = duration;
        Serial.println("Starting measurements...");
    }
}

void stopDepassivationProcess(String message) {
    digitalWrite(MOSFET_GATE_PIN, LOW);
    digitalWrite(MOSFET_LED_PIN, LOW);
    Serial.println("Load disconnected.");
    Serial.println("PROCESS_END: " + message);
}

void measureAndLogTestData() {
    // Apply load right before measurement
    digitalWrite(MOSFET_GATE_PIN, HIGH);
    digitalWrite(MOSFET_LED_PIN, HIGH);
    delay(50); // Short delay to stabilize voltage after load is applied

    float busVoltage_V = ina219.getBusVoltage_V();
    float shuntVoltage_mV = ina219.getShuntVoltage_mV();
    float current_mA = ina219.getCurrent_mA();
    float power_mW = ina219.getPower_mW();
    float loadVoltage_V = busVoltage_V + (shuntVoltage_mV / 1000.0);
    float resistance_Ohm = 0;
    if (abs(current_mA) > 0.1) {
        resistance_Ohm = (loadVoltage_V * 1000) / current_mA;
    }

    Serial.print("DATA,");
    Serial.print(millis() - processStartTime);
    Serial.print(",");
    Serial.print(loadVoltage_V, 3);
    Serial.print(",");
    Serial.print(current_mA, 2);
    Serial.print(",");
    Serial.print(power_mW, 2);
    Serial.print(",");
    Serial.println(resistance_Ohm, 2);

    // Turn off load after sending data
    digitalWrite(MOSFET_GATE_PIN, LOW);
    digitalWrite(MOSFET_LED_PIN, LOW);
}

void measureAndLogLiveData() {
    float busVoltage_V = ina219.getBusVoltage_V();
    float current_mA = ina219.getCurrent_mA();
    float power_mW = ina219.getPower_mW();
    float resistance_Ohm = 0;
    // To calculate load voltage, we need shunt voltage.
    float shuntVoltage_mV = ina219.getShuntVoltage_mV();
    float loadVoltage_V = busVoltage_V + (shuntVoltage_mV / 1000.0);

    if (abs(current_mA) > 0.1) { // Avoid division by zero or nonsensical values
        resistance_Ohm = (loadVoltage_V * 1000) / current_mA;
    }

    Serial.print("LIVE_DATA,");
    Serial.print(loadVoltage_V, 3);
    Serial.print(",");
    Serial.print(current_mA, 2);
    Serial.print(",");
    Serial.print(power_mW, 2);
    Serial.print(",");
    Serial.println(resistance_Ohm, 2);
}

// =================================================================
//  LED Control
// =================================================================
void setRgbColor(int r, int g, int b) {
    // ESP32 analogWrite is 8-bit (0-255) by default
    analogWrite(RGB_R_PIN, r);
    analogWrite(RGB_G_PIN, g);
    analogWrite(RGB_B_PIN, b);
}

void updateLed() {
    switch (currentState) {
        case TEST_RUNNING:
        case FINISHING: {
            // Pulsing Blue
            float breath = (sin(millis() / 500.0) + 1.0) / 2.0;
            setRgbColor(0, 0, (int)(breath * 255));
            break;
        }
        case SUCCESS: {
            // Flashing Green
            bool on = (millis() - stateChangeTime) % 500 < 250;
            setRgbColor(0, on ? 255 : 0, 0);
            break;
        }
        case FAILED: {
            // Flashing Red
            bool on = (millis() - stateChangeTime) % 500 < 250;
            setRgbColor(on ? 255 : 0, 0, 0);
            break;
        }
        default:
            // For IDLE, LIVE_VIEW, the color is set once in setState()
            break;
    }
}
