"""
CLI setup.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raifm import __version__
from raifm.config import DEFAULT_CONFIG, HACKRFCFG, Config, load_config, station_name
from raifm.usb import BUDGET_MBPS, UsbPlan, usb2_buses
from raifm.utils import (
    convert,
    gen_test_iq,
    hackrf_clock,
    hackrf_serials,
    hackrf_state,
    hash_gen,
    hostname,
    log_path,
    save_metadata,
    setup_logging,
    sha256,
    write_sha256,
)

if TYPE_CHECKING:
    from raifm.run import Job


def obs_jobs(
    cfg: Config, run_dir: Path, found: list[tuple[int, str]], run_log: Path
) -> list[Job]:
    """gnuradio jobs for the connected hackrf"""

    from raifm.run import Job

    ncores = os.cpu_count() or 1

    return [
        Job(
            label=station_name(idx),
            serial=serial,
            device=f"hackrf={serial},bias={cfg.bias}",
            antenna=f"ant_{serial}",
            rate_hz=cfg.samp_rate,
            samples=cfg.n_samples,
            path_out=run_dir / f"{station_name(idx)}.bin",
            core=(idx - 1) % ncores,
            t_start=cfg.t_start,
            log=run_log,
        )
        for idx, serial in found
    ]


def test_jobs(cfg: Config, ref: Path, t_start: datetime, run_log: Path) -> list[Job]:
    """gnuradio jobs for test"""

    from raifm.run import Job

    ncores = os.cpu_count() or 1
    device = (
        f"file={ref.as_posix()},"
        f"freq={cfg.central_freq:.0f},"
        f"rate={cfg.test_samp_rate:.0f}"
    )

    return [
        Job(
            label=station_name(idx),
            serial="file",
            device=device,
            antenna="file",
            rate_hz=cfg.test_samp_rate,
            samples=cfg.test_n_samples,
            path_out=cfg.test_dir / f"{station_name(idx)}.bin",
            core=(idx - 1) % ncores,
            t_start=t_start,
            log=run_log,
        )
        for idx in range(1, cfg.n_stations + 1)
    ]


def connected_boards(cfg: Config) -> list[tuple[int, str]]:
    """config position and serial of every connected hackrf"""

    connected = set(hackrf_serials())
    return [
        (idx, serial)
        for idx, serial in enumerate(cfg.serial_num, 1)
        if serial in connected
    ]


def cmd_obs(cfg: Config) -> None:
    """start per station gnuradio obs at t_start"""

    run_log = log_path()
    print(f"raifm: log {run_log}", flush=True)
    log = setup_logging(run_log)
    cmd_check(cfg, log)

    found = connected_boards(cfg)
    if not found:
        log.info("no hackrf connected")
        return None

    seen = {idx for idx, _ in found}
    missing = [
        station_name(idx)
        for idx in range(1, len(cfg.serial_num) + 1)
        if idx not in seen
    ]
    run_dir = cfg.obs_dir / cfg.t_start.strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True)

    if missing:
        print(f"raifm: not connected: {', '.join(missing)}", flush=True)
        log.info("not connected: %s", ", ".join(missing))
    print(
        f"raifm: {cfg.samp_rate / 1e6:.1f} Msps, {cfg.t_total:.1f} s -> {run_dir}",
        flush=True,
    )
    log.info("obs %.1f Msps %.1f s -> %s", cfg.samp_rate / 1e6, cfg.t_total, run_dir)

    jobs = obs_jobs(cfg, run_dir, found, run_log)
    from raifm.run import run_jobs

    run_jobs(cfg, jobs)

    checksums = hash_gen([job.path_out for job in jobs])
    for job in jobs:
        size = job.path_out.stat().st_size
        write_sha256(job.path_out, checksums[job.path_out])
        print(f"    {job.label:12s} {size / 1e9:.2f} GB  {checksums[job.path_out]}")
        log.info("%s %.2f GB %s", job.label, size / 1e9, checksums[job.path_out])

    meta = run_dir / f"metadata.{hostname()}.json"
    save_metadata(
        meta,
        "obs",
        cfg,
        [
            {
                "name": job.label,
                "serial": job.serial,
                "file": job.path_out.name,
                "samples": job.samples,
                "bytes": job.path_out.stat().st_size,
                "sha256": checksums[job.path_out],
            }
            for job in jobs
        ],
    )
    print(f"raifm: wrote {meta}")
    log.info("wrote %s", meta)

    print("raifm: hackrf_debug -S readouts")
    for idx, serial in found:
        state = hackrf_state(serial)
        print(f"    {station_name(idx)} {serial}")
        if failed := state.get("hackrf_open() failed"):
            print(f"        {failed}")
            log.info("%s %s %s", station_name(idx), serial, failed)
            continue
        log.info(
            "%s %s M0 %s M4 %s shortfall %s",
            station_name(idx),
            serial,
            state.get("M0 count", "?"),
            state.get("M4 count", "?"),
            state.get("Number of shortfalls", "?"),
        )
        print(f"        M0 {state.get('M0 count', '?')}")
        print(f"        M4 {state.get('M4 count', '?')}")
        print(
            f"        shortfall {state.get('Number of shortfalls', '?')} "
            f"(longest {state.get('Longest shortfall', '?')}, "
            f"limit {state.get('Shortfall limit', '?')})"
        )


def cmd_test(cfg: Config) -> None:
    """test osmocom source saving and compare hash"""

    samples = cfg.test_n_samples
    cfg.test_dir.mkdir(parents=True, exist_ok=True)

    iq = cfg.test_dir / HACKRFCFG.test_iq
    ref = cfg.test_dir / HACKRFCFG.test_c64

    run_log = log_path()
    print(f"raifm: log {run_log}", flush=True)
    log = setup_logging(run_log)
    log.info(
        "test %d stations at %.1f Msps %.0f s, %.1e samples",
        cfg.n_stations,
        cfg.test_samp_rate / 1e6,
        cfg.test_t_total,
        samples,
    )

    t_start = datetime.now(UTC) + timedelta(seconds=3)
    print(
        f"raifm: test {cfg.n_stations} stations at {cfg.test_samp_rate / 1e6:.1f} Msps:"
        f" {cfg.test_t_total:.0f} s with {samples:.1e} samples",
        flush=True,
    )

    gen_test_iq(iq, samples)
    convert(iq, ref)

    jobs = test_jobs(cfg, ref, t_start, run_log)
    from raifm.run import run_jobs

    run_jobs(cfg, jobs)

    reference = sha256(ref)
    checksums = hash_gen([job.path_out for job in jobs])

    bad = [job.label for job in jobs if checksums[job.path_out] != reference]
    print(f"raifm: reference {ref.name} {reference}")
    log.info("reference %s %s", ref.name, reference)

    for job in jobs:
        mark = "PASS" if checksums[job.path_out] == reference else "FAIL"
        write_sha256(job.path_out, checksums[job.path_out])
        print(f"    {mark} {job.label:12s} {checksums[job.path_out]}")
        log.info("%s %s %s", mark, job.label, checksums[job.path_out])

    save_metadata(
        cfg.test_dir / f"metadata.{hostname()}.json",
        "test",
        cfg,
        [
            {
                "name": job.label,
                "file": job.path_out.name,
                "samples": job.samples,
                "bytes": job.path_out.stat().st_size,
                "sha256": checksums[job.path_out],
                "match": checksums[job.path_out] == reference,
            }
            for job in jobs
        ],
        {"reference": {"file": ref.name, "sha256": reference}},
    )

    if bad:
        print(
            f"raifm: {len(bad)} of {cfg.n_stations} stations differ: {', '.join(bad)}"
        )
    else:
        print("raifm: test station readout byte identical to reference")


def cmd_check(cfg: Config, logger: logging.Logger | None = None) -> None:
    """check clkin status on connected hackrf"""

    found = connected_boards(cfg)
    if not found:
        print(f"raifm: 0/{len(cfg.serial_num)} configured hackrf connected")
        if logger:
            logger.info("0/%d configured hackrf connected", len(cfg.serial_num))
        return None

    names = ", ".join(station_name(idx) for idx, _ in found)
    print(
        f"raifm: {len(found)}/{len(cfg.serial_num)} configured hackrf connected:"
        f" {names}"
    )
    print("raifm: hackrf_clock -i readouts")
    if logger:
        logger.info("%d/%d connected: %s", len(found), len(cfg.serial_num), names)
    for idx, serial in found:
        clock = hackrf_clock(serial).get("CLKIN status", "?")
        print(f"    {station_name(idx):12s} {serial} {clock}")
        if logger:
            logger.info("%s %s %s", station_name(idx), serial, clock)


def cmd_purge(cfg: Config, goahead: bool) -> None:
    """purge test bin"""

    targets = [
        path for path in sorted(cfg.test_dir.rglob("ant*.bin*")) if path.is_file()
    ]
    if not targets:
        print("raifm: nothing to purge")
        return None
    if not goahead:
        print("raifm: dry run, pass --yes to purge")
        return None

    total = sum(path.stat().st_size for path in targets)
    print(f"raifm: purging {len(targets)} files, total {total / 1e9:.1f} GB")

    for path in targets:
        print(f"    {path}  {path.stat().st_size / 1e9:.2f} GB")
    for path in targets:
        path.unlink()

    print(f"raifm: unlinked {len(targets)} files, {total / 1e9:.1f} GB")


def cmd_usb(cfg: Config, n_ports: int, n_hackrf: int) -> None:
    """print the usb 2.0 data rate budget of n_hackrf boards over n_ports"""

    plan = UsbPlan(n_hackrf, n_ports, cfg.samp_rate)
    buses = usb2_buses()
    print("raifm: checking data rate requirements")
    print(f"    {sys.platform} platform with {buses} usb 2.0 bus")
    print(
        f"    {n_hackrf} hackrf, {cfg.samp_rate / 1e6:.1f} Msps,"
        f" {n_ports} port, {HACKRFCFG.size_i8} B per sample"
    )
    print(
        f"    per hackrf {plan.per_board_mbps:.1f} Mbps,"
        f" total {plan.total_mbps:.1f} Mbps"
    )

    for label, n_bus in (("1 bus", 1), (f"{n_ports} bus", n_ports)):
        load = plan.bus_mbps(n_bus)
        verdict = (
            f"ok, {BUDGET_MBPS - load:.1f} Mbps spare"
            if load <= BUDGET_MBPS
            else f"over by {load - BUDGET_MBPS:.1f} Mbps"
        )
        print(f"    {label:10s} {load:8.1f} Mbps of {BUDGET_MBPS:.1f} -> {verdict}")

    print(f"INFO: max {plan.max_rate_hz(1) / 1e6:.2f} Msps per usb 2.0 bus")
    print(f"SET : {plan.max_rate_hz(n_ports) / 1e6:.2f} Msps on {n_ports} usb 2.0 bus")


# TODO
# def cmd_trim(cfg: Config) -> None:
#     """cut the samples that a station lost out of every station"""

#     runs = sorted(path for path in cfg.obs_dir.glob("*") if path.is_dir())
#     if not runs:
#         print(f"raifm: no run under {cfg.obs_dir}")
#         return None

#     run_dir = runs[-1]
#     paths = {path.stem: path for path in sorted(run_dir.glob("antenna_*.bin"))}
#     if len(paths) < 3:
#         print(
#             f"raifm: {len(paths)} stations, "
#             "3 or more stations are needed to judge which one lost samples"
#         )
#         return None

#     steps, unlocked = find_steps(paths)
#     print(
#         f"raifm: {run_dir} {len(paths)} stations, "
#         f"{len(steps)} steps, {unlocked} windows without a peak"
#     )
#     for step in steps:
#         print(f"    at sample {step.at}: {step.station} lost {step.lost}")
#     if not steps:
#         return None

#     for path in trim(paths, steps, cfg.obs_dir.parent / "trim").values():
#         print(f"    {path} {path.stat().st_size / 1e9:.2f} GB")


def build_parser() -> argparse.ArgumentParser:
    """cli arg parser"""

    parser = argparse.ArgumentParser(
        prog="raifm",
        description="RAIFM CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    mode = parser.add_mutually_exclusive_group()

    mode.add_argument(
        "-o",
        "--obs",
        action="store_true",
        help="obs run with osmocom src gnuradio ops",
    )
    mode.add_argument(
        "-t",
        "--test",
        action="store_true",
        help="test osmocom src save and compare hash",
    )
    mode.add_argument(
        "-p",
        "--purge",
        action="store_true",
        help="purge test bin files",
    )
    # TODO
    # mode.add_argument(
    #     "-m",
    #     "--trim",
    #     action="store_true",
    #     help="cut the samples a station lost out of the latest obs run",
    # )
    mode.add_argument(
        "-c",
        "--check",
        action="store_true",
        help="check the clkin on the connected boards",
    )
    mode.add_argument(
        "-u",
        "--usb",
        action="store_true",
        help="usb 2.0 data rate budget of the boards",
    )

    parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG, help="configuration file"
    )
    parser.add_argument("--start", metavar="ISO8601", help="override [obs] t_start")
    parser.add_argument("--duration", type=float, metavar="S", help="override t_total")
    parser.add_argument("--rate", type=float, metavar="HZ", help="override samp_rate")
    parser.add_argument(
        "-y", "--yes", action="store_true", help="confirm test file purge"
    )
    parser.add_argument(
        "--ports", type=int, default=1, metavar="N", help="usb ports in use"
    )
    parser.add_argument(
        "--buffer",
        type=int,
        metavar="N",
        help="gnuradio buffer (Minoutbuf), default is 0",
    )
    parser.add_argument(
        "--hackrf",
        type=int,
        metavar="N",
        help="hackrf boards in use, defaults to [hackrf] n_stations",
    )

    parser.add_argument(
        "-v", "--version", action="version", version=f"raifm {__version__}"
    )

    return parser


def cli_overrides(cfg: Config, args: argparse.Namespace) -> Config:
    """cli args overrides"""

    cli_cfg: dict[str, Any] = {}

    if args.buffer is not None:
        cli_cfg["buffer"] = args.buffer

    if args.test:
        if args.duration is not None:
            cli_cfg["test_t_total"] = args.duration
        if args.rate is not None:
            cli_cfg["test_samp_rate"] = args.rate
    else:
        if args.start is not None:
            cli_cfg["t_start"] = datetime.fromisoformat(args.start)
        if args.duration is not None:
            cli_cfg["t_total"] = args.duration
        if args.rate is not None:
            cli_cfg["samp_rate"] = args.rate

    overrides = replace(cfg, **cli_cfg) if cli_cfg else cfg

    return overrides


def main(argv: list[str] | None = None) -> None:
    """
    main cli

    -o
        obs runs with osmocom_source from actual hackrf signal
    -t
        runs osmocom_source data processing test with fake c64 hackrf readouts
    -p
        purge test data .bin files
    -c
        check the clock input of the connected boards
    """

    args = build_parser().parse_args(argv)
    cfg = cli_overrides(load_config(args.config), args)

    if args.purge:
        cmd_purge(cfg, args.yes)
    # TODO
    # elif args.trim:
    #     cmd_trim(cfg)
    elif args.check:
        cmd_check(cfg)
    elif args.usb:
        cmd_usb(cfg, args.ports, args.hackrf or cfg.n_stations)
    elif args.test:
        cmd_test(cfg)
    else:
        cmd_obs(cfg)


if __name__ == "__main__":
    main()
