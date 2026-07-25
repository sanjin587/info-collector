"""
飞书 API 客户端
处理鉴权、Token 管理、API 请求封装
"""
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests

from utils.logger import logger


class FeishuClient:
    """飞书 API 客户端"""

    _BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token = None
        self._token_expires_at: Optional[datetime] = None

    # ── Token 管理 ──────────────────────────────────────────

    def _get_tenant_access_token(self) -> str:
        """获取 tenant_access_token（自动缓存和刷新）"""
        if self._token and self._token_expires_at and datetime.now() < self._token_expires_at:
            return self._token

        url = f"{self._BASE_URL}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                raise RuntimeError(f"获取 tenant_access_token 失败: {data.get('msg', 'unknown error')}")

            self._token = data["tenant_access_token"]
            # Token 有效期通常 2 小时，提前 5 分钟刷新
            expire_seconds = data.get("expire", 7200) - 300
            self._token_expires_at = datetime.now() + timedelta(seconds=max(expire_seconds, 60))
            logger.info("成功获取飞书 tenant_access_token")
            return self._token

        except requests.RequestException as e:
            logger.error(f"飞书认证请求失败: {e}")
            raise

    # ── 通用请求 ────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        retry: bool = True,
    ) -> Dict[str, Any]:
        """发送带 Token 的 API 请求，自动处理 Token 刷新"""
        token = self._get_tenant_access_token()
        url = f"{self._BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()

            if result.get("code") != 0:
                # Token 过期，刷新后重试一次
                if result.get("code") == 99991663 and retry:
                    logger.warning("Token 已过期，正在刷新...")
                    self._token = None
                    self._token_expires_at = None
                    return self._request(method, path, params, json_data, retry=False)

                logger.error(f"飞书 API 返回错误: code={result.get('code')}, msg={result.get('msg')}")
                raise RuntimeError(f"飞书 API 返回错误: code={result.get('code')}, msg={result.get('msg')}")

            return result

        except requests.RequestException as e:
            logger.error(f"飞书 API 请求失败 [{method} {path}]: {e}")
            raise

    def get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET 请求"""
        return self._request("GET", path, params=params)

    def post(self, path: str, json_data: Optional[Dict] = None) -> Dict[str, Any]:
        """POST 请求"""
        return self._request("POST", path, json_data=json_data)

    def put(self, path: str, json_data: Optional[Dict] = None) -> Dict[str, Any]:
        """PUT 请求"""
        return self._request("PUT", path, json_data=json_data)

    def delete(self, path: str, json_data: Optional[Dict] = None) -> Dict[str, Any]:
        """DELETE 请求"""
        return self._request("DELETE", path, json_data=json_data)
