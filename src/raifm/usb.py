"""
Hackrf USB 2.0 datarate estimator utils
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from raifm.config import HACKRFCFG

LINK_MBPS = 480.0
OVERHEAD = 0.80
BUDGET_MBPS = LINK_MBPS * OVERHEAD


@dataclass(frozen=True)
class UsbPlan:
    """usb 2.0 wire rate of n_hackrf over n_ports buses"""

    n_hackrf: int
    n_ports: int
    rate_hz: int

    @property
    def per_board_mbps(self) -> float:
        """rate of one hackrf"""
        return self.rate_hz * HACKRFCFG.size_i8 * 8 / 1e6

    @property
    def total_mbps(self) -> float:
        """rate of all hackrf at the same time"""
        return self.n_hackrf * self.per_board_mbps

    def bus_mbps(self, n_ports: int) -> float:
        """worst usb bus load when hackrf are spread over n_ports buses"""
        boards = -(-self.n_hackrf // max(n_ports, 1))
        return boards * self.per_board_mbps

    def max_rate_hz(self, n_ports: int) -> float:
        """hackrf sample rate/ total data rate of n_ports buses"""
        boards = -(-self.n_hackrf // max(n_ports, 1))
        return BUDGET_MBPS * 1e6 / (boards * HACKRFCFG.size_i8 * 8)


def usb2_buses() -> int | None:
    """get num of usb 2.0 host bus on local machine"""
    if sys.platform.startswith("linux"):
        root = Path("/sys/bus/usb/devices")
        return sum(
            1
            for path in root.glob("usb*")
            if (path / "speed").exists()
            and (path / "speed").read_text().strip() == "480"
        )

    if sys.platform == "darwin":
        res = subprocess.run(
            ["system_profiler", "SPUSBDataType", "-json"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(res.stdout)
        buses = data.get("SPUSBDataType", [])
        return sum(
            1
            for bus in buses
            if "USB 2.0 Bus" in bus.get("_name", "")
            or bus.get("host_controller", "").endswith("EHCI")
        )

    if sys.platform == "win32":
        ps_cmd = (
            "(Get-PnpDevice -Class USB -Status OK | Where-Object { "
            "$_.FriendlyName -like '*USB 2.0 Root Hub*' -or "
            "$_.FriendlyName -like '*USB Root Hub (USB 3.0)*' "
            "}).Count"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            check=True,
        )
        output = res.stdout.strip()
        return int(output) if output.isdigit() else 0

    else:
        return None
