#!/usr/bin/env python3
"""
LLM Chat Interactive CLI

A command-line chat interface for OpenAI-API-compatible LLM services.

Usage:
    python test/llm_chat.py
    python test/llm_chat.py --url http://192.168.226.117:1040 --model qwen3
    python test/llm_chat.py --stream  # Enable streaming output
    python test/llm_chat.py --no-stream  # Disable streaming output
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')
import argparse
from typing import Optional, List, Dict

from tools.logger import get_logger, setup_logging

logger = get_logger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass


import os

DEFAULT_URL = os.getenv("OPENAI_API_BASE", "http://192.168.226.117:1040/v1")
DEFAULT_MODEL = f"{os.getenv('LLM_MODEL', 'openai/qwen3')}"


def parse_args():
    parser = argparse.ArgumentParser(description="LLM Chat Interactive CLI")
    parser.add_argument("--url", default=DEFAULT_URL, help="LLM service URL (with /v1 suffix)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name (with provider prefix like openai/)")
    parser.add_argument("--api-key", default=None, help="API key (optional)")
    parser.add_argument("--stream", action="store_true", default=True, help="Enable streaming output (default)")
    parser.add_argument("--think", action="store_true", default=False, help="Enable thinking mode (instruct LLM to output <think> tags)")
    parser.add_argument("--system-prompt", default="You are a helpful assistant.", help="System prompt")
    return parser.parse_args()


def build_system_prompt(base_prompt: str, think: bool) -> str:
    """Build system prompt with thinking mode instruction."""
    if think:
        return f"{base_prompt}\n\nUse thinking mode: Before answering, write your reasoning inside <think> tags. Example: <think>Let me analyze this problem...</think>Your answer here."
    else:
        return f"{base_prompt}\n\nDo not use thinking mode. Provide direct answers without <think> tags."


def chat_completion_stream(
    url: str,
    model: str,
    messages: List[Dict[str, str]],
    api_key: Optional[str] = None,
    think: bool = False
) -> str:
    """Stream chat completion response."""
    from litellm import completion
    
    kwargs = {
        "model": model,
        "messages": messages,
        "api_base": url,
        "max_tokens": 8192,
        "stream": True,
        "extra_body": {"enable_thinking": think},
    }
    
    if api_key:
        kwargs["api_key"] = api_key
    
    full_content = ""
    in_think_block = False
    sys.stdout.write("\nAssistant: ")
    sys.stdout.flush()
    
    try:
        response = completion(**kwargs)
        for chunk in response:
            if hasattr(chunk, 'choices') and chunk.choices:
                if hasattr(chunk.choices[0], 'delta') and chunk.choices[0].delta:
                    content = chunk.choices[0].delta.content or ""
                    full_content += content
                    
                    if think:
                        # Show everything including think tags
                        sys.stdout.write(content)
                        sys.stdout.flush()
                    else:
                        # Filter out  thinking... response blocks
                        while content:
                            if in_think_block:
                                # Inside a think block, look for closing tag
                                end_idx = content.find(' response')
                                if end_idx != -1:
                                    content = content[end_idx + 8:]
                                    in_think_block = False
                                else:
                                    # Still inside think block, discard all
                                    content = ""
                            else:
                                # Not in think block, look for opening tag
                                start_idx = content.find(' thinking')
                                if start_idx != -1:
                                    # Print everything before the tag
                                    sys.stdout.write(content[:start_idx])
                                    sys.stdout.flush()
                                    content = content[start_idx + 7:]
                                    in_think_block = True
                                else:
                                    # No think tags, print all
                                    sys.stdout.write(content)
                                    sys.stdout.flush()
                                    content = ""
        sys.stdout.write("\n")
        sys.stdout.flush()
        
        # Clean up response for history if not in think mode
        if not think:
            import re
            full_content = re.sub(r'<think>.*?</think>', '', full_content, flags=re.DOTALL)
        
        return full_content.strip()
    except Exception as e:
        logger.error("\nError during streaming: %s", e)
        return ""


def chat_completion_sync(
    url: str,
    model: str,
    messages: List[Dict[str, str]],
    api_key: Optional[str] = None,
    think: bool = False
) -> str:
    """Get chat completion response synchronously."""
    from litellm import completion
    
    kwargs = {
        "model": model,
        "messages": messages,
        "api_base": url,
        "max_tokens": 8192,
        "stream": False,
        "extra_body": {"enable_thinking": think},
    }
    
    if api_key:
        kwargs["api_key"] = api_key
    
    try:
        response = completion(**kwargs)
        content = response.choices[0].message.content
        
        # Client-side filtering as backup
        if not think:
            import re
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        logger.info("\nAssistant: %s", content.strip())
        return content.strip()
    except Exception as e:
        logger.error("\nError: %s", e)
        return ""


def main():
    args = parse_args()
    setup_logging(level="INFO")
    
    # Determine streaming mode
    streaming = args.stream
    
    # Build system prompt with thinking mode instruction
    system_prompt = build_system_prompt(args.system_prompt, args.think)
    
    logger.info("=" * 60)
    logger.info("LLM Chat Interactive CLI")
    logger.info("=" * 60)
    logger.info("URL: %s", args.url)
    logger.info("Model: %s", args.model)
    logger.info("Streaming: %s", 'Enabled' if streaming else 'Disabled')
    logger.info("Thinking Mode: %s", 'Enabled' if args.think else 'Disabled')
    logger.info("=" * 60)
    logger.info("Type 'exit' or 'quit' to exit")
    logger.info("Type 'clear' to clear history")
    logger.info("=" * 60)
    
    # Initialize conversation history
    messages = [{"role": "system", "content": system_prompt}]
    
    try:
        while True:
            user_input = input("\nYou: ").strip()
            
            if user_input.lower() in ["exit", "quit"]:
                logger.info("Goodbye!")
                break
            
            if user_input.lower() == "clear":
                messages = [{"role": "system", "content": system_prompt}]
                logger.info("History cleared!")
                continue
            
            if not user_input:
                continue
            
            # Add user message to history
            messages.append({"role": "user", "content": user_input})
            
            # Generate response
            if streaming:
                response = chat_completion_stream(args.url, args.model, messages, args.api_key, args.think)
            else:
                response = chat_completion_sync(args.url, args.model, messages, args.api_key, args.think)
            
            # Add assistant response to history
            if response:
                messages.append({"role": "assistant", "content": response})
                
    except KeyboardInterrupt:
        logger.info("\n\nGoodbye!")


if __name__ == "__main__":
    main()