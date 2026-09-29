import string
import random


def generate_secure_password(length=12) -> str:
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special_chars = "!@#$%&*()_+-="

    password = [
        random.choice(lowercase),
        random.choice(uppercase),
        random.choice(digits),
        random.choice(special_chars)
    ]

    all_chars = lowercase + uppercase + digits + special_chars
    for _ in range(length - len(password)):
        password.append(random.choice(all_chars))

    random.shuffle(password)
    return "".join(password)