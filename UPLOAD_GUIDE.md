# 上传到 GitHub · 操作手册

本仓库已在本地初始化并完成首次提交（分支 `main`、1 个 commit）。
按下面任一种方式推送到 GitHub 即可。

---

## 方式 A：命令行（推荐，可控）

### 1. 在 GitHub 网页创建空仓库

打开 https://github.com/new

- **Repository name**：`filename-stats`（或你喜欢的名字，如 `file-name-stat`）
- **Description**：`把格式化文件名批量提取成表格，一键粘贴进 Excel。不写正则、AI 辅助、中文友好`
- **Public / Private**：按需（含私人预设逻辑，建议先 Private）
- **不要**勾选 "Add a README file / .gitignore / license"（本地已有，避免冲突）
- 点 **Create repository**

### 2. 关联远程并推送

在 `F:\Wider\文件统计\` 下执行（把 `<你的用户名>` 和 `<仓库名>` 换成实际的）：

```powershell
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git branch -M main
git push -u origin main
```

推送时会弹窗要求登录（浏览器授权或填 Personal Access Token）。

> 若提示要 token：GitHub → Settings → Developer settings → Personal access tokens →
> Fine-grained tokens，勾选该仓库的 **Contents: Read and write**，用 token 当密码。

---

## 方式 B：网页上传（不想用命令行时）

1. 在 GitHub 新建空仓库（同上，不勾任何初始化选项）。
2. 打开仓库页 → **Add file → Upload files**。
3. 把 `F:\Wider\文件统计\` 下这些内容拖进去（**保持目录结构**）：
   - `.gitignore`
   - `LICENSE`
   - `README.md`
   - `build/`（含 `build.py`、`build.bat`、`src/` 全部 .py）
   - `assets/`（若有）
4. **不要**上传：`output/`、`build/python/`、`build/_tmp/`、`config.json`、`*.zip`、`__pycache__/`。

---

## 上传前自检（已完成）

- [x] `.gitignore` 忽略：`output/`、`build/python/`、`build/_tmp/`、`config.json`、
      `presets.json`、`ai_config.json`、`*.json.bak`、`*.spec`、`__pycache__/`、`*.pyc`、`*.zip`
- [x] 已确认仓库内**不含** `config.json`（里面有明文 api_key）
- [x] 已确认源码里**未硬编码**任何 `sk-` 开头的密钥
- [x] 已添加 `LICENSE`（MIT）
- [x] 已添加 `.gitignore`
- [x] 首次提交已生成

---

## 可选：发布可下载的 exe（Release）

仓库里不放大文件（exe 各 9~13MB）。想让人直接下载 exe，用 **Release**：

1. 仓库 → 右侧 **Releases → Create a new release**
2. **Choose a tag**：填 `v1.0.0` → **Create new tag**
3. **Release title**：`v1.0.0`
4. 描述里写更新说明；把 `output\文件名统计.exe`、`output\文件名统计_cli.exe`
   拖到 **Attach binaries** 区域
5. **Publish release**

之后把 Release 链接贴进 README 的「下载」一节即可。

---

## 可选：完善仓库信息

- **Topics**（仓库主页右上齿轮）：`windows` `excel` `filename` `regex` `tkinter`
  `chinese` `batch-rename` `csv-export` `ai`
- **About → Description**：写一句定位（见上）
- **Social preview**：上传一张截图（可在 `assets/` 下放 `screenshot.png` 并在 README 引用）

---

## 后续日常更新

```powershell
cd F:\Wider\文件统计
git add -A
git commit -m "描述这次改了什么"
git push
```

> 注意：每次在 `build/` 下构建后，`output/` 与 `build/python/` 会变化，
> 但它们已被忽略，不会误传。
