from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from core.base_platform import Account, AccountStatus
from core.db import AccountModel, engine
from services.chatgpt_sync import (
    ensure_account_model_oauth_and_upload_to_cpa,
    has_cpa_upload_success,
    is_cli_proxy_enabled,
    update_account_model_cli_proxy_state,
    upload_account_model_to_cpa,
)
from services.cpa_manager import list_auth_files
from services.external_apps import install, list_status, start, start_all, stop, stop_all

router = APIRouter(prefix="/integrations", tags=["integrations"])


class BackfillRequest(BaseModel):
    platforms: list[str] = Field(default_factory=lambda: ["grok", "kiro"])
    account_ids: list[int] = Field(default_factory=list)
    pending_only: bool = False
    cli_proxy_only: bool = False
    status: Optional[str] = None
    email: Optional[str] = None


class ChatgptCliProxyMarkRequest(BaseModel):
    account_ids: list[int] = Field(default_factory=list)
    enabled: bool = True


class ChatgptOAuthBackfillRequest(BaseModel):
    account_ids: list[int] = Field(default_factory=list)
    only_enabled: bool = True


class ChatgptCpaStatusRequest(BaseModel):
    emails: list[str] = Field(default_factory=list)


def _to_account(model: AccountModel) -> Account:
    return Account(
        platform=model.platform,
        email=model.email,
        password=model.password,
        user_id=model.user_id,
        region=model.region,
        token=model.token,
        status=AccountStatus(model.status),
        extra=model.get_extra(),
    )


def _query_accounts(body: BackfillRequest | ChatgptOAuthBackfillRequest) -> list[AccountModel]:
    targets = set(getattr(body, "platforms", []) or [])
    with Session(engine) as s:
        q = select(AccountModel)
        if getattr(body, "account_ids", None):
            q = q.where(AccountModel.id.in_(body.account_ids))
            if targets:
                q = q.where(AccountModel.platform.in_(targets))
        elif targets:
            q = q.where(AccountModel.platform.in_(targets))

        if getattr(body, "status", None):
            q = q.where(AccountModel.status == body.status)
        if getattr(body, "email", None):
            q = q.where(AccountModel.email.contains(body.email))
        return list(s.exec(q).all())


@router.get("/services")
def get_services():
    return {"items": list_status()}


@router.post("/services/start-all")
def start_all_services():
    return {"items": start_all()}


@router.post("/services/stop-all")
def stop_all_services():
    return {"items": stop_all()}


@router.post("/services/{name}/start")
def start_service(name: str):
    return start(name)


@router.post("/services/{name}/install")
def install_service(name: str):
    return install(name)


@router.post("/services/{name}/stop")
def stop_service(name: str):
    return stop(name)


@router.post("/chatgpt/cli-proxy-mark")
def mark_chatgpt_cli_proxy_accounts(body: ChatgptCliProxyMarkRequest):
    summary = {"total": 0, "success": 0, "failed": 0, "items": []}
    if not body.account_ids:
        return summary

    with Session(engine) as s:
        rows = s.exec(
            select(AccountModel)
            .where(AccountModel.id.in_(body.account_ids))
            .where(AccountModel.platform == "chatgpt")
        ).all()

        for row in rows:
            update_account_model_cli_proxy_state(
                row,
                body.enabled,
                msg="已标记为 CLIProxyAPI 账号" if body.enabled else "已取消 CLIProxyAPI 标记",
                session=s,
                commit=False,
            )
            summary["items"].append(
                {
                    "platform": row.platform,
                    "email": row.email,
                    "results": [{"name": "CLIProxyAPI", "ok": True, "msg": "ok"}],
                }
            )
            summary["success"] += 1
            summary["total"] += 1
        s.commit()
    return summary


@router.post("/chatgpt/oauth-backfill")
def backfill_chatgpt_oauth(body: ChatgptOAuthBackfillRequest):
    summary = {"total": 0, "success": 0, "failed": 0, "items": []}
    if not body.account_ids:
        return summary

    with Session(engine) as s:
        rows = s.exec(
            select(AccountModel)
            .where(AccountModel.id.in_(body.account_ids))
            .where(AccountModel.platform == "chatgpt")
        ).all()

        for row in rows:
            item = {"platform": row.platform, "email": row.email, "results": []}
            if body.only_enabled and not is_cli_proxy_enabled(row):
                item["results"].append(
                    {"name": "OAuth", "ok": False, "msg": "账号未标记为 CLIProxyAPI 账号"}
                )
                summary["failed"] += 1
                summary["total"] += 1
                summary["items"].append(item)
                continue

            try:
                ok, msg = ensure_account_model_oauth_and_upload_to_cpa(
                    row,
                    session=s,
                    commit=False,
                )
                item["results"].append({"name": "OAuth+CPA", "ok": ok, "msg": msg})
                if ok:
                    summary["success"] += 1
                else:
                    summary["failed"] += 1
            except Exception as exc:
                s.rollback()
                item["results"].append({"name": "OAuth+CPA", "ok": False, "msg": str(exc)})
                summary["failed"] += 1
            summary["total"] += 1
            summary["items"].append(item)
        s.commit()
    return summary


