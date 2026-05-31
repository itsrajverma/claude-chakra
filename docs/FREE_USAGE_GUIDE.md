# Running Claude Chakra for Free — the Maximum-Mileage Guide

Claude Chakra is a proxy that lets **Claude Code** (and the VS Code / JetBrains
extensions) talk to ~a dozen free model backends instead of a paid Anthropic key. This
guide is about one thing: **squeezing the most free coding out of it before any quota
runs dry.**

The trick isn't a single magic provider — it's **stacking** them. Each free tier has a
daily/requests cap; chain enough of them (and pool multiple keys per provider) and you
effectively never hit a wall during a normal day of coding.

> **TL;DR**
> 1. Grab free keys from **Groq + Cerebras + Google Gemini** (no credit card on any of
>    them). Add **GitHub Models**, **Hugging Face**, **Chutes**, **SambaNova**, and
>    **OpenRouter** `:free` models for depth.
> 2. Paste one key per account into each provider's `*_API_KEYS` pool to multiply quota.
> 3. Run `chakra-providers` — it prints a ready-made `MODEL` + `MODEL_FALLBACKS` chain
>    from every free provider you've configured.
> 4. Keep a local **Ollama** model as the bottomless final fallback.

---

## 1. The one command that does the planning for you

After you've added any keys (via the Admin UI or `~/.chakra/.env`), run:

```bash
chakra-providers
```

It inspects your config and prints:

- every free provider and whether it's **[ready]** (and how many keys are pooled),
- the **get-a-key URL** for free providers you haven't set up yet, and
- a **copy-pasteable `MODEL_FALLBACKS` chain** wired from all your configured free
  tiers, ordered so a request spills to the next provider the instant one runs out.

```
Free providers: 3/11 configured (8 more available with a free key).
...
  MODEL=groq/llama-3.3-70b-versatile
  MODEL_FALLBACKS=groq/llama-3.3-70b-versatile,gemini/gemini-2.5-flash,github/openai/gpt-4o-mini
```

Paste those two lines into your config and you're running on a stacked free bench.

---

## 2. The free providers (and how to max each one)

All limits below are **approximate** and change often — treat them as "order of
magnitude," and always confirm on the provider's own dashboard.

| Provider | `MODEL` example | Credit card? | Rough free ceiling | Why it's on the list |
| --- | --- | --- | --- | --- |
| **Groq** | `groq/llama-3.3-70b-versatile` | ❌ none | ~1k req/day (70B), ~14k (8B) | Fastest tokens/sec anywhere |
| **Cerebras** | `cerebras/qwen-3-coder-480b` | ❌ none | large daily allowance | Huge coder models, very fast |
| **Google Gemini** | `gemini/gemini-2.5-flash` | ❌ none | ~1.5k req/day on Flash | Biggest single free RPD |
| **GitHub Models** | `github/openai/gpt-4o-mini` | ❌ none (GitHub PAT) | per-model RPM/RPD | GPT, Llama, DeepSeek, Grok… |
| **Hugging Face** | `huggingface/meta-llama/Llama-3.3-70B-Instruct` | ❌ none | monthly credit pool | Widest model catalog |
| **Chutes** | `chutes/deepseek-ai/DeepSeek-V3-0324` | ❌ none | prototyping quota | DeepSeek/Qwen/GLM, cheap-at-scale |
| **SambaNova** | `sambanova/Meta-Llama-3.3-70B-Instruct` | ❌ none | persistent free tier | Fast Llama 3.3 / 3.1 405B |
| **Mistral** | `mistral/mistral-small-latest` | ❌ none | "Experiment" tier | All Mistral models |
| **OpenRouter** | `open_router/deepseek/deepseek-chat:free` | ❌ none | ~50 req/day per `:free` model | Dozens of `:free` models |
| **OpenCode Zen** | `opencode/big-pickle` | ❌ none | some free models | Coding-tuned models |
| **NVIDIA NIM** | `nvidia_nim/z-ai/glm4.7` | ❌ none | free credits | The default; big model menu |

Get-a-key links live in the [README Provider Matrix](../README.md#provider-matrix), and
`chakra-providers` prints them inline for anything you haven't set up.

### Local = unlimited (your final safety net)

| Provider | Example | Notes |
| --- | --- | --- |
| **Ollama** | `ollama/llama3.1` | `ollama pull llama3.1`, zero keys, runs offline |
| **LM Studio** | `lmstudio/<model>` | GUI model server on `localhost:1234` |
| **llama.cpp** | `llamacpp/<model>` | `llama-server` on `localhost:8080` |

Put one of these **last** in your fallback chain and you can keep coding even if every
cloud tier is exhausted or your connection drops.

---

## 3. The three levers that multiply free usage

### Lever 1 — Pool multiple keys per provider (`*_API_KEYS`)

Free limits are usually **per key/account**. Every authenticated provider accepts a
JSON list (or comma-separated string) of keys and round-robins across them, rotating off
any key that returns `429` for a 60-second cooldown:

```bash
GROQ_API_KEYS=["gsk_account_one","gsk_account_two","gsk_account_three"]
GEMINI_API_KEYS=["AIza_one","AIza_two"]
```

Three Groq keys ≈ three times the daily Groq quota, transparently.

### Lever 2 — Chain providers (`MODEL_FALLBACKS`)

When the tier-resolved provider's **whole key pool** is exhausted/cooling (or it returns
`5xx`/auth), the request **transparently retries the next provider in the chain — mid-request,
before Claude Code sees a single byte:**

