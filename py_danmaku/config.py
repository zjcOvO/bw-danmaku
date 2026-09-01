import os
import yaml
from pathlib import Path


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._config = {}
        self._load_config()

    def _load_config(self):
        config_path = Path(__file__).parent.parent / "config.yaml"
        if not config_path.exists():
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = {}

    @property
    def onebot(self):
        return self._config.get("onebot", {})

    @property
    def qqbot(self):
        return self._config.get("qqbot", {})

    @property
    def bilibili(self):
        return self._config.get("bilibili", {})

    @property
    def manual(self):
        return self._config.get("manual", {})

    @property
    def display(self):
        return self._config.get("display", {})
