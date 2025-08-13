## Battery Depassivation Station

### Overview

This project provides a complete hardware and software solution for testing and analyzing the depassivation process of batteries. It consists of two main parts:

1.  **Python GUI**: A user-friendly desktop application built with Tkinter for controlling tests, viewing live data, and managing a history of test results.
2.  **ESP32 Firmware**: Code for an ESP32 microcontroller that controls the hardware (MOSFET, INA219 sensor) to perform the actual test on the battery.

The two components communicate over a serial (USB) connection, creating a robust and easy-to-use testing station.

---

### Features

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

### Project Structure

The workspace is organized into two main folders:

- **`GUI/`**: Contains the Python source code for the desktop application.
- **`Firmware/`**: Contains the C++/Arduino source code for the ESP32, managed by PlatformIO.

---

### Part 1: GUI Setup and Usage

#### Dependencies

The application requires the following Python libraries:

- **`pyserial`**
- **`matplotlib`**

#### Installation

1.  **Navigate to the `GUI/` directory.**
2.  **Install the required libraries using the `requirements.txt` file:**
    ```bash
    pip install -r requirements.txt
    ```

#### Running the Application

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

### Part 2: Firmware Setup and Usage

The firmware is managed using the **PlatformIO IDE** extension in Visual Studio Code.

#### Dependencies

