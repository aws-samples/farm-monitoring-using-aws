'''
 * Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
 * OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 '''



from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTShadowClient
 
import datetime, sys, time, logging, os, random,json

#btlewrap is wrapper around different bluetooth low energy backends
from btlewrap import available_backends, BluepyBackend, GatttoolBackend, PygattBackend

#miflora - Library for Xiaomi Mi plant sensor
from miflora.miflora_poller import MiFloraPoller, \
    MI_CONDUCTIVITY, MI_MOISTURE, MI_LIGHT, MI_TEMPERATURE, MI_BATTERY
from miflora import miflora_scanner
 

UP_FREQ =1 #Upload frequency of the Raspberrypi gateway
max_timeout = 360000   # [in seconds] # 10mins 


#MAC address of the MiFlora sensors
mac=["C4:7C:8D:XX:XX:XX","C4:7C:8D:YY:YY:YY","C4:7C:8D:ZZ:ZZ:ZZ","C4:7C:8D:XY:XY:XY"]

# Custom MQTT message callback
def customCallback(client, userdata, message):
        pass
        print("Received a new message: ")
        print(message.payload)
        print("from topic: ")
        print(message.topic)
        print("--------------\n\n")

# Custom MQTT message callback for shadow get
def customCallback_shadow(payload, responseStatus, token):
        print("Received a new shadow message: ")
        print(payload)
        print("--------------\n\n")
        payloadDict = json.loads(payload)
        print("++++++++SHADOW++++++++++")
        print("Up Freq:"+ str(payloadDict["state"]["desired"]["UploadFrequency"]))
        print("version: " + str(payloadDict["version"]))
        print("+++++++++++++++++++++++\n\n")
        global UP_FREQ
        UP_FREQ = payloadDict["state"]["desired"]["UploadFrequency"]
         
        #return UP_FREQ

#Custom MQTT message callback for shadow delta
def customShadowCallback_Delta(payload, responseStatus, token):
        # payload is a JSON string ready to be parsed using json.loads(...)
        # in both Py2.x and Py3.x
        print(responseStatus)
        print(payload)
        payloadDict = json.loads(payload)
        print("++++++++DELTA++++++++++")
        print("Up Freq:"+ str(payloadDict["state"]["UploadFrequency"]))
        print("version: " + str(payloadDict["version"]))
        print("+++++++++++++++++++++++\n\n")
        global UP_FREQ
        UP_FREQ = payloadDict["state"]["UploadFrequency"]
        

#Get Miflora sensor values
def getSensorData(mac_address):
    data = {}
    backend=GatttoolBackend
    
    mac =mac_address
    poller = MiFloraPoller(mac,backend)
    print("Getting data from Mi Flora")
    
    if mac == "C4:7C:8D:XX:XX:XX":
        sensorname = "Sensor1"
    elif mac == "C4:7C:8D:YY:YY:YY":
        sensorname ="Sensor2"
    elif mac == "C4:7C:8D:ZZ:ZZ:ZZ":
        sensorname ="Sensor3"
    elif mac == "C4:7C:8D:XY:XY:XY":
        sensorname ="Sensor4"
    else:
        sensorname="Unknown"


    data['Name'] = sensorname
    data['Temperature'] = format(poller.parameter_value(MI_TEMPERATURE))
    data['Moisture'] = format(poller.parameter_value(MI_MOISTURE))
    data['Light'] = format(poller.parameter_value(MI_LIGHT))
    data['Conductivity'] = format(poller.parameter_value(MI_CONDUCTIVITY))
    data['Battery'] = format(poller.parameter_value(MI_BATTERY))
    data['DateTime'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return data



# For certificate based connection
iot = AWSIoTMQTTClient('iot-data');
iot_shadow = AWSIoTMQTTShadowClient('iot-shadow');


# For TLS mutual authentication
iot.configureEndpoint("YOUR.ENDPOINT", 8883)
iot_shadow.configureEndpoint("YOUR.ENDPOINT", 8883)

iot.configureCredentials("YOUR/ROOT/CA/PATH", "YOUR/PRIAVTEKEY/PATH", "YOUR/CERTIFICATE/PATH")
iot_shadow.configureCredentials("YOUR/ROOT/CA/PATH", "YOUR/PRIAVTEKEY/PATH", "YOUR/CERTIFICATE/PATH")



iot.configureAutoReconnectBackoffTime(1, 32, 20)
iot.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
iot.configureDrainingFrequency(2)  # Draining: 2 Hz
iot.configureConnectDisconnectTimeout(10)  # 10 sec
iot.configureMQTTOperationTimeout(5)  # 5 sec

iot_shadow.configureAutoReconnectBackoffTime(1, 32, 20)
iot_shadow.configureConnectDisconnectTimeout(10)  # 10 sec
iot_shadow.configureMQTTOperationTimeout(5)  # 5 sec

# Configure logging
logger = logging.getLogger("AWSIoTPythonSDK.core")
logger.setLevel(logging.INFO)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)



iot.connect()
iot_shadow.connect()
iot.subscribe("farmbot/", 1, customCallback)


# Create a deviceShadow with persistent subscription
Bot = iot_shadow.createShadowHandlerWithName("Bot", True)

#shadowCallbackContainer_Bot = shadowCallbackContainer(Bot)

Bot.shadowGet(customCallback_shadow,5)

# Listen on deltas
Bot.shadowRegisterDeltaCallback(customShadowCallback_Delta)


timeout_start = time.time()
while time.time() < timeout_start + max_timeout:
    try:  
        
        for x in range (4): 
            time.sleep(UP_FREQ)
            data = json.dumps(getSensorData(mac[x]))
            print("--------------\n")
            print("message payload:"+data+"\n")
            response = iot.publish(
                topic='farmbot/',
                payload=data,
                QoS=1
            )
    except Exception as ex:
        print (ex)
        pass        
        
        
time.sleep(3)

iot.disconnect()
 
