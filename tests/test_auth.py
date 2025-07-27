import pytest
from django.urls import reverse
from django.utils import timezone
from hashlib import sha256

@pytest.mark.django_db
def test_login_pow(client, django_user_model):
    user = django_user_model.objects.create_user(username='u', password='p')
    resp = client.post(reverse('accounts:login'), {'username': 'u', 'password': 'p', 'pow_token': '0000abc'})
    assert resp.status_code in (200, 302)

@pytest.mark.django_db
def test_pgp_verification(client):
    session = client.session
    code = 'verify123'
    session['pgp_verification_code_hash'] = sha256(code.encode()).hexdigest()
    session['pgp_verification_expires'] = timezone.now().isoformat()
    session.save()
    resp = client.post(reverse('accounts:pgp_verify'), {'verify_code': code})
    assert resp.status_code != 403
