# Application + Transport Layer Visualizer (Assignment 2)

Extends the Assignment 1 dashboard so the right panel supports **two
synchronized views** of the same exchange: an Application-layer view
(DNS/HTTP/SMTP) and a Transport-layer view (UDP + full TCP lifecycle),
switchable via tabs, both driven by the same underlying step timeline so
they never fall out of sync.

## What's new in Assignment 2

- **View tabs** — "Both / Application Layer / Transport Layer" above the
  timeline. Switching tabs only filters which steps are *visible*; the
  playback position (and the shared wire animation, OSI rail, and TCP
  state badge at the top) is identical underneath, so the two views stay
  perfectly synchronized with the left panel at all times.
- **Real TCP data segments.** Previously only the handshake and teardown
  were modeled at the transport layer. Now every single application
  message (each HTTP request/response, every SMTP line) is paired with
  its own TCP segment carrying real Seq/Ack numbers that increment by the
  actual payload length, PSH+ACK flags, window size, and segment length —
  tracked as a genuine byte stream per direction (`TcpStream` class in
  `protocols.py`), not hardcoded numbers.
- **Visual + semantic upgrades**: a live wire animation between Client/Server
  nodes, a TCP connection-state badge (SYN_SENT → ESTABLISHED → FIN_WAIT →
  CLOSED) that's accurate to what's actually happening, an OSI-layer rail,
  and a sci-fi HUD visual treatment.

## Project structure

```
dashboard/
├── main.py             FastAPI app (unchanged from Assignment 1)
├── protocols.py         Full rewrite: paired Application+Transport steps, TcpStream class
├── requirements.txt
├── static/
│   ├── index.html         Added view-tabs markup, HUD frame, wire visualization
│   ├── style.css           View-tab filtering CSS, HUD/wire/OSI-rail styling
│   └── app.js               View-tab handlers, wire animation, TCP state tracking
└── README.md
```

## How the two views stay synchronized

Every step in the single master array carries a `layer` field
("Application" or "Transport"). Playback (`currentIndex`) always advances
through *all* steps regardless of which tab is active — the tabs only add
a CSS class to the timeline container that hides elements of the other
layer via `display: none`. Because filtering is purely visual and the
index never resets or diverges, switching tabs mid-playback preserves
your exact position in the exchange — this is what "synchronized views"
means here, and it also means the shared elements at the top (wire
animation, TCP state badge, OSI rail) are always accurate no matter which
tab you're on.

## How Seq/Ack tracking works

`TcpStream` (in `protocols.py`) keeps a running `seq_c` / `seq_s` counter
per direction, seeded from the handshake's final ISN+1. Each call to
`add_app_message()`:
1. Appends the Application-layer step (the human-readable HTTP/SMTP message)
2. Computes `payload_len = len(raw.encode('utf-8'))`
3. Appends a Transport-layer step: `Seq` = the sender's current counter,
   `Ack` = the receiver's current counter (bytes received so far),
   `Flags = PSH, ACK`, `Length = payload_len`
4. Increments the sender's counter by `payload_len` for the next segment

This mirrors real TCP: sequence numbers count bytes, not messages, and
each segment acknowledges everything received from the peer so far.

## Setup & run

```bash
cd dashboard
pip install -r requirements.txt
uvicorn main:app --reload
```
Open **http://127.0.0.1:8000**.

## What's simulated vs. real

All traffic is simulated (no real sockets), but every number is
*computed*, not hardcoded: Seq/Ack progression, TCP state transitions,
and connection lifecycle are all internally consistent and would hold up
to scrutiny against a real packet capture's logic, even though no real
network traffic is generated.

## Extra credit ideas (per the assignment)

- Real socket-based TCP server instead of simulation
- Congestion-window illustration (shrink/grow visualization tied to a
  simulated loss event)
- Persistent vs. non-persistent TCP connection comparison (toggle)
- QUIC handshake visualization for streaming
- Side-by-side TCP vs UDP comparison for the streaming case
