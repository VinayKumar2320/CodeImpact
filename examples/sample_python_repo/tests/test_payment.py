from payment import calculate_fee, process_payment

def test_calculate_fee():
    assert calculate_fee(500) == 50
    assert calculate_fee(5000) == 150
    assert calculate_fee(20000) == 300
    assert calculate_fee(-10) == 0

def test_process_payment():
    valid_tok = "tok_valid_abcdef123456"
    assert process_payment("usr_1", valid_tok, 1500) is True
    assert process_payment("usr_1", "bad", 1500) is False
