from __future__ import annotations

import http.client
import json
import time
from typing import Any
import traceback
import requests


class NebuisLLM:
    def __init__(self, host, key, model, timeout=60, **kwargs):
        """Https API
        Args:
            host   : host name. please note that the host name does not include 'https://'
            key    : API key.
            model  : LLM model name.
            timeout: API timeout.
        """

        self._host = host
        self._key = key
        self._model = model
        self._timeout = timeout
        self._kwargs = kwargs
        self._cumulative_error = 0

    def draw_samples(self, prompts: list[str | Any], *args, **kwargs) -> list[str]:
        """
        Args:
            prompts: list of prompts.
            Returns:
                list of responses.
        """
        return [self.draw_sample(prompt, *args, **kwargs) for prompt in prompts]

    def draw_sample(self, prompt: str | Any, *args, **kwargs) -> str:
        """
        Args:
            prompt: prompt.
        Returns:
            response.
        """
        if not self.api_key:
            return None, "API key not configured", {}

        if isinstance(prompt, str):
            prompt = [{'role': 'user', 'content': prompt.strip()}]

        while True:
            try:
                url = f"{self._host}/chat/completions"
                payload = {
                    "model": self._model,
                    "messages": prompt,
                    "max_tokens": self._kwargs.get('max_tokens', 4096),
                    "temperature": self._kwargs.get('temperature', 1.0),
                    "top_p": self._kwargs.get('top_p', None),
                    "presence_penalty": self._kwargs.get('presence_penalty', None),
                    "extra_body": {"top_k": self._kwargs.get('top_k', None)},
                }
                headers = {
                    'Authorization': f'Bearer {self._key}',
                    'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
                    'Content-Type': 'application/json'
                }
                response = requests.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    result = response.json()
                    result_response = result["choices"][0]["message"]["content"].strip()
                    if self.debug_mode:
                        self._cumulative_error = 0
                    return result_response
            except Exception as e:
                self._cumulative_error += 1
                if self.debug_mode:
                    if self._cumulative_error == 10:
                        raise RuntimeError(f'{self.__class__.__name__} error: {traceback.format_exc()}.'
                                           f'You may check your API host and API key.')
                else:
                    print(f'{self.__class__.__name__} error: {traceback.format_exc()}.'
                          f'You may check your API host and API key.')
                    time.sleep(2)
                continue