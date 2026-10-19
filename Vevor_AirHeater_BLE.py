import argparse
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, List
from bluepy.btle import Peripheral, DefaultDelegate
import threading
import time
import os
import sys
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout

# Enumerator definitions
class HeaterMode(IntEnum):
    LEVEL = 0x01
    AUTOMATIC = 0x02

class HeaterPower(IntEnum):
    OFF = 0x00
    ON = 0x01

class HeaterCommand(IntEnum):
    STATUS = 0x01
    MODE = 0x02
    POWER = 0x03
    LEVEL_OR_TEMP = 0x04

RUNNING_STEPS = {
    0x00: "Warmup",
    0x01: "Self test running",
    0x02: "Ignition",
    0x03: "Heating",
    0x04: "Shutting down",
}

# Error texts from the AirHeaterBLE app ("AA 55" heaters, error in byte 4)
ERRORS_AA55 = (
    "No fault", "Startup failure", "Lack of fuel", "Supply voltage overrun",
    "Outlet sensor fault", "Inlet sensor fault", "Pulse pump fault", "Fan fault",
    "Ignition unit fault", "Overheating", "Overheat sensor fault",
)

# Error texts from the AirHeaterBLE app ("AA 66" heaters, error in byte 17)
ERRORS_AA66 = (
    "No fault", "Supply voltage overrun", "Unknown", "Ignition unit fault",
    "Pulse pump fault", "Overheating", "Fan fault", "Unknown", "Lack of fuel",
    "Overheat sensor fault", "Startup failure",
)

def to_int16(value: int) -> int:
    """Convert an unsigned 16-bit value to signed"""
    return value - 0x10000 if value & 0x8000 else value

@dataclass
class HeaterStatus:
    power: bool
    mode: HeaterMode
    temperature: int
    target_temperature_level: int
    level: int
    running_state: int
    altitude: int
    voltage_battery: float
    temp_heating: int
    temp_room: int
    error_code: int
    display_error_code: int = 0
    protocol: str = "AA 55"

    @property
    def running_state_description(self) -> str:
        if not self.power and self.running_state == 0:
            return "Standby"
        return RUNNING_STEPS.get(self.running_state, "Unknown state")

    @property
    def error_description(self) -> str:
        errors = ERRORS_AA66 if self.protocol == "AA 66" else ERRORS_AA55
        return errors[self.error_code] if self.error_code < len(errors) else "Unknown error"

    @staticmethod
    def from_frame(data: bytes) -> Optional["HeaterStatus"]:
        """Parse a status frame (protocols "AA 55" and "AA 66", see PROTOCOL.md)"""
        if len(data) < 17 or data[0] != 0xAA or data[1] not in (0x55, 0x66):
            return None
        aa66 = data[1] == 0x66
        display_error = data[17] if len(data) > 17 else 0
        mode = data[8]
        if mode == HeaterMode.LEVEL:
            level = data[9]
        else:
            level = data[10] + 1
        return HeaterStatus(
            power=bool(data[3]),
            mode=HeaterMode.AUTOMATIC if mode == HeaterMode.AUTOMATIC else HeaterMode.LEVEL,
            temperature=to_int16(data[15] | (data[16] << 8)),
            target_temperature_level=data[9],
            level=level,
            running_state=data[5],
            altitude=data[6] | (data[7] << 8),
            voltage_battery=(data[11] | (data[12] << 8)) / 10,
            temp_heating=to_int16(data[13] | (data[14] << 8)),
            temp_room=to_int16(data[15] | (data[16] << 8)),
            error_code=display_error if aa66 else data[4],
            display_error_code=display_error,
            protocol="AA 66" if aa66 else "AA 55",
        )

    def __str__(self) -> str:
        # Ottieni la descrizione testuale o un valore di default se non è valido
        running_state_description = self.running_state_description

        return (
            f"Power: {'ON' if self.power else 'OFF'}\n"
            f"Mode: {'AUTOMATIC' if self.mode == HeaterMode.AUTOMATIC else 'LEVEL'}\n"
            f"Current Temperature: {self.temp_room}°C\n"
            f"Target: {self.target_temperature_level}{'°C' if self.mode == HeaterMode.AUTOMATIC else ' (level)'}\n"
            f"Heating Temperature: {self.temp_heating}°C\n"
            f"Battery: {self.voltage_battery:.1f}V\n"
            f"Altitude: {self.altitude}m\n"
            f"Running state: {running_state_description}\n"
            f"Current level: {self.level}\n"
            f"Status Code: {self.error_code} ({self.error_description})"
        )

