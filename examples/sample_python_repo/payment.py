from auth import validate_session_token

def calculate_fee(amount_cents: int) -> int:
    if amount_cents <= 0:
        return 0
    elif amount_cents < 1000:
        return 50
    elif amount_cents < 10000:
        return 150
    else:
        return 300


def process_payment(user_id: str, token: str, amount_cents: int) -> bool:
    if not validate_session_token(token):
        return False

    fee = calculate_fee(amount_cents)
    total = amount_cents + fee
    if total <= 0:
        return False
    return True
