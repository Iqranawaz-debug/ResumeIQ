# Windows asyncio test isolation fix

## Verified baseline, before implementation

Windows/Python 3.14: full unittest discovery ran 135 tests: 121 passed,
14 failures, zero errors/skips/expected failures. Security-only discovery
ran 17 tests: 3 passed and the same 14 failed. All fourteen tracebacks have
the same setup failure (not a failure in their security assertions):

```text
unittest.async_case.IsolatedAsyncioTestCase._callSetUp
  self._asyncioRunner.get_loop()
asyncio.runners.Runner._lazy_init -> events.new_event_loop
asyncio.windows_events.ProactorEventLoop.__init__
asyncio.proactor_events._make_self_pipe -> socket.socketpair()
socket._fallback_socketpair -> csock.connect((addr, port))
unittest.mock -> AssertionError: External effects forbidden
```

`test_security.setUpModule` patches process-global `socket.socket.connect`
before any isolated async runner is initialized. The installed Python source
confirms `_callSetUp` initializes the loop BEFORE calling synchronous `setUp`,
then calls `asyncSetUp`. The tests intend to block external network calls and
account persistence, not framework initialization. Account reads are already
isolated before importing auth; `_save_users` has a separate write guard.

Affected methods in `test_security`:

- `SessionTests.test_login_normalizes_existing_account_and_logout_revokes`
- `SessionTests.test_login_throttle_and_recovery`
- `SessionTests.test_session_expires_at_boundary`
- `SessionTests.test_unknown_and_wrong_password_have_same_message`
- `UploadTests.test_body_limit_declared_and_chunked_before_app`
- `UploadTests.test_extension_empty_and_byte_limits`
- `UploadTests.test_invalid_signatures_and_text_encoding`
- `UploadTests.test_known_oversize_not_read`
- `UploadTests.test_pdf_pages_and_encryption`
- `UploadTests.test_real_http_workflow_and_safe_validation_errors`
- `UploadTests.test_text_and_docx_structure_limits`
- `UploadTests.test_unknown_size_read_stops_at_limit_plus_one`
- `UploadTests.test_upload_retains_no_raw_document_and_analysis_requires_id`
- `UploadTests.test_zip_entry_and_expanded_limits`

Selected approach: install a scoped guard in test setup after framework loop
initialization, before application setup/body/teardown. Keep account isolation
and all original assertions; block socket/DNS/HTTP and asyncio outbound paths,
with explicit offline negative controls and guaranteed cleanup. No destination
allowlist, private-loop override or scoring/application change is needed.

## Implemented solution and security preservation

The shared `OfflineAsyncTestCase` uses public unittest lifecycle hooks. Its
`setUp` installs `network_guard` after the framework creates the loop, before
any application fixture code. Its `run` owns an `ExitStack`, keeping the guard
active through setup, the test body, teardown, cleanups AND runner shutdown
(pending-task cancellation and async-generator finalization). The stack restores
every patch even if setup fails. The synchronous privacy tests use the same
guard via `enterContext`. Application imports in the security module remain
guarded separately, with account reads isolated before auth import.

The guard rejects `socket.connect`, `connect_ex`, `create_connection`, `sendto`,
DNS resolution methods and HTTP connection establishment. When HTTPX is
installed it also rejects synchronous/asynchronous client `send`, before the
transport can run. HTTPX is already a provider SDK dependency in the normal
environment; no dependency was added. Active-loop connection and datagram
methods are guarded explicitly because Windows IOCP can bypass Python's
`socket.connect`. Existing loop wakeup writes continue to work. There is no
localhost/IP/port allowlist, no exception-message matching and no sleep-based
ordering. All application networking remains guarded while it executes.

The account-write guard remains module-scoped. Upload fixtures now isolate all
mutable auth/resume/history/version dictionaries per test, including the
previously un-restored upload-version state. All original 17 security tests,
test bodies and assertions are retained; none was weakened, deleted, skipped,
or converted to an expected failure.

This timing change avoids a custom socketpair implementation or a blanket
loopback exception. It is portable and limited to tests. Normal framework
initialization runs before application setup; the restrictions are not removed
while application cleanup or task finalizers run.

## Nine new harness regressions

`test_network_guard.py` verifies:

1. TCP connect/connect_ex, DNS, UDP and localhost operations are rejected.
2. Guard restoration when its context exits with an exception.
3. Repeated scopes restore original socket functions without leaking patches.
4. A deliberately disabled guard makes the negative-control assertion fail.
5. Async setup/body/teardown/cleanup and pending-task cancellation all execute;
   the cancellation finalizer remains guarded, the loop closes, and no tasks
   remain on it.
6. Guard restoration even when a synthetic test's setup raises.
7. Async loop/IOCP connection and datagram paths are rejected.
8. HTTP client requests are blocked before transport, and the provider adapter
   uses the explicitly mocked SDK boundary with a synthetic API key.
