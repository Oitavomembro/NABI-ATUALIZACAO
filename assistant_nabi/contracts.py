from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable
from uuid import uuid4


class CapabilityLevel(IntEnum):
    CONVERSATION = 0
    READ = 1
    DRAFT = 2
    SIMPLE_CONFIRMATION = 3
    REINFORCED_CONFIRMATION = 4
    RESTRICTED = 5


class ToolKind(StrEnum):
    READ = "READ"
    DRAFT = "DRAFT"
    MUTATION = "MUTATION"


class ParameterType(StrEnum):
    TEXT = "TEXT"
    INTEGER = "INTEGER"
    DECIMAL_TEXT = "DECIMAL_TEXT"
    BOOLEAN = "BOOLEAN"


def _required_text(value: object, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} é obrigatório.")
    return normalized


def _immutable_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _immutable_value(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_immutable_value(item) for item in value)
    if isinstance(value, (str, int, bool, type(None))):
        return value
    raise TypeError("Ferramentas aceitam somente dados estruturados simples.")


def _immutable_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise TypeError("Os parâmetros da ferramenta devem formar um mapeamento.")
    return _immutable_value(value)


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    name: str
    parameter_type: ParameterType
    required: bool = False
    max_length: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_text(self.name, "Parâmetro"))
        parameter_type = (
            self.parameter_type
            if isinstance(self.parameter_type, ParameterType)
            else ParameterType(self.parameter_type)
        )
        object.__setattr__(self, "parameter_type", parameter_type)
        if self.max_length is not None and int(self.max_length) <= 0:
            raise ValueError("O tamanho máximo deve ser positivo.")
        if self.max_length is not None and parameter_type is not ParameterType.TEXT:
            raise ValueError("Tamanho máximo só pode ser usado em parâmetros de texto.")

    def validate(self, value: Any) -> None:
        if self.parameter_type is ParameterType.TEXT:
            if not isinstance(value, str):
                raise ValueError(f"O parâmetro {self.name} deve ser texto.")
            if self.max_length is not None and len(value) > self.max_length:
                raise ValueError(f"O parâmetro {self.name} excede o tamanho permitido.")
            return
        if self.parameter_type is ParameterType.INTEGER:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"O parâmetro {self.name} deve ser inteiro.")
            return
        if self.parameter_type is ParameterType.BOOLEAN:
            if not isinstance(value, bool):
                raise ValueError(f"O parâmetro {self.name} deve ser booleano.")
            return
        if not isinstance(value, str):
            raise ValueError(f"O parâmetro {self.name} deve ser decimal em texto.")
        try:
            from decimal import Decimal, InvalidOperation

            parsed = Decimal(value.strip().replace(",", "."))
        except (InvalidOperation, ValueError):
            parsed = None
        if parsed is None or not parsed.is_finite():
            raise ValueError(f"O parâmetro {self.name} deve ser decimal válido.")


