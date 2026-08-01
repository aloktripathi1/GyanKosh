"""Security-audit follow-up: local_storage.py previously did `base_path /
storage_path` with no containment check, so a storage_path containing `..`
segments could escape the storage root entirely. These tests attempt real
traversal (not a mock, not "the code looks right") and assert it's rejected."""

import io
import time

import pytest

from app.storage.local_storage import LocalStorageBackend, PathTraversalError, verify_signature


def test_read_rejects_simple_parent_traversal(tmp_path):
    backend = LocalStorageBackend(str(tmp_path))
    secret = tmp_path.parent / "outside_storage_root.txt"
    secret.write_text("must never be readable via the storage interface")

    with pytest.raises(PathTraversalError):
        backend.read("../outside_storage_root.txt")


def test_read_rejects_traversal_disguised_inside_a_nested_path(tmp_path):
    """The classic bypass attempt: start inside a legitimate-looking
    subdirectory, then walk back out further than the base."""
    backend = LocalStorageBackend(str(tmp_path))
    secret = tmp_path.parent.parent / "etc_passwd_stand_in.txt"
    secret.write_text("root secret")

    with pytest.raises(PathTraversalError):
        backend.read("documents/../../../etc_passwd_stand_in.txt")


def test_save_also_rejects_traversal(tmp_path):
    """Not just reads — a malicious storage key must not be able to write
    outside the storage root either."""
    backend = LocalStorageBackend(str(tmp_path))
    with pytest.raises(PathTraversalError):
        backend.save("../../escape.txt", io.BytesIO(b"malicious"))
    assert not (tmp_path.parent / "escape.txt").exists()


def test_delete_rejects_traversal(tmp_path):
    backend = LocalStorageBackend(str(tmp_path))
    victim = tmp_path.parent / "do_not_delete_me.txt"
    victim.write_text("still here")

    with pytest.raises(PathTraversalError):
        backend.delete("../do_not_delete_me.txt")
    assert victim.exists()


def test_legitimate_nested_access_still_works(tmp_path):
    """The fix must not be so strict it breaks real, non-malicious usage."""
    backend = LocalStorageBackend(str(tmp_path))
    backend.save("documents/abc/report.txt", io.BytesIO(b"real content"))
    assert backend.read("documents/abc/report.txt") == b"real content"


# --- signed URL / expiry ---


def test_url_generates_a_verifiable_signature(tmp_path):
    backend = LocalStorageBackend(str(tmp_path))
    url = backend.url("tkp/job1/lesson_plans.pdf", expires_in=3600)

    assert url.startswith("/files/tkp/job1/lesson_plans.pdf?")
    query = dict(pair.split("=") for pair in url.split("?", 1)[1].split("&"))
    assert verify_signature("tkp/job1/lesson_plans.pdf", int(query["expires"]), query["sig"])


def test_signature_rejects_expired_link():
    already_expired = int(time.time()) - 10
    # Even a correctly-computed signature for an already-past expiry must fail.
    from app.storage.local_storage import _sign

    sig = _sign("tkp/job1/lesson_plans.pdf", already_expired)
    assert not verify_signature("tkp/job1/lesson_plans.pdf", already_expired, sig)


def test_signature_rejects_tampered_path():
    """A signature is scoped to one exact path — a valid signature for file A
    must not authorize access to file B."""
    from app.storage.local_storage import _sign

    expires_at = int(time.time()) + 3600
    sig = _sign("tkp/job1/lesson_plans.pdf", expires_at)
    assert not verify_signature("tkp/job1/teacher_guide.pdf", expires_at, sig)


def test_signature_rejects_tampered_expiry():
    """Bumping the expiry forward without re-signing must not extend access."""
    from app.storage.local_storage import _sign

    real_expiry = int(time.time()) + 60
    sig = _sign("tkp/job1/lesson_plans.pdf", real_expiry)
    extended_expiry = real_expiry + 1_000_000
    assert not verify_signature("tkp/job1/lesson_plans.pdf", extended_expiry, sig)
