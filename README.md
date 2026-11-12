# strw-ra-interferometer

Radio Astronomy paint-can interferometer project at Leiden Observatory.

## toc

- [strw-ra-interferometer](#strw-ra-interferometer)
  - [toc](#toc)
  - [tree](#tree)
  - [env](#env)
  - [quickstart](#quickstart)
  - [conventions](#conventions)

## tree

The current project is laid out with:

```sh
.
├── config.toml
├── data
├── dev
├── env.yml
├── LICENSE
├── main.py
├── pyproject.toml
├── README.md
└── src
    └── raifm
```

## env

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

Current version should read `0.1.0`:

```sh
python main.py -v
raifm 0.1.0
```

## quickstart

Run operations from cli:

```sh
# the default
# this will trigger actual obsevation from real hackrf data stream
# optional cli flag -o
python main.py

# run tests
# this goes: [fake hackrf c64 data] -> [osmocom source] -> c64 bin
# test runs are armed in parallel and starts roughly within 1ms with each other
python main.py -t
# optionally set duration (s) and sample rate (Hz)
python main.py -t --duration 10 --rate 1000000

# purge
# unlink test generated .bin files under ./data/test
# pass -y to confirm purge, otherwise it'll be a dry run
python main.py -p -y

# usb 2.0 budget: n hackrf over m ports, at [obs] samp_rate
python main.py -u --hackrf 3 --ports 3
# all hackrf connected to a usb hub share the hub's bus
# how much we can push the samp rate dependends on how many independent busses we use
python main.py -u --hackrf 3 --ports 1
```

The antenna stations are assigned from 1 index under `./config.toml`.
These hackrf serials are meant to be kept as is,
we recommend assigning stations to array configs following existing labels.

## conventions

The timestamps follow `ISO8601` conventions at `UTC` time,
we can overwrite existing start time configs via:

```sh
python main.py --start "2026-11-11T11:11:11Z"
```

The saved binary data files can be found under `./data/obs/`,
this directory would be automatically populated by the observation starting time.
