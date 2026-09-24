# github-auto

一个面向多 GitHub 账号的本地自动化 CLI。

## 特性

- 多 GitHub 账号配置
- 修改仓库描述/可见性
- 使用 `keyring` 保存 Token，不写入 YAML
- 每个账号独立 SSH Key / Host
- 创建 GitHub Repository
- 自动生成 README
- 自动初始化本地 Git
- 自动绑定 SSH remote
- 自动 commit / push
- push 前校验 GitHub 身份，降低多账号误推送风险
- 支持 Windows / macOS / Linux

## 环境要求

- Python 3.10+
- Git
- GitHub CLI `gh`
- GitHub 账号
- 每个账号建议配置独立 SSH Key

安装：

```bash
pip install -e .
```

初始化配置：

```bash
 --ssh-key ~/.ssh/id_ed25519_github_a
github-auto account add account_b --username another --email another@example.com
```

登录 GitHub CLI：

```bash
gh auth login
```

验证：

```bash
github-auto account verify account_a
```

创建并推送：

```bash
github-auto repo create test --account account_a --public --readme --push
```

## SSH 配置

程序会维护 `~/.ssh/config` 中由 `github-auto` 管理的区块，例如：

```sshconfig
# BEGIN github-auto account_a
Host github-account-a
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_github_a
    IdentitiesOnly yes
# END github-auto account_a
```

因此不同项目可以使用：

```text
git@github-account-a:owner/repo.git
git@github-account-b:owner/repo.git
```

而不需要不断修改全局 SSH Key。

## Token

Token 不保存在配置文件中。可以通过：

```bash
github-auto auth token-set account_a
```

交互式输入 Token。

程序优先使用：

1. `GH_TOKEN_<ACCOUNT>` 环境变量
2. keyring
3. 当前 `gh` 登录状态

> 如果使用 `gh` 创建仓库，实际认证由 GitHub CLI 管理；如果使用 Token API，则需要给对应 Token 足够的 Repository 权限。

## 配置文件

默认：

- Windows: `%APPDATA%\github-auto\config.yaml`
- macOS/Linux: `~/.config/github-auto/config.yaml`

也可以设置：

```bash
GITHUB_AUTO_CONFIG=/path/to/config.yaml
```

## 常用命令

```bash
github-auto account list
github-auto account current
github-auto account use account_a
github-auto account verify account_a
github-auto account add account_a --username user --email user@example.com
github-auto account remove account_a

github-auto ssh setup account_a
github-auto auth token-set account_a
github-auto auth token-delete account_a

github-auto repo create my-project --account account_a --public
github-auto repo list --account account_a
github-auto repo info owner/repo --account account_a
github-auto repo edit owner/repo --account account_a --description "new description"
github-auto repo clone owner/repo --account account_a
github-auto repo delete owner/repo --account account_a
github-auto repo star owner/repo --account account_a
github-auto repo star owner/repo --account account_a --unstar
github-auto repo fork owner/repo --account account_a
github-auto repo watch owner/repo --account account_a
github-auto repo watch owner/repo --account account_a --unwatch
github-auto repo search "keyword" --account account_a --limit 10
github-auto repo browse owner/repo --account account_a
github-auto repo browse owner/repo/src --account account_a
github-auto repo download owner/repo --account account_a --branch main
github-auto repo download owner/repo --account account_a --output ./download.zip

github-auto user info username --account account_a
github-auto user follow username --account account_a
github-auto user follow username --account account_a --unfollow
github-auto user followers username --account account_a
github-auto user following username --account account_a

github-auto git push --account account_a
```

## 注意

删除 Repository 是不可逆操作，CLI 会要求确认；可以使用 `--yes` 跳过交互确认。

本项目不绕过 GitHub 的认证、权限或风控机制，仅使用 GitHub CLI、Git、SSH 和官方 API。

## 防封号机制

为防止操作过快触发 GitHub 风控，所有 API 请求都会添加随机延迟：

### 高风险操作（写操作）
- `repo star` - 点赞/取消点赞：延迟 5-65 秒
- `repo fork` - Fork 仓库：延迟 5-65 秒
- `repo watch` - Watch/取消 Watch：延迟 5-65 秒
- `repo delete` - 删除仓库：延迟 5-65 秒
- `repo edit` - 编辑仓库：延迟 5-65 秒
- `user follow` - 关注/取消关注用户：延迟 5-65 秒

### 低风险操作（读操作）
- `repo list/info/browse/search` - 列表/详情/浏览/搜索：延迟 2-10 秒
- `user info/followers/following` - 用户信息/粉丝/关注：延迟 2-10 秒

延迟公式：`sleep(base + random(0, spread))`

github-auto account add account_a --username yourname --email you@example.com