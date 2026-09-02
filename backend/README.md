# Project-Astra
A Python desktop AI assistant with voice control, wake word, TTS, Ollama AI, and system automation.

Backend launch command (from this directory):

```text
python main.py
```

Optional services report `OFFLINE` without preventing typed commands from working. Configure
`OLLAMA_BASE_URL`, `TTS_ENABLED`, `WAKE_WORD_ENABLED`, `SPEECH_RECOGNITION_ENABLED`, and
`LOG_LEVEL` through environment variables.

## Model separation

| Role | Env var | Default | Used for |
| --- | --- | --- | --- |
| Normal conversation | `AI_MODEL` | `qwen3:1.7b` | Chat answers only |
| Structured agent planning | `AGENT_MODEL` | `qwen3:4b` | JSON task plans only |

- The planner **never** falls back to the conversation model. If `AGENT_MODEL` is not
  installed (checked against Ollama `/api/tags` at startup and before each plan), the agent
  returns a controlled "planner unavailable" response and nothing executes.
- Startup reports whether both models are installed.
- `OLLAMA_MODEL` remains a backward-compatible alias for `AI_MODEL`, and
  `AGENT_PLANNER_MODEL` an alias for `AGENT_MODEL`.

## Timeouts and planner budget

- `AI_TIMEOUT` (default 90s): normal chat requests.
- `AGENT_PLANNER_TIMEOUT` (default 45s): bounded planning; raise it on slower hardware —
  measured qwen3:4b two-step planning can take 21–50s including cold model loads.
- `AGENT_PLANNER_NUM_PREDICT` (default 128): planner output token budget. qwen3:4b
  pretty-prints JSON under Ollama structured-output mode, so two-step plans need ~140
  tokens; set 160 if planning truncates.
- Truncated or malformed planner output is rejected as a controlled failure — malformed
  plans are never repaired and never executed.

## Safety architecture

Model output → JSON parse → schema validation → step-id validation → tool allowlist →
argument validation → reference validation → approval check → execution.
Tools such as `create_note`, `create_todo`, `create_file`, and `create_folder` require
explicit approval before any persistent write.

## Verification tools

- `run_phase14_smoke.py` — six end-to-end smoke tests in fresh processes.
- `real_ollama_test.py` — real (non-mocked) normal-AI and planner requests.
- `security_scan.py` — scans project code for unsafe execution primitives.
- `phase15_tts_voice.py` / `phase16_import_check.py` — TTS/voice and import-safety checks.