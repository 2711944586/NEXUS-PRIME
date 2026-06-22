import hmac
import re

from .captcha import CAPTCHA_TERMS_VERSION, captcha_answer_hash, decode_captcha_token, normalize_captcha_answer


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
PHONE_PATTERN = re.compile(r"^[0-9+\-\s()]{6,24}$")


def validate_register_gate(payload):
    accepted_terms = bool(payload.get("accepted_terms"))
    accepted_privacy = bool(payload.get("accepted_privacy"))
    accepted_data_scope = bool(payload.get("accepted_data_scope"))
    if not (accepted_terms and accepted_privacy and accepted_data_scope):
        return "请先阅读并同意服务许可、隐私声明和数据使用范围"
    if payload.get("terms_version") != CAPTCHA_TERMS_VERSION:
        return "许可版本已更新，请刷新注册页后重新确认"
    challenge = decode_captcha_token(payload.get("captcha_token"))
    if not challenge:
        return "验证码已失效，请刷新验证码后重试"
    answer = normalize_captcha_answer(payload.get("captcha_answer"))
    expected_hash = str(challenge.get("answer_hash") or "")
    nonce = str(challenge.get("nonce") or "")
    if not answer or not nonce or not expected_hash or not hmac.compare_digest(captcha_answer_hash(answer, nonce), expected_hash):
        return "验证码识别失败，请重新输入"
    return None


def normalize_register_payload(payload):
    email = str(payload.get("email") or "").strip().lower()
    username = str(payload.get("username") or "").strip()
    full_name = str(payload.get("full_name") or "").strip()
    position = str(payload.get("position") or "").strip()
    department_name = str(payload.get("department_name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    password = str(payload.get("password") or "")
    return {
        "email": email,
        "username": username,
        "full_name": full_name,
        "position": position,
        "department_name": department_name,
        "phone": phone,
        "password": password,
    }


def validate_register_profile(payload):
    values = normalize_register_payload(payload)
    errors = {}
    if not values["full_name"] or len(values["full_name"]) < 2:
        errors["full_name"] = "请输入至少 2 个字符的姓名或岗位昵称"
    if not USERNAME_PATTERN.match(values["username"]):
        errors["username"] = "用户名需为 3-32 位字母、数字、点、下划线或短横线"
    if not EMAIL_PATTERN.match(values["email"]):
        errors["email"] = "请输入有效邮箱地址"
    password = values["password"]
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        errors["password"] = "密码至少 8 位，并同时包含字母和数字"
    if not values["position"] or len(values["position"]) < 2:
        errors["position"] = "请输入岗位或业务角色"
    if not values["department_name"] or len(values["department_name"]) < 2:
        errors["department_name"] = "请输入所属部门"
    if values["phone"] and not PHONE_PATTERN.match(values["phone"]):
        errors["phone"] = "手机号格式不符合要求"
    return values, errors
