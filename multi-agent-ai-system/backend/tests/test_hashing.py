from app.auth.security import get_password_hash, verify_password

def test_hashing():
    pwd = "secret"
    hashed = get_password_hash(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed)
    assert not verify_password("wrong", hashed)
