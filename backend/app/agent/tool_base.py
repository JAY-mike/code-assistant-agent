"""Base class and schemas for allow-listed Agent tools."""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class Tool(ABC):
    name: str = ""
    description: str = ""
    args_model: type[BaseModel] | None = None

    def function_schema(self) -> dict:
        """Return the OpenAI-compatible function schema exposed to the model."""
        if self.args_model is None:
            raise ValueError(f"Tool '{self.name}' must define an args_model")

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }

    def validate_args(self, args: dict) -> dict:
        """Validate untrusted model arguments before a tool is executed."""
        if self.args_model is None:
            raise ValueError(f"Tool '{self.name}' must define an args_model")
        return self.args_model.model_validate(args).model_dump()

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool and return a text observation."""
        pass
