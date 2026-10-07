import asyncio
import plistlib
from dataclasses import dataclass

from app.core.config import get_settings

settings = get_settings()


@dataclass
class IOSDevice:
    udid: str
    name: str | None = None
    model: str | None = None
    ios_version: str | None = None


class IOSService:
    def __init__(
        self,
        idevice_id_path: str = None,
        idevice_info_path: str = None,
        idevice_backup_path: str = None,
        timeout: int = None,
    ):
        self.idevice_id_path = idevice_id_path or settings.idevice_id_path
        self.idevice_info_path = idevice_info_path or settings.idevice_info_path
        self.idevice_backup_path = idevice_backup_path or settings.idevice_backup_path
        self.timeout = timeout or settings.ios_timeout

    async def _run_cmd(self, cmd: list[str]) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            return -1, "", f"Timeout after {self.timeout}s"
        return proc.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")

    async def list_devices(self) -> list[IOSDevice]:
        code, stdout, stderr = await self._run_cmd([self.idevice_id_path, "-l"])
        if code != 0:
            return []
        devices = []
        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split()
            udid = parts[0]
            name = " ".join(parts[1:]) if len(parts) > 1 else None
            info = await self.get_device_info(udid)
            devices.append(
                IOSDevice(
                    udid=udid,
                    name=name,
                    model=info.get("ProductType"),
                    ios_version=info.get("ProductVersion"),
                )
            )
        return devices

    async def get_device_info(self, udid: str) -> dict:
        code, stdout, stderr = await self._run_cmd([self.idevice_info_path, "-u", udid, "-x"])
        if code != 0:
            return {}
        try:
            plist_data = stdout.encode("utf-8")
            info = plistlib.loads(plist_data)
            return info
        except Exception:
            return {}

    async def get_battery_info(self, udid: str) -> dict:
        info = await self.get_device_info(udid)
        battery = {}
        if "BatteryCurrentCapacity" in info:
            battery["level"] = info["BatteryCurrentCapacity"]
        if "BatteryHealth" in info:
            battery["health"] = info["BatteryHealth"]
        if "BatteryIsCharging" in info:
            battery["is_charging"] = info["BatteryIsCharging"]
        return battery

    async def get_storage_info(self, udid: str) -> dict:
        info = await self.get_device_info(udid)
        storage = {}
        if "TotalDiskCapacity" in info:
            storage["total_bytes"] = info["TotalDiskCapacity"]
        if "TotalDataCapacity" in info:
            storage["data_bytes"] = info["TotalDataCapacity"]
        return storage

    async def run_diagnostic(self, udid: str, diag_type: str) -> dict:
        info = await self.get_device_info(udid)
        result = {"device_info": info}

        if diag_type in ("basic_info", "full"):
            result["basic_info"] = {
                "model": info.get("ProductType"),
                "name": info.get("DeviceName"),
                "ios_version": info.get("ProductVersion"),
                "build_version": info.get("BuildVersion"),
                "serial_number": info.get("SerialNumber"),
                "imei": info.get("InternationalMobileEquipmentIdentity"),
                "meid": info.get("MEID"),
                "iccid": info.get("ICCID"),
                "cpu_architecture": info.get("CPUArchitecture"),
                "hardware_model": info.get("HardwareModel"),
            }

        if diag_type in ("battery", "full"):
            result["battery"] = await self.get_battery_info(udid)

        if diag_type in ("storage", "full"):
            result["storage"] = await self.get_storage_info(udid)

        if diag_type in ("security", "full"):
            result["security"] = {
                "passcode_enabled": info.get("PasscodeEnabled"),
                "activation_lock": info.get("ActivationLockEnabled"),
                "mdm_enabled": info.get("MDMEnabled"),
                "supervised": info.get("Supervised"),
            }

        if diag_type in ("hardware", "full"):
            result["hardware"] = {
                "cpu_architecture": info.get("CPUArchitecture"),
                "hardware_model": info.get("HardwareModel"),
                "bluetooth_address": info.get("BluetoothAddress"),
                "wifi_address": info.get("WiFiAddress"),
            }

        if diag_type in ("software", "full"):
            result["software"] = {
                "installed_apps_count": len(info.get("InstalledApplications", [])),
                "available_disk_space": info.get("AvailableDiskSpace"),
            }

        if diag_type in ("network", "full"):
            result["network"] = {
                "wifi_address": info.get("WiFiAddress"),
                "bluetooth_address": info.get("BluetoothAddress"),
                "cellular_technology": info.get("CellularTechnology"),
            }

        if diag_type == "imei_check":
            result["imei"] = info.get("InternationalMobileEquipmentIdentity")
            result["meid"] = info.get("MEID")

        if diag_type == "backup":
            result["backup_supported"] = True

        return result

    async def backup_device(self, udid: str, backup_path: str) -> bool:
        code, stdout, stderr = await self._run_cmd(
            [self.idevice_backup_path, "backup", "-u", udid, backup_path]
        )
        return code == 0


ios_service = IOSService()