@dataclass(frozen=True, slots=True)
class ToolSchema:
    parameters: tuple[ParameterDefinition, ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(self.parameters)
        if any(not isinstance(item, ParameterDefinition) for item in normalized):
            raise TypeError("Schema aceita somente definições de parâmetro.")
        names = [item.name for item in normalized]
        if len(names) != len(set(names)):
            raise ValueError("O schema possui parâmetros duplicados.")
        object.__setattr__(self, "parameters", normalized)

    def validate(self, values: Mapping[str, Any]) -> None:
        allowed = {item.name: item for item in self.parameters}
        unknown = sorted(set(values) - set(allowed))
        if unknown:
            raise ValueError(f"Parâmetro não permitido: {unknown[0]}.")
        missing = sorted(
            item.name for item in self.parameters if item.required and item.name not in values
        )
        if missing:
            raise ValueError(f"Parâmetro obrigatório ausente: {missing[0]}.")
        for name, value in values.items():
            allowed[name].validate(value)


@dataclass(frozen=True, slots=True)
class AssistantActor:
    username: str
    profile: str
    session_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "username", _required_text(self.username, "Usuário"))
        object.__setattr__(self, "profile", _required_text(self.profile, "Perfil").upper())
        object.__setattr__(self, "session_id", _required_text(self.session_id, "Sessão"))


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    kind: ToolKind
    capability: CapabilityLevel
    permission_module: str
    permission_action: str = "view"
    schema: ToolSchema = field(default_factory=ToolSchema)

    def __post_init__(self) -> None:
        name = _required_text(self.name, "Nome da ferramenta")
        kind = self.kind if isinstance(self.kind, ToolKind) else ToolKind(self.kind)
        capability = (
            self.capability
            if isinstance(self.capability, CapabilityLevel)
            else CapabilityLevel(self.capability)
        )
        if kind is ToolKind.READ and capability is not CapabilityLevel.READ:
            raise ValueError("Ferramenta de leitura deve possuir capacidade READ.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "capability", capability)
        object.__setattr__(
            self, "permission_module", _required_text(self.permission_module, "Módulo")
        )
        object.__setattr__(
            self, "permission_action", _required_text(self.permission_action, "Permissão")
        )
        if not isinstance(self.schema, ToolSchema):
            raise TypeError("Schema da ferramenta inválido.")


@dataclass(frozen=True, slots=True)
class ToolRequest:
    tool_name: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_name", _required_text(self.tool_name, "Ferramenta"))
        object.__setattr__(self, "request_id", _required_text(self.request_id, "Requisição"))
        object.__setattr__(self, "parameters", _immutable_mapping(self.parameters))


@dataclass(frozen=True, slots=True)
class ToolResult:
    request_id: str
    tool_name: str
    success: bool
    payload: Mapping[str, Any] = field(default_factory=dict)
    message: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _required_text(self.request_id, "Requisição"))
        object.__setattr__(self, "tool_name", _required_text(self.tool_name, "Ferramenta"))
        object.__setattr__(self, "payload", _immutable_mapping(self.payload))
        object.__setattr__(self, "message", str(self.message or "").strip())


@dataclass(frozen=True, slots=True)
class ModelReply:
    """Saída estruturada não confiável produzida por um provedor de linguagem."""

    message: str
    tool_requests: tuple[ToolRequest, ...] = ()

    def __post_init__(self) -> None:
        message = str(self.message or "").strip()
        requests = tuple(self.tool_requests)
        if any(not isinstance(request, ToolRequest) for request in requests):
            raise TypeError("O modelo retornou uma requisição de ferramenta inválida.")
        if not message and not requests:
            raise ValueError("O modelo retornou uma resposta vazia.")
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "tool_requests", requests)


@dataclass(frozen=True, slots=True)
class AssistantTurn:
    message: str
    tool_results: tuple[ToolResult, ...] = ()
    safe_failure: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "message", str(self.message or "").strip())
        results = tuple(self.tool_results)
        if any(not isinstance(result, ToolResult) for result in results):
            raise TypeError("O turno contém resultado de ferramenta inválido.")
        object.__setattr__(self, "tool_results", results)


@runtime_checkable
class PermissionPort(Protocol):
    def allows(self, actor: AssistantActor, module: str, action: str) -> bool: ...


@runtime_checkable
class ReadToolPort(Protocol):
    def execute(self, request: ToolRequest, *, actor: AssistantActor) -> Mapping[str, Any]: ...


@runtime_checkable
class AssistantAuditPort(Protocol):
    def record(
        self,
        *,
        actor: AssistantActor,
        request: ToolRequest,
        result: ToolResult,
    ) -> None: ...


@runtime_checkable
class LanguageModelPort(Protocol):
    """Porta futura: nenhum SDK de modelo pertence ao núcleo da Nabi."""

    def respond(
        self, message: str, *, available_tools: tuple[ToolDefinition, ...]
    ) -> ModelReply: ...