9. Thread-safe framework wakeups and ordinary task execution still work.

Negative controls use mocked lower layers returning harmless values, reserved
documentation addresses or `.invalid` names. No actual external connection is
attempted, even if the guard is broken. Each control asserts the lower layer
was not called. The disabled-guard mutation proves the test is meaningful:
without interception, the assertion expecting `NetworkForbidden` fails.
The nested lifecycle probes intentionally test failure/cancellation behavior;
their expected failures are asserted inside passing harness tests, not hidden
security-suite failures.

## Files changed in this phase

- `backend/tests/test_security.py`: scoped guard bases, guarded imports,
  per-test mutable-state restoration; original assertions unchanged.
- `backend/tests/network_guard.py` (new): scoped networking guard and small
  unittest base classes.
- `backend/tests/test_network_guard.py` (new): nine offline regression tests.
- `docs/windows-asyncio-test-fix.md` (new): this investigation and report.

SHA-256 snapshots of **49** production Python files, frontend source files,
main API, Vite configuration, manifests, constraints and frontend lockfile
matched before/after. No production, scoring, authentication, provider privacy,
API, parsing or frontend behavior was changed. Prior Phase 1–4 modifications
and untracked files were preserved. No dependencies or environment files changed.

## Before and after

| Verification | Reproduced before | After |
|---|---|---|
| Security module | 3 passed, 14 failed (17 total) | **17 passed** |
| Full backend unittest suite | 121 passed, 14 failed (135 total) | **144 passed** |
| New guard regressions | Not present | **9 passed** |
| Security + guard under existing pytest | Not run | **26 passed** |
| Frontend Node tests | Previous phase: 15 passed | **15 passed** |
| Frontend lint | Previous phase: passed | **Passed** |
| Frontend production build | Previous phase: passed | **Passed**, no build warnings |
| Git whitespace check | Existing work preserved | **Passed** (LF/CRLF notices only) |

All final runs have zero failures, errors, skips and expected failures.
All 14 formerly blocked bodies now run, including the in-process ASGI
signup/upload/analyze/history/logout workflow, validation privacy, session
expiry/throttling, upload byte/format/decompression limits and resume-ID checks.
Existing Phase 4 tests also cover cross-user isolation, response types, provider
data minimization and scoring preservation. No browser end-to-end run is claimed.

### Repeated runs and order

| Run | Result |
|---|---|
| Security alone, repeat 1 | 17/17 passed |
| Security alone, repeat 2 | 17/17 passed |
| Security alone, repeat 3 | 17/17 passed |
| Full suite, repeat 1 | 144/144 passed |
| Full suite, repeat 2 | 144/144 passed |
| Full suite, security first | 144/144 passed |
| Full suite, security last | 144/144 passed |

Repeats and reordered runs were performed in the same process to expose leaked
patches/state; original socket function identity was asserted between runs.
No intermittent test failures occurred. Windows asyncio debug output sometimes
reported slow test tasks during password hashing/DOCX processing; these were
timing diagnostics, not pending-task or unclosed-client failures.

Commands from `backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_security.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_network_guard.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Repeated/order checks use the standard unittest loader and runner, rebuilding
the suite for each run. Targeted pytest used the already available pytest
installation on the venv import path, as in previous phases. Frontend checks
used `node --test tests/*.test.js`, `npm run lint`, and `npm run build`.

## Runner and platform limitations

The restricted execution runner introduced a separate limitation after the
mock-order bug was fixed: Windows socketpair initialization stalled at
`socket._fallback_socketpair -> accept()` before test setup. A timed diagnostic
terminated that run and captured its stack. Approved runs outside that runner
restriction completed successfully with the test-level network guard active.
No production or test assertion workaround was added for the runner restriction.
The restricted runner also exposed a lightweight environment without HTTPX;
the normal verification environment exercised the HTTPX guard paths.

Executed on Windows/Python 3.14. Linux and macOS were reviewed conceptually but
not executed. The solution uses public unittest/context-manager and asyncio
APIs, without platform-specific ports, policies or private event-loop hooks.
The guard is an offline testing safeguard, not an OS security sandbox against
arbitrary native code, subprocesses or deliberately bypassed monkey patches.
The suite uses in-process ASGI rather than a live listening HTTP server; no
external provider service was contacted.

## Git state

Branch remains `feature/resumeiq-redesign`. This phase changes only the four
test/documentation files listed above. The test directory and docs directory
already appeared as untracked in the supplied worktree; the new helper,
regression module and report also remain untracked. Existing tracked changes
from earlier phases remain in place. Nothing was staged, committed, pushed,
merged, reset, stashed or deleted. No remote operations were performed.
