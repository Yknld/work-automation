"""Experimental Microsoft 365 Copilot UI client using installed Edge."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

URL = 'https://m365.cloud.microsoft/chat'
# Candidate selectors, not a stable Microsoft API. Override after inspecting your UI.
DEFAULT_REPLY = '[data-content="ai-message"], [data-testid="copilot-message"]'

class CopilotError(RuntimeError):
    pass

class Completion:
    """Require observed generation plus stable new assistant text; never old history."""
    def __init__(self, previous):
        self.previous = previous
        self.saw_busy = False
        self.text = ''
        self.changed = 0

    def update(self, replies, busy, now, completed=False):
        self.saw_busy |= busy
        if len(replies) <= len(self.previous):
            return None
        value = replies[-1].strip()
        if value != self.text:
            self.text, self.changed = value, now
        if value and (self.saw_busy or completed) and not busy and now - self.changed >= 3:
            return value
        return None

class Copilot:
    def __init__(self, reply_selector=DEFAULT_REPLY, timeout=180):
        self.reply_selector = reply_selector
        self.timeout = timeout
        self.context = None
        self.runtime = None
        self.owned_chat = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        root = Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local/share'))
        profile = root/'CopilotPythonBridge'/'EdgeProfile'
        profile.mkdir(parents=True, exist_ok=True)
        self.runtime = sync_playwright().start()
        try:
            self.context = self.runtime.chromium.launch_persistent_context(
                str(profile), channel='msedge', headless=False,
                accept_downloads=False, chromium_sandbox=True)
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.page.goto(URL, wait_until='domcontentloaded', timeout=60000)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        try:
            if self.context:
                self.context.close()
        finally:
            if self.runtime:
                self.runtime.stop()

    def composer(self):
        # Only choose an unambiguous visible editor, never arbitrary page content.
        candidates = self.page.get_by_role('textbox').filter(visible=True)
        if candidates.count() == 1:
            return candidates.first
        for name in ['Message Copilot', 'Envoyer un message à Copilot']:
            candidate = self.page.get_by_role('textbox', name=name, exact=True)
            if candidate.count() == 1 and candidate.is_visible():
                return candidate
        return None

    def wait_ready(self):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self.page.url.startswith('https://m365.cloud.microsoft/'):
                editor = self.composer()
                if editor is not None and editor.is_editable():
                    return editor
            self.page.wait_for_timeout(500)
        raise CopilotError('Copilot editor not ready. Check the visible Edge window for sign-in, policy messages, or a changed interface.')

    def submit_prompt(self, editor, prompt):
        editor.fill(prompt)
        # Wait for the app to enable Send after processing the editor input.
        send = self.page.get_by_role('button', name=re.compile(
            r'^(Send|Send message|Send prompt|Submit|Submit prompt|Envoyer|Envoyer le message)(\s*\([^)]*\))?$', re.I
        )).filter(visible=True)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            count = send.count()
            if count > 1:
                raise CopilotError('Multiple Send buttons found. No submission attempted.')
            if count == 1 and send.is_enabled():
                print('Clicking Send once...', file=sys.stderr, flush=True)
                send.click(timeout=5000)
                return
            self.page.wait_for_timeout(200)
        raise CopilotError('Send button was not uniquely identified and enabled. Prompt is filled but was not submitted. No Enter fallback was attempted.')

    def copy_buttons(self):
        return self.page.get_by_role('button', name=re.compile(
            r'^(Copy|Copy response|Copy message|Copy answer|Copier|Copier la réponse|Copier le message)(\s*\([^)]*\))?$', re.I
        )).filter(visible=True)

    def reply_near_copy(self, button, prompt):
        # Read the smallest reply container around its toolbar, not the clipboard
        # or whole page. Reject containers containing the prompt or composer.
        return button.evaluate("""(button, prompt) => {
            let node = button.parentElement;
            for (let depth = 0; node && depth < 8; depth++, node = node.parentElement) {
                if (['BODY', 'MAIN', 'HTML'].includes(node.tagName)) return '';
                if (node.querySelector('[role="textbox"], textarea, [contenteditable="true"]')) return '';
                if ((node.innerText || '').includes(prompt)) return '';
                const copy = node.cloneNode(true);
                copy.querySelectorAll('button, [role="button"], [role="toolbar"], script, style').forEach(n => n.remove());
                const text = (copy.innerText || copy.textContent || '').trim();
                if (text) return text;
            }
            return '';
        }""", prompt)

    def delete_saved_chat(self):
        """Caller must save/validate output first. Never select chats by title/order."""
        path = self.owned_chat
        if not path or urlsplit(self.page.url).path != path:
            raise CopilotError('Cleanup stopped: current chat is not the recorded automation chat.')
        # Exact conversation path only; titles are not unique.
        links = self.page.locator('a[href]').filter(visible=True)
        matches = [links.nth(i) for i in range(links.count())
                   if urlsplit(links.nth(i).get_attribute('href') or '').path == path]
        if len(matches) != 1:
            raise CopilotError('Cleanup stopped: cannot identify the exact chat link.')
        link = matches[0]
        link.hover()
        # Scope menu lookup to the smallest ancestor containing just this chat link.
        container = link
        menu = None
        for _ in range(4):
            container = container.locator('..')
            if container.locator('a[href*="/chat/conversation/"]').count() != 1:
                break
            buttons = container.get_by_role('button', name=re.compile(r'more|options|menu|plus', re.I)).filter(visible=True)
            if buttons.count() == 1:
                menu = buttons
                break
        if menu is None:
            raise CopilotError('Cleanup stopped: exact chat menu not found. Chat retained.')
        menu.click()
        delete = self.page.get_by_role('menuitem', name=re.compile(r'^(Delete|Supprimer)$', re.I))
        if delete.count() != 1:
            raise CopilotError('Cleanup stopped: Delete menu action not uniquely identified.')
        delete.click()
        dialog = self.page.get_by_role('dialog').filter(visible=True)
        dialog.wait_for(state='visible', timeout=5000)
        if dialog.count() != 1 or not re.search(r'delete chat|supprimer', dialog.inner_text(), re.I):
            raise CopilotError('Cleanup stopped: expected confirmation dialog not found.')
        if urlsplit(self.page.url).path != path:
            raise CopilotError('Cleanup stopped: active conversation changed.')
        confirm = dialog.get_by_role('button', name=re.compile(r'^(Delete|Supprimer)$', re.I))
        if confirm.count() != 1:
            raise CopilotError('Cleanup stopped: confirmation button is ambiguous.')
        confirm.click()
        dialog.wait_for(state='hidden', timeout=10000)
        deadline = time.monotonic()+10
        while time.monotonic()<deadline:
            still_present = any(urlsplit(x.get_attribute('href') or '').path == path
                                for x in self.page.locator('a[href]').all())
            if not still_present:
                self.owned_chat = None
                return
            self.page.wait_for_timeout(250)
        raise CopilotError('Cleanup could not verify removal. Batch stopped; output is saved.')

    def ask(self, prompt):
        if not prompt.strip():
            raise ValueError('Prompt must not be empty')
        self.wait_ready()
        # Every call begins independently; refuse to append to an unknown conversation.
        new_chat = self.page.get_by_role('button', name=re.compile(r'^(New chat|Nouvelle conversation)$', re.I))
        if new_chat.count() != 1:
            new_chat = self.page.get_by_role('link', name=re.compile(r'^(New chat|Nouvelle conversation)$', re.I))
        if new_chat.count() != 1:
            raise CopilotError('Cannot identify New chat uniquely. No prompt was sent.')
        self.owned_chat = None
        new_chat.click()
        editor = self.wait_ready()
        fresh_chat = '/chat/conversation/' not in urlsplit(self.page.url).path
        replies = self.page.locator(self.reply_selector)
        tracker = Completion(replies.all_inner_texts())
        copies_before = self.copy_buttons().count()
        copy_tracker = Completion([])
        announced = False
        self.submit_prompt(editor, prompt)
        # No auto-retry: submission may have succeeded even if detection fails.
        stop = self.page.get_by_role('button', name=re.compile(r'stop (generating|responding|response)|arrêter', re.I))
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            busy = any(stop.nth(i).is_visible() for i in range(stop.count()))
            copies = self.copy_buttons()
            has_new_copy = copies.count() > copies_before
            result = tracker.update(replies.all_inner_texts(), busy, time.monotonic(), completed=has_new_copy)
            if result is None and has_new_copy:
                body = self.reply_near_copy(copies.last, prompt)
                result = copy_tracker.update([body], busy, time.monotonic(), completed=True)
                if body and not announced:
                    print('Reply detected; waiting for it to settle...', file=sys.stderr, flush=True)
                    announced = True
            if result is not None:
                path = urlsplit(self.page.url).path
                if fresh_chat and path.startswith('/chat/conversation/'):
                    self.owned_chat = path
                return result
            self.page.wait_for_timeout(250)
        raise CopilotError('No verified completed reply detected. The prompt may have been sent. Inspect Edge; do not blindly retry. Response selectors or generation controls may need updating.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prompt', help='Prompt text (visible in shell history). Defaults to a fictional test.')
    parser.add_argument('--prompt-file', type=Path, help='Read UTF-8 prompt locally instead of shell history')
    parser.add_argument('--reply-selector', default=DEFAULT_REPLY, help='CSS selector for assistant-only message bodies')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--check', action='store_true', help='Open Copilot and detect editor without sending a prompt')
    args = parser.parse_args()
    if args.prompt and args.prompt_file:
        parser.error('Use --prompt or --prompt-file, not both')
    if args.timeout < 10:
        parser.error('--timeout must be at least 10 seconds')
    try:
        prompt = args.prompt_file.read_text(encoding='utf-8') if args.prompt_file else args.prompt or 'Reply with exactly: Connection test successful.'
        with Copilot(args.reply_selector, args.timeout) as client:
            print('Opened dedicated Edge window. Automatic SSO may sign you in; check that window if prompted.', file=sys.stderr)
            try:
                if args.check:
                    client.wait_ready()
                    print('Copilot editor detected. No prompt sent. Reply capture is not yet verified.')
                else:
                    print(client.ask(prompt))
            except CopilotError:
                if sys.stdin.isatty():
                    print('Keeping Edge open for inspection. Press Enter to close it.', file=sys.stderr)
                    input()
                raise
    except ImportError:
        print('Install the Python package: python -m pip install -r requirements.txt', file=sys.stderr)
        return 2
    except (CopilotError, ValueError, OSError) as exc:
        # Do not dump browser internals, page contents, cookies, or credentials.
        print(str(exc) if isinstance(exc, CopilotError) else type(exc).__name__+': check local arguments/files.', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f'{type(exc).__name__}: Edge could not complete the operation. Check installed Edge, profile conflicts, and company automation policy. No automatic retry.', file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
