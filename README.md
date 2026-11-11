# strw-ra-interferometer

Radio Astronomy paint-can interferometer project at Leiden Observatory.

## toc

- [strw-ra-interferometer](#strw-ra-interferometer)
  - [toc](#toc)
  - [tree](#tree)
  - [env](#env)
  - [quickstart](#quickstart)
  - [work in progress](#work-in-progress)

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

# obs with file_meta_sink headers instead of a plain file sink
python main.py --meta

# usb 2.0 budget: n boards over m ports, at [obs] samp_rate
python main.py -u --hackrf 3 --ports 3
# boards behind one hub share the hub's single bus
python main.py -u --hackrf 3 --ports 1
```

## work in progress

- a utility to scan the latest observation data and find common lost time samples
- more console prints to visualize job progress
