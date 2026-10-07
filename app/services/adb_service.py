import asyncio
import re
from dataclasses import dataclass

from app.core.config import get_settings

settings = get_settings()


@dataclass
class ADBDevice:
    serial: str
    status: str
    model: str | None = None
    manufacturer: str | None = None
    android_version: str | None = None
    sdk_version: str | None = None


class ADBService:
    def __init__(self, adb_path: str = None, timeout: int = None):
        self.adb_path = adb_path or settings.adb_path
        self.timeout = timeout or settings.adb_timeout

    async def _run_adb(self, args: list[str], serial: str = None) -> tuple[int, str, str]:
        cmd = [self.adb_path]
        if serial:
            cmd.extend(["-s", serial])
        cmd.extend(args)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout
            )
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            return -1, "", f"Timeout after {self.timeout}s"
        return proc.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")

    async def list_devices(self) -> list[ADBDevice]:
        code, stdout, stderr = await self._run_adb(["devices", "-l"])
        if code != 0:
            return []
        devices = []
        for line in stdout.strip().split("\n")[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial = parts[0]
            status = parts[1]
            model = None
            manufacturer = None
            for part in parts[2:]:
                if part.startswith("model:"):
                    model = part[6:]
                elif part.startswith("product:") and not manufacturer:
                    manufacturer = part[8:]
            devices.append(ADBDevice(serial=serial, status=status, model=model, manufacturer=manufacturer))
        return devices

    async def get_device_info(self, serial: str) -> dict:
        info = {}
        # Get properties in parallel
        props = [
            ("ro.product.model", "model"),
            ("ro.product.manufacturer", "manufacturer"),
            ("ro.build.version.release", "android_version"),
            ("ro.build.version.sdk", "sdk_version"),
            ("ro.serialno", "serial_number"),
            ("ro.bootloader", "bootloader"),
            ("ro.hardware", "hardware"),
            ("ro.product.cpu.abi", "cpu_abi"),
        ]
        tasks = [self._run_adb(["shell", "getprop", prop], serial) for prop, _ in props]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for (prop, key), result in zip(props, results):
            if isinstance(result, Exception):
                info[key] = None
            else:
                code, stdout, stderr = result
                info[key] = stdout.strip() if code == 0 and stdout.strip() else None

        # Battery
        code, stdout, stderr = await self._run_adb(["shell", "dumpsys", "battery"], serial)
        if code == 0:
            info["battery"] = self._parse_battery(stdout)

        # Storage
        code, stdout, stderr = await self._run_adb(["shell", "df", "/data"], serial)
        if code == 0:
            info["storage"] = self._parse_storage(stdout)

        # IMEI (requires root or specific permission)
        code, stdout, stderr = await self._run_adb(["shell", "service", "call", "iphonesubinfo", "1"], serial)
        if code == 0:
            info["imei"] = self._parse_imei(stdout)

        # Root check
        code, stdout, stderr = await self._run_adb(["shell", "which", "su"], serial)
        info["is_rooted"] = code == 0 and "su" in stdout

        # Encryption
        code, stdout, stderr = await self._run_adb(["shell", "getprop", "ro.crypto.state"], serial)
        info["is_encrypted"] = code == 0 and "encrypted" in stdout.lower()

        return info

    def _parse_battery(self, output: str) -> dict:
        battery = {}
        patterns = {
            "level": r"level: (\d+)",
            "health": r"health: (\d+)",
            "status": r"status: (\d+)",
            "technology": r"technology: (\w+)",
            "temperature": r"temperature: (\d+)",
            "voltage": r"voltage: (\d+)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, output)
            if match:
                battery[key] = int(match.group(1)) if match.group(1).isdigit() else match.group(1)
        health_map = {1: "unknown", 2: "good", 3: "overheat", 4: "dead", 5: "over_voltage", 6: "unspecified", 7: "cold"}
        if "health" in battery and isinstance(battery["health"], int):
            battery["health"] = health_map.get(battery["health"], "unknown")
        status_map = {1: "unknown", 2: "charging", 3: "discharging", 4: "not_charging", 5: "full"}
        if "status" in battery and isinstance(battery["status"], int):
            battery["status"] = status_map.get(battery["status"], "unknown")
        return battery

    def _parse_storage(self, output: str) -> dict:
        lines = output.strip().split("\n")
        if len(lines) < 2:
            return {}
        parts = lines[1].split()
        if len(parts) >= 4:
            return {
                "total_bytes": int(parts[1]) * 1024,
                "used_bytes": int(parts[2]) * 1024,
                "free_bytes": int(parts[3]) * 1024,
            }
        return {}

    def _parse_imei(self, output: str) -> str | None:
        # Parse service call output for IMEI
        match = re.search(r"([0-9a-f]{4}\s+){8}", output)
        if match:
            hex_str = match.group(0).replace(" ", "")
            try:
                imei = bytes.fromhex(hex_str).decode("utf-16-be").strip("\x00")
                if imei.isdigit() and len(imei) >= 14:
                    return imei
            except Exception:
                pass
        return None

    async def run_diagnostic(self, serial: str, diag_type: str) -> dict:
        info = await self.get_device_info(serial)
        result = {"device_info": info}

        if diag_type in ("basic_info", "full"):
            result["basic_info"] = {
                "model": info.get("model"),
                "manufacturer": info.get("manufacturer"),
                "android_version": info.get("android_version"),
                "sdk_version": info.get("sdk_version"),
                "serial_number": info.get("serial_number"),
                "cpu_abi": info.get("cpu_abi"),
                "hardware": info.get("hardware"),
            }

        if diag_type in ("battery", "full"):
            result["battery"] = info.get("battery", {})

        if diag_type in ("storage", "full"):
            result["storage"] = info.get("storage", {})

        if diag_type in ("security", "full"):
            result["security"] = {
                "is_rooted": info.get("is_rooted", False),
                "is_encrypted": info.get("is_encrypted", False),
                "bootloader": info.get("bootloader"),
            }

        if diag_type in ("hardware", "full"):
            result["hardware"] = {
                "cpu_abi": info.get("cpu_abi"),
                "hardware": info.get("hardware"),
            }

        if diag_type in ("software", "full"):
            code, stdout, stderr = await self._run_adb(["shell", "pm", "list", "packages"], serial)
            if code == 0:
                packages = [line.replace("package:", "").strip() for line in stdout.strip().split("\n") if line.strip()]
                result["software"] = {"installed_packages_count": len(packages), "packages": packages[:50]}

        if diag_type in ("network", "full"):
            code, stdout, stderr = await self._run_adb(["shell", "ip", "addr", "show"], serial)
            if code == 0:
                result["network"] = {"interfaces": stdout.strip()}

        if diag_type == "imei_check":
            result["imei"] = info.get("imei")

        return result

    async def backup_device(self, serial: str, backup_path: str) -> bool:
        code, stdout, stderr = await self._run_adb(["backup", "-f", backup_path, "-apk", "-shared", "-all"], serial)
        return code == 0


adb_service = ADBService()
