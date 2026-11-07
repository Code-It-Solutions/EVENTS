from app.utils.disposable_email import is_disposable


def test_known_and_subdomain_blocked():
    for e in ["a@mailinator.com", "A@YOPMAIL.COM", "x@sub.guerrillamail.com", "y@10minutemail.com."]:
        assert is_disposable(e), e


def test_normal_domains_allowed():
    for e in ["a@gmail.com", "b@afrionexsolutions.com", "c@mailinator.com.ke.example.org", "bad", ""]:
        assert not is_disposable(e), e
