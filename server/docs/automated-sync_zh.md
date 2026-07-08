# Wiki 自动同步指南

当 LLM Wiki 能够持续反映您的背景笔记系统时，管理效果最佳。无需每次编写新内容时手动摄取文件，您可以编排一个端到端的自动化流水线。

本指南概述了适用于本地 Mac/Linux 环境的生产级 cron/launchd 策略。

## 两步架构

LLM Wiki Agent 的摄取是一个两步过程：
1. **同步到 `raw/`**：将文件从您的个人库/工具获取到知识库的原始文件区。
2. **批量摄取**：在 `server/` 目录下通过 `python -m wiki_engine update` 增量更新知识库。

### 步骤 1：主编排脚本

在您的 wiki 项目 `server/` 目录创建一个 shell 脚本（`daily-automated-sync.sh`）：

```bash
#!/usr/bin/env bash
set -uo pipefail

# 定义变量
LAB_DIR="$HOME/projects/active/personal-wiki-lab"
SERVER_DIR="$LAB_DIR/server"
LOG_FILE="$LAB_DIR/automation-cron.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")
KB_ID=1
SOURCE_DIR="$LAB_DIR/raw"

echo "=====================================================" >> "$LOG_FILE"
echo "[$DATE] 开始自动 wiki 同步..." >> "$LOG_FILE"

cd "$SERVER_DIR" || exit 1

# 1. 在此运行您的个人 Vault-to-Raw 同步脚本
# 示例: "$LAB_DIR/sync-raw.sh" >> "$LOG_FILE" 2>&1

# 2. 增量更新知识库（导入 raw/ 并摄入新文件）
export LLM_MODEL="gemini/gemini-3-flash-preview"
export GEMINI_API_KEY="AIzaSy..."  # 或 export OPENAI_API_KEY

echo "[$DATE] 增量更新知识库 (kb_id=$KB_ID)..." >> "$LOG_FILE"
python -m wiki_engine update --kb-id "$KB_ID" --source "$SOURCE_DIR" >> "$LOG_FILE" 2>&1

# 3. 图谱自愈（补全缺失实体页面）
echo "[$DATE] 图谱自愈..." >> "$LOG_FILE"
python -m wiki_engine heal --kb-id "$KB_ID" >> "$LOG_FILE" 2>&1

echo "[$(date "+%Y-%m-%d %H:%M:%S")] 自动同步完成。" >> "$LOG_FILE"
echo "=====================================================" >> "$LOG_FILE"
```

不要忘记使其可执行：`chmod +x daily-automated-sync.sh`。

### 步骤 2：系统调度器（macOS launchd）

对于 macOS，`launchd` 比 `cron` 更加健壮。

在 `~/Library/LaunchAgents/com.personal-wiki-sync.plist` 创建一个 `.plist` 文件：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.personal-wiki-sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/your-username/projects/active/personal-wiki-lab/daily-automated-sync.sh</string>
    </array>
    
    <!-- 每天凌晨 2:00 自动执行 -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <!-- 如果错过了时间间隔，在系统启动时运行 -->
    <key>RunAtLoad</key>
    <true/>

    <!-- 诊断日志 -->
    <key>StandardOutPath</key>
    <string>/Users/your-username/projects/active/personal-wiki-lab/daemon.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/your-username/projects/active/personal-wiki-lab/daemon.stderr.log</string>
</dict>
</plist>
```

加载守护进程：
```bash
launchctl load ~/Library/LaunchAgents/com.personal-wiki-sync.plist
```

### 自我修复与健康监控
由于自动化在夜间静默运行，您的 `daemon.stderr.log` 确保您能够发现任何 API 失败。编排脚本包含 `python -m wiki_engine heal`（或 `python -m tools.heal`），强烈建议使用：它将无缝拦截并构建您一天中积累但从未单独形式化的概念。