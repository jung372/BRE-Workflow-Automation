from .general import fetch_general
from .eiass   import fetch_eiass
from .kepco   import fetch_kepco


def fetch_site(site: dict, p_instance) -> tuple:
    """site['type'] 에 따라 알맞은 스크래퍼로 라우팅."""
    t = site.get("type")
    if t == "eiass":
        return fetch_eiass(site)
    if t == "kepco":
        return fetch_kepco(site, p_instance)
    return fetch_general(site, p_instance)
