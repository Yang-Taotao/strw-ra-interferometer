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

from raifm.config import Config
from raifm.utils import osmocom_source, setup_logging, sleep_until


@dataclass(frozen=True)
class Job:
    """set single gnuradio job per hackrf on single core"""

    label: str
    serial: str
    device: str
    antenna: str
    rate_hz: int
    samples: int
    path_out: Path
    core: int
    t_start: datetime
    log: Path


def capture_process(cfg: Config, job: Job) -> None:
    """capture one station per core, start on the common timestamp"""

    from gnuradio import blocks, gr

    sys.stderr = job.log.open("a", encoding="utf-8")
    log = setup_logging(job.log)

    p = psutil.Process()
    p.cpu_affinity([job.core])

    src = osmocom_source(cfg, job.device, job.antenna, job.rate_hz)
    head = blocks.head(gr.sizeof_gr_complex, job.samples)
    sink = blocks.file_sink(gr.sizeof_gr_complex, str(job.path_out), False)

    tb = gr.top_block(f"capture_{job.label}")
    tb.connect(src, head, sink)

    log.info("%s armed, waiting for %s", job.label, job.t_start.isoformat())
    sleep_until(job.t_start)
    late = (datetime.now(UTC) - job.t_start).total_seconds() * 1e6
    started = time.monotonic()
    log.info("%s gnuradio started +%.6f ms", job.label, late)
    tb.run()
    log.info(
        "%s done %d samples in %.6f s",
        job.label,
        job.samples,
        time.monotonic() - started,
    )

    print(
        f"    [{job.label}] started +{late:.6f} ms, "
        f"{job.samples} samples in {time.monotonic() - started:.1f} s",
        flush=True,
    )


def progress(total: float, width: int = 40) -> None:
    """draw progress bar for total seconds, every station runs the same duration"""

    if total <= 0:
        return

    t_begin = datetime.now(UTC)
    while (done := (datetime.now(UTC) - t_begin).total_seconds()) < total:
        full = int(width * done / total)
        bar = "#" * full + "." * (width - full)
        print(
            f"\r    [{bar}] {done:5.1f} / {total:.1f} s",
            end="",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(0.1)
    print(
        f"\r    [{'#' * width}] {total:.1f} / {total:.1f}",
        file=sys.stderr,
        flush=True,
    )


def run_jobs(cfg: Config, jobs: list[Job]) -> None:
    """mp job run setup, every station armed before the common timestamp"""

    context = multiprocessing.get_context("spawn")
    procs = [
        context.Process(target=capture_process, args=(cfg, job), name=job.label)
        for job in jobs
    ]

    for proc in procs:
        proc.start()

    t_start = jobs[0].t_start.isoformat()
    late = (datetime.now(UTC) - jobs[0].t_start).total_seconds()
    if late > 0:
        print(
            f"raifm: start time was {late:.1f} s ago, "
            "stations start as soon as they arm",
            flush=True,
        )
    print(f"raifm: {len(jobs)} hackrf armed, waiting for {t_start}", flush=True)
    log = setup_logging(jobs[0].log)
    log.info("%d stations armed, waiting for %s", len(jobs), t_start)

    # a station dying before the start writes no data: 
    # kill every station and crash right away
    while datetime.now(UTC) < jobs[0].t_start:
        dead = [proc for proc in procs if proc.exitcode]
        if dead:
            for proc in dead:
                print(
                    f"raifm: {proc.name} exited {proc.exitcode} at"
                    " startup, no data written",
                    flush=True,
                )
            log.error(
                "%s exited at startup, no data written, aborting run",
                ", ".join(proc.name for proc in dead),
            )
            print("raifm: aborting all stations", flush=True)
            for proc in procs:
                proc.kill()
            raise SystemExit(1)
        time.sleep(0.2)
    print(
        f"raifm: {len(jobs)} gnuradio processes started, "
        f"recording {jobs[0].samples} samples each",
        flush=True,
    )
    log.info("%d gnuradio processes started", len(jobs))
    progress(jobs[0].samples / jobs[0].rate_hz)

    for proc in procs:
        proc.join()
        if proc.exitcode:
            log.error("%s exited %s", proc.name, proc.exitcode)
        else:
            log.info("%s exited 0", proc.name)

    failed = [proc.name for proc in procs if proc.exitcode]
    if failed:
        print(
            f"raifm: {len(failed)} of {len(jobs)} stations failed:"
            f" {', '.join(failed)}",
            flush=True,
        )
        raise SystemExit(1)

    log.info("%d stations finished", len(jobs))
    print(f"raifm: {len(jobs)} stations finished", flush=True)
