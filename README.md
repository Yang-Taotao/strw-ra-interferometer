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

## quickstart

Run operations from cli:

```sh
python main.py
```

## work in progress

Future sections are work in progress.
