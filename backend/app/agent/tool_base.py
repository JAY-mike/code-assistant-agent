"""工具基类：所有 Agent 工具都继承这个"""

from abc import ABC , abstractmethod

class Tool(ABC):
    name :str = ""
    description: str =""
    parameters : dict = {}

    @abstractmethod
    def execute(self , **kwargs) -> str:
        """执行工具 ， 返回文本结果"""
        pass

