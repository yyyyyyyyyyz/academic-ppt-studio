# 公开部署与持续更新指南（Academic Studio）

本工作台已采用 **单容器 + 单端口架构**（FastAPI 同时托管 `frontend/dist` 生产网页与全部 `/api/*` + RDKit / 原生 PPTX 编译引擎），支持以下 3 种主流零运维上线方式，并在你 `git push` 后自动更新线上网页。

---

## 一、先将项目推送到 GitHub

在仓库根目录 `D:\academic-ppt-design` 执行：

```powershell
git status
git add .
git commit -m "feat: add Nature showcase, 5 cover/closing templates, BYOK modal, and Docker deployment"
# 若尚未绑定 GitHub 远程仓库：
git remote add origin https://github.com/<你的用户名>/academic-ppt-studio.git
git branch -M main
git push -u origin main
```

---

## 二、选择上线平台（均支持绑定 GitHub 自动更新）

### 方案 A：Hugging Face Spaces（免费 2 核 16 GB 内存，推荐先试跑）
1. 登录 [huggingface.co/spaces](https://huggingface.co/spaces) → 点击 **Create new Space**。
2. Space SDK 选择 **Docker** → **Blank**，硬件选择免费 **CPU basic (2 vCPU · 16 GB)**。
3. 在 Space 仓库根目录创建一个带 YAML 头部的 `README.md`（或合并到你的仓库根目录）：
   ```yaml
   ---
   title: Academic PPT Studio
   emoji: 🧬
   colorFrom: red
   colorTo: indigo
   sdk: docker
   app_port: 7860
   ---
   ```
4. 将代码推送到 Space Git（或在 GitHub Actions 里同步推至 Space），构建完成后即获得公网 HTTPS 链接 `https://<用户名>-academic-ppt-studio.hf.space`。

### 方案 B：Zeabur / Railway / Render（国内直连体验更好，push 即发布）
- **Zeabur（国内访问快）**：登录 [zeabur.com](https://zeabur.com) → 新建项目 → Add Service → 选择 **GitHub** 仓库 `academic-ppt-studio` → Zeabur 会自动识别根目录 `Dockerfile`，绑定自动生成的域名或自己的域名即可。
- **Railway**：仓库已内置 [railway.json](file:///D:/academic-ppt-design/railway.json)，在 Railway 中直接 `Deploy from GitHub repo` 即可。
- **Render**：仓库已内置 [render.yaml](file:///D:/academic-ppt-design/render.yaml)，在 Render 点击 `New Blueprint Instance` 关联本仓库即可。

---

## 三、AI 模型与安全环境变量配置（可选）

每位访客都可以在网页右上角 **「AI 模型」** 填写自己的 DeepSeek / 通义千问 / Gemini Key（密钥仅保存在访客浏览器 `localStorage`，不落盘）。

如果你想为未配置 Key 的访客提供**默认公共 AI 文献解析能力**，可以在云平台后台设置以下环境变量：

| 变量名 | 说明 | 示例值 |
| :--- | :--- | :--- |
| `LLM_PROVIDER_MODE` | 文本规划策略 | `auto`（有 Key 用云端，无 Key 自动降级本地引擎） |
| `FIGURE_PROVIDER_MODE` | 绘图策略 | `local`（RDKit / 3D / 矢量图本地免费秒出） |
| `OPENAI_API_KEY` | 可选：DeepSeek / 通义 / OpenAI Key | `sk-...` |
| `OPENAI_BASE_URL` | 对应兼容接口地址 | `https://api.deepseek.com/v1` |
| `OPENAI_TEXT_MODEL` | 文本模型名 | `deepseek-chat` |
| `ALLOWED_ORIGINS` | 正式域名白名单 | `https://your-domain.com` |
| `DECK_TTL_HOURS` | 临时文稿自动清理时间（小时） | `24`（保留示范稿不受影响） |
| `MAX_UPLOAD_MB` | 单次文件上传体积上限（MB） | `20` |

---

## 四、后续如何不断优化与更新线上版本

1. 本地开发新功能（新分子画风、新催化机理图、排版微调或修复问题）。
2. 在本地跑一次完整自动化门禁测试：
   ```powershell
   D:\academic-ppt-design\backend\.venv\Scripts\python.exe -m pytest D:\academic-ppt-design\backend\tests -q
   ```
3. 提交并推送至 GitHub：
   ```powershell
   git add .
   git commit -m "chore: update mechanism figures"
   git push origin main
   ```
4. 云平台监听到 `main` 更新后会自动重新构建镜像并热切换，所有用户刷新浏览器即用到最新版。
