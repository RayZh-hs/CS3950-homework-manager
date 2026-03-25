# CS3950 Homework Manager

This repository implements a homework manager for CS3950, a course on algorithm design and analysis. It provides a set of Mango commands to list assignments from OC Canvas, fetch homework materials, generate a LaTeX starter from the assignment PDF, and submit the final files back to Canvas.

## Quickstart

1. Install [Mango](https://github.com/Mango-CLI/Mango).
2. Initialize your course folder from this template:

```bash
cd CS3950
mango @init --template https://github.com/RayZh-hs/CS3950-homework-manager.git
```

3. Configure the environment.

The homework manager reads environment variables from these places:

1. your current shell environment
2. a `.env` file in the current working directory
3. `.mango/.env`

Later sources override earlier ones, so `.mango/.env` is the most reliable place to keep template-specific settings.

The easiest setup is:

```bash
cp .mango/.env.example .mango/.env
```

Then edit `.mango/.env` and fill in the values you need. If you are using Codex, you can set `OC_INFER_AGENT_FROM=codex` and use the configuration from `~/.codex` instead of manually filling in the `OC_AGENT_*` variables.

## Environment Variables

See `.mango/.env.example` for the complete template. The supported variables are:

### Canvas access

- `OC_API_KEY` (required before running `mango homework` commands): API key for OC Canvas. Generate one from your OC account settings page at <https://oc.sjtu.edu.cn/profile/settings>.

### Agent configuration

The default `fetch` workflow tries to generate `main.tex` from the first downloaded PDF attachment. To use that workflow, configure one of the following agent setups.

#### Option A: manual `OC_AGENT_*` settings

- `OC_AGENT_ENDPOINT`: API endpoint for the model provider. Default when unset is `https://api.openai.com/v1/responses`.
- `OC_AGENT_API_KEY`: API key used for agent requests.
- `OC_AGENT_MODEL`: model name to call. Defaults to `gpt-4o-mini` in code; the example file uses `gpt-5.4`.
- `OC_AGENT_TIMEOUT`: request timeout in seconds. Defaults to `180`.
- `OC_AGENT_USER_AGENT`: optional `User-Agent` header.

#### Option B: infer settings from Codex

- `OC_INFER_AGENT_FROM=codex`: infer the endpoint and model from `~/.codex/config.toml` and the API key from `~/.codex/auth.json`.
- `OPENAI_API_KEY`: optional fallback API key if Codex auth is not available locally.

If both `OC_INFER_AGENT_FROM` and manual `OC_AGENT_*` variables are present, the manual `OC_AGENT_*` values take precedence. In practice, this means `OC_AGENT_ENDPOINT`, `OC_AGENT_API_KEY`, `OC_AGENT_MODEL`, or `OC_AGENT_TIMEOUT` will switch the template into manual mode.

### Homework metadata

- `OC_STUDENT_NAME`: optional name inserted into the generated LaTeX author block.
- `OC_STUDENT_ID`: optional student ID inserted into the generated LaTeX author block.

### Build tooling

- `LATEX_COMMAND`: command used by `submit` to build `main.tex`. Defaults to `pdflatex`.

## External Tools

The template expects a few external commands to be available:

- `mango`: used to run the template commands.
- `pdflatex` or your configured `LATEX_COMMAND`: used during `mango homework submit` when `main.tex` exists.
- `pdftotext`: used only if the model provider rejects direct PDF input and the template falls back to extracted PDF text.

## Usage Guide

All `mango homework` commands should be run in or below the root directory of the course folder. `mango homework` is aliased to `mango hw` by default.

- `mango homework --help`
  - Show usage and available subcommands.

- `mango homework list`
  - List homework assignments from Canvas.
  - Ordered by due time (`due_at`).
  - Status prefix is `[downloaded|submitted]`, where each value is `Y` or `N`.

- `mango homework fetch <assignment-id|name-keyword>`
  - Resolve an assignment by exact numeric ID or case-insensitive name substring.
  - Download linked files from the assignment page into `homework/<id>-<slug>/`.
  - Store local metadata in `homework/<id>-<slug>/.hwmeta.json`.
  - If at least one PDF attachment is downloaded, use the first PDF as agent input and write the generated LaTeX to `homework/<id>-<slug>/main.tex`.
  - If no PDF attachment is found, the auto-generation step is skipped.

- `mango homework submit <assignment-id|name-keyword>`
  - Require the local homework directory to exist first.
  - Run `build_homework()` from `.mango/settings.py`.
  - By default, compile `main.tex` with `LATEX_COMMAND` if `main.tex` exists.
  - Submit files from `homework/<id>-<slug>/submit/` if that directory exists; otherwise submit `homework/<id>-<slug>/main.pdf` if present.
  - Store submission metadata back into `homework/<id>-<slug>/.hwmeta.json`.

## Notes

- The course-specific configuration lives in `.mango/settings.py`.
- The default template is currently configured for OC Canvas at `https://oc.sjtu.edu.cn/` and course ID `88632`.
- If your query matches multiple assignments during `fetch` or `submit`, the CLI prints the candidate IDs and names and exits so you can retry with a more specific query.
