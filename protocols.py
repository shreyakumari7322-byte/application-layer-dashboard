"""
protocols.py
------------
Generates a single synchronized timeline spanning two OSI layers for each
simulated activity (Browsing, Mail, Streaming):

  Transport layer : UDP (DNS) and TCP (handshake, per-message data segments
                    with real Seq/Ack tracking, teardown)
  Application layer: DNS, HTTP, SMTP

Every application-layer message (an HTTP request, an SMTP line, etc.) is
paired with a sibling Transport-layer step representing the TCP segment
that actually carries it — with Seq/Ack numbers that increment correctly
based on bytes already sent in each direction, real PSH/ACK flags, and
window size. This lets the frontend show an "Application Layer" view, a
"Transport Layer" view, or both, while staying driven by one shared
step index (so switching views never loses sync with the left panel).

Step shapes:

Divider (section label):
{ "seq": int, "type": "divider", "layer": "Transport"|"Application",
  "label": str, "t_ms": int }

Message:
{ "seq": int, "type": "message", "layer": "Transport"|"Application",
  "protocol": "DNS"|"TCP"|"HTTP"|"SMTP", "direction": "c2s"|"s2c",
  "label": str, "raw": str, "fields": {...}, "t_ms": int,
  "conn_state": str | None,   # only set on TCP handshake/teardown steps
  "pair_id": int | None       # links an Application step to its Transport segment
}
"""

import random
import re
from urllib.parse import urlparse


def _domain_from_url(url: str) -> tuple[str, str]:
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = "http://" + url
    parsed = urlparse(url)
    domain = parsed.netloc or "example.com"
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    return domain, path


def _fake_ip() -> str:
    return f"{random.randint(93,151)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _client_port() -> int:
    return random.randint(49152, 65535)


def _divider(layer: str, label: str, t_ms: int) -> dict:
    return {"seq": 0, "type": "divider", "layer": layer, "label": label, "t_ms": t_ms}


# --------------------------------------------------------- transport layer

def _dns_over_udp_steps(domain: str, start_t: int) -> tuple[list[dict], int]:
    txid = random.randint(0x1000, 0xFFFF)
    ip = _fake_ip()
    cport = _client_port()
    steps = [
        _divider("Transport", "Transport Layer — UDP (DNS lookup)", start_t),
        {
            "seq": 0, "type": "message", "layer": "Transport", "protocol": "DNS",
            "direction": "c2s", "label": "DNS Query (A record) over UDP", "conn_state": None, "pair_id": None,
            "raw": (
                f"UDP  src={cport} dst=53\n"
                f"; Transaction ID: 0x{txid:04X}\n"
                f"; Flags: 0x0100 (Standard query, Recursion Desired)\n"
                f"QUESTION SECTION:\n;{domain}.\tIN\tA"
            ),
            "fields": {
                "Transport": "UDP (connectionless)", "Src Port": str(cport), "Dst Port": "53",
                "Transaction ID": f"0x{txid:04X}", "Query name": domain,
            },
            "t_ms": start_t + 10,
        },
        {
            "seq": 0, "type": "message", "layer": "Transport", "protocol": "DNS",
            "direction": "s2c", "label": "DNS Response over UDP", "conn_state": None, "pair_id": None,
            "raw": (
                f"UDP  src=53 dst={cport}\n"
                f"; Transaction ID: 0x{txid:04X}\n"
                f"; Flags: 0x8180 (Response, No error)\n"
                f"ANSWER SECTION:\n{domain}.\t300\tIN\tA\t{ip}"
            ),
            "fields": {
                "Transport": "UDP (connectionless)", "Resolved IP": ip, "TTL": "300s", "Response code": "NOERROR",
            },
            "t_ms": start_t + 45,
        },
    ]
    return steps, start_t + 70


