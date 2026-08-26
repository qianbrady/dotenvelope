# dotenvelope

[![CI](https://github.com/qianbrady/dotenvelope/actions/workflows/ci.yml/badge.svg)](https://github.com/qianbrady/dotenvelope/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
> Check your `.env.example` against what your code *actually reads* — undocumented, zombie, and no-default variables in one pass.

纯标准库（Python ≥ 3.10）的环境变量审计器：比对 `.env.example` ↔ 代码实际读取 ↔ 运行时默认值兜底，输出**缺文档变量 / 僵尸变量 / 默认值缺失风险**三类清单与 0-100 健康分。支持 Python 与 Node 项目。

## 为什么需要它

`.env.example` 是团队约定的配置清单，但没人保证它跟代码同步：

- 新人加了 `os.getenv("NEW_FLAG")` 忘了写进 `.env.example` → **部署时静默缺失**；
- 半年前删掉的旧配置还躺在 `.env.example` 里 → **误导新人填一堆没用的值**；
- 代码用 `os.environ["X"]` / `process.env.X` 无兜底读取 → **变量未设置时直接 KeyError / undefined**。

dotenvelope 把这三类问题一次扫出来，并给出健康分。

## 安装与使用

无需安装依赖（标准库），克隆后直接跑：

```bash
# 审计当前位置的项目
python -m dotenvelope audit

# 审计指定路径
python -m dotenvelope audit --path /path/to/project

# 把代码里缺文档的变量补进 .env.example（--yes 跳过确认）
python -m dotenvelope sync --path /path/to/project --yes
```

### 输出示例

```
dotenvelope audit v0.1.0
路径: D:\earn money\001\.build-tmp\demo-proj
扫描: 2 个源码文件, 跳过 0 个目录
.env.example: 存在 (4 个变量)

[缺文档变量 undocumented] 2
  HOST
    web/server.js:2  process.env.X
  SECRET_KEY
    app/main.py:5  os.environ[...]

[僵尸变量 zombie] 1
  OLD_FLAG

[默认值缺失风险 no-default] 2
  HOST
    web/server.js:2  process.env.X
  SECRET_KEY
    app/main.py:5  os.environ[...]

健康分: 60/100
总结: 存在 5 个问题 (发现 2 个缺文档变量, 1 个僵尸变量, 2 个默认值缺失)。
```

### 三类问题

| 类别 | 判定 | 后果 |
|---|---|---|
| **缺文档** undocumented | 代码里读取了（`os.environ`/`os.getenv`/`process.env`），`.env.example` 里没有 | 新配置没有被文档化，部署环境可能缺失 |
| **僵尸** zombie | `.env.example` 里有，代码里从未读取 | 文档误导；清理后更易维护 |
| **默认值缺失** no-default | 代码以无兜底方式读取（`os.environ['X']`、单参 `os.getenv('X')`、裸 `process.env.X`） | 变量未设置时抛 `KeyError` / 得 `None` / `undefined` |

### 健康分公式

起始 100 分，逐一扣减（下限 0，确定性输出）：

| 问题 | 扣分 |
|---|---|
| 每个缺文档变量 | −12 |
| 每个僵尸变量 | −4 |
| 每个默认值缺失 | −6 |

### 退出码

| 码 | 含义 |
|---|---|
| 0 | 审计干净 / sync 完成 |
| 1 | 发现问题 / 路径无效 / sync 被取消 |
| 2 | 用法错误（argparse） |

## 扫描规则与局限

- **语言**：Python（`os.environ.get` / `os.environ[...]` / `os.getenv`，`.py/.pyw/.pyi`，标准库 AST 解析，**注释/docstring/字符串字面量不误报**）、Node（`process.env.X` / `process.env['X']`，`.js/.mjs/.cjs/.jsx/.ts/.tsx`，`//` 与 `/* */` 注释先屏蔽）；
- **默认值判定**：`.get(KEY, fallback)`、`os.getenv(KEY, fallback)`、`process.env.X || v`、`process.env.X ?? v` 视为有兜底；
- **排除目录**：`node_modules`、`.venv`/`venv`、`__pycache__`、`.git`、`dist`、`build` 等，以及所有 `.` 开头的目录；
- **编码**：源码按 UTF-8 读取、`errors="replace"`，GBK 等遗留编码不会崩溃；
- **已知局限**：动态访问（`os.environ.get(os.environ["A"])`、展开 `process.env`、拼接变量名）不可见，此类变量应保留在 `.env.example` 中；`import os as x` 别名不识别。

## 与 dotenv-linter 的差异

[dotenv-linter](https://github.com/dotenv-linter/dotenv-linter)（Rust）检查的是 【`.env` 文件内部的格式错误】——键重复、大小写、引号、空白、分隔符、排序……这些都能在文件自身内发现。

dotenvelope 查的是【“文档 ↔ 代码 ↔ 运行环境”三方一致性】：文档声明的变量是否真的被代码使用、代码读取的变量是否被文档覆盖、读取时有没有默认值兜底。两工具互补：dotenv-linter 管单文件格式，dotenvelope 管跨文件契约。

| 维度 | dotenv-linter | dotenvelope |
|---|---|---|
| 检查对象 | `.env` 文件内部 | `.env.example` ↔ 源码 ↔ 运行时 |
| 语言 | 任意（文件层） | Python / Node（代码层） |
| 缺文档变量 | 不涉及 | ✅ 代码有、文档无 |
| 僵尸变量 | 不涉及 | ✅ 文档有、代码无 |
| 默认值缺失 | 不涉及 | ✅ 无兜底读取 |
| 健康分 | 无 | ✅ 0-100 |
| 自动补文档 | 无（`fix` 修格式） | ✅ `sync` 补进 `.env.example` |

## 开发

```bash
# 全部测试（标准库 unittest）
python -m unittest discover -s tests -q
```

## 许可

MIT © 2025 ox-alpha。详见 [LICENSE](LICENSE)。