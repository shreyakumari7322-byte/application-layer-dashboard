"""
protocols.py
------------
Generates realistic, step-by-step application-layer protocol message
sequences for the three simulated activities: Browsing, Mail, Streaming.

Each step is a dict:
{
    "seq": int,                 # order in the sequence
    "protocol": "DNS"|"HTTP"|"SMTP",
    "direction": "c2s"|"s2c",   # client->server or server->client
    "label": str,               # short human title, e.g. "DNS Query (A record)"
    "raw": str,                 # the literal wire-format-style message text
    "fields": {k: v, ...},      # key fields worth highlighting in the UI
    "t_ms": int                 # relative timestamp (ms) for pacing the animation
}
"""

import random
import re
from urllib.parse import urlparse


def _domain_from_url(url: str) -> tuple[str, str]:
    """Return (domain, path) from a user-entered URL, tolerating missing scheme."""
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


def _dns_steps(domain: str, start_t: int) -> list[dict]:
    """A standard iterative-from-the-client DNS lookup (query + response)."""
    txid = random.randint(0x1000, 0xFFFF)
    ip = _fake_ip()
    return [
        {
            "seq": 0,
            "protocol": "DNS",
            "direction": "c2s",
            "label": "DNS Query (A record)",
            "raw": (
                f"; Transaction ID: 0x{txid:04X}\n"
                f"; Flags: 0x0100 (Standard query, Recursion Desired)\n"
                f"; Questions: 1\n"
                f"QUESTION SECTION:\n"
                f";{domain}.\tIN\tA"
            ),
            "fields": {
                "Transaction ID": f"0x{txid:04X}",
                "Query type": "A (IPv4 address)",
                "Query name": domain,
                "Recursion Desired": "true",
            },
            "t_ms": start_t,
        },
        {
            "seq": 0,
            "protocol": "DNS",
            "direction": "s2c",
            "label": "DNS Response",
            "raw": (
                f"; Transaction ID: 0x{txid:04X}\n"
                f"; Flags: 0x8180 (Response, Recursion Available, No error)\n"
                f"; Answers: 1\n"
                f"ANSWER SECTION:\n"
                f"{domain}.\t300\tIN\tA\t{ip}"
            ),
            "fields": {
                "Transaction ID": f"0x{txid:04X}",
                "Response code": "NOERROR",
                "Resolved IP": ip,
                "TTL": "300s",
            },
            "t_ms": start_t + 40,
        },
    ]


# ---------------------------------------------------------------- BROWSING

def browsing_sequence(url: str) -> list[dict]:
    domain, path = _domain_from_url(url)
    steps = _dns_steps(domain, start_t=0)
    t = steps[-1]["t_ms"] + 30

    steps.append({
        "seq": 0, "protocol": "HTTP", "direction": "c2s",
        "label": "HTTP GET Request",
        "raw": (
            f"GET {path} HTTP/1.1\n"
            f"Host: {domain}\n"
            f"User-Agent: Mozilla/5.0 (DashboardSimClient/1.0)\n"
            f"Accept: text/html,application/xhtml+xml\n"
            f"Accept-Language: en-US,en;q=0.9\n"
            f"Connection: keep-alive"
        ),
        "fields": {
            "Method": "GET",
            "Path": path,
            "Host": domain,
            "Connection": "keep-alive",
        },
        "t_ms": t,
    })
    t += 60
    steps.append({
        "seq": 0, "protocol": "HTTP", "direction": "s2c",
        "label": "HTTP Response",
        "raw": (
            "HTTP/1.1 200 OK\n"
            "Content-Type: text/html; charset=UTF-8\n"
            "Content-Length: 4821\n"
            "Server: nginx/1.25\n"
            "Cache-Control: max-age=600\n"
            "Connection: keep-alive\n\n"
            "<!DOCTYPE html><html><head>...</head><body>...</body></html>"
        ),
        "fields": {
            "Status": "200 OK",
            "Content-Type": "text/html; charset=UTF-8",
            "Content-Length": "4821 bytes",
        },
        "t_ms": t,
    })

    for i, s in enumerate(steps):
        s["seq"] = i
    return steps


# -------------------------------------------------------------------- MAIL

