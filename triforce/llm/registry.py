"""Model registry — loads models.yaml and adapter manifests."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from triforce.llm.errors import PolicyError
from triforce.llm.types import Adapter, Model

logger = logging.getLogger(__name__)

DEFAULT_MODELS_YAML = Path(__file__).parent / "models.yaml"
DEFAULT_ADAPTERS_DIR = Path(__file__).parent / "adapters"


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise PolicyError(
            "pyyaml is required to load the model registry. "
            "Install with: pip install pyyaml"
        ) from exc
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class Registry:
    """Loads and exposes the model + adapter registry.

    Construction is cheap; the registry holds frozen dataclasses in memory.
    """

    def __init__(
        self,
        models_path: Optional[Path] = None,
        adapters_dir: Optional[Path] = None,
    ) -> None:
        self._models_path = models_path or DEFAULT_MODELS_YAML
        self._adapters_dir = adapters_dir or DEFAULT_ADAPTERS_DIR
        self._models: dict[str, Model] = {}
        self._adapters: dict[str, Adapter] = {}
        self._loaded = False

    def load(self) -> None:
        """Read models.yaml and adapter manifests into memory."""
        if self._loaded:
            return

        data = _load_yaml(self._models_path)
        models_list = data.get("models", [])
        if not isinstance(models_list, list):
            raise PolicyError(
                f"{self._models_path}: 'models' must be a list, got {type(models_list).__name__}"
            )

        for entry in models_list:
            model = Model(
                id=entry["id"],
                provider=entry["provider"],
                base_id=entry["base_id"],
                capabilities=frozenset(entry.get("capabilities", [])),
                context_window=int(entry.get("context_window", 8_000)),
                p95_latency_ms=int(entry.get("p95_latency_ms", 1_000)),
                cost_per_1k_tokens_usd=float(entry.get("cost_per_1k_tokens_usd", 0.0)),
                is_local=bool(entry.get("is_local", False)),
                supports_tools=bool(entry.get("supports_tools", True)),
                supports_vision=bool(entry.get("supports_vision", False)),
                tags=frozenset(entry.get("tags", [])),
            )
            if model.id in self._models:
                raise PolicyError(f"Duplicate model id in registry: {model.id}")
            self._models[model.id] = model

        self._load_adapters()
        self._loaded = True
        logger.info(
            "Registry loaded: %d models, %d adapters",
            len(self._models),
            len(self._adapters),
        )

    def _load_adapters(self) -> None:
        manifest = self._adapters_dir / "manifest.yaml"
        if not manifest.exists():
            return
        data = _load_yaml(manifest)
        for entry in data.get("adapters", []):
            adapter = Adapter(
                id=entry["id"],
                base_model_id=entry["base_model_id"],
                task_tags=frozenset(entry.get("task_tags", [])),
                path=entry.get("path", ""),
                eval_score=entry.get("eval_score"),
                description=entry.get("description", ""),
            )
            self._adapters[adapter.id] = adapter

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def all_models(self) -> list[Model]:
        self.load()
        return list(self._models.values())

    def get(self, model_id: str) -> Optional[Model]:
        self.load()
        return self._models.get(model_id)

    def find_adapters_for(self, model_id: str, task_type: str) -> list[Adapter]:
        """Return adapters whose base model matches and whose task_tags include task_type."""
        self.load()
        return [
            a
            for a in self._adapters.values()
            if a.base_model_id == model_id and task_type in a.task_tags
        ]

    def candidates(
        self,
        is_local_allowed: bool = True,
        is_cloud_allowed: bool = True,
        requires_tools: bool = False,
        requires_vision: bool = False,
    ) -> list[Model]:
        """Pre-filter models by hard constraints. Returns ordered by latency."""
        self.load()
        out: list[Model] = []
        for m in self._models.values():
            if m.is_local and not is_local_allowed:
                continue
            if (not m.is_local) and not is_cloud_allowed:
                continue
            if requires_tools and not m.supports_tools:
                continue
            if requires_vision and not m.supports_vision:
                continue
            out.append(m)
        return sorted(out, key=lambda m: m.p95_latency_ms)


# Module-level singleton for cheap access
_REGISTRY: Optional[Registry] = None


def get_registry() -> Registry:
    """Return the process-wide Registry, lazy-initialized."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = Registry()
        _REGISTRY.load()
    return _REGISTRY
