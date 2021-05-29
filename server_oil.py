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

### Diff between Oil servers:
### 1. socket_port & http_port
### 2. MySQL SELECT query
### 3. gen_cmd(nodeid, b"\x01\x__") (__ = id + 1, ex: id = 1 => 02)
### 4. sendDaily msg

socket_port = [ 3107, 3110 ]
http_port = [ 3207, 3210 ]
sent_msg = [ '0102', '0102']

Line_url = "https://maker.ifttt.com/trigger/Demo/with/key/iMHP9IsfpS0DbbDCMJmro16spw7fdOZxl5te3bC2eb6"


def port_info(index):
    return "\nsocket_port:{}, http_port:{}\n".format(socket_port[index], http_port[index])


def go_to_log(e, index):
    log_path = "./recv_p{}.log".format(socket_port[index])
    with open(log_path, "a", newline="") as f:
        f.write(str(e))


def getVol(res):
    vol = int(res[10:12], 16)
    volDec = int(res[12:14], 16)
    voltage = (vol + (volDec << 8)) / 100

    return round(voltage, 4)


def sendLine(msg):
    url = Line_url
    payload = {"value1": "{}".format(msg)}
    requests.post(url, data=payload)


def sendDaily(msg):
    url = "https://maker.ifttt.com/trigger/Offline/with/key/gGxGAp8lK5x806_GrrJO6LIvLctRATq3cnd_bN73zxC"
    payload = {"value1": "{}".format(msg)}
    requests.post(url, data=payload)


def line_message(mes,index):
    print("Offline warning!")
    curl = (
        'curl -X POST -H "Content-Type: application/json" -d \'{"value1": "%s", "value2": "%d", "value3": "%s"}\' https://maker.ifttt.com/trigger/Offline/with/key/gGxGAp8lK5x806_GrrJO6LIvLctRATq3cnd_bN73zxC'
        % ("111.185.9.227", http_port[index], mes)
    )
    os.system(curl)





global_q = qu.Queue()
response = ""
res_03 = ""
comp_res = False


def handleChat(conn, addr, index):
    global response
    print("\nConnected by {}\n".format(addr))
    res_time = 0

    start = datetime.now()
    nxt = datetime(start.year, start.month, start.day, 8, index)

    if start > nxt:
        nxt += timedelta(days=1)

    while 1:
        # Handle Response
        global response, res_03, comp_res

        time_start = time.time()
        data = conn.recv(11)
        if time.time() - time_start >= 60 * 9 + 30:
            line_message('超過10分鐘未收到心跳封包"w"',index)

        start = datetime.now()
        if start > nxt:
            nxt = datetime(start.year, start.month, start.day, 8, index)
            nxt += timedelta(days=1)

            if data == b"w":
                msg = "<br>5. O | 油壓 | port " + str(socket_port[index]) + " 有心跳"
                threading.Thread(target=sendDaily, args=(msg,)).start()
            msg = "<br>6. O | 油壓 | python3 /home/oem/Socket_2020/server_p"+str(socket_port[index])+".py 有服務"
            threading.Thread(target=sendDaily, args=(msg,)).start()

        time.sleep(0.1)
        if len(data) > 1:
            if data[1] != b"\x7E":
                response = data

        checksum()
        if comp_res:  # Means checksum is correct
            try:
                res = response
                res = "".join("{:02x}".format(d) for d in res)

                print(res_time, time.time())
                if time.time() - res_time <= 10 and int(res[4:6], 16) == 3:
                    print("Code 03:", res)
                    res_03 = res
                    # Define MySQL Config (IP, username, password, DB name)
                    db_mob = pymysql.connect(
                        host="localhost", user="oil", passwd="gridwell123", db="Oil", charset="utf8"
                    )
                    cur_mob = db_mob.cursor()

                    # Check D3 and voltage
                    vol = getVol(res)
                    # Get Node ID from payload
                    ## node_id = int(res[2:4], 16)
                    # Get D3 status
                    d3 = int(res[6:8], 16)
                    # MySQL SELECT query
                    query = "SELECT `name` FROM `mobile_1` WHERE `id` = "+str(index+1)
                    cur_mob.execute(query)
                    node_name = cur_mob.fetchall()[0][0]
                    # MySQL INSERT query
                    query = (
                        "INSERT INTO `history_1` (`name`, `record`) "
                        + "VALUES ('{} 油壓訊號', '接點訊號：{} 電池電壓：{}V".format(node_name, d3, vol)
                        + "')"
                    )
                    cur_mob.execute(query)
                    db_mob.commit()
                    db_mob.close()
                    # Line message
                    msg = (
                        "<br>{} 油壓訊號<br>接點訊號：{}<br>電池電壓：{}V".format(node_name, d3, vol)
                        + "<br>詳見：http://oil.iotwebhub.net/Oil"
                    )
                    threading.Thread(target=sendLine, args=(msg,)).start()

                    go_to_log(msg,index)

                if int(res[4:6], 16) == 3:
                    response = ""
                    res_time = time.time()

            except:
                print("Error code 03\n")
                print(traceback.format_exc())
                go_to_log("Error code 03", index)
                go_to_log(traceback.format_exc(), index)

        # For logging
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            d_str = data.decode("ASCII")
            if len(d_str) > 0:
                if d_str != "w":
                    log_str = "\n{} | Recv: {} | {}".format(now_str, d_str, "".join("{:02x}".format(d) for d in data))
                    go_to_log(log_str, index)
                    go_to_log(port_info(index), index)
                else:
                    go_to_log(d_str, index)  # "w" (0x77)
        except:
            hex_str = ":".join("{:02x}".format(d) for d in data)
            print("\nRAW: {}\n".format(hex_str))
            go_to_log("\n{} | {}{}".format(now_str, hex_str, port_info(index)), index)

        # Handle command sending
        global global_q
        if global_q.qsize() > 0:
            msg = global_q.get()
            print("msg", msg)
            if msg == "exit":
                conn.send(msg.encode())
                time.sleep(1)
                conn.close()
                break
            else:
                conn.send(msg)

        # Make sure checksum checked
        comp_res = False
    # End of while 1
    print("connection closed")