def mail_sequence(to_addr: str, subject: str, body: str) -> list[dict]:
    from_addr = "shreya@studentmail.edu"
    mail_domain = (to_addr.split("@")[-1] or "mail.example.com").strip()
    steps = _dns_steps(f"mail.{mail_domain}" if "." in mail_domain else mail_domain, start_t=0)
    t = steps[-1]["t_ms"] + 30
    msg_id = f"{random.randint(10**8,10**9)}.{random.randint(1,999)}@mail.{mail_domain}"

    def add(direction, label, raw, fields, dt=50):
        nonlocal t
        steps.append({
            "seq": 0, "protocol": "SMTP", "direction": direction,
            "label": label, "raw": raw, "fields": fields, "t_ms": t,
        })
        t += dt

    add("s2c", "Server Greeting", f"220 mail.{mail_domain} ESMTP ready", {"Code": "220", "Meaning": "Service ready"})
    add("c2s", "EHLO", "EHLO studentmail.edu", {"Command": "EHLO", "Client domain": "studentmail.edu"})
    add("s2c", "EHLO Response",
        f"250-mail.{mail_domain} Hello studentmail.edu\n250-SIZE 35882577\n250-STARTTLS\n250 8BITMIME",
        {"Code": "250", "Extensions": "SIZE, STARTTLS, 8BITMIME"})
    add("c2s", "MAIL FROM", f"MAIL FROM:<{from_addr}>", {"Command": "MAIL FROM", "Sender": from_addr})
    add("s2c", "MAIL FROM Response", "250 2.1.0 OK", {"Code": "250", "Meaning": "Sender accepted"})
    add("c2s", "RCPT TO", f"RCPT TO:<{to_addr}>", {"Command": "RCPT TO", "Recipient": to_addr})
    add("s2c", "RCPT TO Response", "250 2.1.5 OK", {"Code": "250", "Meaning": "Recipient accepted"})
    add("c2s", "DATA", "DATA", {"Command": "DATA"})
    add("s2c", "DATA Response", "354 Start mail input; end with <CRLF>.<CRLF>", {"Code": "354"})
    add("c2s", "Message Content",
        f"From: {from_addr}\nTo: {to_addr}\nSubject: {subject}\n\n{body}\n.",
        {"Subject": subject, "Body length": f"{len(body)} chars", "Terminator": "<CRLF>.<CRLF>"}, dt=80)
    add("s2c", "Message Accepted", f"250 2.0.0 OK: queued as {msg_id}",
        {"Code": "250", "Queue ID": msg_id})
    add("c2s", "QUIT", "QUIT", {"Command": "QUIT"})
    add("s2c", "Closing", f"221 2.0.0 mail.{mail_domain} closing connection", {"Code": "221"})

    for i, s in enumerate(steps):
        s["seq"] = i
    return steps


# --------------------------------------------------------------- STREAMING

def streaming_sequence(quality: str) -> list[dict]:
    domain = "cdn.streamservice.net"
    steps = _dns_steps(domain, start_t=0)
    t = steps[-1]["t_ms"] + 30

    def add(direction, label, raw, fields, dt=60):
        nonlocal t
        steps.append({
            "seq": 0, "protocol": "HTTP", "direction": direction,
            "label": label, "raw": raw, "fields": fields, "t_ms": t,
        })
        t += dt

    add("c2s", "GET Master Playlist",
        f"GET /video42/master.m3u8 HTTP/1.1\nHost: {domain}\nAccept: application/vnd.apple.mpegurl",
        {"Method": "GET", "Resource": "master.m3u8", "Purpose": "List available quality variants"})
    add("s2c", "Master Playlist Response",
        "HTTP/1.1 200 OK\nContent-Type: application/vnd.apple.mpegurl\n\n"
        "#EXTM3U\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=2800000,RESOLUTION=1280x720\n360p/index.m3u8\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080\n1080p/index.m3u8",
        {"Status": "200 OK", "Variants listed": "360p, 720p, 1080p"})
    add("c2s", "GET Quality Variant Playlist",
        f"GET /video42/{quality}/index.m3u8 HTTP/1.1\nHost: {domain}",
        {"Method": "GET", "Selected quality": quality})
    add("s2c", "Variant Playlist Response",
        "HTTP/1.1 200 OK\nContent-Type: application/vnd.apple.mpegurl\n\n"
        "#EXTM3U\n#EXT-X-TARGETDURATION:6\n"
        "#EXTINF:6.0,\nseg000.ts\n#EXTINF:6.0,\nseg001.ts\n#EXTINF:6.0,\nseg002.ts",
        {"Status": "200 OK", "Segment duration": "6.0s each", "Segments listed": "3"})

    for i in range(3):
        add("c2s", f"GET Segment {i}",
            f"GET /video42/{quality}/seg{i:03d}.ts HTTP/1.1\nHost: {domain}\nRange: bytes=0-",
            {"Method": "GET", "Segment": f"seg{i:03d}.ts"}, dt=30)
        add("s2c", f"Segment {i} Response",
            f"HTTP/1.1 200 OK\nContent-Type: video/MP2T\nContent-Length: 940812\n\n[binary MPEG-TS data]",
            {"Status": "200 OK", "Content-Type": "video/MP2T", "Size": "~940 KB"}, dt=60)

    for i, s in enumerate(steps):
        s["seq"] = i
    return steps
