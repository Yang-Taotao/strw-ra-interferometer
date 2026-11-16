
# contributing

Contributions are best made by Pull Requests from latest `main` branch forks.

## branching

In general, clone and branch from latest `main` into a feature branch:

```sh
git checkout main
git checkout -b xxx
```

> [!NOTE]
> Typically, this reads to a dev branch such as `dev/xxx`,
> a feature branch `feat/xxx`, and fixes such as `fix/xxx`.

To keep your branch up to data with the latest changes on `main`, do quick rebase:

```sh
git fetch origin
git rebase origin/main
```

## commits

Use conventional commits to keep descriptive and trackable changes.

## formatting and validation

General formatting and linting is handled by `ruff`.
And instructions on how to handle `ruff` is dependent on your own setup.

In general, get the linter error reports and run formatter check with:

```sh
ruff check
ruff format --check
```

These will show the issues in current codes without applying any inplace fixes.

## pull requests

Pull requests should always be opened against the latest `main` branch.

> [!IMPORTANT]
> Pull requests in this project is handled by squash merging to keep the commits atomic.
>
> We recommend to not reuse a branch after it has been merged to `main`.
>
> Instead, make a new branch from the latest `main` again.
