from __future__ import annotations


class AssistantDraftCatalog:
    """Resolve rascunhos por ID sem misturar seus serviços de domínio."""

    def __init__(self, *services) -> None:
        self._services = tuple(service for service in services if service is not None)
        if not self._services:
            raise ValueError("Ao menos um serviço de rascunhos é obrigatório.")

    def get(self, draft_id: str):
        found = []
        for service in self._services:
            try:
                found.append(service.get(draft_id))
            except ValueError:
                continue
        if not found:
            raise ValueError("Rascunho não encontrado ou descartado.")
        if len(found) > 1:
            raise RuntimeError("Identificador de rascunho ambíguo.")
        return found[0]