def _tcp_handshake_steps(cport: int, sport: int, start_t: int) -> tuple[list[dict], int, int, int]:
    """Returns (steps, next_t, client_isn_next, server_isn_next)."""
    isn_c = random.randint(1000, 9000)
    isn_s = random.randint(1000, 9000)
    t = start_t
    steps = [_divider("Transport", "Transport Layer — TCP Handshake (connection setup)", t)]
    t += 10
    steps.append({
        "seq": 0, "type": "message", "layer": "Transport", "protocol": "TCP",
        "direction": "c2s", "label": "TCP SYN", "conn_state": "SYN_SENT", "pair_id": None,
        "raw": f"TCP  src={cport} dst={sport}\nFlags: SYN\nSeq: {isn_c}\nWin: 64240",
        "fields": {"Flags": "SYN", "Seq": str(isn_c), "Src Port": str(cport), "Dst Port": str(sport), "Window Size": "64240"},
        "t_ms": t,
    })
    t += 30
    steps.append({
        "seq": 0, "type": "message", "layer": "Transport", "protocol": "TCP",
        "direction": "s2c", "label": "TCP SYN-ACK", "conn_state": "SYN_SENT", "pair_id": None,
        "raw": f"TCP  src={sport} dst={cport}\nFlags: SYN, ACK\nSeq: {isn_s}\nAck: {isn_c + 1}\nWin: 65535",
        "fields": {"Flags": "SYN, ACK", "Seq": str(isn_s), "Ack": str(isn_c + 1), "Window Size": "65535"},
        "t_ms": t,
    })
    t += 25
    steps.append({
        "seq": 0, "type": "message", "layer": "Transport", "protocol": "TCP",
        "direction": "c2s", "label": "TCP ACK (connection established)", "conn_state": "ESTABLISHED", "pair_id": None,
        "raw": f"TCP  src={cport} dst={sport}\nFlags: ACK\nSeq: {isn_c + 1}\nAck: {isn_s + 1}",
        "fields": {"Flags": "ACK", "Seq": str(isn_c + 1), "Ack": str(isn_s + 1), "State": "ESTABLISHED"},
        "t_ms": t,
    })
    t += 25
    return steps, t, isn_c + 1, isn_s + 1


def _tcp_teardown_steps(cport: int, sport: int, seq_c: int, seq_s: int, start_t: int) -> tuple[list[dict], int]:
    t = start_t
    steps = [_divider("Transport", "Transport Layer — TCP Teardown (connection close)", t)]
    t += 10
    steps.append({
        "seq": 0, "type": "message", "layer": "Transport", "protocol": "TCP",
        "direction": "c2s", "label": "TCP FIN, ACK", "conn_state": "FIN_WAIT_1", "pair_id": None,
        "raw": f"TCP  src={cport} dst={sport}\nFlags: FIN, ACK\nSeq: {seq_c}\nAck: {seq_s}",
        "fields": {"Flags": "FIN, ACK", "Seq": str(seq_c), "Ack": str(seq_s)},
        "t_ms": t,
    })
    t += 25
    steps.append({
        "seq": 0, "type": "message", "layer": "Transport", "protocol": "TCP",
        "direction": "s2c", "label": "TCP ACK", "conn_state": "FIN_WAIT_2", "pair_id": None,
        "raw": f"TCP  src={sport} dst={cport}\nFlags: ACK\nAck: {seq_c + 1}",
        "fields": {"Flags": "ACK", "Ack": str(seq_c + 1)},
        "t_ms": t,
    })
    t += 20
    steps.append({
        "seq": 0, "type": "message", "layer": "Transport", "protocol": "TCP",
        "direction": "s2c", "label": "TCP FIN, ACK", "conn_state": "TIME_WAIT", "pair_id": None,
        "raw": f"TCP  src={sport} dst={cport}\nFlags: FIN, ACK\nSeq: {seq_s}\nAck: {seq_c + 1}",
        "fields": {"Flags": "FIN, ACK", "Seq": str(seq_s), "Ack": str(seq_c + 1)},
        "t_ms": t,
    })
    t += 25
    steps.append({
        "seq": 0, "type": "message", "layer": "Transport", "protocol": "TCP",
        "direction": "c2s", "label": "TCP ACK (connection closed)", "conn_state": "CLOSED", "pair_id": None,
        "raw": f"TCP  src={cport} dst={sport}\nFlags: ACK\nAck: {seq_s + 1}",
        "fields": {"Flags": "ACK", "Ack": str(seq_s + 1), "State": "CLOSED"},
        "t_ms": t,
    })
    t += 20
    return steps, t


def _renumber(steps: list[dict]) -> list[dict]:
    for i, s in enumerate(steps):
        s["seq"] = i
    return steps


