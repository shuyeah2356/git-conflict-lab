# git-conflict-lab

Git 合并冲突实验仓库，支持以下能力：

- 多文件冲突制造（含几十文件）
- 自动批量修复冲突
- Git 历史冲突热点分析
- 冲突风险预测
- CI 自动检测冲突标记

## 一键制造冲突（创建不同分支）

在仓库根目录执行：

```bash
python tools/conflict_lab.py generate --count 30 --base-branch main --left-branch conflict-left --right-branch conflict-right
```

说明：
- 会在 `main` 写入基础文件并提交
- 创建 `conflict-left` 和 `conflict-right` 两个分支并各自修改同一批文件
- 在 `conflict-right` 合并 `conflict-left`，制造几十文件冲突

## 自动批量修复

```bash
python tools/conflict_lab.py autoresolve --strategy union --stage
```

可选策略：
- `ours`: 保留当前分支版本
- `theirs`: 保留被合并分支版本
- `union`: 合并保留双方非重复行

## 冲突检测

```bash
python tools/conflict_lab.py detect
```

## Git 历史分析

```bash
python tools/conflict_lab.py history --days 90 --top 10
```

## 冲突预测

```bash
python tools/conflict_lab.py predict --days 90 --top 10
```

## CI 自动处理（检测）

已配置 GitHub Actions：`.github/workflows/conflict-ci.yml`

- 每次 push / pull request 自动执行 `python tools/conflict_lab.py ci-check`
- 若存在冲突标记（`<<<<<<<`, `=======`, `>>>>>>>`），CI 失败
