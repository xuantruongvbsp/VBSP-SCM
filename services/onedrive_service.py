"""OneDrive Service — Upload file công văn lên OneDrive qua Microsoft Graph API.

Sử dụng Client Credentials (App-only auth) — không cần user login.
Cấu hình trong .streamlit/secrets.toml section [onedrive].
Fallback graceful: nếu chưa cấu hình hoặc lỗi → trả về KetQuaOneDrive(False, ...).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

import requests

import db
from logger import get_logger

logger = get_logger(__name__)

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_URL_TPL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
_CHUNK_SIZE = 4 * 1024 * 1024  # 4MB — giới hạn simple upload; trên sẽ dùng upload session


@dataclass
class KetQuaOneDrive:
    thanh_cong: bool
    url: str = ""
    loi: str = ""


def _kiem_tra_config() -> bool:
    """Kiểm tra secrets.toml có section [onedrive] với đủ thông tin không."""
    try:
        import streamlit as st
        cfg = st.secrets.get("onedrive", {})
        return bool(cfg.get("tenant_id") and cfg.get("client_id") and cfg.get("client_secret"))
    except Exception:
        return False


def _lay_cfg() -> dict:
    import streamlit as st
    return dict(st.secrets.get("onedrive", {}))


def _drive_prefix(cfg: dict) -> str:
    """Trả về prefix URL drive. Ưu tiên drive_id, fallback user_id."""
    drive_id = (cfg.get("drive_id") or "").strip()
    user_id = (cfg.get("user_id") or "").strip()
    if drive_id:
        return f"{_GRAPH_BASE}/drives/{drive_id}"
    if user_id:
        return f"{_GRAPH_BASE}/users/{user_id}/drive"
    raise ValueError("Cần cấu hình drive_id hoặc user_id trong secrets.toml [onedrive]")


def _lay_token() -> str:
    """Lấy access token, cache vào kv_store 'onedrive_token_cache' (TTL token - 60s buffer)."""
    cache = db.doc_kv("onedrive_token_cache") or {}
    expires_at_str = cache.get("expires_at", "")
    if cache.get("access_token") and expires_at_str:
        try:
            if datetime.fromisoformat(expires_at_str) > datetime.now() + timedelta(seconds=60):
                return cache["access_token"]
        except Exception:
            pass

    cfg = _lay_cfg()
    resp = requests.post(
        _TOKEN_URL_TPL.format(tenant_id=cfg["tenant_id"]),
        data={
            "grant_type": "client_credentials",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))
    db.ghi_kv(
        "onedrive_token_cache",
        {
            "access_token": token,
            "expires_at": (datetime.now() + timedelta(seconds=expires_in - 60)).isoformat(),
        },
        username="system",
    )
    return token


def _sanitize(name: str) -> str:
    """Loại bỏ ký tự không hợp lệ trong tên file OneDrive."""
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def _upload_nho(token: str, drive_prefix: str, remote_path: str, file_bytes: bytes) -> str:
    """Upload file ≤4MB. Trả về item_id."""
    url = f"{drive_prefix}/root:/{remote_path}:/content"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
    }
    resp = requests.put(url, headers=headers, data=file_bytes, timeout=60,
                        params={"@microsoft.graph.conflictBehavior": "replace"})
    resp.raise_for_status()
    return resp.json()["id"]


def _upload_lon(token: str, drive_prefix: str, remote_path: str, file_bytes: bytes) -> str:
    """Upload file >4MB qua upload session (chunked). Trả về item_id."""
    # 1. Tạo upload session
    url = f"{drive_prefix}/root:/{remote_path}:/createUploadSession"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"item": {"@microsoft.graph.conflictBehavior": "replace"}}
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    upload_url = resp.json()["uploadUrl"]

    # 2. Upload từng chunk
    total = len(file_bytes)
    start = 0
    item_id = None
    while start < total:
        end = min(start + _CHUNK_SIZE - 1, total - 1)
        chunk = file_bytes[start:end + 1]
        chunk_headers = {
            "Content-Range": f"bytes {start}-{end}/{total}",
            "Content-Length": str(len(chunk)),
        }
        r = requests.put(upload_url, headers=chunk_headers, data=chunk, timeout=120)
        if r.status_code in (200, 201):
            item_id = r.json().get("id")
        elif r.status_code == 202:
            pass  # tiếp tục chunk tiếp theo
        else:
            r.raise_for_status()
        start = end + 1

    if not item_id:
        raise RuntimeError("Upload session hoàn tất nhưng không nhận được item_id")
    return item_id


def _tao_share_link(token: str, drive_prefix: str, item_id: str) -> str:
    """Tạo share link dạng view (read-only, scope organization). Trả về URL."""
    url = f"{drive_prefix}/items/{item_id}/createLink"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"type": "view", "scope": "organization"}
    resp = requests.post(url, headers=headers, json=body, timeout=15)
    resp.raise_for_status()
    link = resp.json().get("link", {}).get("webUrl", "")
    return link


def kiem_tra_ket_noi() -> dict:
    """Kiểm tra kết nối OneDrive. Trả về dict với keys: ok, loi, drive_name, drive_url."""
    if not _kiem_tra_config():
        return {"ok": False, "loi": "Chưa cấu hình credentials trong secrets.toml [onedrive]"}
    try:
        cfg = _lay_cfg()
        token = _lay_token()
        drive_prefix = _drive_prefix(cfg)
        resp = requests.get(
            f"{drive_prefix}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "ok": True,
            "drive_name": data.get("name", ""),
            "drive_url": data.get("webUrl", ""),
            "owner": (data.get("owner", {}).get("user", {}).get("displayName", "")
                      or data.get("owner", {}).get("application", {}).get("displayName", "")),
            "quota_used_gb": round(data.get("quota", {}).get("used", 0) / 1e9, 2),
            "quota_total_gb": round(data.get("quota", {}).get("total", 1) / 1e9, 2),
        }
    except Exception as e:
        logger.error("kiem_tra_ket_noi OneDrive: %s", e)
        return {"ok": False, "loi": str(e)}


def upload_cong_van(
    file_bytes: bytes,
    file_name: str,
    so_hieu: str,
    ngay_ban_hanh: date,
) -> KetQuaOneDrive:
    """Upload file công văn lên OneDrive.

    Folder: VBSP-SCM/CongVan/{year}/{month}/
    Tên file: {so_hieu_sanitized}_{file_name}

    Trả về KetQuaOneDrive(False, loi=...) nếu chưa cấu hình hoặc gặp lỗi.
    """
    if not _kiem_tra_config():
        return KetQuaOneDrive(False, loi="OneDrive chưa được cấu hình (thiếu secrets.toml [onedrive])")

    try:
        cfg = _lay_cfg()
        token = _lay_token()
        drive_prefix = _drive_prefix(cfg)

        year = ngay_ban_hanh.year
        month = f"{ngay_ban_hanh.month:02d}"
        safe_so_hieu = _sanitize(so_hieu)
        safe_file_name = _sanitize(file_name)
        remote_name = f"{safe_so_hieu}_{safe_file_name}"
        folder_path = f"VBSP-SCM/CongVan/{year}/{month}"
        remote_path = f"{folder_path}/{remote_name}"

        size = len(file_bytes)
        if size <= _CHUNK_SIZE:
            item_id = _upload_nho(token, drive_prefix, remote_path, file_bytes)
        else:
            item_id = _upload_lon(token, drive_prefix, remote_path, file_bytes)

        share_url = _tao_share_link(token, drive_prefix, item_id)
        logger.info("OneDrive upload OK: %s → %s", remote_path, share_url)
        return KetQuaOneDrive(True, url=share_url)

    except Exception as e:
        logger.error("upload_cong_van thất bại: %s", e, exc_info=True)
        return KetQuaOneDrive(False, loi=str(e))
