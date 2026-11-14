# strw-ra-interferometer

**Radio Astronomy paint-can interferometer project** at [Leiden Observatory](https://www.strw.leidenuniv.nl/).

> [!CAUTION]
> Work in progress project
>
> Breaking changes may be frequent, see `README` for instructions.

## toc

- [strw-ra-interferometer](#strw-ra-interferometer)
  - [toc](#toc)
  - [tree](#tree)
  - [quickstart](#quickstart)
    - [prep](#prep)
    - [env](#env)
    - [cli](#cli)
  - [conventions](#conventions)
  - [metadata sidecar](#metadata-sidecar)

## tree

The current project is laid out with:

```sh
.
├── config.toml     # config file
├── data            # data directory
│   ├── obs
│   └── test
├── dev
├── env.yml         # conda env source
├── LICENSE
├── main.py         # cli
├── pyproject.toml
├── README.md
└── src
    └── raifm       # src
```

## quickstart

### prep

First clone the project to a directory and enter:

```sh
git clone https://github.com/Yang-Taotao/strw-ra-interferometer.git
cd strw-ra-interferometer
```

### env

> [!IMPORTANT]
> Make sure `miniforge3` or equivalent is installed.

The dependencies are handled entirely by `conda`.
Create and activate this `env` from `./env.yml`:

```sh
conda env create -f env.yml -n strw-ra-py314
conda activate strw-ra-py314
```

We then do a quick editable install of the current package:

```sh
pip install -e .
```

> [!NOTE]
> No `conda` needed if the host has `gnuradio`, `gr-osmosdr`, and `hackrf`.
> Apt installed ones are separated from the uv venv, thus you need:
>
> ```sh
> sudo apt install gnuradio gr-osmosdr hackrf
> PYTHONPATH=src python3 -m raifm.cli -t --duration 5
> ```

Current version should read `0.2.0`:

```sh
raifm -v
raifm 0.2.0
```

### cli

Run operations from cli:

```sh
# the default
# this will trigger actual obsevation from real hackrf data stream
# optional cli flag -o
raifm

# run tests
# this goes: [fake hackrf c64 data] -> [osmocom source] -> c64 bin
# test runs are armed in parallel and starts roughly within 1ms with each other
raifm -t
# optionally set duration (s) and sample rate (Hz)
raifm -t --duration 10 --rate 1000000

# purge
# unlink test generated .bin files under ./data/test
# pass -y to confirm purge, otherwise it'll be a dry run
raifm -p -y

# usb 2.0 budget: n hackrf over m ports, at [obs] samp_rate
raifm -u --hackrf 3 --ports 3
# all hackrf connected to a usb hub share the hub's bus
# how much we can push the samp rate dependends on how many independent busses we use
```

> [!NOTE]
> The antenna stations are assigned from 1 index under `./config.toml`.
>
> These hackrf serials are meant to be kept as is.
>
> We recommend assigning stations to array configs following existing labels.

## conventions

The timestamps follow `ISO8601` conventions at `UTC` time,
we can overwrite existing start time configs via:

```sh
raifm --start "2026-11-11T11:11:11Z"
```

The saved binary data files can be found under `./data/obs/`,
this directory would be automatically populated by the observation starting time.

## metadata sidecar

Per-run parameters are automatically written to a `.json` sidecar.
Example directory tree under `./data`:

```sh
.
├── obs
│   └── 20261111T111111Z
│       ├── antenna_01.bin
│       ├── antenna_02.bin
│       └── metadata.json
└── test
    ├── antenna_01.bin
    ├── antenna_02.bin
    ├── antenna_03.bin
    ├── antenna_04.bin
    ├── antenna_05.bin
    ├── antenna_06.bin
    ├── antenna_07.bin
    ├── antenna_08.bin
    ├── antenna_09.bin
    ├── antenna_10.bin
    ├── metadata.json
    ├── test_c64.bin
    └── test_iq.bin
```

> [!NOTE]
> The metadata contains source parameters from `config.toml`,
> actual metadata saves enteries from cli overrides.
>
> The aim is to keep `config.toml` atomic across devices.
>
> The `metadata.json` files are preserved across `-p` purge calls for tests.
