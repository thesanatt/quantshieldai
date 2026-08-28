import os
from unittest.mock import MagicMock, patch

import pytest

import quantshield.live.notify as notify_mod
from quantshield.live.notify import _sanitize, format_emergency, notify, send_discord, send_email, send_pushover


class TestSanitize:
    @pytest.mark.parametrize('msg', ['API_KEY=abc123', 'SECRET=xyz', 'PASSWORD=hunter2', 'ALPACA_KEY=abc',
                                     'token=deadbeef', 'DISCORD_WEBHOOK_URL=https://x'])
    def test_blocks_assignments_of_sensitive_names(self, msg: str) -> None:
        assert _sanitize(msg) == '[REDACTED: message contained sensitive data]'

    @pytest.mark.parametrize('msg', ['Portfolio up 5% today, VIX at 18', 'Bought 15 NVDA, 20 GOOGL',
                                     'US: $103,000 (+3.4%). India: Rs.1,080,000',
                                     'Zerodha access token expired; run the daily login before 09:25 IST'])
    def test_allows_normal_messages(self, msg: str) -> None:
        assert _sanitize(msg) == msg


class TestSendDiscord:
    @patch.dict(os.environ, {'DISCORD_WEBHOOK_URL': ''})
    def test_no_url_returns_false(self) -> None:
        assert send_discord('test') is False

    @patch.dict(os.environ, {'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/123/abc'})
    @patch('quantshield.live.notify.requests.post')
    def test_posts_sanitized_content(self, post: MagicMock) -> None:
        post.return_value = MagicMock(status_code=204)
        assert send_discord('hello') is True
        assert post.call_args.kwargs['json']['content'] == 'hello'
        assert post.call_args.kwargs['timeout'] == 10

    @patch.dict(os.environ, {'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/123/abc'})
    @patch('quantshield.live.notify.requests.post', side_effect=Exception('network'))
    def test_exception_returns_false(self, post: MagicMock) -> None:
        assert send_discord('test') is False

    @patch.dict(os.environ, {'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/123/abc'})
    @patch('quantshield.live.notify.requests.post')
    def test_non_success_status(self, post: MagicMock) -> None:
        post.return_value = MagicMock(status_code=500)
        assert send_discord('test') is False


class TestSendEmail:
    @patch.dict(os.environ, {'SMTP_EMAIL': '', 'SMTP_PASSWORD': '', 'SMTP_TO': ''})
    def test_no_creds_returns_false(self) -> None:
        assert send_email('test') is False

    @patch.dict(os.environ, {'SMTP_EMAIL': 'a@b.com', 'SMTP_PASSWORD': '', 'SMTP_TO': 'c@d.com'})
    def test_missing_password_returns_false(self) -> None:
        assert send_email('test') is False

    @patch.dict(os.environ, {'SMTP_EMAIL': 'a@b.com', 'SMTP_PASSWORD': 'pass', 'SMTP_TO': 'c@d.com'})
    @patch('quantshield.live.notify.smtplib.SMTP')
    def test_sends_email(self, smtp_class: MagicMock) -> None:
        server = MagicMock()
        smtp_class.return_value.__enter__ = MagicMock(return_value=server)
        smtp_class.return_value.__exit__ = MagicMock(return_value=False)
        assert send_email('hello', subject='S') is True
        server.starttls.assert_called_once()
        server.login.assert_called_once_with('a@b.com', 'pass')
        assert server.sendmail.call_args[0][:2] == ('a@b.com', 'c@d.com')

    @patch.dict(os.environ, {'SMTP_EMAIL': 'a@b.com', 'SMTP_PASSWORD': 'pass', 'SMTP_TO': 'c@d.com'})
    @patch('quantshield.live.notify.smtplib.SMTP', side_effect=Exception('smtp error'))
    def test_exception_returns_false(self, smtp: MagicMock) -> None:
        assert send_email('test') is False


class TestSendPushover:
    @patch.dict(os.environ, {'PUSHOVER_USER_KEY': '', 'PUSHOVER_APP_TOKEN': ''})
    def test_no_creds_returns_false(self) -> None:
        assert send_pushover('test') is False

    @patch.dict(os.environ, {'PUSHOVER_USER_KEY': 'ukey', 'PUSHOVER_APP_TOKEN': 'atok'})
    @patch('quantshield.live.notify.requests.post')
    def test_with_creds_calls_api(self, post: MagicMock) -> None:
        post.return_value = MagicMock(status_code=200)
        assert send_pushover('hello') is True
        data = post.call_args.kwargs['data']
        assert data == {'token': 'atok', 'user': 'ukey', 'message': 'hello', 'title': 'Quant Engine'}

    @patch.dict(os.environ, {'PUSHOVER_USER_KEY': 'ukey', 'PUSHOVER_APP_TOKEN': 'atok'})
    @patch('quantshield.live.notify.requests.post', side_effect=Exception('fail'))
    def test_exception_returns_false(self, post: MagicMock) -> None:
        assert send_pushover('test') is False

    @patch.dict(os.environ, {'PUSHOVER_USER_KEY': 'ukey', 'PUSHOVER_APP_TOKEN': 'atok'})
    @patch('quantshield.live.notify.requests.post')
    def test_non_200_returns_false(self, post: MagicMock) -> None:
        post.return_value = MagicMock(status_code=500)
        assert send_pushover('test') is False


