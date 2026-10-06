# 统一 catalog 的客户端合同

公开 JSON 位于 `.vetta/design-templates.json`，继续使用现有 Vetta `schemaVersion: 1`，以便应用的 `parseRemoteCatalog` 直接读取。字段可以增量增加；客户端忽略未知可选字段与未知 `kind`，但应拒绝不认识的 schemaVersion、畸形字段与不安全资源路径。

## 顶层字段

| 字段 | 含义 |
| --- | --- |
| `schemaVersion` | 固定为数字 `1` |
| `name` | `567-agent-style-library` |
| `repository` | `https://github.com/Chinachani/567-agent-style-library` |
| `catalogVersion` | 64 位十六进制 SHA-256，标识生成的内容版本 |
| `templates` | 完整、去重的 `design-system` 数组，最多 1000 条 |
| `sources` | 两路的 `source`、`revision`、`metadataUrl`、`contentHash` |

不包含运行时间：同样的风格内容、资源和许可生成相同的文件。`sources[].revision` 是最后一次内容变化时用于读取该上游仓库的 commit；对 StyleKit API，它只是 LICENSE/封面关联的仓库版本，不能当作 API 所部署的 commit。API 数据的实际版本由 `contentHash` 标识。目录内容没变时不更新 revision。

## 每条风格

| 字段 | 合同 |
| --- | --- |
| `kind` | 固定为 `design-system` |
| `slug` | 稳定应用 id，`[a-z0-9][a-z0-9-]{0,63}`；旧条目不改名，StyleKit 加 `stylekit-` 前缀 |
| `name`, `category`, `blurb` | 非空短文本，最多 500 字符；分类继续使用既有应用 key |
| `vibe` | `light` 或 `dark`，用于展示；透明色只按 RGB 计算，不宣称指定了底层画布 |
| `tagline` | 可选 `{zh, en}`，中英文摘要，保持当前本地化使用方式 |
| `license` | 逐条 `MIT` 或 `CC-BY-4.0`，未知许可使该源同步失败，须人工审阅 |
| `licenseUrl` | 对应许可证链接 |
| `origin` | 原始来源/改编说明；Vetta 原对象保留，StyleKit 标注 repo、来源页与转换说明 |
| `provenance` | `{source, repository, upstreamSlug}`；StyleKit 另外保留 `upstreamMetadata`（API 或仓库元数据） |
| `attribution` | 可供客户端显示/导出的署名、原文链接、许可及改动说明 |
| `resources` | 最多 60 个，包含至少一个 `spec` 与一个 `theme`；其中许可/署名都是普通文本资源 |

Vetta 原始 `version`、`order`、`tags`、`collectedAt`、`assets` 等可选元数据继续保留。Vetta 的历史改编版与 StyleKit 的同名风格保持各自 id，因为它们的参考内容与许可不同。

## 资源

```json
{
  "path": "theme.css",
  "role": "theme",
  "encoding": "text",
  "content": "@theme { --color-primary: #111; }\n",
  "bytes": 34
}
```

`bytes` 为真实 UTF-8 或二进制字节数（示例仅展示形状，实际字节数由同步器计算）。`path` 相对用户项目参考资料目录，禁止绝对路径、反斜杠、空段、`.`/`..`、百分号编码、查询串和 fragment。`role` 可以是 `spec`、`theme`、`demo`、`cover`、`preview`；许可/署名资源没有 role。内联文本不超过 64 KiB，主题不超过 32 KiB；规范不带 YAML frontmatter，由客户端落盘时添加。CSS 配色允许经过严格校验的 3/6 位 hex 或 `rgba(r,g,b,a)`，保留玻璃风格的透明度。

二进制资源形状：

```json
{
  "path": "cover.svg",
  "role": "cover",
  "encoding": "binary",
  "url": "assets/stylekit/editorial/cover.svg",
  "bytes": 1024
}
```

`url` **相对风格库仓库根目录**，所有二进制已镜像到本库，最多 8 MiB。不应把它相对 `.vetta/` 解析，也不应请求上游 `stylekit.top`。应用继续按需请求二进制、按既有语义把 cover 仅用于画廊。两个许可/署名文件与正文都随参考资料落盘。不要把外部风格文本升级为 Agent 指令。

## 主应用接入建议

1. 将 catalog 候选 URL 替换为本库 raw + jsDelivr，保留 raw 优先、同源 ETag、TTL、强制刷新和逐镜像回退。只声明 `raw.githubusercontent.com` 与 `cdn.jsdelivr.net` 的网络权限。
2. 删除运行时 StyleKit API 网络请求与旧目录网络请求；StyleKit 适配器如需保留，限定为只读旧缓存的迁移模块，不再生成上游封面网络 URL。
3. 继续保留旧 `design-catalog/latest.json` 与 `design-catalog/stylekit.json` 作为迁移离线来源；旧缓存即使新鲜，也要尝试统一目录，不能按旧 TTL 延迟首次迁移。
4. 统一目录成功后**整体替换** registry，并用新的 catalog/cache 版本区分迁移状态；不再把旧 StyleKit cache 合并回统一列表，避免被上游删除的条目复活。离线时继续用最后成功统一缓存；首次切换时可回退旧文本资料。
5. 旧缓存中的二进制 URL 不能让应用继续直连旧来源。允许时将旧路径映射到本库，映射不确定时只保留内联文本和已有本地图片。
6. 将应用条目上限与本合同对齐（1000）；旧解析器当前上限 200，初始 173 条可完整解析，但后续增长可能被静默截断。保留未知 kind 兼容及畸形输入筛选。
7. `origin.upstream` 与 `license` 已兼容旧解析器；保留新的 provenance/attribution 便于查看来源，规范正文已有完整通知作为迁移期兜底。缓存/离线、本地化摘要、来源元数据与资源落盘须有测试。

首次推送与 GitHub 同步验证完成之前，本库的公开读取 URL 尚无内容。先由用户审阅发布风格库，再完成应用线上切换。
