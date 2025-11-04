from abc import ABC, abstractmethod
from typing import Dict

class BaseModel(ABC):
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        pass

class BaseStrategy(ABC):
    @abstractmethod
    def format_prompt(self, input_data: Dict) -> str:
        pass

    @abstractmethod
    def post_process(self, output: str) -> str:
        pass