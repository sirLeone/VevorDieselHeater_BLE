# VEVOR / AirHeaterBLE protocol

Source: the decompiled AirHeaterBLE app v1.08 (`com.clj.airheater`, `assets/apps/__UNI__1471D01/www/app-service.js`),
cross-checked with [iotmaestro/vevor-heater-ble](https://github.com/iotmaestro/vevor-heater-ble),
[bderleta/vevor-ble-bridge](https://github.com/bderleta/vevor-ble-bridge) and
[warehog/esphome-diesel-heater-ble](https://github.com/warehog/esphome-diesel-heater-ble).

- Service `0000ffe0-0000-1000-8000-00805f9b34fb`, characteristic `0000ffe1-0000-1000-8000-00805f9b34fb`
  (write commands, subscribe to notifications).
- The heater answers every command with a status notification.

## Heater variants

The app recognises the variant from the first two bytes of the status frame:

| Header    | App name | Frame                    | Supported here |
|-----------|----------|--------------------------|----------------|
| `AA 55`   | md 1     | 20 bytes, plain          | yes (tested)   |
| `AA 66`   | md 3     | 20 bytes, plain          | yes (same layout, error in byte 17) |
| `AA 88`   | md 2     | encrypted / CRC16        | no             |
| XOR "password" encrypted `AA 55` / `AA 66` | newer app versions | 48 bytes | no |

Only md 2 and the encrypted variants have the extended settings (timer, tank volume, pump type,
temperature offset, ...). For `AA 55` / `AA 66` heaters the app offers only: on/off, mode, level,
temperature and password.

## Command frame (8 bytes)

| Byte | Value                                              |
|------|----------------------------------------------------|
| 0    | `0xAA`                                             |
| 1    | `0x55`                                             |
| 2    | passkey / 100 (`0x0C` = 12 for the default `1234`) |
| 3    | passkey % 100 (`0x22` = 34 for the default `1234`) |
| 4    | command                                            |
| 5    | value, low byte                                    |
| 6    | value, high byte                                   |
| 7    | (byte2 + byte3 + byte4 + byte5 + byte6) % 256      |

### Commands

| Cmd | Value                                    | Description                               | Heaters |
|-----|------------------------------------------|-------------------------------------------|---------|
| 1   | 0                                        | Status request                            | all     |
| 2   | 1 = Level, 2 = Automatic (temperature)   | Running mode                              | all     |
| 3   | 0 = off, 1 = on                          | Power                                     | all     |
| 4   | 1–10 (Level mode) / 8–36 °C (Automatic)  | Set level / target temperature            | all     |
| 10  | minutes since midnight                   | Set heater clock                          | md 2    |
| 11  | minutes since midnight                   | Timer start time                          | md 2    |
| 12  | minutes                                  | Timer run time                            | md 2    |
| 13  | 0 / 1                                    | Timer on/off                              | md 2    |
| 14  | 0–5                                      | Display language                          | md 2    |
| 15  | signed offset °C                         | Room temperature correction               | md 2    |
| 16  | litres (steps of 5)                      | Tank volume                               | md 2    |
| 17  | pump type index                          | Oil pump type                             | md 2    |
| 18  | 0 / 1                                    | Automatic start & stop (thermostat mode)  | md 2    |

Commands 10–18 are listed for completeness. They can be tried on any heater through the ESPHome
`send_command` action or the `C<cmd>,<value>` command of the Python script, but `AA 55` / `AA 66`
heaters do not report these settings back.

## Status frame (`AA 55` / `AA 66`, 20 bytes, little endian)

| Byte  | Description                                                                       |
|-------|-----------------------------------------------------------------------------------|
| 0–1   | Header `AA 55` or `AA 66`                                                         |
| 2     | Command this frame answers                                                        |
| 3     | Running state: 0 = off, 1 = on                                                    |
| 4     | Error code (`AA 55`)                                                              |
| 5     | Running step: 0 warmup, 1 self test, 2 ignition, 3 heating, 4 shutting down       |
| 6–7   | Altitude (m)                                                                      |
| 8     | Mode: 1 = Level, 2 = Automatic                                                    |
| 9     | Level 1–10 (Level mode) or target temperature 8–36 °C (Automatic mode)            |
| 10    | Current level − 1 (Automatic mode)                                                |
| 11–12 | Supply voltage × 10                                                               |
| 13–14 | Heat exchanger temperature (°C, signed)                                           |
| 15–16 | Room temperature (°C, signed)                                                     |
| 17    | Error code shown on the panel (`AA 55`) / error code (`AA 66`)                    |
| 18    | Reserved                                                                          |
| 19    | Checksum                                                                          |

### Error codes

There are two numbering schemes. The app shows byte 4 with the *controller* table for `AA 55` heaters and
byte 17 with the *panel* table for `AA 66` heaters. On `AA 55` heaters byte 17 holds the code shown on the
heater panel (E-xx), which follows the panel table.

The English texts in the app are poor translations, so the descriptions below are taken from the Chinese
texts of the app. Panel codes 2 and 7 are not named in the app; they come from the heater manuals.

| Code | Controller table (`AA 55`, byte 4)                  | Panel table (`AA 55` byte 17, `AA 66` byte 17)  |
|------|-----------------------------------------------------|-------------------------------------------------|
| 0    | No fault (无故障)                                   | No fault (无故障)                               |
| 1    | Startup failure (启动失败)                          | Supply voltage abnormal (电压异常)              |
| 2    | Flame-out, lack of fuel (缺油熄火)                  | Overvoltage (manuals)                           |
| 3    | Supply voltage abnormal (电压异常)                  | Glow plug fault (点火塞异常)                    |
| 4    | Air outlet sensor fault (出风传感异常)              | Fuel pump fault (油泵异常)                      |
| 5    | Air inlet sensor fault (进风传感异常)               | Overheat protection (过热保护)                  |
| 6    | Fuel pump fault (油泵异常)                          | Fan fault (风机异常)                            |
| 7    | Fan fault (风机异常)                                | Communication fault (manuals)                   |
| 8    | Glow plug fault (点火塞异常)                        | Flame-out, lack of fuel (缺油熄火)              |
| 9    | Overheat protection (高温保护)                      | Overheat sensor fault (过热保护传感器)          |
| 10   | Heat exchanger temperature sensor fault (炉温传感器异常) | Repeated startup failure (二次启动失败)     |

While an error is active the app does not allow mode, level or temperature changes (power on/off is
still allowed). The ESPHome configuration and the Python script do the same.
