# Samples

真实评估样本建议按一个样本一个目录组织，例如：

```text
evaluation/samples/
├── animation_short/
│   ├── video.mp4
│   ├── manifest.json
│   └── notes.md
├── microfilm_dialogue/
│   ├── video.mp4
│   ├── manifest.json
│   └── notes.md
```

每个样本建议至少补齐：

- 原始视频或其受控引用
- 运行后的 manifest
- 场景标签：`hard_cut`、`dissolve`、`fade`、`flash_false_positive`、`long_scene`
- 人工评审备注：漏切、碎切、错类型、切点偏早/偏晚

当前仓库还没有提交真实样本，本目录先作为占位结构保留。
