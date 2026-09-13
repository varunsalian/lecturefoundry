# Contributing

Thanks for helping improve Coursera Lectures.

## Development setup

```bash
git clone https://github.com/varunsalian/coursera-lectures.git
cd coursera-lectures
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
```

On Windows PowerShell, activate the environment with
`.venv\\Scripts\\Activate.ps1`.

## Pull requests

1. Open an issue first for large features or behavioral changes.
2. Keep changes focused and include tests for new behavior.
3. Run `pytest` and `python -m compileall -q src tests` before submitting.
4. Never include Coursera cookies, API keys, downloaded transcripts, generated
   course pages, or other course materials in commits or test fixtures.
5. Explain user-visible behavior and any security or privacy implications in
   the pull-request description.

Tests must use fakes or fixtures that you have permission to distribute; they
must not contact Coursera or paid AI services.
