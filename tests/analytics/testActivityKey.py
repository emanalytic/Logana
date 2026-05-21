from logana.analytics.activityKey import resolveActivityKey
from helpers.eventFactory import buildLogEvent


def test_activityPrefersUrlPath():
    assert resolveActivityKey(buildLogEvent(message="ignored", urlPath="/api/users")) == "/api/users"


def test_activityUsesSyslogProgram():
    event = buildLogEvent(
        message="sshd(pam_unix)[19939]: authentication failure",
        parserId="syslog",
        urlPath="",
    )
    assert resolveActivityKey(event) == "svc:sshd"


def test_activitySkipsMonthTokensInFingerprint():
    event = buildLogEvent(
        message="[Sun Dec 04 04:47:44 2005] [error] mod_jk child workerEnv in error state 6",
        parserId="tokenExtractor",
        urlPath="",
    )
    key = resolveActivityKey(event)
    assert not key.startswith("msg:sun-dec")
