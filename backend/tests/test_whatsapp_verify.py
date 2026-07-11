import hashlib
import hmac

from app.whatsapp.verify import iter_incoming_messages, verify_signature


def test_verify_signature_ok():
    secret = "s3cr3t"
    body = b'{"a":1}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(secret, body, sig)
    assert not verify_signature(secret, body, "sha256=deadbeef")
    assert not verify_signature(secret, body, None)


def test_iter_text_message():
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "5491100000000", "id": "wamid.ABC", "type": "text",
                        "text": {"body": "cena 20 euros"},
                    }]
                }
            }]
        }]
    }
    msgs = iter_incoming_messages(payload)
    assert len(msgs) == 1
    assert msgs[0].wa_id == "5491100000000"
    assert msgs[0].wamid == "wamid.ABC"
    assert msgs[0].type == "text"
    assert msgs[0].text == "cena 20 euros"


def test_iter_interactive_button():
    payload = {"entry": [{"changes": [{"value": {"messages": [{
        "from": "549110", "id": "wamid.X", "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": "split_mine:tok123"}},
    }]}}]}]}
    msgs = iter_incoming_messages(payload)
    assert msgs[0].type == "interactive"
    assert msgs[0].interactive_id == "split_mine:tok123"