@router.post("/chatgpt/cpa-statuses")
def get_chatgpt_cpa_statuses(body: ChatgptCpaStatusRequest):
    # 这里直接查询 CPA 的 auth-files，再按邮箱回传给前端，避免页面只看本地缓存状态。
    wanted = {
        str(email or "").strip().lower()
        for email in body.emails
        if str(email or "").strip()
    }
    if not wanted:
        return {"ok": True, "items": []}

    files = list_auth_files()
    by_email: dict[str, dict] = {}

    for item in files:
        raw_email = str(item.get("email", "") or "").strip().lower()
        raw_name = str(item.get("name", "") or "").strip().lower()
        if raw_name.endswith(".json"):
            raw_name = raw_name[:-5]
        email = raw_email or raw_name
        if not email or email not in wanted:
            continue

        status = str(item.get("status", "") or "").strip().lower()
        uploaded = bool(item.get("name")) and status != "error"
        candidate = {
            "email": email,
            "uploaded": uploaded,
            "uploaded_at": item.get("last_refresh") or item.get("updated_at") or "",
            "last_message": str(item.get("status", "") or "").strip(),
        }
        previous = by_email.get(email)
        if previous is None or (not previous.get("uploaded") and uploaded):
            by_email[email] = candidate

    return {"ok": True, "items": list(by_email.values())}


@router.post("/backfill")
def backfill_integrations(body: BackfillRequest):
    summary = {"total": 0, "success": 0, "failed": 0, "items": []}
    rows = _query_accounts(body)
    if body.pending_only:
        rows = [row for row in rows if row.platform != "chatgpt" or not has_cpa_upload_success(row)]
    if body.cli_proxy_only:
        rows = [row for row in rows if row.platform != "chatgpt" or is_cli_proxy_enabled(row)]

    if any(row.platform == "grok" for row in rows):
        from services.grok2api_runtime import ensure_grok2api_ready

        ok, msg = ensure_grok2api_ready()
        if not ok:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "items": [{"platform": "grok", "email": "", "results": [{"name": "grok2api", "ok": False, "msg": msg}]}],
            }

    with Session(engine) as s:
        for row in rows:
            item = {"platform": row.platform, "email": row.email, "results": []}
            try:
                if row.platform == "chatgpt":
                    ok, msg = upload_account_model_to_cpa(row, session=s, commit=False)
                    item["results"].append({"name": "CPA", "ok": ok, "msg": msg})
                elif row.platform == "grok":
                    from core.config_store import config_store
                    from platforms.grok.grok2api_upload import upload_to_grok2api

                    account = _to_account(row)
                    api_url = str(config_store.get("grok2api_url", "") or "").strip() or "http://127.0.0.1:8011"
                    app_key = str(config_store.get("grok2api_app_key", "") or "").strip() or "grok2api"
                    ok, msg = upload_to_grok2api(account, api_url=api_url, app_key=app_key)
                    item["results"].append({"name": "grok2api", "ok": ok, "msg": msg})
                elif row.platform == "kiro":
                    from core.config_store import config_store
                    from platforms.kiro.account_manager_upload import upload_to_kiro_manager

                    account = _to_account(row)
                    configured_path = str(config_store.get("kiro_manager_path", "") or "").strip() or None
                    ok, msg = upload_to_kiro_manager(account, path=configured_path)
                    item["results"].append({"name": "Kiro Manager", "ok": ok, "msg": msg})
                else:
                    item["results"].append({"name": "skip", "ok": False, "msg": "未配置对应导入目标"})
                    ok = False

                if all(result.get("ok") for result in item["results"]):
                    summary["success"] += 1
                else:
                    summary["failed"] += 1
            except Exception as exc:
                s.rollback()
                item["results"].append({"name": "error", "ok": False, "msg": str(exc)})
                summary["failed"] += 1

            summary["items"].append(item)
            summary["total"] += 1
        s.commit()
    return summary
