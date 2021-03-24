#! /usr/bin/python3
# Binh Nguyen, Feb 24, 2020
# python interface to work with SDS011 air quality sensor


import time
import serial
import os
import json
import socket
import paho.mqtt.publish as publish
import requests
from requests.auth import HTTPBasicAuth


#os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
#time.tzset()

# MQTT host, users
mqtt = '192.168.1.100'  # change this
topic = 'sensor/sds011' # and this
auth = {'username': 'mqtt_user', 'password': 'mqtt_password'} # and these two

# Domoticz host
domoticzserver="127.0.0.1:8080" # change Domoticz server address
domoticzusername = "" # and username
domoticzpassword = "" # and password
device_index_pm25 = 1 # change to idx of PM2.5 custom sensor
device_index_pm10 = 2 # change to idx of PM10 custom sensor

def time_(): return int(time.time())


def datetime_():
    return time.strftime('%x %X', time.localtime())


def p_print(binstr):
    '''return a easy to read heximal string'''
    return ' '.join([f'{x:02x}' for x in binstr])


def host_folder():
    """designate a folder to save each month"""
    this_month_folder = time.strftime('%b%Y')
    basedir = os.path.abspath(os.path.dirname(__file__))
    basedir = '/'.join(basedir.split('/')[: -1])
    all_dirs = [d for d in os.listdir(basedir) if os.path.isdir(d)]
    if len(all_dirs) == 0 or this_month_folder not in all_dirs:
        os.makedirs(this_month_folder)
        print('created: {}'.format(this_month_folder))
    return os.path.join(basedir, this_month_folder)


def internet_ready():
    '''check if internet connect is ready'''
    try:
        _ = socket.create_connection((mqtt, 1883), 3)
        return True
    except Exception as e:
        print("Error {}".format(e))
        return False


def record_data(data):
    id_, pm25, pm10 = data
    id_ = f'sds011_{id_}'
    payload = f'{datetime_()},{id_},{pm25},{pm10}\n'
    print(f'saved: {payload.strip()}')
    filename = os.path.join(host_folder(), f'{id_}.csv')
    with open(filename, 'a+') as f:
        f.write(payload)
    return None


def push_mqtt_server(data):
    id_, pm25, pm10 = data
    id_ = f'sds011_{id_}'
    header = ['time', 'sensor', 'pm25', 'pm10']
    payload = dict(zip(header, [datetime_(), id_, pm25, pm10]))
    payload['type'] = 'json'
    print(f'pushed: {payload}')
    payload = json.dumps(payload)

    try:
        if internet_ready():
            publish.single(topic, payload, hostname=mqtt, auth=auth)
    except Exception as e:
        print('Error: {}'.format(e))
        pass
    return None

def push_domo_server(data):
    id_, pm25, pm10 = data
    id_ = f'sds011_{id_}'
    header = ['time', 'sensor', 'pm25', 'pm10']
    domoticz_url = format("http://%s/json.htm?type=command&param=udevice&idx=%s&nvalue=0&svalue=%s"
        %(
        domoticzserver, 
        device_index_pm25, 
        pm25, 
        ))	
    try:
        resp = requests.get(domoticz_url, auth=HTTPBasicAuth(domoticzusername, domoticzpassword))
    except requests.HTTPError as e:
        print("Domoticz HTTP error", e.reason)
    except requests.ConnectionError:
        print("Domoticz Request failed!")
    else:
        if resp.status_code == 200:
            print("Domoticz PM2.5 update successfull!")
        else:
            print("domoticz PM2.5 update failed:", resp.status_code)
    domoticz_url = format("http://%s/json.htm?type=command&param=udevice&idx=%s&nvalue=0&svalue=%s"
        %(
        domoticzserver, 
        device_index_pm10, 
        pm10, 
        ))	
    try:
        resp = requests.get(domoticz_url, auth=HTTPBasicAuth(domoticzusername, domoticzpassword))
    except requests.HTTPError as e:
        print("Domoticz HTTP error", e.reason)
    except requests.ConnectionError:
        print("Domoticz Request failed!")
    else:
        if resp.status_code == 200:
            print("Domoticz PM10 update successfull!")
        else:
            print("domoticz PM10 update failed:", resp.status_code)
    return None



