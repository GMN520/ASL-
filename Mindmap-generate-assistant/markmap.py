from flask import Flask, request, send_from_directory, url_for
import time
import subprocess
import os
from pathlib import Path
import shutil

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
MARKDOWN_DIR = BASE_DIR / "markdown"
HTML_DIR = BASE_DIR / "static" / "html"


def find_markmap_cli():
    """查找项目本地或系统中的 Markmap CLI。"""
    configured = os.getenv("MARKMAP_CLI")
    candidates = [
        Path(configured) if configured else None,
        BASE_DIR / "node_modules" / ".bin" / "markmap.cmd",
        BASE_DIR / "node_modules" / ".bin" / "markmap",
    ]

    for candidate in candidates:
        if candidate and candidate.is_file():
            return str(candidate)

    system_cli = shutil.which("markmap.cmd") or shutil.which("markmap")
    if system_cli:
        return system_cli

    raise FileNotFoundError(
        "未找到 Markmap CLI。请在服务目录运行 npm.cmd install。"
    )


# 测试根路径
@app.route('/')
def index():
    return "Flask server is running!"


# 上传并处理Markdown文件的路径
@app.route('/upload', methods=['POST'])
def upload_markdown():
    content = request.get_data(as_text=True)
    time_name = str(int(time.time()))  # 生成时间戳作为文件名
    md_file_name = time_name + ".md"  # Markdown文件名
    html_file_name = time_name + ".html"  # HTML文件名

    # 创建 markdown 和 html 文件夹。
    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    md_file_path = MARKDOWN_DIR / md_file_name
    html_file_path = HTML_DIR / html_file_name

    # 将Markdown内容写入文件
    with md_file_path.open("w", encoding="utf-8", newline="") as f:
        f.write(content)

    app.logger.info("Markdown file created: %s", md_file_path)

    # 使用subprocess调用markmap-cli将Markdown转换为HTML，并移动到static/html目录
    try:
        markmap_cli = find_markmap_cli()
        result = subprocess.run(
            [
                markmap_cli,
                str(md_file_path),
                "--no-open",
                "--output",
                str(html_file_path),
            ],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout,
                                                stderr=result.stderr)

        if not html_file_path.is_file():
            raise RuntimeError("Markmap CLI 执行成功，但没有生成 HTML 文件")

        app.logger.info("HTML file created: %s", html_file_path)

        # 返回转换后的HTML文件链接
        return f'Markdown文件已保存. 点击预览: {url_for("get_html", filename=html_file_name, _external=True)}'
    except subprocess.CalledProcessError as e:
        # 如果转换过程中出现错误，返回错误信息
        return f"Error generating HTML file: {e.output}\n{e.stderr}", 500
    except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as e:
        app.logger.exception("Error generating Markmap HTML")
        return f"Error generating HTML file: {e}", 500


# 提供HTML文件的路径
@app.route('/html/<filename>')
def get_html(filename):
    return send_from_directory(HTML_DIR, filename)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5002, debug=True)
