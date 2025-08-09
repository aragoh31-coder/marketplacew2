import hashlib
import random
import string


def generate_pow_token():
    """Generate a valid PoW token that starts with 0000 when hashed"""
    while True:
        token = "".join(random.choices(string.ascii_letters + string.digits, k=10))
        hash_result = hashlib.sha256(token.encode()).hexdigest()
        if hash_result.startswith("0000"):
            return token, hash_result


if __name__ == "__main__":
    token, hash_result = generate_pow_token()
    print(f"Valid PoW token: {token}")
    print(f"Hash: {hash_result}")
