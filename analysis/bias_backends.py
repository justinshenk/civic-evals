"""Rating backends for the candidate-bias factorial driver.

Two backends share one contract so Step 1 (base Qwen3-14B) and Step 2
(PCT LoRA) can use identical prompts, parsing, and OLS without an
OpenRouter key:

- ``openrouter`` — AsyncOpenAI against https://openrouter.ai/api/v1
- ``local`` — Hugging Face Transformers (and optional PEFT adapter)
  on the local GPU. Required for the PCT checkpoint, which is a LoRA
  adapter rather than an API-hosted model.

Every successful call returns ``(response_text, parsed_rating)``. Call
failures return an error sentinel string and ``None`` so the OLS path
drops them the same way the historical OpenRouter driver did.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
from dataclasses import dataclass
from typing import Protocol

from bias_templates import parse_rating

# Qwen3 (and similar) wrap chain-of-thought in these tags when thinking
# mode is on. Strip before rating parse so the OLS never sees CoT text.
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_thinking(text: str) -> str:
    """Remove Qwen-style think blocks; leave the final answer intact."""
    return _THINK_BLOCK_RE.sub("", text or "").strip()


@dataclass(frozen=True)
class RateRequest:
    """One candidate-profile prompt for a named model."""

    model: str
    profile: str
    seed: int | None = None


@dataclass(frozen=True)
class RateResult:
    text: str
    rating: float | None
    backend: str
    thinking: bool | None = None


class RatingBackend(Protocol):
    """Minimal async interface used by ``multi_model_bias.gather_for_model``."""

    name: str

    async def rate(self, request: RateRequest) -> RateResult: ...

    async def aclose(self) -> None: ...


# ---- OpenRouter -----------------------------------------------------------


class OpenRouterBackend:
    """OpenAI-compatible chat completions via OpenRouter."""

    name = "openrouter"

    def __init__(
        self,
        *,
        max_tokens: int = 1024,
        concurrency: int = 8,
        thinking: bool | None = None,
    ) -> None:
        from openai import AsyncOpenAI

        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY missing from environment / .env")
        self._client = AsyncOpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
        self._max_tokens = max_tokens
        self._sem = asyncio.Semaphore(concurrency)
        # OpenRouter exposes a unified ``reasoning`` map for thinking models.
        # None = leave provider default alone (historical six-model behavior).
        self._thinking = thinking

    async def rate(self, request: RateRequest) -> RateResult:
        async with self._sem:
            try:
                kwargs: dict = {
                    "model": request.model,
                    "max_tokens": self._max_tokens,
                    "messages": [{"role": "user", "content": request.profile}],
                }
                if self._thinking is not None:
                    kwargs["extra_body"] = {"reasoning": {"enabled": self._thinking}}
                msg = await self._client.chat.completions.create(**kwargs)
                text = (msg.choices[0].message.content or "") if msg.choices else ""
            except Exception as e:  # noqa: BLE001 — record and continue the factorial
                return RateResult(
                    text=f"<error: {type(e).__name__}: {e}>",
                    rating=None,
                    backend=self.name,
                    thinking=self._thinking,
                )
        cleaned = strip_thinking(text) if self._thinking else text
        return RateResult(
            text=cleaned,
            rating=parse_rating(cleaned),
            backend=self.name,
            thinking=self._thinking,
        )

    async def aclose(self) -> None:
        await self._client.close()


# ---- Local Transformers (+ optional PEFT) ---------------------------------


class LocalTransformersBackend:
    """Local Hugging Face generation for base weights and LoRA adapters.

    Model ids are Hugging Face hub paths (e.g. ``Qwen/Qwen3-14B``), not
    OpenRouter slugs. Pass ``adapter_id`` to load a PEFT adapter on top
    of the base (Step 2: ``justinphan3110/Qwen3-14B_PCT``).
    """

    name = "local"

    def __init__(
        self,
        *,
        max_new_tokens: int = 1024,
        thinking: bool = False,
        dtype: str = "bfloat16",
        adapter_id: str | None = None,
        seed: int | None = 0,
        do_sample: bool = True,
        temperature: float = 1.0,
        top_p: float = 1.0,
        model_revision: str | None = None,
        adapter_revision: str | None = None,
    ) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not torch.cuda.is_available():
            raise RuntimeError(
                "Local backend requires CUDA. Activate the civic-evals venv "
                "with scripts/activate_civic_env.sh (clears PYTHONPATH and "
                "sets CUDA_VISIBLE_DEVICES to the MIG UUID)."
            )

        self._torch = torch
        self._max_new_tokens = max_new_tokens
        self._thinking = thinking
        self._adapter_id = adapter_id
        self._seed = seed
        self._do_sample = do_sample
        self._temperature = temperature
        self._top_p = top_p
        self._model_revision = model_revision
        self._adapter_revision = adapter_revision
        self._lock = asyncio.Lock()
        self._models: dict[str, tuple] = {}  # model_id -> (tokenizer, model)
        self._dtype = getattr(torch, dtype)
        self._AutoModelForCausalLM = AutoModelForCausalLM
        self._AutoTokenizer = AutoTokenizer

    def _load(self, model_id: str):
        if model_id in self._models:
            return self._models[model_id]

        tokenizer = self._AutoTokenizer.from_pretrained(
            model_id, revision=self._model_revision
        )
        model = self._AutoModelForCausalLM.from_pretrained(
            model_id,
            revision=self._model_revision,
            dtype=self._dtype,
            device_map="auto",
        )
        if self._adapter_id:
            from peft import PeftModel

            # Tokenizer for chat template comes from the adapter repo when
            # CAIS ships one; fall back to the base tokenizer otherwise.
            with contextlib.suppress(Exception):
                tokenizer = self._AutoTokenizer.from_pretrained(
                    self._adapter_id, revision=self._adapter_revision
                )
            model = PeftModel.from_pretrained(
                model, self._adapter_id, revision=self._adapter_revision
            )

        model.eval()
        self._models[model_id] = (tokenizer, model)
        return tokenizer, model

    def _generate_sync(
        self, model_id: str, profile: str, request_seed: int | None = None
    ) -> str:
        tokenizer, model = self._load(model_id)
        messages = [{"role": "user", "content": profile}]

        # Qwen3's chat template takes enable_thinking=; other families
        # ignore unknown kwargs via a fallback without it.
        try:
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=self._thinking,
            )
        except TypeError:
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

        inputs = tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        gen_kwargs: dict = {
            "max_new_tokens": self._max_new_tokens,
            "do_sample": self._do_sample,
        }
        if self._do_sample:
            gen_kwargs.update(temperature=self._temperature, top_p=self._top_p)
        call_seed = request_seed if request_seed is not None else self._seed
        if call_seed is not None:
            self._torch.manual_seed(call_seed)
            if self._torch.cuda.is_available():
                self._torch.cuda.manual_seed_all(call_seed)

        with self._torch.inference_mode():
            out = model.generate(**inputs, **gen_kwargs)
        gen = out[0][inputs["input_ids"].shape[1] :]
        return tokenizer.decode(gen, skip_special_tokens=True)

    async def rate(self, request: RateRequest) -> RateResult:
        # One generation at a time on the GPU; concurrent calls would OOM
        # or thrash the single MIG slice.
        async with self._lock:
            try:
                text = await asyncio.to_thread(
                    self._generate_sync, request.model, request.profile, request.seed
                )
            except Exception as e:  # noqa: BLE001
                return RateResult(
                    text=f"<error: {type(e).__name__}: {e}>",
                    rating=None,
                    backend=self.name,
                    thinking=self._thinking,
                )
        cleaned = strip_thinking(text) if self._thinking else text
        return RateResult(
            text=cleaned,
            rating=parse_rating(cleaned),
            backend=self.name,
            thinking=self._thinking,
        )

    async def aclose(self) -> None:
        self._models.clear()
        if self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()
