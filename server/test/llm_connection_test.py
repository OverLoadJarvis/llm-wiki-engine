#!/usr/bin/env python3
"""
LLM Service Connection Test Module

Tests connectivity and basic functionality of OpenAI-API-compatible LLM services.

Usage:
    python test/llm_connection_test.py
    python test/llm_connection_test.py --url http://192.168.226.117:1040
    python test/llm_connection_test.py --model gpt-4o-mini --verbose
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import argparse
import time
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from tools.logger import get_logger, setup_logging

logger = get_logger(__name__)


DEFAULT_URL = "http://192.168.226.117:1040"
DEFAULT_MODEL = "qwen3"


def parse_args():
    parser = argparse.ArgumentParser(description="Test LLM service connection")
    parser.add_argument("--url", default=DEFAULT_URL, help="LLM service URL")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name")
    parser.add_argument("--api-key", default=None, help="API key (optional)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    return parser.parse_args()


def test_connection(url: str, model: str, api_key: Optional[str] = None, verbose: bool = False) -> dict:
    """Test basic HTTP connectivity to the LLM service."""
    logger.info("\n%s", "=" * 60)
    logger.info("Test 1: Connection Test")
    logger.info("%s", "=" * 60)
    logger.info("URL: %s", url)

    try:
        import requests
        start_time = time.time()
        response = requests.get(f"{url.rstrip('/')}/v1/models", timeout=10)
        elapsed = time.time() - start_time

        if verbose:
            logger.info("Status Code: %s", response.status_code)
            logger.info("Response Time: %.3fs", elapsed)
            logger.info("Response: %s", response.text[:500])

        if response.status_code == 200:
            logger.info("✓ Connection successful!")
            return {"success": True, "elapsed": elapsed, "status_code": response.status_code}
        else:
            logger.error("✗ Connection failed with status code: %s", response.status_code)
            return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        logger.error("✗ Connection failed: %s", e)
        return {"success": False, "error": str(e)}


def test_chat_completion(url: str, model: str, api_key: Optional[str] = None, verbose: bool = False) -> dict:
    """Test chat completion with a simple prompt."""
    logger.info("\n%s", "=" * 60)
    logger.info("Test 2: Chat Completion Test")
    logger.info("%s", "=" * 60)

    try:
        from litellm import completion
    except ImportError:
        logger.error("✗ litellm not installed")
        return {"success": False, "error": "litellm not installed"}

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say 'Hello, LLM service is working!' in a friendly manner."}
    ]

    kwargs = {
        "model": f"openai/{model}",
        "messages": messages,
        "api_base": f"{url}/v1",
        "max_tokens": 8192,
    }

    if api_key:
        kwargs["api_key"] = api_key

    if verbose:
        logger.info("Model: %s", model)
        logger.info("Messages: %s", json.dumps(messages, ensure_ascii=False, indent=2))

    try:
        start_time = time.time()
        response = completion(**kwargs)
        elapsed = time.time() - start_time

        if verbose:
            logger.info("Response Time: %.3fs", elapsed)
            logger.info("Full Response: %s", response)

        content = response.choices[0].message.content
        logger.info("✓ Chat completion successful!")
        logger.info("  Response: %s", content)
        logger.info("  Time: %.3fs", elapsed)

        return {
            "success": True,
            "elapsed": elapsed,
            "response": content,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            } if hasattr(response, 'usage') and response.usage else None
        }
    except Exception as e:
        logger.error("✗ Chat completion failed: %s", e)
        return {"success": False, "error": str(e)}


def test_streaming(url: str, model: str, api_key: Optional[str] = None, verbose: bool = False) -> dict:
    """Test streaming chat completion."""
    logger.info("\n%s", "=" * 60)
    logger.info("Test 3: Streaming Test")
    logger.info("%s", "=" * 60)

    try:
        from litellm import completion
    except ImportError:
        logger.error("✗ litellm not installed")
        return {"success": False, "error": "litellm not installed"}

    messages = [
        {"role": "user", "content": "Count from 1 to 5, one number per line."}
    ]

    kwargs = {
        "model": f"openai/{model}",
        "messages": messages,
        "api_base": f"{url}/v1",
        "max_tokens": 50,
        "stream": True,
    }

    if api_key:
        kwargs["api_key"] = api_key

    if verbose:
        logger.info("Model: %s", model)
        logger.info("Messages: %s", json.dumps(messages, ensure_ascii=False, indent=2))

    try:
        start_time = time.time()
        response = completion(**kwargs)

        full_content = ""
        chunk_count = 0
        for chunk in response:
            chunk_count += 1
            if hasattr(chunk, 'choices') and chunk.choices:
                if hasattr(chunk.choices[0], 'delta') and chunk.choices[0].delta:
                    content = chunk.choices[0].delta.content or ""
                    full_content += content
                    if verbose:
                        sys.stdout.write(f"  Chunk {chunk_count}: {content}")
                        sys.stdout.flush()

        elapsed = time.time() - start_time

        if verbose:
            sys.stdout.write("\n")
            sys.stdout.flush()

        logger.info("✓ Streaming successful!")
        logger.info("  Chunks received: %d", chunk_count)
        logger.info("  Full response: %s", full_content)
        logger.info("  Time: %.3fs", elapsed)

        return {
            "success": True,
            "elapsed": elapsed,
            "chunk_count": chunk_count,
            "response": full_content
        }
    except Exception as e:
        logger.error("✗ Streaming failed: %s", e)
        return {"success": False, "error": str(e)}


def test_embedding(url: str, model: str, api_key: Optional[str] = None, verbose: bool = False) -> dict:
    """Test embedding generation."""
    logger.info("\n%s", "=" * 60)
    logger.info("Test 4: Embedding Test")
    logger.info("%s", "=" * 60)

    try:
        from litellm import embedding
    except ImportError:
        logger.error("✗ litellm not installed, skipping embedding test")
        return {"success": False, "error": "litellm not installed"}

    kwargs = {
        "model": f"openai/{model}",
        "input": "This is a test sentence for embedding.",
        "api_base": f"{url}/v1",
    }

    if api_key:
        kwargs["api_key"] = api_key

    if verbose:
        logger.info("Model: %s", model)

    try:
        start_time = time.time()
        response = embedding(**kwargs)
        elapsed = time.time() - start_time

        if verbose:
            logger.info("Response Time: %.3fs", elapsed)
            logger.info("Full Response: %s", response)

        embedding_data = response.data[0].get("embedding", []) if hasattr(response, 'data') and response.data else []
        dimensions = len(embedding_data)

        logger.info("✓ Embedding successful!")
        logger.info("  Dimensions: %d", dimensions)
        logger.info("  Time: %.3fs", elapsed)

        return {
            "success": True,
            "elapsed": elapsed,
            "dimensions": dimensions,
        }
    except Exception as e:
        if "404" in str(e):
            logger.warning("~ Embedding endpoint not available on this server (404)")
            return {"success": None, "error": "Embedding endpoint not available (404)"}
        logger.error("✗ Embedding failed: %s", e)
        return {"success": False, "error": str(e)}


def main():
    args = parse_args()

    setup_logging(level="INFO")

    logger.info("\n" + "=" * 60)
    logger.info("LLM Service Connection Test")
    logger.info("=" * 60)
    logger.info("Target: %s", args.url)
    logger.info("Model: %s", args.model)
    logger.info("Verbose: %s", args.verbose)

    results = {}

    result1 = test_connection(args.url, args.model, args.api_key, args.verbose)
    results["connection"] = result1

    if result1.get("success"):
        result2 = test_chat_completion(args.url, args.model, args.api_key, args.verbose)
        results["chat_completion"] = result2

        result3 = test_streaming(args.url, args.model, args.api_key, args.verbose)
        results["streaming"] = result3

        result4 = test_embedding(args.url, args.model, args.api_key, args.verbose)
        results["embedding"] = result4

    logger.info("\n%s", "=" * 60)
    logger.info("Summary")
    logger.info("%s", "=" * 60)

    passed = sum(1 for r in results.values() if r.get("success") is True)
    skipped = sum(1 for r in results.values() if r.get("success") is None)
    failed = sum(1 for r in results.values() if r.get("success") is False)
    total = len(results)

    logger.info("Tests passed: %d/%d (%d skipped)", passed, total, skipped)

    for test_name, result in results.items():
        success = result.get("success")
        if success is True:
            status = "✓ PASS"
        elif success is None:
            status = "~ SKIP"
        else:
            status = "✗ FAIL"
        logger.info("  %s: %s", test_name, status)
        if success is False and args.verbose:
            logger.info("    Error: %s", result.get('error'))
        elif success is None:
            logger.info("    Note: %s", result.get('error'))

    if failed == 0:
        if skipped > 0:
            logger.info("\n✓ All critical tests passed (%d optional test(s) skipped)!", skipped)
        else:
            logger.info("\n✓ All tests passed!")
        return 0
    else:
        logger.error("\n✗ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
