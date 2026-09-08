from services.orders import rupiah
from services.payment import amount_from_payload, normalize_payload, normalize_status, signature_matches


def test_rupiah():
    assert rupiah(12500) == "Rp12.500"


def test_nested_webhook_payload():
    payload = {"data": {"status": "paid", "total_amount": "10016.00"}}
    data = normalize_payload(payload)
    assert normalize_status(data["status"]) == "PAID"
    assert amount_from_payload(data) == 10016


def test_signature_requires_exact_value():
    assert signature_matches("abc", "abc") is True
    assert signature_matches("abc", "ABC") is False
    assert signature_matches("abc", None) is False