```bash
MODEL=groq/llama-3.3-70b-versatile
MODEL_FALLBACKS=groq/llama-3.3-70b-versatile,cerebras/qwen-3-coder-480b,gemini/gemini-2.5-flash,github/openai/gpt-4o-mini,sambanova/Meta-Llama-3.3-70B-Instruct,ollama/llama3.1
```

Notes:
- Fallback triggers on **open failures** (`429` / `5xx` / auth / exhausted pool). A `400`
  (malformed request) is **not** retried across providers.
- Once a response **starts streaming**, it commits to that provider (the bytes are already
  on the wire) — exactly like key rotation.
- Every model in the chain is **validated against its provider at startup**, so a typo
  fails fast instead of mid-session.

`chakra-providers` builds this line for you from your configured free tiers.

### Lever 3 — Spread tiers across providers (`MODEL_OPUS/SONNET/HAIKU`)

Claude Code sends three model tiers. Route each to a **different** provider so no single
quota carries the whole session — the cheap/fast Haiku traffic shouldn't burn your best
model's daily cap:

```bash
MODEL_OPUS=cerebras/qwen-3-coder-480b          # heavy reasoning / big edits
MODEL_SONNET=groq/llama-3.3-70b-versatile       # day-to-day coding
MODEL_HAIKU=gemini/gemini-2.5-flash             # quick probes, title generation
MODEL=ollama/llama3.1                           # fallback when all else is dry
```

---

## 4. Recommended starter stacks

**"No credit card, ever"** — three signups, all cardless:

```bash
MODEL=groq/llama-3.3-70b-versatile
MODEL_FALLBACKS=groq/llama-3.3-70b-versatile,cerebras/qwen-3-coder-480b,gemini/gemini-2.5-flash
```

**"Maximum coding depth"** — add coder-grade models + a local backstop:

```bash
MODEL_OPUS=cerebras/qwen-3-coder-480b
MODEL_SONNET=groq/llama-3.3-70b-versatile
MODEL_HAIKU=gemini/gemini-2.5-flash
MODEL=ollama/llama3.1
MODEL_FALLBACKS=cerebras/qwen-3-coder-480b,sambanova/Meta-Llama-3.3-70B-Instruct,github/openai/gpt-4o-mini,chutes/deepseek-ai/DeepSeek-V3-0324,huggingface/meta-llama/Llama-3.3-70B-Instruct,ollama/llama3.1
```

**"Offline / flaky internet"** — local first, cloud as a bonus:

```bash
MODEL=ollama/llama3.1
MODEL_FALLBACKS=ollama/llama3.1,groq/llama-3.3-70b-versatile
```

---

## 5. Don't waste the quota you have

- **Built-in probe shortcuts.** Claude Code fires small "is this connection alive?" /
  title-generation probes constantly. Chakra answers the trivial ones **locally**
  (`api/optimization_handlers.py`) so they never touch a provider — free quota saved
  automatically, nothing to configure.
- **Tune the local rate limiter.** `PROVIDER_RATE_LIMIT` / `PROVIDER_RATE_WINDOW` cap how
  fast Chakra forwards requests; lower them if a provider is rejecting bursts, raise them
  if you're leaving throughput on the table.
- **Pick smaller models for small jobs.** Routing `MODEL_HAIKU` to an 8B model (e.g.
  `groq/llama-3.1-8b-instant`) burns far less of your premium daily caps.
- **Region/proxy.** Some free tiers are region-gated; each provider has a `*_PROXY`
  setting (e.g. `GEMINI_PROXY`) if you need to route around that.

---

## 6. Quick setup recap

1. Install: `uv tool install --force .` → gives you `chakra-server`, `chakra-claude`,
   `chakra-providers`.
2. `chakra-init` to scaffold `~/.chakra/.env` (or edit keys in the Admin UI at `/admin`).
3. Add free keys for Groq / Cerebras / Gemini (cardless) plus any others you want.
4. `chakra-providers` → paste the suggested `MODEL` + `MODEL_FALLBACKS`.
5. `chakra-claude` to launch Claude Code pointed at the proxy. Code for free. 🌀

See the [README](../README.md) for the full provider matrix, the Admin UI tour, and the
Discord/Telegram bot wrappers.
