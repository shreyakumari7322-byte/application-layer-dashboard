"""
main.py — FastAPI backend for the Dual-Panel Activity & Protocol Visualizer.

Run with:
    pip install fastapi uvicorn
    python -m uvicorn main:app --reload

Then open http://127.0.0.1:8000
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import protocols

app = FastAPI(title="Application Layer Dual-Panel Visualizer")


class BrowseRequest(BaseModel):
    url: str


class MailRequest(BaseModel):
    to: str
    subject: str
    body: str


class StreamRequest(BaseModel):
    quality: str = "720p"


@app.post("/api/simulate/browse")
def simulate_browse(req: BrowseRequest):
    return {"activity": "browsing", "steps": protocols.browsing_sequence(req.url)}


@app.post("/api/simulate/mail")
def simulate_mail(req: MailRequest):
    return {
        "activity": "mail",
        "steps": protocols.mail_sequence(req.to, req.subject, req.body),
    }


@app.post("/api/simulate/stream")
def simulate_stream(req: StreamRequest):
    return {"activity": "streaming", "steps": protocols.streaming_sequence(req.quality)}


# Serve the frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")
