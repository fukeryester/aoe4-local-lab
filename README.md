# AoE4 Local Lab

Windows 上的 AoE IV 本机单人对局分析工具：只读采集实体、玩家颜色和相机信息，显示单位名称覆盖层，并提供可编辑名称表。

## 快速安装

新增辅助功能请下载 [v1.1.0-preview.1](https://github.com/fukeryester/aoe4-local-lab/releases/tag/v1.1.0-preview.1) 的 `AoE4LocalLab-v1.1.0-preview.1-portable.zip`，解压后运行 `AoE4LocalLab-preview.exe`。无需安装 Python。建议解压到新文件夹；升级已有安装时只替换程序和说明，不覆盖自己的 `config/`。

预览版支持屏蔽自己、按玩家断农提醒、近满人口提醒、实时分数、军事统计和敌军数量阈值提醒。自动造农、受袭撤离只有离线决策逻辑，执行器尚未接通，界面禁用。提醒是工具覆盖层；人口预警按现人口判断。详细验证范围见 [辅助功能适配记录](docs/ASSISTANCE_WIP.md)。

从本仓库 Releases 下载 `AoE4LocalLab-portable.zip`，解压到可写目录（例如 G 盘）。双击 `AoE4LocalLab.exe`。保留整个文件夹即可迁移配置，无需安装 Python。

上述不带版本号的便携包为 v1.0.0，保留原有名称覆盖层功能，不含新增辅助功能。

启动游戏并进入本机单人对局，使用窗口化或无边框模式。工具会检查游戏版本，切回游戏后显示标签。菜单或加载期间可能显示读取错误，进入有效对局后自动重连。

## 自定义单位名称

点击“单位名称配置”，双击“自定义名称”编辑，点击“保存并应用”。支持搜索、备注、手动新增蓝图，以及 CSV 导出到 Excel 编辑后导入。清空自定义名称恢复默认。完整蓝图精确匹配；不同文明、等级分别配置。同一蓝图的己方、队友和对手共用名称。

程序自动收集遇到的蓝图，配置窗口可通过“收集当前对局”刷新。仓库包含上传时的名称配置快照。

## 文件与存储

- `source/`：Python 源码及测试。
- `config/unit_names.json`：已有单位名称配置。
- `config/settings.json`：采样和界面设置。
- `docs/AI_SETUP.md`：给 AI 使用的安装、构建、验证指南。
- `docs/USAGE.md`：详细使用说明。
- `AGENTS.md`：AI 修改代码前应阅读的约束。

EXE 使用其所在目录下的 `config/`，配置和日志不再写入 AppData。源码运行使用 `source/config/`；首次运行前可将根目录 `config/` 复制到那里。两种运行方式的配置独立，不会自动双向同步。

## 源码运行与构建

Windows x64，已验证 Python 3.12（包含 tkinter）。运行无需第三方库。

```powershell
Copy-Item -Path .\config -Destination .\source\config -Recurse
Set-Location .\source
python app.py
python -m unittest discover -p 'test_*.py'
```

仅在 `source/config` 尚不存在时执行上述复制，避免覆盖已有配置。

构建 EXE：在仓库根目录运行 `./build.ps1`，产物位于 `dist/`。研究脚本 `source/research.py` 另外需要 Capstone，不参与应用运行与打包。

## 适配及验证范围

适配游戏版本：17.0.12182.0。
游戏 EXE SHA-256：`4c99b868cbec98b2219e135908a31d03c64c7b71f2bbcf1469dab1d7c6df2c9f`。
版本不匹配会拒绝读取。不要跳过校验后沿用旧偏移。

已有本机单人对局的实体采集、颜色、投影与覆盖层验证；名称配置通过界面保存和重启读取验证。45 项自动测试通过。新增辅助的数据及面板已在本机单人对局验证，但敌军 26/51/101 阈值和近满人口提醒尚未完成实机触发验证。多人、其他版本、大规模后期、驻军及运输状态未全面验证。

上传不包含游戏文件、内存转储或本机日志。
