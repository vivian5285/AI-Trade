from dataclasses import dataclass
from typing import Dict, Any
import os
from dotenv import load_dotenv

@dataclass
class BaseConfig:
    """基础配置类"""
    def __init__(self):
        load_dotenv()
        
    def get_env(self, key: str, default: Any = None) -> Any:
        """获取环境变量"""
        return os.getenv(key, default)
        
    def validate(self) -> bool:
        """验证配置是否有效"""
        raise NotImplementedError("子类必须实现此方法")
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')} 