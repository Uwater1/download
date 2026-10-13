# Contributing

## Before opening a change

- Read the README and keep changes focused on the downloader, storage, migration, or workflow behavior.
- Do not commit API keys, cookies, credentials, local virtual environments, or unreviewed generated data.
- For changes that affect downloaded files, explain the expected snapshot/history impact and test with a temporary `--output-root`.

## Development

```sh
python3.12 -m venv /workspace/download-env
/workspace/download-env/bin/python -m pip install -r requirements.txt
/workspace/download-env/bin/python -m pytest -q
```

Use the pinned Python and dependency versions. Tests must pass before a pull request is requested. Network-dependent behavior should be tested with fixtures or mocks; do not make tests depend on live Yahoo responses.

## Pull requests

- Use a descriptive title and explain the user-visible or data-model effect.
- Keep generated Parquet changes separate from code changes when practical.
- Include tests for changed behavior and mention commands run.
- Request review from the code owners listed in `.github/CODEOWNERS`.
- Treat review comments as technical discussion: be specific, assume good intent, and resolve disagreements with a reproducible example.

Maintainers may ask for a smaller change, additional validation, or a rollback plan before merging.