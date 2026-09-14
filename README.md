# Application Layer Dual-Panel Visualizer

A dashboard for the Computer Networks "Dual-Panel Activity & Protocol Visualizer"
assignment. The left panel performs a simulated Browsing / Mail / Streaming
activity; the right panel animates the exact application-layer messages
(DNS, HTTP, SMTP) that activity would produce, step by step.

## Project structure

```
dashboard/
├── main.py            FastAPI app: serves the frontend + 3 simulation endpoints
├── protocols.py        Generates the DNS / HTTP / SMTP message sequences
├── requirements.txt
├── static/
│   ├── index.html       Dual-panel page structure
│   ├── style.css        Styling (dark "network console" theme)
│   └── app.js            Panel wiring, API calls, step-by-step animation
└── README.md
```

## How it works (architecture)

1. The user performs an action on the **left panel** (submits a URL, composes
   mail, or hits Play on the stream).
2. The frontend (`app.js`) sends a `POST` request to the matching FastAPI
   endpoint (`/api/simulate/browse`, `/api/simulate/mail`, or
   `/api/simulate/stream`).
3. The backend (`protocols.py`) builds an ordered list of "step" objects —
   each one a single protocol message with its direction (client→server or
   server→client), raw wire-format text, key fields, and a relative
   timestamp.
4. The frontend receives that list and renders it into the **right panel**
   as a timeline, then auto-plays through it one step at a time (a `setInterval`
   loop reveals one step every ~900ms). Play/Pause, Step forward/back, Replay,
   and a scrubber slider all just move a single `currentIndex` pointer and
   re-render which steps are "revealed" — this is what keeps the two panels
   in sync and lets you scrub freely without re-fetching data.

## Setup & run

```bash
cd dashboard
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open **http://127.0.0.1:8000** in your browser.

## What's simulated vs. real

Per the assignment, all protocol traffic is **simulated** (no real sockets) —
but the message formats are modeled closely on real DNS/HTTP/SMTP behavior:

- **DNS**: transaction ID, standard query flags, A-record question/answer
  sections, TTL.
- **HTTP**: proper GET request line + headers (Host, User-Agent, Accept), and
  a response with status line + Content-Type/Content-Length headers.
- **SMTP**: the full real command sequence — server greeting (220), EHLO,
  EHLO response with extensions, MAIL FROM, RCPT TO, DATA, the message
  content terminated with `<CRLF>.<CRLF>`, QUIT, and connection close (221).
- **Streaming**: modeled as HLS — DNS lookup, a master playlist request
  listing quality variants, a variant playlist request, then individual
  `.ts` segment requests (this is how real adaptive streaming — YouTube,
  Netflix, etc. — actually works over HTTP).

## Extending this for extra credit

- Swap the simulated DNS/HTTP calls for real ones using Python's `socket` /
  `http.client` against a real test server.
- Add a TLS indicator step (`ClientHello`/`ServerHello`) before HTTP steps
  to show HTTPS.
- Add a toggle comparing persistent (keep-alive, multiple requests over one
  TCP connection) vs. non-persistent HTTP connections.

## Notes for your submission

This project was built with AI assistance (Claude). For your **AI usage log**
deliverable, export this conversation or take screenshots of the build
process. For the **reflection document**, some honest starting points based
on this build:
- The SMTP flow needed the exact real command order (EHLO → MAIL FROM →
  RCPT TO → DATA → content → QUIT) — worth double-checking against RFC 5321
  if you modify it.
- The streaming simulation models adaptive bitrate streaming (HLS-style)
  rather than a single long-lived connection, which is closer to how
  real streaming services behave than a naive "one big HTTP download" model.
