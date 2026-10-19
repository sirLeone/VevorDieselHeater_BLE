# Bruciatore_BLE Controller

This project provides a Python script for interacting with the VEVOR diesel air heater, All-in-One model, via Bluetooth Low Energy (BLE). The code has been developed through Bluetooth data sniffing between the heater and the manufacturer's "AirHeaterBLE" app.

## Description

The VEVOR diesel air heater is designed for use in cars, campers, trucks, and RVs. This script allows you to control the heater using a BLE-compatible device, such as a Raspberry Pi or a computer with a Bluetooth adapter.

## Features

- Bluetooth Low Energy connection with the VEVOR Diesel Air Heater device.
- Sending specific commands to control various heater functionalities.
- Monitoring and displaying information received from the heater, such as temperature, ignition status, power, and more.

## Requirements

- Python 3.x
- Arch Linux: sudo pacman -S base-devel cmake libevdev libconfig systemd-libs glib2
- Debian/Ubuntu: sudo apt install build-essential cmake pkg-config libevdev-dev libudev-dev libconfig++-dev libglib2.0-dev
- Bluepy Library: `pip install bluepy`

## Usage

1. Ensure your Bluetooth device is enabled.
2. Run the Python script: `python Vevor_AirHeater_BLE.py <MAC> [--passkey 1234]`
3. The script requests the heater status every second; type commands to control the heater.

## Supported Commands

Available Commands:
- `P0`: Turn heater OFF.
- `P1`: Turn heater ON.
- `M1` / `M2`: Mode LEVEL / AUTOMATIC (temperature).
- `T8-T36`: Set temperature (8-36°C).
- `L1-L10`: Set power level (1-10).
- `+` / `-`: Level or temperature up / down (depending on the current mode).
- `S`: Refresh status.
- `C<cmd>,<value>`: Send a raw command, e.g. `C3,1` (see [PROTOCOL.md](PROTOCOL.md)).
- `exit`: Exit program.

## Protocol

The full protocol, taken from the AirHeaterBLE app and compared with other projects, is described in
[PROTOCOL.md](PROTOCOL.md). This project supports heaters that answer with the `AA 55` header (20 byte frame);
`AA 66` heaters use the same frame and are supported as well.
  
## Product Information

For more details about the VEVOR Diesel Air Heater, visit the [VEVOR product page](https://www.vevor.it/riscaldatore-aria-diesel-c_10321/vevor-riscaldatore-d-aria-diesel-all-in-one-per-auto-camper-camion-rv-12v-5kw-temperatura-regolabile-8-36-controllo-bluetooth-riscaldatore-da-parcheggio-per-auto-consumo-di-carburante-0-16-0-52l-h-p_010971160616).

## Important Note

This project is created for educational purposes and automation of the VEVOR diesel air heater. Use the software at your own risk. The author is not responsible for any damage resulting from the improper use of the code.
For a more comprehensive understanding of the utilized protocol, refer to the detailed explanation available at [this link](https://github.com/iotmaestro/vevor-heater-ble).

## Using ESP32 Board with Home Assistant
This is (ESP32-VevorBLE.yaml) the file to insert into an [esp32](https://upload.wikimedia.org/wikipedia/commons/3/33/Espressif_ESP-WROOM-32_Wi-Fi_%26_Bluetooth_Module.jpg) bluethoot card. to be able to use it with home assistant and on wifi

Set the `heater_mac` (and `heater_passkey` if you changed the password in the app) substitutions and add
these entries to your `secrets.yaml`:

```yaml
wifi_ssid: "..."
wifi_password: "..."
api_encryption_key: "..."   # 32 byte base64 key, see https://esphome.io/components/api
ota_password: "..."
```

Entities:

| Type          | Entities |
|---------------|----------|
| Controls      | Heater Power, Heater Mode (Level / Automatic), Heater LEVEL (1-10), Heater Temperature (8-36°C) |
| Buttons       | Level Up / Down, Temperature Up / Down, Refresh Status, Restart ESP |
| Sensors       | Room Temperature, Heating Temperature, Battery Voltage, Altitude, Power Status (set level / temperature), Fan Speed (current level), Error Code, Error (text), Glow Plug Status (running step), Heater Status, Heater Mode |
| Diagnostics   | Heater Connected, Heater BLE RSSI, WiFi Signal, Controller Error Code, Running Step, Protocol, Last Frame, Uptime |

The controls follow the heater state, also when it is changed on the heater panel or in the app.
The `send_command` Home Assistant action sends any command from [PROTOCOL.md](PROTOCOL.md), e.g.
`esphome.<device_name>_send_command` with `cmd: 3`, `value: 1`.

## Thanks

Thanks to:
- [jsnyder](https://github.com/jsnyder)
