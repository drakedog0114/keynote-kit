# Contributing

Thanks for taking the time to contribute.

## Development setup

```bash
git clone https://github.com/<you>/keynote-kit.git
cd keynote-kit
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
```

Keynote must be installed and your terminal must be allowed to control it
(*System Settings → Privacy & Security → Automation*).

## Running the checks

```bash
ruff check .
pytest            # smoke tests are skipped when Keynote is unavailable
python examples/02_demo_deck.py
```

## Reporting a Keynote scripting trap

Keynote's scripting bridge has many undocumented defects. If you hit a new one, please open an
issue containing:

1. The minimal script that reproduces it (JXA or AppleScript, not the wrapper).
2. The exact error number and message.
3. The Keynote version: `defaults read "/Applications/Keynote.app/Contents/Info.plist" CFBundleShortVersionString`
   (or the `Keynote Creator Studio.app` equivalent).

Reproductions that make it into a workaround are also added to `docs/gotchas.md` — that file is
the project's most valuable asset.

## Pull requests

- Keep changes focused; one concern per PR.
- Add an entry to `CHANGELOG.md` under `[Unreleased]`.
- If you add a workaround, document the underlying defect in `docs/gotchas.md`.
- Public API changes need a docstring and a README/API mention.

## Code style

- Python 3.10+, type hints on public functions, `ruff` with the repo config.
- No third-party runtime dependency in `keynote_kit/deck.py` and `keynote_kit/runner.py`;
  `Pillow` and `matplotlib` are optional extras used by `charts` / `diagrams`.

## License

By contributing you agree that your contributions are licensed under the MIT License.
