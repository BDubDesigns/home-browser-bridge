#!/usr/bin/env python3
"""CONNECT tunnel to a tailnet host:port via the runtime HTTP proxy.

Reads the proxy URL from TUNNEL_PROXY (or HTTPS_PROXY) env only -- never
from argv, so no credential ever appears in a command line. Designed as an
OpenSSH ProxyCommand: stdin/stdout become the tunneled channel.

Usage: ssh-via-tailscale-proxy.py <host> <port>
"""
import base64
import os
import socket
import sys
import threading
import urllib.parse


def main():
    if len(sys.argv) != 3:
        print("usage: ssh-via-tailscale-proxy.py <host> <port>", file=sys.stderr)
        return 2
    host, port = sys.argv[1], int(sys.argv[2])
    proxy_url = os.environ.get("TUNNEL_PROXY") or os.environ.get("HTTPS_PROXY")
    if not proxy_url:
        print("no TUNNEL_PROXY or HTTPS_PROXY in env", file=sys.stderr)
        return 1
    p = urllib.parse.urlparse(proxy_url)
    if not p.hostname or not p.port:
        print("proxy URL missing host/port", file=sys.stderr)
        return 1
    try:
        s = socket.create_connection((p.hostname, p.port), timeout=30)
    except OSError as e:
        print(f"cannot reach proxy: {e}", file=sys.stderr)
        return 1
    req = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n"
    if p.username:
        creds = f"{urllib.parse.unquote(p.username)}:{urllib.parse.unquote(p.password or '')}"
        req += "Proxy-Authorization: Basic " + base64.b64encode(creds.encode()).decode() + "\r\n"
    req += "\r\n"
    try:
        s.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                print("proxy closed the connection", file=sys.stderr)
                return 1
            buf += chunk
    except OSError as e:
        print(f"proxy handshake failed: {e}", file=sys.stderr)
        return 1
    head, rest = buf.split(b"\r\n\r\n", 1)
    status = head.split(b"\r\n", 1)[0]
    if b" 200" not in status:
        print(f"proxy CONNECT failed: {status.decode(errors='replace')}", file=sys.stderr)
        return 1
    if rest:
        os.write(1, rest)

    def stdin_to_sock():
        try:
            while True:
                data = os.read(0, 65536)
                if not data:
                    break
                s.sendall(data)
        except OSError:
            pass
        finally:
            try:
                s.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    def sock_to_stdout():
        try:
            while True:
                data = s.recv(65536)
                if not data:
                    break
                os.write(1, data)
        except OSError:
            pass

    t1 = threading.Thread(target=stdin_to_sock, daemon=True)
    t2 = threading.Thread(target=sock_to_stdout, daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    return 0


if __name__ == "__main__":
    sys.exit(main())
