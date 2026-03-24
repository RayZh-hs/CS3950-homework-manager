# CS3950 Homework Manager

This repository implements a homework manager for CS3950, a course on algorithm design and analysis. It provides a full set of tools to fetch, setup and submit homework assignments from OC Canvas.

## Quickstart

To use the template, download [Mango](https://github.com/Mango-CLI/Mango) and use it to initialize a course folder:

```
cd CS3950
mango @init --template https://github.com/RayZh-hs/CS3950-homework-manager.git
```

After that, set environment variables either in `.mango/.env` or your shell environment. See `.mango/.env.example` for details. The required variables are:

- `OC_API_KEY`: API key for OC Canvas instance. You can generate one from your account settings page [here](https://oc.sjtu.edu.cn/profile/settings). Make sure to keep this token secret.

Run `mango homework --help` to see usage instructions.

## Usage Guide

This guide is inherited from the original README of the template repository, see [here](https://github.com/RayZh-hs/canvas-homework-manager-template/blob/main/README.md) for the original version.

All `mango homework` commands should be run in or below the root directory of the course folder. It has been aliased to `mango hw` by default.

- `mango homework`
	- Show usage and available subcommands (`list`, `fetch`, `submit`).

- `mango homework list`
	- List available homeworks online.
	- Ordered by due time (`due_at`).
	- Status prefix `[downloaded|submitted]`, where each value is `Y` or `N`.

- `mango homework fetch <assignment-id|name-keyword>`
	- Fetch one homework from Canvas.
	- Downloads linked files from the assignment page.
	- Creates local structure under `homework/<id>-<slug>/`.
	- Executes `post_fetch_homework()` hook in `.mango/settings.py`.

- `mango homework submit <assignment-id|name-keyword>`
	- Runs `build_homework()` hook in `.mango/settings.py`.
	- Collects artifacts from `get_submission_artifacts()`.
	- Uploads files and submits them to Canvas.

- `mango homework --help`
	- Show usage and available subcommands.
