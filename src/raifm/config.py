"""
Configs.
"""

import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_CONFIG = Path("config.toml")


@dataclass(frozen=True)
class HackrfConfig:
    """build hackrf hardware cfg"""

    size_c64: int = 8  # 8 bytes per c64 data sample
    size_i8: int = 2  # 2 bytes per int8 data sample
    test_iq: str = "test_iq.bin"  # test hackrf cfg I/Q file
    test_c64: str = "test_c64.bin"  # test gnuradio processed c64
    gen_chunk: int = 1000000
    meta_segment: int = 1000000  # samples per file_meta_sink segment
    test_seed: int = 42


HACKRFCFG = HackrfConfig()


@dataclass(frozen=True)
class Config:
    """build from config.toml cfg"""

    n_stations: int
    serial_num: tuple[str, ...]
    t_start: datetime
    t_total: float
    samp_rate: float
    central_freq: float
    gain_rf: int
    gain_if: int
    gain_bb: int
    n_chan: int
    bias: int
    obs_dir: Path
    test_dir: Path
    test_t_total: float
    test_samp_rate: float

    @property
    def n_samples(self) -> int:
        """get total samp per station"""
        return round(self.samp_rate * self.t_total)

    @property
    def test_n_samples(self) -> int:
        """get total samp per station in test case"""
        return round(self.test_samp_rate * self.test_t_total)


def station_name(idx: int) -> str:
    """gen station label"""
    return f"antenna_{idx:02d}"


def load_config(path: Path = DEFAULT_CONFIG) -> Config:
    """parse config.toml"""

    cfg = tomllib.loads(path.read_text(encoding="utf-8"))
    return Config(
        n_stations=cfg["hackrf"]["n_stations"],
        serial_num=tuple(cfg["hackrf"]["serial_num"]),
        t_start=datetime.fromisoformat(cfg["obs"]["t_start"]),
        t_total=cfg["obs"]["t_total"],
        samp_rate=cfg["obs"]["samp_rate"],
        central_freq=cfg["obs"]["central_freq"],
        gain_rf=cfg["gain"]["rf"],
        gain_if=cfg["gain"]["if"],
        gain_bb=cfg["gain"]["bb"],
        n_chan=cfg["obs"]["n_chan"],
        bias=cfg["hackrf"]["bias"],
        obs_dir=Path(cfg["data"]["obs"]),
        test_dir=Path(cfg["data"]["test"]),
        test_t_total=cfg["test"]["t_total"],
        test_samp_rate=cfg["test"]["samp_rate"],
    )
