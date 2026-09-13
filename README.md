# LectureFoundry

[![Tests](https://github.com/varunsalian/lecturefoundry/actions/workflows/tests.yml/badge.svg)](https://github.com/varunsalian/lecturefoundry/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Forge transcripts from courses you can access into structured, accessible study
experiences. Use a local Ollama model, an authenticated AI CLI, or a hosted API.

The project keeps AI-generated content separate from page rendering: a model
returns validated lesson JSON, then deterministic templates render safe HTML.
The same core library can power the CLI today and a web UI later.

> [!IMPORTANT]
> This is an independent project and is not affiliated with or endorsed by
> Coursera. Use it only with courses and content you are authorized to access.
> Paying for access does not necessarily grant permission to redistribute
> transcripts or generated derivatives. Downloaded and generated content is
> ignored by Git by default.

## Features

- Downloads transcripts for an enrolled Coursera course using a securely
  prompted `CAUTH` cookie.
- Preserves the real module and lecture order in a reusable course catalog.
- Generates one numbered lecture at a time, preventing accidental whole-course
  AI usage.
- Supports four study patterns: one-page revision, descriptive deep dive,
  active recall, and concept map.
- Supports Ollama, Codex CLI, Claude Code CLI, OpenAI, OpenAI-compatible APIs,
  Anthropic, and Gemini.
- Uses structured output plus strict local validation for reliable lesson data.
- Renders accessible, standalone HTML without placing raw model HTML into the
  page.
- Stages output before installation so a failed generation cannot overwrite a
  working lecture.
- Keeps cookies and unrelated environment credentials away from AI CLI
  subprocesses.

## Requirements

- Python 3.10 or newer
- A Coursera account with access to the course you want to process
- At least one supported AI backend

For local generation, install [Ollama](https://ollama.com/) and pull an
instruction model. Codex and Claude users can instead use their authenticated
CLIs. Hosted providers require their own API key and account.

## Quick start

Clone the repository and install it in an isolated environment:

```bash
git clone https://github.com/varunsalian/lecturefoundry.git
cd lecturefoundry
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

On Windows PowerShell, activate with `.venv\\Scripts\\Activate.ps1`.

List the available commands and AI providers:

```bash
lecturefoundry --help
lecturefoundry ai providers
```

### 1. Get your Coursera cookie

Sign in to Coursera in your browser. Open its developer tools, inspect the
cookies stored for `https://www.coursera.org`, and copy the value of the cookie
named `CAUTH`. Browser menus vary, but it is normally under **Application** or
**Storage > Cookies**.

Treat this value like a password. Do not paste it into configuration files,
shell history, screenshots, issues, or commits.

### 2. Download a course

The slug is the part after `/learn/` in a Coursera course URL. Run:

```bash
lecturefoundry fetch \
  --slug the-science-of-well-being \
  --language en \
  --format txt
```

The CLI asks for `CAUTH` using a hidden prompt. For automation, put it in a
temporary environment variable and pass only the variable's name:

```bash
export COURSERA_CAUTH='your-cookie-value'
lecturefoundry fetch --slug the-science-of-well-being
unset COURSERA_CAUTH
```

New downloads create `transcripts/<course>/course.json`. If transcripts came
from an older version, create the ordered catalog with:

```bash
lecturefoundry index --slug the-science-of-well-being
```

### 3. Configure an AI backend

Edit [`lecture.toml`](lecture.toml). The default is Ollama; set its `model` to
one shown by `ollama list`, then verify it:

```bash
lecturefoundry ai check
```

To use Codex CLI, authenticate Codex separately and enable access only for
transcripts you trust:

```toml
[ai]
provider = "codex"

[ai.codex]
command = "codex"
model = "gpt-5.6-luna"
allow_agentic_file_reads = true
```

Then check it with `lecturefoundry ai check`. Codex runs ephemerally in a
read-only temporary directory with project rules and user configuration
disabled. It is still an agentic CLI capable of inspecting readable files, so
the explicit opt-in defaults to `false`.

For a hosted provider, keep the key in the environment and store only the
variable name in `lecture.toml`:

```toml
[ai]
provider = "openai"

[ai.openai]
model = "your-model-id"
base_url = "https://api.openai.com/v1"
api_key_env = "OPENAI_API_KEY"
structured_output = true
```

```bash
export OPENAI_API_KEY='your-key'
lecturefoundry ai check
```

The equivalent configuration tables for every provider are already included
in `lecture.toml`. Literal credentials in provider configuration are rejected.

### 4. Generate one lecture

See the available patterns:

```bash
lecturefoundry patterns
```

Generate Module 1, Lecture 4 as a revision page:

```bash
lecturefoundry generate \
  --slug the-science-of-well-being \
  --module 1 \
  --lecture 4 \
  --pattern revision
```

Override the provider or model for one invocation with `--provider` and
`--model`. Existing output is protected unless `--force` is explicitly passed.

Open the resulting `index.html` directly in a browser. Output is organized by
course, numbered module, numbered lecture, and pattern:

```text
site/
└── the-science-of-well-being/
    └── 01-introduction/
        └── 04-what-is-the-g-i-joe-fallacy/
            ├── source.json
            └── revision/
                ├── index.html
                ├── lesson.json
                └── generation.json
```

Different patterns can coexist for the same lecture. `generation.json` records
the provider, model, pattern version, timestamp, and transcript checksum.

## Providers

| Provider | Integration | Authentication |
| --- | --- | --- |
| `ollama` | Local or hosted Ollama HTTP API | None locally; environment key when hosted |
| `codex` | Non-interactive `codex exec` | Codex CLI login or supported environment key |
| `claude` | Claude Code print mode | Claude CLI login or supported environment key |
| `openai` | OpenAI Responses API | Environment variable |
| `openai-compatible` | Chat Completions-compatible API | Environment variable |
| `anthropic` | Anthropic Messages API | Environment variable |
| `gemini` | Gemini `generateContent` API | Environment variable |

Remote providers receive the selected lecture transcript. The CLI prints a
notice before this happens. Local Ollama URLs are treated as local; hosted
Ollama endpoints are treated as remote.

Run a small provider smoke test with:

```bash
printf 'Reply with exactly: ready\n' | lecturefoundry ai run
```

`[OK]` from `ai check` means the connection or saved login was verified.
`[CONFIGURED]` means settings were found but could not be verified without a
generation; it exits with status 2 so scripts do not mistake it for a verified
connection.

## Architecture

```text
CLI / future UI
       |
       +-- Fetch service --> TranscriptProvider --> CourseraProvider
       |
       +-- Generate service --> Pattern prompt --> AIBackend
                                    |
                                    +-- validated lesson JSON
                                                   |
                                                   +-- deterministic HTML
```

All backends implement the same `AIBackend.generate()` interface. Generation
begins with one canonical JSON Schema, projects it into the provider's supported
subset, and re-applies the complete contract through strict local validation.
If a provider rejects native structured output, it can be disabled in
`lecture.toml`; the schema is then included in the prompt and still validated
locally.

## Privacy and security

- `transcripts/`, `site/`, cookies, `.env` files, build products, and caches are
  excluded by `.gitignore`.
- The Coursera cookie is read from a hidden prompt or a named environment
  variable.
- Configuration accepts credential-variable names, not literal credential
  values.
- AI CLI subprocesses receive an allowlisted environment and cannot inherit the
  Coursera cookie.
- Generation HTTP POST requests are not automatically retried, avoiding
  duplicate billable requests.
- Model-produced JSON is validated and escaped before deterministic rendering.

Please report vulnerabilities privately as described in
[`SECURITY.md`](SECURITY.md).

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
python -m compileall -q src tests
```

Tests use fake providers and do not contact Coursera or paid AI services. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request. Community
participation is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## License

The source code is available under the [MIT License](LICENSE). This license
applies to this repository's code, not to downloaded course material,
transcripts, or third-party content processed with it.
