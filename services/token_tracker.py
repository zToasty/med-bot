"""
Счётчик токенов и стоимости для всего бота.
Используется как singleton — импортируй tracker из любого модуля.

Цены (март 2025, OpenAI):
  - text-embedding-3-small: $0.02  / 1M токенов
  - gpt-4o-mini input:       $0.15  / 1M токенов
  - gpt-4o-mini output:      $0.60  / 1M токенов
  - gpt-4o input:            $2.50  / 1M токенов
  - gpt-4o output:           $10.00 / 1M токенов
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Стоимость за 1M токенов в долларах
PRICING: dict[str, dict[str, float]] = {
    "text-embedding-3-small": {"input": 0.02,  "output": 0.0},
    "text-embedding-3-large": {"input": 0.13,  "output": 0.0},
    "gpt-4o-mini":            {"input": 0.15,  "output": 0.60},
    "gpt-4o":                 {"input": 2.50,  "output": 10.00},
}


@dataclass
class ModelStats:
    input_tokens:  int   = 0
    output_tokens: int   = 0
    requests:      int   = 0
    cost_usd:      float = 0.0


@dataclass
class TokenTracker:
    stats:      dict[str, ModelStats] = field(default_factory=dict)
    started_at: datetime              = field(default_factory=datetime.now)

    def _get_or_create(self, model: str) -> ModelStats:
        if model not in self.stats:
            self.stats[model] = ModelStats()
        return self.stats[model]

    def add_embedding(self, model: str, input_tokens: int) -> None:
        """Записывает использование эмбеддингов."""
        s = self._get_or_create(model)
        s.input_tokens += input_tokens
        s.requests     += 1

        price = PRICING.get(model, {}).get("input", 0.0)
        s.cost_usd += (input_tokens / 1_000_000) * price

        logger.debug(f"[tokens] embedding {model}: +{input_tokens} tokens")

    def add_chat(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Записывает использование chat completion."""
        s = self._get_or_create(model)
        s.input_tokens  += input_tokens
        s.output_tokens += output_tokens
        s.requests      += 1

        p = PRICING.get(model, {"input": 0.0, "output": 0.0})
        s.cost_usd += (input_tokens  / 1_000_000) * p["input"]
        s.cost_usd += (output_tokens / 1_000_000) * p["output"]

        logger.debug(f"[tokens] chat {model}: +{input_tokens} in / +{output_tokens} out")

    def summary(self) -> str:
        """Возвращает читаемый отчёт по всем моделям."""
        if not self.stats:
            return "📊 Токены ещё не использовались."

        uptime  = datetime.now() - self.started_at
        hours   = int(uptime.total_seconds() // 3600)
        minutes = int((uptime.total_seconds() % 3600) // 60)

        lines = [
            f"📊 <b>Статистика токенов</b>",
            f"🕐 Работаю: {hours}ч {minutes}мин",
            "",
        ]

        total_cost = 0.0
        for model, s in self.stats.items():
            total_tokens = s.input_tokens + s.output_tokens
            total_cost  += s.cost_usd
            lines += [
                f"<b>{model}</b>",
                f"  запросов:  {s.requests:,}",
                f"  входящих:  {s.input_tokens:,}",
                f"  исходящих: {s.output_tokens:,}",
                f"  итого:     {total_tokens:,}",
                f"  стоимость: ${s.cost_usd:.4f}",
                "",
            ]

        lines.append(f"💰 <b>Итого: ${total_cost:.4f}</b>")
        return "\n".join(lines)

    def reset(self) -> None:
        """Сбрасывает все счётчики."""
        self.stats      = {}
        self.started_at = datetime.now()
        logger.info("[tokens] Счётчики сброшены.")


# Singleton — импортируй этот объект везде
tracker = TokenTracker()