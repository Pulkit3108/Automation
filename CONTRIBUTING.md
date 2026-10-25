# Contributing

End users should install with `pipx`; see [`setup/`](setup/README.md). A repository virtual
environment is only for development and validation.

## Development Environment

Clone the repository, then create an isolated environment.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

## Validation

```bash
ruff check .
pytest
python -m unittest discover -s tests -v
python -m pip check
npx --yes markdownlint-cli2 README.md DESIGN.md AGENTS.md CONTRIBUTING.md setup/*.md
```

Default tests use test doubles and must not contact live job portals, browsers, keyrings, native
schedulers, notifications, or user data.

The application version has one source in `resume_automation.__version__`; setuptools reads it
dynamically. Bump it for every user-facing release.

## Change Boundaries

- Keep portal behavior in `providers/<name>.py` behind the provider contract.
- Keep profile, workflow, results, locks, notifications, and scheduler orchestration
  provider-neutral.
- Add focused tests for every behavior change.
- Never commit credentials, résumés, browser state, logs, screenshots, traces, results, or generated
  scheduler files.
- Do not commit or publish changes without explicit authorization.
