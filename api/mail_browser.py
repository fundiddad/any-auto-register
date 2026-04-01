"""LuckMail 邮箱浏览接口。"""

from dataclasses import asdict, is_dataclass
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from core.config_store import config_store
from core.luckmail import LuckMailClient


router = APIRouter(prefix="/mail-browser", tags=["mail-browser"])


def _serialize(value: Any) -> Any:
    """统一把 SDK dataclass 结果转成可直接返回的 dict。"""
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def _get_luckmail_settings() -> dict[str, str]:
    """从全局配置读取 LuckMail 连接信息。"""
    base_url = (
        config_store.get("luckmail_base_url", "https://mails.luckyous.com/").strip()
        or "https://mails.luckyous.com/"
    )
    api_key = config_store.get("luckmail_api_key", "").strip()
    return {
        "base_url": base_url,
        "api_key": api_key,
    }


def _build_client() -> LuckMailClient:
    """在请求开始时临时创建客户端，避免长期持有连接状态。"""
    settings = _get_luckmail_settings()
    if not settings["api_key"]:
        raise HTTPException(400, "请先在全局配置里填写 LuckMail API Key")
    return LuckMailClient(
        base_url=settings["base_url"],
        api_key=settings["api_key"],
    )


def _raise_luckmail_error(exc: Exception) -> None:
    """把第三方错误统一映射成前端可读的 HTTP 错误。"""
    raise HTTPException(502, f"LuckMail 请求失败: {exc}") from exc


@router.get("/profile")
def get_profile():
    """返回当前账号概览，方便前端显示余额和站点信息。"""
    settings = _get_luckmail_settings()
    if not settings["api_key"]:
        return {
            "configured": False,
            "base_url": settings["base_url"],
            "username": "",
            "email": "",
            "balance": "",
        }

    try:
        with _build_client() as client:
            info = client.user.get_user_info()
    except HTTPException:
        raise
    except Exception as exc:
        _raise_luckmail_error(exc)

    return {
        "configured": True,
        "base_url": settings["base_url"],
        "username": info.username,
        "email": info.email,
        "balance": info.balance,
        "status": info.status,
    }


@router.get("/purchases")
def get_purchases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = "",
    tag_id: Optional[int] = Query(None),
    user_disabled: Optional[int] = Query(None),
):
    """分页读取可浏览的已购邮箱列表。"""
    try:
        with _build_client() as client:
            result = client.user.get_purchases(
                page=page,
                page_size=page_size,
                keyword=keyword.strip() or None,
                tag_id=tag_id,
                user_disabled=user_disabled,
            )
    except HTTPException:
        raise
    except Exception as exc:
        _raise_luckmail_error(exc)

    return {
        "items": [_serialize(item) for item in result.list],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
    }


@router.get("/mails")
def get_mails(token: str = Query(..., min_length=1)):
    """按 token 读取单个邮箱的邮件列表。"""
    try:
        with _build_client() as client:
            result = client.user.get_token_mails(token.strip())
    except HTTPException:
        raise
    except Exception as exc:
        _raise_luckmail_error(exc)

    return {
        "email_address": result.email_address,
        "project": result.project,
        "warranty_until": result.warranty_until,
        "mails": [_serialize(item) for item in result.mails],
    }


@router.get("/mail-detail")
def get_mail_detail(
    token: str = Query(..., min_length=1),
    message_id: str = Query(..., min_length=1),
):
    """读取单封邮件详情。"""
    try:
        with _build_client() as client:
            detail = client.user.get_token_mail_detail(
                token.strip(),
                message_id.strip(),
            )
    except HTTPException:
        raise
    except Exception as exc:
        _raise_luckmail_error(exc)

    return _serialize(detail)
