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

class Utils:
  def __init__(self, http_port,socket_port, db_name, db_user):
    self.ip = '219.68.111.4'
    self.socket_port = socket_port
    self.http_port = http_port
    self.response = ""
    self.comp_res = False
    self.db_name = db_name
    self.db_user = db_user
    self.global_q = qu.Queue()
    self.port_info =  "\nsocket_port:{}, http_port:{}\n".format(socket_port, http_port)
    self.line_url = 'https://maker.ifttt.com/trigger/alarm/with/key/dangI5_PO9KBF65pU04RXNUfwOBvvdeaiC7cES-YYsc'
  
  def go_to_log(self, e):
    log_path = "./Oil-{}.log".format(self.socket_port)
    with open(log_path, "a", newline="") as f:
        f.write(str(e))
  
  def getVol(self, res):
    vol = int(res[10:12], 16)
    volDec = int(res[12:14], 16)
    voltage = (vol + (volDec << 8)) / 100

    return round(voltage, 4)
  
  def checksum(self):
    if len(self.response) == 8:
        if sum(self.response[1:-1]) & 0xFF == self.response[-1]:
            self.comp_res = True
  
  def sendLine(self, msg):
    payload = {'value1': msg}
    requests.post(self.line_url, data=payload)

  def db_connect(self):
    self.db = pymysql.connect(
      host="mysql", user=self.db_user, passwd="gridwell123", db=self.db_name, charset="utf8"
    )
    self.cursor = self.db.cursor()

  def db_commit(self):
    self.db.commit()
    self.db.close()

  def handleChat(self, conn, addr, d):
    print("\nConnected by {}\n".format(addr))
    res_time = 0

    start = datetime.now()
    nxt = datetime(start.year, start.month, start.day, 8, d['mins'])

    if start > nxt:
        nxt += timedelta(days=1)

    while 1:
        # Handle Response
        time_start = time.time()
        data = conn.recv(11)
        if time.time() - time_start >= 60 * 9 + 30:
            line_message('超過10分鐘未收到心跳封包"w"')
        start = datetime.now()
        if start > nxt:
            nxt = datetime(start.year, start.month, start.day, 8, d['mins'])
            nxt += timedelta(days=1)

            threading.Thread(target=self.sendLine, args=(d['msgs'][0])).start()
            threading.Thread(target=self.sendLine, args=(d['msgs'][1])).start()

        time.sleep(0.1)

        if len(data) > 1 and data[1] != b"\x7E":
            self.response = data

        self.checksum()
        if self.comp_res:  # Means checksum is correct
            try:
                res = "".join("{:02x}".format(d) for d in self.response)
                print(res_time, time.time())
                
                if time.time() - res_time <= 10 and int(res[4:6], 16) == 3:
                    # Define MySQL Config (IP, username, password, DB name)
                    self.db_connect()

                    # Check D3 and voltage
                    vol = self.getVol(res)
                    # Get Node ID from payload
                    ## node_id = int(res[2:4], 16)
                    # Get D3 status
                    d3 = int(res[6:8], 16)
                    # MySQL SELECT query
                    query = "SELECT `name` FROM `{}` WHERE `{}` = 1".format(d['mobile_db_name'], d['mobile_db_id'])
                    self.cursor.execute(query)

                    node_name = self.cursor.fetchall()[0][0]
                    # MySQL INSERT query
                    query = "INSERT INTO `{}` (`name`, `record`) VALUES ('{} 油壓訊號', '接點訊號：{} 電池電壓：{}V')".format(d['history_db_name'], node_name, d3, vol)

                    self.cursor.execute(query)
                    self.db_commit()
                    # Line message
                    msg = (
                        '<br>{} 油壓訊號<br>接點訊號：{}<br>電池電壓：{}V<br>詳見：http://oil.iotwebhub.net/Oil'.format(node_name, d3, vol)
                    )

                    self.go_to_log(msg)

                if int(res[4:6], 16) == 3:
                    self.response = ""
                    res_time = time.time()
            except:
                print("Error code 03\n")
                print(traceback.format_exc())
                self.go_to_log("Error code 03")
                self.go_to_log(traceback.format_exc())

        # For logging
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            d_str = data.decode("ASCII")
            if len(d_str) > 0:
                if d_str != "w":
                    log_str = "\n{} | Recv: {} | {}".format(now_str, d_str, "".join("{:02x}".format(d) for d in data))
                    self.go_to_log(log_str)
                    self.go_to_log(self.port_info)
                else:
                    self.go_to_log(d_str)  # "w" (0x77)
        except:
            hex_str = ":".join("{:02x}".format(d) for d in data)
            print("\nRAW: {}\n".format(hex_str))
            self.go_to_log("\n{} | {}{}".format(now_str, hex_str, self.port_info))

        # Handle command sending
        if self.global_q.qsize() > 0:
            msg = self.global_q.get()
            print("msg", msg)
            if msg == "exit":
                conn.send(msg.encode())
                time.sleep(1)
                conn.close()
                break
            else:
                conn.send(msg)

        # Make sure checksum checked
        self.comp_res = False
    # End of while 1
    print("connection closed")


    # For threading launch
  def launch_socket(self, data):
    HOST = "0.0.0.0"
    PORT = self.socket_port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.settimeout(60 * 10)
    s.bind((HOST, PORT))
    s.listen(5)
    # Logging
    print("\n***** socket launched")
    print(" ***** {}\n".format(self.port_info))
    self.go_to_log("\n***** socket launched")
    self.go_to_log(" ***** {}\n".format(self.port_info))
    
    while True:
        connection, client_address = s.accept()
        connection.settimeout(60 * 10)
        threading.Thread(
            target=self.handleChat,
            args=(
                connection,
                client_address,
                data
            ),
        ).start()
  
  @staticmethod
  def gen_cmd(nodeid, cmd_key):
    cmd = b"\x7E" + nodeid.to_bytes(1, "big") + cmd_key
    checksum = (sum(cmd[1:]) & 0xFF).to_bytes(1, "big")
    cmd += checksum

    return cmd