# Battery Analyzer - Wiring Guide

This document provides a comprehensive, pin-by-pin guide for assembling the hardware for the Battery Analyzer project. It is broken down into two main circuits for clarity: the low-power control circuit and the high-power load circuit.

## Component List

*   ESP32 DevKitC V4 (or similar)
*   INA219 Current Sensor Module
*   IRFZ44N N-Channel MOSFET
*   Common Cathode RGB LED (5mm)
*   Standard LED (e.g., 5mm Red, for MOSFET status)
*   Push Buttons (x3)
*   10k Ohm Resistors (x4)
*   220 Ohm Resistors (x4) - *One for each LED color and one for the MOSFET status LED*
*   High-Power Load Resistor (e.g., 20 Ohm, 10W)
*   Battery Holder
*   Solderless Breadboard & Jumper Wires

---

## 1. Low-Power Control Circuit

This circuit includes all the components that are powered and controlled directly by the ESP32.

### A. Power Distribution

Connect the ESP32's main power pins to the breadboard's power rails.

*   `ESP32 VIN` → Breadboard **Positive (+)** power rail.
*   `ESP32 GND` → Breadboard **Ground (-)** power rail.

### B. INA219 Sensor (I2C)

The INA219 sensor communicates with the ESP32 over the I2C protocol.

*   `INA219 VCC` → `ESP32 3V3` pin.
*   `INA219 GND` → Breadboard **Ground (-)** rail.
*   `INA219 SCL` → `ESP32 GPIO 22`
*   `INA219 SDA` → `ESP32 GPIO 21`

### C. MOSFET Control & Status LED

The MOSFET is controlled by a GPIO pin. A pulldown resistor ensures it stays off by default. A new status LED provides visual feedback for when the load is active.

*   `IRFZ44N Gate` (left pin) → `ESP32 GPIO 13`.
*   `IRFZ44N Gate` (left pin) → One leg of a **10k Ohm resistor**. The other leg of this resistor connects to the Breadboard **Ground (-)** rail. This is a crucial pulldown resistor.
*   **MOSFET Status LED**:
    *   `ESP32 GPIO 14` → One leg of a **220 Ohm resistor**.
    *   The other leg of the resistor → Anode (long leg) of the standard LED.
    *   Cathode (short leg) of the LED → Breadboard **Ground (-)** rail.

### D. RGB Status LED (Common Cathode)

The RGB LED provides rich status information. Each color pin requires its own current-limiting resistor.

*   `LED Red` pin → One leg of a **220 Ohm resistor**. The other leg → `ESP32 GPIO 25`.
*   `LED Green` pin → One leg of a **220 Ohm resistor**. The other leg → `ESP32 GPIO 26`.
*   `LED Blue` pin → One leg of a **220 Ohm resistor**. The other leg → `ESP32 GPIO 27`.
*   `LED Common Cathode` (longest pin) → Breadboard **Ground (-)** rail.

### E. Push Buttons

Each button is connected to power and a GPIO pin, with a pulldown resistor to prevent the pin from "floating".

*   **Button 1 (Start Test):** `ESP32 GPIO 32`
*   **Button 2 (Abort Test):** `ESP32 GPIO 33`
*   **Button 3 (Toggle Measure Mode):** `ESP32 GPIO 34`

For **each** button, wire it as follows:
1.  One leg → Breadboard **Positive (+)** rail.
2.  Opposite leg → The corresponding **ESP32 GPIO pin** (e.g., GPIO 32).
3.  Connect this *same leg* (the one going to the GPIO pin) to one leg of a **10k Ohm resistor**.
4.  The other leg of the 10k Ohm resistor → Breadboard **Ground (-)** rail.

---

## 2. High-Power Load Circuit

This is the path the battery current flows through when the MOSFET is active. **Use thicker gauge wires for these connections if possible.**

1.  **Battery Positive (+)** terminal → `INA219 VIN+` terminal screw.
2.  `INA219 VIN-` terminal screw → One leg of the **High-Power Load Resistor**.
3.  The other leg of the **High-Power Load Resistor** → `IRFZ44N Drain` pin (center pin).
4.  `IRFZ44N Source` pin (right pin) → **Battery Negative (-)** terminal.
5.  Also connect the `IRFZ44N Source` pin (right pin) → Breadboard **Ground (-)** rail. This creates a common ground for the entire circuit, which is essential for it to work correctly.
