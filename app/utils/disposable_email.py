"""Block throwaway email providers at registration."""

# shortcut: static list of the most common providers; for full coverage swap in a maintained
# list (e.g. github.com/disposable-email-domains) loaded from a file and refreshed periodically.
DISPOSABLE_DOMAINS = frozenset("""
10minutemail.com 10minutemail.net 20minutemail.com 33mail.com anonbox.net burnermail.io
discard.email dispostable.com dropmail.me emailondeck.com emailfake.com email-fake.com fakeinbox.com
fakemail.net getairmail.com getnada.com guerrillamail.biz guerrillamail.com guerrillamail.de
guerrillamail.info guerrillamail.net guerrillamail.org guerrillamailblock.com grr.la harakirimail.com
inboxbear.com incognitomail.org jetable.org kasmail.com mail.tm mailcatch.com maildrop.cc mailinator.com
mailinator.net mailinator2.com mailnesia.com mailpoof.com mailsac.com mailtemp.net mintemail.com
moakt.com mohmal.com mytemp.email mytrashmail.com nada.email no-spam.ws nowmymail.com sharklasers.com
spam4.me spambog.com spambox.us spamgourmet.com spamex.com tempail.com tempinbox.com tempmail.com
tempmail.net tempmail.plus tempmailo.com temp-mail.io temp-mail.org tempr.email throwawaymail.com
trash-mail.com trashmail.com trashmail.de trashmail.net trbvm.com wegwerfmail.de yopmail.com yopmail.fr
yopmail.net zetmail.com 1secmail.com 1secmail.net 1secmail.org emltmp.com tmpmail.org tmpmail.net
""".split())


def is_disposable(email: str) -> bool:
    """True if the email's domain (or any parent domain) is a known throwaway provider."""
    domain = (email or "").rsplit("@", 1)[-1].strip().lower().rstrip(".")
    parts = domain.split(".")
    return any(".".join(parts[i:]) in DISPOSABLE_DOMAINS for i in range(len(parts) - 1))
