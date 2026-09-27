"""Production cloud backends for immutable model artifacts and signing."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Callable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from p37_neuro.deployment.release import (
    ReleaseManifest,
    SignedRelease,
    public_key_fingerprint,
)
from p37_neuro.deployment.store import sha256_file


@dataclass(frozen=True, slots=True)
class RemoteArtifact:
    """One immutable model artifact stored outside the local filesystem."""

    sha256: str
    uri: str
    size_bytes: int


class S3ArtifactStore:
    """Content-addressed artifact publisher for S3 and S3-compatible stores."""

    def __init__(
        self,
        bucket: str,
        *,
        prefix: str = "p37/artifacts",
        client: Any | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        if not bucket.strip():
            raise ValueError("bucket cannot be empty")
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        if client is None:
            try:
                boto3: Any = import_module("boto3")
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "S3 support is optional; install p37-neuro[cloud]"
                ) from exc
            client = boto3.client("s3", endpoint_url=endpoint_url)
        self.client = client

    def key_for(self, digest: str) -> str:
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("digest must be a lowercase SHA-256 hex string")
        suffix = f"{digest[:2]}/{digest[2:4]}/{digest}"
        return f"{self.prefix}/{suffix}" if self.prefix else suffix

    def put(self, path: str | Path) -> RemoteArtifact:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        digest = sha256_file(source)
        key = self.key_for(digest)
        size = source.stat().st_size

        try:
            existing = self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            response = getattr(exc, "response", {})
            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = response.get("Error", {}).get("Code")
            if status not in {404, None} and code not in {"404", "NoSuchKey", "NotFound"}:
                raise
            self.client.upload_file(
                str(source),
                self.bucket,
                key,
                ExtraArgs={
                    "Metadata": {
                        "sha256": digest,
                        "p37-immutable": "true",
                    }
                },
            )
        else:
            metadata = existing.get("Metadata", {})
            stored_digest = metadata.get("sha256")
            stored_size = int(existing.get("ContentLength", -1))
            if stored_digest != digest or stored_size != size:
                raise RuntimeError("remote artifact key exists with different content metadata")

        return RemoteArtifact(
            sha256=digest,
            uri=f"s3://{self.bucket}/{key}",
            size_bytes=size,
        )

    def download(self, sha256: str, destination: str | Path) -> Path:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".part")
        self.client.download_file(self.bucket, self.key_for(sha256), str(temporary))
        if sha256_file(temporary) != sha256:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("downloaded artifact failed SHA-256 verification")
        temporary.replace(target)
        return target


def _response_crc_value(value: Any) -> int:
    raw = getattr(value, "value", value)
    return int(raw)


class GcpKmsReleaseSigner:
    """Google Cloud KMS signer for EC_SIGN_ED25519 release keys.

    Private key material never enters the process. The class verifies the KMS
    resource name and CRC32C integrity fields before returning a signed release.
    """

    def __init__(
        self,
        key_version_name: str,
        *,
        client: Any | None = None,
        crc32c: Callable[[bytes], int] | None = None,
    ) -> None:
        if not key_version_name.strip():
            raise ValueError("key_version_name cannot be empty")
        self.key_version_name = key_version_name

        if client is None:
            try:
                kms: Any = import_module("google.cloud.kms")
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "Google Cloud KMS support is optional; install p37-neuro[cloud]"
                ) from exc
            client = kms.KeyManagementServiceClient()
        self.client = client

        if crc32c is None:
            try:
                google_crc32c: Any = import_module("google_crc32c")
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "CRC32C support is optional; install p37-neuro[cloud]"
                ) from exc
            crc32c = lambda data: int(google_crc32c.value(data))
        self.crc32c = crc32c
        self._public_key: Ed25519PublicKey | None = None

    @property
    def public_key(self) -> Ed25519PublicKey:
        if self._public_key is not None:
            return self._public_key

        response = self.client.get_public_key(request={"name": self.key_version_name})
        if response.name != self.key_version_name:
            raise RuntimeError("KMS public-key response resource mismatch")

        pem = str(response.pem)
        if hasattr(response, "pem_crc32c"):
            expected = _response_crc_value(response.pem_crc32c)
            if expected != self.crc32c(pem.encode("utf-8")):
                raise RuntimeError("KMS public-key response failed CRC32C verification")

        key = serialization.load_pem_public_key(pem.encode("utf-8"))
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("KMS release key must use EC_SIGN_ED25519")
        self._public_key = key
        return key

    def sign(self, manifest: ReleaseManifest) -> SignedRelease:
        payload = manifest.canonical_bytes()
        payload_crc32c = self.crc32c(payload)
        response = self.client.asymmetric_sign(
            request={
                "name": self.key_version_name,
                "data": payload,
                "data_crc32c": payload_crc32c,
            }
        )

        if response.name != self.key_version_name:
            raise RuntimeError("KMS signing response resource mismatch")
        if not bool(response.verified_data_crc32c):
            raise RuntimeError("KMS did not verify request CRC32C")
        if _response_crc_value(response.signature_crc32c) != self.crc32c(response.signature):
            raise RuntimeError("KMS signature response failed CRC32C verification")

        public_key = self.public_key
        public_key.verify(response.signature, payload)
        return SignedRelease(
            manifest=manifest,
            signature_b64=base64.b64encode(response.signature).decode("ascii"),
            signer_fingerprint=public_key_fingerprint(public_key),
        )
