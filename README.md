# 567 Agent Style Library

567 Agent 的统一设计风格目录。应用读取本仓库的一个 catalog；本仓库每天导入两路上游，保留风格文本、配色、必要的静态资源与 attribution。

上游为 [Vetta Design Templates](https://github.com/openvetta/vetta-design-templates) 和 [StyleKit](https://github.com/AnxForever/stylekit)。Vetta 的 raw 与 jsDelivr 地址只是同一目录的镜像回退，始终只产生一份条目。StyleKit 优先读取 `https://stylekit.top/api/styles`；API 不可用或格式校验失败时，安全解析固定版本仓库 `lib/styles/meta-registry.ts` 中的字面量数组，不执行 TypeScript、构建脚本或任何上游指令。SVG/JPEG 等封面从同一上游仓库的固定 commit 下载，不让客户端直连 StyleKit。

## 目录与读取地址

```text
.vetta/design-templates.json     统一 catalog（生成）
sources/vetta.json               Vetta 的最后成功快照、内容摘要、来源 revision
sources/stylekit.json            StyleKit 的最后成功快照、内容摘要、来源 revision
assets/stylekit/<slug>/cover.*   镜像 SVG/JPEG 等封面（生成）
assets/vetta/<slug>/...          上游有二进制资源时的镜像（生成）
licenses/*-MIT.txt               上游仓库完整 MIT 许可（生成）
ATTRIBUTION.md                  所有条目的许可、原始来源与改编说明（生成）
schema/catalog.schema.json       schemaVersion 1 的机器可读合同
docs/catalog-contract.md         客户端接入与缓存迁移合同
scripts/sync.py                  只依赖 Python 标准库的同步器
tests/test_sync.py               无网络的合同与恢复测试
```

审阅并推送到 `main` 后的客户端读取地址：

- 首选：[GitHub raw catalog](https://raw.githubusercontent.com/Chinachani/567-agent-style-library/main/.vetta/design-templates.json)
- 同源镜像回退：[jsDelivr catalog](https://cdn.jsdelivr.net/gh/Chinachani/567-agent-style-library@main/.vetta/design-templates.json)
- 仓库根地址分别为 `https://raw.githubusercontent.com/Chinachani/567-agent-style-library/main/` 与 `https://cdn.jsdelivr.net/gh/Chinachani/567-agent-style-library@main/`。资源 URL 相对仓库根解析，不相对 `.vetta/` 解析。

这些地址在首次推送前不会提供新目录。jsDelivr 的浮动分支缓存可能滞后，客户端应优先 raw 并保留离线缓存。

初始快照（2026-10-06）：173 条风格 = 25 条 Vetta + 148 条 StyleKit；148 个镜像封面 = 145 个 SVG + 3 个 JPEG；170 条 MIT + 3 条 CC-BY-4.0。Vetta 上游 revision 为 `7a2a911660733647c12195a1a20bd36f0e2b99ce`，StyleKit 资源 revision 为 `0156849969ca108fbc82d9600b89577b2795a669`。后续快照以生成 catalog 和 `sources/` 为准。

## 本地操作

需要 Git 与 Python 3.12+，无需安装依赖、访问令牌或 npm 工具。

```bash
python3 -m unittest discover -s tests -v
python3 scripts/sync.py
python3 scripts/sync.py --check
```

`--check` 离线重建快照并核对 catalog、来源摘要、每个静态资源与 attribution；不写入仓库。禁止手工编辑生成文件。内容不变时同步器不重写文件，不记录运行时间，也不因上游无关 commit 更新而制造目录变更。`catalogVersion` 是内容 SHA-256，不是时间戳。

每路同步先完整验证，任何条目、资源或许可失败都保留该路最后成功快照；另一路仍可正常更新。所有来源第一次都成功后才生成首份目录。错误会输出到日志并以非零状态结束，避免故障被当成成功。单路故障时 Actions 可以提交另一条来源的有效更新，但整个 workflow 最终仍标为失败。空目录、冲突 id、未知许可、缺失规范/主题均不会替换最后可用数据。成功来源中已删除的条目和其镜像资源会被移除。

已导入的 id 保持稳定：旧 Vetta 使用原 `slug`，StyleKit 使用 `stylekit-<upstream-slug>`。同源完全相同的重复记录去重；相同 id 的冲突记录会失败。旧 Vetta 的改编版本与 StyleKit 原始风格可以同时存在，因为它们的规范、配色与许可不同，不能按名字误合并。

## GitHub Actions

`Sync upstream styles` 每日 UTC 19:17 运行，即北京时间次日 03:17；也可在 Actions 页面使用 **Run workflow** 手动触发。只在远端默认分支运行。调度时间是 GitHub 的预计执行时间，可能延迟；公开仓库长时间无活动后 GitHub 也可能停用定时任务，届时需在 Actions 页面重新启用。

同步 job 测试通过后导入，只暂存 `.vetta/`、`sources/`、`assets/`、`licenses/`、`ATTRIBUTION.md`，有实际 diff 才由 `github-actions[bot]` 提交并普通 push；不会 force push。并发组防止两个同步 run 相互覆盖。所有第三方 Actions 固定到 commit SHA。PR 检查只有读权限，并且不会联网导入或发布内容。

仓库设置需要：

1. 将审阅后的文件推送到默认分支 `main`；workflow 在本地尚未运行于 GitHub。
2. 启用 Actions，允许使用 `actions/checkout`（固定的 v4.2.2 commit）。
3. 允许同步 job 使用 `GITHUB_TOKEN` 的 `contents: write` 权限。若组织策略强制只读，需要管理员调整。无需自定义 secrets 或 repository variables；无需 PAT。
4. 若 `main` 保护规则/Ruleset 禁止 bot 直接提交或必须 PR，需为该同步 bot 配置允许的写入方式。本 workflow 不创建 PR、不绕过规则，也不使用高权限 PAT；普通 push 被拒时 run 会失败，用户可再选择允许该 bot 或调整 workflow。
5. 手动执行一次 `Sync upstream styles`，检查 bot push 权限与输出；确认后应用再切换读取 URL。可在个人通知设置中启用 Actions 失败通知。

## 许可与来源

本仓库同步工具为 MIT；导入内容遵循每条 `license`，不会被本仓库许可重新授权。Vetta 仓库与 StyleKit 仓库当前均声明 MIT，但旧 Vetta 的 `geometric-bold`、`claymorphism`、`glassmorphism` 条目单独声明 CC-BY-4.0，保持该标识与原始改编说明。初始 Vetta 条目来自 VoltAgent/awesome-design-md 时，其完整 MIT 通知也随参考包保留。

每条目录保留 `origin` 与 `provenance`，新增 `attribution`、`licenseUrl`，并内联 `567-ATTRIBUTION.md` 与 `567-LICENSE.txt` 两份资源。规范正文末尾也附带许可与 attribution，确保只拷贝 `DESIGN.md` 的客户端路径同样保留通知。CC-BY-4.0 条目保留原作者/来源链接、既有改编说明和许可链接；同步器附加自己所做的格式整理与镜像说明。参见 [ATTRIBUTION.md](ATTRIBUTION.md)。

同步器只处理数据与静态资源，限制大小、数量、文件类型、路径及下载/重定向目标；不运行下载的代码，不抓取 community submissions、用户内容、上游应用源码或安装包。SVG 的脚本、事件属性、外部引用和实体声明被拒绝。原有参考 HTML/CSS 只作为文本资料存储，导入过程不执行它们。
