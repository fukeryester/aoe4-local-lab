# AI 协作约束

先阅读 README.md 和 docs/AI_SETUP.md。

- 运行环境是 Windows x64，Python 3.12，Tk UI。
- 只读采集；保留版本哈希检查和无效容器检查。
- 不修改游戏文件或内存，不注入 DLL，不调用游戏内部函数。
- 配置始终相对于程序目录。打包后依据 sys.executable，源码依据 __file__；不要使用 PyInstaller 临时解压目录或当前工作目录。
- unit_names.json 是用户数据：保留自定义名称、备注和未知蓝图；原子保存，损坏配置不静默覆盖。
- 修改名称逻辑后运行 source 下的 test_lab.py 和 test_unit_names.py。
- 没有实机对局验证时明确标注，不用模拟数据冒充真实采集结果。
- 不提交 config/lab.log、进程转储、游戏文件、凭据或本地虚拟环境。
- 发布前区分源码、便携运行包和用户配置；升级不得覆盖现有配置。
