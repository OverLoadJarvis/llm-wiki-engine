"""
测试 tools/utils.py 中的 call_llm_stream 函数 - 流式输出测试
"""
import sys
import time
from pathlib import Path

# 确保能导入 tools/utils.py
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.utils import call_llm_stream
from tools.logger import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

prompt = "请用中文写一首关于春天的五言绝句，并逐句解释其含义。"

logger.info("===== 开始测试 call_llm_stream 流式输出 =====")
logger.info("Prompt: %s", prompt)
logger.info("-" * 50)

collected = []
print("流式输出内容：", end="\n\n")
start_time = time.time()

try:
    for chunk in call_llm_stream(prompt, max_tokens=512):
        print(chunk, end="", flush=True)
        collected.append(chunk)
except SystemExit as e:
    logger.error("call_llm_stream 内部退出 (code=%s)，请确认 litellm 已安装: pip install litellm", e.code)
    sys.exit(1)
except Exception as e:
    logger.error("流式调用异常: %s", e)
    sys.exit(1)

elapsed = time.time() - start_time
full_text = "".join(collected)

print("\n\n" + "-" * 50)
logger.info("===== 流式输出测试完成 =====")
logger.info("总耗时: %.2f 秒", elapsed)
logger.info("总字符数: %d", len(full_text))
logger.info("接收块数: %d", len(collected))
logger.info("测试结果: 通过")