- **Visual Studio Code**
- **The official [PlatformIO IDE extension](https://platformio.org/install/ide?install=vscode) from the VS Code Marketplace.**
- **The hardware libraries (`Adafruit INA219`) are managed automatically by PlatformIO via the `platformio.ini` file.**

#### Setup and Upload

1.  **Open the entire project workspace in VS Code.**
2.  **Open the `Firmware/platformio.ini` file.**
3.  **Change the `upload_port` and `monitor_port` to match the COM port of your ESP32.**
4.  **Use the PlatformIO toolbar icons at the bottom of the VS Code window:**
    - **Click the Build (✓) icon to compile the code.**
    - **Click the Upload (→) icon to flash the firmware to your ESP32. You may need to use the manual boot sequence (hold BOOT, press EN, release BOOT) while PlatformIO is trying to connect.**

---

### Communication Protocol

The GUI and ESP32 communicate using a simple text-based protocol over serial.

- **Commands sent from GUI to Hardware**:
  - `START,<duration_seconds>,<pass_fail_voltage>`: Initiates a new test. (e.g., `START,10,3.2`)
  - `ABORT`: Immediately stops the currently running test.

- **Data sent from Hardware to GUI**:
  - `DATA,<time_ms>,<voltage_V>,<current_mA>`: A single data point reading from the test. (e.g., `DATA,1000,3.650,150.20`)
  - `PROCESS_START`: Acknowledges that the test has begun.
  - `PROCESS_END: [message]`: Signals that the test has finished, with a reason.
  - Any other line is treated as a general log message.

---

### Detailed Code Explanation

#### Part 1: Firmware (`Firmware/Depassivation-Firmware/src/main.cpp`)

O firmware é desenhado para ser eficiente e não-bloqueante, o que significa que pode responder a comandos a qualquer momento, mesmo durante um teste.

- **`setup()` function**:
  - `Serial.begin(115200)`: Inicia a comunicação serial a 115200 bits por segundo. Esta velocidade deve corresponder à configurada na GUI para que a comunicação funcione.
  - `pinMode(...)` & `digitalWrite(...)`: Configura os pinos do MOSFET e do LED como saídas e garante que começam desligados para segurança.
  - `ina219.begin()`: Tenta inicializar a comunicação I2C com o sensor INA219. Se falhar, o `while(1)` com o LED a piscar serve como um código de erro visual crítico, impedindo que o firmware continue a funcionar sem o seu principal sensor.

- **`loop()` function**:
  - Esta função é o coração do programa e corre continuamente. É desenhada para ser "não-bloqueante", ou seja, executa as suas tarefas muito rapidamente sem nunca ficar presa à espera.
  - `handleSerialCommands()`: É chamada em cada ciclo para verificar se chegaram novos comandos da GUI.
  - `if (isProcessRunning)`: Este bloco de código só é executado se um teste estiver ativo.
  - `if (millis() - processStartTime >= depassivationDurationMs)`: Esta é a forma padrão no Arduino de gerir o tempo sem bloquear o código. Compara o tempo atual (`millis()`) com o tempo de início do teste para ver se a duração definida já passou.
  - `if (millis() - lastMeasurementTime >= measurementIntervalMs)`: Um temporizador semelhante verifica se já passou 1 segundo desde a última medição, para manter um intervalo de amostragem constante.

- **`handleSerialCommands()` function**:
  - `if (Serial.available() > 0)`: Apenas tenta ler dados se a porta serial indicar que há algo para ser lido, evitando esperas desnecessárias.
  - `command.indexOf(',')`: Usa funções de manipulação de strings para encontrar as vírgulas no comando `START` e extrair os parâmetros (duração e tensão) enviados pela GUI.

- **`measureAndLogData()` function**:
  - `ina219.get...()`: Pede à biblioteca do sensor para ler os valores mais recentes de tensão e corrente.
  - `loadVoltage_V = busVoltage_V + (shuntVoltage_mV / 1000.0)`: Calcula a tensão real da bateria sob carga, que é a métrica mais importante do teste.
  - `Serial.print(...)`: Constrói a string de dados no formato `DATA,...` e envia-a para a GUI. O `Serial.println()` no final é crucial, pois envia o caractere de nova linha (`\n`) que a GUI usa para saber que a mensagem terminou.

#### Part 2: GUI (Python Files)

A GUI é modular, separando a interface, a gestão de dados e a comunicação em ficheiros distintos para melhor organização.

- **`gui.py` - `DepassivationApp` class**:
  - O `__init__` contém uma decisão de design importante: a variável `self.connection_handler` pode ser uma instância de `SerialHandler` (para hardware real) ou `SimulationHandler`. O resto do código interage com esta variável de forma abstrata, sem precisar de saber se a fonte dos dados é real ou simulada.
  - A função **`handle_serial_data(data)`** é o centro nevrálgico da lógica da GUI. Atua como um despachante central para todas as mensagens recebidas.
    - **Não é chamada diretamente**, mas sim agendada para execução no *thread* principal através de `root.after()`. Isto é fundamental para a estabilidade de uma aplicação com *threads* em Tkinter.
    - Ao receber `PROCESS_END`, a função orquestra os passos finais: calcular o resultado (Passa/Falha), atualizar a base de dados através do `data_handler`, e reativar os botões da interface.
    - Ao receber `DATA`, atualiza múltiplos elementos da UI: as etiquetas com as métricas ao vivo, o gráfico Matplotlib, e envia o ponto de dados para ser guardado na base de dados.

- **`data_handler.py` - `DataHandler` class**:
  - Esta classe segue o "Princípio da Responsabilidade Única": a sua única função é gerir a persistência dos dados (leitura e escrita na base de dados e em ficheiros de configuração).
  - O `@contextmanager _get_db_cursor` é uma técnica robusta em Python para garantir que as conexões à base de dados são sempre fechadas corretamente, mesmo em caso de erro, prevenindo ficheiros de base de dados corrompidos.
  - A utilização de `ON DELETE CASCADE` na criação da tabela SQL é uma funcionalidade poderosa. Simplifica o código, pois ao apagar um teste da tabela `tests`, o SQLite encarrega-se de apagar automaticamente todos os pontos de dados correspondentes, mantendo a consistência da base de dados.

- **`serial_handler.py` - `SerialHandler` class**:
  - O uso de `threading.Thread` é essencial. A leitura da porta serial pode ser uma operação de bloqueio (ficar à espera de dados). Ao colocá-la num *thread* separado, a interface gráfica (`GUI`) permanece sempre responsiva aos cliques do utilizador.
  - O `daemon=True` na criação do *thread* é uma salvaguarda importante. Garante que, se o utilizador fechar a janela principal, este *thread* secundário será terminado automaticamente, impedindo que o processo Python fique "preso" em segundo plano.
  - O bloco `try...except serial.SerialException` dentro do loop de leitura torna a aplicação robusta. Se o cabo USB for desconectado durante a operação, em vez de a aplicação falhar, a exceção é capturada e a GUI é notificada para lidar com a desconexão de forma controlada.

- **`simulation_handler.py` - `SimulationHandler` class**:
  - Esta classe imita a "interface" da `SerialHandler` (tem os mesmos métodos `start` e `abort`). Isto permite que a `gui.py` a utilize sem qualquer alteração no seu próprio código.
  - A função `_run_simulation` gera dados que parecem realistas (uma queda de tensão gradual com um pouco de ruído aleatório) para fornecer uma experiência de utilizador credível, mesmo sem hardware.
