"""
Minimal SIP Registrar / Proxy.

Handles just enough SIP to let:
  - pyVoIP register as extension 100 (the dispatch AI)
  - Android phone (LinPhone) register as extension 200
  - Route calls between them
  - Support auto-call from dispatch → phone

This is NOT a full PBX. It handles REGISTER, INVITE, ACK, BYE, CANCEL
and proxies responses. Nothing more.
"""

import re
import socket
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("dispatch.sip")


@dataclass
class Registration:
    extension: str
    contact_uri: str
    contact_addr: tuple  # (ip, port)
    expires: int = 3600
    registered_at: float = 0.0

    @property
    def is_expired(self) -> bool:
        return time.time() > self.registered_at + self.expires


@dataclass
class Dialog:
    call_id: str
    caller_addr: tuple  # (ip, port) of whoever sent the INVITE
    callee_addr: tuple  # (ip, port) of the target
    state: str = "trying"  # trying, ringing, confirmed, terminated


class SIPMessage:
    """Minimal SIP message parser/builder."""

    def __init__(self, raw: str):
        self.raw = raw
        self.headers: dict[str, list[str]] = {}
        self.body = ""
        self.request_line = ""
        self.status_line = ""
        self.is_request = False
        self.is_response = False
        self._parse()

    def _parse(self):
        parts = self.raw.split("\r\n\r\n", 1)
        header_block = parts[0]
        self.body = parts[1] if len(parts) > 1 else ""

        lines = header_block.split("\r\n")
        first_line = lines[0]

        if first_line.startswith("SIP/2.0"):
            self.is_response = True
            self.status_line = first_line
        else:
            self.is_request = True
            self.request_line = first_line

        for line in lines[1:]:
            if ":" not in line:
                continue
            name, _, value = line.partition(":")
            name = name.strip()
            value = value.strip()
            key = name.lower()
            if key not in self.headers:
                self.headers[key] = []
            self.headers[key].append(value)

    @property
    def method(self) -> str:
        if self.is_request:
            return self.request_line.split(" ", 1)[0]
        return ""

    @property
    def request_uri(self) -> str:
        if self.is_request:
            parts = self.request_line.split(" ")
            if len(parts) >= 2:
                return parts[1]
        return ""

    @property
    def status_code(self) -> int:
        if self.is_response:
            parts = self.status_line.split(" ", 2)
            if len(parts) >= 2:
                return int(parts[1])
        return 0

    def get_header(self, name: str) -> str:
        vals = self.headers.get(name.lower(), [])
        return vals[0] if vals else ""

    def get_all_headers(self, name: str) -> list[str]:
        return self.headers.get(name.lower(), [])

    @property
    def call_id(self) -> str:
        return self.get_header("call-id")

    @property
    def from_header(self) -> str:
        return self.get_header("from")

    @property
    def to_header(self) -> str:
        return self.get_header("to")

    @property
    def contact(self) -> str:
        return self.get_header("contact")

    @property
    def cseq(self) -> str:
        return self.get_header("cseq")

    @property
    def via_headers(self) -> list[str]:
        return self.get_all_headers("via")


def _extract_extension(uri: str) -> str:
    """Extract extension/user from a SIP URI like sip:100@host."""
    match = re.search(r"sip:(\w+)@", uri)
    if match:
        return match.group(1)
    match = re.search(r"sip:(\w+)", uri)
    if match:
        return match.group(1)
    return ""


def _extract_uri_host_port(uri: str) -> tuple[str, int]:
    """Extract host and port from SIP URI."""
    match = re.search(r"@([\d.]+):(\d+)", uri)
    if match:
        return match.group(1), int(match.group(2))
    match = re.search(r"@([\d.]+)", uri)
    if match:
        return match.group(1), 5060
    return "", 5060


