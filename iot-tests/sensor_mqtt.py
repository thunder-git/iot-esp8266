# clean.py Test of asynchronous mqtt client with clean session.
# (C) Copyright Peter Hinch 2017-2019.
# Released under the MIT licence.

# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers

# The use of clean_session means that after a connection failure subscriptions
# must be renewed (MQTT spec 3.1.2.4). This is done by the connect handler.
# Note that publications issued during the outage will be missed. If this is
# an issue see unclean.py.

# red LED: ON == WiFi fail
# blue LED heartbeat: demonstrates scheduler is running.

from mqtt_as import MQTTClient, config
from config import wifi_led, blue_led  # Local definitions
import uasyncio as asyncio
from bmp180 import BMP180
from machine import I2C, Pin, RTC
import ntptime
import utime

PUB_TOPIC = 'home/room1/sensor1'

# Subscription callback
def sub_cb(topic, msg, retained):
    print((topic, msg, retained))

# Demonstrate scheduler is operational.
async def heartbeat():
    s = True
    while True:
        await asyncio.sleep_ms(500)
        blue_led(s)
        s = not s

async def wifi_han(state):
    wifi_led(not state)
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    await client.subscribe('foo_topic', 1)

async def main(client):
    # configure I2C bus and BMP180 sensor
    i2c_bus = I2C(scl=Pin(5), sda=Pin(4), freq=1000000)
    bmp180 = BMP180(i2c_bus)
    bmp180.oversample_sett = 2
    bmp180.baseline = 101325
    
    # configure local time
    ntptime.settime()
    rtc = RTC()
    try:
        await client.connect()
    except OSError:
        print('Connection failed.')
        return
    n = 0
    while True:
        await asyncio.sleep(5)
        sensor_temp = bmp180.temperature
        sensor_press = bmp180.pressure/100
        print('publish', n, ' temperature:', sensor_temp, ', pressure:', sensor_press)
        payload = """
        {{
            "temperature": {},
            "pressure": {}
        }}
        """
        time = str(946684800 + utime.mktime((rtc.datetime()[0], rtc.datetime()[1], rtc.datetime()[2], rtc.datetime()[4], rtc.datetime()[5], rtc.datetime()[6], 0, 0)))
        tag = 'sensor1'
        # If WiFi is down the following will pause for the duration.
        await client.publish(PUB_TOPIC, payload.format(sensor_temp, sensor_press), qos = 1)
        n += 1

# Define configuration
config['subs_cb'] = sub_cb
config['wifi_coro'] = wifi_han
config['connect_coro'] = conn_han
config['clean'] = True
       
# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)

loop = asyncio.get_event_loop()
loop.create_task(heartbeat())
try:
    loop.run_until_complete(main(client))
finally:
    client.close()  # Prevent LmacRxBlk:1 errors
