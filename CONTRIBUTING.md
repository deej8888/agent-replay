# Contributing

Small, focused contributions are welcome. Open an issue for substantial behavior or storage changes before implementing them. Bug reports should include sanitized reproduction steps, expected/actual behavior, Python/Node versions, and relevant errors. Do not attach real credentials or customer traces.

Follow the [README quick start](README.md#quick-start), create a branch, and keep commits focused. Use conventional commit prefixes such as `feat(sdk):`, `fix(replay):`, `test(api):`, and `docs:`.

Run Python lint, format, mypy and pytest plus frontend lint, typecheck and Vitest before submitting. For UI/API changes, build the frontend and run Playwright end-to-end tests. For schema changes, add an Alembic revision, test upgrade from the prior revision, and exercise SQLite and PostgreSQL. See [.github/workflows/ci.yaml](.github/workflows/ci.yaml).

Python code uses Ruff formatting and strict mypy for runtime SDK/API/example modules. The frontend uses strict TypeScript, ESLint and Prettier. Prefer small modules with explicit boundaries. Tests should check behavior and failure cases, especially that replay never reaches an integration implementation. Keep the demo and standard test suite free of paid API requirements.

Preserve the distinction between stored playback and code re-execution. New replay features must define their determinism, matching and isolation semantics in `docs/replay.md`. Do not introduce fallbacks to live APIs. Keep all UI actions connected to real behaviors and make unsupported capabilities explicit.

Pull requests should state the concrete problem, resulting behavior, and validation. Include before/after screenshots for meaningful UI changes. By submitting a contribution, you agree it can be distributed under the project's MIT license.
