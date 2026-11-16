# Complete the customer dashboard journey

The dashboard is a local, dependency-free pre-alpha interface. It binds to the loopback interface and does not publish content or call external services.

## Start

From a trusted checkout:

```bash
python3 -m pip install -e .
menaxvi dashboard --root .
```

Open `http://127.0.0.1:8765`. Dashboard data is stored at `~/.menaxvi/dashboard.json` with owner-only file permissions. Use `--data PATH` to select a separate test data file.

## Journey

1. Create an account with an email address and a password of at least 10 characters.
2. Complete every business-context field and save the workspace.
3. Select the approved reviewed-campaign-message module and create a plan.
4. Expand **Review plan** and inspect inputs, task steps, gates, policies, resource versions, and the plan digest.
5. Choose **Approve gate & execute** to record the human decision and create the artifact.
6. Expand **Evidence log** to inspect timestamps, inputs, decisions, outputs, and SHA-256 digests.
7. On a new plan, choose **Trigger controlled failure**. Confirm that no artifact is created and the prior state remains available.
8. Choose **Create retry**, then execute the bounded second attempt. Alternatively, create a manual rollback plan from a recorded attempt.
9. Sign out, sign in again, and confirm that the workspace, execution history, artifact, rollback plan, and evidence are restored.

## Safety boundaries

- The server is intended for one local operator and is not a production identity service.
- Passwords are stored as PBKDF2-SHA256 hashes. Session tokens are held in memory and sent in `HttpOnly; SameSite=Strict` cookies.
- A restart signs all users out but preserves durable customer data. Sign in again to restore the journey.
- Controlled failure, retry, and rollback append evidence. Rollback creates compensating instructions; it performs no external action.
- Customer-facing errors do not include stack traces, secrets, or internal exception details.
