# Evaluation

本目录用于承载 V1 的最小评估集、样本清单和 baseline 报告。

当前约定：

- `sample-set.v1.json`
  记录样本清单和覆盖标签
- `baseline.example.json`
  基于当前示例 manifest 生成的最小 baseline 快照
- `baseline.example.md`
  供终端和文档快速阅读的 Markdown 版 baseline
- `samples/`
  未来放真实评估素材、标注说明和辅助文档
- `runs/`
  存放真实视频或专项验证的运行产物、日志和报告

当前仓库尚未提交真实视频素材，因此第一版 baseline 先基于
`examples/manifest.v1.example.json` 建立参考记录。

`runs/` 目录默认用于本地真实视频验证，不作为稳定样例提交。
如果某次验证需要长期保留，建议将结论提炼成文档或脚本，再提交到仓库。