class VEVORHeater:
    HEADER = bytearray([0xAA, 0x55])
    SERVICE_UUID = "0000FFE0-0000-1000-8000-00805F9B34FB"
    CHAR_UUID = "0000FFE1-0000-1000-8000-00805F9B34FB"

    class NotificationDelegate(DefaultDelegate):
        def __init__(self, heater, console: Console):
            super().__init__()
            self.heater = heater
            self.console = console
            self.last_update = None

        def handleNotification(self, cHandle, data):
            """Handle BLE device notifications"""
            try:
                status = HeaterStatus.from_frame(data)
                if status:
                    self.heater.status = status
                    self.display_status(status)
                else:
                    self.console.print(f"[red]Unsupported frame: {data.hex(' ')}[/red]")

            except Exception as e:
                self.console.print(f"[red]Error processing notification: {e}[/red]")
        #####
        def display_status(self, status: HeaterStatus):
            """Display formatted status using Rich"""
            current_time = time.time()
            if self.last_update and current_time - self.last_update < 1:
                return
            
            self.last_update = current_time
            
            # Ottieni la descrizione del running state
            running_state_description = status.running_state_description
            
            os.system('cls' if os.name == 'nt' else 'clear')
            
            layout = Layout()
            layout.split_column(
                Layout(name="status"),
                Layout(name="commands")
            )
            
            # Create status table with header as first row
            status_table = Table(show_header=False, box=None)
            status_table.add_row(
                f"[bold blue]VEVOR Heater Control - {datetime.now().strftime('%H:%M:%S')}[/bold blue]"
            )
            status_table.add_row("Power", "[green]ON[/green]" if status.power else "[red]OFF[/red]")
            status_table.add_row("Mode", "[yellow]AUTOMATIC[/yellow]" if status.mode == HeaterMode.AUTOMATIC else "[yellow]LEVEL[/yellow]")
            status_table.add_row("Running State", f"[green]{running_state_description}[/green]")
            status_table.add_row("Room Temperature", f"[cyan]{status.temp_room}°C[/cyan]")
            status_table.add_row("Target", f"[green]{status.target_temperature_level}{'°C' if status.mode == HeaterMode.AUTOMATIC else ' (level)'}[/green]")
            status_table.add_row("Heating Temperature", f"[red]{status.temp_heating}°C[/red]")
            status_table.add_row("Current Level", f"[green]{status.level}[/green]")
            status_table.add_row("Battery", f"[magenta]{status.voltage_battery:.1f}V[/magenta]")
            status_table.add_row("Altitude", f"[white]{status.altitude}m[/white]")
            error_color = "green" if status.error_code == 0 else "red"
            status_table.add_row("Error", f"[{error_color}]{status.error_code} - {status.error_description}[/{error_color}]")
            status_table.add_row("Protocol", f"[white]{status.protocol}[/white]")
            
            commands = """
[bold green]Available Commands:[/bold green]
[white]P0[/white] - Turn heater OFF
[white]P1[/white] - Turn heater ON
[white]M1[/white] / [white]M2[/white] - Mode LEVEL / AUTOMATIC
[white]T8-T36[/white] - Set temperature (8-36°C)
[white]L1-L10[/white] - Set power level (1-10)
[white]+[/white] / [white]-[/white] - Level or temperature up / down
[white]S[/white] - Refresh status
[white]C<cmd>,<value>[/white] - Send raw command (e.g. C3,1)
[white]exit[/white] - Exit program

Enter command: """
            
            layout["status"].update(Panel(status_table, title="Status"))
            layout["commands"].update(Panel(commands, title="Commands"))
            
            self.console.print(layout)


    def __init__(self, mac_address: str, passkey: int = 1234):
        if not 0 <= passkey <= 9999:
            raise ValueError("Passkey must be between 0 and 9999")
        self.mac_address = mac_address
        self.passkey = passkey
        self.status: Optional[HeaterStatus] = None
        self.lock = threading.Lock()
        self.peripheral: Optional[Peripheral] = None
        self.logger = logging.getLogger("VEVORHeater")
        self.console = Console()
        logging.basicConfig(level=logging.INFO)

    def connect(self):
        """Connect to BLE device"""
        try:
            self.peripheral = Peripheral(self.mac_address, "public")
            self.peripheral.setDelegate(self.NotificationDelegate(self, self.console))
            self.logger.info(f"Connected to {self.mac_address}")
        except Exception as e:
            self.logger.error(f"Failed to connect: {e}")
            raise

    def disconnect(self):
        """Disconnect from device"""
        if self.peripheral:
            try:
                self.peripheral.disconnect()
                self.peripheral = None
                self.logger.info("Disconnected")
            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")

    def calculate_checksum(self, data: bytearray) -> int:
        """Calculate checksum"""
        return sum(data[2:]) % 256

    def create_command(self, command_type: int, value: int) -> bytearray:
        """Create command with checksum"""
        data = bytearray([
            *self.HEADER,
            self.passkey // 100,  # Passkey, two most significant digits (12 for 1234)
            self.passkey % 100,   # Passkey, two least significant digits (34 for 1234)
            command_type,
            value & 0xFF,         # Value, low byte
            (value >> 8) & 0xFF,  # Value, high byte
            0x00   # Checksum placeholder
        ])
        data[-1] = self.calculate_checksum(data)
        return data

    def send_command(self, command: bytearray):
        """Send command to BLE device and read response"""
        if not self.peripheral:
            raise ConnectionError("Device not connected")

        with self.lock:
            try:
                service = self.peripheral.getServiceByUUID(self.SERVICE_UUID)
                char = service.getCharacteristics(self.CHAR_UUID)[0]

                char.write(command, withResponse=True)

                # The heater answers every command with a status notification
                return self.peripheral.waitForNotifications(1.0)
            except Exception as e:
                self.logger.error(f"Error sending command: {e}")
                return None

    def request_status(self):
        self.send_command(self.create_command(HeaterCommand.STATUS, 0))

    def set_mode(self, mode: HeaterMode):
        cmd = self.create_command(HeaterCommand.MODE, mode)
        self.send_command(cmd)

    def set_power(self, power: bool):
        value = HeaterPower.ON if power else HeaterPower.OFF
        cmd = self.create_command(HeaterCommand.POWER, value)
        self.send_command(cmd)

    def set_level(self, level: int):
        if not 1 <= level <= 10:
            raise ValueError("Level must be between 1 and 10")
        if not self.status or self.status.mode != HeaterMode.LEVEL:
            self.set_mode(HeaterMode.LEVEL)
        cmd = self.create_command(HeaterCommand.LEVEL_OR_TEMP, level)
        self.send_command(cmd)

    def set_temperature(self, temp: int):
        if not 8 <= temp <= 36:
            raise ValueError("Temperature must be between 8°C and 36°C")
        if not self.status or self.status.mode != HeaterMode.AUTOMATIC:
            self.set_mode(HeaterMode.AUTOMATIC)
        cmd = self.create_command(HeaterCommand.LEVEL_OR_TEMP, temp)
        self.send_command(cmd)

    def step(self, delta: int):
        """Change level (LEVEL mode) or temperature (AUTOMATIC mode) by delta"""
        if not self.status:
            raise ConnectionError("Heater status not received yet")
        if self.status.mode == HeaterMode.AUTOMATIC:
            self.set_temperature(max(8, min(36, self.status.target_temperature_level + delta)))
        else:
            self.set_level(max(1, min(10, self.status.target_temperature_level + delta)))

    def send_raw(self, command_type: int, value: int):
        """Send any command (see PROTOCOL.md)"""
        if not 0 <= command_type <= 0xFF or not 0 <= value <= 0xFFFF:
            raise ValueError("Command must be 0-255 and value 0-65535")
        self.send_command(self.create_command(command_type, value))

