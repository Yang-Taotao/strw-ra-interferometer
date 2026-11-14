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
  - [buffers](#buffers)
  - [metadata sidecar](#metadata-sidecar)
    - [metadata](#metadata)
    - [file checksum](#file-checksum)

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
>
> For users on windows,
> use `conda prompt` or equivalent for running the following cli commands.
>
> Alternatively, if you are using `uv` or py `venv`,
> make sure you have system site packages
> such as `hackrf` and `gnuradio` installed locally.

The dependencies can be entirely handled by `conda`.
Create and activate this `env` from `./env.yml`:

```sh
conda env create -f env.yml -n strw-ra-py314
conda activate strw-ra-py314
```

We then do a quick editable install of the current package:

```sh
pip install -e .
```

Current version should read `0.2.1`:

```sh
raifm -v
raifm 0.2.1
```

> [!IMPORTANT]
> No `conda` needed if the host has `gnuradio`, `gr-osmosdr`, and `hackrf`.
>
> If these packages are managed as system site packages via package managers
> such as `apt`, `brew`, and `pacman`,
> then `uv` will not be managing these system wide packages in the `uv` `.venv`.

With `uv` and `apt`, we do:

```sh
sudo apt install gnuradio gr-osmosdr hackrf
PYTHONPATH=src python3 -m raifm.cli -v
raifm 0.2.1
```

### cli

> [!IMPORTANT]
> Run operations from cli.

The default mode is observation,
this will trigger actual obsevation from real `hackrf` data stream.
An optional flag of `-o` can be added to achieve the same effect.

```sh
raifm
```

A test mode is included with flag `-t`,
this goes: `[fake hackrf c64 data] -> [osmocom source] -> c64 bin`.
Test runs are armed in parallel and starts roughly within ~0.01 ms with each other:

```sh
raifm -t
```

Optionally set duration (s) and sample rate (Hz) as cli overrides:

```sh
raifm -t --duration 10 --rate 1000000
```

These tests will then generate some amount of data.
The data size is controlled by test observation duration and sampling rate.
We can purge these test data via `-p` flag.
This unlinks the test data once `-y` flag is parsed to confirm the operation:

```sh
raifm -p -y
```

We check the `CLKIN` status on all configured `hackrf` with `-c` flag:

```sh
raifm -c
```

To check for max sampling rate for your USB 2.0 bus budget on your local device,
use `-u` flag and specify the number of `hackrf`
and number of USB `ports` connected on your laptop.
For example, this checks for 4 `hackrf` devices connected to 2 USB hubs
that is then connected to 2 USB ports on the motherboard.

```sh
raifm -u --hackrf 4 --ports 2
```

> [!NOTE]
> All `hackrf` connected to a USB hub share the hub's bus
>
> How much we can push the samp rate dependends on how many independent busses we use

## conventions

> [!NOTE]
> The antenna stations are assigned from 1 index under `./config.toml`.
>
> These `hackrf` serials are meant to be kept as is.
>
> We recommend assigning stations to array configs following existing labels.

The timestamps follow `ISO8601` conventions at `UTC` time,
we can overwrite existing start time configs via:

```sh
raifm --start "20261111T111111Z"
```

Additional overrides such as a 600 seconds observation duration can be added:

```sh
raifm --start "20261111T111111Z" --duration 600
```

The saved binary data files can be found under `./data/obs/`,
this directory would be automatically populated by the observation starting time.

> [!NOTE]
> For details on `data` directory structure, see [metadata sidecar](#metadata-sidecar).

After an observation finishes,
we check `hackrf_debug -S` for all connected `hackrf`.

## buffers

Two buffers exists for `osmocom source`: `Minoutbuf` and `Maxoutbuf`.
The default values for these enteries are zero.

This can be overwritten via cli,
for example, we set `Minoutbuf` to 100000 for a test mode run:

```sh
raifm -t --buffer 100000
```

## metadata sidecar

Per-run parameters are automatically written to a `.json` sidecar.
Example directory tree under `./data`:

```sh
.
├── obs
│   └── 20261111T111111Z
│       ├── antenna_01.bin
│       ├── antenna_01.bin.sha256
│       ├── antenna_02.bin
│       ├── antenna_02.bin.sha256
│       └── metadata.json
└── test
    ├── antenna_01.bin
    ├── antenna_01.bin.sha256
    ├── antenna_02.bin
    ├── antenna_02.bin.sha256
    ├── antenna_03.bin
    ├── antenna_03.bin.sha256
    ├── metadata.json
    ├── test_c64.bin
    └── test_iq.bin
```

### metadata

> [!NOTE]
> The metadata contains source parameters from `config.toml`,
> actual metadata saves enteries from cli overrides.
>
> The aim is to keep `config.toml` atomic across devices.
>
> The `metadata.json` files are preserved across `-p` purge calls for tests.

To parse the `metadata.json` back in for analysis in `py`:

```py
from raifm import config

# set path and parse json to dataclass
test_metadata_path = "./data/test/run.json"
TestCFG = config.MetadataCFG.parse_json(obs_metadata_path)

# read attr - example to get n_stations
n_stations = TestCFG.n_stations
```

Currently, we support the following metadata:

```sh
@dataclass(frozen=True)
class MetadataCFG:
    """per run metadata cfg"""

    n_stations: int
    serial_num: list[str]
    t_start: datetime
    t_total: float
    samp_rate: float
    central_freq: float
    gain_rf: int
    gain_if: int
    gain_bb: int
    n_chan: int
    bias: int
    obs_dir: str
    test_dir: str
    test_t_total: float
    test_samp_rate: float
    buffer: int
```

### file checksum

> [!IMPORTANT]
> A `.sha256` checksum file file is written alongside individual `.bin` data.
>
> We recommend users to perform a quick file checksum post file transfer.

On Linux platform, this can be done via:

```sh
cd data/obs/xxx
sha256sum -c *.sha256
```

For MacOS platform, this becomes:

```sh
cd data/obs/xxx
shasum -a 256 -c *.sha256
```

With Windows platform,
we recommend using `git bash` or `wsl` to run commands for this step:

```sh
cd data/obs/xxx
sha256sum -c *.sha256
```
