import time

RETRYABLE_SERVER_CODES = {500, 502, 503, 504}


def _is_daily_quota_exhausted(e) -> bool:
    """True if a 429 is a per-day request quota cap (e.g. the free tier's
    20-requests/day limit) rather than a short-lived per-minute rate limit.
    Retrying a daily cap just burns another of the scarce remaining requests
    on a call that's guaranteed to fail again for hours."""
    details = getattr(e, "details", None)
    if not isinstance(details, dict):
        return False
    err = details.get("error", details)
    if not isinstance(err, dict):
        return False
    for d in err.get("details", []) or []:
        for violation in d.get("violations", []) or []:
            if "day" in str(violation.get("quotaId", "")).lower():
                return True
    return False


def generate_content_with_retry(client, max_retries: int = 3, backoff_secs: float = 1.5, **kwargs):
    """Calls client.models.generate_content, retrying on transient errors
    (server overload, short-lived per-minute rate limits) with exponential
    backoff. Does NOT retry a 429 caused by an exhausted daily quota, since
    that can't recover for hours. Raises the last error once retries are
    exhausted, or immediately for non-retryable errors (bad key, daily
    quota, malformed request, etc.)."""
    from google.genai import errors

    last_error = None
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(**kwargs)
        except errors.APIError as e:
            last_error = e
            code = getattr(e, "code", None)
            retryable = code in RETRYABLE_SERVER_CODES or (code == 429 and not _is_daily_quota_exhausted(e))
            if not retryable or attempt == max_retries - 1:
                raise
            time.sleep(backoff_secs * (2 ** attempt))
    raise last_error