# For threading launch
def launch_socket(index):
    HOST = "0.0.0.0"
    PORT = socket_port[index]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.settimeout(60 * 10)
    s.bind((HOST, PORT))
    s.listen(5)
    # Logging
    print("\n***** socket launched")
    print(" ***** {}\n".format(port_info(index)))
    go_to_log("\n***** socket launched", index)
    go_to_log(" ***** {}\n".format(port_info(index)), index)

    while True:
        connection, client_address = s.accept()
        connection.settimeout(60 * 10)
        threading.Thread(
            target=handleChat,
            args=(
                connection,
                client_address,
                index
            ),
        ).start()


def gen_cmd(nodeid, cmd_key):
    cmd = b"\x7E" + nodeid.to_bytes(1, "big") + cmd_key
    checksum = (sum(cmd[1:]) & 0xFF).to_bytes(1, "big")
    cmd += checksum

    return cmd


comp_res = False


def checksum():
    global response, comp_res
    if len(response) == 8:
        # print(":".join("{:02x}".format(c) for c in response))
        # print(hex(sum(response[1:-1]) & 0xFF))
        if sum(response[1:-1]) & 0xFF == response[-1]:
            comp_res = True


# End of Socket function define

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

        global global_q
        if global_q.qsize() == 0:

            cmd = gen_cmd(nodeid, bytes.fromhex(sent_msg[index]))
            global_q.put(cmd)
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

        global response, comp_res
        checksum()
        res = ""
        if comp_res:  # Means checksum is correct
            res = response
            res = "".join("{:02x}".format(d) for d in res)
            response = ""
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

        global global_q
        if global_q.qsize() == 0:
            global_q.put("exit")
            print("\nGET: discon")

    return "discon, nodeid: {}".format(nodeid)


atexit.register(line_message, "伺服程式被迫中斷")
app.run(host="0.0.0.0", port=8306, debug=True, use_reloader=False)

for index in range(4):
    if socket_port[index] != 0:
        threading.Thread(target=launch_socket, args=(index, )).start()
        time.sleep(0.5)
    else:
        print("%%% SET [socket_port] and [http_port] BEFORE STARTING SERVICE %%%")