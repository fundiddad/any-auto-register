"""ChatGPT 账号与 CLIProxyAPI 同步相关的辅助逻辑。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from core.db import AccountModel, engine

CPA_SYNC_NAME = "cpa"
CLI_PROXY_SYNC_NAME = "cliproxyapi"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


def _get_account_extra(account: Any) -> dict[str, Any]:
    if hasattr(account, "get_extra"):
        try:
            extra = account.get_extra()
            if isinstance(extra, dict):
                return extra
        except Exception:
            pass
    extra = getattr(account, "extra", {})
    return extra if isinstance(extra, dict) else {}


def _get_sync_state(extra_or_account: Any, name: str) -> dict[str, Any]:
    extra = extra_or_account if isinstance(extra_or_account, dict) else _get_account_extra(extra_or_account)
    sync_statuses = extra.get("sync_statuses", {})
    if not isinstance(sync_statuses, dict):
        return {}
    state = sync_statuses.get(name, {})
    return state if isinstance(state, dict) else {}


def get_cpa_sync_state(extra_or_account: Any) -> dict[str, Any]:
    return _get_sync_state(extra_or_account, CPA_SYNC_NAME)


def get_cli_proxy_sync_state(extra_or_account: Any) -> dict[str, Any]:
    return _get_sync_state(extra_or_account, CLI_PROXY_SYNC_NAME)


def has_cpa_upload_success(extra_or_account: Any) -> bool:
    state = get_cpa_sync_state(extra_or_account)
    return bool(state.get("uploaded") or state.get("uploaded_at"))


def is_cli_proxy_enabled(extra_or_account: Any) -> bool:
    state = get_cli_proxy_sync_state(extra_or_account)
    return bool(state.get("enabled"))


def record_cpa_sync_result(extra: dict[str, Any], ok: bool, msg: str) -> dict[str, Any]:
    sync_statuses = extra.get("sync_statuses")
    if not isinstance(sync_statuses, dict):
        sync_statuses = {}

    state = sync_statuses.get(CPA_SYNC_NAME)
    if not isinstance(state, dict):
        state = {}

    now = _utcnow_iso()
    state["last_attempt_ok"] = bool(ok)
    state["last_message"] = msg
    state["last_attempt_at"] = now
    state["uploaded"] = bool(state.get("uploaded")) or bool(ok)
    if ok:
        state["uploaded_at"] = now

    sync_statuses[CPA_SYNC_NAME] = state
    extra["sync_statuses"] = sync_statuses
    return state


def set_cli_proxy_sync_enabled(
    extra: dict[str, Any],
    enabled: bool,
    *,
    message: str = "",
) -> dict[str, Any]:
    """标记当前账号是否属于 CLIProxyAPI 中已存在、允许维护的账号。"""
    sync_statuses = extra.get("sync_statuses")
    if not isinstance(sync_statuses, dict):
        sync_statuses = {}

    state = sync_statuses.get(CLI_PROXY_SYNC_NAME)
    if not isinstance(state, dict):
        state = {}

    state["enabled"] = bool(enabled)
    state["updated_at"] = _utcnow_iso()
    if message:
        state["message"] = message

    sync_statuses[CLI_PROXY_SYNC_NAME] = state
    extra["sync_statuses"] = sync_statuses
    return state


def build_chatgpt_sync_account(account: Any):
    extra = _get_account_extra(account)

    class _SyncAccount:
        pass

    obj = _SyncAccount()
    obj.email = getattr(account, "email", "")
    obj.password = getattr(account, "password", "")
    obj.access_token = extra.get("access_token") or getattr(account, "token", "")
    obj.refresh_token = extra.get("refresh_token", "")
    obj.id_token = extra.get("id_token", "")
    obj.session_token = extra.get("session_token", "")
    obj.client_id = extra.get("client_id", "app_EMoamEEZ73f0CkXaXp7hrann")
    obj.cookies = extra.get("cookies", "")
    return obj


class _MailboxOtpAdapter:
    """把 mailbox.wait_for_code 适配为 OAuthClient 的 OTP 回调接口。"""

    def __init__(self, mailbox, mail_account):
        self.mailbox = mailbox
        self.mail_account = mail_account
        self._used_codes: set[str] = set()
        try:
            # 先缓存当前邮件 ID，优先等待新验证码。
            self._before_ids = mailbox.get_current_ids(mail_account)
        except Exception:
            self._before_ids = None

    def wait_for_verification_code(
        self,
        email: str,
        timeout: int = 60,
        otp_sent_at=None,
        exclude_codes=None,
    ):
        del email, otp_sent_at
        codes = set(exclude_codes or set()) | self._used_codes
        for before_ids in (self._before_ids, None):
            code = self.mailbox.wait_for_code(
                self.mail_account,
                keyword="",
                timeout=timeout,
                before_ids=before_ids,
            )
            if code and code not in codes:
                self._used_codes.add(code)
                return code
        return None


def _build_oauth_mailbox_adapter(account: Any, proxy_url: str | None = None):
    """尽量恢复邮箱 OTP 能力，便于为旧账号补抓 refresh_token。"""
    from core.base_mailbox import MailboxAccount, create_mailbox
    from core.config_store import config_store

    extra = _get_account_extra(account)
    merged_extra = config_store.get_all().copy()
    for key, value in extra.items():
        if value not in (None, ""):
            merged_extra[key] = value

    provider = str(merged_extra.get("mail_provider", "") or "").strip()
    if not provider:
        return None

    mailbox = create_mailbox(provider=provider, extra=merged_extra, proxy=proxy_url)
    mail_account = MailboxAccount(
        email=str(getattr(account, "email", "") or "").strip(),
        account_id=str(extra.get("mailbox_token", "") or "").strip(),
    )
    return _MailboxOtpAdapter(mailbox, mail_account)


def ensure_chatgpt_account_oauth(
    account: Any,
    *,
    proxy_url: str | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    """为已有账号补齐或刷新 OAuth 凭据。"""
    from core.config_store import config_store
    from platforms.chatgpt.chatgpt_client import ChatGPTClient
    from platforms.chatgpt.oauth_client import OAuthClient
    from platforms.chatgpt.token_refresh import TokenRefreshManager

    sync_account = build_chatgpt_sync_account(account)
    if not getattr(account, "email", ""):
        return False, "账号缺少 email", {}
    if not getattr(account, "password", ""):
        return False, "账号缺少 password", {}

    refresh_token = str(getattr(sync_account, "refresh_token", "") or "").strip()
    if refresh_token:
        manager = TokenRefreshManager(proxy_url=proxy_url)
        refreshed = manager.refresh_by_oauth_token(
            refresh_token=refresh_token,
            client_id=getattr(sync_account, "client_id", "") or None,
        )
        if refreshed.success:
            return True, "已有 refresh_token，已完成 OAuth 刷新", {
                "access_token": refreshed.access_token,
                "refresh_token": refreshed.refresh_token or refresh_token,
            }

    # 旧账号缺 refresh_token 时，退回到邮箱 OTP 登录补抓。
    fingerprint = ChatGPTClient(proxy=proxy_url, verbose=False, browser_mode="protocol")
    oauth_client = OAuthClient(
        config=config_store.get_all(),
        proxy=proxy_url,
        verbose=False,
        browser_mode="protocol",
    )
    # 复用同一个浏览器指纹和会话，避免 Cookie 与 header 组合不一致。
    oauth_client.session = fingerprint.session
    otp_adapter = _build_oauth_mailbox_adapter(account, proxy_url=proxy_url)
    token_data = oauth_client.login_and_get_tokens(
        email=getattr(account, "email", ""),
        password=getattr(account, "password", ""),
        device_id=fingerprint.device_id,
        user_agent=fingerprint.ua,
        sec_ch_ua=fingerprint.sec_ch_ua,
        impersonate=fingerprint.impersonate,
        skymail_client=otp_adapter,
    )
    if not token_data:
        return False, oauth_client.last_error or "OAuth 登录未返回 token", {}

    new_refresh_token = str(token_data.get("refresh_token") or "").strip()
    if not new_refresh_token:
        return False, "OAuth 登录成功，但未拿到 refresh_token", {}
    return True, "OAuth 凭据补齐成功", token_data


def upload_chatgpt_account_to_cpa(
    account: Any,
    api_url: str | None = None,
    api_key: str | None = None,
) -> tuple[bool, str]:
    try:
        sync_account = build_chatgpt_sync_account(account)
        if not getattr(sync_account, "access_token", ""):
            return False, "账号缺少 access_token"

        from platforms.chatgpt.cpa_upload import generate_token_json, upload_to_cpa

        token_data = generate_token_json(sync_account)
        return upload_to_cpa(token_data, api_url=api_url, api_key=api_key)
    except Exception as exc:
        return False, f"上传异常: {exc}"


def update_account_model_cpa_sync(
    account: AccountModel,
    ok: bool,
    msg: str,
    session: Session | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    extra = account.get_extra()
    state = record_cpa_sync_result(extra, ok, msg)
    account.set_extra(extra)
    account.updated_at = _utcnow()
    if session is not None:
        session.add(account)
        if commit:
            session.commit()
            session.refresh(account)
    return state


def update_account_model_cli_proxy_state(
    account: AccountModel,
    enabled: bool,
    *,
    msg: str = "",
    session: Session | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    extra = account.get_extra()
    state = set_cli_proxy_sync_enabled(extra, enabled, message=msg)
    account.set_extra(extra)
    account.updated_at = _utcnow()
    if session is not None:
        session.add(account)
        if commit:
            session.commit()
            session.refresh(account)
    return state


def persist_cpa_sync_result(account: Any, ok: bool, msg: str) -> None:
    if isinstance(account, AccountModel) and account.id is not None:
        with Session(engine) as session:
            row = session.get(AccountModel, account.id)
            if row:
                update_account_model_cpa_sync(row, ok, msg, session=session, commit=True)
                return

    extra = getattr(account, "extra", None)
    if isinstance(extra, dict):
        record_cpa_sync_result(extra, ok, msg)


def upload_account_model_to_cpa(
    account: AccountModel,
    session: Session | None = None,
    api_url: str | None = None,
    api_key: str | None = None,
    commit: bool = True,
) -> tuple[bool, str]:
    ok, msg = upload_chatgpt_account_to_cpa(account, api_url=api_url, api_key=api_key)
    update_account_model_cpa_sync(account, ok, msg, session=session, commit=commit)
    if ok:
        # 上传成功后，自动视为已纳入 CLIProxyAPI 的维护范围。
        update_account_model_cli_proxy_state(
            account,
            True,
            msg="已上传到 CLIProxyAPI",
            session=session,
            commit=commit,
        )
    return ok, msg


def ensure_account_model_oauth_and_upload_to_cpa(
    account: AccountModel,
    *,
    session: Session | None = None,
    api_url: str | None = None,
    api_key: str | None = None,
    proxy_url: str | None = None,
    commit: bool = True,
) -> tuple[bool, str]:
    """先补 OAuth，再回传到 CLIProxyAPI，并把结果写回数据库。"""
    ok, oauth_msg, token_data = ensure_chatgpt_account_oauth(account, proxy_url=proxy_url)
    if not ok:
        update_account_model_cpa_sync(account, False, oauth_msg, session=session, commit=commit)
        return False, oauth_msg

    extra = account.get_extra()
    extra["access_token"] = str(token_data.get("access_token") or extra.get("access_token") or "").strip()
    extra["refresh_token"] = str(token_data.get("refresh_token") or extra.get("refresh_token") or "").strip()
    if token_data.get("id_token"):
        extra["id_token"] = str(token_data.get("id_token") or "").strip()
    if token_data.get("session_token"):
        extra["session_token"] = str(token_data.get("session_token") or "").strip()
    account.set_extra(extra)
    account.token = extra.get("access_token", "")
    account.updated_at = _utcnow()
    if session is not None:
        session.add(account)
        if commit:
            session.commit()
            session.refresh(account)

    upload_ok, upload_msg = upload_account_model_to_cpa(
        account,
        session=session,
        api_url=api_url,
        api_key=api_key,
        commit=commit,
    )
    if upload_ok:
        return True, f"{oauth_msg}；{upload_msg}"
    return False, upload_msg