class SDS011(object):
    '''attributes for the SDS011 sensors'''
    HEAD = 0xaa
    cmdID = 0xb4
    b1 = 0x02
    b2 = 0x00
    b3 = 0x00
    TAIL = 0xab
    FILL = [0x00]*10

    '''attribute to operate and record data'''

    lastSample = 0
    lastFanOn = 0
    name = 'sds'

    def __init__(self, port, name=name, interval=60, save_data=True, push_mqtt=False, push_domo=False):
        '''initiate a serial port object'''

        self.port = port
        self.name = name
        self.INVL = interval
        self.save_data = save_data
        self.push_mqtt = push_mqtt
        self.push_domo = push_domo
        self.passive = False
        self.isFanOn = False
        # self.INVL = INVL
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=9600,
                timeout=2)
        except serial.SerialException as e:
            print(f'Time: {time.ctime()} {e}')

    def __repl__(self):
        return f'{self.name}, fan: {self.isFanOn}, last sample {self.lastSample}, last turn fan on {self.lastFanOn}'

    def _check_sum(self, bytes_):
        '''total return value == ckc value'''
        # print(f'Checksum: {bytes_}')
        calc = 0
        calc = sum(bytes_[2:-2])
        calc = calc & 0xFF

        if bytes_[-2] != calc:
            print('Unmatched CHECKSUM')
            return False
        return True

    def _call_mode(self, cmd):
        '''available mode or cmd or SDS011'''

        cmd_dict = {
            'set_active': [2, 1, 0],
            'set_query': [2, 1, 1],
            'query_data': [4, 0, 0],
            'set_sleep': [6, 1, 0],
            'set_work': [6, 1, 1],
            'check_mode': [2, 0, 0],
            'check_fan_sleep': [6, 0, 0],
            'check_fan_work': [6, 0, 1],
            # the third element 1-30 (minutes)
            'set_working_period': [8, 1, 2],
            'check_firmware': [7, 0, 0],

        }
        avail_modes = list(cmd_dict.keys())
        if not cmd in avail_modes:
            return print(f'this mode is not available. Try keywords: {avail_modes}')

        for key, value in cmd_dict.items():
            if key == cmd:
                cmd_id = value
                # print(f'Sending cmd: {cmd} with value {value}')
                return self._build_cmd(cmd_id)

    def _build_cmd(self, cmd_id, id_=None):
        '''convert int mode to bytearrays'''

        assert len(cmd_id) == 3, print('required 3 bytes')
        cmd = [0xAA, 0xB4]
        [cmd.append(i) for i in cmd_id]
        [cmd.append(i) for i in SDS011.FILL]
        if id_ is None:
            cmd.append(0xFF)
            cmd.append(0xFF)
        else:
            cmd.append(id_[0])
            cmd.append(id_[1])

        ckc = sum(cmd[2:])
        cmd.append(ckc & 0xFF)  # take the lower 8bits of Checksum
        cmd.append(SDS011.TAIL)
        return cmd

    def _send_cmd(self, cmd=None):
        '''send command to the sensor'''
        try:
            self.ser.reset_output_buffer()
            time.sleep(0.1)
            self.ser.write(cmd)
            # print(f'{p_print(cmd)}')
        except Exception as e:
            print(f'Exp as {e}')
        return None

    def _read_response(self, bytes_):
        '''read coming bytes and match with defined output'''
        ID = f'{bytes_[6]:02X}{bytes_[7]:02X}'
        cmdID = bytes_[1]
        status = [bytes_[2], bytes_[3], bytes_[4]]
        # print(f'ID: {ID}, cmdID: {cmdID:02X} with status {status}')

        status_dict = {
            'set_active': [2, 0, 0],
            'set_query': [2, 0, 1],
            'set_sleep': [6, 0, 0],
            'set_work': [6, 0, 1]
        }
        if cmdID == 0xc0:
            pm25 = (bytes_[3]*256 + bytes_[2]) / 10.0
            pm10 = (bytes_[5]*256 + bytes_[4]) / 10.0
            return (ID, pm25, pm10)
        if bytes_[2] == 0x07:
            return f'{bytes_[2]}-{bytes_[3]}-{bytes_[4]}'
        for key, value in status_dict.items():
            if value == status:
                return key
        return print('Not found status')

    def _read_serial(self, flush=False):
        ''' read and record with matched heads'''
        # print(f'Bytes in buffer: {self.ser.in_waiting}')
        if flush:
            self.ser.reset_input_buffer()
            time.sleep(3)
        recv = self.ser.read(self.ser.in_waiting)
        recv_matched = b''
        for i, byte in enumerate(recv):
            if byte == SDS011.HEAD:
                recv_matched += recv[i: i+10]
        # print(f'Type: {type(recv_matched)}, length: {len(recv_matched)}')
        if self._check_sum(recv_matched):
            return recv_matched
        return None

    def set_passive(self):
        try:  
            cmd = self._call_mode('set_query')
            # print(f'cmd: {cmd}')
            self._send_cmd(cmd=cmd)
            inp = self._read_serial(flush=True)
            status = self._read_response(inp)
            if status == 'set_query':
                self.passive = True
        except Exception as e:
            print(f'Error: {e}')
            cmd = self._call_mode('set_query')
            self._send_cmd(cmd=cmd)
        return None

    def fan_status(self):
        cmd = self._call_mode('check_fan')
        # print(f'cmd: {cmd}')
        self._send_cmd(cmd=cmd)
        inp = self._read_serial(flush=True)
        status = self._read_response(inp)
        if status == 'set_work':
            self.isFanOn = True
        return None

    def run_passive(self):
        if not self.passive:
            self.set_passive()
            self.passive = True

        if not self.isFanOn:
            if time_() - self.lastSample >= self.INVL:
                # self._send_cmd(SDS011._call_mode('check_fan'))
                cmd = self._call_mode('set_work')
                self._send_cmd(cmd=cmd)
                self.lastFanOn = time_()
                self.isFanOn = True
        if self.isFanOn and time_() - self.lastFanOn >= 20:
            cmd = self._call_mode('query_data')
            self._send_cmd(cmd=cmd)
            resp = self._read_serial(flush=True)
            # print(f'Reasponse from Serial: {resp}')
            if resp is not None:
                data = self._read_response(resp)
                if isinstance(data, tuple):
                    # print(f"PMS data: {data}")
                    if self.name == SDS011.name:
                        self.name, *_ = data
                    if self.save_data:
                        record_data(data)

                    if self.push_mqtt:
                        push_mqtt_server(data)
                    
                    if self.push_domo:
                        push_domo_server(data)

                    self._send_cmd(self._call_mode('set_sleep'))
                    self.lastSample = time_()
                    self.isFanOn = False

        else:
            time.sleep(1)
            # print('-'*40 	)

    def run_query(self):
        if not self.passive:
            self.set_passive()
            self.passive = True

        if not self.isFanOn:
            if time_() - self.lastSample >= self.INVL:
                # self._send_cmd(SDS011._call_mode('check_fan'))
                cmd = self._call_mode('set_work')
                self._send_cmd(cmd=cmd)
                self.lastSample = time_()
                self.isFanOn = True
        if self.isFanOn and time_() - self.lastSample >= self.INVL:
            cmd = self._call_mode('query_data')
            self._send_cmd(cmd=cmd)
            resp = self._read_serial(flush=True)
            # print(f'Reasponse from Serial: {resp}')
            if resp is not None:
                data = self._read_response(resp)
                if isinstance(data, tuple):
                    # print(f"PMS data: {data}")
                    if self.name == SDS011.name:
                        self.name, *_ = data
                    if self.save_data:
                        record_data(data)

                    if self.push_mqtt:
                        push_mqtt_server(data)
                    if self.push_domo:
                        push_domo_server(data)

                    self.lastSample = time_()

        else:
            time.sleep(1)


if __name__ == '__main__':
    p1 = SDS011(port='/dev/ttyUSB1', push_mqtt=True)
    while True:
        p1.run_passive()
    # p1.set_passive()
