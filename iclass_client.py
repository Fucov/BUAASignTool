from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import re
import time
from urllib.parse import unquote, urlsplit, urlunsplit

from Crypto.Cipher import AES


SSO_LOGIN_URL = "https://sso.buaa.edu.cn/login"
WEBVPN_CAS_LOGIN_URL = (
    "https://sso.buaa.edu.cn/login?"
    "service=https%3A%2F%2Fd.buaa.edu.cn%2Flogin%3Fcas_login%3Dtrue"
)
SSO_VPN_ENTRY = "https://d.buaa.edu.cn/"
ICLASS_MY_CENTER_URL = "https://iclass.buaa.edu.cn:8346/?type=jumpMyCenter"
VPN_OFFSET_CORRECTION_MS = -1000
WEBVPN_AES_KEY = b"wrdvpnisthebest!"


def _webvpn_encrypt_host(host):
    """Encrypt a host exactly as BUAA WebVPN does in proxied URLs."""
    plain = host.encode("utf-8")
    padded_length = ((len(plain) + 15) // 16) * 16
    padded = plain.ljust(padded_length, b"0")
    cipher = AES.new(WEBVPN_AES_KEY, AES.MODE_ECB)
    feedback = WEBVPN_AES_KEY
    encrypted = bytearray()

    for index in range(0, len(padded), 16):
        stream = cipher.encrypt(feedback)
        block = bytes(a ^ b for a, b in zip(padded[index:index + 16], stream))
        encrypted.extend(block)
        feedback = block

    return WEBVPN_AES_KEY.hex() + encrypted.hex()[:len(plain) * 2]


def to_webvpn_url(raw_url):
    """Convert a direct URL to BUAA WebVPN's protocol/port-aware form."""
    parsed = urlsplit(raw_url)
    if not parsed.hostname or parsed.hostname == "d.buaa.edu.cn":
        return raw_url

    if parsed.port is None:
        protocol = parsed.scheme
    elif (parsed.scheme, parsed.port) in (("http", 80), ("https", 443)):
        protocol = parsed.scheme
    else:
        protocol = f"{parsed.scheme}-{parsed.port}"

    tail = urlunsplit(("", "", parsed.path or "/", parsed.query, parsed.fragment))
    return f"https://d.buaa.edu.cn/{protocol}/{_webvpn_encrypt_host(parsed.hostname)}{tail}"


def get_sso_login_url(use_vpn):
    return to_webvpn_url(WEBVPN_CAS_LOGIN_URL) if use_vpn else SSO_LOGIN_URL


def extract_iclass_login_name(value):
    """Extract the transient loginName without turning base64 '+' into spaces."""
    if not value:
        return None
    match = re.search(r"loginName=([^&#\"'<>\s]+)", value, flags=re.IGNORECASE)
    return unquote(match.group(1)) if match else None


def get_network_urls(use_vpn):
    """Return the current iClass endpoint set for direct or WebVPN mode."""
    base = "https://iclass.buaa.edu.cn:8347"
    direct = {
        "service_home": base,
        "my_center": ICLASS_MY_CENTER_URL,
        "user_login": f"{base}/app/user/login.action",
        "course_list": f"{base}/app/choosecourse/get_myall_course.action",
        "semester_list": f"{base}/app/course/get_base_school_year.action",
        "course_sign_detail": f"{base}/app/my/get_my_course_sign_detail.action",
        "sign_timestamp": "http://iclass.buaa.edu.cn:8081/app/common/get_timestamp.action",
        "scan_sign": "http://iclass.buaa.edu.cn:8081/app/course/stu_scan_sign.action",
        "course_schedule_by_date": f"{base}/app/course/get_stu_course_sched.action",
    }
    if not use_vpn:
        return direct
    return {key: to_webvpn_url(value) for key, value in direct.items()}


def server_time_offset_from_date(date_header, now_ms=None, use_vpn=False):
    """Derive server clock offset from an HTTP Date header."""
    if not date_header:
        return VPN_OFFSET_CORRECTION_MS if use_vpn else 0

    try:
        server_time = parsedate_to_datetime(date_header)
        offset = int(server_time.timestamp() * 1000) - (
            int(now_ms) if now_ms is not None else int(time.time() * 1000)
        )
    except (TypeError, ValueError, OverflowError):
        offset = 0

    if use_vpn:
        offset += VPN_OFFSET_CORRECTION_MS
    return offset


def server_now_millis(offset_ms):
    return int(time.time() * 1000) + int(offset_ms or 0)


def api_status(data):
    if not isinstance(data, dict):
        return ""
    raw = data.get("STATUS", data.get("status", ""))
    return str(raw)


def is_status_ok(data):
    return api_status(data) == "0"


def status_means_no_data(data):
    return api_status(data) == "2"


def api_message(data, default=""):
    if not isinstance(data, dict):
        return default
    for key in ("ERRMSG", "ERRORMSG", "MSG", "message", "msg"):
        value = data.get(key)
        if value is not None and str(value):
            return str(value)
    return default


@dataclass(frozen=True)
class SignClassification:
    status: str
    message: str


def classify_sign_response(data):
    if is_status_ok(data):
        return SignClassification("success", api_message(data, "已提交"))

    message = api_message(data, "签到失败")
    if "已签到" in message:
        return SignClassification("skipped", message)
    return SignClassification("failed", message)


def value_to_string(data, key):
    if not isinstance(data, dict):
        return ""
    value = data.get(key)
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
