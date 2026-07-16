"""Lightweight test doubles for Supabase and httpx used across router/service tests."""


class FakeResp:
    """Mimics a supabase-py execute() result (`.data`)."""

    def __init__(self, data):
        self.data = data


class FakeQuery:
    """A fluent query builder whose chained methods all return self. Each call to
    execute() pops the next queued FakeResp for that table."""

    def __init__(self, responses: list):
        self._responses = responses

    def __getattr__(self, _name):
        def method(*_args, **_kwargs):
            return self

        return method

    def execute(self):
        if self._responses:
            return self._responses.pop(0)
        return FakeResp(None)


class FakeStorage:
    def __init__(self, download=b"", signed_url="https://signed.example/file"):
        self._download = download
        self._signed_url = signed_url
        self.uploaded = []
        self.removed = []

    def from_(self, _bucket):
        return self

    def download(self, _path):
        if isinstance(self._download, Exception):
            raise self._download
        return self._download

    def upload(self, path, *_args, **_kwargs):
        self.uploaded.append(path)

    def remove(self, paths):
        self.removed.append(paths)

    def create_signed_url(self, _path, _expires):
        return {"signedURL": self._signed_url}


class FakeSupabase:
    """Configure with `tables={"documents": [FakeResp(...), ...]}` — successive
    execute() calls against a table pop responses in order. Optionally configure
    `rpcs={"increment_daily_usage": [FakeResp(...)]}` the same way."""

    def __init__(
        self,
        tables=None,
        download=b"",
        signed_url="https://signed.example/f",
        rpcs=None,
    ):
        self._tables = tables or {}
        self._rpcs = rpcs or {}
        self.rpc_calls = []
        self.storage = FakeStorage(download=download, signed_url=signed_url)

    def table(self, name):
        return FakeQuery(self._tables.get(name, []))

    def rpc(self, name, params=None):
        self.rpc_calls.append((name, params))
        return FakeQuery(self._rpcs.get(name, []))


class FakeResponse:
    def __init__(self, *, status_code=200, json_data=None, headers=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=None, response=self
            )


class FakeAsyncClient:
    """Drop-in for httpx.AsyncClient. `post_responses`/`get_response` are canned."""

    def __init__(self, *, post_responses=None, get_response=None, **_kwargs):
        self._post_responses = list(post_responses or [])
        self._get_response = get_response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def post(self, *_args, **_kwargs):
        if self._post_responses:
            return self._post_responses.pop(0)
        return FakeResponse(status_code=500)

    async def get(self, *_args, **_kwargs):
        return self._get_response or FakeResponse(json_data={"data": {}})
