"""JWT bearer authentication for the gateway.

When configured, the gateway validates ``Authorization: Bearer <token>`` and
**overrides** the ``X-User-ID`` header with the token's ``sub`` claim before
proxying — user identity stops being client-asserted.

Two verification modes:
- ``JWT_SECRET`` — HS256 shared secret, for single-operator deployments
- ``JWT_JWKS_URL`` — RS256/ES256 via an OIDC provider's JWKS endpoint
  (key fetch is cached by PyJWKClient; the one-time fetch is blocking,
  which is acceptable at this frequency)
"""

import jwt


class AuthError(Exception):
    pass


class JwtAuthenticator:
    def __init__(
        self,
        secret: str = "",
        jwks_url: str = "",
        issuer: str = "",
        audience: str = "",
    ):
        if not secret and not jwks_url:
            raise ValueError("JwtAuthenticator needs a secret or a JWKS URL")
        self._secret = secret
        self._issuer = issuer or None
        self._audience = audience or None
        self._jwks_client = jwt.PyJWKClient(jwks_url) if jwks_url else None

    def authenticate(self, token: str) -> str:
        """Validate the token and return the subject (user id)."""
        try:
            if self._jwks_client is not None:
                key = self._jwks_client.get_signing_key_from_jwt(token).key
                algorithms = ["RS256", "ES256"]
            else:
                key = self._secret
                algorithms = ["HS256"]
            claims = jwt.decode(
                token,
                key,
                algorithms=algorithms,
                issuer=self._issuer,
                audience=self._audience,
                options={
                    "require": ["sub", "exp"],
                    "verify_aud": self._audience is not None,
                },
            )
        except jwt.PyJWTError as exc:
            raise AuthError(str(exc)) from exc
        return str(claims["sub"])
