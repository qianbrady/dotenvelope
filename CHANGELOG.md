# Changelog

## v0.1.0 — 2026-08-26

First release.

### Added

- `audit` 子命令：比对 `.env.example` 与代码实读环境变量，输出三类清单
  （缺文档 undocumented / 僵尸 zombie / 默认值缺失风险 no-default）与
  0-100 健康分；退出码 0/1/2。
- `sync` 子命令：把代码里缺文档的变量补进 `.env.example`，
  `--yes` 跳过确认；文件不存在时自动创建。
- 源码扫描：Python 用标准库 `ast` 解析（`os.environ.get` / `os.environ[...]` /
  `os.getenv`，注释与字符串字面量不误报），Node 用行级正则
  （`process.env.X` / `process.env['X']`，`//` 与 `/* */` 注释先屏蔽）；
  自动跳过 `node_modules` / `.venv` / `__pycache__` 等目录。
- 确定性输出：所有清单按字典序，重复运行结果一致。
- 健壮性：main() 入口重配置 stdio 为 UTF-8（GBK 控制台不崩溃）；
  源码按 UTF-8 + `errors="replace"` 读取；`.env.example` 自动剥离 UTF-8 BOM。
- 测试：34 例（Python/JS 扫描、三方比对分类、健康分公式、确定性、
  GBK 冒烟、BOM、排除目录、cli 退出码）。