class TcpStream:
    """Tracks a TCP byte stream's sequence numbers in each direction so every
    application message can be paired with an accurate TCP data segment."""

    def __init__(self, cport: int, sport: int, seq_c: int, seq_s: int, win: int = 64240):
        self.cport = cport
        self.sport = sport
        self.seq_c = seq_c
        self.seq_s = seq_s
        self.win = win
        self._next_pair_id = 1

    def add_app_message(self, steps: list, t: int, direction: str, protocol: str,
                         label: str, raw: str, fields: dict, app_dt: int = 50, seg_dt: int = 25) -> int:
        """Appends an Application-layer step AND its paired Transport-layer
        TCP data segment. Returns the new t_ms cursor."""
        pair_id = self._next_pair_id
        self._next_pair_id += 1

        steps.append({
            "seq": 0, "type": "message", "layer": "Application", "protocol": protocol,
            "direction": direction, "label": label, "raw": raw, "fields": fields,
            "t_ms": t, "conn_state": None, "pair_id": pair_id,
        })
        t += app_dt

        payload_len = len(raw.encode("utf-8"))
        if direction == "c2s":
            seg_seq, seg_ack = self.seq_c, self.seq_s
            self.seq_c += payload_len
            src, dst = self.cport, self.sport
        else:
            seg_seq, seg_ack = self.seq_s, self.seq_c
            self.seq_s += payload_len
            src, dst = self.sport, self.cport

        steps.append({
            "seq": 0, "type": "message", "layer": "Transport", "protocol": "TCP",
            "direction": direction, "conn_state": None, "pair_id": pair_id,
            "label": f"TCP Segment carrying: {label}",
            "raw": (
                f"TCP  src={src} dst={dst}\nFlags: PSH, ACK\n"
                f"Seq: {seg_seq}\nAck: {seg_ack}\nWin: {self.win}\nLen: {payload_len}"
            ),
            "fields": {
                "Flags": "PSH, ACK", "Seq": str(seg_seq), "Ack": str(seg_ack),
                "Window Size": str(self.win), "Length": f"{payload_len} bytes",
                "Carries": protocol,
            },
            "t_ms": t,
        })
        t += seg_dt
        return t

    def teardown(self, steps: list, t: int) -> int:
        td_steps, t = _tcp_teardown_steps(self.cport, self.sport, self.seq_c, self.seq_s, t)
        steps.extend(td_steps)
        return t


# ---------------------------------------------------------------- BROWSING

def browsing_sequence(url: str) -> list[dict]:
    domain, path = _domain_from_url(url)
    steps, t = _dns_over_udp_steps(domain, start_t=0)

    cport, sport = _client_port(), 80
    hs_steps, t, seq_c, seq_s = _tcp_handshake_steps(cport, sport, t)
    steps += hs_steps
    stream = TcpStream(cport, sport, seq_c, seq_s)

    steps.append(_divider("Application", "Application Layer — HTTP", t))
    t += 10

    t = stream.add_app_message(
        steps, t, "c2s", "HTTP", "HTTP GET Request",
        f"GET {path} HTTP/1.1\nHost: {domain}\n"
        f"User-Agent: Mozilla/5.0 (DashboardSimClient/1.0)\n"
        f"Accept: text/html,application/xhtml+xml\nConnection: keep-alive",
        {"Method": "GET", "Path": path, "Host": domain}, app_dt=60,
    )
    t = stream.add_app_message(
        steps, t, "s2c", "HTTP", "HTTP Response",
        "HTTP/1.1 200 OK\nContent-Type: text/html; charset=UTF-8\n"
        "Content-Length: 4821\nServer: nginx/1.25\nConnection: keep-alive\n\n"
        "<!DOCTYPE html><html><head>...</head><body>...</body></html>",
        {"Status": "200 OK", "Content-Type": "text/html", "Content-Length": "4821 bytes"}, app_dt=40,
    )

    t = stream.teardown(steps, t)
    return _renumber(steps)


# ------------------------------------------------------------------- MAIL

