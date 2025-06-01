# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx[http2]",
# ]
#
# [[tool.uv.index]]
# url = "https://pypi.tuna.tsinghua.edu.cn/simple"
# default = true
# ///

import os
import json
import httpx
from datetime import datetime, timedelta, timezone

# 配置参数
GITHUB_REPO = "python/cpython"
BRANCH = "main"
DAYS_AGO = 0  # 0 表示今天
MAX_PAGES = 5  # 最大分页数（每页 100 条）

def get_github_commits():
    """获取 GitHub 提交记录"""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"

    # 计算时间范围（UTC）
    now = datetime.now(timezone.utc)
    since = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=DAYS_AGO)
    until = since + timedelta(days=1)

    commits = []
    for page in range(1, MAX_PAGES + 1):
        url = f"https://api.github.com/repos/{GITHUB_REPO}/commits"
        params = {
            "sha": BRANCH,
            "per_page": 100,
            "page": page,
            "since": since.isoformat(),
            "until": until.isoformat()
        }

        response = httpx.get(url, params=params, headers=headers)
        if response.status_code != 200:
            raise Exception(f"GitHub API 错误: {response.status_code} - {response.text}")

        page_commits = response.json()
        if not page_commits:
            break
        commits.extend(page_commits)

    return commits

def generate_openai_summary(messages):
    """调用 OpenAI 生成总结"""
    prompt = f"""请用中文总结今日 Python 官方仓库 ({GITHUB_REPO}) 的提交内容，按类别归类（如：
- Bug 修复
- 功能改进
- 文档更新
- 测试用例
- 性能优化
- 代码清理
- 其他变更

用 markdown 格式输出，每个类别列出具体提交（短哈希链接到 commit），最后给出统计摘要。以下是原始提交列表：

{"\n".join(messages)}"""

    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"
        },
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 2000
        }
    )

    if response.status_code != 200:
        raise Exception(f"OpenAI API 错误: {response.status_code} - {response.text}")

    return response.json()["choices"][0]["message"]["content"]

def main():
    # 检查 API 密钥
    if not os.environ.get("OPENAI_API_KEY"):
        print("错误：请设置环境变量 OPENAI_API_KEY")
        return

    try:
        # 获取提交记录
        commits = get_github_commits()
        if not commits:
            print(f"{datetime.now().strftime('%Y-%m-%d')} 没有新提交")
            return

        # 格式化提交消息
        messages = [
            f"- [{commit['sha'][:7]}]({commit['html_url']}) "
            f"{commit['commit']['message'].split('\n')[0]}"
            for commit in commits
        ]

        # 生成总结报告
        summary = generate_openai_summary(messages)
        
        # 输出结果
        print(f"\n## Python 仓库提交日报 ({datetime.now().strftime('%Y-%m-%d')}) ##\n")
        print(summary)
        
        # 可选：保存到文件
        with open(f"cpython_summary_{datetime.now().strftime('%Y%m%d')}.md", "w") as f:
            f.write(summary)

    except Exception as e:
        print(f"运行错误: {str(e)}")

if __name__ == "__main__":
    main()