"""
Hardware interface.
"""

# supress gnuradio.blocks pylance warning
# pyright: reportAttributeAccessIssue=false

import multiprocessing
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import psutil
from gnuradio import blocks, gr

from raifm.config import HACKRFCFG, Config
from raifm.utils import osmocom_source, sleep_until


@dataclass(frozen=True)
class Job:
    """set single gnuradio job per hackrf on single core"""

    label: str
    device: str
    antenna: str
    rate_hz: float
    samples: int
    path_out: Path
    core: int
    t_start: datetime
    meta: bool


def capture_process(cfg: Config, job: Job) -> None:
    """capture one station per core, start on the common timestamp"""

    p = psutil.Process()
    p.cpu_affinity([job.core])

    src = osmocom_source(cfg, job.device, job.antenna, job.rate_hz)
    head = blocks.head(gr.sizeof_gr_complex, job.samples)
    if job.meta:
        sink = blocks.file_meta_sink(
            gr.sizeof_gr_complex,
            str(job.path_out),
            samp_rate=job.rate_hz,
            complex=True,
            max_segment_size=HACKRFCFG.meta_segment,
        )
    else:
        sink = blocks.file_sink(gr.sizeof_gr_complex, str(job.path_out), False)

    tb = gr.top_block(f"capture_{job.label}")
    tb.connect(src, head, sink)

    sleep_until(job.t_start)
    late = (datetime.now(UTC) - job.t_start).total_seconds() * 1e3
    started = time.monotonic()
    tb.run()

    print(
        f"[{job.label}] start +{late:.3f} ms "
        f"{job.samples} samples in {time.monotonic() - started:.1f} s",
        flush=True,
    )


def run_jobs(cfg: Config, jobs: list[Job]) -> None:
    """mp job run setup"""
    context = multiprocessing.get_context("spawn")
    procs = [
        context.Process(target=capture_process, args=(cfg, job), name=job.label)
        for job in jobs
    ]

    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join()
