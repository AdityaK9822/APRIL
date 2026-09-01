# APRIL

APRIL is a local macOS assistant that turns a natural-language request into a shell command, runs it locally, and shows the result in the app window or terminal.

It is intentionally designed to run on your own machine and to execute real commands. Because of that, it should only be used in an environment where you trust the app and understand the consequences of shell execution.

## Safety notice

This project runs shell commands with `subprocess.run(..., shell=True)`. That means it can execute arbitrary commands on the host machine.

Use it only on a machine you control, and only if you are comfortable with:

- full local command execution
- possible access to files and system tools on the host
- the need to review or confirm commands before running them

The app includes an opt-in confirmation gate via `APRIL_CONFIRM=1`, which is off by default.

## Features

- local command translation from plain English to shell commands
- optional voice input using wake-word + whisper + TTS
- optional macOS AppKit window UI
- image-aware requests via local screenshot or image file path
- all model/backend configuration driven by `.env`

## Local setup

1. Create a Python environment and install dependencies:

   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy the example env file:

   ```bash
   cp .env.example .env
   ```

3. Start Ollama and make sure your model is available, for example:

   ```bash
   ollama pull gemma3:4b
   ```

4. Run the app:

   ```bash
   python main.py
   ```

   For the terminal-only mode:

   ```bash
   GUI=0 python main.py
   ```

## Environment variables

See [.env.example](.env.example) for the default configuration. The app reads values from `.env` at runtime.

## Repo notes

This project intentionally does not commit local secrets or generated model files. The repo ignores:

- `.env`
- `.venv/`
- `voices/`
- `models/`
- `__pycache__/`
- downloaded voice/model artifacts

## License

This project is provided as source code for local experimentation and personal use. Add your own license before production use if you intend to redistribute it.