def communication_thread(heater: VEVORHeater, stop_event: threading.Event):
    """Thread function for sending and receiving data"""
    while not stop_event.is_set():
        try:
            heater.request_status()
        except Exception as e:
            heater.console.print(f"[red]Communication error: {e}[/red]")
        time.sleep(1)

def main():
    parser = argparse.ArgumentParser(description="VEVOR diesel air heater BLE controller")
    parser.add_argument("mac", nargs="?", default="21:47:08:1a:b1:1e", help="Heater BLE MAC address")
    parser.add_argument("--passkey", type=int, default=1234, help="Heater password (default 1234)")
    args = parser.parse_args()

    console = Console()
    heater = VEVORHeater(args.mac, args.passkey)
    stop_event = threading.Event()  # Initialize stop_event at the start
    thread = None
    
    try:
        console.print("[yellow]Connecting to heater...[/yellow]")
        heater.connect()
        console.print("[green]Connected successfully![/green]")
        
        thread = threading.Thread(target=communication_thread, args=(heater, stop_event))
        thread.start()

        while True:
            cmd = input().lower()

            if cmd == "exit":
                console.print("[yellow]Shutting down...[/yellow]")
                stop_event.set()
                break
            elif cmd in ["p0", "p1"]:
                try:
                    heater.set_power(True if cmd == "p1" else False)
                    console.print(f"[green]Power {'ON' if cmd == 'p1' else 'OFF'}[/green]")
                except Exception as e:
                    console.print(f"[red]Error setting power: {e}[/red]")
            elif cmd in ["m1", "m2"]:
                heater.set_mode(HeaterMode.LEVEL if cmd == "m1" else HeaterMode.AUTOMATIC)
                console.print(f"[green]Mode {'LEVEL' if cmd == 'm1' else 'AUTOMATIC'}[/green]")
            elif cmd in ["+", "-"]:
                try:
                    heater.step(1 if cmd == "+" else -1)
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
            elif cmd == "s":
                heater.request_status()
            elif cmd.startswith("c"):
                try:
                    command_type, value = (int(v, 0) for v in cmd[1:].split(","))
                    heater.send_raw(command_type, value)
                    console.print(f"[green]Command {command_type} sent with value {value}[/green]")
                except ValueError as e:
                    console.print(f"[red]Invalid raw command: {e}[/red]")
            elif cmd.startswith("t"):
                try:
                    temp = int(cmd[1:])
                    if 8 <= temp <= 36:
                        heater.set_temperature(temp)
                        console.print(f"[green]Temperature set to {temp}°C[/green]")
                    else:
                        console.print("[red]Temperature must be between 8°C and 36°C[/red]")
                except ValueError:
                    console.print("[red]Invalid temperature format[/red]")
            elif cmd.startswith("l"):
                try:
                    level = int(cmd[1:])
                    if 1 <= level <= 10:
                        heater.set_level(level)
                        console.print(f"[green]Power level set to {level}[/green]")
                    else:
                        console.print("[red]Level must be between 1 and 10[/red]")
                except ValueError:
                    console.print("[red]Invalid level format[/red]")
            else:
                console.print("[red]Invalid command[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
    finally:
        console.print("[yellow]Disconnecting...[/yellow]")
        stop_event.set()
        if thread:
            thread.join()
        heater.disconnect()
        console.print("[green]Disconnected successfully[/green]")

if __name__ == "__main__":
    main()
