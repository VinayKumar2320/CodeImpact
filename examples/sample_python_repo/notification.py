from payment import process_payment

def send_receipt(user_email: str, user_id: str, token: str, amount_cents: int) -> bool:
    success = process_payment(user_id, token, amount_cents)
    if not success:
        return False
    # Send email notification
    return True