def _build_response(request: SIPMessage, status_code: int, reason: str,
                    extra_headers: Optional[dict] = None, body: str = "") -> str:
    """Build a SIP response from a request."""
    lines = [f"SIP/2.0 {status_code} {reason}"]

    # Copy Via headers (all of them, in order)
    for via in request.via_headers:
        lines.append(f"Via: {via}")

    lines.append(f"From: {request.from_header}")

    to_hdr = request.to_header
    # Add tag to To header if not present (for responses to INVITE/REGISTER)
    if ";tag=" not in to_hdr:
        to_hdr += f";tag={uuid.uuid4().hex[:8]}"
    lines.append(f"To: {to_hdr}")

    lines.append(f"Call-ID: {request.call_id}")
    lines.append(f"CSeq: {request.cseq}")

    if extra_headers:
        for k, v in extra_headers.items():
            lines.append(f"{k}: {v}")

    content_length = len(body.encode()) if body else 0
    lines.append(f"Content-Length: {content_length}")

    msg = "\r\n".join(lines) + "\r\n\r\n"
    if body:
        msg += body
    return msg


class SIPRegistrar:
    """Minimal SIP registrar and call proxy."""

    def __init__(self, host: str = "0.0.0.0", port: int = 5060, lan_ip: str = "127.0.0.1"):
        self.host = host
        self.port = port
        self.lan_ip = lan_ip
        self.sock: Optional[socket.socket] = None
        self.registrations: dict[str, Registration] = {}
        self.dialogs: dict[str, Dialog] = {}
        self._running = False
        self._lock = threading.Lock()
        self._on_phone_registered: Optional[callable] = None

    def set_phone_registered_callback(self, callback):
        """Called when the phone extension registers (for auto-call)."""
        self._on_phone_registered = callback

    def is_extension_registered(self, extension: str) -> bool:
        with self._lock:
            reg = self.registrations.get(extension)
            return reg is not None and not reg.is_expired

    def get_registration(self, extension: str) -> Optional[Registration]:
        with self._lock:
            reg = self.registrations.get(extension)
            if reg and not reg.is_expired:
                return reg
        return None

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self._running = True
        logger.info(f"SIP Registrar listening on {self.host}:{self.port}")

        thread = threading.Thread(target=self._receive_loop, daemon=True)
        thread.start()

    def stop(self):
        self._running = False
        if self.sock:
            self.sock.close()

    def _receive_loop(self):
        while self._running:
            try:
                data, addr = self.sock.recvfrom(8192)
                msg_str = data.decode("utf-8", errors="replace")
                self._handle_message(msg_str, addr)
            except OSError:
                if self._running:
                    logger.error("Socket error in registrar", exc_info=True)
                break
            except Exception:
                logger.error("Error handling SIP message", exc_info=True)

    def _handle_message(self, raw: str, addr: tuple):
        try:
            msg = SIPMessage(raw)
        except Exception:
            logger.warning(f"Failed to parse SIP message from {addr}")
            return

        if msg.is_request:
            method = msg.method
            logger.debug(f"SIP {method} from {addr}")
            if method == "REGISTER":
                self._handle_register(msg, addr)
            elif method == "INVITE":
                self._handle_invite(msg, addr)
            elif method == "ACK":
                self._handle_ack(msg, addr)
            elif method == "BYE":
                self._handle_bye(msg, addr)
            elif method == "CANCEL":
                self._handle_cancel(msg, addr)
            elif method == "OPTIONS":
                self._handle_options(msg, addr)
            else:
                logger.debug(f"Ignoring SIP method: {method}")
        elif msg.is_response:
            self._handle_response(msg, addr)

    def _handle_register(self, msg: SIPMessage, addr: tuple):
        """Accept registration and store contact."""
        # Extract extension from To header
        ext = _extract_extension(msg.to_header)
        if not ext:
            ext = _extract_extension(msg.request_uri)

        contact = msg.contact
        # Parse Expires header or contact expires param
        expires_hdr = msg.get_header("expires")
        expires = int(expires_hdr) if expires_hdr else 3600

        if expires == 0:
            # Unregister
            with self._lock:
                self.registrations.pop(ext, None)
            logger.info(f"Extension {ext} unregistered")
        else:
            # Extract actual contact address
            contact_host, contact_port = addr  # Use source address as contact
            # Also try to parse from Contact header
            if contact:
                parsed_host, parsed_port = _extract_uri_host_port(contact)
                if parsed_host and parsed_host != "0.0.0.0":
                    contact_host = parsed_host
                    contact_port = parsed_port

            reg = Registration(
                extension=ext,
                contact_uri=contact or f"sip:{ext}@{addr[0]}:{addr[1]}",
                contact_addr=(contact_host, contact_port),
                expires=expires,
                registered_at=time.time(),
            )
            with self._lock:
                self.registrations[ext] = reg
            logger.info(f"Extension {ext} registered at {contact_host}:{contact_port}")

            # Notify if phone registered (for auto-call)
            from voice_dispatch.config import PHONE_EXTENSION
            if ext == PHONE_EXTENSION and self._on_phone_registered:
                threading.Thread(target=self._on_phone_registered, daemon=True).start()

        # Send 200 OK
        response = _build_response(
            msg, 200, "OK",
            extra_headers={
                "Contact": contact or f"<sip:{ext}@{self.lan_ip}:{self.port}>",
                "Expires": str(expires),
            }
        )
        self.sock.sendto(response.encode(), addr)

    def _handle_invite(self, msg: SIPMessage, addr: tuple):
        """Route INVITE to the target extension."""
        target_ext = _extract_extension(msg.request_uri)
        logger.info(f"INVITE for extension {target_ext} from {addr}")

        reg = self.get_registration(target_ext)
        if not reg:
            # 404 Not Found
            response = _build_response(msg, 404, "Not Found")
            self.sock.sendto(response.encode(), addr)
            logger.warning(f"Extension {target_ext} not registered")
            return

        # Send 100 Trying back to caller
        trying = _build_response(msg, 100, "Trying")
        self.sock.sendto(trying.encode(), addr)

        # Store dialog for routing responses
        dialog = Dialog(
            call_id=msg.call_id,
            caller_addr=addr,
            callee_addr=reg.contact_addr,
        )
        with self._lock:
            self.dialogs[msg.call_id] = dialog

        # Add our Via header and forward to callee
        our_via = f"SIP/2.0/UDP {self.lan_ip}:{self.port};branch=z9hG4bK{uuid.uuid4().hex[:12]}"
        forwarded = self._add_via_and_forward(msg.raw, our_via)
        self.sock.sendto(forwarded.encode(), reg.contact_addr)
        logger.info(f"Forwarded INVITE to {reg.contact_addr}")

    def _handle_response(self, msg: SIPMessage, addr: tuple):
        """Forward response back to the caller."""
        call_id = msg.call_id
        with self._lock:
            dialog = self.dialogs.get(call_id)

        if not dialog:
            logger.debug(f"No dialog for response Call-ID {call_id}")
            return

        # Remove our top Via header before forwarding
        forwarded = self._remove_top_via(msg.raw)

        # Determine direction: if from callee → send to caller, and vice versa
        if addr == dialog.callee_addr or addr[0] == dialog.callee_addr[0]:
            self.sock.sendto(forwarded.encode(), dialog.caller_addr)
            logger.debug(f"Forwarded {msg.status_code} to caller {dialog.caller_addr}")
        else:
            self.sock.sendto(forwarded.encode(), dialog.callee_addr)
            logger.debug(f"Forwarded {msg.status_code} to callee {dialog.callee_addr}")

        # Update dialog state
        if msg.status_code == 180:
            dialog.state = "ringing"
        elif msg.status_code == 200:
            dialog.state = "confirmed"

    def _handle_ack(self, msg: SIPMessage, addr: tuple):
        """Forward ACK to callee."""
        call_id = msg.call_id
        with self._lock:
            dialog = self.dialogs.get(call_id)
        if dialog:
            our_via = f"SIP/2.0/UDP {self.lan_ip}:{self.port};branch=z9hG4bK{uuid.uuid4().hex[:12]}"
            forwarded = self._add_via_and_forward(msg.raw, our_via)
            target = dialog.callee_addr if addr == dialog.caller_addr or addr[0] == dialog.caller_addr[0] else dialog.caller_addr
            self.sock.sendto(forwarded.encode(), target)

    def _handle_bye(self, msg: SIPMessage, addr: tuple):
        """Forward BYE and clean up dialog."""
        call_id = msg.call_id
        with self._lock:
            dialog = self.dialogs.get(call_id)

        if dialog:
            # Forward to the other party
            if addr == dialog.caller_addr or addr[0] == dialog.caller_addr[0]:
                target = dialog.callee_addr
            else:
                target = dialog.caller_addr

            our_via = f"SIP/2.0/UDP {self.lan_ip}:{self.port};branch=z9hG4bK{uuid.uuid4().hex[:12]}"
            forwarded = self._add_via_and_forward(msg.raw, our_via)
            self.sock.sendto(forwarded.encode(), target)

            # Send 200 OK back to sender
            response = _build_response(msg, 200, "OK")
            self.sock.sendto(response.encode(), addr)

            # Clean up
            with self._lock:
                self.dialogs.pop(call_id, None)
            logger.info(f"Call {call_id} terminated (BYE)")
        else:
            # No dialog, just respond 200 OK
            response = _build_response(msg, 200, "OK")
            self.sock.sendto(response.encode(), addr)

    def _handle_cancel(self, msg: SIPMessage, addr: tuple):
        """Handle CANCEL — cancel a pending INVITE."""
        call_id = msg.call_id
        # Send 200 OK for the CANCEL
        response = _build_response(msg, 200, "OK")
        self.sock.sendto(response.encode(), addr)

        with self._lock:
            dialog = self.dialogs.get(call_id)
        if dialog:
            # Send CANCEL to callee
            our_via = f"SIP/2.0/UDP {self.lan_ip}:{self.port};branch=z9hG4bK{uuid.uuid4().hex[:12]}"
            forwarded = self._add_via_and_forward(msg.raw, our_via)
            self.sock.sendto(forwarded.encode(), dialog.callee_addr)
            with self._lock:
                self.dialogs.pop(call_id, None)

    def _handle_options(self, msg: SIPMessage, addr: tuple):
        """Respond to OPTIONS (keepalive / capability check)."""
        response = _build_response(
            msg, 200, "OK",
            extra_headers={"Allow": "INVITE, ACK, BYE, CANCEL, OPTIONS, REGISTER"}
        )
        self.sock.sendto(response.encode(), addr)

    def _add_via_and_forward(self, raw: str, via: str) -> str:
        """Add our Via header as the topmost Via."""
        lines = raw.split("\r\n")
        result = [lines[0]]  # Request line
        via_inserted = False
        for line in lines[1:]:
            if not via_inserted and (line.lower().startswith("via:") or line == ""):
                result.append(f"Via: {via}")
                via_inserted = True
            result.append(line)
        if not via_inserted:
            result.insert(1, f"Via: {via}")
        return "\r\n".join(result)

    def _remove_top_via(self, raw: str) -> str:
        """Remove the topmost Via header (ours) from a response."""
        lines = raw.split("\r\n")
        result = [lines[0]]  # Status line
        removed = False
        for line in lines[1:]:
            if not removed and line.lower().startswith("via:"):
                # Check if this is our Via
                if self.lan_ip in line or f":{self.port}" in line:
                    removed = True
                    continue
            result.append(line)
        return "\r\n".join(result)
