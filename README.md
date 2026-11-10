# Work Automation

Experimental Python automation for Microsoft 365 Copilot in installed Microsoft Edge. No extension, separate browser download, or local API server. This is unofficial UI automation, not Microsoft's Copilot API.

## First test on Windows

Keep `automation.py` and `requirements.txt` together. In that folder:

```powershell
python -m pip install -r requirements.txt
python automation.py --check
```

Do **not** run `playwright install`. The script uses installed Edge (`channel="msedge"`). Playwright includes its own automation driver; it is not pure Python internally.

A dedicated Edge window opens. Work SSO may sign in automatically, but this is not guaranteed: the script does not attach to your already-open window or copy its cookies. If Microsoft requires sign-in/MFA, complete it normally in the new window. Company policies may block automation; the script does not bypass them.

`--check` only verifies that a message editor is detected. It sends nothing. Next run the fictional connection test:

```powershell
python automation.py
```

Or provide a prompt:

```powershell
python automation.py --prompt "Does 'We held three workshops' describe a concrete activity? Answer Yes, No, or Unclear."
```

For prompts you do not want in shell history, place a UTF-8 file outside this repository and use `--prompt-file "C:\Work\prompt.txt"`. Prompt content is sent to your organization's Microsoft 365 Copilot service, not processed offline. Use only data approved for that service.

## Python usage

```python
from automation import Copilot

with Copilot() as copilot:
    answer = copilot.ask("Reply with exactly: Hello.")
    print(answer)
```

Every call clicks New chat first and submits by clicking a uniquely identified, enabled Send button once (rather than relying on Enter). Edge is launched with its Chromium sandbox enabled. Requests run sequentially. This version returns text only; Excel integration is not implemented yet.

## Current validation status

The reply-completion logic has local unit tests. **Live Microsoft 365 Copilot submission, SSO and response capture have not been tested against the intended work account.** The default assistant selectors are candidates, not confirmed selectors for that tenant. English and limited French controls are recognized.

If the editor is found but reply capture times out, the prompt may already have been submitted. Do not repeatedly retry. In an interactive terminal the window stays open until you press Enter, so you can inspect it. Fast replies can also complete when a new Copy control appears and the reply text settles.

The adapter detects assistant message selectors or a small response container around a newly appearing Copy button. It never clicks Copy or reads the clipboard. Completion requires settled text, no visible generation control, and either observed generation or a new Copy control. This is still heuristic; a pause during streaming can resemble completion. If your UI differs, the reply selector can be overridden with `--reply-selector`, but it must target assistant message bodies only, not the entire conversation. Control changes may require a code update. Do not send private chat contents, cookies or login details to diagnose this.

UI completion detection is heuristic. This is a prototype for small fictional tests, not a validated unattended batch processor. There is no automatic resend, rate-limit bypass, or screenshot/page-content logging.

## Local browser state

The dedicated session is stored outside the repository at `%LOCALAPPDATA%\CopilotPythonBridge\EdgeProfile` on Windows (under `~/.local/share` on other platforms). Treat that folder as sensitive browser state. Never upload it. Close the dedicated window before another run. Normal browser profiles are untouched.

## Tests

From this repository folder:

```powershell
python -m unittest discover -s tests -v
```

## References

- [Playwright Python: installed Edge and enterprise policies](https://playwright.dev/python/docs/browsers)
- [Microsoft 365 Copilot Chat API: official alternative](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/ai-services/chat/overview)
