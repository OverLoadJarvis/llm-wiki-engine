#!/usr/bin/env python3
"""
LLM Simple Chat - Single API Call Module

一个简单的 LLM 对话模块，直接使用 requests 库进行单次 API 调用。
LLM 配置信息从.env 文件读取。

Usage:
    python test/llm_simple_chat.py
    python test/llm_simple_chat.py "你好"
"""

import os
import requests
from typing import Optional

from tools.logger import get_logger, setup_logging

logger = get_logger(__name__)


def load_env():
    """Load environment variables from .env file."""
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        pass


def get_llm_config():
    """Get LLM configuration from environment variables."""
    base_url = f"{os.getenv('OPENAI_API_BASE', 'http://192.9.54.10:30090/pserver/api/v1')}/chat/completions"
    # base_url = os.getenv('OPENAI_API_BASE', 'http://192.9.54.10:30090/pserver/api/v1')
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("LLM_MODEL", "openai/ctdi-DeepSeek-V4-Flash-768de1")
    
    return {
        "url": base_url,
        "api_key": api_key,
        "model": model
    }


def chat(
    message: str,
    system_prompt: Optional[str] = None,
    url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> str:
    """
    单次 LLM API 调用
    
    Args:
        message: 用户消息
        system_prompt: 系统提示词（可选）
        url: API 基础 URL（可选，默认从.env 读取）
        api_key: API 密钥（可选，默认从.env 读取）
        model: 模型名称（可选，默认从.env 读取）
    
    Returns:
        LLM 响应内容
    """
    config = get_llm_config()
    
    api_url = url or config["url"]
    token = api_key or config["api_key"]
    model_name = model or config["model"]
    
    messages = []
    
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    messages.append({"role": "user", "content": message})
    
    payload = {
        "model": model_name,
        "messages": messages
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        
        # 调试：打印完整响应
        logger.debug("\nRaw response: %s", result)
        
        # 检查是否有 error 字段
        if "error" in result:
            return f"API Error: {result['error']}"
        
        # 检查是否有 choices 字段
        if "choices" not in result:
            return f"Error: Response missing 'choices' field. Got keys: {list(result.keys())}"
        
        if not result["choices"]:
            return "Error: Empty choices array"
        
        content = result["choices"][0]["message"]["content"]
        
        return content.strip()
    
    except requests.exceptions.RequestException as e:
        return f"Error: {str(e)}"
    except (KeyError, IndexError) as e:
        return f"Error parsing response: {str(e)}"


def main():
    """命令行交互模式"""
    load_env()
    setup_logging(level="INFO")
    config = get_llm_config()
    
    logger.info("=" * 60)
    logger.info("LLM Simple Chat - 单次 API 调用")
    logger.info("=" * 60)
    logger.info("URL: %s", config['url'])
    logger.info("Model: %s", config['model'])
    logger.info("=" * 60)
    logger.info("Type 'exit' or 'quit' to exit")
    logger.info("=" * 60)
    
    try:
        while True:
            user_input = input("\nYou: ").strip()
            
            if user_input.lower() in ["exit", "quit"]:
                logger.info("Goodbye!")
                break
            
            if not user_input:
                continue
            
            response = chat(user_input)
            logger.info("\nAssistant: %s", response)
            
    except KeyboardInterrupt:
        logger.info("\n\nGoodbye!")


if __name__ == "__main__":
    main()
