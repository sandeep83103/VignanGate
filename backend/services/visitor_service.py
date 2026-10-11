import hmac
import hashlib
import json
import base64
import time
import io
import datetime
from typing import Dict, Any, Optional, Tuple
import qrcode
from PIL import Image

SECRET_KEY = "vignan-vfstr-super-secure-gate-key-2026"

class VisitorService:
    """
    Manages the digital lifecycle of campus visitors:
    1. Pre-registration & Intake
    2. Host Approval Workflow
    3. Cryptographically Signed QR Pass Generation
    4. Optical Gate Scanner Validation
    """

    @staticmethod
    def generate_signed_token(visitor_id: str, name: str, host: str, gate: str, valid_hours: int = 8) -> str:
        """
        Generates a cryptographically signed, tamper-evident token (HMAC-SHA256).
        Token payload: Base64(JSON) + '.' + Signature
        """
        now = int(time.time())
        expires = now + (valid_hours * 3600)

        payload = {
            "vid": visitor_id,
            "name": name,
            "host": host,
            "gate": gate,
            "iat": now,
            "exp": expires
        }

        raw_payload = json.dumps(payload, separators=(',', ':'))
        b64_payload = base64.urlsafe_b64encode(raw_payload.encode()).decode()

        signature = hmac.new(
            SECRET_KEY.encode(),
            b64_payload.encode(),
            hashlib.sha256
        ).hexdigest()[:24]

        return f"{b64_payload}.{signature}"

    @staticmethod
    def verify_token(token: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Verifies signature, tamper-evidence, and expiration of the QR token.
        Returns: (is_valid, payload, error_message)
        """
        try:
            parts = token.split('.')
            if len(parts) != 2:
                return False, None, "Malformed QR token structure"

            b64_payload, signature = parts[0], parts[1]

            # Recompute signature
            expected_sig = hmac.new(
                SECRET_KEY.encode(),
                b64_payload.encode(),
                hashlib.sha256
            ).hexdigest()[:24]

            if not hmac.compare_digest(signature, expected_sig):
                return False, None, "Cryptographic signature verification failed (Tampered QR)"

            # Decode payload
            raw_payload = base64.urlsafe_b64decode(b64_payload.encode()).decode()
            payload = json.loads(raw_payload)

            now = int(time.time())
            if now > payload.get("exp", 0):
                return False, payload, "Visitor pass expired"

            return True, payload, "Pass Verified"

        except Exception as e:
            return False, None, f"Token decode error: {str(e)}"

    @staticmethod
    def generate_qr_image_bytes(token: str) -> bytes:
        """Generates a high-contrast PNG QR Code image as bytes."""
        qr = qrcode.QRCode(
            version=2,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=3,
        )
        qr.add_data(token)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#17233b", back_color="#ffffff")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()

visitor_service = VisitorService()
