
from subprocess import Popen



socket_port = [ 3107, 3110 ] # 改3107, 3110 oil
http_port = [ 3207, 3210 ] # 3207, 3210
sent_msg = [ '0102', '0102']
Line_url = "https://maker.ifttt.com/trigger/DemoTest/with/key/iMHP9IsfpS0DbbDCMJmro16spw7fdOZxl5te3bC2eb6"


for i in range(3):
    Popen(["python3", "port_function.py", socket_port[i], http_port[i], sent_msg[i], Line_url])