def mail_sequence(to_addr: str, subject: str, body: str) -> list[dict]:
    from_addr = "shreya@studentmail.edu"
    mail_domain = (to_addr.split("@")[-1] or "mail.example.com").strip()
    dns_target = f"mail.{mail_domain}" if "." in mail_domain else mail_domain

    steps, t = _dns_over_udp_steps(dns_target, start_t=0)

    cport, sport = _client_port(), 25
    hs_steps, t, seq_c, seq_s = _tcp_handshake_steps(cport, sport, t)
    steps += hs_steps
    stream = TcpStream(cport, sport, seq_c, seq_s)

    steps.append(_divider("Application", "Application Layer — SMTP", t))
    t += 10
    msg_id = f"{random.randint(10**8,10**9)}.{random.randint(1,999)}@{dns_target}"

    def add(direction, label, raw, fields, dt=45):
        nonlocal t
        t = stream.add_app_message(steps, t, direction, "SMTP", label, raw, fields, app_dt=dt)

    add("s2c", "Server Greeting", f"220 {dns_target} ESMTP ready", {"Code": "220"})
    add("c2s", "EHLO", "EHLO studentmail.edu", {"Command": "EHLO"})
    add("s2c", "EHLO Response", f"250-{dns_target} Hello\n250-SIZE 35882577\n250-STARTTLS\n250 8BITMIME",
        {"Code": "250", "Extensions": "SIZE, STARTTLS, 8BITMIME"})
    add("c2s", "MAIL FROM", f"MAIL FROM:<{from_addr}>", {"Sender": from_addr})
    add("s2c", "MAIL FROM Response", "250 2.1.0 OK", {"Code": "250"})
    add("c2s", "RCPT TO", f"RCPT TO:<{to_addr}>", {"Recipient": to_addr})
    add("s2c", "RCPT TO Response", "250 2.1.5 OK", {"Code": "250"})
    add("c2s", "DATA", "DATA", {"Command": "DATA"})
    add("s2c", "DATA Response", "354 Start mail input; end with <CRLF>.<CRLF>", {"Code": "354"})
    add("c2s", "Message Content", f"From: {from_addr}\nTo: {to_addr}\nSubject: {subject}\n\n{body}\n.",
        {"Subject": subject, "Body length": f"{len(body)} chars"}, dt=70)
    add("s2c", "Message Accepted", f"250 2.0.0 OK: queued as {msg_id}", {"Queue ID": msg_id})
    add("c2s", "QUIT", "QUIT", {"Command": "QUIT"})
    add("s2c", "Closing", f"221 2.0.0 {dns_target} closing connection", {"Code": "221"})

    t = stream.teardown(steps, t)
    return _renumber(steps)


# -------------------------------------------------------------- STREAMING

def streaming_sequence(quality: str) -> list[dict]:
    domain = "cdn.streamservice.net"
    steps, t = _dns_over_udp_steps(domain, start_t=0)

    cport, sport = _client_port(), 443
    hs_steps, t, seq_c, seq_s = _tcp_handshake_steps(cport, sport, t)
    steps += hs_steps
    stream = TcpStream(cport, sport, seq_c, seq_s)

    steps.append(_divider("Application", "Application Layer — HTTP (adaptive streaming, over TCP)", t))
    t += 10

    def add(direction, label, raw, fields, dt=55):
        nonlocal t
        t = stream.add_app_message(steps, t, direction, "HTTP", label, raw, fields, app_dt=dt)

    add("c2s", "GET Master Playlist", f"GET /video42/master.m3u8 HTTP/1.1\nHost: {domain}",
        {"Resource": "master.m3u8", "Purpose": "List quality variants"})
    add("s2c", "Master Playlist Response",
        "HTTP/1.1 200 OK\nContent-Type: application/vnd.apple.mpegurl\n\n"
        "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=2800000,RESOLUTION=1280x720\n360p/index.m3u8\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080\n1080p/index.m3u8",
        {"Status": "200 OK", "Variants": "360p, 720p, 1080p"})
    add("c2s", "GET Quality Variant Playlist", f"GET /video42/{quality}/index.m3u8 HTTP/1.1\nHost: {domain}",
        {"Selected quality": quality})
    add("s2c", "Variant Playlist Response",
        "HTTP/1.1 200 OK\nContent-Type: application/vnd.apple.mpegurl\n\n"
        "#EXTM3U\n#EXT-X-TARGETDURATION:6\n"
        "#EXTINF:6.0,\nseg000.ts\n#EXTINF:6.0,\nseg001.ts\n#EXTINF:6.0,\nseg002.ts",
        {"Status": "200 OK", "Segment duration": "6.0s each"})

    for i in range(3):
        add("c2s", f"GET Segment {i}", f"GET /video42/{quality}/seg{i:03d}.ts HTTP/1.1\nHost: {domain}\nRange: bytes=0-",
            {"Segment": f"seg{i:03d}.ts"}, dt=30)
        add("s2c", f"Segment {i} Response",
            "HTTP/1.1 200 OK\nContent-Type: video/MP2T\nContent-Length: 940812\n\n[binary MPEG-TS data]",
            {"Status": "200 OK", "Size": "~940 KB"}, dt=55)

    t = stream.teardown(steps, t)
    return _renumber(steps)
