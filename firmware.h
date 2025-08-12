#include <Wire.h>
#include <Adafruit_INA219.h>

// --- Pin Definitions ---
const int MOSFET_GATE_PIN = 23; // GPIO to control the MOSFET Gate

// --- Depassivation Settings ---
const unsigned long DEPASSIVATION_DURATION_MS = 10000; // 10 seconds

// --- Global Objects ---
Adafruit_INA219 ina219;

// --- State Variables ---
bool isProcessRunning = false;
unsigned long processStartTime = 0;

void setup() {
  // Start Serial communication
  Serial.begin(115200);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB
  }
  Serial.println("ESP32 Battery Depassivation Station");
  Serial.println("Send 'START' to begin the process.");
  Serial.println("Send 'ABORT' to stop the process.");

  // Initialize MOSFET pin as an output and set it to LOW
  pinMode(MOSFET_GATE_PIN, OUTPUT);
  digitalWrite(MOSFET_GATE_PIN, LOW);

  // Initialize the INA219 sensor
  if (!ina219.begin()) {
    Serial.println("Failed to find INA219 chip. Check connections.");
    while (1) {
      delay(10);
    }
  }
  Serial.println("INA219 sensor found.");
}

void loop() {
  // Check for incoming serial commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    if (command.equalsIgnoreCase("START") && !isProcessRunning) {
      startDepassivation();
    } else if (command.equalsIgnoreCase("ABORT") && isProcessRunning) {
      abortDepassivation("Process aborted by user.");
    }
  }

  // If the process is running, perform measurements
  if (isProcessRunning) {
    // Check if the duration has elapsed
    if (millis() - processStartTime >= DEPASSIVATION_DURATION_MS) {
      abortDepassivation("Process completed successfully.");
    } else {
      measureAndLogData();
      delay(1000); // Wait 1 second between measurements
    }
  }
}

/**
 * @brief Starts the depassivation process.
 */
void startDepassivation() {
  Serial.println("PROCESS_START");
  isProcessRunning = true;
  processStartTime = millis();
  
  // Turn on the MOSFET to connect the load
  digitalWrite(MOSFET_GATE_PIN, HIGH);
  Serial.println("Load connected. Starting measurements...");
}

/**
 * @brief Stops the depassivation process and prints a final message.
 * @param message The reason for stopping the process.
 */
void abortDepassivation(String message) {
  // Turn off the MOSFET
  digitalWrite(MOSFET_GATE_PIN, LOW);
  isProcessRunning = false;
  Serial.println("Load disconnected.");
  Serial.println("PROCESS_END: " + message);
  Serial.println("Send 'START' to begin a new process.");
}

/**
 * @brief Reads data from the INA219 sensor and logs it to the Serial port.
 */
void measureAndLogData() {
  float shuntVoltage = ina219.getShuntVoltage_mV();
  float busVoltage = ina219.getBusVoltage_V();
  float current_mA = ina219.getCurrent_mA();
  float loadVoltage = busVoltage + (shuntVoltage / 1000);

  // Format data as a CSV string for easy parsing
  String dataLog = "DATA,";
  dataLog += String(millis() - processStartTime) + ",";
  dataLog += String(loadVoltage) + ",";
  dataLog += String(current_mA);
  
  Serial.println(dataLog);
}
