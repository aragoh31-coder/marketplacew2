import hashlib

def validate_pow(request):
    pow_token = request.POST.get('pow_token')
    if not pow_token:
        return False
    return hashlib.sha256(pow_token.encode()).hexdigest().startswith('0000')
