"""
Hardware interface.
"""

# supress gnuradio.blocks pylance warning
# pyright: reportAttributeAccessIssue=false

import multiprocessing
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import psutil
from gnuradio import blocks, gr

from raifm.config import Config
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


def capture_process(cfg: Config, job: Job) -> None:
    """capture one station per core, start on the common timestamp"""

    p = psutil.Process()
    p.cpu_affinity([job.core])

    src = osmocom_source(cfg, job.device, job.antenna, job.rate_hz)
    head = blocks.head(gr.sizeof_gr_complex, job.samples)
    sink = blocks.file_sink(gr.sizeof_gr_complex, str(job.path_out), False)

    tb = gr.top_block(f"capture_{job.label}")
    tb.connect(src, head, sink)

    sleep_until(job.t_start)
    late = (datetime.now(UTC) - job.t_start).total_seconds() * 1e3
    started = time.monotonic()
    tb.run()

    print(
        f"    [{job.label}] started +{late:.6f} ms, "
        f"{job.samples} samples in {time.monotonic() - started:.1f} s",
        flush=True,
    )


def progress(t_end: datetime, width: int = 30) -> None:
    """draw progress bar until t_end, every station runs the same duration"""

    t_begin = datetime.now(UTC)
    total = (t_end - t_begin).total_seconds()
    while (remaining := (t_end - datetime.now(UTC)).total_seconds()) > 0:
        done = total - remaining
        full = int(width * done / total)
        bar = "#" * full + "." * (width - full)
        print(
            f"\r    [{bar}] {done:5.1f} / {total:.1f} s",
            end="",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(0.2)
    print(
        f"\r    [{'#' * width}] {total:.1f} / {total:.1f} s",
        file=sys.stderr,
        flush=True,
    )


def run_jobs(cfg: Config, jobs: list[Job], t_end: datetime) -> None:
    """mp job run setup, every station armed before the common timestamp"""

    context = multiprocessing.get_context("spawn")
    procs = [
        context.Process(target=capture_process, args=(cfg, job), name=job.label)
        for job in jobs
    ]

    for proc in procs:
        proc.start()

    t_start = jobs[0].t_start.isoformat()
    print(f"raifm: {len(jobs)} hackrf armed, waiting for {t_start}", flush=True)

    sleep_until(jobs[0].t_start)
    print(
        f"raifm: {len(jobs)} gnuradio processes started, "
        f"recording {jobs[0].samples} samples each",
        flush=True,
    )
    progress(t_end)

    for proc in procs:
        proc.join()
    print(f"raifm: {len(jobs)} stations finished", flush=True)
