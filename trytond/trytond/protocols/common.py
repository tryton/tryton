#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import errno
import os
import socket
import threading
import sys
import gzip
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
from SocketServer import StreamRequestHandler


def endsocket(sock):
    if os.name != 'nt':
        try:
            sock.shutdown(getattr(socket, 'SHUT_RDWR', 2))
        except socket.error, e:
            if e.errno != errno.ENOTCONN:
                raise
        sock.close()


class daemon(threading.Thread):
    def __init__(self, interface, port, secure, name=None):
        threading.Thread.__init__(self, name=name)
        self.secure = secure
        self.ipv6 = False
        for family, _, _, _, _ in socket.getaddrinfo(interface or None, port,
                socket.AF_UNSPEC, socket.SOCK_STREAM):
            if family == socket.AF_INET6:
                self.ipv6 = True
            break

    def stop(self):
        self.server.shutdown()
        self.server.socket.shutdown(socket.SHUT_RDWR)
        self.server.server_close()
        return

    def run(self):
        self.server.serve_forever()
        return True


class RegisterHandlerMixin:

    def setup(self):
        self.server.handlers.add(self)
        StreamRequestHandler.setup(self)

    def finish(self):
        StreamRequestHandler.finish(self)
        try:
            self.server.handlers.remove(self)
        except KeyError:
            pass


class GZipRequestHandlerMixin:

    if sys.version_info[:2] <= (2, 6):
        # Copy from SimpleXMLRPCServer.py with gzip encoding added
        def do_POST(self):
            """Handles the HTTP POST request.

            Attempts to interpret all HTTP POST requests as XML-RPC calls,
            which are forwarded to the server's _dispatch method for handling.
            """

            # Check that the path is legal
            if not self.is_rpc_path_valid():
                self.report_404()
                return

            try:
                # Get arguments by reading body of request.
                # We read this in chunks to avoid straining
                # socket.read(); around the 10 or 15Mb mark, some platforms
                # begin to have problems (bug #792570).
                max_chunk_size = 10 * 1024 * 1024
                size_remaining = int(self.headers["content-length"])
                L = []
                while size_remaining:
                    chunk_size = min(size_remaining, max_chunk_size)
                    L.append(self.rfile.read(chunk_size))
                    size_remaining -= len(L[-1])
                data = ''.join(L)

                data = self.decode_request_content(data)
                if data is None:
                    return  # response has been sent

                # In previous versions of SimpleXMLRPCServer, _dispatch
                # could be overridden in this class, instead of in
                # SimpleXMLRPCDispatcher. To maintain backwards compatibility,
                # check to see if a subclass implements _dispatch and dispatch
                # using that method if present.
                response = self.server._marshaled_dispatch(
                        data, getattr(self, '_dispatch', None)
                    )
            except Exception:  # This should only happen if the module is buggy
                # internal error, report as HTTP server error
                self.send_response(500)
                self.end_headers()
            else:
                # got a valid XML RPC response
                self.send_response(200)
                self.send_header("Content-type", "text/xml")

                # Handle gzip encoding
                if ('gzip' in self.headers.get('Accept-Encoding',
                            '').split(',')
                        and len(response) > self.encode_threshold):
                    buffer = StringIO.StringIO()
                    output = gzip.GzipFile(mode='wb', fileobj=buffer)
                    output.write(response)
                    output.close()
                    buffer.seek(0)
                    response = buffer.getvalue()
                    self.send_header('Content-Encoding', 'gzip')

                self.send_header("Content-length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        def decode_request_content(self, data):
            #support gzip encoding of request
            encoding = self.headers.get("content-encoding", "identity").lower()
            if encoding == "identity":
                return data
            if encoding == "gzip":
                f = StringIO.StringIO(data)
                gzf = gzip.GzipFile(mode="rb", fileobj=f)
                try:
                    decoded = gzf.read()
                except IOError:
                    self.send_response(400, "error decoding gzip content")
                f.close()
                gzf.close()
                return decoded
            else:
                self.send_response(501, "encoding %r not supported" % encoding)
            self.send_header("Content-length", "0")
            self.end_headers()
