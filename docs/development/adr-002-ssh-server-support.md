# ADR-002: SSH server support

- Status: Proposed
- Date: 2026-09-05
- Scope: Architecture proposal; implementation pending

## Context

PICLE needs a design for optional remote interactive sessions over SSH on
Windows and Linux. The transport must bridge asynchronous SSH streams and
PICLE's synchronous command execution while isolating each session's state,
output and history. Host-account authentication and command authorization
must remain separate from the OS identity under which commands execute.

## Decision

Use AsyncSSH as an optional embedded transport with these authentication methods:

- Linux host usernames and passwords through a dedicated PAM service.
- Windows local or domain usernames and passwords through `LogonUser`.
- SSH public keys as an additional method.

Authorize authenticated users against canonical PICLE command paths. Support user and group policies with `allow` and `deny` rules. `deny` always overrides `allow`; the default policy is `allow *` for backward compatibility and simple deployments.

Authentication does not change process identity. Embedded sessions run as the PICLE server account. Deployments which require commands to run as the authenticated host user should use system OpenSSH to launch a separate PICLE process.

## Rationale

AsyncSSH can serve an interactive PICLE session on Windows and Linux. It supports server-side shell sessions, public-key and password authentication, terminal metadata, and line editing. It also requires Python 3.10+, matching PICLE. See the [AsyncSSH documentation](https://asyncssh.readthedocs.io/en/stable/#line-editing) and [package metadata](https://pypi.org/project/asyncssh/).

The proposed host-password design has a critical identity problem: authenticating a host user does not make an in-process PICLE session run as that user. Commands still run as the account hosting the PICLE server.

This is unsafe with PICLE's current `shell` command, which executes arbitrary OS commands. If the server runs as root, `SYSTEM`, an administrator, or another privileged account, every accepted user may gain that account's privileges.

Host authentication is also platform-specific:

- Linux requires a dedicated PAM service and account-policy handling, not only a call to `pam_authenticate()`. See the [Linux-PAM interface](https://man7.org/linux/man-pages/man3/pam.3.html).
- Windows `LogonUser` validates credentials and returns a token. Impersonation or creating a process under that token is a separate operation with additional privilege and lifecycle requirements. See [`LogonUser`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-logonuserw).

PAM and `LogonUser` authentication are feasible, but must be isolated behind platform-specific providers and run away from the asyncio event loop. System OpenSSH remains the better mode when OS-user process identity is required.

## Feasibility

| Area | Rating | Main issue |
| --- | --- | --- |
| AsyncSSH transport | High | Mature server API and compatible Python version. |
| Basic remote PICLE session | Medium-high | Requires an adapter between async SSH streams and PICLE's synchronous loop. |
| Local terminal feature parity | Medium | `prompt_toolkit`, completion, inline help, interrupts, and terminal control need remote-specific handling. |
| Concurrent sessions | Medium | Output, history, model state, and blocking commands must be isolated. |
| Linux host authentication | Medium | Requires PAM service and account/session policy. |
| Windows host authentication | Medium | Requires `LogonUser`, token handling, and platform-specific process creation. |
| In-process host-user isolation | Low | Authentication does not change the server process identity. |
| Public Internet exposure | Low initially | Requires rate limits, auditing, timeouts, secure defaults, and security testing. |

## Current PICLE constraints

- `App.start()` and `cmdloop()` are synchronous and blocking.
- AsyncSSH readers are asynchronous; PICLE expects file-like `readline()` and `write()` methods.
- `prompt_toolkit` expects a local terminal.
- Rich uses a module-global console instead of `App.stdout`, which can mix or misroute output.
- All sessions default to the same `picle_history.txt` file.
- `cls` clears the server terminal instead of the SSH client.
- `shell` runs commands as the server process account.
- Application models may contain mutable state that is unsafe to share between sessions.

Each SSH channel therefore needs a new `App` and root-model instance, isolated output, and isolated or disabled history.

## Alternatives considered

| Option | Benefits | Problems | Decision |
| --- | --- | --- | --- |
| Embedded AsyncSSH with PAM or `LogonUser` | Reuses host accounts without requiring system SSH. | Platform-specific; sessions still run as the shared server account. | Selected embedded mode. |
| Embedded AsyncSSH with public keys | Portable and avoids reusable passwords. | Requires key provisioning; sessions still use the server account. | Supported alternative. |
| System OpenSSH launches PICLE | Real host identity, process isolation, mature authentication and auditing. | Requires administrator setup and platform-specific documentation. | Preferred host-identity mode. |
| Privileged broker launching per-user workers | Combines embedded SSH with OS-user isolation. | Complex privileged service which duplicates much of `sshd`. | Defer. |

OpenSSH can restrict users to PICLE through a forced command or subsystem. Forwarding must be disabled separately. See the [OpenSSH server configuration manual](https://man.openbsd.org/sshd_config) and [Windows OpenSSH configuration](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh-server-configuration).

## Proposed architecture

```text
Embedded mode

SSH client
  -> AsyncSSH listener
  -> platform authenticator (PAM, LogonUser, or public key)
  -> command-tree authorizer
  -> new PICLE session
  -> remote terminal adapter

Host-identity mode

SSH client
  -> system OpenSSH
  -> restricted PICLE launcher
  -> new PICLE process running as the host user
```

Keep SSH outside `App`. Provide a separate optional API such as:

```text
picle.ssh.serve(root_factory, config)
```

Main components:

- `SSHServerConfig`: listener, host keys, authentication methods, authorization policy, timeouts, limits, and audit settings.
- `Authenticator`: validates credentials and returns a normalized principal with username and host groups.
- `Authorizer`: evaluates the principal against canonical command paths.
- `SessionFactory`: creates a new root model and `App` for each channel.
- `RemoteTerminal`: handles input, output, newlines, interrupts, resize events, and disconnects.
- `ServerHandle`: provides explicit start, stop, and wait operations.

Prefer an asynchronous PICLE session driver which awaits complete lines and calls the existing parser and dispatcher. A bounded worker-thread bridge is acceptable for a prototype but adds cancellation, shutdown, and backpressure complexity.

Do not promise full `prompt_toolkit` parity in the first release. Initial support should cover line editing, execution, help commands, clean disconnects, and predictable terminal output.

## Host password authentication

### Linux

Use a dedicated PAM service, for example `picle-ssh`. Authentication must include the configured PAM authentication and account checks so locked, expired, or otherwise ineligible accounts are rejected. End every PAM transaction and do not retain the password.

PAM calls may block and must run in a bounded worker executor. Treat PAM errors as authentication failures externally while retaining safe diagnostic detail in server logs.

### Windows

Use `LogonUser` with a documented logon type and provider. Support explicit local and domain username formats. Close every returned token handle after authentication.

The token proves the credentials were accepted; it does not make the in-process PICLE session execute as that user. Do not use thread impersonation in the shared server process. Per-user execution requires a separate process or system OpenSSH.

### Common requirements

- Password authentication must be explicitly enabled in server configuration.
- Never place passwords in command-line arguments, configuration files, logs, audit events, or session objects.
- Apply authentication timeouts and rate limits by source and username.
- Return indistinguishable failures for unknown users and incorrect passwords.
- Run PAM, `LogonUser`, and other blocking identity-provider calls outside the event loop.
- Perform command authorization after authentication succeeds.

## Command-tree authorization

Authorization rules operate on canonical PICLE model and command paths, not the raw input string. Aliases and serialization aliases must resolve to the same canonical path before evaluation.

Pattern syntax:

- `*` matches every command.
- `show` matches the `show` node itself.
- `show *` matches every command below `show`.
- `show version` matches only that command path.

Policy example:

```yaml
default: allow
groups:
  operators:
    allow:
      - "show *"
    deny:
      - "show secrets"
users:
  alice:
    deny:
      - "shell"
```

Evaluation order:

1. Collect rules for the authenticated user and their host groups.
2. Resolve the entered command to its canonical path.
3. If any `deny` rule matches, deny the command.
4. Otherwise, if any `allow` rule matches, allow it.
5. Otherwise, use `default`, which is `allow` unless configured differently.

An administrator can build a strict allow-list by setting `default: deny` and adding rules such as `allow: ["show *"]`. Because explicit deny has priority, an allow rule cannot override a matching deny rule.

Authorization must be applied consistently to:

- Command execution, immediately before dispatch.
- Help, command-tree output, discovery, and completion so denied paths are not advertised. A model node remains visible when it contains at least one visible command.
- Dynamically mounted models and commands.
- Built-in commands such as `shell`, `history`, and navigation commands.

The execution check is authoritative. Hiding a command from help or completion is not a security control.

The default `allow *` policy includes built-in commands such as `shell`. This preserves existing PICLE behavior but means every authenticated user can execute commands with the server account's privileges unless an administrator adds an explicit deny rule. Production examples should deny `shell` unless it is required.

## Consequences and required defaults

- Bind to loopback unless external listening is explicitly configured.
- Require a persistent host key; fail closed if it is missing or insecure.
- Support PAM on Linux, `LogonUser` on Windows, and SSH public keys.
- Require password authentication to be explicitly enabled.
- Separate authentication from authorization.
- Default command authorization to `allow *`; allow deployments to select `default: deny`.
- Make explicit deny rules override every allow rule.
- Run under a dedicated unprivileged service account.
- Accept one interactive shell channel per connection by default.
- Reject SSH `exec`, subsystems, SFTP/SCP, forwarding, and extra channels.
- Set authentication, idle, connection, session, and output limits.
- Do not accept client environment variables by default.
- Do not log passwords, private keys, or command results.
- Disable remote persistent history by default. If enabled, isolate it by principal.
- Document that `allow *` includes `shell` and other high-risk commands; provide explicit deny examples for production deployments.
- Route all output, including Rich output, through the session writer.
- Pin to a maintained AsyncSSH release. Version 2.22.0 must be excluded because of [CVE-2026-45309](https://github.com/advisories/GHSA-g794-3fmp-753h), fixed in 2.23.0.

## Delivery sequence

1. Separate terminal input/output from command parsing and dispatch.
2. Make output and history session-specific.
3. Test concurrent session isolation.
4. Add command-path authorization and filter execution, help, discovery, and completion.
5. Add optional AsyncSSH transport and public-key authentication.
6. Add PAM and `LogonUser` providers with rate limits and audit events.
7. Test Windows and Linux clients, PTY behavior, disconnects, slow clients, and blocking commands.
8. Document system OpenSSH deployment for per-user process identity.

## Acceptance criteria

- Missing or unavailable authentication providers fail closed.
- PAM and `LogonUser` enforce host account status and do not block unrelated sessions.
- Host identity is stable across restarts.
- Only the interactive PICLE shell is exposed.
- Concurrent clients cannot share output, history, shell state, or application state unintentionally.
- Blocking commands do not stall authentication or unrelated sessions.
- Slow clients cannot cause unbounded memory growth.
- Disconnects, cancellation, exceptions, and shutdown release all resources.
- The server runs without root or administrator privileges.
- Documentation states which OS account executes commands.
- Authorization uses canonical paths, supports `*` and subtree patterns, and gives deny rules priority.
- Authorization is enforced during execution and reflected in help, discovery, and completion.
- The default policy is `allow *`, and `default: deny` produces a strict allow-list.
- Authentication failure, authorization denial, and session lifecycle events are auditable without logging secrets.

## Dependency note

AsyncSSH is licensed under `EPL-2.0 OR GPL-2.0-or-later`; PICLE is MIT-licensed. Confirm redistribution and notice requirements before adding AsyncSSH to an extra or bundled distribution. See the [AsyncSSH license](https://github.com/ronf/asyncssh#license).

## Sources reviewed

- [`picle/picle.py`](https://github.com/dmulyalin/picle/blob/master/picle/picle.py)
- [`picle/picle_cmd.py`](https://github.com/dmulyalin/picle/blob/master/picle/picle_cmd.py)
- [`pyproject.toml`](https://github.com/dmulyalin/picle/blob/master/pyproject.toml)
- Local `AGENTS.md`
- External sources linked above, reviewed 2026-09-05
