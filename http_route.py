# encoding: utf-8
from flask import Flask, request
from flask_cors import CORS
import socket, time, threading
import queue as qu
from datetime import datetime, timedelta
import pymysql
import requests
import traceback
import os
import atexit
import sys

from util import Utils

socket_port = int(sys.argv[1])
http_port = int(sys.argv[2])
index = int(sys.argv[5])
db_name = 'Oil'
db_user = 'oil'


print("into http_route, not yet run utils")
util = Utils(http_port, socket_port, db_name, db_user)
print("in http_route, after run utils")

atexit.register(util.sendLine, "伺服程式被迫中斷")
# For threading launch

app = Flask(__name__)
CORS(app)

# GET /init_stat?nodeid=
@app.route("/init_stat", methods=["GET"])
def init_stat():
    nodeid = request.args.get("nodeid")
    if nodeid != "":
        try:
            nodeid = int(nodeid)
        except:
            print("\nFail to int(nodeid)")

        global util
        if util.global_q.qsize() == 0:
            cmd = Utils.gen_cmd(nodeid, b"\x01\x02")
            util.global_q.put(cmd)
            print("\nGET: INIT_STAT")
            return "OK"

    return "Fail"

# GET /stat?nodeid=
@app.route("/get_stat", methods=["GET"])
def get_stat():
    nodeid = request.args.get("nodeid")
    if nodeid != "":
        try:
            nodeid = int(nodeid)
        except:
            print("\nFail to int(nodeid)")

        print("\nGET: GET_STAT")

        global util
        util.checksum()
        res = ""
        if util.comp_res:  # Means checksum is correct
            res = "".join("{:02x}".format(d) for d in util.response)
            util.response = ""
        if res == "":
            res = "Unknown"

    return res

# GET /discon?nodeid=
@app.route("/discon", methods=["GET"])
def get_discon():
    nodeid = request.args.get("nodeid")
    if nodeid != "":
        try:
            nodeid = int(nodeid)
        except:
            print("\nFail to int(nodeid)")

        global util
        if util.global_q.qsize() == 0:
            util.global_q.put("exit")
            print("\nGET: discon")

    return "discon, nodeid: {}".format(nodeid)

data = {}
data['mins'] = index
data['msgs'] = ['<br>1. O | 油壓 | port ' + str(socket_port) + ' 有心跳',
    '<br>2. O | 油壓 | python3 /home/oem/Socket_2020/' + str(socket_port) + ' 有服務'
]
data['mobile_db_name'] = 'mobile_3'
data['mobile_db_id'] = '3'
data['history_db_name'] = 'history_3'

if socket_port != 0:
    threading.Thread(target=util.launch_socket, args=(data,)).start()
    time.sleep(0.5)
    app.run(host="0.0.0.0", port=http_port, debug=True, use_reloader=False)
else:
    print("%%% SET [socket_port] and [http_port] BEFORE STARTING SERVICE %%%")
