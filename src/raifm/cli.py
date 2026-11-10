"""
CLI setup.
"""

import argparse
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from raifm import __version__
from raifm.config import DEFAULT_CONFIG, HACKRFCFG, Config, load_config, station_name
from raifm.run import Job, run_jobs

# TODO
# from raifm.trim import find_steps, trim
from raifm.usb import BUDGET_MBPS, UsbPlan, usb2_buses
from raifm.utils import convert, gen_test_iq, hash_gen, sha256


def obs_jobs(cfg: Config, run_dir: Path, meta: bool) -> list[Job]:
    """gnuradio jobs for obs"""

    ncores = os.cpu_count() or 1

    return [
        Job(
            label=station_name(idx),
            device=f"hackrf={serial},bias={cfg.bias}",
            antenna=f"ant_{serial}",
            rate_hz=cfg.samp_rate,
            samples=cfg.n_samples,
            path_out=run_dir / f"{station_name(idx)}.bin",
            core=(idx - 1) % ncores,
            t_start=cfg.t_start,
            meta=meta,
        )
        for idx, serial in enumerate(cfg.serial_num, 1)
    ]


def test_jobs(cfg: Config, ref: Path, t_start: datetime) -> list[Job]:
    """gnuradio jobs for test"""

    ncores = os.cpu_count() or 1
    device = f"file={ref},freq={cfg.central_freq:.0f},rate={cfg.test_samp_rate:.0f}"

    return [
        Job(
            label=station_name(idx),
            device=device,
            antenna="file",
            rate_hz=cfg.test_samp_rate,
            samples=cfg.test_n_samples,
            path_out=cfg.test_dir / f"{station_name(idx)}.bin",
            core=(idx - 1) % ncores,
            t_start=t_start,
            meta=False,
        )
        for idx in range(cfg.n_stations)
    ]


def cmd_obs(cfg: Config, meta: bool) -> None:
    """start per station gnuradio obs at t_start"""

    run_dir = cfg.obs_dir / cfg.t_start.strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True)

    jobs = obs_jobs(cfg, run_dir, meta)
    print(
        f"raifm: {cfg.n_stations} stations at {cfg.samp_rate / 1e6:.1f} Msps:"
        f" {cfg.t_total:.0f} s -> {run_dir}"
    )

    run_jobs(cfg, jobs)

    checksums = hash_gen([job.path_out for job in jobs])
    for job in jobs:
        size = job.path_out.stat().st_size
        print(f"  {job.label:12s} {size / 1e9:.2f} GB  {checksums[job.path_out]}")


def cmd_test(cfg: Config) -> None:
    """test osmocom source saving and compare hash"""

    samples = cfg.test_n_samples
    cfg.test_dir.mkdir(parents=True, exist_ok=True)

    iq = cfg.test_dir / HACKRFCFG.test_iq
    ref = cfg.test_dir / HACKRFCFG.test_c64

    t_start = datetime.now(UTC) + timedelta(seconds=3)
    print(
        f"raifm: test {cfg.n_stations} stations at {cfg.test_samp_rate / 1e6:.1f} Msps:"
        f" {cfg.test_t_total:.0f} s with {samples:.2e} samples"
    )

    gen_test_iq(iq, samples)
    convert(iq, ref)

    jobs = test_jobs(cfg, ref, t_start)
    run_jobs(cfg, jobs)

    reference = sha256(ref)
    checksums = hash_gen([job.path_out for job in jobs])

    bad = [job.label for job in jobs if checksums[job.path_out] != reference]
    print(f"raifm: reference {ref.name} {reference}")

    for job in jobs:
        mark = "PASS" if checksums[job.path_out] == reference else "FAIL"
        print(f"    {mark} {job.label:12s} {checksums[job.path_out]}")

    if bad:
        print(
            f"raifm: {len(bad)} of {cfg.n_stations} stations differ: {', '.join(bad)}"
        )
    else:
        print("raifm: test station readout byte identical to reference")


def cmd_purge(cfg: Config, goahead: bool) -> None:
    """purge test bin"""

    targets = [
        path for path in sorted(cfg.test_dir.rglob("ant*.bin")) if path.is_file()
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

    print(f"raifm: unlikned {len(targets)} files, {total / 1e9:.1f} GB")


def cmd_usb(cfg: Config, n_ports: int, n_hackrf: int) -> None:
    """print the usb 2.0 data rate budget of n_hackrf boards over n_ports"""

    plan = UsbPlan(n_hackrf, n_ports, cfg.samp_rate)
    print(
        f"raifm: {n_hackrf} boards at {cfg.samp_rate / 1e6:.1f} Msps,"
        f" {n_ports} port(s), {HACKRFCFG.size_i8} B per sample"
    )
    print(
        f"    per board {plan.per_board_mbps:.1f} Mbit/s,"
        f" all boards {plan.total_mbps:.1f} Mbit/s"
    )

    for label, buses in (("one bus", 1), (f"{n_ports} bus(es)", n_ports)):
        load = plan.bus_mbps(buses)
        verdict = (
            f"ok, {BUDGET_MBPS - load:.1f} Mbit/s spare"
            if load <= BUDGET_MBPS
            else f"over by {load - BUDGET_MBPS:.1f} Mbit/s"
        )
        print(f"    {label:10s} {load:8.1f} Mbit/s of {BUDGET_MBPS:.1f} -> {verdict}")

    print(
        f"    max rate {plan.max_rate_hz(1) / 1e6:.2f} Msps on one bus,"
        f" {plan.max_rate_hz(n_ports) / 1e6:.2f} Msps on {n_ports} bus(es)"
    )
    print(f"    this machine has {usb2_buses()} usb 2.0 buses")


# TODO
# def cmd_trim(cfg: Config) -> None:
#     """drop the windows in which any station lost samples"""

#     runs = sorted(path for path in cfg.obs_dir.glob("*") if path.is_dir())
#     if not runs:
#         print(f"raifm: no run under {cfg.obs_dir}")
#         return None

#     run_dir = runs[-1]
#     paths = {path.stem: path for path in sorted(run_dir.glob("ant*.bin"))}
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
    #     help="cut lost sample windows out of the latest obs run",
    # )
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
        "--meta", action="store_true", help="save with file_meta_sink headers"
    )
    parser.add_argument(
        "--ports", type=int, default=1, metavar="N", help="usb ports in use"
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
    """

    args = build_parser().parse_args(argv)
    cfg = cli_overrides(load_config(args.config), args)

    if args.purge:
        cmd_purge(cfg, args.yes)
    # TODO
    # elif args.trim:
    #     cmd_trim(cfg)
    elif args.usb:
        cmd_usb(cfg, args.ports, args.hackrf or cfg.n_stations)
    elif args.test:
        cmd_test(cfg)
    else:
        cmd_obs(cfg, args.meta)
