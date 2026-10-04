# tests/

114 automated tests for the execution engine and node handlers. **No extra packages needed**: they use
Python's built-in `unittest` (pytest also runs them if you prefer).

## Run (from the project root)
```
python -m unittest discover -s tests -t . -v        # everything (~10 s)
python -m unittest tests.test_retries -v            # one file
pytest tests -v                                     # same tests via pytest (optional)
```

## What each file covers
| File | Tests | Covers |
|---|---|---|
| `test_executor.py` | 39 | Graph validation (cycles, missing trigger/fields, unknown types), node registry, run lifecycle, failure + skip handling, timeouts, cancellation, isolation between concurrent runs, node safety (Python snippet sandbox limits, file-path traversal, blocked internal addresses, credential redaction) |
| `test_data_passing.py` | 28 | `{{template}}` resolution (types, defaults, list indexes, errors), data flowing between nodes (HTTP -> condition -> email, webhook -> ML -> email, filter/map chains, joins), JSON extract, log truncation/redaction |
| `test_conditions.py` | 21 | Every comparison operator, true/false routing, rejoining branches, nested conditions, switch/default, the safe expression evaluator (allowed and blocked syntax) |
| `test_retries.py` | 17 | Retry policy maths and clamping, recover-after-failure, giving up, backoff delays, config errors never retried, timeouts retried, only the failing node re-runs |
| `test_parallel.py` | 9 | Branches truly run concurrently, join waits for all parents, diamond data correctness, concurrency limit, failed branch blocks the join but not its sibling |

## How they work
- `helpers.py` starts a tiny local fake API (flaky, delayed, counting and echo endpoints), so tests use the
  **real** `api_integrations` code over real HTTP, with no internet needed.
- Output files and the simulated email outbox go to a temp folder, never your real `outputs/`.
- The ML node is tested with a stand-in model, so these tests don't depend on `ml_model_train/`.

## Not covered yet
API routes, the SQLite recording layer and the WebSocket need FastAPI/SQLAlchemy installed; they can be
added as a separate test file once the stack is set up.
