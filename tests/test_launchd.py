import os
import subprocess
import xml.etree.ElementTree as ET

import pytest

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SCRIPT = os.path.join(PROJECT_DIR, 'scripts', 'launchd.sh')
DEPLOY = os.path.join(PROJECT_DIR, 'scripts', 'deploy_dashboard.sh')


def render(job: str) -> tuple[str, dict]:
    result = subprocess.run(['bash', SCRIPT, job, 'render'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    root = ET.fromstring(result.stdout.encode())
    items = list(root.find('dict'))
    parsed = {items[i].text: items[i + 1] for i in range(0, len(items), 2)}
    return result.stdout, parsed


def strings(node: ET.Element) -> list[str]:
    return [s.text for s in node.findall('string')]


class TestScripts:
    def test_scripts_exist_and_old_ones_removed(self) -> None:
        assert os.access(SCRIPT, os.X_OK)
        assert os.access(DEPLOY, os.X_OK)
        for old in ('cron_schedule.sh', 'feed_schedule.sh'):
            assert not os.path.exists(os.path.join(PROJECT_DIR, 'scripts', old))

    @pytest.mark.parametrize('argv', [[], ['bogus', 'install'], ['monitor'], ['monitor', 'bogus']])
    def test_usage_on_bad_args(self, argv: list[str]) -> None:
        result = subprocess.run(['bash', SCRIPT] + argv, capture_output=True, text=True)
        assert result.returncode == 1
        assert 'Usage' in result.stdout

    def test_deploy_logs_to_monitor_and_fails_loudly(self) -> None:
        src = open(DEPLOY).read()
        assert 'set -euo pipefail' in src
        assert 'data/monitor/deploy.log' in src
        assert '/dev/null' not in src
        assert 'quantshield.live.export' in src


class TestMonitorPlist:
    def test_program_arguments_and_interval(self) -> None:
        text, plist = render('monitor')
        assert plist['Label'].text == 'com.quantengine.monitor'
        args = strings(plist['ProgramArguments'])
        assert args[0] == os.path.join(PROJECT_DIR, 'venv', 'bin', 'python')
        assert args[1:] == ['-m', 'quantshield.live.daemon', '--once', '--auto-execute']
        assert plist['StartInterval'].text == '1800'
        assert plist['RunAtLoad'].tag == 'true'
        assert 'StartCalendarInterval' not in plist
        assert plist['WorkingDirectory'].text == PROJECT_DIR
        assert plist['StandardOutPath'].text.endswith('data/monitor/daemon.log')
        assert plist['StandardErrorPath'].text.endswith('data/monitor/daemon.log')
        env = plist['EnvironmentVariables']
        assert env.find('key').text == 'PATH'
        assert 'venv/bin' in env.find('string').text
        assert '<!DOCTYPE plist' in text


class TestFeedPlist:
    def test_calendar_and_caffeinate(self) -> None:
        _, plist = render('feed')
        assert plist['Label'].text == 'com.quantengine.feed'
        args = strings(plist['ProgramArguments'])
        assert args[:2] == ['/usr/bin/caffeinate', '-i']
        assert args[2] == os.path.join(PROJECT_DIR, 'scripts', 'run_intraday_session.sh')
        cal = plist['StartCalendarInterval'].findall('dict')
        assert len(cal) == 5
        days = []
        for entry in cal:
            kv = dict(zip([k.text for k in entry.findall('key')], [v.text for v in entry.findall('integer')], strict=True))
            assert kv['Hour'] == '22' and kv['Minute'] == '30'
            days.append(kv['Weekday'])
        assert days == ['0', '1', '2', '3', '4']
        assert plist['RunAtLoad'].tag == 'false'
        assert 'StartInterval' not in plist
        assert plist['StandardOutPath'].text.endswith('data/monitor/feed.log')


class TestLaunchctlVerbs:
    def test_uses_bootstrap_and_bootout(self) -> None:
        src = open(SCRIPT).read()
        assert 'launchctl bootstrap' in src
        assert 'launchctl bootout' in src
        assert 'launchctl load' not in src and 'launchctl unload' not in src
