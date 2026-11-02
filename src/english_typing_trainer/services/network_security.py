from __future__ import annotations

import os
import sys


def configure_https_certificates() -> None:
    """Use bundled CA roots on Mac, while preserving an explicit user override."""
    if sys.platform == "darwin" and not os.environ.get("SSL_CERT_FILE"):
        import certifi

        os.environ["SSL_CERT_FILE"] = certifi.where()
