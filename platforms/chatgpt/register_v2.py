"""
注册流程引擎 V2。
基于 curl_cffi 的注册状态机，注册完成后先复用 ChatGPT 会话拿 session access_token，
再继续走一次 OAuth PKCE，把长期可刷新的 refresh_token 一并补齐。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Callable, Optional

from platforms.chatgpt.register import RegistrationResult

from .chatgpt_client import ChatGPTClient
from .oauth_client import OAuthClient
from .utils import generate_random_birthday, generate_random_name

logger = logging.getLogger(__name__)


class EmailServiceAdapter:
    """把旧版邮箱服务适配成 V2 OAuth 流程需要的接口。"""

    def __init__(self, email_service, email: str, log_fn):
        self.es = email_service
        self.email = email
        self.log_fn = log_fn
        self._used_codes: set[str] = set()

    def wait_for_verification_code(
        self,
        email: str,
        timeout: int = 60,
        otp_sent_at=None,
        exclude_codes=None,
    ):
        """等待邮箱 OTP，并避免重复返回已经试过的验证码。"""
        self.log_fn(f"正在等待邮箱 {email} 的验证码（{timeout}s）...")
        code = self.es.get_verification_code(
            timeout=timeout,
            otp_sent_at=otp_sent_at,
            exclude_codes=exclude_codes or self._used_codes,
        )
        if code:
            self._used_codes.add(code)
            self.log_fn(f"成功获取验证码: {code}")
        return code


class RegistrationEngineV2:
    def __init__(
        self,
        email_service,
        proxy_url: Optional[str] = None,
        browser_mode: str = "protocol",
        callback_logger: Optional[Callable[[str], None]] = None,
        task_uuid: Optional[str] = None,
        max_retries: int = 2,
        extra_config: Optional[dict] = None,
    ):
        self.email_service = email_service
        self.proxy_url = proxy_url
        self.browser_mode = browser_mode or "protocol"
        self.callback_logger = callback_logger
        self.task_uuid = task_uuid
        self.max_retries = max(1, int(max_retries or 1))
        self.extra_config = dict(extra_config or {})

        self.email = None
        self.password = None
        self.logs: list[str] = []

    def _log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        self.logs.append(log_message)
        if self.callback_logger:
            self.callback_logger(log_message)
        if level == "error":
            logger.error(log_message)
        else:
            logger.info(log_message)

    def _should_retry(self, message: str) -> bool:
        text = str(message or "").lower()
        retriable_markers = [
            "tls",
            "ssl",
            "curl: (35)",
            "authorize",
            "registration_disallowed",
            "http 400",
            "authorization code",
            "consent",
            "workspace",
            "organization",
            "otp",
            "session",
            "accesstoken",
            "next-auth",
        ]
        return any(marker in text for marker in retriable_markers)

    def _fetch_oauth_tokens(
        self,
        chatgpt_client: ChatGPTClient,
        email_addr: str,
        password: str,
        email_service_adapter: EmailServiceAdapter,
    ):
        """复用注册阶段的同一个会话，补齐 OAuth refresh_token。"""
        oauth_client = OAuthClient(
            config=self.extra_config,
            proxy=self.proxy_url,
            verbose=False,
            browser_mode=self.browser_mode,
        )
        # 关键点：沿用注册过程中已经登录过的 auth/chatgpt 会话，避免重新建登录态。
        oauth_client.session = chatgpt_client.session
        oauth_client._log = self._log

        token_data = oauth_client.login_and_get_tokens(
            email=email_addr,
            password=password,
            device_id=chatgpt_client.device_id,
            user_agent=chatgpt_client.ua,
            sec_ch_ua=chatgpt_client.sec_ch_ua,
            impersonate=chatgpt_client.impersonate,
            skymail_client=email_service_adapter,
        )
        if not token_data:
            return False, oauth_client.last_error or "OAuth 流程未返回 token"

        token_data["client_id"] = str(token_data.get("client_id") or oauth_client.oauth_client_id or "").strip()
        refresh_token = str(token_data.get("refresh_token") or "").strip()
        if not refresh_token:
            return False, "OAuth 流程成功结束，但未拿到 refresh_token"
        return True, token_data

    def run(self) -> RegistrationResult:
        result = RegistrationResult(success=False, logs=self.logs)
        try:
            last_error = ""
            for attempt in range(self.max_retries):
                try:
                    if attempt == 0:
                        self._log("=" * 60)
                        self._log("开始注册流程 V2（Session 复用 + OAuth RefreshToken 补齐）")
                        self._log(f"执行模式: {self.browser_mode}")
                        self._log("=" * 60)
                    else:
                        self._log(f"整条流程重试 {attempt + 1}/{self.max_retries} ...")
                        time.sleep(1)

                    email_data = self.email_service.create_email()
                    email_addr = self.email or (email_data.get("email") if email_data else None)
                    if not email_addr:
                        result.error_message = "创建邮箱失败"
                        return result

                    result.email = email_addr
                    pwd = self.password or "AAb1234567890!"
                    result.password = pwd

                    first_name, last_name = generate_random_name()
                    birthdate = generate_random_birthday()
                    self._log(f"邮箱: {email_addr}, 密码: {pwd}")
                    self._log(f"注册信息: {first_name} {last_name}, 生日: {birthdate}")

                    # 同一个邮箱适配器会被注册流程和后续 OAuth OTP 共用。
                    skymail_adapter = EmailServiceAdapter(self.email_service, email_addr, self._log)

                    chatgpt_client = ChatGPTClient(
                        proxy=self.proxy_url,
                        verbose=False,
                        browser_mode=self.browser_mode,
                    )
                    chatgpt_client._log = self._log

                    self._log("步骤 1/2: 执行注册状态机...")
                    success, msg = chatgpt_client.register_complete_flow(
                        email_addr,
                        pwd,
                        first_name,
                        last_name,
                        birthdate,
                        skymail_adapter,
                    )
                    if not success:
                        last_error = f"注册流程失败: {msg}"
                        if attempt < self.max_retries - 1 and self._should_retry(msg):
                            self._log(f"注册流程失败，准备整条流程重试: {msg}")
                            continue
                        result.error_message = last_error
                        return result

                    self._log("步骤 2/2: 复用注册会话，直接获取 ChatGPT Session / AccessToken...")
                    session_ok, session_result = chatgpt_client.reuse_session_and_get_tokens()
                    if not session_ok:
                        last_error = f"注册成功，但复用会话获取 AccessToken 失败: {session_result}"
                        if attempt < self.max_retries - 1:
                            self._log(f"{last_error}，准备整条流程重试")
                            continue
                        result.error_message = last_error
                        return result

                    self._log("Session Token 提取完成")
                    result.access_token = str(session_result.get("access_token") or "").strip()
                    result.session_token = str(session_result.get("session_token") or "").strip()
                    result.account_id = (
                        session_result.get("account_id")
                        or session_result.get("user_id")
                        or ("v2_acct_" + chatgpt_client.device_id[:8])
                    )
                    result.workspace_id = session_result.get("workspace_id", "")
                    result.metadata = {
                        "auth_provider": session_result.get("auth_provider", ""),
                        "expires": session_result.get("expires", ""),
                        "user_id": session_result.get("user_id", ""),
                        "user": session_result.get("user") or {},
                        "account": session_result.get("account") or {},
                    }

                    self._log("步骤 2.5/2: 复用当前登录会话执行 OAuth PKCE，补齐 RefreshToken...")
                    oauth_ok, oauth_result = self._fetch_oauth_tokens(
                        chatgpt_client=chatgpt_client,
                        email_addr=email_addr,
                        password=pwd,
                        email_service_adapter=skymail_adapter,
                    )
                    if oauth_ok:
                        oauth_data = oauth_result
                        result.refresh_token = str(oauth_data.get("refresh_token") or "").strip()
                        result.id_token = str(oauth_data.get("id_token") or "").strip()
                        # OAuth 可能返回更新后的 access_token，优先保存它，减少首次上传即过期的概率。
                        result.access_token = str(
                            oauth_data.get("access_token") or result.access_token or ""
                        ).strip()
                        result.metadata["oauth_refresh_token_ready"] = True
                        result.metadata["oauth_id_token_ready"] = bool(result.id_token)
                        result.metadata["oauth_client_id"] = str(oauth_data.get("client_id") or "").strip()
                        self._log("OAuth Token 提取完成，已拿到 refresh_token")
                    else:
                        oauth_error = str(oauth_result or "").strip()
                        result.metadata["oauth_refresh_token_ready"] = False
                        result.metadata["oauth_error"] = oauth_error
                        self._log(f"OAuth Token 提取失败，将仅保存 session access_token: {oauth_error}")

                    result.success = True
                    if result.workspace_id:
                        self._log(f"Session Workspace ID: {result.workspace_id}")

                    self._log("=" * 60)
                    self._log("注册流程成功结束")
                    self._log("=" * 60)
                    return result
                except Exception as attempt_error:
                    last_error = str(attempt_error)
                    if attempt < self.max_retries - 1 and self._should_retry(last_error):
                        self._log(f"本轮出现异常，准备整条流程重试: {last_error}")
                        continue
                    raise

            result.error_message = last_error or "注册失败"
            return result
        except Exception as exc:
            self._log(f"V2 注册全流程执行异常: {exc}", "error")
            import traceback

            traceback.print_exc()
            result.error_message = str(exc)
            return result
