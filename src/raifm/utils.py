"""
Helper utils.
"""

# supress gnuradio.blocks pylance warning
# pyright: reportAttributeAccessIssue=false

import hashlib
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import osmosdr
from gnuradio import blocks, gr

from raifm.config import HACKRFCFG, Config


def sha256(path: Path) -> str:
    """get file sha256 hash"""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def hash_gen(paths: list[Path]) -> dict[Path, str]:
    """get all sha256 hash for file in list"""
    return {path: sha256(path) for path in paths}


def hackrf_state(serial: str) -> dict[str, str]:
    """get M0 state and byte count of one hackrf (hackrf_debug -S)"""
    out = subprocess.run(
        ["hackrf_debug", "-S", "-d", serial],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    pairs = (line.split(":", 1) for line in out.splitlines() if ":" in line)
    return {key.strip(): value.strip() for key, value in pairs}


def gen_test_iq(path: Path, samples: int) -> None:
    """gen fake hackrf raw I/Q int8 data"""
    rng = np.random.default_rng(HACKRFCFG.test_seed)
    remaining = samples
    with path.open("wb") as handle:
        while remaining:
            chunk = min(HACKRFCFG.gen_chunk, remaining)
            noise = rng.normal(0.0, 20.0, size=chunk * HACKRFCFG.size_i8)
            handle.write(noise.clip(-128.0, 127.0).astype(np.int8).tobytes())
            remaining -= chunk


def convert(path_in: Path, path_out: Path) -> None:
    """cast mock hackrf int8 to c64 via gnuradio"""
    tb = gr.top_block("i8_to_c64")

    src = blocks.file_source(gr.sizeof_char, str(path_in), False)

    widen = blocks.char_to_float()
    split = blocks.stream_to_streams(gr.sizeof_float, 2)
    pack = blocks.float_to_complex(1)
    scale = blocks.multiply_const_cc(2**-7)

    sink = blocks.file_sink(gr.sizeof_gr_complex, str(path_out), False)

    tb.connect((src, 0), (widen, 0))
    tb.connect((widen, 0), (split, 0))

    tb.connect((split, 0), (pack, 0))
    tb.connect((split, 1), (pack, 1))

    tb.connect((pack, 0), (scale, 0))
    tb.connect((scale, 0), (sink, 0))

    tb.run()


def osmocom_source(
    cfg: Config,
    device: str,
    antenna: str,
    rate_hz: float,
) -> osmosdr.source:
    """gnuradio osmocom src block"""
    src = osmosdr.source(device)

    src.set_sample_rate(rate_hz)
    src.set_center_freq(cfg.central_freq)
    src.set_antenna(antenna)

    for chan in range(cfg.n_chan):
        src.set_gain(cfg.gain_rf, "RF", chan)
        src.set_gain(cfg.gain_if, "IF", chan)
        src.set_gain(cfg.gain_bb, "BB", chan)

    return src


def sleep_until(t_start: datetime) -> None:
    """sleep until starting UTC timestamp"""
    while (remaining := (t_start - datetime.now(UTC)).total_seconds()) > 0:
        time.sleep(max(0.0, remaining - 0.000001))  # 1 micro sec
