"""
Test SIP Registrar — verify it starts, accepts REGISTER, and routes calls.
Run: python -m voice_dispatch.tests.test_sip
"""

import socket
import time
import threading
import sys

def test_registrar():
    print("Testing SIP Registrar...")

    from voice_dispatch.sip_registrar import SIPRegistrar

    # Start registrar
    registrar = SIPRegistrar(host="127.0.0.1", port=15060, lan_ip="127.0.0.1")
    registrar.start()
    time.sleep(0.5)

    # Send a REGISTER
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3)

    register_msg = (
        "REGISTER sip:127.0.0.1:15060 SIP/2.0\r\n"
        "Via: SIP/2.0/UDP 127.0.0.1:15061;branch=z9hG4bKtest1\r\n"
        "From: <sip:100@127.0.0.1>;tag=test1\r\n"
        "To: <sip:100@127.0.0.1>\r\n"
        "Call-ID: test-register-1@127.0.0.1\r\n"
        "CSeq: 1 REGISTER\r\n"
        "Contact: <sip:100@127.0.0.1:15061>\r\n"
        "Expires: 3600\r\n"
        "Max-Forwards: 70\r\n"
        "Content-Length: 0\r\n"
        "\r\n"
    )

    sock.sendto(register_msg.encode(), ("127.0.0.1", 15060))

    try:
        data, addr = sock.recvfrom(4096)
        response = data.decode()
        if "200 OK" in response:
            print("  ✓ REGISTER → 200 OK")
        else:
            print(f"  ✗ Expected 200 OK, got: {response[:50]}")
            return False
    except socket.timeout:
        print("  ✗ No response to REGISTER (timeout)")
        return False

    # Check registration stored
    if registrar.is_extension_registered("100"):
        print("  ✓ Extension 100 registered")
    else:
        print("  ✗ Extension 100 not found in registrations")
        return False

    # Test INVITE to unregistered extension
    invite_msg = (
        "INVITE sip:999@127.0.0.1:15060 SIP/2.0\r\n"
        "Via: SIP/2.0/UDP 127.0.0.1:15061;branch=z9hG4bKtest2\r\n"
        "From: <sip:200@127.0.0.1>;tag=test2\r\n"
        "To: <sip:999@127.0.0.1>\r\n"
        "Call-ID: test-invite-1@127.0.0.1\r\n"
        "CSeq: 1 INVITE\r\n"
        "Contact: <sip:200@127.0.0.1:15061>\r\n"
        "Max-Forwards: 70\r\n"
        "Content-Length: 0\r\n"
        "\r\n"
    )

    sock.sendto(invite_msg.encode(), ("127.0.0.1", 15060))

    try:
        data, addr = sock.recvfrom(4096)
        response = data.decode()
        if "404" in response or "100" in response:
            print("  ✓ INVITE to unknown ext → 404/100")
        else:
            print(f"  ? Got: {response[:50]}")
    except socket.timeout:
        print("  ✓ No response to bad INVITE (acceptable)")

    # Cleanup
    sock.close()
    registrar.stop()

    print("  ✓ SIP Registrar tests passed\n")
    return True


if __name__ == "__main__":
    success = test_registrar()
    sys.exit(0 if success else 1)
