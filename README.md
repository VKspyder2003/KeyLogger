# Keylogger

This program is a malicious Python application with the following capabilities:

1. **Keystroke Logging:** Records the keystrokes on the victim's machine and sends them to a specified source via encrypted email (Base64 encryption).
2. **Screenshot Capture:** Takes screenshots at regular intervals and when certain keys (ENTER or DELETE) are pressed.
3. **System Information Retrieval:** Gathers critical system information, including public IP, saved WiFi passwords, browser history, and running processes.

## How to Use

1. Open `main.py` and enter your Gmail credentials and app password in the respective variables. If needed, follow this [link](https://support.google.com/mail/answer/185833?hl=en) for assistance with setting up an app password.

2. Set the `timer` variable (in seconds) to determine the interval between data reports.

3. Optionally, you can enable real-time debugging by passing an additional parameter to the `start` method:

    ```python
    keylogger.start(print_debug_logs=True)
    ```

## Converting `main.py` to `main.exe`

To convert the Python script to an executable (.exe) file, you can use `pyinstaller`. Follow these steps:

1. Install `pyinstaller` using the command:

    ```bash
    pip install pyinstaller
    ```

2. Navigate to the project folder and run the following command:

    ```bash
    pyinstaller --onefile --noconsole main.py
    ```

3. The final `main.exe` file will be generated in the `dist` folder upon completion.

**Note:** The use of keyloggers and similar tools without explicit consent is unethical and may be illegal. Always ensure you have proper authorization before using such software.
