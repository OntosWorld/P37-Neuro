from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from p37_neuro.deployment.cloud import GcpKmsReleaseSigner, S3ArtifactStore
from p37_neuro.deployment.release import ReleaseManifest, verify_release


class MissingObject(Exception):
    def __init__(self) -> None:
        self.response = {
            "ResponseMetadata": {"HTTPStatusCode": 404},
            "Error": {"Code": "NoSuchKey"},
        }


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, dict[str, str]]] = {}

    def head_object(self, *, Bucket: str, Key: str):
        try:
            body, metadata = self.objects[(Bucket, Key)]
        except KeyError as exc:
            raise MissingObject from exc
        return {"ContentLength": len(body), "Metadata": metadata}

    def upload_file(
        self,
        filename: str,
        bucket: str,
        key: str,
        *,
        ExtraArgs: dict[str, dict[str, str]],
    ) -> None:
        self.objects[(bucket, key)] = (
            Path(filename).read_bytes(),
            dict(ExtraArgs["Metadata"]),
        )

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        body, _ = self.objects[(bucket, key)]
        Path(filename).write_bytes(body)


@dataclass
class BoxedInt:
    value: int


@dataclass
class FakePublicKeyResponse:
    name: str
    pem: str
    pem_crc32c: BoxedInt


@dataclass
class FakeSignatureResponse:
    name: str
    signature: bytes
    signature_crc32c: BoxedInt
    verified_data_crc32c: bool = True


class FakeKms:
    def __init__(self, name: str, private_key: Ed25519PrivateKey, crc32c) -> None:
        self.name = name
        self.private_key = private_key
        self.crc32c = crc32c

    def get_public_key(self, *, request):
        assert request["name"] == self.name
        pem = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        return FakePublicKeyResponse(
            name=self.name,
            pem=pem,
            pem_crc32c=BoxedInt(self.crc32c(pem.encode("utf-8"))),
        )

    def asymmetric_sign(self, *, request):
        assert request["name"] == self.name
        payload = request["data"]
        assert request["data_crc32c"] == self.crc32c(payload)
        signature = self.private_key.sign(payload)
        return FakeSignatureResponse(
            name=self.name,
            signature=signature,
            signature_crc32c=BoxedInt(self.crc32c(signature)),
        )


def _checksum(data: bytes) -> int:
    return sum(data) % (2**32)


def test_s3_store_is_content_addressed_and_verified(tmp_path: Path) -> None:
    model = tmp_path / "model.onnx"
    model.write_bytes(b"p37-model")
    client = FakeS3()
    store = S3ArtifactStore("models", prefix="prod", client=client)

    remote = store.put(model)
    assert remote.uri.startswith("s3://models/prod/")
    assert remote.size_bytes == len(b"p37-model")

    output = store.download(remote.sha256, tmp_path / "download.onnx")
    assert output.read_bytes() == b"p37-model"


def test_kms_signer_preserves_release_verification() -> None:
    key_name = (
        "projects/p/locations/global/keyRings/releases/cryptoKeys/p37/"
        "cryptoKeyVersions/1"
    )
    private_key = Ed25519PrivateKey.generate()
    signer = GcpKmsReleaseSigner(
        key_name,
        client=FakeKms(key_name, private_key, _checksum),
        crc32c=_checksum,
    )
    manifest = ReleaseManifest(
        schema_version=1,
        artifact_id="candidate-42",
        artifact_sha256="b" * 64,
        config_id="cfg",
        dataset_id="dataset",
        stage="E6",
        metrics={"success_rate": 0.8},
    )

    release = signer.sign(manifest)
    verify_release(release, signer.public_key)
