from concurrent.futures import ThreadPoolExecutor
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.gen
import threading
import asyncio
import socket
import numpy as np
import imutils
import copy
import time
import cv2
import os

# bind all IP
HOST = '0.0.0.0' 
# Listen on Port 
PORT = 3333 
#Size of receive buffer   
BUFFER_SIZE = 100000

lock = threading.Lock()
connectedDevices = dict()

executor = ThreadPoolExecutor(max_workers=4)

def decodeJpg(data, client):
    decoded = cv2.imdecode(np.frombuffer(
        data, dtype=np.uint8), cv2.IMREAD_COLOR)
    frame = imutils.rotate_bound(decoded, 90)
    (flag, encodedImage) = cv2.imencode(".jpg", frame)

    # ensure the frame was successfully encoded
    if not flag:
        return
    connectedDevices[client] = data

def udp_server():   
    # Create a TCP/IP socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Bind the socket to the host and port
    s.bind((HOST, PORT))
    asyncio.set_event_loop(asyncio.new_event_loop())
    while True:
        # Receive BUFFER_SIZE bytes data
        # data is a list with 2 elements
        # first is data
        #second is client address
        data = s.recvfrom(BUFFER_SIZE)
        if data:
            tornado.ioloop.IOLoop.instance().run_in_executor(None, lambda: decodeJpg(data[0], data[1]))
    # Close connection
    s.close()


class StreamHandler(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def get(self, slug):
        self.set_header(
            'Cache-Control', 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0')
        self.set_header('Pragma', 'no-cache')
        self.set_header(
            'Content-Type', 'multipart/x-mixed-replace;boundary=--jpgboundary')
        self.set_header('Connection', 'close')

        my_boundary = "--jpgboundary"
        client = None
        for c in connectedDevices.keys():
            if str(c) == slug:
                print(slug)
                client = c
                break
        while client is not None:
            jpgData = connectedDevices[client]
            if jpgData is None:
                print("empty frame")
                continue
            self.write(my_boundary)
            self.write("Content-type: image/jpeg\r\n")
            self.write("Content-length: %s\r\n\r\n" % len(jpgData))
            self.write(jpgData)
            yield self.flush()


class TemplateHandler(tornado.web.RequestHandler):
    def get(self):
        deviceIds = [str(d) for d in connectedDevices]
        print("devices: {}".format(deviceIds))
        self.render(os.path.sep.join(
            [os.path.dirname(__file__), "templates", "index.html"]), url="http://localhost:3000/video_feed/", deviceIds=deviceIds)


application = tornado.web.Application([
    (r'/video_feed/([^/]+)', StreamHandler),
    (r'/', TemplateHandler),
])


if __name__ == "__main__":
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(3000)
    myIP = socket.gethostbyname(socket.gethostname())
    print('***Server Started at %s***' % myIP)
    tornado.ioloop.IOLoop.current().run_in_executor(executor, udp_server)
    tornado.ioloop.IOLoop.current().start()