class TestNotify:
    @patch('quantshield.live.notify.send_discord', return_value=False)
    @patch('quantshield.live.notify.send_email', return_value=False)
    @patch('quantshield.live.notify.send_pushover', return_value=False)
    def test_all_fail_returns_false(self, po: MagicMock, em: MagicMock, dc: MagicMock) -> None:
        assert notify('test') is False

    @patch('quantshield.live.notify.send_discord', return_value=True)
    @patch('quantshield.live.notify.send_email', return_value=False)
    def test_discord_success_short_circuits(self, em: MagicMock, dc: MagicMock) -> None:
        assert notify('test') is True
        em.assert_not_called()

    @patch('quantshield.live.notify.send_discord', return_value=False)
    @patch('quantshield.live.notify.send_email', return_value=True)
    def test_email_fallback(self, em: MagicMock, dc: MagicMock) -> None:
        assert notify('test') is True
        dc.assert_called_once()
        assert em.call_args.kwargs['subject'] == '[INFO] Quant Engine'

    @patch('quantshield.live.notify.send_discord', return_value=False)
    @patch('quantshield.live.notify.send_email', return_value=False)
    @patch('quantshield.live.notify.send_pushover', return_value=True)
    def test_pushover_success_counts(self, po: MagicMock, em: MagicMock, dc: MagicMock) -> None:
        assert notify('test') is True
        po.assert_called_once()

    @patch('quantshield.live.notify.send_discord', return_value=True)
    def test_level_prefixes_plain_ascii(self, dc: MagicMock) -> None:
        notify('crisis', level='emergency')
        assert dc.call_args[0][0] == 'EMERGENCY: crisis'
        notify('warn', level='warning')
        assert dc.call_args[0][0] == 'WARNING: warn'
        notify('info msg', level='info')
        assert dc.call_args[0][0] == 'info msg'

    @patch('quantshield.live.notify.send_discord', return_value=True)
    def test_local_log_line_on_stderr(self, dc: MagicMock, capsys: pytest.CaptureFixture) -> None:
        notify('hello there', level='warning')
        err = capsys.readouterr().err
        assert '[notify]' in err and 'WARNING: hello there' in err


class TestFormatEmergency:
    def test_contains_triggers_vix_and_affected(self) -> None:
        msg = format_emergency({'triggers': ['VIX > 40', 'SBIN.NS down -6.0% today'], 'us_vix': 45.0,
                                'india_vix': None, 'affected_tickers': ['SBIN.NS']})
        assert msg.splitlines()[0] == 'CRASH ALERT'
        assert 'US VIX: 45.0' in msg
        assert 'India VIX' not in msg
        assert '- VIX > 40' in msg and '- SBIN.NS down -6.0% today' in msg
        assert 'Affected: SBIN.NS' in msg

    def test_no_secrets_and_ascii_only(self) -> None:
        msg = format_emergency({'triggers': ['test'], 'us_vix': 20, 'india_vix': 31.0, 'affected_tickers': []})
        for keyword in ('DISCORD', 'API_KEY', 'SECRET', 'ALPACA', 'WEBHOOK', 'PASSWORD'):
            assert keyword not in msg.upper()
        assert msg.isascii()


class TestSurface:
    def test_public_surface_is_exactly_the_three_channels_plus_notify(self) -> None:
        public = {
            name for name, obj in vars(notify_mod).items()
            if not name.startswith('_') and callable(obj) and getattr(obj, '__module__', None) == notify_mod.__name__
        }
        assert public == {'format_emergency', 'notify', 'send_discord', 'send_email', 'send_pushover'}

    @patch('quantshield.live.notify.send_discord', return_value=True)
    def test_every_level_renders_ascii(self, dc: MagicMock) -> None:
        for level in ('info', 'warning', 'emergency'):
            notify('VIX 45.0, INR 88.2', level=level)
            assert dc.call_args[0][0].isascii()
