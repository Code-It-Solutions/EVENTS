# Church hierarchy data for KAYO
# Archdeaconries and their Parishes

CHURCH_DATA = {
    "Nambale Archdeaconry": [
        "Nasira Parish",
        "St Thomas Nambale Cathedral Parish",
        "Malanga Parish",
        "Ebuwanga Parish",
        "Emaduwa Parish",
        "Buloma Parish"
    ],
    "Namaindi Archdeaconry": [
        "Namaindi Parish",
        "Mulwakari Parish",
        "Kaludeka Parish"
    ],
    "Khasoko Archdeaconry": [
        "Khasoko Parish",
        "Sikinga Parish",
        "Mungore Parish",
        "Namusasi Parish",
        "Lupida Parish"
    ],
    "Lugulu Archdeaconry": [
        "Lugulu Parish",
        "Buduma Parish",
        "Bukuyudi Parish",
        "Emasinde Parish"
    ],
    "Bukhalalire Archdeaconry": [
        "Bukhalalire Parish",
        "Bumutiru Parish",
        "Simuli Parish",
        "Busiada Parish"
    ],
    "Bujumba Archdeaconry": [
        "Bujumba Parish",
        "Igula Parish",
        "Bumala Parish",
        "Dadira Parish"
    ],
    "Busende Archdeaconry": [
        "Busende Parish",
        "Nasewa Parish",
        "Budokomi Parish",
        "Burumba Parish",
        "Mayenje Parish",
        "Mundaya Parish",
        "Bugeng'i Parish",
        "Emaseno Parish"
    ],
    "Busia Archdeaconry": [
        "St. Stephen's Busia Parish"
    ],
    "Namboboto Archdeaconry": [
        "Namboboto Parish",
        "Busibi Parish",
        "Funyula Parish",
        "Odiado Parish",
        "Nyakwaka Parish",
        "Luchululo Parish",
        "Lugala Parish",
        "Nyakhobi Parish",
        "Wakhungu Parish"
    ],
    "Sigalame Archdeaconry": [
        "Sigalame Parish",
        "Nandereka Parish",
        "Namahudu Parish",
        "Neyayo Parish",
        "Namasari Parish"
    ],
    "Lugare Archdeaconry": [
        "Port-Victoria Parish",
        "Lugare Parish",
        "Osieko Parish",
        "Budalangi Parish"
    ]
}

# Get list of archdeaconries for dropdown
def get_archdeaconries():
    """Returns list of tuples for SelectField choices"""
    choices = [('', 'Select Archdeaconry')]
    choices.extend([(arch, arch) for arch in sorted(CHURCH_DATA.keys())])
    return choices

# Get parishes for a specific archdeaconry
def get_parishes(archdeaconry=None):
    """Returns list of tuples for SelectField choices"""
    if archdeaconry and archdeaconry in CHURCH_DATA:
        choices = [('', 'Select Parish')]
        choices.extend([(p, p) for p in sorted(CHURCH_DATA[archdeaconry])])
        return choices
    
    # Return all parishes if no archdeaconry specified
    choices = [('', 'Select Parish')]
    all_parishes = []
    for parishes in CHURCH_DATA.values():
        all_parishes.extend(parishes)
    choices.extend([(p, p) for p in sorted(set(all_parishes))])
    return choices

# Get all parishes as flat list
def get_all_parishes():
    """Returns all parishes as a flat list"""
    all_parishes = []
    for parishes in CHURCH_DATA.values():
        all_parishes.extend(parishes)
    return sorted(set(all_parishes))
