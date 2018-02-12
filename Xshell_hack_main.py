# -*- coding: utf-8 -*-

from entryboard import *
import time
import RPi.GPIO as GPIO
import ipget
from time import sleep
import paho.mqtt.client as mqtt
from transitions import Machine
import re
import json
import random

LEDS = [LED1, LED2, LED3, LED4]
COLOR_LEDS = [LED5_R, LED5_G, LED5_B]
HOST = 'yutakaneji.com'
PORT = 1883
KEEP_ALIVE = 60
PUBLISH_NUMBER = 2
SLEEP_TIME = 2
IS_RUNNING = True

CLIENT = mqtt.Client(protocol=mqtt.MQTTv311)

_topic = ''
_ipaddress = ""

_app_states = ['disconnected', 'mqtt_connected', 'viewer_connected', 'closing']
_transitions = [
    {'trigger': 'con_mqtt', 'source': 'disconnected', 'dest': 'mqtt_connected'},
    {'trigger': 'con_viewer', 'source': 'mqtt_connected', 'dest': 'viewer_connected'},
    {'trigger': 'discon', 'source': 'viewer_connected', 'dest': 'closing'}
]
_app_machine = Machine(states=_app_states, transitions=_transitions, initial='disconnected')

_color_led_state = [False, False, False]


def start():
    global CLIENT
    global _ipaddress
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LEDS, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(COLOR_LEDS, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(BUZZER, GPIO.OUT)
    bz = GPIO.PWM(BUZZER, 1000)
    bz.start(50)
    time.sleep(1)
    bz.stop()
    
    CLIENT.on_connect = on_connect
    CLIENT.on_message = on_message
    CLIENT.connect(HOST, port=PORT, keepalive=KEEP_ALIVE)
    ip = ipget.ipget()
    
    # ipaddress = ip.ipaddr("wlan0") #つながってないとエラーになる
    _ipaddress = ip.ipaddr("eth0")
    print _ipaddress
    return


# MQTTに接続したら呼ばれる
def on_connect(client, userdata, flags, respons_code):
    global _topic
    print('status {0}'.format(respons_code))
    _app_machine.con_mqtt()
    
    my_id = re.split('[,._/]', _ipaddress)[2:4]
    _topic = str(my_id[0] + '-' + my_id[1])
    client.subscribe(_topic)


def on_message(client, userdata, message):
    global IS_RUNNING
    try:
        json_string = str(message.payload)
        print json_string
        
        temp_json = json.loads(json_string)
        temp_command = temp_json['command']
        
        if _app_machine.state == 'mqtt_connected':
            if temp_command == 'received':
                _app_machine.con_viewer()
            else:
                print "not valid command at mqtt state"
        
        elif _app_machine.state == 'viewer_connected':
            if temp_command == 'shutdown':
                _app_machine.discon()
                IS_RUNNING = False
            elif 'led' in temp_command:
                if 'R' in temp_command:
                    _color_led_state[0] = not _color_led_state[0]
                    GPIO.output(LED5_R, _color_led_state[0])
                elif 'G' in temp_command:
                    _color_led_state[1] = not _color_led_state[1]
                    GPIO.output(LED5_G, _color_led_state[1])
                
                elif 'B' in temp_command:
                    _color_led_state[2] = not _color_led_state[2]
                    GPIO.output(LED5_B, _color_led_state[2])
            
            else:
                print "not valid command at viewer state"
        
        else:
            pass
            # IS_RUNNING = False
    except Exception as e:
        print "error while json parsing onmessage"
        # print e


def loop():
    global CLIENT
    print "app_sate: ", _app_machine.state
    if _app_machine.state == 'mqtt_connected':
        sendJson = {"my_id": _topic}
        CLIENT.publish('nominate', str(sendJson).replace("'", '"'))
        time.sleep(1)
    elif _app_machine.state == 'viewer_connected':
        print "loping, press ctr-C to stop"
        for l in LEDS:
            GPIO.output(l, 1)
            time.sleep(0.5)
            GPIO.output(l, 0)
        #センサーのあたいとしてダミーデータを送る
        base_temperature = 25.0 if "13" in _topic else 50.0
        current_temperature = base_temperature + (random.randint(-20, 20) / 10)
        sendJson = {"temperature": current_temperature, "my_id": _topic}
        CLIENT.publish("viewer", str(sendJson).replace("'", '"'))
    return


def on_application_quit():
    global CLIENT
    GPIO.cleanup(BUZZER)
    GPIO.cleanup(LEDS)
    GPIO.cleanup(COLOR_LEDS)
    CLIENT.disconnect()
    print "***** Application stopped *****"
    return


# 　以下はいわばフレームワークのように使うので、原則として修正は行わない
if __name__ == '__main__':
    start()
    try:
        while CLIENT.loop() == 0 and IS_RUNNING:
            loop()
        on_application_quit()
    except KeyboardInterrupt:
        on_application_quit()
