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
import time
import urllib.parse

# The tunnel proxy sometimes closes a CONNECT immediately (for example while
# a per-address approval is still pending) and then accepts the same request
# a moment later. Retry the handshake instead of failing on the first close.
CONNECT_ATTEMPTS = 12
CONNECT_RETRY_DELAY_S = 3


def connect_once(proxy, host, port):
    """One CONNECT attempt. Returns (socket, rest_bytes) on a 200, or None
    when the proxy closed the connection before answering (retryable).
    Raises SystemExit with a message on a definitive failure."""
    try:
        s = socket.create_connection((proxy.hostname, proxy.port), timeout=30)
    except OSError as e:
        print(f"cannot reach proxy: {e}", file=sys.stderr)
        return None
    req = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n"
    if proxy.username:
        creds = f"{urllib.parse.unquote(proxy.username)}:{urllib.parse.unquote(proxy.password or '')}"
        req += "Proxy-Authorization: Basic " + base64.b64encode(creds.encode()).decode() + "\r\n"
    req += "\r\n"
    try:
        s.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                s.close()
                return None
            buf += chunk
    except OSError as e:
        print(f"proxy handshake failed: {e}", file=sys.stderr)
        try:
            s.close()
        except OSError:
            pass
        return None
    head, rest = buf.split(b"\r\n\r\n", 1)
    status = head.split(b"\r\n", 1)[0]
    if b" 200" not in status:
        print(f"proxy CONNECT failed: {status.decode(errors='replace')}", file=sys.stderr)
        sys.exit(1)
    return s, rest


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
    s = None
    rest = b""
    for attempt in range(1, CONNECT_ATTEMPTS + 1):
        result = connect_once(p, host, port)
        if result is not None:
            s, rest = result
            break
        if attempt < CONNECT_ATTEMPTS:
            time.sleep(CONNECT_RETRY_DELAY_S)
    if s is None:
        print(f"proxy closed the connection ({CONNECT_ATTEMPTS} attempts)", file=sys.stderr)
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
