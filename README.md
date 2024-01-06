# Keylogger

It is malicious program written in python with the following abilities:
1. Logging the keystrokes of the victim's machine and sending them to source via encrypted mail (Base64 encryption).
2. Added functionality of screenshots after every set interval and also when the user presses ENTER or DEL key.
3. Retrieves critical system information such as Public IP, saved Wifi passwords, browser history, running processes etc.


## How to Use

Go to main.py and enter your gmail and app password according to their respective variables.
Follow this [link](https://support.google.com/mail/answer/185833?hl=en) in case you need help to set app password.

Also set the timer variable (by default 60 seconds).

You can also pass an additional parameter to start method for printing the execution of functions realtime during the debugging phase. (By default it is set to false)

`keylogger.start(print_debug_logs=True)`

Convert main.py to an executable and you are good to go.