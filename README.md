# AI精准施肥决策系统

PyQt6 桌面应用框架，包含登录注册、九个业务菜单、SQLite 数据持久化、热更新监听和可扩展的精准施肥核心算法。

## 启动

```bash
source .venv/bin/activate
python app.py
```

首次启动会自动创建 `data/fertilizer_ai.db`，默认管理员账号：

- 用户名：`admin`
- 密码：`admin123`

## 结构

- `fertilizer_ai/core/`：施肥决策算法、热更新、模型
- `fertilizer_ai/data/`：SQLite 仓库和初始化数据
- `fertilizer_ai/ui/`：登录注册、主窗口、通用控件
- `fertilizer_ai/modules/`：九个菜单页，每个菜单一个文件

## GitHub Actions 打包

推送到 `main` 或 `master` 分支后，会自动运行 `.github/workflows/windows-installer.yml`。

流水线会在 Windows 环境中完成：

```text
安装 Python 3.12
安装 requirements.txt
编译检查
PyInstaller 生成桌面程序
Inno Setup 生成 Windows 安装包
上传 Actions 产物
```

打包完成后，在 GitHub 仓库页面进入：

```text
Actions -> Windows 安装包 -> 最近一次运行 -> Artifacts
```

下载 `AI精准施肥决策系统-Windows安装包`，里面就是可安装到 Windows 电脑上的 `.exe` 安装包。
