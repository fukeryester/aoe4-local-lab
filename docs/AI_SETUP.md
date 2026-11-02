# AI 安装与维护指南

## 安装已编译版本
1. 从当前仓库 Release 下载便携 ZIP，并解压到用户指定的可写目录。
2. 检查 ZIP 中包含程序 EXE、config/unit_names.json、使用说明.txt。v1.1.0-preview.1 程序名为 AoE4LocalLab-preview.exe；v1.0.0 和默认源码构建为 AoE4LocalLab.exe。
3. 启动前保留已有 config；升级时更新 EXE，不覆盖用户名称配置。
4. 运行 EXE。配置路径基于 EXE 所在目录，不依赖当前工作目录。
5. 进入适配版本的本机单人对局，检查连接状态与实体列表；游戏菜单期间不应以读取失败判定安装失败。

## 从源码运行
1. Windows x64；检查 `python --version`、`python -c "import tkinter"`。
2. app.py 及其运行模块仅依赖 Python 标准库。
3. 工作目录切换到 source，运行 `python app.py`。
4. source/config 为源码运行的数据目录。若需要根目录配置，首次运行前复制，已有目录不覆盖。
5. 在 source 下运行 `python -m unittest discover -p 'test_*.py'`，当前应通过 45 项。

## 2026-11-02 辅助功能预览

新增辅助发布为 `v1.1.0-preview.1` 预发布包，解压后运行 `AoE4LocalLab-preview.exe`，使用同级 `config/`。开发机上对应 `preview/AoE4LocalLab-preview.exe` 和 `preview/config`，与根目录正式版配置相互独立。源码的新采集适配在 `source/live_assistance.py`。详细实机结果与未完成项见 [ASSISTANCE_WIP.md](ASSISTANCE_WIP.md)。v1.0.0 Release 不含新增辅助功能。

屏蔽自己、断农提醒、人口容量读取、实时分数、军事价值/军事人口/存活军数已接入实机数据。自动造农和撤离尚无已验证执行器；界面明确禁用，不能仅因存在离线决策器就宣称已实现。人口预警暂按现人口判断，不包含未验证的排队人口预测。

## 构建与分发
仓库根目录执行 `powershell -ExecutionPolicy Bypass -File .\build.ps1`，仅为该次脚本执行指定策略，不修改系统设置。
脚本创建独立 .venv，安装固定 PyInstaller 版本，输出 dist/AoE4LocalLab.exe；只复制不存在的 unit_names.json/settings.json，并附带 docs、AGENTS.md 和说明，不覆盖目标已有配置。
分发使用新建暂存目录，只打包 EXE、config 中的两个 JSON、README.md、AGENTS.md、docs 中的说明及使用说明.txt。旧 dist 可能包含运行日志，不能未经检查整体上传。不要加入日志、游戏可执行文件、游戏资源、进程内存转储、认证凭据。

## 功能验证
- 名称表按完整 blueprint 精确匹配；默认别名是回退值。
- 更改一行并保存，检查 config/unit_names.json；重新打开程序确认保留。
- CSV 往返应保留中文、引号、逗号；重复蓝图或格式错误应拒绝整次导入。
- 实机验证应在用户明确提供的本机测试对局中进行；没有运行中的对局时只报告离线验证。
- 采样间隔 20–2000 ms；相机约 30 Hz。不要把采样间隔误认为覆盖层 FPS。

## 故障排查
- 版本哈希不匹配：需要重新研究并验证版本适配，不能禁用检查。
- 菜单/切换对局期间读取失败：等待进入有效对局；检查 config/lab.log。
- 无标签：检查游戏是否前台、画面标签开关、玩家筛选、窗口模式。
- 名称无变化：检查完整蓝图键、保存并应用，以及是否选择了完整蓝图显示模式。
- 配置损坏：备份原文件再修复 JSON；不要删除用户配置或用默认数据覆盖。
- 文件不可写：使用用户可写目录。不要回退到 C 盘 AppData。

当前运行时不会从旧 AppData 自动迁移；需要迁移时显式复制旧配置，并且不得覆盖较新的目标配置。
