"""
OpenRouter embedding adapter.

Phase 1 of docs/semantic-search.md.  OpenRouter's embeddings endpoint is
OpenAI-shaped, so a bake-off candidate is a model id rather than another
adapter -- one class covers qwen3-embedding-8b, bge-m3, voyage-4,
text-embedding-3-large and gemini-embedding-2 alike.

Built on `requests`, holding one Session for the life of the provider.  The
corpus takes three batched calls and Phase 4's runtime embeds a query per cache
miss, so connection reuse is worth having on both paths -- a fresh TLS
handshake per call is most of the latency budget when the whole request is one
short string.

The key comes from the OPENROUTER_API_KEY environment variable, falling back to
a git-ignored .env at the repo root.  (pipenv also loads .env by itself, so
`pipenv run` sees the variable without the fallback; the fallback is for
everything else.)  Never settings_local.py: that file is rewritten each
admission cycle, and the key has to reach both the scripts/ tools and the web
process.
"""

import os
import time

import requests

from .base import EmbeddingError, EmbeddingProvider

API_URL = 'https://openrouter.ai/api/v1/embeddings'

DEFAULT_MODEL = 'qwen/qwen3-embedding-8b'

# OpenRouter documents no maximum array length; 64 keeps a request small enough
# to retry cheaply and still embeds the 159-title corpus in three calls.
DEFAULT_BATCH_SIZE = 64

# Generous, because this is the once-per-cycle generation path.  Phase 4's
# runtime query path passes its own ~1.5s timeout: a visitor waiting on a
# search page is a different deadline from a script embedding 290 majors.
DEFAULT_TIMEOUT = 30.0

RETRY_STATUSES = frozenset([408, 429, 500, 502, 503, 504])
MAX_ATTEMPTS = 3

# a rate limiter is allowed to ask for longer than we are willing to wait
MAX_RETRY_AFTER = 10.0

ENV_VAR = 'OPENROUTER_API_KEY'


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))


def read_env_file(path=None):
    """Parse a .env file into a dict.  Missing file is not an error.

    Deliberately minimal: KEY=value lines, # comments, optional surrounding
    quotes.  Anything fancier belongs in a real dotenv library, which this
    project does not have and does not need for one key.
    """
    if path is None:
        path = os.path.join(_repo_root(), '.env')
    if not os.path.exists(path):
        return {}

    values = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
                value = value[1:-1]
            values[key.strip()] = value
    return values


def read_api_key(env_path=None):
    """The OpenRouter key: environment first, then .env.  Raises if absent."""
    key = os.environ.get(ENV_VAR) or read_env_file(env_path).get(ENV_VAR)
    if not key:
        raise EmbeddingError(
            'no %s in the environment or in .env at the repo root. '
            'See docs/semantic-search.md, Phase 1.' % ENV_VAR)
    return key


def _retry_after(response, default):
    """Seconds to wait before retrying, honouring Retry-After within reason.

    Only the delta-seconds form is honoured.  RFC 9110 also allows an HTTP-date,
    which falls back to the caller's backoff -- a date means the wait is long
    enough that a search page should not be holding a connection for it anyway.
    """
    header = response.headers.get('Retry-After') if response is not None else None
    try:
        return min(float(header), MAX_RETRY_AFTER)
    except (TypeError, ValueError):
        return default


class OpenRouterProvider(EmbeddingProvider):
    """Embeddings via https://openrouter.ai/api/v1/embeddings.

    `deny_data_collection` sends `provider: {data_collection: "deny"}`, which
    keeps OpenRouter from routing to backends that train on the request.  It is
    on by default: these are search queries from a public university site, and
    docs/semantic-search.md accepts the egress rather than welcoming it.  If a
    model becomes unroutable under it, turning it off is the fix -- and a
    deliberate one.

    Retries are an explicit loop rather than an HTTPAdapter/urllib3 Retry
    policy.  Both work; this one keeps the behaviour readable in one place and
    directly testable with a stub session, and it lets a 429's Retry-After
    override the backoff.
    """

    name = 'openrouter'

    def __init__(self, model=DEFAULT_MODEL, api_key=None, dimensions=None,
                 timeout=DEFAULT_TIMEOUT, batch_size=DEFAULT_BATCH_SIZE,
                 deny_data_collection=True, url=API_URL, session=None,
                 sleep=time.sleep):
        self.model = model
        self.dimensions = dimensions
        self.timeout = timeout
        self.batch_size = batch_size
        self.deny_data_collection = deny_data_collection
        self.url = url
        self.session = session if session is not None else requests.Session()
        self._api_key = api_key
        self._sleep = sleep          # injectable so tests do not wait
        self.request_count = 0

    @property
    def api_key(self):
        if self._api_key is None:
            self._api_key = read_api_key()
        return self._api_key

    def _headers(self):
        return {'Authorization': 'Bearer %s' % self.api_key,
                'Content-Type': 'application/json',
                'X-Title': 'admportal major search'}

    def _payload(self, texts):
        payload = {'model': self.model, 'input': texts,
                   'encoding_format': 'float'}
        if self.dimensions:
            payload['dimensions'] = self.dimensions
        if self.deny_data_collection:
            payload['provider'] = {'data_collection': 'deny'}
        return payload

    def _post(self, texts):
        last_error = None

        for attempt in range(MAX_ATTEMPTS):
            self.request_count += 1
            response = None
            try:
                response = self.session.post(self.url,
                                             json=self._payload(texts),
                                             headers=self._headers(),
                                             timeout=self.timeout)
                if response.status_code == 200:
                    # requests' JSONDecodeError is BOTH a ValueError and a
                    # RequestException.  Keep this catch here, inside the 200
                    # branch: moved or widened, an HTML error page from a proxy
                    # would fall through to the retry handler below and be
                    # retried three times as if it were a connection failure.
                    try:
                        return response.json()
                    except ValueError as e:
                        raise EmbeddingError(
                            '%s returned unparseable JSON: %s'
                            % (self.url, e)) from e

                last_error = EmbeddingError(
                    '%s returned HTTP %d: %s'
                    % (self.url, response.status_code, response.text[:500]))
                if response.status_code not in RETRY_STATUSES:
                    raise last_error
            except requests.RequestException as e:
                last_error = EmbeddingError('%s unreachable: %s'
                                            % (self.url, e))

            if attempt < MAX_ATTEMPTS - 1:
                self._sleep(_retry_after(response, 2 ** attempt))

        raise last_error

    def _vectors_from(self, response, expected):
        try:
            data = response['data']
        except (TypeError, KeyError) as e:
            raise EmbeddingError('no "data" in the OpenRouter response: %r'
                                 % (response,)) from e

        if len(data) != expected:
            raise EmbeddingError('asked for %d embeddings, got %d'
                                 % (expected, len(data)))

        # the response carries an explicit index; do not trust array order
        try:
            ordered = sorted(data, key=lambda item: item['index'])
        except KeyError:
            ordered = data

        return [item['embedding'] for item in ordered]

    def embed_documents(self, texts):
        texts = list(texts)
        if not texts:
            return []

        vectors = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            vectors.extend(self._vectors_from(self._post(batch), len(batch)))

        if self.dimensions is None and vectors:
            self.dimensions = len(vectors[0])
        return vectors
