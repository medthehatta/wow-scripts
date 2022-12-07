"""
This module contains helper methods for authenticating with various
aspects of a Domino deployment.
"""
import time
from urllib.parse import urlparse, urljoin, parse_qs

import bs4
import requests


class AccessToken:
    """Base class for an access token."""

    def get(self):
        """Get the token."""
        raise NotImplementedError

    @property
    def auth_headers(self):
        """Get a dict of authentication headers."""
        raise NotImplementedError


class ConstantHeader(AccessToken):
    """A constant header, like a more general ApiKey."""

    def __init__(self, header, value):
        self.header = header
        self.value = value

    def get(self):
        """Get the header value."""
        return self.value

    @property
    def auth_headers(self):
        """Get a dict of authentication headers."""
        return {self.header: self.value}


class TSMToken(AccessToken):

    def __init__(
        self,
        token,
        leeway=60,
    ):
        """Initialize the instance."""
        self.token = token
        # Token initialization is lazy: no guarantees you have a valid token
        # until you try calling `get()`
        self.tokens = None
        self.refresh_expire_time = None
        self.expire_time = None
        self.leeway = leeway

    def _request_tokens_with_grant(self, grant_data):
        """Get the access token given the `grant_data`."""
        response = requests.post(
            url="https://auth.tradeskillmaster.com/oauth2/token",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Apache-HttpClient",
            },
            json=grant_data,
        )
        response.raise_for_status()
        self.tokens = response.json()
        # Refresh the token `leeway` seconds earlier than we "really need to"
        # to be careful.
        self.expire_time = (
            time.time() + int(self.tokens["expires_in"]) - self.leeway
        )
        self.refresh_expire_time = (
            time.time() + int(self.tokens["expires_in"]) + 10 - self.leeway
        )
        return self.tokens

    def _login(self):
        """Get the access token with the login flow."""
        return self._request_tokens_with_grant(
            {
                "client_id": "c260f00d-1071-409a-992f-dda2e5498536",
                "grant_type": "api_token",
                "scope": "app:realm-api app:pricing-api",
                "token": self.token,
            },
        )

    def _refresh(self):
        """Refresh the access token with a refresh flow."""
        refresh_token = self.tokens["refresh_token"]
        return self._request_tokens_with_grant(
            {
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

    def get(self):
        """Retrieve the token, refreshing if necessary."""
        current_time = time.time()
        if self.tokens is None:
            self.tokens = self._login()
        elif current_time > self.refresh_expire_time:
            self.tokens = self._login()
        elif current_time > self.expire_time:
            self.tokens = self._refresh()
        return self.tokens["access_token"]

    @property
    def auth_headers(self):
        return {"Authorization": f"Bearer {self.get()}"}

    
class BlizzardToken(AccessToken):

    def __init__(
        self,
        client_id,
        client_secret,
        leeway=60,
    ):
        """Initialize the instance."""
        self.client_id = client_id
        self.client_secret = client_secret
        # Token initialization is lazy: no guarantees you have a valid token
        # until you try calling `get()`
        self.tokens = None
        self.expire_time = None
        self.leeway = leeway

    def _login(self):
        """Get the access token with the login flow."""
        response = requests.post(
            url="https://oauth.battle.net/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "Apache-HttpClient",
            },
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
        )
        response.raise_for_status()
        self.tokens = response.json()
        # Refresh the token `leeway` seconds earlier than we "really need to"
        # to be careful.
        self.expire_time = (
            time.time() + int(self.tokens["expires_in"]) - self.leeway
        )
        self.refresh_expire_time = (
            time.time() + int(self.tokens["expires_in"]) + 10 - self.leeway
        )
        return self.tokens

    def get(self):
        """Retrieve the token, refreshing if necessary."""
        current_time = time.time()
        if self.tokens is None:
            self.tokens = self._login()
        elif current_time > self.expire_time:
            self.tokens = self._refresh()
        return self.tokens["access_token"]

    @property
    def auth_headers(self):
        return {"Authorization": f"Bearer {self.get()}"}
