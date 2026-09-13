"""Command-line adapter for the lecture toolkit."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

from lecturefoundry.ai import AIBackendError, GenerationRequest, create_ai_backend
from lecturefoundry.build import BuildRequest, generate_lecture
from lecturefoundry.catalog import (
    catalog_from_coursera_materials,
    missing_transcripts,
    save_catalog,
)
from lecturefoundry.config import SUPPORTED_PROVIDERS, load_ai_settings
from lecturefoundry.models import FetchRequest, TranscriptFormat
from lecturefoundry.patterns import PATTERNS
from lecturefoundry.providers import CourseraProvider
from lecturefoundry.services import fetch_transcripts


PROVIDER_DESCRIPTIONS = {
    "ollama": "Ollama HTTP API (local or hosted)",
    "codex": "Authenticated Codex CLI",
    "claude": "Authenticated Claude Code CLI",
    "openai": "Native OpenAI Responses API",
    "openai-compatible": "OpenAI-compatible Chat Completions API",
    "anthropic": "Native Anthropic Messages API",
    "gemini": "Native Google Gemini generateContent API",
}
ONLINE_PROVIDERS = {
    "codex",
    "claude",
    "openai",
    "openai-compatible",
    "anthropic",
    "gemini",
}


def _uses_remote_service(provider: str, options: dict) -> bool:
    if provider in ONLINE_PROVIDERS:
        return True
    if provider != "ollama":
        return False
    hostname = urlparse(
        str(options.get("base_url", "http://localhost:11434"))
    ).hostname
    return hostname not in {"localhost", "127.0.0.1", "::1"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lecturefoundry",
        description="Build local lecture experiences from course transcripts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Download transcripts for an enrolled Coursera course.",
    )
    fetch_parser.add_argument("--slug", required=True, help="Course URL slug")
    fetch_parser.add_argument("--output", type=Path, default=Path("transcripts"))
    fetch_parser.add_argument("--language", default="en")
    fetch_parser.add_argument(
        "--format",
        dest="transcript_format",
        choices=[item.value for item in TranscriptFormat],
        default=TranscriptFormat.TXT.value,
    )
    fetch_parser.add_argument(
        "--cookie-env",
        default="COURSERA_CAUTH",
        metavar="NAME",
        help="Environment variable containing CAUTH (default: COURSERA_CAUTH)",
    )

    index_parser = subparsers.add_parser(
        "index",
        help="Create an ordered course catalog for downloaded transcripts.",
    )
    index_parser.add_argument("--slug", required=True, help="Course URL slug")
    index_parser.add_argument(
        "--transcripts",
        type=Path,
        default=Path("transcripts"),
        help="Transcript root directory (default: transcripts)",
    )
    index_parser.add_argument(
        "--cookie-env",
        default="COURSERA_CAUTH",
        metavar="NAME",
        help="Environment variable containing CAUTH (default: COURSERA_CAUTH)",
    )

    patterns_parser = subparsers.add_parser(
        "patterns",
        help="List available lecture-generation patterns.",
    )
    patterns_parser.set_defaults(command="patterns")

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate and render one numbered lecture page.",
    )
    generate_parser.add_argument("--slug", required=True, help="Course URL slug")
    generate_parser.add_argument("--module", type=int, required=True, help="Module number")
    generate_parser.add_argument("--lecture", type=int, required=True, help="Lecture number within the module")
    generate_parser.add_argument(
        "--pattern",
        choices=list(PATTERNS),
        required=True,
        help="Learning pattern to generate",
    )
    generate_parser.add_argument("--transcripts", type=Path, default=Path("transcripts"))
    generate_parser.add_argument("--output", type=Path, default=Path("site"))
    generate_parser.add_argument("--config", type=Path, default=Path("lecture.toml"))
    generate_parser.add_argument(
        "--provider",
        choices=SUPPORTED_PROVIDERS,
        help="Override the configured AI provider",
    )
    generate_parser.add_argument("--model", help="Override the configured model")
    generate_parser.add_argument("--base-url", help="Override the provider API base URL")
    generate_parser.add_argument(
        "--api-key-env",
        metavar="NAME",
        help="Override the environment-variable name containing the API key",
    )
    generate_parser.add_argument(
        "--temperature",
        type=float,
        help="Sampling temperature when supported by the selected model/provider",
    )
    generate_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing generation for this pattern",
    )

    ai_parser = subparsers.add_parser(
        "ai",
        help="Check or invoke a configured AI backend.",
    )
    ai_subparsers = ai_parser.add_subparsers(dest="ai_command", required=True)

    def add_ai_options(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument(
            "--config",
            type=Path,
            default=Path("lecture.toml"),
            help="Project configuration file (default: lecture.toml)",
        )
        command_parser.add_argument(
            "--provider",
            choices=SUPPORTED_PROVIDERS,
            help="Override the configured AI provider",
        )
        command_parser.add_argument("--model", help="Override the configured model")
        command_parser.add_argument("--base-url", help="Override the provider API base URL")
        command_parser.add_argument(
            "--api-key-env",
            metavar="NAME",
            help="Override the environment-variable name containing the API key",
        )

    ai_subparsers.add_parser("providers", help="List configured backend types")

    check_parser = ai_subparsers.add_parser("check", help="Check backend availability")
    add_ai_options(check_parser)

    run_parser = ai_subparsers.add_parser("run", help="Generate text from a prompt")
    add_ai_options(run_parser)
    run_parser.add_argument(
        "--prompt",
        help="Prompt text; when omitted, read it from standard input",
    )
    run_parser.add_argument(
        "--temperature",
        type=float,
        help="Sampling temperature when supported by the selected model/provider",
    )
    return parser


def _read_cauth(environment_variable: str) -> str:
    token = os.environ.get(environment_variable)
    if token:
        return token
    return getpass.getpass("Coursera CAUTH (input hidden): ")


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "fetch":
        request = FetchRequest(
            slug=args.slug,
            output_dir=args.output.resolve(),
            language=args.language,
            transcript_format=TranscriptFormat(args.transcript_format),
        )
        provider = CourseraProvider(_read_cauth(args.cookie_env))
        result = fetch_transcripts(provider, request)

        print(
            f"Fetched {result.downloaded}/{result.total} transcripts "
            f"to {result.output_dir} "
            f"({result.skipped} skipped, {result.failed} failed)."
        )
        return 0 if result.succeeded else 1

    if args.command == "index":
        try:
            course_dir = args.transcripts.resolve() / args.slug
            provider = CourseraProvider(_read_cauth(args.cookie_env))
            materials = provider.get_course_materials(args.slug)
            catalog = catalog_from_coursera_materials(args.slug, materials, course_dir)
            catalog_path = save_catalog(catalog, course_dir)
            lecture_count = sum(len(module.lectures) for module in catalog.modules)
            missing_count = sum(1 for _ in missing_transcripts(catalog))
            print(
                f"Indexed {lecture_count} lectures across {len(catalog.modules)} modules "
                f"in {catalog_path}."
            )
            if missing_count:
                print(
                    f"warning: {missing_count} catalog lectures have no downloaded transcript",
                    file=sys.stderr,
                )
            return 0
        except (OSError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    if args.command == "patterns":
        for key, pattern in PATTERNS.items():
            print(f"{key:14} {pattern.name} — {pattern.description}")
        return 0

    if args.command == "generate":
        try:
            settings = load_ai_settings(
                args.config,
                provider_override=args.provider,
                model_override=args.model,
                base_url_override=args.base_url,
                api_key_env_override=args.api_key_env,
            )
            backend = create_ai_backend(settings)
            if _uses_remote_service(settings.provider, settings.options):
                print(
                    f"notice: sending this lecture transcript to the configured "
                    f"{settings.provider} service",
                    file=sys.stderr,
                )
            result = generate_lecture(
                backend,
                BuildRequest(
                    course_slug=args.slug,
                    module_number=args.module,
                    lecture_number=args.lecture,
                    pattern=args.pattern,
                    transcripts_dir=args.transcripts.resolve(),
                    output_dir=args.output.resolve(),
                    system_prompt=settings.system_prompt,
                    temperature=args.temperature,
                    force=args.force,
                ),
            )
            model = f"/{result.model}" if result.model else ""
            print(f"Generated {result.html_path} with {result.provider}{model}.")
            return 0
        except (AIBackendError, FileExistsError, FileNotFoundError, OSError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    if args.command == "ai":
        if args.ai_command == "providers":
            for name in SUPPORTED_PROVIDERS:
                print(f"{name:18} {PROVIDER_DESCRIPTIONS[name]}")
            return 0

        try:
            settings = load_ai_settings(
                args.config,
                provider_override=args.provider,
                model_override=args.model,
                base_url_override=args.base_url,
                api_key_env_override=args.api_key_env,
            )
            backend = create_ai_backend(settings)

            if args.ai_command == "check":
                status = backend.check()
                marker = (
                    "OK"
                    if status.available and status.verified
                    else "CONFIGURED"
                    if status.available
                    else "UNAVAILABLE"
                )
                print(f"[{marker}] {status.provider}: {status.detail}")
                if status.available and status.verified:
                    return 0
                return 2 if status.available else 1

            prompt = args.prompt if args.prompt is not None else sys.stdin.read()
            result = backend.generate(
                GenerationRequest(
                    prompt=prompt,
                    system_prompt=settings.system_prompt,
                    temperature=args.temperature,
                )
            )
            print(result.text)
            return 0
        except (AIBackendError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
